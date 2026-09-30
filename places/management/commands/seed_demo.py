"""
Données de démonstration pour le développement : un compte « demo », des lieux et des avis.

Usage :
    python manage.py seed_demo                      # mot de passe généré et affiché une fois
    python manage.py seed_demo --password "..."     # mot de passe choisi (jamais réaffiché)

Refuse de s'exécuter en production (DEBUG=False). Relancer la commande ne crée pas de doublons ;
elle remet seulement le mot de passe du compte « demo ».
"""
import secrets

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Avg

from places.models import Place, Review

DEMO_USERNAME = 'demo'
DEMO_EMAIL = 'demo@spotfinder.local'

# Sites touristiques : vrais lieux publics. Restaurants, bars, hôtel, loisir : noms inventés,
# pour ne pas attribuer de faux avis à de vrais commerces.
PLACES = [
    {
        'name': 'Maquis Le Bon Goût',
        'category': 'restaurant',
        'city': 'Cotonou',
        'address': 'Quartier Haie Vive',
        'latitude': 6.3615,
        'longitude': 2.3938,
        'budget_min': 2000,
        'budget_max': 6000,
        'phone_number': '+229 01 00 00 00 01',
        'description': 'Cuisine béninoise : amiwo, poisson braisé, sauce arachide. (Lieu fictif de démonstration)',
    },
    {
        'name': 'Chez Tantie Rose',
        'category': 'restaurant',
        'city': 'Cotonou',
        'address': 'Akpakpa',
        'latitude': 6.3702,
        'longitude': 2.4478,
        'budget_min': 1500,
        'budget_max': 4000,
        'description': 'Plats du jour faits maison, ambiance familiale. (Lieu fictif de démonstration)',
    },
    {
        'name': 'Le Rooftop Lagune',
        'category': 'bar',
        'city': 'Cotonou',
        'address': 'Ganhi',
        'latitude': 6.3565,
        'longitude': 2.4302,
        'budget_min': 5000,
        'budget_max': 15000,
        'description': 'Vue sur la lagune, cocktails et musique live le week-end. (Lieu fictif de démonstration)',
    },
    {
        'name': 'Hôtel Les Cocotiers',
        'category': 'hotel',
        'city': 'Ouidah',
        'address': 'Route des pêches',
        'latitude': 6.3290,
        'longitude': 2.0850,
        'budget_min': 25000,
        'budget_max': 60000,
        'description': 'Chambres au calme à deux pas de la plage. (Lieu fictif de démonstration)',
    },
    {
        'name': 'Espace Jeux Soleil',
        'category': 'loisir',
        'city': 'Porto-Novo',
        'address': 'Ouando',
        'latitude': 6.5035,
        'longitude': 2.6120,
        'budget_min': 1000,
        'budget_max': 5000,
        'description': 'Jeux pour enfants, billard et baby-foot. (Lieu fictif de démonstration)',
    },
    {
        'name': 'Porte du Non-Retour',
        'category': 'touristique',
        'city': 'Ouidah',
        'address': 'Plage de Ouidah, fin de la Route des Esclaves',
        'latitude': 6.3240,
        'longitude': 2.0890,
        'description': 'Monument mémoriel de la traite négrière, au bout de la Route des Esclaves.',
    },
    {
        'name': 'Place de l’Amazone',
        'category': 'touristique',
        'city': 'Cotonou',
        'address': 'Boulevard de la Marina',
        'latitude': 6.3560,
        'longitude': 2.4050,
        'description': 'Place et statue monumentale en hommage aux guerrières du royaume du Danhomè.',
    },
    {
        'name': 'Jardin des Plantes et de la Nature',
        'category': 'touristique',
        'city': 'Porto-Novo',
        'address': 'Centre-ville',
        'latitude': 6.4970,
        'longitude': 2.6040,
        'description': 'Jardin botanique ombragé au cœur de la capitale.',
    },
]

# Auteurs des avis d'exemple : comptes sans mot de passe utilisable (connexion impossible)
REVIEWERS = ['awa_demo', 'koffi_demo', 'sena_demo']
REVIEWS = [
    ('Maquis Le Bon Goût', 'awa_demo', 5, 'Le meilleur amiwo du quartier, service rapide et accueil chaleureux.'),
    ('Maquis Le Bon Goût', 'koffi_demo', 4, 'Très bon rapport qualité-prix, un peu d’attente le midi.'),
    ('Chez Tantie Rose', 'sena_demo', 5, 'Comme à la maison. Le plat du jour change tous les jours.'),
    ('Le Rooftop Lagune', 'awa_demo', 4, 'Superbe vue au coucher du soleil, cocktails un peu chers.'),
    ('Porte du Non-Retour', 'koffi_demo', 5, 'Un lieu émouvant, à visiter avec un guide pour comprendre l’histoire.'),
    ('Place de l’Amazone', 'sena_demo', 4, 'Impressionnant de nuit quand la statue est éclairée.'),
]


class Command(BaseCommand):
    help = 'Crée un compte « demo », des lieux et des avis de démonstration (développement uniquement).'

    def add_arguments(self, parser):
        parser.add_argument('--password', help='Mot de passe du compte « demo » (sinon généré et affiché)')

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Refusé : données de démonstration réservées au développement (DEBUG=True).')

        password = options['password']
        generated = password is None
        if generated:
            password = secrets.token_urlsafe(12)
        try:
            validate_password(password)
        except ValidationError as error:
            raise CommandError('Mot de passe refusé : ' + ' '.join(error.messages))

        with transaction.atomic():
            demo, created = User.objects.get_or_create(username=DEMO_USERNAME, defaults={'email': DEMO_EMAIL})
            demo.set_password(password)
            demo.save()

            places = {}
            for data in PLACES:
                fields = {key: value for key, value in data.items() if key != 'name'}
                place, _ = Place.objects.get_or_create(name=data['name'], defaults={**fields, 'owner': demo})
                places[place.name] = place

            reviewers = {}
            for username in REVIEWERS:
                reviewer, was_created = User.objects.get_or_create(username=username)
                if was_created:
                    reviewer.set_unusable_password()
                    reviewer.save()
                reviewers[username] = reviewer

            for place_name, username, rating, comment in REVIEWS:
                Review.objects.get_or_create(
                    place=places[place_name],
                    user=reviewers[username],
                    defaults={'rating': rating, 'comment': comment},
                )

            # Note moyenne de chaque lieu, comme après un avis ajouté depuis l'application
            for place in places.values():
                average = Review.objects.filter(place=place).aggregate(Avg('rating'))['rating__avg']
                place.rating = round(average, 2) if average else 0
                place.save(update_fields=['rating'])

        self.stdout.write(self.style.SUCCESS(
            f'Données de démonstration prêtes : {len(PLACES)} lieux, {len(REVIEWS)} avis.'
        ))
        self.stdout.write(f"Compte {'créé' if created else 'mis à jour'} — nom d'utilisateur : {DEMO_USERNAME}")
        if generated:
            self.stdout.write(f'Mot de passe : {password}')
            self.stdout.write('Notez-le : il ne sera plus affiché (relancez la commande pour en générer un autre).')
        else:
            self.stdout.write('Mot de passe : celui passé avec --password')
