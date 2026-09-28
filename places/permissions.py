from rest_framework import permissions


# ============================================
# PERMISSION: Admin ou lecture seule
# ============================================
class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Lecture publique, modification réservée aux administrateurs.
    Utilisé pour les catégories.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)


# ============================================
# PERMISSION: Propriétaire ou lecture seule
# ============================================
class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Lecture publique, modification réservée au propriétaire de l'objet
    (ou à un administrateur).
    L'attribut `owner_field` de la vue indique le champ propriétaire (défaut: 'owner').
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.is_staff:
            return True
        owner_field = getattr(view, 'owner_field', 'owner')
        return getattr(obj, f'{owner_field}_id', None) == request.user.id
