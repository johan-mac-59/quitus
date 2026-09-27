# 🧹 Nettoyage automatique de données

**Outil de profilage et de nettoyage de fichiers CSV, Excel et JSON**, utilisable
en ligne de commande ou par une interface web. Il inspecte un fichier dont vous
ne connaissez ni la structure, ni l'encodage, ni le séparateur, vous montre ses
défauts, puis les corrige sous votre contrôle — et vous rend un rapport d'audit.

**Version 1.0.0**

---

## 🚀 Démarrage rapide

```bash
git clone https://github.com/johan-mac-59/PROJET_NETTOYAGE_AUTO.git
cd PROJET_NETTOYAGE_AUTO
```

**Avec uv** (recommandé, le verrou de dépendances est versionné) :

```bash
uv sync
uv run streamlit run app.py      # interface web
uv run python main.py            # ligne de commande
```

**Avec pip** :

```bash
python -m venv .venv
.venv\Scripts\activate           # Windows
source .venv/bin/activate        # macOS / Linux
pip install -r requirements.txt

streamlit run app.py             # interface web -> http://localhost:8501
python main.py                   # ligne de commande
```

Un échantillon de démonstration est versionné dans `data/samples/` : les deux
modes fonctionnent immédiatement après le clone, sans placer un seul fichier.

**Prérequis** : Python ≥ 3.14.

---

## 🖥️ Les deux modes d'utilisation

Le projet a **une seule logique métier** (`src/`) et **deux façades**. Un
correctif profite donc aux deux, par construction.

### Interface web

```bash
streamlit run app.py
```

Déposez un fichier, lancez l'analyse, réglez les options, nettoyez, téléchargez.
Cinq onglets : **Aperçu**, **Profilage**, **Nettoyage**, **Graphiques**,
**Téléchargements**. Les graphiques sont interactifs et construits à la demande ;
les rapports sont produits en mémoire et proposés au téléchargement.

### Ligne de commande

```bash
python main.py                                   # chemins et questions par défaut
python main.py --input mon_fichier.csv
python main.py -i brut.csv -o propre.csv -r rapports/
python main.py --input brut.csv --oui-a-tout     # aucune question, tout accepté
python main.py --input brut.csv --non-interactif # aucune question, traitements lourds refusés
python main.py --input brut.csv --format-rapport html
```

| Option | Rôle |
|---|---|
| `--input`, `-i` | Fichier à nettoyer |
| `--output`, `-o` | Fichier CSV de sortie |
| `--reports`, `-r` | Répertoire des rapports |
| `--format-rapport` | `md` ou `html` ; sans cette option, la question est posée |
| `--oui-a-tout` | Accepte écrêtage, remplissage et rapports sans rien demander |
| `--non-interactif` | Ne demande rien et refuse les traitements lourds |

Les deux derniers modes rendent le pipeline utilisable dans un script ou une
chaîne d'intégration continue. Le code de sortie vaut 0 en cas de succès, 1 sinon.

---

## ⚙️ Ce que fait le pipeline

| Module | Rôle |
|---|---|
| **`file_loader`** | **Lecture intelligente.** Détecte le format (CSV, Excel, JSON, JSON Lines), l'encodage (UTF-8, Latin1, CP1252) et le séparateur (`,` `;` `\t` `\|`). Accepte un chemin ou des octets en mémoire, ce qui permet à l'interface web de consommer un fichier déposé sans fichier temporaire. |
| **`data_profiler`** | **Double audit.** `PreCleaningProfiler` diagnostique les anomalies avant nettoyage ; `ExploratoryProfiler` valide le résultat après, en ajoutant matrice de dispersion et corrélations. Produit des rapports Markdown et HTML autonomes. |
| **`cleaner_engine`** | **Moteur de transformation.** Doublons, espaces superflus, casse incohérente, types mal détectés, formats monétaires (`"1 200,50 €"` → `1200.50`), entiers nullables `Int64`, valeurs manquantes, valeurs aberrantes (IQR). Nettoyage itératif, qui s'arrête dès que plus rien ne change. |
| **`plot_factory`** | **Fabrique de graphiques.** Cinq graphiques, exposés comme objets réutilisables : un même code alimente les rapports HTML et l'interface web. |
| **`cleaner_logger`** | **Traçabilité.** Rapport console comparatif avant / après. |
| **`cleaner_reporter`** | **Audit.** Rapport Markdown structuré, avec indicateurs de transformation. |
| **`console_capture`** | **Passerelle.** Détourne la sortie console vers l'interface web, pour que la traçabilité du terminal reste visible dans le navigateur. |

### Ordonnancement

1. **Chargement** — détection du format, de l'encodage et du séparateur.
2. **Audit initial** — inspection des données brutes.
3. **Décisions** — l'utilisateur choisit d'écrêter les valeurs aberrantes et de
   combler les valeurs manquantes. Ces deux traitements modifient les
   distributions : ils ne sont jamais appliqués sans accord explicite.
4. **Nettoyage** — corrections automatiques, puis traitements choisis.
5. **Validation** — second profilage, sur les données nettoyées.
6. **Livraison** — CSV propre et rapports.

---

## 🏗️ Architecture

```
PROJET_NETTOYAGE_AUTO/
├── app.py                      # Façade web (Streamlit)
├── main.py                     # Façade ligne de commande
├── src/                        # Logique métier, agnostique de l'interface
│   ├── file_loader.py
│   ├── data_profiler.py
│   ├── cleaner_engine.py
│   ├── plot_factory.py
│   ├── cleaner_logger.py
│   ├── cleaner_reporter.py
│   └── console_capture.py
├── tests/                      # 264 tests
├── data/
│   ├── samples/                # Échantillon de démonstration (versionné)
│   ├── raw/                    # Données sources (ignoré par git)
│   ├── processed/              # Sorties (ignoré par git)
│   └── reports/                # Rapports (ignoré par git)
├── .streamlit/config.toml      # Configuration web — à versionner, voir Confidentialité
├── pyproject.toml              # Dépendances (uv)
├── requirements.txt            # Dépendances (pip)
└── DEROULEMENT_PROJET.md       # Journal technique du projet
```

### Le principe : `src/` ne connaît aucune interface

Aucun module de `src/` ne pose de question et aucun n'importe `streamlit`. Les
décisions arrivent sous forme de **paramètres explicites** :

```python
# Le même code, deux façades
run_profiling_workflow(source, reports_dir, report_format="html")  # web : transmis
run_profiling_workflow(source, reports_dir)                        # terminal : demandé
```

Cette frontière n'est pas qu'une convention : `tests/test_integrite_source.py` la
vérifie automatiquement, et échoue si un module de `src/` importe `streamlit` ou
si un appel à `input()` n'est pas protégé contre l'absence de terminal.

---

## 🔒 Confidentialité

### Que devient un fichier déposé dans l'interface web

| Étape | Où vivent les données | Persistance |
|---|---|---|
| Dépôt | mémoire du serveur (en local : votre machine) | la session |
| Analyse et nettoyage | mémoire du serveur | la session |
| Cache de calcul | mémoire du serveur, partagé entre sessions | **1 heure au plus, 8 entrées** |
| Téléchargements | votre navigateur | vous décidez |
| Enregistrement local | disque du serveur | **persistant — décoché par défaut** |

**Par défaut, rien n'est écrit sur le serveur.** Tous les livrables sont produits
en mémoire et transmis au navigateur. Une case à cocher, décochée, offre
l'enregistrement dans `data/` pour un usage local.

Le bouton **« Effacer mes données »** vide immédiatement la session et purge le
cache partagé.

### Cookies

**Aucun traceur.** `.streamlit/config.toml` contient `gatherUsageStats = false`,
ce qui désactive la télémétrie de Streamlit — le seul cookie non essentiel que
l'application aurait posé. Il ne subsiste qu'un cookie technique de protection
CSRF, strictement nécessaire au fonctionnement et donc exempt de consentement.

**Ce fichier doit rester versionné** : c'est une mesure de conformité, pas une
préférence locale.

### Si vous déployez l'application publiquement

Vous devenez responsable du traitement des fichiers que vos visiteurs déposent.
Les mesures de minimisation sont déjà en place — aucune rétention, aucune
journalisation des contenus, cache borné. L'application invite par ailleurs
explicitement à ne pas déposer de données sensibles.

L'échantillon versionné dans `data/samples/` est **entièrement synthétique** et
ne contient aucune donnée personnelle.

---

## 🧪 Tests

```bash
python -m pytest              # 264 tests
python -m pytest -q tests/test_app_streamlit.py    # interface web (sans navigateur)
```

La suite couvre les modules métier, mais aussi trois familles moins habituelles :

* **`test_app_streamlit.py`** — 27 tests d'intégration qui pilotent réellement
  l'application via le harnais `AppTest` de Streamlit, sans navigateur. Ils
  vérifient des effets mesurables (les doublons disparaissent, la casse est
  uniformisée, l'écrêtage demandé n'est pas ignoré) et les deux garanties de
  confidentialité annoncées.
* **`test_plot_factory.py`** — vérifie qu'après la construction de 90 figures, le
  registre global de matplotlib est **vide**. Sans quoi un serveur de longue
  durée fuirait à chaque interaction.
* **`test_integrite_source.py`** — contrôles structurels : aucune fonction
  définie deux fois, aucun import de `streamlit` dans `src/`, aucun `input()`
  sans garde, aucune fonction publique sans docstring.

---

## 🔧 Choix techniques notables

* **Types entiers nullables (`Int64`)** — préserve l'intégrité des colonnes
  numériques contenant des valeurs manquantes. L'écrêtage IQR resserre ses bornes
  vers l'intérieur sur ces colonnes, pandas refusant d'insérer une valeur
  fractionnaire dans un tableau d'entiers.
* **Détection de dates explicite** — six formats sont essayés nommément avant de
  recourir à l'inférence de pandas, en retenant celui au meilleur taux de
  réussite. Évite les confusions jour/mois.
* **Intelligence monétaire** — `"1 200,50 €"` devient `1200.50`, en distinguant
  le séparateur décimal du séparateur de milliers.
* **Graphiques hors de pyplot** — les figures sont créées via l'API
  d'embarquement de matplotlib (`Figure` + `FigureCanvasAgg`) et non
  `plt.figure()`, ce qui les soustrait au registre global et rend toute fuite
  mémoire structurellement impossible.
* **Nettoyage itératif** — certaines corrections en débloquent d'autres (corriger
  un type révèle des valeurs aberrantes). Le moteur repasse jusqu'à stabilisation,
  cinq fois au plus.

---

## ⚠️ Comportement en cas d'erreur

| Situation | Réaction |
|---|---|
| Fichier introuvable | `FileNotFoundError`, avec le chemin résolu et l'option à utiliser |
| Extension inconnue | Tentative de détection du format, puis `ValueError` explicite |
| Fichier vide | DataFrame vide retourné sans erreur ; le profilage, lui, signale l'impossibilité |
| Ligne JSON corrompue | Signalée et ignorée : un enregistrement invalide ne fait pas perdre le fichier |
| Absence de terminal | Les invites retiennent leur valeur par défaut documentée, sans lever ni bloquer |

Ce dernier point rend le pipeline utilisable avec une sortie redirigée, dans une
chaîne d'intégration continue, ou depuis un serveur web.

---

## 📈 Évolutions prévues

Voir [`améliorations_futures.md`](améliorations_futures.md). Les principaux axes :
module de validation de contraintes, détection des notes (`17/20`) et des
pourcentages, et sélection du traitement colonne par colonne dans l'interface web.

Le journal technique détaillé du projet, étape par étape, se trouve dans
[`DEROULEMENT_PROJET.md`](DEROULEMENT_PROJET.md).

---

## 🛠️ Technologies

Python · pandas · NumPy · Matplotlib · Seaborn · Streamlit · pytest
Programmation orientée objet, architecture modulaire, tests unitaires et d'intégration.
