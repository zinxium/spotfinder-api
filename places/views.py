from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth.models import User
from django.db.models import Q, Avg
from .models import Place, Review, Favorite, Category, Visit
from .serializers import PlaceSerializer, ReviewSerializer, FavoriteSerializer, UserSerializer, CategorySerializer, VisitSerializer


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
    permission_classes = [AllowAny]
    
    # Ajoute la pagination
    pagination_class = StandardResultsSetPagination


# ============================================
# VIEWSET: Review
# ============================================
class ReviewViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer les avis.
    - Lecture publique : tout le monde peut voir les avis
    - Création : seuls les utilisateurs authentifiés peuvent créer
    """
    serializer_class = ReviewSerializer
    
    # Permissions : lecture publique, création authentifiée
    permission_classes = [IsAuthenticatedOrReadOnly]
    
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
        serializer.save(user=self.request.user)


# ============================================
# VIEWSET: Favorite
# ============================================
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
        return Favorite.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Quand un favori est créé, associe l'utilisateur actuel"""
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
class PlaceViewSet(viewsets.ModelViewSet):
    """
    ViewSet principal pour gérer les places.
    - Lecture publique : tout le monde peut voir les places
    - Création/Modification : seuls les utilisateurs authentifiés
    """
    queryset = Place.objects.all()
    
    serializer_class = PlaceSerializer
    
    # Permissions : lecture publique, modification authentifiée
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    # Ajoute la pagination
    pagination_class = StandardResultsSetPagination

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
        try:
            data = request.data
            rating = data.get('rating')
            comment = data.get('comment')
            
            # Valide les données
            if not rating or not comment:
                return Response(
                    {'error': 'Rating and comment are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Crée ou met à jour l'avis (un avis par utilisateur par place)
            review, created = Review.objects.update_or_create(
                place=place,
                user=request.user,
                defaults={'rating': rating, 'comment': comment}
            )
            
            # Recalcule la note moyenne de la place
            avg_rating = Review.objects.filter(place=place).aggregate(Avg('rating'))['rating__avg']
            if avg_rating:
                place.rating = round(avg_rating, 2)
                place.save()
            
            # Retourne l'avis créé/modifié
            serializer = ReviewSerializer(review, context={'request': request})
            status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
            return Response(serializer.data, status=status_code)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

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


# ============================================
# VUE: Register (Créer un compte)
# ============================================
@api_view(['POST'])
def register(request):
    """
    Endpoint pour créer un nouvel utilisateur.
    
    Usage: POST /api/auth/register/
    Données requises: {
        "username": "john_doe",
        "email": "john@example.com",
        "password": "secure_password_123"
    }
    
    Retour: Token d'authentification pour l'utilisateur créé
    """
    try:
        data = request.data
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        # Vérifie que username et password sont fournis
        if not username or not password:
            return Response(
                {'error': 'Username and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Vérifie que le username n'existe pas déjà
        if User.objects.filter(username=username).exists():
            return Response(
                {'error': 'Username already exists'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Crée le nouvel utilisateur
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        
        # Génère un token d'authentification pour cet utilisateur
        token, created = Token.objects.get_or_create(user=user)
        
        # Retourne les infos de l'utilisateur et son token
        return Response({
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'token': token.key
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


# ============================================
# VUE: Login (Connexion)
# ============================================
@api_view(['POST'])
def login(request):
    """
    Endpoint pour se connecter et obtenir un token.
    
    Usage: POST /api/auth/login/
    Données requises: {
        "username": "john_doe",
        "password": "secure_password_123"
    }
    
    Retour: Token d'authentification
    """
    try:
        data = request.data
        username = data.get('username')
        password = data.get('password')
        
        # Vérifie que username et password sont fournis
        if not username or not password:
            return Response(
                {'error': 'Username and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Récupère l'utilisateur
        user = User.objects.get(username=username)
        
        # Vérifie que le mot de passe est correct
        if not user.check_password(password):
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Récupère ou crée le token de l'utilisateur
        token, created = Token.objects.get_or_create(user=user)
        
        # Retourne les infos et le token
        return Response({
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'token': token.key
        }, status=status.HTTP_200_OK)
    except User.DoesNotExist:
        return Response(
            {'error': 'User not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


# ============================================
# VUE: Logout (Déconnexion)
# ============================================
@api_view(['POST'])
def logout(request):
    """
    Endpoint pour se déconnecter.
    Supprime le token d'authentification.
    
    Usage: POST /api/auth/logout/
    Authentification requise: Token dans le header
    """
    try:
        # Vérifie que l'utilisateur est authentifié
        if request.user.is_authenticated:
            # Supprime le token de cet utilisateur
            Token.objects.filter(user=request.user).delete()
            return Response(
                {'status': 'Successfully logged out'},
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {'error': 'Not authenticated'},
                status=status.HTTP_401_UNAUTHORIZED
            )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


# ============================================
# VIEWSET: Visit (Historique des visites)
# ============================================
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
        queryset = Visit.objects.filter(user=self.request.user)
        
        # Si un place_id est fourni, filtre les visites de cette place
        place_id = self.request.query_params.get('place_id')
        if place_id:
            queryset = queryset.filter(place_id=place_id)
        
        return queryset
    
    def perform_create(self, serializer):
        """Quand une visite est créée, associe l'utilisateur actuel"""
        serializer.save(user=self.request.user)

