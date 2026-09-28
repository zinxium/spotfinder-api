# SpotFinder API

API REST de **SpotFinder**, l'application mobile de découverte de lieux (restaurants, cafés, hôtels, bars, sites touristiques) portée par la communauté.

Construite avec **Django 6** et **Django REST Framework**, authentification **JWT**.

| | |
|---|---|
| Version | voir [`spotfinderapi/__init__.py`](spotfinderapi/__init__.py) et le [CHANGELOG](CHANGELOG.md) |
| Documentation interactive | `/api/docs/` (Swagger) · `/api/redoc/` (ReDoc) · `/api/schema/` (OpenAPI) |
| Licence | MIT |

---

## Sommaire

1. [Fonctionnalités](#fonctionnalités)
2. [Démarrage rapide](#démarrage-rapide)
3. [Configuration](#configuration)
4. [Authentification](#authentification)
5. [Endpoints](#endpoints)
6. [Droits d'accès](#droits-daccès)
7. [Tests](#tests)
8. [Structure du projet](#structure-du-projet)
9. [Déploiement](#déploiement)
10. [Contribuer et versionner](#contribuer-et-versionner)

---

## Fonctionnalités

- **Lieux** : création, consultation, recherche avancée (texte, ville, catégorie, budget, note), image
- **Avis** : note de 1 à 5 et commentaire, un avis par utilisateur et par lieu, note moyenne recalculée
- **Favoris** et **historique des visites**, privés à chaque utilisateur
- **Authentification JWT** : token d'accès court, refresh token avec rotation et révocation
- **Sécurité** : droits par propriétaire, limitation de débit, validation des mots de passe (détails dans [Droits d'accès](#droits-daccès))
- Stockage des images en local ou sur **Cloudinary**

## Démarrage rapide

**Prérequis :** Python **3.12** (Django 6 ne supporte pas les versions antérieures), Git. PostgreSQL est optionnel en développement.

```bash
git clone git@github.com:zinxium/spotfinder-api.git
cd spotfinder-api

# Environnement virtuel
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux / macOS

pip install -r requirements.txt

# Configuration : copier le modèle puis l'adapter
cp .env.example .env

python manage.py migrate
python manage.py createsuperuser   # optionnel, pour /admin/
python manage.py runserver
```

L'API répond sur http://127.0.0.1:8000/ et la documentation sur http://127.0.0.1:8000/api/docs/.

> **Astuce développement :** pour utiliser SQLite au lieu de PostgreSQL, mettre `DATABASE_URL=sqlite:///db.sqlite3` dans `.env`.

## Configuration

Toutes les variables se trouvent dans [`.env.example`](.env.example). Les principales :

| Variable | Rôle | Défaut |
|---|---|---|
| `DEBUG` | Mode développement | `False` |
| `SECRET_KEY` | Clé secrète Django | **obligatoire en production** |
| `ALLOWED_HOSTS` | Domaines autorisés, séparés par des virgules | `localhost,127.0.0.1` (**obligatoire en production**) |
| `DATABASE_URL` | URL de base de données (prioritaire) | — |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | PostgreSQL si pas de `DATABASE_URL` | `DB_PASSWORD` obligatoire en production |
| `JWT_ACCESS_MINUTES` | Durée du token d'accès | `15` |
| `JWT_REFRESH_DAYS` | Durée du refresh token | `7` |
| `JWT_SIGNING_KEY` | Clé de signature des JWT | `SECRET_KEY` |
| `THROTTLE_AUTH` | Limite connexion / inscription / refresh par IP | `10/minute` |
| `THROTTLE_ANON`, `THROTTLE_USER` | Limites globales | `100/minute`, `300/minute` |
| `CORS_ALLOWED_ORIGINS` | Origines web autorisées | `http://localhost:3000,...` |
| `USE_CLOUDINARY` + `CLOUDINARY_*` | Stockage des images sur Cloudinary | `False` |

**Principe fail-fast :** avec `DEBUG=False`, l'application refuse de démarrer si une variable obligatoire manque, plutôt que d'utiliser une valeur par défaut dangereuse.

## Authentification

L'API utilise des **JSON Web Tokens**. Guide complet, avec l'intégration côté application mobile : **[docs/AUTHENTIFICATION.md](docs/AUTHENTIFICATION.md)**.

En bref :

```http
POST /api/auth/login/
{"username": "alice", "password": "..."}

→ 200 {"user": {...}, "access": "<jwt>", "refresh": "<jwt>"}
```

Puis dans chaque requête : `Authorization: Bearer <access>`.

## Endpoints

Tous les chemins sont préfixés par `/api/`. Le détail des paramètres et des réponses est dans Swagger (`/api/docs/`).

### Authentification

| Méthode | Chemin | Accès | Description |
|---|---|---|---|
| POST | `auth/register/` | public | Créer un compte → tokens |
| POST | `auth/login/` | public | Se connecter → tokens |
| POST | `auth/refresh/` | public | Nouveau couple access/refresh |
| POST | `auth/logout/` | connecté | Révoquer le refresh token |

### Ressources

| Ressource | Chemin | Lecture | Écriture |
|---|---|---|---|
| Lieux | `places/` | public | connecté (création), propriétaire (modification) |
| Recherche | `places/search/?search=&city=&category=&budget_min=&budget_max=&min_rating=` | public | — |
| Avis d'un lieu | `places/{id}/reviews/`, `places/{id}/add_review/` | public | connecté |
| Favori d'un lieu | `places/{id}/favorite/` (POST / DELETE) | — | connecté |
| Avis | `reviews/?place_id=` | public | connecté (création), auteur (modification) |
| Catégories | `categories/` | public | admin |
| Favoris | `favorites/`, `favorites/toggle/` | propriétaire | propriétaire |
| Visites | `visits/?place_id=` | propriétaire | propriétaire |
| Profil | `users/`, `users/{id}/places/` | soi-même (admin : tous) | soi-même |

Les listes sont paginées : `?page=2&page_size=20` (100 maximum).

## Droits d'accès

| Règle | Détail |
|---|---|
| Authentification requise par défaut | Chaque vue publique l'autorise explicitement |
| Lieux | Seul le propriétaire (ou un admin) modifie ou supprime ; `owner` et `rating` sont fixés par le serveur |
| Avis | Seul l'auteur (ou un admin) modifie ou supprime |
| Catégories | Modification réservée aux admins |
| Favoris, visites, profil | Visibles uniquement par leur propriétaire |
| Création de compte | Uniquement via `auth/register/` (mots de passe validés) |
| Anti brute-force | 10 tentatives par minute et par IP sur login, register et refresh → `429` |
| Pas de fuite d'information | Même erreur pour « utilisateur inconnu » et « mauvais mot de passe » ; pas de message d'exception interne renvoyé |

## Tests

Les tests couvrent l'authentification JWT et tous les droits d'accès ci-dessus.

```bash
python manage.py test places
```

Ils tournent aussi automatiquement sur GitHub Actions à chaque push et pull request vers `main` (voir [`.github/workflows/django.yml`](.github/workflows/django.yml)).

## Structure du projet

```
spotfinder-api/
├── spotfinderapi/          # Configuration du projet Django
│   ├── __init__.py         # __version__ : version de l'API
│   ├── settings.py         # Réglages (sécurité, JWT, CORS, stockage…)
│   └── urls.py             # Routes racine, admin, documentation
├── places/                 # Application principale
│   ├── models.py           # Place, Category, Review, Favorite, Visit
│   ├── serializers.py      # Conversion JSON et validation
│   ├── permissions.py      # IsOwnerOrReadOnly, IsAdminOrReadOnly
│   ├── views.py            # ViewSets et vues d'authentification
│   ├── urls.py             # Routes /api/…
│   └── tests.py            # Tests de sécurité et d'authentification
├── docs/                   # Documentation détaillée
├── schema.yml              # Schéma OpenAPI généré
├── CHANGELOG.md            # Historique des versions
└── CONTRIBUTING.md         # Branches, commits, versions
```

## Déploiement

Déploiement sur Render via [`render.yaml`](render.yaml). Guide pas à pas, variables et vérifications : **[docs/DEPLOIEMENT.md](docs/DEPLOIEMENT.md)**.

## Contribuer et versionner

Branches, conventions de commit, gestion des versions et checklist avant fusion : **[CONTRIBUTING.md](CONTRIBUTING.md)**.

## Licence

MIT, voir [LICENSE](LICENSE).
