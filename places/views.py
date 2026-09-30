from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import SimpleRateThrottle
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth.models import User
from django.db.models import Q, Avg
from drf_spectacular.utils import extend_schema_view, extend_schema
from .models import Place, Review, Favorite, Category, Visit
from .serializers import PlaceSerializer, ReviewSerializer, FavoriteSerializer, UserSerializer, CategorySerializer, VisitSerializer, RegisterSerializer, LoginSerializer, LogoutSerializer, AuthResponseSerializer
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
    destroy=extend_schema(tags=["Users"]),
    places=extend_schema(tags=["Users"]),
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
    search=extend_schema(tags=["Places"]),
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
        
        Met à jour automatiquement la note moyenne de la place.
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
        
        # Recalcule la note moyenne de la place
        avg_rating = Review.objects.filter(place=place).aggregate(Avg('rating'))['rating__avg']
        if avg_rating:
            place.rating = round(avg_rating, 2)
            place.save(update_fields=['rating'])
        
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
        
        # Filtre par budget minimum
        budget_min = request.query_params.get('budget_min')
        if budget_min:
            queryset = queryset.filter(budget_min__gte=budget_min)
        
        # Filtre par budget maximum
        budget_max = request.query_params.get('budget_max')
        if budget_max:
            queryset = queryset.filter(budget_max__lte=budget_max)
        
        # Recherche par texte (dans nom, ville, adresse, description)
        search_query = request.query_params.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(city__icontains=search_query) |
                Q(address__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        # Filtre par catégorie
        category = request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Filtre par note minimale
        min_rating = request.query_params.get('min_rating')
        if min_rating:
            queryset = queryset.filter(rating__gte=min_rating)
        
        # Filtre par ville
        city = request.query_params.get('city')
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

