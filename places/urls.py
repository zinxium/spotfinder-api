from rest_framework import routers
from django.urls import path
from .views import (
    PlaceViewSet, UserViewSet, CategoryViewSet, ReviewViewSet, 
    FavoriteViewSet, VisitViewSet, register, login, logout, TokenRefresh,
    password_change, password_reset_request, password_reset_verify, password_reset_confirm,
)

# ============================================
# ROUTEUR (Génère automatiquement les routes CRUD)
# ============================================
router = routers.DefaultRouter()

# Registre les ViewSets pour générer automatiquement les routes CRUD
# Chaque ViewSet génère des routes comme:
# - GET /places/ (liste)
# - POST /places/ (créer)
# - GET /places/{id}/ (détail)
# - PUT /places/{id}/ (modifier)
# - DELETE /places/{id}/ (supprimer)

# Routes pour les places
router.register(r'places', PlaceViewSet, basename='place')

# Routes pour les utilisateurs
router.register(r'users', UserViewSet, basename='user')

# Routes pour les catégories
router.register(r'categories', CategoryViewSet, basename='category')

# Routes pour les avis
router.register(r'reviews', ReviewViewSet, basename='review')

# Routes pour les favoris
router.register(r'favorites', FavoriteViewSet, basename='favorite')

# Routes pour l'historique des visites
router.register(r'visits', VisitViewSet, basename='visit')


# ============================================
# ROUTES D'AUTHENTIFICATION (Manuelles)
# ============================================
urlpatterns = [
    # Création d'un compte
    # POST /api/auth/register/
    # Données: {"username": "john", "email": "john@example.com", "password": "..."}
    path('auth/register/', register, name='register'),
    
    # Connexion
    # POST /api/auth/login/
    # Données: {"username": "john", "password": "..."}
    # Retour: {"user": {...}, "access": "...", "refresh": "..."}
    path('auth/login/', login, name='login'),
    
    # Renouvellement du token d'accès (rotation du refresh token)
    # POST /api/auth/refresh/
    # Données: {"refresh": "..."}
    path('auth/refresh/', TokenRefresh.as_view(), name='token_refresh'),
    
    # Déconnexion (révocation du refresh token)
    # POST /api/auth/logout/
    # Authentification requise: Authorization: Bearer <access>
    # Données: {"refresh": "..."}
    path('auth/logout/', logout, name='logout'),

    # Changement de mot de passe (connecté)
    # POST /api/auth/password/change/
    # Données: {"current_password": "...", "new_password": "..."}
    # Retour: {"access": "...", "refresh": "..."} (les autres appareils sont déconnectés)
    path('auth/password/change/', password_change, name='password_change'),

    # Mot de passe oublié, en 3 étapes
    # 1. POST /api/auth/password/reset/ {"email": "..."} : code à 6 chiffres envoyé par email
    # 2. POST /api/auth/password/reset/verify/ {"email": "...", "code": "123456"} : {"reset_token": "..."}
    # 3. POST /api/auth/password/reset/confirm/ {"reset_token": "...", "password": "..."}
    path('auth/password/reset/', password_reset_request, name='password_reset'),
    path('auth/password/reset/verify/', password_reset_verify, name='password_reset_verify'),
    path('auth/password/reset/confirm/', password_reset_confirm, name='password_reset_confirm'),

    # Suppression de son compte : DELETE /api/users/me/ {"password": "..."} (route du routeur ci-dessous)
] + router.urls

