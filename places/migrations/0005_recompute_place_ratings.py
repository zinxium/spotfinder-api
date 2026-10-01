from django.db import migrations
from django.db.models import Avg


def recompute_ratings(apps, schema_editor):
    """
    Recalcule une fois la note de chaque lieu : avant le signal sur Review, modifier ou supprimer
    un avis par /api/reviews/ laissait l'ancienne note (et un lieu sans avis gardait sa dernière note).
    """
    Place = apps.get_model('places', 'Place')
    Review = apps.get_model('places', 'Review')
    for place in Place.objects.all().only('id'):
        average = Review.objects.filter(place_id=place.id).aggregate(Avg('rating'))['rating__avg']
        Place.objects.filter(pk=place.id).update(rating=round(average, 2) if average is not None else 0)


class Migration(migrations.Migration):

    dependencies = [
        ('places', '0004_visit'),
    ]

    operations = [
        # Rien à défaire : revenir en arrière garde des notes justes
        migrations.RunPython(recompute_ratings, migrations.RunPython.noop),
    ]
