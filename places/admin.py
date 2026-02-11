from django.contrib import admin
from .models import Place, Category, Review, Favorite, Visit

# ============================================
# ADMIN: Category
# ============================================
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """
    Configuration de l'affichage des catégories dans l'admin Django.
    """
    # Affiche le nom et la date dans la liste
    list_display = ('name', 'created_at')
    
    # Champs recherchables
    search_fields = ('name',)


# ============================================
# ADMIN: Place
# ============================================
@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    """
    Configuration de l'affichage des places dans l'admin Django.
    Affiche les informations principales et permet de filtrer/chercher facilement.
    """
    # Colonnes affichées dans la liste
    list_display = ('name', 'city', 'category', 'rating', 'created_at')
    
    # Champs pour filtrer la liste (colonnes à droite)
    list_filter = ('category', 'city', 'created_at')
    
    # Champs recherchables
    search_fields = ('name', 'city', 'address')
    
    # Champs en lecture seule (ne peuvent pas être modifiés)
    readonly_fields = ('rating', 'created_at', 'updated_at')


# ============================================
# ADMIN: Review
# ============================================
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """
    Configuration de l'affichage des avis dans l'admin Django.
    """
    # Colonnes affichées dans la liste
    list_display = ('user', 'place', 'rating', 'created_at')
    
    # Champs pour filtrer la liste
    list_filter = ('rating', 'created_at')
    
    # Champs recherchables
    search_fields = ('user__username', 'place__name')
    
    # Champs en lecture seule
    readonly_fields = ('created_at', 'updated_at')


# ============================================
# ADMIN: Favorite
# ============================================
@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    """
    Configuration de l'affichage des favoris dans l'admin Django.
    """
    # Colonnes affichées dans la liste
    list_display = ('user', 'place', 'created_at')
    
    # Champs pour filtrer la liste
    list_filter = ('created_at',)
    
    # Champs recherchables
    search_fields = ('user__username', 'place__name')


# ============================================
# ADMIN: Visit
# ============================================
@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    """
    Configuration de l'affichage des visites dans l'admin Django.
    """
    # Colonnes affichées dans la liste
    list_display = ('user', 'place', 'visited_at', 'duration_minutes')
    
    # Champs pour filtrer la liste
    list_filter = ('visited_at', 'duration_minutes')
    
    # Champs recherchables
    search_fields = ('user__username', 'place__name', 'personal_note')
    
    # Champs en lecture seule
    readonly_fields = ('visited_at',)
    
    # Organisation des champs dans le formulaire d'édition
    fieldsets = (
        ('Informations générales', {
            'fields': ('user', 'place', 'visited_at')
        }),
        ('Détails de la visite', {
            'fields': ('duration_minutes', 'personal_note')
        }),
    )

