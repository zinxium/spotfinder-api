# 🚀 Déploiement sur Render

## Configuration Render

Ce projet est configuré pour être déployé facilement sur [Render.com](https://render.com).

### Prérequis

1. Compte Render gratuit : https://render.com
2. Repository GitHub avec ce code
3. PostgreSQL database sur Render (ou externe)
4. Cloudinary account (optionnel, pour images)

---

## 📋 Étapes de déploiement

### 1. **Créer la base de données PostgreSQL**

Sur le dashboard Render :
- Cliquez sur **"New +"** → **"PostgreSQL"**
- Configurez :
  - **Name** : `spotfinder-db`
  - **Database** : `spotfinder_db`
  - **User** : `spotfinder_root`
  - **Region** : Choisissez la vôtre
  - **Plan** : Free (ou plus selon vos besoins)

Copiez l'**Internal Database URL** (format `postgresql://...`).

---

### 2. **Créer le service Web**

Sur le dashboard Render :
- Cliquez sur **"New +"** → **"Web Service"**
- Connectez votre **repository GitHub**
- Configurez :
  - **Name** : `spotfinder-api`
  - **Environment** : `Python 3`
  - **Build Command** :
    ```bash
    pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
    ```
  - **Start Command** :
    ```bash
    gunicorn spotfinderapi.wsgi:application
    ```
  - **Plan** : Free (ou plus)

---

### 3. **Configurer les variables d'environnement**

Dans le Web Service Render, allez à **"Environment"** et ajoutez :

#### Option A (⭐ Recommandée) : DATABASE_URL
Le plus simple et sûr pour la production :

```env
# SÉCURITÉ
DEBUG=False
SECRET_KEY=your-production-secret-key-here
ALLOWED_HOSTS=your-app-name.onrender.com

# BASE DE DONNÉES - Render fournit automatiquement DATABASE_URL
# Copiez l'Internal Database URL depuis votre PostgreSQL Render
DATABASE_URL=postgresql://user:password@host:port/dbname

# CLOUDINARY (si vous l'utilisez)
USE_CLOUDINARY=True
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret
CLOUDINARY_URL=cloudinary://key:secret@cloud_name

# CORS
CORS_ALLOWED_ORIGINS=https://your-frontend-domain.com,https://your-app-name.onrender.com

# SÉCURITÉ (production)
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

#### Option B : Credentials individuels
⚠️ **En production, DB_PASSWORD doit être fort et défini explicitement** (pas de valeur par défaut) :

```env
# SÉCURITÉ
DEBUG=False
SECRET_KEY=your-production-secret-key-here
ALLOWED_HOSTS=your-app-name.onrender.com

# BASE DE DONNÉES - Credentials individuels
# ⚠️ IMPORTANT: DB_PASSWORD est OBLIGATOIRE en production et doit être fort
DB_NAME=spotfinder_db
DB_USER=spotfinder_root
DB_PASSWORD=your_very_secure_password_here
DB_HOST=your-db-host.render.internal
DB_PORT=5432
```

**Préférez l'Option A (DATABASE_URL) pour la production car elle est plus sûre et facile à gérer.**

---

### 4. **Générer une SECRET_KEY sécurisée**

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copiez la clé générée et collez-la dans la variable `SECRET_KEY`.

---

### 5. **Déployer**

- Render détecte automatiquement les changements sur GitHub
- Après push sur `main`, Render redéploie automatiquement
- Ou cliquez sur **"Manual Deploy"** pour forcer un déploiement

---

## ✅ Vérifier le déploiement

```bash
# Voir les logs
https://dashboard.render.com → votre Web Service → "Logs"

# Tester l'API
curl https://your-app-name.onrender.com/api/

# Accéder à Swagger
https://your-app-name.onrender.com/api/schema/swagger-ui/
```

---

## 📚 Documentation supplémentaire

- [Render Django Deployment](https://render.com/docs/deploy-django)
- [PostgreSQL sur Render](https://render.com/docs/postgresql)
- [Environment Variables](https://render.com/docs/configure-environment-variables)

---

## ⚠️ Points importants

- ✅ **Whitenoise** sert les fichiers statiques en production
- ✅ **Gunicorn** est le serveur WSGI utilisé
- ✅ **PostgreSQL** est configuré automatiquement
- ✅ **HTTPS** activé par défaut sur Render
- ✅ **CORS** configuré pour éviter les erreurs de cross-origin

---

## 🔧 Dépannage

### Erreur "DisallowedHost"
→ Vérifiez que `ALLOWED_HOSTS` contient votre domaine Render

### Images ne s'affichent pas
→ Activez `USE_CLOUDINARY=True` et vérifiez les credentials

### Migrations échouent
→ Vérifiez la `DATABASE_URL` et que PostgreSQL est accessible

### Erreur 500
→ Vérifiez les logs Render pour plus de détails
