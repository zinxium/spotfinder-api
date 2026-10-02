# Changelog

Toutes les modifications notables de l'API SpotFinder sont consignées ici.

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Versions : [Semantic Versioning](https://semver.org/lang/fr/). Règles détaillées dans [CONTRIBUTING.md](CONTRIBUTING.md).

## [Non publié]

### Ajouté
- Commande `python manage.py seed_demo` : compte `demo` (mot de passe généré et affiché une fois, ou `--password`), 8 lieux et 6 avis de démonstration ; refusée si `DEBUG=False`, sans doublons si relancée (5 tests)
- **Recherche sans accents** : `search` ignore accents et majuscules (« benin » trouve « Bénin »), chaque mot devant apparaître dans le nom, la ville, l'adresse ou la description. Champ interne `search_text` (non renvoyé), recalculé à chaque enregistrement ; migration `0007` qui le remplit pour les lieux existants. Fonctionne sur PostgreSQL comme sur SQLite (4 tests)
- **Recherche autour d'une position** : paramètres `lat`, `lng` et `radius_km` sur `/api/places/search/`, tri du plus proche au plus loin, champ `distance_km` dans chaque lieu. Distance calculée par la base (haversine), précédée d'un préfiltre rectangulaire (4 tests)
- **Statistiques du profil** : `GET /api/users/me/stats/` (visites, favoris, lieux ajoutés, avis) en un seul appel, au lieu de trois (2 tests)
- Visites : `place_details`, le lieu complet (photo, note), comme pour les favoris
- **Changement de mot de passe** : `POST /api/auth/password/change/` (`current_password`, `new_password`). Toutes les sessions sont révoquées ; la réponse contient de nouveaux tokens pour rester connecté sur cet appareil ; email d'alerte (4 tests)
- **Mot de passe oublié** en 3 étapes : `POST /api/auth/password/reset/` (code à 6 chiffres par email), `.../verify/` (jeton à usage unique), `.../confirm/` (nouveau mot de passe, sessions révoquées, email d'alerte). Même réponse que l'email soit inscrit ou non ; code et jeton stockés en empreinte HMAC, valables 10 minutes, 5 essais par code ; limites par IP et par email (10 tests)
- **Suppression du compte** : `DELETE /api/users/me/` avec le mot de passe. Supprime avis (notes recalculées), favoris, visites et sessions ; email de confirmation (4 tests)
- Emails de compte envoyés en arrière-plan ; SMTP configurable (`EMAIL_*`), console en développement ; fournisseur gratuit conseillé et réglages Render dans `docs/DEPLOIEMENT.md`
- `GET /api/favorites/` : chaque favori inclut `place_details`, le lieu complet au même format que `/api/places/{id}/`. L'application affiche ainsi la liste des favoris sans une requête par lieu. Champs existants inchangés (rétrocompatible).

### Modifié
- Un lieu dont l'auteur supprime son compte reste en ligne, sans auteur (`owner` passe à vide, migration `0006`) au lieu d'être supprimé avec les avis, favoris et visites des autres membres
- `DELETE /api/users/{id}/` est réservé aux administrateurs : il supprimait un compte sans demander le mot de passe
- Flux Git : branche d'intégration `dev` (les branches de travail y sont fusionnées), `main` reçoit `dev` quand tout est fonctionnel
- CI (tests Django et revue des dépendances) déclenchée aussi sur `dev`
- Messages d'erreur en **français** par défaut (`LANGUAGE_CODE=fr`) : validation Django et DRF, et la plupart des messages JWT (quelques-uns restent en anglais, faute de traduction dans simplejwt)

### Corrigé
- **Date des visites** : `visited_at` était fixé à la date d'enregistrement et la date choisie dans l'app était ignorée (visite du 27 enregistrée au 30). La date envoyée est conservée (maintenant par défaut), modifiable, et refusée si elle est dans le futur ; migration `0007` (4 tests)
- **Photo d'un lieu** : le champ `image` était en lecture seule, une photo envoyée à la création était ignorée sans erreur. Il accepte maintenant un envoi `multipart/form-data` ; le fichier doit être une vraie image (Pillow) de 5 Mo au plus. La réponse garde une URL complète (4 tests)
- **Note d'un lieu** : modifier ou supprimer un avis par `/api/reviews/` (ou par l'admin, ou en supprimant un compte) ne recalculait pas la note, et un lieu sans avis gardait sa dernière note. Calcul centralisé (`Place.refresh_rating`), déclenché par un signal à chaque changement d'avis ; migration `0005` qui recalcule une fois toutes les notes existantes (3 tests)
- **Profil** : `PATCH /api/users/{id}/` acceptait l'email d'un autre compte. L'email reste unique sans tenir compte de la casse, comme à l'inscription, et il est enregistré en minuscules (2 tests)
- **Recherche** : `budget_min=abc` (ou une note invalide) provoquait une erreur 500. Les paramètres sont vérifiés d'abord (`PlaceSearchParamsSerializer`) et une valeur invalide renvoie 400 ; note limitée à 0-5 ; paramètres décrits dans la documentation OpenAPI (3 tests)
- Inscription : les erreurs de mot de passe (trop court, trop courant…) sont rattachées au champ `password` au lieu de `non_field_errors`, pour être affichées sous le bon champ dans l'application

## [1.1.1] - 2026-09-28

### Corrigé
- **Boucle de redirection HTTPS en production** : derrière le proxy de Render, Django recevait les requêtes en HTTP et redirigeait sans fin vers `https://`. Ajout de `SECURE_PROXY_SSL_HEADER` (désactivable avec `TRUST_PROXY_SSL_HEADER=False`).
- **Stockage des images** : `DEFAULT_FILE_STORAGE` est ignoré depuis Django 5.1, donc les images partaient sur le disque local même avec `USE_CLOUDINARY=True`, et le disque Render est effacé à chaque déploiement. Passage au réglage `STORAGES`.
- **Fichiers statiques** : `STATICFILES_STORAGE` également ignoré ; WhiteNoise compresse et versionne de nouveau les fichiers en production
- `render.yaml` : Python 3.12.7 (Django 6 ne supporte pas 3.11), suppression de l'activation d'un `venv` inexistant sur Render, `runtime` au lieu de `env` (déprécié)
- Schéma OpenAPI : plus d'avertissements pour la route racine, les favoris et les visites

### Ajouté
- `.env.example` : `TRUST_PROXY_SSL_HEADER` ; `CORS_ALLOW_CREDENTIALS=False`, aligné sur la valeur par défaut
- `render.yaml` déclare toutes les variables nécessaires ; `SECRET_KEY` est générée par Render, les secrets restent hors de Git
- Guide de déploiement : [docs/DEPLOIEMENT.md](docs/DEPLOIEMENT.md)

## [1.1.0] - 2026-09-28

### Sécurité
- **Authentification JWT** (djangorestframework-simplejwt) à la place des tokens DRF : token d'accès de 15 min, refresh token de 7 jours, rotation et révocation (blacklist) à chaque rafraîchissement
- Limitation de débit : 10 requêtes/min par IP sur connexion, inscription et refresh ; limites globales anonyme/utilisateur
- Le login ne révèle plus si un compte existe (même réponse pour un utilisateur inconnu ou un mauvais mot de passe)
- Les messages d'exception internes ne sont plus renvoyés au client
- Mots de passe validés par les règles Django (8 caractères minimum, pas trop courant, pas uniquement numérique)
- Permissions par défaut : authentification requise ; les vues publiques l'autorisent explicitement
- Lieux : seul le propriétaire (ou un admin) peut modifier ou supprimer ; `owner` et `rating` ne sont plus modifiables par le client
- Avis : seul l'auteur (ou un admin) peut modifier ou supprimer
- Catégories : modification réservée aux admins (elles étaient modifiables par n'importe qui, même sans être connecté)
- `ALLOWED_HOSTS` obligatoire en production (plus de `*` par défaut)
- `CORS_ALLOW_CREDENTIALS` désactivé par défaut (le JWT passe par l'en-tête `Authorization`)
- `db.sqlite3` n'est plus suivi par Git (il contenait des comptes et des hash de mots de passe)

### Ajouté
- `POST /api/auth/refresh/` : renouvellement du token d'accès
- `places/permissions.py` : `IsOwnerOrReadOnly`, `IsAdminOrReadOnly`
- Tests automatisés : authentification JWT et droits d'accès (22 tests)
- Version unique dans `spotfinderapi/__init__.py`, affichée par Swagger
- Documentation : README restructuré, [docs/AUTHENTIFICATION.md](docs/AUTHENTIFICATION.md), [CONTRIBUTING.md](CONTRIBUTING.md)

### Modifié
- **Incompatible** : `register` et `login` renvoient `{"user", "access", "refresh"}` au lieu de `{"user_id", "username", "email", "token"}` ; l'en-tête devient `Authorization: Bearer <access>`
- **Incompatible** : `logout` attend `{"refresh": "..."}` et répond `205`
- `register` : email obligatoire, nom d'utilisateur et email uniques sans tenir compte de la casse
- CI : Python 3.12 (Django 6 ne supporte pas 3.7 à 3.9)
- Les listes de lieux sont triées par date de création décroissante (pagination stable)

### Supprimé
- `POST /api/users/` (les comptes se créent uniquement via `/api/auth/register/`)
- Application `rest_framework.authtoken`
- Doublon de `SPECTACULAR_SETTINGS` dans `settings.py`

### Corrigé
- `add_review` valide la note (1 à 5)
- Un avis ou un favori en double renvoie `400` au lieu d'une erreur `500`

## [1.0.0] - 2026-02-12
### Documentation API & Swagger

**Structuration complète de la documentation Swagger**
- Ajout de tags drf-spectacular pour tous les ViewSets (Places, Reviews, Favorites, Users, Categories, Visits)
- Tagging des endpoints d'authentification (register, login, logout)
- Création de serializers typés pour l'authentification (RegisterSerializer, LoginSerializer, LogoutSerializer)
- Type hints ajoutés aux méthodes de serializers (get_image, get_reviews_count, etc.)
- Configuration SPECTACULAR_SETTINGS dans settings.py avec titre et description
- Routes racine et d'authentification documentées dans Swagger
- Tous les endpoints CRUD correctement catégorisés (create, update, partial_update, destroy)
- Documentation Swagger professionnelle sur `/api/docs/`

**Configuration ALLOWED_HOSTS depuis .env**
- ALLOWED_HOSTS maintenant configuré depuis la variable d'environnement
- Défaut à "*" pour le développement
- Conversion automatique en liste depuis le .env
- Validation correcte pour Django

**Route racine d'accueil**
- Ajout d'une vue racine GET / qui retourne un message de bienvenue
- Lien vers la documentation `/api/docs/`
- Évite les erreurs 404 sur la racine

## [0.9.0] - 2026-02-11
### Stockage Cloud

**Configuration Cloudinary comme alternative à S3**
- Ajout de cloudinary et django-cloudinary-storage
- Configuration conditionnelle USE_CLOUDINARY
- Variables CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
- Stockage automatique avec optimisation d'images
- CDN intégré et transformations d'images
- Documentation CLOUDINARY_CONFIG.md créée
- Variables ajoutées dans .env et .env.example

## [0.8.0] - 2026-02-11
### Base de données

**Migration vers PostgreSQL**
- Configuration PostgreSQL dans settings.py avec variables d'environnement
- Variables DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
- Ajout de psycopg2-binary dans requirements.txt
- Mise à jour de .env.example avec variables PostgreSQL
- Mise à jour de la documentation README et ENVIRONMENT_CONFIG.md
- Prérequis PostgreSQL ajouté au README

## [0.7.0] - 2026-02-11
### Sécurité

**Stratégie fail-fast pour les variables d'environnement critiques**
- SECRET_KEY et ALLOWED_HOSTS obligatoires en production (DEBUG=False)
- Exception ImproperlyConfigured si variables manquantes en prod
- Validation ALLOWED_HOSTS non vide en production
- Fonction get_secret() pour gérer les variables obligatoires
- Développement préserve les valeurs par défaut sûres
- Production impose la configuration explicite
- Documentation mise à jour avec stratégie fail-fast

## [0.6.0] - 2026-02-11
### Sécurité

**Renforcement de la sécurité avec variables d'environnement**
- Installation de python-decouple pour la gestion des secrets
- Déplacement de SECRET_KEY, DEBUG, ALLOWED_HOSTS vers .env
- Création de .env avec valeurs de développement sûres
- Création de .env.example comme template pour l'équipe
- Configuration ALLOWED_HOSTS avec valeurs par défaut sécurisées
- Variables MEDIA_URL/MEDIA_ROOT configurables
- Documentation complète dans ENVIRONMENT_CONFIG.md
- .env exclu du versioning Git (.gitignore déjà configuré)

## [0.5.0] - 2026-02-11
### Ajouté

**Documentation complète du stockage des images**
- Explication du système ImageField avec upload_to='places/'
- Configuration MEDIA_URL et MEDIA_ROOT
- Structure des dossiers media/places/
- Guide d'upload via API (cURL, Python)
- Configuration pour production (Nginx, S3)
- Bonnes pratiques et débogage
- Fichier IMAGE_STORAGE.md créé

## [0.4.0] - 2026-02-11
### Ajouté

**Routes d'historique des visites avec nouveau modèle Visit**
- Modèle Visit avec champs : user, place, visited_at, duration_minutes, personal_note
- Serializer VisitSerializer avec informations détaillées des places
- ViewSet VisitViewSet avec filtrage par utilisateur et place
- Routes CRUD complètes sur /api/visits/
- Configuration admin complète pour la gestion des visites
- Pagination et permissions appropriées

## [0.3.0] - 2026-02-11
### Ajouté

**Fichier .gitignore complet pour le projet Django**
- Exclusion des fichiers Python (__pycache__, *.pyc, etc.)
- Exclusion de l'environnement virtuel (venv/)
- Exclusion de la base de données SQLite (db.sqlite3)
- Exclusion des fichiers médias et statiques
- Exclusion des logs et fichiers temporaires
- Exclusion des fichiers IDE (VSCode, PyCharm, etc.)
- Exclusion des fichiers système (Windows, macOS, Linux)
- Configuration complète pour le développement collaboratif

## [0.2.0] - 2026-02-11
### Ajouté

**Documentation Swagger/OpenAPI complète avec drf-spectacular**
- Interface Swagger UI interactive sur /api/docs/
- Documentation ReDoc sur /api/redoc/
- Schéma OpenAPI 3.0 sur /api/schema/
- Documentation automatique de tous les endpoints API
- Configuration complète avec titre, description et métadonnées

## [0.1.0] - 2026-02-11
### Ajouté
- Structure de projet Django initialisée et application `places`
- Modèle `Place` (name, description, image, budget)
- Endpoint REST `/api/places/` (CRUD complet)
- Base SQLite pour le développement et support des migrations
