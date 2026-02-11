# Routes d'Historique - SpotFinder API

## 📋 Historique des Visites

### **Modèle Visit**
- `user` : Utilisateur qui a visité
- `place` : Place visitée
- `visited_at` : Date/heure de la visite (auto)
- `duration_minutes` : Durée en minutes (optionnel)
- `personal_note` : Note personnelle (optionnel)

### **Endpoints Disponibles**

| Route | Méthode | Description |
|-------|---------|-------------|
| `/api/visits/` | GET | Liste des visites de l'utilisateur connecté |
| `/api/visits/` | POST | Enregistrer une nouvelle visite |
| `/api/visits/<id>/` | GET | Détails d'une visite |
| `/api/visits/<id>/` | PUT/PATCH | Modifier une visite |
| `/api/visits/<id>/` | DELETE | Supprimer une visite |

### **Filtres Disponibles**
- `?place_id=<id>` : Visites d'une place spécifique

### **Exemples d'Utilisation**

#### **Enregistrer une visite**
```json
POST /api/visits/
{
    "place": 1,
    "duration_minutes": 45,
    "personal_note": "Très bon restaurant, reviendrai !"
}
```

#### **Voir son historique**
```json
GET /api/visits/
[
    {
        "id": 1,
        "place": 1,
        "place_name": "Café du Centre",
        "place_address": "123 Rue Principale",
        "place_city": "Paris",
        "visited_at": "2026-02-11T14:30:00Z",
        "duration_minutes": 45,
        "personal_note": "Très bon restaurant, reviendrai !"
    }
]
```

### **Permissions**
- ✅ Lecture : Utilisateur authentifié (ses propres visites uniquement)
- ✅ Écriture : Utilisateur authentifié
- ❌ Accès admin : Via Django Admin

### **Utilisations Possibles**
- Suivre l'historique des visites d'un utilisateur
- Calculer des statistiques de fréquentation
- Recommandations basées sur l'historique
- Notes personnelles sur les lieux visités

---

## 🚀 Prochaines Étapes Possibles

### **Autres Types d'Historique**
1. **Historique des recherches** : Mots-clés recherchés
2. **Historique des réservations** : Réservations effectuées
3. **Historique des modifications** : Changements sur les places

### **Améliorations**
- Géolocalisation des visites
- Photos/visites
- Statistiques avancées
- Export d'historique

---

*Documentation générée automatiquement - Version 0.4.0*</content>
<parameter name="filePath">c:\Users\czinx\django-projects\spotfinder-api\HISTORIQUE_DOCUMENTATION.md