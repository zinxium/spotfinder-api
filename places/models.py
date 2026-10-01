import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

# ============================================
# MODÈLE: Category (Catégories de places)
# ============================================
class Category(models.Model):
    """
    Modèle pour les catégories de places (Restaurant, Hôtel, etc.)
    """
    # Nom unique de la catégorie
    name = models.CharField(max_length=100, unique=True)
    
    # Description optionnelle de la catégorie
    description = models.TextField(blank=True)
    
    # Date de création automatique
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        """Affiche le nom de la catégorie"""
        return self.name
    
    class Meta:
        # Trier les catégories par nom
        ordering = ['name']
        verbose_name_plural = 'Categories'


# ============================================
# MODÈLE: Place (Lieux/Endroits)
# ============================================
class Place(models.Model):
    """
    Modèle principal pour les places/lieux (restaurants, hôtels, sites touristiques, etc.)
    """
    
    # Choix disponibles pour la catégorie
    CATEGORY_CHOICES = [
        ('restaurant', 'Restaurant'),
        ('touristique', 'Site Touristique'),
        ('loisir', 'Loisir'),
        ('hotel', 'Hôtel'),
        ('bar', 'Bar'),
    ]

    # Champs obligatoires
    # Nom du lieu
    name = models.CharField(max_length=255)
    
    # Description détaillée du lieu
    description = models.TextField(blank=True)
    
    # Numéro de téléphone optionnel
    phone_number = models.CharField(max_length=20, blank=True)
    
    # Catégorie du lieu (choix parmi CATEGORY_CHOICES)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    
    # Ville du lieu
    city = models.CharField(max_length=100)
    
    # Adresse complète du lieu
    address = models.CharField(max_length=255, blank=True)
    
    # Coordonnées géographiques (pour localiser sur une carte)
    latitude = models.FloatField()
    longitude = models.FloatField()
    
    # Image du lieu (stockée dans media/places/)
    image = models.ImageField(upload_to='places/', blank=True, null=True)

    # Informations budgétaires (en FCFA)
    # Budget minimum
    budget_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Budget maximum
    budget_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Note moyenne du lieu (calculée automatiquement à partir des avis)
    rating = models.FloatField(default=0)

    # Propriétaire/créateur du lieu (lien avec l'utilisateur).
    # Si son compte est supprimé, le lieu reste en ligne sans auteur : il appartient à la
    # communauté (avis, favoris et visites des autres membres y sont rattachés).
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='places', null=True, blank=True)

    # Dates de suivi
    # Date de création automatique (ne change jamais)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Date de modification automatique (mise à jour à chaque modification)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        """Affiche le nom de la place"""
        return self.name

    @classmethod
    def refresh_rating(cls, place_id):
        """
        Recalcule la note moyenne d'un lieu à partir de ses avis (0 s'il n'en a plus).
        Appelée à chaque création, modification ou suppression d'avis (voir signals.py).
        Mise à jour par requête filtrée : sans effet, et sans erreur, si le lieu vient d'être supprimé.
        """
        average = Review.objects.filter(place_id=place_id).aggregate(models.Avg('rating'))['rating__avg']
        cls.objects.filter(pk=place_id).update(rating=round(average, 2) if average is not None else 0)

    # Propriété calculée : budget moyen
    @property
    def budget_avg(self):
        """Calcule et retourne le budget moyen"""
        if self.budget_min and self.budget_max:
            return (self.budget_min + self.budget_max) / 2
        return None


# ============================================
# MODÈLE: Review (Avis et commentaires)
# ============================================
class Review(models.Model):
    """
    Modèle pour les avis/commentaires que les utilisateurs laissent sur les places.
    Chaque utilisateur ne peut laisser qu'un avis par place.
    """
    
    # Lien vers la place (un avis appartient à une place)
    # Si la place est supprimée, tous ses avis sont supprimés aussi
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='reviews')
    
    # Lien vers l'utilisateur (un avis est écrit par un utilisateur)
    # Si l'utilisateur est supprimé, tous ses avis sont supprimés aussi
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    
    # Note de 1 à 5 étoiles
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    
    # Texte du commentaire
    comment = models.TextField()
    
    # Date de création automatique
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Date de modification automatique
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        """Affiche l'avis au format: Utilisateur - Place (Note)"""
        return f"{self.user.username} - {self.place.name} ({self.rating}/5)"
    
    class Meta:
        # Tri par date décroissante (plus récent d'abord)
        ordering = ['-created_at']
        
        # Contrainte: un utilisateur ne peut laisser qu'un seul avis par place
        unique_together = ('place', 'user')


# ============================================
# MODÈLE: Favorite (Favoris)
# ============================================
class Favorite(models.Model):
    """
    Modèle pour les favoris des utilisateurs.
    Permet aux utilisateurs de marquer leurs places préférées.
    """
    
    # Lien vers l'utilisateur (un favori appartient à un utilisateur)
    # Si l'utilisateur est supprimé, tous ses favoris sont supprimés
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    
    # Lien vers la place (une place peut être favori de plusieurs utilisateurs)
    # Si la place est supprimée, elle est supprimée de tous les favoris
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='favorited_by')
    
    # Date d'ajout aux favoris
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        """Affiche le favori au format: Utilisateur - Place"""
        return f"{self.user.username} - {self.place.name}"
    
    class Meta:
        # Tri par date décroissante (plus récent d'abord)
        ordering = ['-created_at']
        
        # Contrainte: un utilisateur ne peut avoir une place qu'une seule fois en favori
        unique_together = ('user', 'place')


# ============================================
# MODÈLE: Visit (Historique des visites)
# ============================================
class Visit(models.Model):
    """
    Modèle pour l'historique des visites des utilisateurs.
    Enregistre chaque fois qu'un utilisateur visite une place.
    """
    
    # Lien vers l'utilisateur (une visite appartient à un utilisateur)
    # Si l'utilisateur est supprimé, toutes ses visites sont supprimées
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='visits')
    
    # Lien vers la place (une place peut être visitée par plusieurs utilisateurs)
    # Si la place est supprimée, elle est supprimée de l'historique des visites
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='visits')
    
    # Date et heure de la visite
    visited_at = models.DateTimeField(auto_now_add=True)
    
    # Durée de la visite en minutes (optionnel)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    
    # Note personnelle de l'utilisateur pour cette visite (optionnel)
    personal_note = models.TextField(blank=True)
    
    def __str__(self):
        """Affiche la visite au format: Utilisateur - Place (Date)"""
        return f"{self.user.username} - {self.place.name} ({self.visited_at.strftime('%Y-%m-%d %H:%M')})"
    
    class Meta:
        # Tri par date décroissante (plus récent d'abord)
        ordering = ['-visited_at']
        
        # Contrainte: un utilisateur peut visiter plusieurs fois la même place
        # (pas de unique_together ici, contrairement aux favoris)


# ============================================
# MODÈLE: PasswordResetCode (Mot de passe oublié)
# ============================================
def _digest(value):
    """
    Empreinte HMAC-SHA256 d'une valeur secrète, signée avec SECRET_KEY.
    Un code à 6 chiffres n'a qu'un million de valeurs possibles : une empreinte simple se
    retrouverait en quelques secondes depuis une copie de la base. Avec la clé du serveur,
    la base seule ne suffit pas.
    """
    return hmac.new(settings.SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()


class PasswordResetCode(models.Model):
    """
    Demande de réinitialisation du mot de passe, en deux temps :
    1. un code à 6 chiffres est envoyé par email (valable quelques minutes, essais limités) ;
    2. une fois le code vérifié, il est remplacé par un jeton de réinitialisation à usage unique,
       qui permet de choisir le nouveau mot de passe.
    Ni le code ni le jeton ne sont conservés en clair : seulement leur empreinte.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_codes')

    # Empreinte du code envoyé par email (vidée une fois le code vérifié)
    code_hash = models.CharField(max_length=64, blank=True)

    # Nombre d'essais de code déjà faits
    attempts = models.PositiveSmallIntegerField(default=0)

    # Empreinte du jeton de réinitialisation, remplie une fois le code vérifié
    token_hash = models.CharField(max_length=64, blank=True, db_index=True)

    # Fin de validité du code, puis du jeton
    expires_at = models.DateTimeField()

    # Date d'utilisation du jeton : la demande ne sert plus
    used_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Réinitialisation de {self.user.username} ({self.created_at:%Y-%m-%d %H:%M})"

    @staticmethod
    def validity():
        return timedelta(minutes=settings.PASSWORD_RESET_CODE_MINUTES)

    @classmethod
    def issue(cls, user):
        """
        Crée une demande pour cet utilisateur et renvoie le code en clair (à envoyer par email).
        Les demandes précédentes encore en cours sont supprimées : seul le dernier code compte.
        """
        cls.objects.filter(user=user, used_at__isnull=True).delete()
        code = f"{secrets.randbelow(1_000_000):06d}"
        cls.objects.create(
            user=user,
            code_hash=_digest(f"{user.pk}:{code}"),
            expires_at=timezone.now() + cls.validity(),
        )
        return code

    @classmethod
    def pending_for(cls, user):
        """Dernière demande dont le code peut encore être essayé, ou None"""
        return cls.objects.filter(
            user=user,
            used_at__isnull=True,
            token_hash='',
            expires_at__gt=timezone.now(),
            attempts__lt=settings.PASSWORD_RESET_MAX_ATTEMPTS,
        ).exclude(code_hash='').first()

    def check_code(self, code):
        """
        Compte un essai, puis compare le code (comparaison à temps constant).
        Le compteur est incrémenté en base avant la comparaison : des essais simultanés
        ne peuvent pas dépasser la limite.
        """
        type(self).objects.filter(pk=self.pk).update(attempts=models.F('attempts') + 1)
        self.refresh_from_db(fields=['attempts'])
        return hmac.compare_digest(self.code_hash, _digest(f"{self.user_id}:{code}"))

    @property
    def attempts_left(self):
        return max(settings.PASSWORD_RESET_MAX_ATTEMPTS - self.attempts, 0)

    def exchange_for_token(self):
        """
        Code vérifié : le remplace par un jeton de réinitialisation à usage unique et le renvoie
        en clair. Le code ne peut plus être réutilisé.
        """
        token = secrets.token_urlsafe(32)
        self.code_hash = ''
        self.token_hash = _digest(token)
        self.expires_at = timezone.now() + self.validity()
        self.save(update_fields=['code_hash', 'token_hash', 'expires_at'])
        return token

    @classmethod
    def from_token(cls, token):
        """Demande correspondant à un jeton valide (vérifié, non utilisé, non expiré), ou None"""
        if not token:
            return None
        return cls.objects.select_related('user').filter(
            token_hash=_digest(token),
            used_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).first()
