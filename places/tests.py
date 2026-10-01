import shutil
import tempfile
from io import BytesIO, StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import override_settings
from rest_framework import status
from PIL import Image
from rest_framework.test import APITestCase

from .models import Category, Place, Review
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
