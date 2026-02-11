from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Place, Review, Favorite, Category, Visit

# ============================================
# SERIALIZER: Category
# ============================================
class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer pour convertir les objets Category en JSON et vice-versa.
    Utilisé pour l'API REST.
    """
    class Meta:
        model = Category
        # Affiche ces champs dans l'API
        fields = ('id', 'name', 'description', 'created_at')
        # Ces champs ne peuvent pas être modifiés (lecture seule)
        read_only_fields = ('id', 'created_at')


# ============================================
# SERIALIZER: Review
# ============================================
class ReviewSerializer(serializers.ModelSerializer):
    """
    Serializer pour les avis/commentaires.
    Affiche le nom d'utilisateur et l'ID à la place de l'objet User complet.
    """
    # Affiche le nom d'utilisateur au lieu de l'ID
    username = serializers.CharField(source='user.username', read_only=True)
    
    # Affiche l'ID de l'utilisateur
    user_id = serializers.CharField(source='user.id', read_only=True)
    
    class Meta:
        model = Review
        # Champs retournés par l'API
        fields = ('id', 'place', 'user_id', 'username', 'rating', 'comment', 'created_at', 'updated_at')
        # Champs en lecture seule (ne peuvent pas être modifiés)
        read_only_fields = ('id', 'user_id', 'username', 'created_at', 'updated_at')


# ============================================
# SERIALIZER: Favorite
# ============================================
class FavoriteSerializer(serializers.ModelSerializer):
    """
    Serializer pour les favoris.
    Affiche le nom de la place au lieu de son ID.
    """
    # Affiche le nom de la place au lieu de son ID
    place_name = serializers.CharField(source='place.name', read_only=True)
    
    class Meta:
        model = Favorite
        # Champs retournés par l'API
        fields = ('id', 'place', 'place_name', 'created_at')
        # Champs en lecture seule
        read_only_fields = ('id', 'created_at')


# ============================================
# SERIALIZER: User
# ============================================
class UserSerializer(serializers.ModelSerializer):
    """
    Serializer pour les utilisateurs.
    Affiche les infos publiques de l'utilisateur.
    """
    class Meta:
        model = User
        # Informations affichées pour chaque utilisateur
        fields = ('id', 'username', 'email', 'first_name', 'last_name')
        # L'ID ne peut pas être modifié
        read_only_fields = ('id',)


# ============================================
# SERIALIZER: Place (Principal)
# ============================================
class PlaceSerializer(serializers.ModelSerializer):
    """
    Serializer principal pour les places.
    Affiche tous les détails d'une place avec des données calculées.
    """
    
    # URL complète de l'image (inclut le domaine)
    image = serializers.SerializerMethodField()
    
    # Nom d'utilisateur du propriétaire (au lieu de son ID)
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    
    # Nombre d'avis sur la place
    reviews_count = serializers.SerializerMethodField()
    
    # Nombre de fois que la place a été ajoutée aux favoris
    favorites_count = serializers.SerializerMethodField()
    
    # Booléen indiquant si l'utilisateur actuel a mis en favori cette place
    is_favorite = serializers.SerializerMethodField()
    
    class Meta:
        model = Place
        # Affiche tous les champs du modèle
        fields = '__all__'
    
    def get_image(self, obj):
        """Retourne l'URL complète de l'image (avec domaine)"""
        request = self.context.get('request')
        if obj.image:
            # Récupère le chemin relatif de l'image
            image_url = obj.image.url
            
            # Si une requête est en cours, construit l'URL absolue
            if request is not None:
                return request.build_absolute_uri(image_url)
            return image_url
        return None
    
    def get_reviews_count(self, obj):
        """Compte le nombre d'avis de cette place"""
        return obj.reviews.count()
    
    def get_favorites_count(self, obj):
        """Compte le nombre de fois que cette place a été mise en favori"""
        return obj.favorited_by.count()
    
    def get_is_favorite(self, obj):
        """Vérifie si l'utilisateur actuel a mis en favori cette place"""
        request = self.context.get('request')
        
        # Si l'utilisateur est authentifié
        if request and request.user.is_authenticated:
            # Vérifie s'il existe un favori avec cet utilisateur et cette place
            return Favorite.objects.filter(user=request.user, place=obj).exists()
        
        return False


# ============================================
# SERIALIZER: Visit
# ============================================
class VisitSerializer(serializers.ModelSerializer):
    """
    Serializer pour l'historique des visites.
    Affiche le nom de la place au lieu de son ID.
    """
    # Affiche le nom de la place au lieu de l'ID
    place_name = serializers.CharField(source='place.name', read_only=True)
    
    # Affiche l'adresse de la place
    place_address = serializers.CharField(source='place.address', read_only=True)
    
    # Affiche la ville de la place
    place_city = serializers.CharField(source='place.city', read_only=True)
    
    class Meta:
        model = Visit
        fields = ('id', 'place', 'place_name', 'place_address', 'place_city', 'visited_at', 'duration_minutes', 'personal_note')
        read_only_fields = ('id', 'visited_at')


