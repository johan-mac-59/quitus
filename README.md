<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/quitus-logo-dark.svg">
    <img src="assets/quitus-logo-light.svg" alt="Quitus — le fichier propre, et la preuve." width="360">
  </picture>
</p>

# Quitus

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.14+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.14+">
  <img src="https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" alt="Streamlit">
  <img src="https://img.shields.io/badge/pandas-150458?style=for-the-badge&logo=pandas&logoColor=white" alt="pandas">
  <img src="https://img.shields.io/badge/NumPy-013243?style=for-the-badge&logo=numpy&logoColor=white" alt="NumPy">
  <img src="https://img.shields.io/badge/Matplotlib-11557C?style=for-the-badge" alt="Matplotlib">
  <img src="https://img.shields.io/badge/seaborn-4C72B0?style=for-the-badge" alt="seaborn">
  <img src="https://img.shields.io/badge/openpyxl-217346?style=for-the-badge" alt="openpyxl">
  <img src="https://img.shields.io/badge/pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white" alt="pytest">
  <img src="https://img.shields.io/badge/uv-DE5FE9?style=for-the-badge&logo=uv&logoColor=white" alt="uv">
</p>

**Outil de profilage et de nettoyage de fichiers CSV, Excel et JSON**, utilisable en ligne de commande ou par une interface web. Il inspecte un fichier dont vous ne connaissez ni la structure, ni l'encodage, ni le séparateur, vous montre ses défauts, puis les corrige sous votre contrôle et vous rend un rapport d'audit.

**Version 1.0.0** · 🌐 **Essayer en ligne : [quitus.streamlit.app](https://quitus.streamlit.app/)**

---

## 🚀 Démarrage rapide

### En ligne, sans rien installer

👉 **[https://quitus.streamlit.app](https://quitus.streamlit.app/)** — déposez un fichier, ou cliquez sur « Essayer avec un exemple ».

### En local

```bash
git clone https://github.com/johan-mac-59/quitus.git
cd quitus
```

**Avec uv** (recommandé, le verrou de dépendances est versionné) :

```bash
uv sync
uv run streamlit run streamlit_app.py   # interface web
uv run python main.py            # ligne de commande
```

**Avec pip** :

```bash
python -m venv .venv
.venv\Scripts\activate           # Windows
source .venv/bin/activate        # macOS / Linux
pip install -r requirements.txt

streamlit run streamlit_app.py   # interface web -> http://localhost:8501
python main.py                   # ligne de commande
```

Un échantillon de démonstration est versionné dans `data/samples/` : les deux modes fonctionnent immédiatement après le clone, sans placer un seul fichier.

**Prérequis** : Python ≥ 3.14.

---

## 🖥️ Les deux modes d'utilisation

Le projet a **une seule logique métier** (`src/`) et **deux façades**. Un
correctif profite donc aux deux, par construction.

### Interface web

```bash
streamlit run streamlit_app.py
```

Déposez un fichier — ou essayez directement avec l'exemple fourni —, lancez
l'analyse, choisissez les deux traitements optionnels, nettoyez. Sept onglets :

| Onglet | Contenu |
|---|---|
| **Présentation** | Le projet, ses principes et son histoire — toujours consultable |
| **Aperçu** | Le fichier brut, ses indicateurs et les types détectés |
| **Avant nettoyage** | Le diagnostic, défauts compris — c'est le constat de départ |
| **Nettoyage** | Le bilan, le détail des conversions de types, le fichier nettoyé et son rapport |
| **Après nettoyage** | Le profil de contrôle, qui vérifie qu'aucune colonne ne reste mal typée |
| **Graphiques** | Distributions, répartitions et analyses multivariées, à la demande |
| **Téléchargements** | Le récapitulatif : tous les fichiers produits, réunis au même endroit |

Chaque rapport se consulte et se récupère **là où il s'affiche**, et l'onglet
Téléchargements les réunit tous. Les rapports HTML s'affichent dans la page ou
en grand dans une fenêtre modale, et se téléchargent ; les rapports Markdown se
téléchargent. Rien n'est calculé tant qu'on ne le demande pas.

> **Pourquoi pas un nouvel onglet du navigateur pour les rapports HTML ?** Les
> navigateurs bloquent l'ouverture d'un HTML encodé dans l'URL, et le service de
> fichiers statiques de Streamlit imposerait d'écrire le rapport sur le serveur,
> dans un dossier public. La fenêtre modale est l'équivalent sûr. Pour un vrai
> onglet, téléchargez le rapport et ouvrez-le : il est autonome.

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
| `--output`, `-o` | Fichier CSV de sortie. Par défaut : `data/processed/<source>_nettoye_<AAAAMMJJ_HHMMSS>.csv` |
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
3. **Décisions** — l'utilisateur choisit d'écrêter les valeurs aberrantes et de combler les valeurs manquantes. Ces deux traitements modifient les distributions : ils ne sont jamais appliqués sans accord explicite.
4. **Nettoyage** — corrections automatiques, puis traitements choisis.
5. **Validation** — second profilage, sur les données nettoyées.
6. **Livraison** — CSV propre et rapports.

---

## 🏗️ Architecture

```
quitus/
├── streamlit_app.py            # Façade web (Streamlit)
├── main.py                     # Façade ligne de commande
├── src/                        # Logique métier, agnostique de l'interface
│   ├── file_loader.py          # Lecture : format, encodage, séparateur
│   ├── data_profiler.py        # Profilage avant et après nettoyage
│   ├── cleaner_engine.py       # Nettoyage
│   ├── plot_factory.py         # Graphiques réutilisables
│   ├── cleaner_logger.py       # Traçabilité console
│   ├── cleaner_reporter.py     # Rapport de nettoyage
│   ├── console_capture.py      # Sortie console vers l'interface web
│   ├── horodatage.py           # Suffixe commun des fichiers d'une exécution
│   └── marque.py               # Nom, devise et logo pour l'application et les rapports
├── tests/                      # 381 tests, un fichier par module et par garantie
├── assets/                     # Logos clair et sombre, icône
├── data/
│   ├── samples/                # Échantillon de démonstration (versionné)
│   ├── raw/                    # Données sources (ignoré par git)
│   ├── processed/              # Sorties (ignoré par git)
│   └── reports/                # Rapports (ignoré par git)
├── .streamlit/config.toml      # Configuration web — à versionner, voir Confidentialité
├── pyproject.toml              # Dépendances (uv)
├── uv.lock                     # Verrou des versions exactes (uv)
├── requirements.txt            # Dépendances (pip)
├── .python-version             # Version de Python attendue
├── README.md
├── AMELIORATIONS.md            # Améliorations à faire, par importance, et livrées
└── DEROULEMENT_PROJET.md       # Journal technique du projet, étape par étape
```

### Le principe : `src/` ne connaît aucune interface

Aucun module de `src/` ne pose de question et aucun n'importe `streamlit`. Les décisions arrivent sous forme de **paramètres explicites** :

```python
# Le même code, deux façades
run_profiling_workflow(source, reports_dir, report_format="html")  # web : transmis
run_profiling_workflow(source, reports_dir)                        # terminal : demandé
```

Cette frontière n'est pas qu'une convention : `tests/test_integrite_source.py` la vérifie automatiquement, et échoue si un module de `src/` importe `streamlit` ou si un appel à `input()` n'est pas protégé contre l'absence de terminal.

---

## 🔒 Confidentialité

### Que devient un fichier déposé dans l'interface web

| Étape | Où vivent les données | Persistance |
|---|---|---|
| Dépôt | mémoire du serveur (en local : votre machine) | la session |
| Analyse et nettoyage | mémoire du serveur | la session |
| Cache de calcul | mémoire du serveur, partagé entre sessions | **1 heure au plus, 8 entrées** |
| Téléchargements | votre navigateur | vous décidez |

**Rien n'est jamais écrit sur le serveur.** Tous les livrables sont produits en
mémoire et transmis au navigateur. Pour enregistrer des fichiers sur votre propre
machine, la ligne de commande (`main.py`) est l'outil adapté : elle écrit dans
`data/processed/` et `data/reports/`.

**Les rapports HTML sont sûrs à ouvrir**, y compris dans l'aperçu intégré : toute
donnée issue du fichier (noms de colonnes, valeurs, modalités) est échappée, et
une politique de sécurité interdit l'exécution de scripts dans le rapport.

Le bouton **« Effacer mes données »** vide immédiatement la session et retire du cache partagé les calculs faits sur le fichier du visiteur — et seulement ceux-là : les calculs des autres visiteurs restent en place. Remplacer le fichier ou relancer le nettoyage retire de même les calculs devenus inutiles. Le fichier déposé lui-même n'est jamais mis en cache.

### Cookies

**Aucun traceur.** `.streamlit/config.toml` contient `gatherUsageStats = false`, ce qui désactive la télémétrie de Streamlit — le seul cookie non essentiel que l'application aurait posé. Il ne subsiste qu'un cookie technique de protection CSRF, strictement nécessaire au fonctionnement et donc exempt de consentement.

**Ce fichier doit rester versionné** : c'est une mesure de conformité, pas une préférence locale.

### Si vous déployez l'application publiquement

Vous devenez responsable du traitement des fichiers que vos visiteurs déposent. Les mesures de minimisation sont déjà en place — aucune rétention, aucune journalisation des contenus, cache borné. L'application invite par ailleurs explicitement à ne pas déposer de données sensibles.

L'échantillon versionné dans `data/samples/` est **entièrement synthétique** et ne contient aucune donnée personnelle.

---

## 🧪 Tests

```bash
python -m pytest              # 381 tests
python -m pytest -q tests/test_app_streamlit.py    # interface web (sans navigateur)
```

La suite couvre les modules métier, mais aussi trois familles moins habituelles :

* **`test_app_streamlit.py`** — tests d'intégration qui pilotent réellement l'application via le harnais `AppTest` de Streamlit, sans navigateur, de la page d'accueil au contrôle après nettoyage. Ils vérifient des effets mesurables (les doublons disparaissent, la casse est uniformisée, l'écrêtage demandé n'est pas ignoré) et les deux garanties de confidentialité annoncées.
* **`test_aucune_perte_silencieuse.py`** — sur un jeu réunissant toutes les sources de perte connues, les valeurs **réellement** vidées par le nettoyage et celles **déclarées** à l'utilisateur doivent coïncider exactement.
* **`test_securite_rapport_html.py`** — un fichier piégé (balises, gestionnaires d'événements, guillemets dans les noms de colonnes) ne doit produire, une fois le rapport analysé comme le ferait un navigateur, aucune balise `script` ni aucun attribut `on…`. Rejoués contre l'ancien code, ces tests échouent : ils détectent réellement la faille qu'ils préviennent.
* **`test_invariant_post_nettoyage.py`** — après nettoyage, plus aucune colonne textuelle ne doit être convertible en nombre ou en date.
* **`test_plot_factory.py`** — vérifie qu'après la construction de 90 figures, le registre global de matplotlib est **vide**. Sans quoi un serveur de longue durée fuirait à chaque interaction.
* **`test_integrite_source.py`** — contrôles structurels : aucune fonction définie deux fois, aucun import de `streamlit` dans `src/`, aucun `input()` sans garde, aucune fonction publique sans docstring.

---

## 🔧 Choix techniques notables

* **Types entiers nullables (`Int64`)** — préserve l'intégrité des colonnes numériques contenant des valeurs manquantes. L'écrêtage IQR resserre ses bornes vers l'intérieur sur ces colonnes, pandas refusant d'insérer une valeur fractionnaire dans un tableau d'entiers.
* **Détection de dates cumulative** — dix formats sont essayés nommément, et
  appliqués **l'un après l'autre** sur ce que les précédents n'ont pas su lire.
  C'est indispensable sur un export réel, où une même colonne mêle couramment
  `13/09/2024`, `2023-09-15` et `18-07-2023` : aucun format ne dépasse 70 % à lui
  seul, alors que leur cumul couvre la colonne entière. Un garde-fou écarte les
  années implausibles, ce qui évite qu'une note `5/5` ne soit prise pour une date.
* **Intelligence numérique** — `"1 200,50 €"` devient `1200.50`, `"17/20"` devient
  `17` et `"78.9875%"` devient `78.9875`, en distinguant le séparateur décimal du
  séparateur de milliers. Pour une note fractionnaire, c'est le **numérateur** qui
  est retenu : c'est le seul choix cohérent quand une colonne mêle `5` et `5/5`.
* **Seuils mesurés sur les valeurs présentes** — une colonne comportant 40 % de
  valeurs manquantes est convertie si les valeurs présentes, elles, sont
  lisibles. Mesurer le taux sur la hauteur de la colonne rendait toute conversion
  impossible au-delà de 10 % de trous.
* **Graphiques hors de pyplot** — les figures sont créées via l'API d'embarquement de matplotlib (`Figure` + `FigureCanvasAgg`) et non `plt.figure()`, ce qui les soustrait au registre global et rend toute fuite mémoire structurellement impossible.
* **Nettoyage itératif** — certaines corrections en débloquent d'autres (corriger un type révèle des valeurs aberrantes). Le moteur repasse jusqu'à stabilisation, cinq fois au plus.

---

## ⚠️ Comportement en cas d'erreur

| Situation | Réaction |
|---|---|
| Fichier introuvable | `FileNotFoundError`, avec le chemin résolu et l'option à utiliser |
| Extension inconnue | Tentative de détection du format, puis `ValueError` explicite |
| Fichier vide | DataFrame vide retourné sans erreur ; le profilage, lui, signale l'impossibilité |
| Ligne JSON corrompue | Signalée et ignorée : un enregistrement invalide ne fait pas perdre le fichier |
| Absence de terminal | Les invites retiennent leur valeur par défaut documentée, sans lever ni bloquer |

Ce dernier point rend le pipeline utilisable avec une sortie redirigée, dans une chaîne d'intégration continue, ou depuis un serveur web.

---

## 📈 Évolutions prévues

Voir [`AMELIORATIONS.md`](AMELIORATIONS.md), qui classe les améliorations à faire par ordre d'importance et recense celles déjà livrées. Les priorités :
préserver les numéros de téléphone (le `0` initial est aujourd'hui perdu), rendre le rapport HTML lisible en mode sombre, et choisir le traitement colonne par colonne dans l'interface web.

Le journal technique détaillé du projet, étape par étape, se trouve dans [`DEROULEMENT_PROJET.md`](DEROULEMENT_PROJET.md).

---

## 🛠️ Technologies

Python · pandas · NumPy · Matplotlib · Seaborn · Streamlit · pytest
Programmation orientée objet, architecture modulaire, tests unitaires et d'intégration.
