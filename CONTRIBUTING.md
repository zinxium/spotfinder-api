# Contribuer à SpotFinder API

Ce document fixe les règles de versionnage du code. Elles s'appliquent **à chaque modification**.

## 1. Branches

| Branche | Rôle |
|---|---|
| `main` | Production : uniquement du code **complet et fonctionnel**, reçu depuis `dev`. Jamais de commit direct. |
| `dev` | Intégration : toutes les branches de travail y sont fusionnées, même en cours d'avancement |
| Branches de travail | Créées depuis `dev`, préfixées selon le tableau ci-dessous |

| Préfixe | Usage | Exemple |
|---|---|---|
| `feat/` | Nouvelle fonctionnalité | `feat/place-photos` |
| `fix/` | Correction de bug | `fix/search-invalid-budget` |
| `security/` | Correctif ou renforcement de sécurité | `security/jwt-auth` |
| `docs/` | Documentation uniquement | `docs/api-endpoints` |
| `chore/` | Maintenance, dépendances, CI | `chore/upgrade-django` |

Flux de travail :

```
feat/ma-fonctionnalite ──PR──▶ dev ──(quand tout fonctionne)──PR──▶ main ──▶ tag vX.Y.Z
```

1. Créer la branche depuis `dev` : `git checkout dev`, `git pull`, `git checkout -b feat/…`
2. Commits, push, puis pull request **vers `dev`**
3. CI verte, puis fusion dans `dev`
4. Quand `dev` est stable et complet : pull request `dev` → `main`, fusion, puis tag de version

La CI (tests Django et revue des dépendances) tourne sur `dev` et sur `main`.

## 2. Messages de commit : Conventional Commits

```
<type>(<portée optionnelle>): <résumé à l'impératif, en minuscules>

<corps optionnel : le pourquoi, pas le comment>

<pied optionnel : BREAKING CHANGE: …, Refs #12>
```

| Type | Quand | Effet sur la version |
|---|---|---|
| `feat` | Nouvelle fonctionnalité | MINEUR |
| `fix` | Correction de bug | CORRECTIF |
| `security` | Correctif de sécurité | CORRECTIF (ou plus) |
| `docs` | Documentation | aucun |
| `test` | Ajout ou modification de tests | aucun |
| `refactor` | Restructuration sans changement de comportement | aucun |
| `ci` / `chore` | CI, dépendances, outillage | aucun |

Un `!` après le type (`feat(auth)!:`) ou un pied `BREAKING CHANGE:` signale un **changement incompatible** pour les clients de l'API.

Chaque commit est **petit et cohérent** : il fait une seule chose, et les tests passent.

## 3. Versions : Semantic Versioning

Format `MAJEUR.MINEUR.CORRECTIF`, défini à un seul endroit : [`spotfinderapi/__init__.py`](spotfinderapi/__init__.py) (`__version__`). Swagger l'affiche automatiquement.

- **MAJEUR** : changement incompatible pour les clients (réponse modifiée, route supprimée…)
- **MINEUR** : ajout rétrocompatible
- **CORRECTIF** : correction rétrocompatible

> Tant que l'application mobile n'est pas publiée, les changements incompatibles restent en MINEUR (1.x). La version 2.0.0 sera réservée au premier changement incompatible après la publication.

### Publier une version

1. Mettre à jour `__version__` dans `spotfinderapi/__init__.py`.
2. Dans [CHANGELOG.md](CHANGELOG.md), renommer la section `[Non publié]` en `[X.Y.Z] - AAAA-MM-JJ`.
3. Régénérer le schéma OpenAPI : `python manage.py spectacular --file schema.yml`.
4. Commit `chore(release): vX.Y.Z` en **dernier commit de la pull request `dev` → `main`**, fusion dans `main`, puis, **seulement une fois la PR fusionnée**, tag :
   ```bash
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```

## 4. CHANGELOG

Format [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Chaque pull request ajoute ses lignes dans la section `[Non publié]`, sous l'une de ces rubriques : **Ajouté**, **Modifié**, **Corrigé**, **Supprimé**, **Sécurité**.

## 5. Checklist avant pull request

- [ ] `python manage.py test places` passe
- [ ] `python manage.py makemigrations --check` ne signale rien (ou les migrations sont incluses)
- [ ] Nouvelle route : permissions explicites et test d'accès
- [ ] Aucun secret dans le code (`.env`, clés, `db.sqlite3`…)
- [ ] README et `docs/` à jour si le comportement change
- [ ] CHANGELOG complété
- [ ] `schema.yml` régénéré si l'API change
