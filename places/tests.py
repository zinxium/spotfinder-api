from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework import status
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
