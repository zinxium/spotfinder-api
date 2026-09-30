# Authentification JWT

Ce guide explique comment un client (l'application mobile SpotFinder, un front web, Postman…) s'authentifie auprès de l'API.

## Principe

À la connexion, l'API renvoie **deux tokens** :

| Token | Durée | Rôle | Où l'envoyer |
|---|---|---|---|
| **access** | 15 min | Prouve l'identité à chaque requête | En-tête `Authorization: Bearer <access>` |
| **refresh** | 7 jours | Sert uniquement à obtenir un nouveau token d'accès | Corps de `POST /api/auth/refresh/` et `/logout/` |

Pourquoi deux tokens ? Le token d'accès circule dans toutes les requêtes : s'il est volé, il ne reste valable que quelques minutes. Le refresh token circule rarement, et il est **à usage unique** : chaque rafraîchissement le remplace et révoque l'ancien.

```
 App mobile                                   API
    │  POST /auth/login/ {username, password}  │
    │─────────────────────────────────────────>│
    │  {user, access, refresh}                 │
    │<─────────────────────────────────────────│
    │                                          │
    │  GET /places/  Authorization: Bearer A1  │
    │─────────────────────────────────────────>│  OK 200
    │                                          │
    │  … 15 minutes plus tard …                │
    │  GET /favorites/  Bearer A1              │
    │─────────────────────────────────────────>│  échec 401 (token expiré)
    │                                          │
    │  POST /auth/refresh/ {refresh: R1}       │
    │─────────────────────────────────────────>│  R1 révoqué
    │  {access: A2, refresh: R2}               │
    │<─────────────────────────────────────────│
    │                                          │
    │  GET /favorites/  Bearer A2  (on rejoue) │
    │─────────────────────────────────────────>│  OK 200
```

## Endpoints

### Inscription

```http
POST /api/auth/register/
Content-Type: application/json

{"username": "alice", "email": "alice@example.com", "password": "Un-Mot-De-Passe-Solide"}
```

- `201` → `{"user": {"id", "username", "email", "first_name", "last_name"}, "access", "refresh"}`
- `400` → erreurs **par champ**, en français, par exemple `{"password": ["Ce mot de passe est trop courant."]}`. Les règles de mot de passe sont toujours renvoyées sous `password`.

Règles appliquées :
- email obligatoire ;
- nom d'utilisateur et email uniques, sans tenir compte de la casse ;
- mot de passe d'au moins 8 caractères, pas trop courant, pas uniquement numérique, pas trop proche du nom d'utilisateur.

### Connexion

```http
POST /api/auth/login/
{"username": "alice", "password": "..."}
```

- `200` → même format que l'inscription
- `400` → `{"non_field_errors": ["Identifiants invalides."]}`. Le message est le même que le compte existe ou non, pour ne pas révéler quels comptes existent.

### Rafraîchissement

```http
POST /api/auth/refresh/
{"refresh": "<refresh token>"}
```

- `200` → `{"access": "...", "refresh": "..."}`. **Il faut remplacer les deux tokens stockés.**
- `401` → refresh token expiré, révoqué ou déjà utilisé. L'utilisateur doit se reconnecter.

### Déconnexion

```http
POST /api/auth/logout/
Authorization: Bearer <access>
{"refresh": "<refresh token>"}
```

- `205` → refresh token révoqué
- `400` → token invalide, ou appartenant à un autre utilisateur

Le token d'accès reste techniquement valable jusqu'à son expiration (15 min au maximum). Le client doit donc le supprimer de son stockage.

## Limitation de débit

`register`, `login` et `refresh` sont limités à **10 requêtes par minute et par adresse IP** (variable `THROTTLE_AUTH`). Au-delà, l'API répond `429 Too Many Requests` avec un en-tête `Retry-After`.

## Intégration dans l'application mobile (React Native / Expo)

1. **Stockage** : ranger les tokens dans `expo-secure-store` (Keychain sur iOS, Keystore sur Android). **Jamais** dans `AsyncStorage`, ni dans les logs.
2. **Requêtes** : un intercepteur ajoute `Authorization: Bearer <access>` à chaque appel.
3. **Expiration** : sur une réponse `401`, appeler `/auth/refresh/` **une seule fois**, même si plusieurs requêtes échouent en même temps (les autres attendent le résultat), puis rejouer la requête.
4. **Échec du refresh** (`401`) : effacer les tokens et renvoyer vers l'écran de connexion.
5. **Déconnexion** : appeler `/auth/logout/`, puis effacer les tokens localement, même si l'appel échoue.

## Configuration serveur

| Variable | Défaut | Effet |
|---|---|---|
| `JWT_ACCESS_MINUTES` | `15` | Durée du token d'accès |
| `JWT_REFRESH_DAYS` | `7` | Durée du refresh token |
| `JWT_SIGNING_KEY` | `SECRET_KEY` | Clé de signature. La changer **déconnecte tout le monde**. |
| `THROTTLE_AUTH` | `10/minute` | Limite des routes d'authentification |

Les refresh tokens révoqués sont stockés en base (application `token_blacklist`). Pour purger périodiquement ceux qui ont expiré :

```bash
python manage.py flushexpiredtokens
```
