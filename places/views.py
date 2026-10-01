from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import SimpleRateThrottle
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
import hashlib
from drf_spectacular.utils import extend_schema_view, extend_schema
from .emails import send_account_deleted, send_password_changed, send_reset_code
from .models import Place, Review, Favorite, Category, Visit, PasswordResetCode
from .serializers import PlaceSerializer, ReviewSerializer, FavoriteSerializer, UserSerializer, CategorySerializer, VisitSerializer, RegisterSerializer, LoginSerializer, LogoutSerializer, AuthResponseSerializer, PlaceSearchParamsSerializer
from .serializers import (
    AccountDeleteSerializer, DetailSerializer, PasswordChangeSerializer, PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer, PasswordResetTokenSerializer, PasswordResetVerifySerializer, TokenPairSerializer,
)
from .permissions import IsAdminOrReadOnly, IsOwnerOrReadOnly


# ============================================
# PAGINATION
# ============================================
class StandardResultsSetPagination(PageNumberPagination):
    """
    Classe de pagination standard pour tous les ViewSets.
    Affiche 10 résultats par page par défaut (peut être changé avec ?page_size=20).
    """
    # Nombre de résultats par page
    page_size = 10
    
    # Paramètre pour changer le nombre de résultats (ex: ?page_size=20)
    page_size_query_param = 'page_size'
    
    # Nombre maximum de résultats autorisés par page
    max_page_size = 100


# ============================================
# VIEWSET: Category
# ============================================
@extend_schema_view(
    list=extend_schema(tags=["Categories"]),
    retrieve=extend_schema(tags=["Categories"]),
    create=extend_schema(tags=["Categories"]),
    update=extend_schema(tags=["Categories"]),
    partial_update=extend_schema(tags=["Categories"]),
    destroy=extend_schema(tags=["Categories"]),
)
class CategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer les catégories.
    Liste complète des opérations CRUD.
    """
    # Récupère toutes les catégories
    queryset = Category.objects.all()
    
    # Utilise le serializer CategorySerializer
    serializer_class = CategorySerializer
    
    # Permissions : n'importe qui peut lire, seul admin peut modifier
    permission_classes = [IsAdminOrReadOnly]
    
    # Ajoute la pagination
    pagination_class = StandardResultsSetPagination


# ============================================
# VIEWSET: Review
# ============================================
@extend_schema_view(
    list=extend_schema(tags=["Reviews"]),
    retrieve=extend_schema(tags=["Reviews"]),
    create=extend_schema(tags=["Reviews"]),
    update=extend_schema(tags=["Reviews"]),
    partial_update=extend_schema(tags=["Reviews"]),
    destroy=extend_schema(tags=["Reviews"]),
)
class ReviewViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer les avis.
    - Lecture publique : tout le monde peut voir les avis
    - Création : seuls les utilisateurs authentifiés peuvent créer
    """
    serializer_class = ReviewSerializer
    
    # Permissions : lecture publique, création authentifiée, modification par l'auteur
    permission_classes = [IsOwnerOrReadOnly]
    owner_field = 'user'
    
    # Ajoute la pagination
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """
        Filtre les avis.
        Peut filtrer par place avec ?place_id=X
        """
        queryset = Review.objects.all()
        
        # Si un place_id est fourni, filtre les avis de cette place
        place_id = self.request.query_params.get('place_id')
        if place_id:
            queryset = queryset.filter(place_id=place_id)
        
        return queryset
    
    def perform_create(self, serializer):
        """Quand un avis est créé, associe l'utilisateur actuel"""
        # Un seul avis par utilisateur et par place (évite une erreur 500 d'intégrité)
        if Review.objects.filter(user=self.request.user, place=serializer.validated_data['place']).exists():
            raise ValidationError({'place': 'Vous avez déjà laissé un avis sur ce lieu.'})
        serializer.save(user=self.request.user)


# ============================================
# VIEWSET: Favorite
# ============================================
@extend_schema_view(
    list=extend_schema(tags=["Favorites"]),
    retrieve=extend_schema(tags=["Favorites"]),
    create=extend_schema(tags=["Favorites"]),
    update=extend_schema(tags=["Favorites"]),
    partial_update=extend_schema(tags=["Favorites"]),
    destroy=extend_schema(tags=["Favorites"]),
    toggle=extend_schema(tags=["Favorites"]),
)
class FavoriteViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer les favoris.
    - Chaque utilisateur ne voit que ses propres favoris
    - Seuls les utilisateurs authentifiés peuvent créer/modifier
    """
    serializer_class = FavoriteSerializer
    
    # Permissions : seuls les utilisateurs authentifiés
    permission_classes = [IsAuthenticated]
    
    # Ajoute la pagination
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Chaque utilisateur ne voit que ses propres favoris"""
        # Génération du schéma Swagger : pas d'utilisateur connecté
        if getattr(self, 'swagger_fake_view', False):
            return Favorite.objects.none()
        return Favorite.objects.filter(user=self.request.user).select_related('place')
    
    def perform_create(self, serializer):
        """Quand un favori est créé, associe l'utilisateur actuel"""
        # Une place ne peut être qu'une fois en favori (évite une erreur 500 d'intégrité)
        if Favorite.objects.filter(user=self.request.user, place=serializer.validated_data['place']).exists():
            raise ValidationError({'place': 'Ce lieu est déjà dans vos favoris.'})
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['post'])
    def toggle(self, request):
        """
        Action personnalisée pour basculer un favori.
        Si la place est déjà en favori, la supprime.
        Sinon, l'ajoute.
        
        Usage: POST /api/favorites/toggle/ avec {"place_id": 1}
        """
        place_id = request.data.get('place_id')
        try:
            # Récupère la place
            place = Place.objects.get(id=place_id)
            
            # Essaie de récupérer ou créer un favori
            favorite, created = Favorite.objects.get_or_create(user=request.user, place=place)
            
            # Si le favori existait déjà, le supprime
            if not created:
                favorite.delete()
                return Response({'status': 'removed from favorites'}, status=status.HTTP_200_OK)
            
            # Sinon, retourne le message de création
            return Response({'status': 'added to favorites'}, status=status.HTTP_201_CREATED)
        except Place.DoesNotExist:
            return Response({'error': 'Place not found'}, status=status.HTTP_404_NOT_FOUND)


# ============================================
# VIEWSET: User
# ============================================
@extend_schema_view(
    list=extend_schema(tags=["Users"]),
    retrieve=extend_schema(tags=["Users"]),
    create=extend_schema(tags=["Users"]),
    update=extend_schema(tags=["Users"]),
    partial_update=extend_schema(tags=["Users"]),
    destroy=extend_schema(tags=["Users"], description="Réservé aux administrateurs. Pour supprimer son propre compte : DELETE /api/users/me/."),
    places=extend_schema(tags=["Users"]),
    me=extend_schema(
        tags=["Users"],
        description=(
            "Supprimer son compte (droit à l'effacement). Le mot de passe est exigé. "
            "Les avis, favoris, visites et sessions sont supprimés ; les lieux ajoutés restent en ligne, sans auteur."
        ),
        request=AccountDeleteSerializer,
        responses={204: None, 400: {}, 401: {}},
    ),
)
class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer les utilisateurs.
    - Les utilisateurs normaux ne voient que leur profil
    - Les administrateurs voient tous les profils
    """
    queryset = User.objects.all()
    
    serializer_class = UserSerializer
    
    # Permissions : seuls les utilisateurs authentifiés
    permission_classes = [IsAuthenticated]
    
    # Ajoute la pagination
    pagination_class = StandardResultsSetPagination
    
    def create(self, request, *args, **kwargs):
        """Les comptes se créent via /api/auth/register/ (avec validation du mot de passe)"""
        return Response(
            {'detail': 'Utilisez /api/auth/register/ pour créer un compte.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def get_queryset(self):
        """Les utilisateurs ne voient que leur propre profil, sauf les admins"""
        # Si c'est un administrateur, affiche tous les utilisateurs
        if self.request.user.is_staff:
            return User.objects.all()
        
        # Sinon, affiche uniquement cet utilisateur
        return User.objects.filter(id=self.request.user.id)

    def get_throttles(self):
        """Suppression du compte : le mot de passe est exigé, on limite donc les essais comme à la connexion"""
        if self.action == 'me':
            return [AuthRateThrottle()]
        return super().get_throttles()

    def destroy(self, request, *args, **kwargs):
        """
        Supprimer un compte par son identifiant : réservé aux administrateurs.
        Un utilisateur supprime le sien avec DELETE /api/users/me/, qui exige son mot de passe.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Utilisez DELETE /api/users/me/ pour supprimer votre compte.'},
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )
        return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        """Avant la suppression, révoque les sessions : un refresh token ne doit pas survivre au compte"""
        revoke_all_sessions(instance)
        instance.delete()

    @action(detail=False, methods=['delete'])
    def me(self, request):
        """
        Supprime le compte de l'utilisateur connecté.

        Usage: DELETE /api/users/me/ avec {"password": "..."}
        Supprimés : le compte, ses avis (les notes des lieux sont recalculées), favoris, visites,
        demandes de réinitialisation et sessions. Conservés : les lieux ajoutés, sans auteur.
        Un email de confirmation est envoyé.
        """
        serializer = AccountDeleteSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        username, email = user.username, user.email
        with transaction.atomic():
            self.perform_destroy(user)
            transaction.on_commit(lambda: send_account_deleted(username, email))
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['get'])
    def places(self, request, pk=None):
        """
        Action personnalisée pour voir les places créées par un utilisateur.
        
        Usage: GET /api/users/{id}/places/
        """
        user = self.get_object()
        
        # Récupère toutes les places créées par cet utilisateur
        places = Place.objects.filter(owner=user)
        
        # Sérialise les places
        serializer = PlaceSerializer(places, many=True, context={'request': request})
        return Response(serializer.data)


# ============================================
# VIEWSET: Place (Principal)
# ============================================
@extend_schema_view(
    list=extend_schema(tags=["Places"]),
    retrieve=extend_schema(tags=["Places"]),
    create=extend_schema(tags=["Places"]),
    update=extend_schema(tags=["Places"]),
    partial_update=extend_schema(tags=["Places"]),
    destroy=extend_schema(tags=["Places"]),
    book=extend_schema(tags=["Places"]),
    add_review=extend_schema(tags=["Places"]),
    reviews=extend_schema(tags=["Places"]),
    favorite=extend_schema(tags=["Places"]),
    search=extend_schema(tags=["Places"], parameters=[PlaceSearchParamsSerializer]),
)
class PlaceViewSet(viewsets.ModelViewSet):
    """
    ViewSet principal pour gérer les places.
    - Lecture publique : tout le monde peut voir les places
    - Création/Modification : seuls les utilisateurs authentifiés
    """
    queryset = Place.objects.all().order_by('-created_at')
    
    serializer_class = PlaceSerializer
    
    # Permissions : lecture publique, création authentifiée, modification par le propriétaire
    permission_classes = [IsOwnerOrReadOnly]
    
    # Ajoute la pagination
    pagination_class = StandardResultsSetPagination

    def get_permissions(self):
        """Réserver, noter ou mettre en favori : tout utilisateur connecté (pas seulement le propriétaire)"""
        if self.action in ('book', 'add_review', 'favorite'):
            return [IsAuthenticated()]
        return super().get_permissions()

    def perform_create(self, serializer):
        """Quand une place est créée, associe l'utilisateur actuel comme propriétaire"""
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'])
    def book(self, request, pk=None):
        """
        Action personnalisée pour réserver une place.
        
        Usage: POST /api/places/{id}/book/
        
        TODO: Implémentez la logique complète de réservation
        """
        place = self.get_object()
        # TODO: Implémentez la logique de réservation
        return Response({
            'status': 'place booked',
            'place_id': place.id,
            'place_name': place.name
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def add_review(self, request, pk=None):
        """
        Action pour ajouter ou modifier un avis sur une place.
        
        Usage: POST /api/places/{id}/add_review/ 
        Données requis: {"rating": 5, "comment": "Excellent lieu!"}
        
        La note moyenne du lieu est mise à jour automatiquement.
        """
        place = self.get_object()
        
        # Valide la note (1 à 5) et le commentaire
        input_serializer = ReviewSerializer(data={**request.data, 'place': place.id})
        input_serializer.is_valid(raise_exception=True)
        
        # Crée ou met à jour l'avis (un avis par utilisateur par place)
        review, created = Review.objects.update_or_create(
            place=place,
            user=request.user,
            defaults={
                'rating': input_serializer.validated_data['rating'],
                'comment': input_serializer.validated_data['comment'],
            }
        )
        
        # La note moyenne du lieu est recalculée automatiquement (signal sur Review, voir signals.py)
        
        # Retourne l'avis créé/modifié
        serializer = ReviewSerializer(review, context={'request': request})
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(serializer.data, status=status_code)

    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        """
        Action pour voir tous les avis d'une place.
        
        Usage: GET /api/places/{id}/reviews/
        """
        place = self.get_object()
        
        # Récupère tous les avis de cette place
        reviews = Review.objects.filter(place=place)
        
        # Sérialise les avis
        serializer = ReviewSerializer(reviews, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post', 'delete'])
    def favorite(self, request, pk=None):
        """
        Action pour ajouter ou retirer une place des favoris.
        
        Usage: 
        - POST /api/places/{id}/favorite/ - Ajouter aux favoris
        - DELETE /api/places/{id}/favorite/ - Retirer des favoris
        """
        place = self.get_object()
        
        if request.method == 'POST':
            # Ajouter aux favoris
            favorite, created = Favorite.objects.get_or_create(user=request.user, place=place)
            if created:
                return Response({'status': 'added to favorites'}, status=status.HTTP_201_CREATED)
            return Response({'status': 'already in favorites'}, status=status.HTTP_200_OK)
        
        else:  # DELETE
            # Retirer des favoris
            favorite = Favorite.objects.filter(user=request.user, place=place)
            if favorite.exists():
                favorite.delete()
                return Response({'status': 'removed from favorites'}, status=status.HTTP_200_OK)
            return Response({'error': 'Not in favorites'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'])
    def search(self, request):
        """
        Action de recherche avancée pour filtrer les places.
        
        Paramètres supportés:
        - search: Recherche par nom, ville, adresse ou description
        - budget_min: Budget minimum
        - budget_max: Budget maximum
        - category: Catégorie (restaurant, hôtel, etc.)
        - min_rating: Note minimale
        - city: Nom de la ville
        - page: Numéro de page (défaut: 1)
        - page_size: Nombre de résultats par page (max: 100)
        
        Exemple: /api/places/search/?search=restaurant&city=Paris&budget_max=50000&min_rating=4
        """
        queryset = self.get_queryset()

        # Paramètres vérifiés d'abord : une valeur invalide renvoie 400, jamais 500
        params = PlaceSearchParamsSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        filters = params.validated_data
        
        # Filtre par budget minimum
        budget_min = filters.get('budget_min')
        if budget_min is not None:
            queryset = queryset.filter(budget_min__gte=budget_min)
        
        # Filtre par budget maximum
        budget_max = filters.get('budget_max')
        if budget_max is not None:
            queryset = queryset.filter(budget_max__lte=budget_max)
        
        # Recherche par texte (dans nom, ville, adresse, description)
        search_query = filters.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(city__icontains=search_query) |
                Q(address__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        # Filtre par catégorie
        category = filters.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Filtre par note minimale
        min_rating = filters.get('min_rating')
        if min_rating is not None:
            queryset = queryset.filter(rating__gte=min_rating)
        
        # Filtre par ville
        city = filters.get('city')
        if city:
            queryset = queryset.filter(city__icontains=city)
        
        # Applique la pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        # Si pas de pagination, retourne directement
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


def _auth_response(user, status_code):
    """Construit la réponse commune à l'inscription et à la connexion : profil + tokens JWT"""
    refresh = RefreshToken.for_user(user)
    return Response({
        'user': UserSerializer(user).data,
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }, status=status_code)


class AuthRateThrottle(SimpleRateThrottle):
    """Limite les tentatives de connexion/inscription par adresse IP (voir THROTTLE_AUTH)"""
    scope = 'auth'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class PasswordResetRateThrottle(SimpleRateThrottle):
    """Limite les demandes de code « mot de passe oublié » par adresse IP (voir THROTTLE_PASSWORD_RESET)"""
    scope = 'password_reset'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class PasswordResetEmailRateThrottle(SimpleRateThrottle):
    """
    Limite les demandes de code pour une même adresse email, quelle que soit l'IP
    (voir THROTTLE_PASSWORD_RESET_EMAIL) : évite d'inonder une boîte mail de codes.
    L'email est haché dans la clé de cache.
    """
    scope = 'password_reset_email'

    def get_cache_key(self, request, view):
        email = str(request.data.get('email', '')).strip().lower()
        if not email:
            return None
        return self.cache_format % {'scope': self.scope, 'ident': hashlib.sha256(email.encode()).hexdigest()}


def revoke_all_sessions(user):
    """
    Révoque tous les refresh tokens de l'utilisateur : chaque appareil devra se reconnecter.
    Les tokens d'accès déjà émis restent valables jusqu'à leur expiration (JWT_ACCESS_MINUTES).
    """
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


# ============================================
# VUE: Register (Créer un compte)
# ============================================
@extend_schema(
    tags=["Authentication"],
    description="Créer un nouvel utilisateur et obtenir ses tokens JWT (access + refresh).",
    request=RegisterSerializer,
    responses={201: AuthResponseSerializer, 400: {}}
)
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AuthRateThrottle])
def register(request):
    """
    Endpoint pour créer un nouvel utilisateur.
    
    Usage: POST /api/auth/register/
    Données requises: {
        "username": "john_doe",
        "email": "john@example.com",
        "password": "un_mot_de_passe_solide"
    }
    
    Retour: {"user": {...}, "access": "...", "refresh": "..."}
    """
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    return _auth_response(user, status.HTTP_201_CREATED)


# ============================================
# VUE: Login (Connexion)
# ============================================
@extend_schema(
    tags=["Authentication"],
    description="Se connecter et obtenir les tokens JWT (access + refresh).",
    request=LoginSerializer,
    responses={200: AuthResponseSerializer, 400: {}}
)
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AuthRateThrottle])
def login(request):
    """
    Endpoint pour se connecter.
    
    Usage: POST /api/auth/login/
    Données requises: {
        "username": "john_doe",
        "password": "un_mot_de_passe_solide"
    }
    
    Retour: {"user": {...}, "access": "...", "refresh": "..."}
    Le token d'accès s'envoie dans l'en-tête: Authorization: Bearer <access>
    """
    serializer = LoginSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    return _auth_response(serializer.validated_data['user'], status.HTTP_200_OK)


# ============================================
# VUE: Refresh (Renouveler le token d'accès)
# ============================================
@extend_schema(
    tags=["Authentication"],
    description="Échanger un refresh token contre un nouveau couple access/refresh. L'ancien refresh token est révoqué.",
)
class TokenRefresh(TokenRefreshView):
    """
    Usage: POST /api/auth/refresh/ avec {"refresh": "..."}
    Retour: {"access": "...", "refresh": "..."}
    """
    throttle_classes = [AuthRateThrottle]


# ============================================
# VUE: Logout (Déconnexion)
# ============================================
@extend_schema(
    tags=["Authentication"],
    description="Se déconnecter : révoque le refresh token fourni.",
    request=LogoutSerializer,
    responses={205: None, 400: {}, 401: {}}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """
    Endpoint pour se déconnecter.
    Révoque (blacklist) le refresh token : il ne pourra plus être utilisé.
    Le token d'accès expire de lui-même au bout de quelques minutes.
    
    Usage: POST /api/auth/logout/ avec {"refresh": "..."}
    Authentification requise: Authorization: Bearer <access>
    """
    serializer = LogoutSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        token = RefreshToken(serializer.validated_data['refresh'])
        # Empêche de révoquer le token d'un autre utilisateur
        if str(token.get('user_id')) != str(request.user.id):
            raise TokenError('Token does not belong to user')
        token.blacklist()
    except TokenError:
        return Response(
            {'detail': 'Token invalide ou expiré.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    return Response(status=status.HTTP_205_RESET_CONTENT)


# ============================================
# VUE: Changement de mot de passe
# ============================================
@extend_schema(
    tags=["Authentication"],
    description=(
        "Changer son mot de passe (l'actuel est exigé). Toutes les sessions sont révoquées : "
        "de nouveaux tokens sont renvoyés pour garder cet appareil connecté. Un email d'alerte est envoyé."
    ),
    request=PasswordChangeSerializer,
    responses={200: TokenPairSerializer, 400: {}, 401: {}}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([AuthRateThrottle])
def password_change(request):
    """
    Usage: POST /api/auth/password/change/
    Données requises: {"current_password": "...", "new_password": "..."}
    Retour: {"access": "...", "refresh": "..."} (les anciens refresh tokens ne marchent plus)
    """
    serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    user = request.user
    with transaction.atomic():
        user.set_password(serializer.validated_data['new_password'])
        user.save(update_fields=['password'])
        revoke_all_sessions(user)
        transaction.on_commit(lambda: send_password_changed(user))
    refresh = RefreshToken.for_user(user)
    return Response({'access': str(refresh.access_token), 'refresh': str(refresh)})


# ============================================
# VUES: Mot de passe oublié (3 étapes)
# ============================================
RESET_REQUEST_MESSAGE = "Si un compte correspond à cet email, un code à 6 chiffres vient d'y être envoyé."
RESET_CODE_ERROR = 'Code incorrect ou expiré.'


@extend_schema(
    tags=["Authentication"],
    description=(
        "Étape 1 : demander un code à 6 chiffres par email. La réponse est la même que le compte "
        "existe ou non. Limité par adresse IP et par email."
    ),
    request=PasswordResetRequestSerializer,
    responses={200: DetailSerializer, 400: {}, 429: {}}
)
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetRateThrottle, PasswordResetEmailRateThrottle])
def password_reset_request(request):
    """
    Usage: POST /api/auth/password/reset/ avec {"email": "..."}
    Un nouveau code remplace le précédent. Rien n'est envoyé si aucun compte actif ne correspond.
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = User.objects.filter(email__iexact=serializer.validated_data['email'], is_active=True).first()
    if user is not None:
        code = PasswordResetCode.issue(user)
        send_reset_code(user, code)
    return Response({'detail': RESET_REQUEST_MESSAGE})


@extend_schema(
    tags=["Authentication"],
    description=(
        "Étape 2 : vérifier le code reçu. 5 essais par code, valable 10 minutes. "
        "Renvoie un jeton à usage unique pour l'étape 3."
    ),
    request=PasswordResetVerifySerializer,
    responses={200: PasswordResetTokenSerializer, 400: {}, 429: {}}
)
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AuthRateThrottle])
def password_reset_verify(request):
    """
    Usage: POST /api/auth/password/reset/verify/ avec {"email": "...", "code": "123456"}
    Retour: {"reset_token": "..."}
    Même erreur que l'email soit inconnu, le code faux, expiré ou épuisé : rien ne révèle un compte.
    """
    serializer = PasswordResetVerifySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = User.objects.filter(email__iexact=serializer.validated_data['email'], is_active=True).first()
    pending = PasswordResetCode.pending_for(user) if user is not None else None
    if pending is None or not pending.check_code(serializer.validated_data['code']):
        return Response({'code': [RESET_CODE_ERROR]}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'reset_token': pending.exchange_for_token()})


@extend_schema(
    tags=["Authentication"],
    description=(
        "Étape 3 : choisir le nouveau mot de passe avec le jeton de l'étape 2. "
        "Toutes les sessions sont révoquées et un email d'alerte est envoyé."
    ),
    request=PasswordResetConfirmSerializer,
    responses={200: DetailSerializer, 400: {}, 429: {}}
)
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AuthRateThrottle])
def password_reset_confirm(request):
    """
    Usage: POST /api/auth/password/reset/confirm/ avec {"reset_token": "...", "password": "..."}
    L'utilisateur se reconnecte ensuite avec son nouveau mot de passe.
    """
    serializer = PasswordResetConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    reset = PasswordResetCode.from_token(serializer.validated_data['reset_token'])
    if reset is None:
        return Response(
            {'reset_token': ['Demande expirée ou déjà utilisée : recommencez depuis le début.']},
            status=status.HTTP_400_BAD_REQUEST
        )
    user = reset.user
    password = serializer.validated_data['password']
    try:
        validate_password(password, user=user)
    except DjangoValidationError as error:
        return Response({'password': list(error.messages)}, status=status.HTTP_400_BAD_REQUEST)
    with transaction.atomic():
        user.set_password(password)
        user.save(update_fields=['password'])
        # Jeton consommé ; les autres demandes de cet utilisateur ne servent plus
        PasswordResetCode.objects.filter(pk=reset.pk).update(used_at=timezone.now())
        PasswordResetCode.objects.filter(user=user).exclude(pk=reset.pk).delete()
        revoke_all_sessions(user)
        transaction.on_commit(lambda: send_password_changed(user))
    return Response({'detail': 'Mot de passe modifié. Connectez-vous avec le nouveau.'})


# ============================================
# VIEWSET: Visit (Historique des visites)
# ============================================
@extend_schema_view(
    list=extend_schema(tags=["Visits"]),
    retrieve=extend_schema(tags=["Visits"]),
    create=extend_schema(tags=["Visits"]),
    update=extend_schema(tags=["Visits"]),
    partial_update=extend_schema(tags=["Visits"]),
    destroy=extend_schema(tags=["Visits"]),
)
class VisitViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer l'historique des visites.
    - Chaque utilisateur ne voit que ses propres visites
    - Seuls les utilisateurs authentifiés peuvent créer/modifier
    """
    serializer_class = VisitSerializer
    
    # Permissions : seuls les utilisateurs authentifiés
    permission_classes = [IsAuthenticated]
    
    # Ajoute la pagination
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """
        Filtre les visites pour n'afficher que celles de l'utilisateur actuel.
        Peut filtrer par place avec ?place_id=X
        """
        # Génération du schéma Swagger : pas d'utilisateur connecté
        if getattr(self, 'swagger_fake_view', False):
            return Visit.objects.none()
        
        queryset = Visit.objects.filter(user=self.request.user)
        
        # Si un place_id est fourni, filtre les visites de cette place
        place_id = self.request.query_params.get('place_id')
        if place_id:
            queryset = queryset.filter(place_id=place_id)
        
        return queryset
    
    def perform_create(self, serializer):
        """Quand une visite est créée, associe l'utilisateur actuel"""
        serializer.save(user=self.request.user)

