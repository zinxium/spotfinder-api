SpotFinder API

SpotFinder est une API REST complète pour la découverte et la gestion de lieux. Développée avec Django 6.0.2 et Django REST Framework, elle offre des fonctionnalités avancées d'authentification, de gestion d'images, d'avis, de favoris et d'historique des visites.

Fonctionnalités

- Gestion complète des lieux (CRUD) avec informations détaillées
- Système d'authentification basé sur les tokens
- Upload et gestion des images pour les lieux
- Système d'avis et de notation des lieux
- Gestion des favoris utilisateur
- Historique des visites des lieux
- Documentation API interactive avec Swagger/OpenAPI
- Pagination et filtrage avancés
- Interface d'administration Django
- Configuration sécurisée des variables d'environnement

Installation

Prérequis

- Python 3.8+
- PostgreSQL 12+
- Git

Étapes d'installation

1. Cloner le dépôt :

   ```bash
   git clone git@github-personal:zinxium/spotfinder-api.git
   cd spotfinder-api
   ```

2. Créer et activer l'environnement virtuel :

   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Linux/Mac
   source venv/bin/activate
   ```

3. Installer les dépendances :

   ```bash
   pip install -r requirements.txt
   ```

4. Configurer les variables d'environnement :

   Copier le fichier .env.example vers .env et le modifier selon vos besoins.

5. Appliquer les migrations :

   ```bash
   python manage.py migrate
   ```

6. Créer un superutilisateur (optionnel, pour l'admin) :

   ```bash
   python manage.py createsuperuser
   ```

7. Lancer le serveur :

   ```bash
   python manage.py runserver
   ```

Configuration

Variables d'environnement

Le projet utilise python-decouple pour gérer les variables d'environnement. Les variables importantes incluent :

- DEBUG : Mode développement (True/False)
- SECRET_KEY : Clé secrète Django (obligatoire en production)
- ALLOWED_HOSTS : Hôtes autorisés (obligatoire en production)
- DB_NAME : Nom de la base de données PostgreSQL
- DB_USER : Utilisateur PostgreSQL
- DB_PASSWORD : Mot de passe PostgreSQL
- DB_HOST : Hôte PostgreSQL (défaut: localhost)
- DB_PORT : Port PostgreSQL (défaut: 5432)
- USE_CLOUDINARY : Utiliser Cloudinary pour le stockage (True/False)
- CLOUDINARY_CLOUD_NAME : Nom du cloud Cloudinary
- CLOUDINARY_API_KEY : Clé API Cloudinary
- CLOUDINARY_API_SECRET : Secret API Cloudinary

Voir le fichier ENVIRONMENT_CONFIG.md pour plus de détails.

Utilisation

API Endpoints

L'API expose les endpoints suivants :

- /api/places/ : Gestion des lieux
- /api/categories/ : Gestion des catégories
- /api/reviews/ : Gestion des avis
- /api/favorites/ : Gestion des favoris
- /api/visits/ : Historique des visites

Documentation API

La documentation interactive est disponible via Swagger à l'adresse /api/docs/ une fois le serveur lancé.

Tests

Pour exécuter les tests :

```bash
python manage.py test
```

Administration

L'interface d'administration Django est accessible via /admin/ après avoir créé un superutilisateur.

Sécurité

Le projet implémente une approche "fail-fast" pour les variables d'environnement sensibles. En production, SECRET_KEY et ALLOWED_HOSTS sont obligatoires et ne peuvent pas utiliser de valeurs par défaut.

Contribuer

1. Forker le projet
2. Créer une branche pour votre fonctionnalité
3. Commiter vos changements
4. Pousser vers la branche
5. Ouvrir une Pull Request

Licence

Ce projet est sous licence MIT. Voir le fichier LICENSE pour plus de détails.