# ✅ Connexion Render PostgreSQL - Configuration complète

## Status: Connecté avec succès ✅

La base de données Render PostgreSQL est **entièrement configurée et testée**.

---

## 📋 Infos de connexion Render

```
Hostname: dpg-d66clsesb7us73avnd30-a
Port: 5432
Database: spotfinder_udra
Username: spotfinder
Password: TK7snyL5tROKX5wGwHgKMZ9GnuyG2jU4
Region: Oregon (us-west)
```

---

## 🔗 URLs de connexion

### URL Interne (Production - Services Render dans la même région)
```
postgresql://spotfinder:TK7snyL5tROKX5wGwHgKMZ9GnuyG2jU4@dpg-d66clsesb7us73avnd30-a/spotfinder_udra
```
**Utiliser dans:** Render Web Service environment (render.yaml, dashboard)

### URL Externe (Développement local - Depuis ton PC Windows)
```
postgresql://spotfinder:TK7snyL5tROKX5wGwHgKMZ9GnuyG2jU4@dpg-d66clsesb7us73avnd30-a.oregon-postgres.render.com/spotfinder_udra
```
**Utiliser dans:** .env local, tests depuis Windows

---

## ✅ Vérifications effectuées

| Vérification | Status | Détails |
|-------------|--------|---------|
| Django settings validation | ✅ | `python manage.py check` → OK |
| Database connection | ✅ | Connection successful |
| Migrations | ✅ | 24 appliquées avec succès |
| Superuser creation | ✅ | `admin` créé |
| dj-database-url | ✅ | Associé et fonctionnel |

---

## 📝 Configuration actuelle (.env)

```dotenv
# DATABASE_URL avec URL externe pour tests locaux
DATABASE_URL=postgresql://spotfinder:TK7snyL5tROKX5wGwHgKMZ9GnuyG2jU4@dpg-d66clsesb7us73avnd30-a.oregon-postgres.render.com/spotfinder_udra
```

### ⚠️ Important pour le déploiement Render

**Avant de déployer sur Render, remplacer DATABASE_URL par l'URL INTERNE dans les variables d'environnement Render:**

```
DATABASE_URL=postgresql://spotfinder:TK7snyL5tROKX5wGwHgKMZ9GnuyG2jU4@dpg-d66clsesb7us73avnd30-a/spotfinder_udra
```

(Sans le `.oregon-postgres.render.com`)

---

## 🚀 Prochaines étapes

### 1. Mettre à jour Render Dashboard

**Web Service → Environment Variables:**

```
DEBUG=False
SECRET_KEY=your-production-secret-key
ALLOWED_HOSTS=your-app-name.onrender.com
DATABASE_URL=postgresql://spotfinder:TK7snyL5tROKX5wGwHgKMZ9GnuyG2jU4@dpg-d66clsesb7us73avnd30-a/spotfinder_udra
CLOUDINARY_URL=cloudinary://572829515971641:QbtGvsWxH_fCgdASc6vRVmJvVLU@dkpacwzgb
USE_CLOUDINARY=True
```

### 2. Vérifier render.yaml

Confirm que le fichier `render.yaml` contient:
```yaml
buildCommand: "pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate"
startCommand: "gunicorn spotfinderapi.wsgi:application"
```

### 3. Déployer sur Render

```bash
git add .
git commit -m "Configure Render PostgreSQL and deploy"
git push
```

Render détectera les changements et déploiera automatiquement.

---

## 🔒 Sécurité

✅ DB_PASSWORD est **OBLIGATOIRE** en production (`DEBUG=False`)  
✅ Pas de valeur par défaut dangereuse  
✅ Configuration flexible (DATABASE_URL vs credentials individuels)  
✅ Whitenoise pour fichiers statiques en production  
✅ CORS configuré pour domaines spécifiques  
✅ Headers de sécurité (SSL, HSTS, CSRF) activés en production

---

## 📖 Commandes utiles

```bash
# Tester la configuration
python manage.py check

# Afficher l'état des migrations
python manage.py showmigrations

# Faire les migrations
python manage.py migrate --noinput

# Créer un superuser
python manage.py createsuperuser

# Lancer le serveur de développement
python manage.py runserver

# Créer les fichiers statiques pour production
python manage.py collectstatic --noinput

# Lancer en production local
gunicorn spotfinderapi.wsgi:application
```

---

## 🐛 Dépannage

### "Name or service not known" (dpg-d66clsesb7us73avnd30-a)
→ URL interne Render - Utiliser SEULEMENT depuis Render Web Service  
→ Pour tests locaux: Utiliser l'URL externe `.oregon-postgres.render.com`

### "FATAL: remaining connection slots are reserved for non-replication superuser connections"
→ Trop de connexions simultanees  
→ Configurer `CONN_MAX_AGE` en production (déjà fait)

### "Relation does not exist"
→ Les migrations n'ont pas été appliquées  
→ Exécuter: `python manage.py migrate`

---

## 📞 Support et Documentation

- [Render PostgreSQL Docs](https://render.com/docs/postgresql)
- [dj-database-url PyPI](https://pypi.org/project/dj-database-url/)
- [Django Database Documentation](https://docs.djangoproject.com/en/6.0/ref/settings/#databases)

---

**Configuration complétée avec succès le 11 Feb 2026** ✅
