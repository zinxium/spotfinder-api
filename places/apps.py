from django.apps import AppConfig


class PlacesConfig(AppConfig):
    name = 'places'

    def ready(self):
        # Branche les signaux (note moyenne des lieux recalculée à chaque changement d'avis)
        from . import signals  # noqa: F401
