from rest_framework import routers
from django.urls import path
from .views import (
    PlaceViewSet, UserViewSet, CategoryViewSet, ReviewViewSet, 
    FavoriteViewSet, VisitViewSet, register, login, logout, TokenRefresh
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
] + router.urls

