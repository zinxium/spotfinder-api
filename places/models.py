from django.db import models
from django.contrib.auth.models import User

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

    # Propriétaire/créateur du lieu (lien avec l'utilisateur)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='places', null=True, blank=True)

    # Dates de suivi
    # Date de création automatique (ne change jamais)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Date de modification automatique (mise à jour à chaque modification)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        """Affiche le nom de la place"""
        return self.name

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
        return f"{self.user.username} - {self.place.name} ({self.rating}★)"
    
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

