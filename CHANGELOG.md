[1.0.0] - 2026-02-12
Documentation API & Swagger

Structuration complète de la documentation Swagger
- Ajout de tags drf-spectacular pour tous les ViewSets (Places, Reviews, Favorites, Users, Categories, Visits)
- Tagging des endpoints d'authentification (register, login, logout)
- Création de serializers typés pour l'authentification (RegisterSerializer, LoginSerializer, LogoutSerializer)
- Type hints ajoutés aux méthodes de serializers (get_image, get_reviews_count, etc.)
- Configuration SPECTACULAR_SETTINGS dans settings.py avec titre et description
- Routes racine et d'authentification documentées dans Swagger
- Tous les endpoints CRUD correctement catégorisés (create, update, partial_update, destroy)
- Documentation Swagger professionnelle sur `/api/docs/`

Configuration ALLOWED_HOSTS depuis .env
- ALLOWED_HOSTS maintenant configuré depuis la variable d'environnement
- Défaut à "*" pour le développement
- Conversion automatique en liste depuis le .env
- Validation correcte pour Django

Route racine d'accueil
- Ajout d'une vue racine GET / qui retourne un message de bienvenue
- Lien vers la documentation `/api/docs/`
- Évite les erreurs 404 sur la racine

[0.9.0] - 2026-02-11
Stockage Cloud

Configuration Cloudinary comme alternative à S3
- Ajout de cloudinary et django-cloudinary-storage
- Configuration conditionnelle USE_CLOUDINARY
- Variables CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
- Stockage automatique avec optimisation d'images
- CDN intégré et transformations d'images
- Documentation CLOUDINARY_CONFIG.md créée
- Variables ajoutées dans .env et .env.example

[0.8.0] - 2026-02-11
Base de données

Migration vers PostgreSQL
- Configuration PostgreSQL dans settings.py avec variables d'environnement
- Variables DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
- Ajout de psycopg2-binary dans requirements.txt
- Mise à jour de .env.example avec variables PostgreSQL
- Mise à jour de la documentation README et ENVIRONMENT_CONFIG.md
- Prérequis PostgreSQL ajouté au README

[0.7.0] - 2026-02-11
Sécurité

Stratégie fail-fast pour les variables d'environnement critiques
- SECRET_KEY et ALLOWED_HOSTS obligatoires en production (DEBUG=False)
- Exception ImproperlyConfigured si variables manquantes en prod
- Validation ALLOWED_HOSTS non vide en production
- Fonction get_secret() pour gérer les variables obligatoires
- Développement préserve les valeurs par défaut sûres
- Production impose la configuration explicite
- Documentation mise à jour avec stratégie fail-fast

[0.6.0] - 2026-02-11
Sécurité

Renforcement de la sécurité avec variables d'environnement
- Installation de python-decouple pour la gestion des secrets
- Déplacement de SECRET_KEY, DEBUG, ALLOWED_HOSTS vers .env
- Création de .env avec valeurs de développement sûres
- Création de .env.example comme template pour l'équipe
- Configuration ALLOWED_HOSTS avec valeurs par défaut sécurisées
- Variables MEDIA_URL/MEDIA_ROOT configurables
- Documentation complète dans ENVIRONMENT_CONFIG.md
- .env exclu du versioning Git (.gitignore déjà configuré)

[0.5.0] - 2026-02-11
Ajouté

Documentation complète du stockage des images
- Explication du système ImageField avec upload_to='places/'
- Configuration MEDIA_URL et MEDIA_ROOT
- Structure des dossiers media/places/
- Guide d'upload via API (cURL, Python)
- Configuration pour production (Nginx, S3)
- Bonnes pratiques et débogage
- Fichier IMAGE_STORAGE.md créé

[0.4.0] - 2026-02-11
Ajouté

Routes d'historique des visites avec nouveau modèle Visit
- Modèle Visit avec champs : user, place, visited_at, duration_minutes, personal_note
- Serializer VisitSerializer avec informations détaillées des places
- ViewSet VisitViewSet avec filtrage par utilisateur et place
- Routes CRUD complètes sur /api/visits/
- Configuration admin complète pour la gestion des visites
- Pagination et permissions appropriées

[0.3.0] - 2026-02-11
Ajouté

Fichier .gitignore complet pour le projet Django
- Exclusion des fichiers Python (__pycache__, *.pyc, etc.)
- Exclusion de l'environnement virtuel (venv/)
- Exclusion de la base de données SQLite (db.sqlite3)
- Exclusion des fichiers médias et statiques
- Exclusion des logs et fichiers temporaires
- Exclusion des fichiers IDE (VSCode, PyCharm, etc.)
- Exclusion des fichiers système (Windows, macOS, Linux)
- Configuration complète pour le développement collaboratif

[0.2.0] - 2026-02-11
Ajouté

Documentation Swagger/OpenAPI complète avec drf-spectacular
- Interface Swagger UI interactive sur /api/docs/
- Documentation ReDoc sur /api/redoc/
- Schéma OpenAPI 3.0 sur /api/schema/
- Documentation automatique de tous les endpoints API
- Configuration complète avec titre, description et métadonnées

[0.1.0] - 2026-02-11
Ajouté

Structure de projet Django initialisée

Application places créée

Modèle Place avec champs : name, description, image, budget

Endpoint REST /api/places/ pour CRUD complet des lieux

Base SQLite utilisée pour le développement

Support des migrations Django

À faire

Ajouter authentification et permissions

Ajouter filtrage et pagination sur /api/places/

Ajouter gestion des images pour les lieux via API

Préparer pour déploiement sur PostgreSQL

Ajouter endpoints pour d’autres entités (ex: categories)