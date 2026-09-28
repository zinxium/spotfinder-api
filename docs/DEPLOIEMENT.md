# Déploiement sur Render

L'API se déploie sur [Render](https://render.com) à partir de [`render.yaml`](../render.yaml) (Blueprint).

## Ce qui se passe à chaque déploiement

| Étape | Commande | Rôle |
|---|---|---|
| Build | `pip install -r requirements.txt` | Installe les dépendances (Python 3.12.7) |
| Build | `python manage.py collectstatic --noinput` | Prépare les fichiers statiques (admin, Swagger), compressés et versionnés par WhiteNoise |
| Build | `python manage.py migrate` | Applique les migrations de la base |
| Démarrage | `gunicorn spotfinderapi.wsgi:application` | Lance le serveur sur le port fourni par Render |

## Prérequis

1. **Une base PostgreSQL** : Render PostgreSQL ou une autre, dont on récupère l'URL de connexion.
2. **Un compte Cloudinary** pour les images. **Obligatoire en production** : le disque d'un service Render est effacé à chaque déploiement, donc des images stockées localement seraient perdues.

## Première mise en place

1. Sur Render : **New > Blueprint**, puis choisir le dépôt `zinxium/spotfinder-api`.
2. Render lit `render.yaml`, génère `SECRET_KEY` et demande les variables marquées `sync: false` :

| Variable | Valeur |
|---|---|
| `ALLOWED_HOSTS` | Domaine du service, ex. `spotfinder-api.onrender.com` |
| `DATABASE_URL` | URL PostgreSQL, ex. `postgresql://user:pass@host:5432/db` |
| `CLOUDINARY_CLOUD_NAME` | Tableau de bord Cloudinary |
| `CLOUDINARY_API_KEY` | Tableau de bord Cloudinary |
| `CLOUDINARY_API_SECRET` | Tableau de bord Cloudinary |
| `CLOUDINARY_URL` | `cloudinary://<api_key>:<api_secret>@<cloud_name>` |

3. Lancer le déploiement, puis créer un administrateur depuis l'onglet **Shell** du service :
   ```bash
   python manage.py createsuperuser
   ```
   Utiliser un mot de passe **nouveau et unique**. L'ancien `db.sqlite3`, visible dans l'historique Git public, contenait un compte administrateur.

> Si le service a été créé à la main (sans Blueprint), `render.yaml` n'est **pas** appliqué. Il faut reporter ces réglages dans **Settings** et **Environment** du service : Python 3.12.7, build et start command ci-dessus, variables ci-dessus.

## Variables optionnelles

Toutes sont décrites dans [`.env.example`](../.env.example) : durée des tokens JWT, limites de débit, CORS, etc. Les valeurs par défaut conviennent pour la production.

## Vérifier un déploiement

| Test | Résultat attendu |
|---|---|
| `GET https://<domaine>/` | `{"message": "Welcome to Spotfinder API", "docs": "/api/docs/"}` |
| `https://<domaine>/api/docs/` | Swagger s'affiche **avec sa mise en forme** (sinon, les fichiers statiques n'ont pas été collectés) |
| `https://<domaine>/admin/` | Page de connexion stylée |
| Créer un lieu avec une image, puis ouvrir l'URL de l'image | L'URL commence par `https://res.cloudinary.com/` |
| `http://<domaine>/` | Redirection automatique vers `https://` |

## En cas d'échec

| Symptôme dans les logs Render | Cause probable |
|---|---|
| `ImproperlyConfigured: La variable d'environnement X est obligatoire en production` | Variable `X` manquante dans **Environment** |
| `DisallowedHost` / erreur 400 | Domaine absent de `ALLOWED_HOSTS` |
| Le navigateur affiche « trop de redirections » | `TRUST_PROXY_SSL_HEADER` mis à `False` alors que l'API est derrière le proxy Render |
| `ValueError: Missing staticfiles manifest entry` | `collectstatic` absent de la build command |
| Erreur de version Python ou de dépendance | `PYTHON_VERSION` différente de 3.12.x |

## Vérifier en local avant de déployer

Simuler la production, sans PostgreSQL :

```powershell
$env:DEBUG="False"; $env:SECRET_KEY="cle-de-test-longue-et-aleatoire-uniquement-locale"
$env:ALLOWED_HOSTS="localhost"; $env:DATABASE_URL="sqlite:///db.sqlite3"
python manage.py collectstatic --noinput
python manage.py check --deploy
```

`check --deploy` doit afficher `System check identified no issues`.
