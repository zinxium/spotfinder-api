# Stockage des Images - SpotFinder API

## 📸 **Système de Stockage des Images**

### **Configuration Actuelle**

#### **1. Modèle Place**
```python
# Dans places/models.py
image = models.ImageField(upload_to='places/', blank=True, null=True)
```

#### **2. Settings Django**
```python
# Dans spotfinderapi/settings.py
MEDIA_URL = 'media/'           # URL d'accès aux fichiers
MEDIA_ROOT = BASE_DIR / 'media' # Chemin physique sur le disque
```

#### **3. URLs**
```python
# Dans spotfinderapi/urls.py (en mode DEBUG seulement)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

---

## 📁 **Structure des Dossiers**

```
spotfinder-api/
├── media/                    # 📂 Dossier racine des médias
│   └── places/              # 📂 Images des lieux
│       ├── cafe_du_centre.jpg
│       ├── restaurant_italia.png
│       └── ...
├── places/
│   └── models.py           # Définition ImageField
└── spotfinderapi/
    ├── settings.py         # Configuration MEDIA_URL/MEDIA_ROOT
    └── urls.py             # Servir les fichiers statiques
```

---

## 🔄 **Comment Ça Marche**

### **Upload d'une Image**
1. **Via API** : `POST /api/places/` avec `image` (multipart/form-data)
2. **Stockage** : Django sauvegarde automatiquement dans `media/places/`
3. **Nom du fichier** : Généré automatiquement (ex: `image_ABC123.jpg`)

### **Accès aux Images**
- **URL complète** : `http://localhost:8000/media/places/image_ABC123.jpg`
- **Dans l'API** : Le serializer retourne l'URL complète
- **En développement** : Servi directement par Django
- **En production** : Doit être servi par un serveur web (Nginx, Apache)

---

## 📤 **Upload via API**

### **Exemple avec cURL**
```bash
curl -X POST http://localhost:8000/api/places/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -F "name=Café du Centre" \
  -F "city=Paris" \
  -F "image=@/path/to/your/image.jpg"
```

### **Exemple avec Python**
```python
import requests

url = 'http://localhost:8000/api/places/'
headers = {'Authorization': 'Token YOUR_TOKEN'}
files = {'image': open('image.jpg', 'rb')}
data = {'name': 'Café du Centre', 'city': 'Paris'}

response = requests.post(url, headers=headers, files=files, data=data)
```

---

## ⚙️ **Configuration pour Production**

### **1. Serveur Web (Nginx)**
```nginx
# Dans nginx.conf
location /media/ {
    alias /path/to/your/project/media/;
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

### **2. Cloud Storage (AWS S3, etc.)**
Pour la production, considérez :
- **AWS S3** avec `django-storages`
- **Google Cloud Storage**
- **Azure Blob Storage**

### **3. Variables d'Environnement**
```python
# settings.py
import os
MEDIA_ROOT = os.getenv('MEDIA_ROOT', BASE_DIR / 'media')
```

---

## 🔍 **Débogage**

### **Vérifier le Stockage**
```python
# Dans Django shell
python manage.py shell

from places.models import Place
place = Place.objects.get(id=1)
print(place.image.url)      # URL d'accès
print(place.image.path)     # Chemin physique
```

### **Problèmes Courants**
- ❌ **403 Forbidden** : Vérifiez les permissions du dossier `media/`
- ❌ **404 Not Found** : Vérifiez `MEDIA_URL` et les URLs statiques
- ❌ **En production** : Configurez le serveur web pour servir `/media/`

---

## 📋 **Bonnes Pratiques**

### **1. Validation des Images**
```python
# Dans serializers.py
from django.core.validators import FileExtensionValidator

class PlaceSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'gif'])]
    )
```

### **2. Redimensionnement**
Utilisez `Pillow` pour redimensionner automatiquement :
```python
# settings.py
IMAGE_RESIZE = {
    'max_width': 1200,
    'max_height': 800,
    'quality': 85
}
```

### **3. Noms de Fichiers Sécurisés**
Django génère automatiquement des noms sécurisés.

---

## 🚀 **Test Rapide**

1. **Démarrez le serveur** : `python manage.py runserver`
2. **Testez l'upload** via Swagger UI : `http://localhost:8000/api/docs/`
3. **Vérifiez le dossier** : `media/places/` contient les images
4. **Accédez via URL** : `http://localhost:8000/media/places/...`

---

## 📚 **Ressources**

- [Django File Upload Documentation](https://docs.djangoproject.com/en/stable/topics/http/file-uploads/)
- [Django Static Files](https://docs.djangoproject.com/en/stable/howto/static-files/)
- [Pillow Documentation](https://pillow.readthedocs.io/)

Le système est **prêt pour le développement** ! 🎉