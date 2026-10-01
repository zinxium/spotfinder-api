import re
import shutil
import tempfile
from datetime import timedelta
from io import BytesIO, StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from PIL import Image
from rest_framework.test import APITestCase

from .models import Category, PasswordResetCode, Place, Review
from .views import AuthRateThrottle


PASSWORD = 'Sp0tF1nder!Secure'


def make_place(owner, **kwargs):
    data = dict(name='Chez Tonton', category='restaurant', city='Cotonou', latitude=6.36, longitude=2.42, owner=owner)
    data.update(kwargs)
    return Place.objects.create(**data)


class BaseAPITestCase(APITestCase):
    def setUp(self):
        # Les compteurs de limitation de débit sont stockés dans le cache
        cache.clear()
        self.alice = User.objects.create_user('alice', 'alice@example.com', PASSWORD)
        self.bob = User.objects.create_user('bob', 'bob@example.com', PASSWORD)

    def login(self, username='alice', password=PASSWORD):
        return self.client.post('/api/auth/login/', {'username': username, 'password': password}, format='json')

    def authenticate(self, username='alice'):
        tokens = self.login(username).data
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        return tokens


# ============================================
# TESTS: Authentification JWT
# ============================================
class AuthTests(BaseAPITestCase):
    def test_register_returns_jwt_pair(self):
        response = self.client.post('/api/auth/register/', {
            'username': 'carol', 'email': 'carol@example.com', 'password': PASSWORD,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['username'], 'carol')
        self.assertNotIn('password', response.data['user'])

    def test_register_rejects_weak_password(self):
        response = self.client.post('/api/auth/register/', {
            'username': 'carol', 'email': 'carol@example.com', 'password': '123456',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(username='carol').exists())

    def test_register_password_errors_are_attached_to_password_field(self):
        # Le client mobile affiche l'erreur sous le champ concerné
        response = self.client.post('/api/auth/register/', {
            'username': 'carol', 'email': 'carol@example.com', 'password': 'password123',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)
        self.assertNotIn('non_field_errors', response.data)

    def test_validation_messages_are_in_french(self):
        response = self.client.post('/api/auth/register/', {
            'username': 'carol', 'email': 'carol@example.com', 'password': 'password123',
        }, format='json')
        self.assertIn('Ce mot de passe est trop courant.', response.data['password'])
        # Messages intégrés de DRF également traduits
        response = self.client.post('/api/auth/register/', {}, format='json')
        self.assertEqual(response.data['username'], ['Ce champ est obligatoire.'])

    def test_register_rejects_duplicate_username_and_email(self):
        response = self.client.post('/api/auth/register/', {
            'username': 'ALICE', 'email': 'Alice@Example.com', 'password': PASSWORD,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)
        self.assertIn('email', response.data)

    def test_login_success(self):
        response = self.login()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_login_does_not_reveal_whether_user_exists(self):
        wrong_password = self.login(password='wrong-password')
        unknown_user = self.login(username='nobody')
        self.assertEqual(wrong_password.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(wrong_password.status_code, unknown_user.status_code)
        self.assertEqual(wrong_password.data, unknown_user.data)

    def test_access_token_grants_access(self):
        self.assertEqual(self.client.get('/api/favorites/').status_code, status.HTTP_401_UNAUTHORIZED)
        self.authenticate()
        self.assertEqual(self.client.get('/api/favorites/').status_code, status.HTTP_200_OK)

    def test_refresh_rotates_and_blacklists_old_token(self):
        refresh = self.login().data['refresh']
        response = self.client.post('/api/auth/refresh/', {'refresh': refresh}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotEqual(response.data['refresh'], refresh)
        # L'ancien refresh token ne peut plus être réutilisé
        reused = self.client.post('/api/auth/refresh/', {'refresh': refresh}, format='json')
        self.assertEqual(reused.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_revokes_refresh_token(self):
        tokens = self.authenticate()
        response = self.client.post('/api/auth/logout/', {'refresh': tokens['refresh']}, format='json')
        self.assertEqual(response.status_code, status.HTTP_205_RESET_CONTENT)
        reused = self.client.post('/api/auth/refresh/', {'refresh': tokens['refresh']}, format='json')
        self.assertEqual(reused.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_cannot_revoke_another_users_token(self):
        bob_refresh = self.login('bob').data['refresh']
        self.authenticate('alice')
        response = self.client.post('/api/auth/logout/', {'refresh': bob_refresh}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        still_valid = self.client.post('/api/auth/refresh/', {'refresh': bob_refresh}, format='json')
        self.assertEqual(still_valid.status_code, status.HTTP_200_OK)

    def test_login_is_rate_limited(self):
        with patch.object(AuthRateThrottle, 'THROTTLE_RATES', {'auth': '3/minute'}):
            codes = [self.login(password='wrong').status_code for _ in range(4)]
        self.assertEqual(codes[:3], [status.HTTP_400_BAD_REQUEST] * 3)
        self.assertEqual(codes[3], status.HTTP_429_TOO_MANY_REQUESTS)


# ============================================
# TESTS: Droits d'accès sur les ressources
# ============================================
class PermissionTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.place = make_place(self.alice)

    def test_places_are_publicly_readable(self):
        self.assertEqual(self.client.get('/api/places/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(f'/api/places/{self.place.id}/').status_code, status.HTTP_200_OK)

    def test_anonymous_cannot_create_place(self):
        response = self.client.post('/api/places/', {'name': 'X'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_owner_and_rating_cannot_be_forged(self):
        self.authenticate('bob')
        response = self.client.post('/api/places/', {
            'name': 'Maquis', 'category': 'bar', 'city': 'Cotonou', 'latitude': 6.3, 'longitude': 2.4,
            'owner': self.alice.id, 'rating': 5,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        place = Place.objects.get(id=response.data['id'])
        self.assertEqual(place.owner, self.bob)
        self.assertEqual(place.rating, 0)

    def test_non_owner_cannot_modify_or_delete_place(self):
        self.authenticate('bob')
        response = self.client.patch(f'/api/places/{self.place.id}/', {'name': 'Hacked'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        response = self.client.delete(f'/api/places/{self.place.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Place.objects.filter(id=self.place.id).exists())

    def test_owner_can_modify_place(self):
        self.authenticate('alice')
        response = self.client.patch(f'/api/places/{self.place.id}/', {'name': 'Chez Tata'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_owner_can_review_and_favorite(self):
        self.authenticate('bob')
        review = self.client.post(f'/api/places/{self.place.id}/add_review/', {'rating': 4, 'comment': 'Top'}, format='json')
        self.assertEqual(review.status_code, status.HTTP_201_CREATED)
        favorite = self.client.post(f'/api/places/{self.place.id}/favorite/')
        self.assertEqual(favorite.status_code, status.HTTP_201_CREATED)
        self.place.refresh_from_db()
        self.assertEqual(self.place.rating, 4)

    def test_add_review_rejects_invalid_rating(self):
        self.authenticate('bob')
        response = self.client.post(f'/api/places/{self.place.id}/add_review/', {'rating': 42, 'comment': 'x'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_author_cannot_modify_review(self):
        review = Review.objects.create(place=self.place, user=self.alice, rating=5, comment='Super')
        self.authenticate('bob')
        response = self.client.patch(f'/api/reviews/{review.id}/', {'rating': 1}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        response = self.client.delete(f'/api/reviews/{review.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_duplicate_review_returns_400_not_500(self):
        Review.objects.create(place=self.place, user=self.bob, rating=5, comment='Super')
        self.authenticate('bob')
        response = self.client.post('/api/reviews/', {'place': self.place.id, 'rating': 3, 'comment': 'Bof'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_only_admin_can_manage_categories(self):
        self.assertEqual(self.client.get('/api/categories/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.post('/api/categories/', {'name': 'Spam'}, format='json').status_code, status.HTTP_401_UNAUTHORIZED)
        self.authenticate('bob')
        self.assertEqual(self.client.post('/api/categories/', {'name': 'Spam'}, format='json').status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Category.objects.filter(name='Spam').exists())

    def test_users_cannot_see_other_profiles_or_create_accounts(self):
        self.authenticate('bob')
        self.assertEqual(self.client.get(f'/api/users/{self.alice.id}/').status_code, status.HTTP_404_NOT_FOUND)
        response = self.client.post('/api/users/', {'username': 'ghost'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertFalse(User.objects.filter(username='ghost').exists())

    def test_favorites_and_visits_are_private(self):
        self.authenticate('alice')
        self.client.post(f'/api/places/{self.place.id}/favorite/')
        self.client.post('/api/visits/', {'place': self.place.id}, format='json')
        self.authenticate('bob')
        self.assertEqual(self.client.get('/api/favorites/').data['count'], 0)
        self.assertEqual(self.client.get('/api/visits/').data['count'], 0)

    def test_favorites_include_place_details(self):
        # L'app affiche les favoris comme des cartes de lieu, sans requête supplémentaire par lieu
        self.authenticate('alice')
        self.client.post(f'/api/places/{self.place.id}/favorite/')
        favorite = self.client.get('/api/favorites/').data['results'][0]
        self.assertEqual(favorite['place'], self.place.id)
        details = favorite['place_details']
        self.assertEqual(details['id'], self.place.id)
        self.assertEqual(details['city'], 'Cotonou')
        self.assertEqual(details['category'], 'restaurant')
        self.assertTrue(details['is_favorite'])


def make_image(name='lieu.png', size=(40, 30)):
    """Petite image PNG valide, comme celle envoyée par l'app"""
    buffer = BytesIO()
    Image.new('RGB', size, (248, 89, 21)).save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


# ============================================
# TESTS: Photo d'un lieu
# ============================================
class PlaceImageTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        # Les fichiers envoyés pendant les tests vont dans un dossier jetable
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)
        self.authenticate('alice')

    def create(self, image):
        return self.client.post('/api/places/', {
            'name': 'Maquis Photo', 'category': 'bar', 'city': 'Cotonou',
            'latitude': '6.36', 'longitude': '2.42', 'image': image,
        }, format='multipart')

    def test_photo_sent_with_a_new_place_is_saved_and_returned_as_url(self):
        response = self.create(make_image())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        place = Place.objects.get(id=response.data['id'])
        self.assertTrue(place.image.name)
        self.assertTrue(response.data['image'].startswith('http'))

    def test_a_file_that_is_not_an_image_is_rejected(self):
        fake = SimpleUploadedFile('lieu.png', b'pas une image', content_type='image/png')
        response = self.create(fake)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('image', response.data)

    def test_a_too_heavy_image_is_rejected(self):
        with patch('places.serializers.PLACE_IMAGE_MAX_BYTES', 100):
            response = self.create(make_image())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('image', response.data)

    def test_place_without_photo_still_works(self):
        response = self.client.post('/api/places/', {
            'name': 'Sans photo', 'category': 'bar', 'city': 'Cotonou', 'latitude': 6.36, 'longitude': 2.42,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data['image'])


# ============================================
# TESTS: Note moyenne d'un lieu
# ============================================
class PlaceRatingTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.place = make_place(self.alice)

    def rating(self):
        self.place.refresh_from_db()
        return self.place.rating

    def test_rating_follows_reviews_created_through_reviews_endpoint(self):
        self.authenticate('bob')
        self.client.post('/api/reviews/', {'place': self.place.id, 'rating': 4, 'comment': 'Bien'}, format='json')
        self.assertEqual(self.rating(), 4)

    def test_rating_is_recalculated_when_a_review_is_modified(self):
        Review.objects.create(place=self.place, user=self.alice, rating=5, comment='Super')
        review = Review.objects.create(place=self.place, user=self.bob, rating=3, comment='Moyen')
        self.authenticate('bob')
        response = self.client.patch(f'/api/reviews/{review.id}/', {'rating': 1}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.rating(), 3)

    def test_rating_is_recalculated_when_a_review_is_deleted_and_reset_without_reviews(self):
        Review.objects.create(place=self.place, user=self.alice, rating=5, comment='Super')
        review = Review.objects.create(place=self.place, user=self.bob, rating=1, comment='Déçu')
        self.assertEqual(self.rating(), 3)
        self.authenticate('bob')
        self.assertEqual(self.client.delete(f'/api/reviews/{review.id}/').status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.rating(), 5)
        Review.objects.filter(place=self.place).delete()
        self.assertEqual(self.rating(), 0)


# ============================================
# TESTS: Recherche de lieux
# ============================================
class PlaceSearchTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        make_place(self.alice, name='Maquis cher', budget_min=20000, budget_max=40000, rating=4.5)
        make_place(self.alice, name='Maquis pas cher', budget_min=1000, budget_max=3000, rating=3)

    def search(self, query):
        return self.client.get(f'/api/places/search/?{query}')

    def test_invalid_numbers_return_400_not_500(self):
        for query, field in [('budget_min=abc', 'budget_min'), ('budget_max=1e999999', 'budget_max'), ('min_rating=xyz', 'min_rating')]:
            response = self.search(query)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, query)
            self.assertIn(field, response.data)

    def test_rating_outside_0_to_5_is_rejected(self):
        self.assertEqual(self.search('min_rating=9').status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_numbers_still_filter(self):
        names = [place['name'] for place in self.search('budget_max=5000').data['results']]
        self.assertEqual(names, ['Maquis pas cher'])
        names = [place['name'] for place in self.search('min_rating=4').data['results']]
        self.assertEqual(names, ['Maquis cher'])


# ============================================
# TESTS: Profil
# ============================================
class ProfileTests(BaseAPITestCase):
    def test_cannot_take_another_users_email(self):
        # L'email sert à retrouver un compte (mot de passe oublié) : il doit rester unique
        self.authenticate('alice')
        response = self.client.patch(f'/api/users/{self.alice.id}/', {'email': 'BOB@example.com'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.email, 'alice@example.com')

    def test_can_keep_or_recase_own_email_and_it_is_stored_lowercase(self):
        self.authenticate('alice')
        response = self.client.patch(f'/api/users/{self.alice.id}/', {'email': 'Alice@Example.com', 'first_name': 'Alice'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.email, 'alice@example.com')
        self.assertEqual(self.alice.first_name, 'Alice')


# ============================================
# TESTS: Changement de mot de passe
# ============================================
NEW_PASSWORD = 'N0uveau!Mot2Passe'


def refresh_works(client, refresh):
    return client.post('/api/auth/refresh/', {'refresh': refresh}, format='json').status_code == status.HTTP_200_OK


@override_settings(EMAIL_SEND_ASYNC=False)
class PasswordChangeTests(BaseAPITestCase):
    def change(self, current, new):
        return self.client.post(
            '/api/auth/password/change/', {'current_password': current, 'new_password': new}, format='json'
        )

    def test_requires_authentication(self):
        self.assertEqual(self.change(PASSWORD, NEW_PASSWORD).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rejects_wrong_current_password(self):
        self.authenticate()
        response = self.change('mauvais', NEW_PASSWORD)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('current_password', response.data)
        self.alice.refresh_from_db()
        self.assertTrue(self.alice.check_password(PASSWORD))

    def test_rejects_weak_or_unchanged_password(self):
        self.authenticate()
        for weak in ('123456', PASSWORD):
            response = self.change(PASSWORD, weak)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, weak)
            self.assertIn('new_password', response.data)

    def test_success_revokes_other_sessions_and_returns_new_tokens(self):
        other_device = self.login().data['refresh']
        self.authenticate()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.change(PASSWORD, NEW_PASSWORD)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(refresh_works(self.client, other_device))
        self.assertTrue(refresh_works(self.client, response.data['refresh']))
        self.assertEqual(self.login(password=NEW_PASSWORD).status_code, status.HTTP_200_OK)
        self.assertEqual(self.login(password=PASSWORD).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['alice@example.com'])


# ============================================
# TESTS: Mot de passe oublié
# ============================================
@override_settings(EMAIL_SEND_ASYNC=False)
class PasswordResetTests(BaseAPITestCase):
    def request_code(self, email='alice@example.com'):
        return self.client.post('/api/auth/password/reset/', {'email': email}, format='json')

    def sent_code(self):
        return re.search(r'\b(\d{6})\b', mail.outbox[-1].body).group(1)

    def verify(self, code, email='alice@example.com'):
        return self.client.post('/api/auth/password/reset/verify/', {'email': email, 'code': code}, format='json')

    def confirm(self, token, password=NEW_PASSWORD):
        return self.client.post(
            '/api/auth/password/reset/confirm/', {'reset_token': token, 'password': password}, format='json'
        )

    def wrong(self, code):
        """Un code à 6 chiffres différent du bon"""
        return f'{(int(code) + 1) % 1_000_000:06d}'

    def test_same_answer_whether_account_exists_or_not(self):
        known = self.request_code('ALICE@example.com')
        unknown = self.request_code('personne@example.com')
        self.assertEqual(known.status_code, status.HTTP_200_OK)
        self.assertEqual(unknown.status_code, status.HTTP_200_OK)
        self.assertEqual(known.data, unknown.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['alice@example.com'])

    def test_full_flow_changes_password_and_revokes_sessions(self):
        old_session = self.login().data['refresh']
        self.request_code()
        code = self.sent_code()
        token = self.verify(code).data['reset_token']
        with self.captureOnCommitCallbacks(execute=True):
            response = self.confirm(token)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.login(password=NEW_PASSWORD).status_code, status.HTTP_200_OK)
        self.assertFalse(refresh_works(self.client, old_session))
        # Alerte « mot de passe modifié » après l'email du code
        self.assertEqual(len(mail.outbox), 2)
        # Code et jeton sont à usage unique
        self.assertEqual(self.verify(code).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.confirm(token, 'Encore!Un4utre').status_code, status.HTTP_400_BAD_REQUEST)

    def test_code_is_not_stored_in_clear(self):
        self.request_code()
        code = self.sent_code()
        stored = PasswordResetCode.objects.get(user=self.alice)
        self.assertNotIn(code, stored.code_hash)
        self.assertEqual(len(stored.code_hash), 64)

    def test_code_is_invalidated_after_5_wrong_attempts(self):
        self.request_code()
        code = self.sent_code()
        for _ in range(5):
            response = self.verify(self.wrong(code))
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn('code', response.data)
        self.assertEqual(self.verify(code).status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_email_and_wrong_code_give_the_same_error(self):
        self.request_code()
        code = self.sent_code()
        self.assertEqual(self.verify(self.wrong(code)).data, self.verify(code, 'personne@example.com').data)

    def test_expired_code_is_rejected(self):
        self.request_code()
        code = self.sent_code()
        PasswordResetCode.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.verify(code).status_code, status.HTTP_400_BAD_REQUEST)

    def test_new_request_replaces_previous_code(self):
        self.request_code()
        first = self.sent_code()
        self.request_code()
        second = self.sent_code()
        if first != second:
            self.assertEqual(self.verify(first).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.verify(second).status_code, status.HTTP_200_OK)

    def test_weak_password_is_rejected_and_token_kept(self):
        self.request_code()
        token = self.verify(self.sent_code()).data['reset_token']
        response = self.confirm(token, '123456')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)
        self.assertEqual(self.confirm(token).status_code, status.HTTP_200_OK)

    def test_requests_are_limited_per_email(self):
        for _ in range(5):
            self.assertEqual(self.request_code().status_code, status.HTTP_200_OK)
        self.assertEqual(self.request_code().status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        # Une autre adresse n'est pas bloquée
        self.assertEqual(self.request_code('bob@example.com').status_code, status.HTTP_200_OK)

    def test_code_must_be_six_digits(self):
        self.assertEqual(self.verify('12ab').status_code, status.HTTP_400_BAD_REQUEST)


# ============================================
# TESTS: Suppression du compte
# ============================================
@override_settings(EMAIL_SEND_ASYNC=False)
class AccountDeletionTests(BaseAPITestCase):
    def delete_me(self, password=PASSWORD):
        return self.client.delete('/api/users/me/', {'password': password}, format='json')

    def test_requires_authentication(self):
        self.assertEqual(self.delete_me().status_code, status.HTTP_401_UNAUTHORIZED)

    def test_wrong_password_keeps_the_account(self):
        self.authenticate()
        response = self.delete_me('mauvais')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)
        self.assertTrue(User.objects.filter(pk=self.alice.pk).exists())

    def test_deletes_personal_data_keeps_places_and_revokes_sessions(self):
        own_place = make_place(self.alice, name='Lieu d’Alice')
        bobs_place = make_place(self.bob, name='Lieu de Bob')
        Review.objects.create(place=bobs_place, user=self.alice, rating=1, comment='Bof')
        Review.objects.create(place=bobs_place, user=self.bob, rating=5, comment='Top')
        session = self.authenticate()['refresh']
        with self.captureOnCommitCallbacks(execute=True):
            response = self.delete_me()
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(pk=self.alice.pk).exists())
        # Avis supprimé, note du lieu recalculée
        bobs_place.refresh_from_db()
        self.assertEqual(bobs_place.rating, 5)
        # Le lieu ajouté reste en ligne, sans auteur
        own_place.refresh_from_db()
        self.assertIsNone(own_place.owner)
        self.client.credentials()
        self.assertEqual(self.client.get(f'/api/places/{own_place.id}/').status_code, status.HTTP_200_OK)
        self.assertFalse(refresh_works(self.client, session))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['alice@example.com'])

    def test_cannot_delete_by_id_without_password(self):
        self.authenticate()
        response = self.client.delete(f'/api/users/{self.alice.id}/')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(User.objects.filter(pk=self.alice.pk).exists())


# ============================================
# TESTS: Données de démonstration (manage.py seed_demo)
# ============================================
class SeedDemoTests(APITestCase):
    def run_seed(self, *args):
        out = StringIO()
        call_command('seed_demo', *args, stdout=out)
        return out.getvalue()

    @override_settings(DEBUG=True)
    def test_creates_demo_account_and_places(self):
        output = self.run_seed('--password', PASSWORD)
        user = User.objects.get(username='demo')
        self.assertTrue(user.check_password(PASSWORD))
        self.assertFalse(user.is_staff)
        self.assertGreaterEqual(Place.objects.count(), 6)
        self.assertTrue(Review.objects.exists())
        self.assertIn('demo', output)
        # Mot de passe choisi : jamais réaffiché
        self.assertNotIn(PASSWORD, output)

    @override_settings(DEBUG=True)
    def test_generates_and_prints_a_strong_password_when_none_given(self):
        output = self.run_seed()
        password = output.split('Mot de passe : ')[1].split()[0]
        self.assertGreaterEqual(len(password), 16)
        self.assertTrue(User.objects.get(username='demo').check_password(password))

    @override_settings(DEBUG=True)
    def test_is_idempotent(self):
        self.run_seed('--password', PASSWORD)
        places = Place.objects.count()
        self.run_seed('--password', PASSWORD)
        self.assertEqual(Place.objects.count(), places)
        self.assertEqual(User.objects.filter(username='demo').count(), 1)

    @override_settings(DEBUG=True)
    def test_rejects_weak_password(self):
        with self.assertRaises(CommandError):
            self.run_seed('--password', '123456')

    @override_settings(DEBUG=False)
    def test_refuses_to_run_in_production(self):
        with self.assertRaises(CommandError):
            self.run_seed('--password', PASSWORD)
        self.assertFalse(User.objects.filter(username='demo').exists())
