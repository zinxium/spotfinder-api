SpotFinder API

SpotFinder est une API REST pour gérer des lieux (places) avec leurs informations, images et budgets. Elle est développée en Django 6.0.2 avec Django REST Framework.

Installation

Cloner le dépôt :

git clone <URL_DU_DEPOT>
cd spotfinderapi


Créer et activer l’environnement virtuel :

python -m venv venv
# Windows
venv\Scripts\activate
# Linux / Mac
source venv/bin/activate


Installer les dépendances :

pip install -r requirements.txt


Appliquer les migrations :

python manage.py migrate


Créer un superutilisateur (pour l’admin Django) :

python manage.py createsuperuser


Lancer le serveur :

python manage.py runserver

Routes existantes

L’API expose actuellement les routes suivantes via un DRF DefaultRouter :

Méthode	URL	Action
GET	/api/places/	Liste tous les lieux
POST	/api/places/	Crée un nouveau lieu
GET	/api/places/<id>/	Récupère un lieu par son id
PUT	/api/places/<id>/	Remplace toutes les informations d’un lieu
PATCH	/api/places/<id>/	Modifie partiellement un lieu
DELETE	/api/places/<id>/	Supprime un lieu
Routes restantes à implémenter

Filtrage par budget ou autres critères (/api/places/?min_budget=...&max_budget=...)

Authentification et autorisation (JWT ou session-based)

Pagination pour les listes de lieux

Upload et gestion des images via API

Endpoints pour d’autres entités si nécessaires (par exemple categories, reviews, etc.)

Administration

L’interface d’admin est accessible via /admin/

Permet de créer, modifier et supprimer des lieux manuellement.