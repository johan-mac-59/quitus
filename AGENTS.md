# AGENTS.md

Instructions pour les assistants de code qui travaillent sur ce dépôt. Elles complètent le [README](README.md), à lire en premier pour toute présentation du projet.

## Le projet

**Quitus** est un outil de profilage et de nettoyage de fichiers de données CSV, Excel, JSON (et JSON Lines) et Parquet. Il inspecte un fichier dont on ne connaît ni la structure, ni l'encodage, ni le séparateur, montre ses défauts, les corrige sous le contrôle de l'utilisateur et rend un rapport d'audit qui justifie chaque correction.

Il a **une seule logique métier** (`src/`) et **deux façades** : une interface web Streamlit (`streamlit_app.py`, déployée sur [quitus.streamlit.app](https://quitus.streamlit.app/)) et une ligne de commande (`main.py`).

## Où trouver quoi

| Chemin | Contenu |
|---|---|
| `README.md` | Présentation, utilisation, architecture, confidentialité, tests |
| `src/` | Logique métier : `file_loader`, `data_profiler`, `cleaner_engine`, `plot_factory`, `cleaner_logger`, `cleaner_reporter`, `console_capture`, `horodatage`, `marque` |
| `tests/` | Suite pytest, un fichier par module et par garantie |
| `docs/API.md` | Documentation des fonctions publiques, générée depuis le code |
| `docs/GLOSSAIRE.md` | Aide-mémoire des notions et des termes du projet, pour un lecteur novice |
| `DEROULEMENT_PROJET.md` | Journal technique du projet, étape par étape |
| `AMELIORATIONS.md` | Améliorations à faire, par importance, et améliorations livrées |
| `data/samples/` | Échantillon de démonstration synthétique, versionné |

## Commandes

```bash
uv sync                                  # installer l'environnement (Python 3.14)
uv run python -m pytest                  # lancer toute la suite de tests
uv run streamlit run streamlit_app.py    # interface web
uv run python main.py                    # ligne de commande
uv run python docs/generer_api.py        # régénérer docs/API.md
```

## Début de session

- **Vérifier à chaque nouvelle session qu'aucune version postérieure n'existe en ligne** : le projet se travaille depuis plusieurs postes (PC, Chromebook), et le dépôt local peut être en retard. Avant toute modification, lancer `git pull --ff-only` sur la branche courante. Si l'arbre de travail contient des modifications non commitées, lancer `git fetch` puis comparer (`git status -sb`) plutôt que de tirer. Signaler au mainteneur toute branche distante plus récente ou tout retard constaté, et ne jamais forcer un pull qui écraserait du travail local.

## Règles du code

- **`src/` ne connaît aucune interface** : aucun module de `src/` n'importe `streamlit` ni ne pose de question. Les décisions arrivent en paramètres explicites. `tests/test_integrite_source.py` le vérifie, avec trois autres contrôles : aucune fonction définie deux fois, aucun `input()` sans garde contre l'absence de terminal, aucune fonction publique sans docstring.
- **Documentation API à jour** : après toute modification d'une fonction publique, régénérer `docs/API.md` ; un test échoue sinon.
- **Pas de perte silencieuse** : toute valeur vidée par le nettoyage doit être déclarée à l'utilisateur (`tests/test_aucune_perte_silencieuse.py`).
- **Écrêtage et remplissage des valeurs manquantes** : jamais appliqués sans accord explicite de l'utilisateur, car ils modifient les distributions.
- **Confidentialité** : rien n'est écrit sur le serveur par l'interface web ; `.streamlit/config.toml` reste versionné (télémétrie désactivée).
- **Vocabulaire** : reprendre tels quels les termes du mainteneur (ex. « non réalisable » pour une règle qui ne s'applique pas au fichier) dans les messages, la documentation et le journal.
- Lancer la suite de tests avant de proposer un changement comme terminé.

## Documentation et journal

- **`DEROULEMENT_PROJET.md` est la source unique de l'historique**, sans CHANGELOG. Chaque grande étape y est consignée avant d'être commitée : une entrée `## Étape N : Titre`, puis des sous-sections numérotées, narratives, en français (problème, démarche, erreurs rencontrées, résultat).
- **Pas d'étape pour une retouche mineure** : une retouche cosmétique se consigne en quelques lignes dans l'étape en cours ou la plus proche.
- **Le journal et `AMELIORATIONS.md` ne parlent que du projet** (technique, décisions, livraisons), jamais de sa communication.
- **README** : aucun tiret cadratin (« — »), remplacé selon le contexte par deux-points, virgule ou parenthèses ; chaque paragraphe, citation ou élément de liste tient sur une seule ligne source.

## Versions et commits

- **Ne jamais changer le numéro de version** (`pyproject.toml`, README, journal) ni créer d'étiquette git sans l'accord explicite du mainteneur. Proposer, ne pas appliquer.
- **Messages de commit concis et explicites** : un titre bref qui nomme le changement, un corps seulement s'il apporte une information utile.
- **Aucune attribution** : pas de ligne `Co-Authored-By`, de mention « généré par » ni de signature d'outil, dans les commits comme dans les fichiers.
