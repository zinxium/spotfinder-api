from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Place, Review


@receiver(post_save, sender=Review)
@receiver(post_delete, sender=Review)
def refresh_place_rating(sender, instance, **kwargs):
    """
    Garde la note moyenne du lieu à jour, quel que soit le chemin : /api/places/{id}/add_review/,
    /api/reviews/ (création, modification, suppression), l'admin, ou la suppression d'un compte.
    """
    Place.refresh_rating(instance.place_id)
