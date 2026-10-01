from decimal import Decimal

from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import Place, Review, Favorite, Category, Visit

# Poids maximal d'une photo de lieu : assez pour une photo de téléphone compressée par l'app
PLACE_IMAGE_MAX_BYTES = 5 * 1024 * 1024

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

    def validate_email(self, value):
        """
        L'email reste unique (sans tenir compte de la casse), comme à l'inscription :
        il sert à retrouver un compte, deux comptes ne peuvent pas le partager.
        Le sien peut être gardé ou réécrit avec d'autres majuscules.
        """
        value = value.lower()
        others = User.objects.filter(email__iexact=value)
        if self.instance is not None:
            others = others.exclude(pk=self.instance.pk)
        if others.exists():
            raise serializers.ValidationError('Cet email est déjà utilisé.')
        return value


# ============================================
# SERIALIZER: Place (Principal)
# ============================================
class PlaceSerializer(serializers.ModelSerializer):
    """
    Serializer principal pour les places.
    Affiche tous les détails d'une place avec des données calculées.
    """
    
    # Photo du lieu : envoyée en multipart à la création ou à la modification ;
    # vérifiée par Pillow (un fichier qui n'est pas une image est refusé), renvoyée en URL complète
    image = serializers.ImageField(required=False, allow_null=True)

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
    
    def validate_image(self, value):
        """Refuse les photos trop lourdes (le contenu est déjà vérifié par Pillow)"""
        if value and value.size > PLACE_IMAGE_MAX_BYTES:
            limit = PLACE_IMAGE_MAX_BYTES // (1024 * 1024)
            raise serializers.ValidationError(f'La photo ne doit pas dépasser {limit} Mo.')
        return value
    
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
# SERIALIZER: Paramètres de recherche
# ============================================
class PlaceSearchParamsSerializer(serializers.Serializer):
    """
    Paramètres de /api/places/search/, vérifiés avant d'interroger la base :
    une valeur invalide (ex. budget_min=abc) renvoie une erreur 400 claire au lieu d'une erreur 500.
    """
    search = serializers.CharField(required=False, allow_blank=True)
    category = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(required=False, allow_blank=True)
    budget_min = serializers.DecimalField(required=False, max_digits=10, decimal_places=2, min_value=Decimal('0'))
    budget_max = serializers.DecimalField(required=False, max_digits=10, decimal_places=2, min_value=Decimal('0'))
    min_rating = serializers.FloatField(required=False, min_value=0, max_value=5)


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


# ============================================
# SERIALIZERS: Mot de passe et compte
# ============================================
def _check_new_password(password, user):
    """Règles de mot de passe de Django (AUTH_PASSWORD_VALIDATORS), erreurs sous le champ concerné"""
    try:
        validate_password(password, user=user)
    except DjangoValidationError as error:
        raise serializers.ValidationError(list(error.messages))
    return password


class PasswordChangeSerializer(serializers.Serializer):
    """Changement de mot de passe d'un utilisateur connecté : l'actuel est exigé"""
    current_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    new_password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate_current_password(self, value):
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError('Mot de passe actuel incorrect.')
        return value

    def validate_new_password(self, value):
        return _check_new_password(value, self.context['request'].user)

    def validate(self, attrs):
        if attrs['current_password'] == attrs['new_password']:
            raise serializers.ValidationError({'new_password': "Choisissez un mot de passe différent de l'actuel."})
        return attrs


class TokenPairSerializer(serializers.Serializer):
    """Nouveaux tokens renvoyés après un changement de mot de passe (cet appareil reste connecté)"""
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)


class PasswordResetRequestSerializer(serializers.Serializer):
    """Étape 1 du mot de passe oublié : l'email du compte"""
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower()


class PasswordResetVerifySerializer(serializers.Serializer):
    """Étape 2 : l'email et le code à 6 chiffres reçu"""
    email = serializers.EmailField()
    code = serializers.RegexField(r'^\d{6}$', error_messages={'invalid': 'Le code contient 6 chiffres.'})

    def validate_email(self, value):
        return value.lower()


class PasswordResetTokenSerializer(serializers.Serializer):
    """Réponse de l'étape 2 : jeton à usage unique pour l'étape 3"""
    reset_token = serializers.CharField(read_only=True)


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Étape 3 : le jeton et le nouveau mot de passe"""
    reset_token = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})


class AccountDeleteSerializer(serializers.Serializer):
    """Suppression du compte : le mot de passe confirme que c'est bien le titulaire"""
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate_password(self, value):
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError('Mot de passe incorrect.')
        return value


class DetailSerializer(serializers.Serializer):
    """Réponse contenant seulement un message"""
    detail = serializers.CharField(read_only=True)
