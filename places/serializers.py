from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
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
        # Le propriétaire est défini par le serveur, la note est calculée à partir des avis
        read_only_fields = ('owner', 'rating', 'created_at', 'updated_at')

    def validate(self, attrs):
        """Vérifie que le budget minimum ne dépasse pas le budget maximum"""
        budget_min = attrs.get('budget_min', getattr(self.instance, 'budget_min', None))
        budget_max = attrs.get('budget_max', getattr(self.instance, 'budget_max', None))
        if budget_min is not None and budget_max is not None and budget_min > budget_max:
            raise serializers.ValidationError({'budget_min': 'Le budget minimum doit être inférieur au budget maximum.'})
        return attrs
    
    def get_image(self, obj) -> str | None:
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
    
    def get_reviews_count(self, obj) -> int:
        """Compte le nombre d'avis de cette place"""
        return obj.reviews.count()
    
    def get_favorites_count(self, obj) -> int:
        """Compte le nombre de fois que cette place a été mise en favori"""
        return obj.favorited_by.count()
    
    def get_is_favorite(self, obj) -> bool:
        """Vérifie si l'utilisateur actuel a mis en favori cette place"""
        request = self.context.get('request')
        
        # Si l'utilisateur est authentifié
        if request and request.user.is_authenticated:
            # Vérifie s'il existe un favori avec cet utilisateur et cette place
            return Favorite.objects.filter(user=request.user, place=obj).exists()
        
        return False


# ============================================
# SERIALIZER: Favorite
# ============================================
class FavoriteSerializer(serializers.ModelSerializer):
    """
    Serializer pour les favoris.
    Renvoie l'ID du lieu (utilisé à la création), son nom, et son détail complet.
    """
    # Affiche le nom de la place au lieu de son ID
    place_name = serializers.CharField(source='place.name', read_only=True)
    
    # Détail complet du lieu (lecture seule), au même format que /api/places/{id}/ :
    # évite au client une requête par favori
    place_details = PlaceSerializer(source='place', read_only=True)
    
    class Meta:
        model = Favorite
        # Champs retournés par l'API
        fields = ('id', 'place', 'place_name', 'place_details', 'created_at')
        # Champs en lecture seule
        read_only_fields = ('id', 'created_at')


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


# ============================================
# SERIALIZER: Authentication
# ============================================
class RegisterSerializer(serializers.Serializer):
    """Serializer pour l'enregistrement d'un nouvel utilisateur"""
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate_username(self, value):
        """Le nom d'utilisateur doit être unique (sans tenir compte de la casse)"""
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Ce nom d'utilisateur est déjà pris.")
        return value

    def validate_email(self, value):
        """L'email doit être unique (sans tenir compte de la casse)"""
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Cet email est déjà utilisé.')
        return value

    def validate(self, attrs):
        """
        Applique les règles de mot de passe de Django (AUTH_PASSWORD_VALIDATORS).
        Les erreurs sont rattachées au champ "password" pour que le client
        puisse les afficher sous ce champ.
        """
        user = User(username=attrs['username'], email=attrs['email'])
        try:
            validate_password(attrs['password'], user=user)
        except DjangoValidationError as error:
            raise serializers.ValidationError({'password': list(error.messages)})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    """Serializer pour la connexion"""
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        """
        Vérifie les identifiants.
        Message d'erreur identique que l'utilisateur existe ou non,
        pour ne pas révéler quels comptes existent.
        """
        user = authenticate(
            request=self.context.get('request'),
            username=attrs['username'],
            password=attrs['password'],
        )
        if user is None:
            raise serializers.ValidationError('Identifiants invalides.', code='authorization')
        attrs['user'] = user
        return attrs


class LogoutSerializer(serializers.Serializer):
    """Serializer pour la déconnexion (révoque le refresh token)"""
    refresh = serializers.CharField(write_only=True)


class AuthResponseSerializer(serializers.Serializer):
    """Réponse de connexion/inscription : utilisateur + tokens JWT"""
    user = UserSerializer(read_only=True)
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)
