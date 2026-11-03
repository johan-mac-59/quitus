# 📚 Documentation API

> Ce document est généré par [`docs/generer_api.py`](generer_api.py) à partir
> des signatures et des docstrings du code. Ne le modifiez pas à la main :
> modifiez la docstring, puis relancez `python docs/generer_api.py`. Un test,
> `tests/test_documentation_api.py`, échoue dès qu'il n'est plus à jour.

Toute la logique métier vit dans `src/`, qui ne connaît ni la ligne de commande
(`main.py`) ni l'interface web (`streamlit_app.py`) : ces deux façades se
contentent d'appeler les fonctions ci-dessous et de leur transmettre les
décisions de l'utilisateur sous forme de paramètres. Seules les fonctions et
classes publiques sont décrites ; celles dont le nom commence par un tiret bas
sont des détails d'implémentation, susceptibles de changer.

## Sommaire

- [`src/file_loader.py`](#srcfile_loaderpy)
  - [`load_dataframe`](#load_dataframe) — fonction
  - [`load_file`](#load_file) — fonction
- [`src/data_profiler.py`](#srcdata_profilerpy)
  - [`PlotSpec`](#plotspec) — classe
  - [`build_report_path`](#build_report_path) — fonction
  - [`DataProfiler`](#dataprofiler) — classe
  - [`PreCleaningProfiler`](#precleaningprofiler) — classe
  - [`ExploratoryProfiler`](#exploratoryprofiler) — classe
- [`src/cleaner_engine.py`](#srccleaner_enginepy)
  - [`clean_empty_columns`](#clean_empty_columns) — fonction
  - [`clean_whitespace`](#clean_whitespace) — fonction
  - [`fix_numeric_types`](#fix_numeric_types) — fonction
  - [`has_leading_zero`](#has_leading_zero) — fonction
  - [`clean_types`](#clean_types) — fonction
  - [`find_mistyped_columns`](#find_mistyped_columns) — fonction
  - [`clean_duplicates`](#clean_duplicates) — fonction
  - [`prepare_target_columns_for_case_cleaning`](#prepare_target_columns_for_case_cleaning) — fonction
  - [`clean_case_sensitivity`](#clean_case_sensitivity) — fonction
  - [`clean_missing_values`](#clean_missing_values) — fonction
  - [`iqr_bounds`](#iqr_bounds) — fonction
  - [`count_outliers`](#count_outliers) — fonction
  - [`clip_outliers`](#clip_outliers) — fonction
  - [`summarize_outliers`](#summarize_outliers) — fonction
  - [`summarize_missing_values`](#summarize_missing_values) — fonction
  - [`ask_user_outlier_correction`](#ask_user_outlier_correction) — fonction
  - [`ask_user_missing_values_correction`](#ask_user_missing_values_correction) — fonction
  - [`get_user_decisions`](#get_user_decisions) — fonction
  - [`run_all_cleaning_steps`](#run_all_cleaning_steps) — fonction
- [`src/cleaner_logger.py`](#srccleaner_loggerpy)
  - [`CleanLogger`](#cleanlogger) — classe
  - [`generate_and_print_report`](#generate_and_print_report) — fonction
- [`src/cleaner_reporter.py`](#srccleaner_reporterpy)
  - [`CleanerReporter`](#cleanerreporter) — classe
  - [`build_cleaning_report_path`](#build_cleaning_report_path) — fonction
  - [`generate_enhanced_report`](#generate_enhanced_report) — fonction
- [`src/plot_factory.py`](#srcplot_factorypy)
  - [`new_figure`](#new_figure) — fonction
  - [`figure_histogram`](#figure_histogram) — fonction
  - [`figure_boxplot`](#figure_boxplot) — fonction
  - [`is_identifier_column`](#is_identifier_column) — fonction
  - [`split_categorical_columns`](#split_categorical_columns) — fonction
  - [`figure_barplot_top`](#figure_barplot_top) — fonction
  - [`figure_scatter_matrix`](#figure_scatter_matrix) — fonction
  - [`figure_correlation_heatmap`](#figure_correlation_heatmap) — fonction
  - [`figure_to_base64_png`](#figure_to_base64_png) — fonction
  - [`figure_to_img_tag`](#figure_to_img_tag) — fonction
- [`src/validator.py`](#srcvalidatorpy)
  - [`MotifTropCouteux`](#motiftropcouteux) — classe
  - [`nouvelle_regle`](#nouvelle_regle) — fonction
  - [`verifier_regle`](#verifier_regle) — fonction
  - [`echapper_markdown`](#echapper_markdown) — fonction
  - [`decrire_regle`](#decrire_regle) — fonction
  - [`regles_vers_texte`](#regles_vers_texte) — fonction
  - [`sauver_regles`](#sauver_regles) — fonction
  - [`regles_depuis_texte`](#regles_depuis_texte) — fonction
  - [`charger_regles`](#charger_regles) — fonction
  - [`valider`](#valider) — fonction
  - [`resumer_resultat`](#resumer_resultat) — fonction
  - [`formater_bilan`](#formater_bilan) — fonction
- [`src/saisie_regles.py`](#srcsaisie_reglespy)
  - [`types_disponibles`](#types_disponibles) — fonction
  - [`champs_du_type`](#champs_du_type) — fonction
  - [`colonnes_attendues`](#colonnes_attendues) — fonction
  - [`lire_borne`](#lire_borne) — fonction
  - [`construire_regle`](#construire_regle) — fonction
  - [`saisies_depuis_regle`](#saisies_depuis_regle) — fonction
- [`src/horodatage.py`](#srchorodatagepy)
  - [`horodater`](#horodater) — fonction
- [`src/marque.py`](#srcmarquepy)
  - [`logo_data_uri`](#logo_data_uri) — fonction
  - [`logo_adaptatif_svg`](#logo_adaptatif_svg) — fonction
  - [`en_tete_html`](#en_tete_html) — fonction
  - [`en_tete_markdown`](#en_tete_markdown) — fonction
- [`src/console_capture.py`](#srcconsole_capturepy)
  - [`capture_output`](#capture_output) — fonction

## `src/file_loader.py`

Chargement intelligent de fichiers tabulaires, quelle que soit leur origine.

Le module expose deux portes d'entrée équivalentes :

* `load_file(chemin)` — pour la ligne de commande, qui part d'un fichier sur disque ;
* `load_dataframe(octets, nom)` — pour l'interface web, qui reçoit un fichier
déposé dans le navigateur et n'a jamais de chemin à lui offrir.

Toute la logique de détection (format, encodage, séparateur) vit dans le coeur
orienté octets. Les fonctions orientées chemin ne sont que des enveloppes, ce
qui garantit un comportement identique dans les deux modes.

### `load_dataframe`

```python
load_dataframe(source: Union[bytes, bytearray, BinaryIO], filename: str) -> pd.DataFrame
```

Charge un DataFrame depuis des octets en mémoire.

**Paramètres**

- `source` — Contenu du fichier, en octets ou sous forme de flux binaire.
- `filename` — Nom du fichier, dont l'extension détermine le format. Le fichier lui-même n'a pas besoin d'exister sur le disque.

**Retour** — Le DataFrame chargé.

**Exceptions**

- `ValueError` — Si le format ne peut être ni déduit ni détecté.

### `load_file`

```python
load_file(file_path: str) -> pd.DataFrame
```

Charge un fichier du disque dans un DataFrame, selon son extension.

**Paramètres**

- `file_path` — Chemin vers le fichier à charger.

**Retour** — Le DataFrame chargé.

**Exceptions**

- `FileNotFoundError` — Si le fichier n'existe pas.
- `ValueError` — Si l'extension n'est pas supportée et que le format ne peut être détecté.

## `src/data_profiler.py`

### `PlotSpec`

```python
class PlotSpec(key: str, section: str, title: str, build: Callable[[], Figure])
```

Description d'un graphique disponible, sans le construire.

**Attributs**

- `key` — Identifiant stable, utilisable comme clé de widget.
- `section` — Regroupement d'affichage (ex. « Distributions »).
- `title` — Libellé lisible.
- `build` — Closure qui construit et retourne la figure, à la demande.

### `build_report_path`

```python
build_report_path(reports_dir, source_path, fmt: str, horodatage: str = None) -> Path
```

Compose le chemin horodaté d'un rapport de profilage.

**Paramètres**

- `reports_dir` — Répertoire de destination.
- `source_path` — Fichier source, dont le nom de base est réutilisé.
- `fmt` — Extension du rapport (`"md"` ou `"html"`).
- `horodatage` — Suffixe imposé, pour que tous les fichiers d'une même exécution partagent la même marque ; l'instant présent si omis.

**Retour** — Le chemin complet du rapport.

### `DataProfiler`

```python
class DataProfiler(df: pd.DataFrame, source_file_path: str = None)
```

Analyse descriptive d'un DataFrame avec génération de rapport.

#### `DataProfiler.run_analysis`

```python
run_analysis() -> Dict[str, Any]
```

Orchestre toutes les analyses.

**Retour** — Les résultats du profilage, également rangés dans `profile_results` : dimensions, types, valeurs manquantes, doublons, statistiques numériques et catégorielles, valeurs aberrantes.

**Exceptions**

- `ValueError` — Si le DataFrame est vide.

#### `DataProfiler.generate_md_report`

```python
generate_md_report(output_filename: str = 'data/processed/data_profiling_report.md') -> str
```

Sauvegarde le rapport Markdown.

**Paramètres**

- `output_filename` — Chemin du fichier à écrire.

**Retour** — Le chemin du fichier écrit.

#### `DataProfiler.generate_report`

```python
generate_report(output_filename: str = 'data/processed/data_profiling_report.md') -> str
```

Alias historique de `generate_md_report`, conservé pour compatibilité.

Ne pas réutiliser ce nom pour une méthode basée sur `reports_dir` : c'est
la collision de noms qui avait fait dériver l'API.

**Paramètres**

- `output_filename` — Chemin du fichier à écrire.

**Retour** — Le chemin du fichier écrit.

#### `DataProfiler.plot_numeric_distribution`

```python
plot_numeric_distribution(col: str) -> Figure
```

Construit l'histogramme de distribution d'une colonne numérique.

**Paramètres**

- `col` — Nom de la colonne.

**Retour** — La figure, à consommer par `st.pyplot` ou `figure_to_img_tag`.

#### `DataProfiler.plot_numeric_boxplot`

```python
plot_numeric_boxplot(col: str) -> Figure
```

Construit la boîte à moustaches d'une colonne numérique.

**Paramètres**

- `col` — Nom de la colonne.

**Retour** — La figure correspondante.

#### `DataProfiler.plot_categorical_top`

```python
plot_categorical_top(col: str, top_n: int = 10) -> Figure
```

Construit le diagramme des modalités les plus fréquentes.

**Paramètres**

- `col` — Nom de la colonne.
- `top_n` — Nombre de modalités affichées.

**Retour** — La figure correspondante.

#### `DataProfiler.iter_plot_specs`

```python
iter_plot_specs() -> Iterator['PlotSpec']
```

Énumère les graphiques disponibles pour ce DataFrame.

Les figures ne sont pas construites ici : chaque `PlotSpec` porte une
closure `build` que le consommateur appelle s'il a besoin du graphique.
C'est ce qui permet à l'interface web de n'afficher que les colonnes
choisies par l'utilisateur, sans payer le rendu des autres.

**Produit** — Un `PlotSpec` par graphique disponible.

#### `DataProfiler.generate_html_report`

```python
generate_html_report(output_filename: str = 'data/processed/data_profiling_report.html') -> str
```

Sauvegarde le rapport HTML, graphiques compris.

**Paramètres**

- `output_filename` — Chemin du fichier à écrire.

**Retour** — Le chemin du fichier écrit.

#### `DataProfiler.render_report`

```python
render_report(fmt: str = 'md') -> str
```

Produit le rapport en mémoire, sans aucun accès au disque.

C'est ce que consomme l'interface web : elle propose le contenu au
téléchargement sans jamais rien écrire sur le serveur.

**Paramètres**

- `fmt` — Format demandé, `"md"` ou `"html"`.

**Retour** — Le contenu du rapport.

**Exceptions**

- `ValueError` — Si le format demandé n'est pas reconnu.

#### `DataProfiler.write_report`

```python
write_report(output_filename, fmt: str = 'md') -> str
```

Écrit le rapport sur le disque.

**Paramètres**

- `output_filename` — Chemin du fichier à écrire.
- `fmt` — Format demandé, `"md"` ou `"html"`.

**Retour** — Le chemin du fichier écrit.

#### `DataProfiler.interactive_report_choice`

```python
interactive_report_choice(reports_dir, input_file, *, choice: str = None, horodatage: str = None)
```

Choisit le format du rapport de profilage et l'écrit.

**Paramètres**

- `reports_dir` — Répertoire de destination.
- `input_file` — Fichier source, dont le nom sert à composer celui du rapport.
- `choice` — Format imposé — `"1"`/`"md"` ou `"2"`/`"html"`. Si omis, la question est posée en terminal. C'est par ce paramètre que l'interface web transmet le choix fait dans un widget.
- `horodatage` — Suffixe commun aux fichiers de l'exécution en cours.

**Retour** — Le chemin du rapport écrit.

#### `DataProfiler.run_profiling_workflow`

```python
run_profiling_workflow(source_path: Path, reports_dir: Path, *, report_format: str = None, generate_report: bool = True, raise_on_error: bool = False, horodatage: str = None) -> Dict[str, Any]
```

Exécute le profilage complet et, éventuellement, écrit un rapport.

**Paramètres**

- `source_path` — Fichier analysé, dont le nom sert à composer celui du rapport.
- `reports_dir` — Répertoire de destination des rapports.
- `report_format` — Format imposé du rapport ; question posée en terminal si omis.
- `horodatage` — Suffixe commun aux fichiers de l'exécution en cours.
- `generate_report` — À False, seule l'analyse est effectuée — c'est le mode utilisé par l'interface web, qui n'écrit rien sur le serveur.
- `raise_on_error` — À True, les erreurs remontent à l'appelant au lieu d'être avalées. L'interface web l'active pour pouvoir afficher un message d'erreur explicite, là où la ligne de commande préfère continuer le pipeline.

**Retour** — Les résultats d'analyse, ou un dictionnaire vide en cas d'erreur tolérée.

**Exceptions**

- `Exception` — Toute erreur survenue pendant le profilage, si `raise_on_error` est vrai.

### `PreCleaningProfiler`

```python
class PreCleaningProfiler(df: pd.DataFrame, source_file_path: str = None)
```

Profileur d'audit, appliqué aux données brutes avant nettoyage.

Le diagnostic complet (anomalies de casse, outliers, valeurs manquantes)
vient de `DataProfiler`. Cette sous-classe existe pour nommer l'intention
dans le pipeline et pour offrir un point d'extension : c'est ici que se
brancheront les seuils de criticité spécifiques au pré-nettoyage.

### `ExploratoryProfiler`

```python
class ExploratoryProfiler(df: pd.DataFrame, source_file_path: str = None)
```

Profileur de validation, appliqué aux données après nettoyage.

Enrichit le rapport de deux visualisations multivariées — matrice de
dispersion et heatmap de corrélation — qui n'ont de sens que sur un
dataset assaini : elles servent à repérer les redondances entre colonnes
et les dépendances entre indicateurs.

#### `ExploratoryProfiler.plot_scatter_matrix`

```python
plot_scatter_matrix() -> Figure
```

Construit la matrice de dispersion des colonnes numériques.

**Retour** — La figure correspondante.

**Exceptions**

- `ValueError` — S'il y a moins de deux colonnes numériques exploitables.

#### `ExploratoryProfiler.plot_correlation_heatmap`

```python
plot_correlation_heatmap() -> Figure
```

Construit la carte thermique des corrélations.

**Retour** — La figure correspondante.

**Exceptions**

- `ValueError` — S'il y a moins de deux colonnes numériques exploitables.

#### `ExploratoryProfiler.iter_plot_specs`

```python
iter_plot_specs() -> Iterator[PlotSpec]
```

Énumère les graphiques, visualisations multivariées incluses.

**Produit** — Un `PlotSpec` par graphique disponible.

## `src/cleaner_engine.py`

### `clean_empty_columns`

```python
clean_empty_columns(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]
```

Supprime les colonnes dont au moins 95 % des valeurs sont manquantes.

**Paramètres**

- `df` — DataFrame à nettoyer.

**Retour** — Le DataFrame sans ces colonnes et le nombre de colonnes supprimées.

### `clean_whitespace`

```python
clean_whitespace(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]
```

Retire les espaces de bordure et réduit les espaces multiples à un seul.

Seules les colonnes textuelles sont traitées, et les valeurs manquantes le
restent.

**Paramètres**

- `df` — DataFrame à nettoyer.

**Retour** — Le DataFrame nettoyé et le nombre de valeurs modifiées.

### `fix_numeric_types`

```python
fix_numeric_types(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]
```

Repasse en entiers les colonnes que pandas a chargées en flottants à tort.

Une colonne d'entiers comportant une valeur manquante est lue en `float64`
(« 1.0 » au lieu de 1). Si toutes ses valeurs présentes sont entières, elle
passe en entier nullable `Int64`, qui accepte les valeurs manquantes.

**Paramètres**

- `df` — DataFrame à corriger.

**Retour** — Le DataFrame corrigé et, par colonne convertie, la description de la conversion.

### `has_leading_zero`

```python
has_leading_zero(series: pd.Series) -> bool
```

Indique si une colonne contient un code écrit avec un zéro initial.

Un numéro de téléphone, un code postal ou un matricule ressemble à un nombre,
mais n'en est pas un : le convertir en entier supprimerait son zéro initial,
une perte que rien ne signalerait. Une seule valeur de ce genre suffit à
garder toute la colonne en texte, car un code ne se mêle pas à des nombres.

La colonne est examinée en entier, et non sur un échantillon : un code situé
au-delà des premières lignes doit protéger la colonne autant qu'un autre.

**Paramètres**

- `series` — Colonne à examiner, quel que soit son type.

**Retour** — True si au moins une valeur présente est faite de chiffres et commence par un zéro suivi d'un chiffre.

### `clean_types`

```python
clean_types(df: pd.DataFrame, pertes: dict = None, echelles: dict = None) -> Tuple[pd.DataFrame, dict]
```

Convertit automatiquement les colonnes textuelles en nombres ou en dates.

Une conversion est retenue dès que la grande majorité des valeurs présentes
est lisible. Les rares valeurs illisibles deviennent alors des valeurs
manquantes — c'est inévitable, une colonne numérique ne pouvant contenir de
texte. Mais ce ne doit jamais être silencieux : chacune est recensée dans
`pertes`, pour que l'utilisateur voie exactement ce qui a été vidé.

**Paramètres**

- `df` — DataFrame à typer.
- `pertes` — Dictionnaire à compléter, facultatif. Pour chaque colonne où des valeurs présentes n'ont pu être converties, reçoit `{colonne: {'count': n, 'examples': [valeurs d'origine]}}`.
- `echelles` — Dictionnaire à compléter, facultatif. Pour chaque colonne de notes dont certaines ont été ramenées à l'échelle commune, reçoit `{colonne: {'scale': échelle, 'count': n, 'examples': [...]}}`.

**Retour** — Le DataFrame typé et le dictionnaire des conversions effectuées, `{colonne: ['object -> float']}`.

### `find_mistyped_columns`

```python
find_mistyped_columns(df: pd.DataFrame) -> dict
```

Recense les colonnes restées en texte alors qu'elles sont convertibles.

C'est la mesure de l'invariant du double profilage : après nettoyage, plus
aucune colonne textuelle ne devrait être interprétable comme nombre ou comme
date. Partagée entre la suite de tests et l'interface web, pour qu'elles
contrôlent exactement la même chose.

**Paramètres**

- `df` — DataFrame, en principe nettoyé, à contrôler.

**Retour** — Un dictionnaire nom de colonne -> raison du signalement ; vide si toutes les colonnes sont correctement typées.

### `clean_duplicates`

```python
clean_duplicates(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]
```

Supprime les lignes en double exact, en gardant la première occurrence.

**Paramètres**

- `df` — DataFrame à nettoyer.

**Retour** — Le DataFrame dédoublonné et le nombre de lignes supprimées.

### `prepare_target_columns_for_case_cleaning`

```python
prepare_target_columns_for_case_cleaning(profiler_results: dict) -> list
```

Détermine les colonnes cibles pour le nettoyage de la casse basé sur les résultats du profiler.

**Paramètres**

- `profiler_results` *(dict)* — Résultats du DataProfiler

**Retour** — list: Liste des noms de colonnes à traiter

### `clean_case_sensitivity`

```python
clean_case_sensitivity(df: pd.DataFrame, target_columns: list = None) -> Tuple[pd.DataFrame, dict]
```

Unifie la casse des colonnes catégorielles en minuscules.

**Paramètres**

- `df` — DataFrame à nettoyer
- `target_columns` — Liste optionnelle de colonnes spécifiques à traiter. Si None, analyse toutes les colonnes string (comportement par défaut).

**Retour** — Le DataFrame nettoyé et, par colonne traitée, le nombre de valeurs dont la casse a changé.

### `clean_missing_values`

```python
clean_missing_values(df: pd.DataFrame, columns: list = None) -> Tuple[pd.DataFrame, dict]
```

Comble les valeurs manquantes : médiane si numérique, mode sinon.

**Paramètres**

- `df` — DataFrame à traiter.
- `columns` — Colonnes à combler ; None pour toutes. Une colonne absente du DataFrame est ignorée.

**Retour** — Le DataFrame comblé et, par colonne traitée, le nombre de valeurs comblées et la méthode employée.

### `iqr_bounds`

```python
iqr_bounds(series: pd.Series, threshold: float = 1.5)
```

Calcule les bornes IQR d'une série numérique.

**Paramètres**

- `series` — Valeurs numériques ; les valeurs manquantes sont ignorées.
- `threshold` — Nombre d'écarts interquartiles tolérés au-delà des quartiles. Plus il est grand, plus l'écrêtage est tolérant.

**Retour** — Le couple (borne basse, borne haute), ou None si les valeurs sont trop peu nombreuses ou toutes identiques pour qu'une borne ait un sens.

### `count_outliers`

```python
count_outliers(series: pd.Series, threshold: float = 1.5) -> int
```

Compte les valeurs hors des bornes IQR, pour un seuil donné.

Sert à l'interface web, qui affiche l'effet d'un seuil avant le nettoyage.
Une colonne encore textuelle mais convertible (« 1 200,50 € ») est estimée
après une conversion simplifiée : c'est `clip_outliers` qui tranchera, sur
des types définitivement corrigés.

**Paramètres**

- `series` — Colonne brute, numérique ou textuelle.
- `threshold` — Seuil IQR.

**Retour** — Le nombre de valeurs hors bornes ; 0 si la colonne n'est pas numérique.

### `clip_outliers`

```python
clip_outliers(df: pd.DataFrame, columns: list = None, thresholds: dict = None) -> Tuple[pd.DataFrame, dict]
```

Écrête les valeurs aberrantes des colonnes numériques (méthode IQR).

**Paramètres**

- `df` — DataFrame à traiter.
- `columns` — Colonnes à écrêter ; None pour toutes les colonnes numériques. Une colonne absente ou non numérique est ignorée.
- `thresholds` — Seuil IQR par colonne ; une colonne absente du dictionnaire prend `SEUIL_IQR`. Un seuil plus grand tolère une dispersion plus forte (des montants), un seuil plus petit resserre les bornes (des mesures stables).

**Retour** — Le DataFrame écrêté et le nombre de valeurs ramenées dans les bornes, par colonne.

### `summarize_outliers`

```python
summarize_outliers(df: pd.DataFrame, stats: dict = None, profiler_results: dict = None) -> dict
```

Résume les valeurs aberrantes détectées, sans aucune entrée/sortie.

Fonction pure : l'interface en ligne de commande s'en sert pour composer son
affichage, l'interface web pour remplir le texte d'aide de ses widgets.

**Paramètres**

- `df` — DataFrame analysé.
- `stats` — Statistiques de nettoyage déjà collectées, éventuellement porteuses d'une clé `outliers_corrected`.
- `profiler_results` — Résultats complets du profileur, porteurs d'une clé `outliers`.

**Retour** — Un dictionnaire à trois clés : `has_outliers` (bool), `columns` (nom de colonne -> nombre d'outliers) et `lines` (lignes de texte prêtes à afficher).

### `summarize_missing_values`

```python
summarize_missing_values(df: pd.DataFrame) -> dict
```

Résume les valeurs manquantes du DataFrame, sans aucune entrée/sortie.

**Paramètres**

- `df` — DataFrame analysé.

**Retour** — Un dictionnaire à trois clés : `total` (nombre total de valeurs manquantes), `by_column` (nom de colonne -> (nombre, pourcentage)) et `lines` (lignes de texte prêtes à afficher).

### `ask_user_outlier_correction`

```python
ask_user_outlier_correction(df: pd.DataFrame, stats: dict, profiler_results: dict = None, *, answer: bool = None, default: bool = False) -> bool
```

Décide s'il faut écrêter les valeurs aberrantes.

**Paramètres**

- `df` — DataFrame à nettoyer.
- `stats` — Statistiques de nettoyage actuelles.
- `profiler_results` — Résultats complets du profileur.
- `answer` — Réponse imposée ; court-circuite l'invite si elle est fournie. C'est par ce paramètre que l'interface web transmet le choix fait dans un widget.
- `default` — Valeur retenue sur réponse vide ou absence de terminal.

**Retour** — True s'il faut écrêter, False sinon.

### `ask_user_missing_values_correction`

```python
ask_user_missing_values_correction(df: pd.DataFrame, stats: dict, profiler_results: dict = None, *, answer: bool = None, default: bool = False) -> bool
```

Décide s'il faut combler les valeurs manquantes.

**Paramètres**

- `df` — DataFrame à nettoyer.
- `stats` — Statistiques de nettoyage actuelles.
- `profiler_results` — Résultats complets du profileur (non utilisé, conservé pour la symétrie de signature avec `ask_user_outlier_correction`).
- `answer` — Réponse imposée ; court-circuite l'invite si elle est fournie.
- `default` — Valeur retenue sur réponse vide ou absence de terminal.

**Retour** — True s'il faut combler, False sinon.

### `get_user_decisions`

```python
get_user_decisions(initial_df: pd.DataFrame, profiler_results: dict, *, correct_outliers: bool = None, fill_missing: bool = None, interactive: bool = True) -> Tuple[bool, bool]
```

Collecte les deux décisions de nettoyage avancé.

Ordre de priorité : une valeur booléenne explicite l'emporte ; à défaut, et
si `interactive` est vrai, la question est posée en terminal ; sinon la
réponse est négative. C'est ce qui permet au même code de servir la ligne
de commande (qui questionne) et l'interface web (qui transmet).

**Paramètres**

- `initial_df` — DataFrame initial.
- `profiler_results` — Résultats du profileur.
- `correct_outliers` — Décision imposée pour l'écrêtage.
- `fill_missing` — Décision imposée pour le remplissage.
- `interactive` — Autorise l'interrogation du terminal.

**Retour** — Le couple (correct_outliers, fill_missing).

### `run_all_cleaning_steps`

```python
run_all_cleaning_steps(df: pd.DataFrame, profile_info: dict = None, max_iterations: int = 5, correct_outliers: bool = True, fill_missing: bool = True, outlier_columns: list = None, missing_columns: list = None, outlier_thresholds: dict = None) -> Tuple[pd.DataFrame, dict]
```

Applique les nettoyages de manière itérative et ordonnée.

Ordre stratégique pour éviter les erreurs en cascade :

1. Forme (espaces) -> Pour préparer la conversion de types
2. Types fixes (Pandas Trap) -> Pour corriger les float64 -> Int64 si possible
3. Conversion Types stricte -> Pour pouvoir faire des calculs statistiques
4. Structure (doublons/vides) -> Une fois qu'on connaît les vrais types
5. Stats (Missing/Outliers) -> En dernier, sur des données propres

Les quatre premières étapes sont répétées tant qu'elles modifient encore
les données, `max_iterations` fois au plus.

**Paramètres**

- `df` — DataFrame à nettoyer
- `profile_info` — Résultats du profilage avant nettoyage ; ils désignent les colonnes dont la casse est à uniformiser. None pour les traiter toutes.
- `max_iterations` — Nombre maximum d'itérations
- `correct_outliers` — Booléen pour décider si on corrige les outliers
- `fill_missing` — Booléen pour décider si on remplit les valeurs manquantes
- `outlier_columns` — Colonnes à écrêter, si `correct_outliers` est vrai ; None pour toutes. C'est par là que l'interface web transmet le choix fait colonne par colonne.
- `missing_columns` — Colonnes à combler, si `fill_missing` est vrai ; None pour toutes.
- `outlier_thresholds` — Seuil IQR par colonne ; `SEUIL_IQR` pour une colonne non mentionnée.

**Retour** — Le DataFrame nettoyé et les statistiques de chaque opération : colonnes supprimées, espaces, casse, types convertis, valeurs illisibles vidées, notes ramenées, doublons, valeurs comblées, valeurs écrêtées et seuils.

## `src/cleaner_logger.py`

### `CleanLogger`

```python
class CleanLogger(initial_df: pd.DataFrame, stats: dict)
```

Gère les logs et l'affichage des statistiques du nettoyage.

#### `CleanLogger.update_final_state`

```python
update_final_state(final_df: pd.DataFrame)
```

Enregistre les dimensions et les colonnes du DataFrame nettoyé.

**Paramètres**

- `final_df` — DataFrame après nettoyage.

#### `CleanLogger.get_summary`

```python
get_summary() -> str
```

Génère un résumé des opérations effectuées.

**Retour** — Le résumé, en texte, prêt à afficher en console ; un avertissement si `update_final_state` n'a pas encore été appelée.

#### `CleanLogger.get_detailed_table`

```python
get_detailed_table(final_df: pd.DataFrame = None) -> pd.DataFrame
```

Retourne un DataFrame résumé des changements (optionnel, pour affichage tabulaire).

**Paramètres**

- `final_df` — DataFrame nettoyé ; s'il est fourni, les changements de type de chaque colonne sont recensés.

**Retour** — Un tableau des changements de type, une ligne par colonne dont le type a changé ; vide si `final_df` n'est pas fourni.

### `generate_and_print_report`

```python
generate_and_print_report(initial_df: pd.DataFrame, stats: Dict, final_df: pd.DataFrame)
```

Affiche en console le résumé comparatif d'un nettoyage.

**Paramètres**

- `initial_df` — DataFrame avant nettoyage.
- `stats` — Statistiques renvoyées par `run_all_cleaning_steps`.
- `final_df` — DataFrame après nettoyage.

## `src/cleaner_reporter.py`

### `CleanerReporter`

```python
class CleanerReporter(profiler, logger, source_file_path=None)
```

Génère un rapport détaillé du nettoyage des données.

#### `CleanerReporter.demander_generation_rapport`

```python
demander_generation_rapport(*, answer: bool = None) -> bool
```

Décide s'il faut générer le rapport de nettoyage.

**Paramètres**

- `answer` — Réponse imposée ; court-circuite l'invite si elle est fournie. C'est par ce paramètre que l'interface web transmet le choix fait dans une case à cocher.

**Retour** — True s'il faut générer le rapport, False sinon.

#### `CleanerReporter.render`

```python
render(stats: dict = None, contraintes: dict = None) -> str
```

Produit le contenu du rapport en mémoire, sans accès au disque.

C'est ce que consomme l'interface web pour proposer le rapport au
téléchargement sans rien écrire sur le serveur.

**Paramètres**

- `stats` — Statistiques de nettoyage à détailler.
- `contraintes` — Résultats du validateur avant et après nettoyage (``{"avant": ..., "apres": ...}``). Sans eux, le rapport ne comporte pas de section « Contraintes ».

**Retour** — Le contenu Markdown du rapport.

#### `CleanerReporter.generate_with_stats`

```python
generate_with_stats(output_path: str, stats: dict = None, contraintes: dict = None) -> str
```

Génère le fichier Markdown complet avec les statistiques.

**Paramètres**

- `output_path` — Chemin du fichier à écrire.
- `stats` — Statistiques de nettoyage à détailler.
- `contraintes` — Résultats du validateur avant et après nettoyage (voir `render`).

**Retour** — Le chemin absolu du fichier écrit.

**Exceptions**

- `RuntimeError` — Si l'écriture échoue.

#### `CleanerReporter.generate`

```python
generate(output_path: str = 'cleaning_report.md') -> str
```

Génère le fichier Markdown complet (ancienne version).

**Paramètres**

- `output_path` — Chemin du fichier à écrire.

**Retour** — Le chemin absolu du fichier écrit.

### `build_cleaning_report_path`

```python
build_cleaning_report_path(reports_dir, input_file, horodatage: str = None) -> Path
```

Compose le chemin horodaté d'un rapport de nettoyage.

**Paramètres**

- `reports_dir` — Répertoire de destination.
- `input_file` — Fichier source, dont le nom de base est réutilisé.
- `horodatage` — Suffixe imposé, pour que tous les fichiers d'une même exécution partagent la même marque ; l'instant présent si omis.

**Retour** — Le chemin complet du rapport.

### `generate_enhanced_report`

```python
generate_enhanced_report(profiler, logger, reports_dir, input_file, stats, *, generate: bool = None, horodatage: str = None, contraintes: dict = None)
```

Génère le rapport de nettoyage détaillé.

**Paramètres**

- `profiler` — Objet exposant un attribut `profile_results`. Un simple `SimpleNamespace(profile_results=...)` suffit : c'est le seul attribut lu.
- `logger` — Journal exposant `.info()` et `.error()`.
- `reports_dir` — Répertoire de destination.
- `input_file` — Fichier source, dont le nom de base est réutilisé.
- `stats` — Statistiques de nettoyage à détailler.
- `generate` — Décision imposée — True génère sans demander, False saute l'étape, None pose la question en terminal.
- `horodatage` — Suffixe commun aux fichiers de l'exécution en cours.
- `contraintes` — Résultats du validateur avant et après nettoyage (``{"avant": ..., "apres": ...}``), pour la section « Contraintes ».

**Retour** — Le chemin du rapport écrit, ou None si l'étape a été sautée ou a échoué.

## `src/plot_factory.py`

Fabrique de graphiques, indépendante de toute interface.

Ce module est le point unique de création des figures du projet. Il alimente
aussi bien les rapports HTML (qui ont besoin d'un PNG encodé en base64) que
l'interface Streamlit (qui a besoin d'un objet `Figure` à passer à `st.pyplot`).

**Pourquoi ne pas utiliser pyplot ?**

`plt.figure()` enregistre chaque figure dans le registre global de pyplot
(`Gcf`), d'où elle ne sort que par un `plt.close()` explicite. Dans un processus
de longue durée — un serveur Streamlit qui vit des heures et réexécute le script
à chaque interaction — ce registre grossit indéfiniment, et matplotlib finit par
émettre `RuntimeWarning: More than 20 figures have been opened`. Un `plt.close()`
oublié, ou sauté par une exception, suffit à créer la fuite.

On utilise donc l'API d'embarquement documentée (`Figure` + `FigureCanvasAgg`).
Une figure construite ainsi n'entre jamais dans le registre global : elle est
libérée par le ramasse-miettes dès que plus personne ne la référence. La fuite
devient structurellement impossible au lieu d'être évitée par discipline.

**Règles de cycle de vie à respecter :**

1. Ne jamais importer `matplotlib.pyplot` ailleurs dans `src/`. Un test le
vérifie (`tests/test_plot_factory.py`).
2. Ne jamais stocker une `Figure` dans `st.session_state` : elle serait retenue
pendant toute la session, pour chaque session. Stocker les données d'entrée
et reconstruire la figure à l'affichage.
3. Côté Streamlit, afficher via un helper unique qui libère les artistes
immédiatement après le rendu (voir `afficher_figure` dans `streamlit_app.py`).

### `new_figure`

```python
new_figure(figsize: tuple[float, float], dpi: int = 100) -> Figure
```

Crée une figure détachée du registre global de pyplot.

**Paramètres**

- `figsize` — Dimensions en pouces (largeur, hauteur).
- `dpi` — Résolution en points par pouce.

**Retour** — Une figure vierge, munie d'un canevas Agg.

### `figure_histogram`

```python
figure_histogram(df: pd.DataFrame, col: str, *, figsize: tuple[float, float] = (7, 3.89), dpi: int = 150) -> Figure
```

Histogramme avec estimation de densité pour une colonne numérique.

**Paramètres**

- `df` — Source des données.
- `col` — Nom de la colonne à tracer.
- `figsize` — Dimensions en pouces.
- `dpi` — Résolution.

**Retour** — La figure construite.

### `figure_boxplot`

```python
figure_boxplot(df: pd.DataFrame, col: str, *, figsize: tuple[float, float] = (3.5, 3.5), dpi: int = 100) -> Figure
```

Boîte à moustaches verticale pour une colonne numérique.

**Paramètres**

- `df` — Source des données.
- `col` — Nom de la colonne à tracer.
- `figsize` — Dimensions en pouces.
- `dpi` — Résolution.

**Retour** — La figure construite.

### `is_identifier_column`

```python
is_identifier_column(series: pd.Series) -> bool
```

Indique si une colonne se comporte comme un identifiant.

Une colonne dont presque chaque valeur est distincte (identifiant, courriel,
nom propre) n'a pas de répartition à montrer : son diagramme en barres
n'aligne que des modalités à une occurrence. Sous 20 valeurs, le jugement
serait trop fragile : la colonne n'est alors jamais écartée.

**Paramètres**

- `series` — La colonne à examiner.

**Retour** — True si au moins 90 % des valeurs présentes sont distinctes.

### `split_categorical_columns`

```python
split_categorical_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]
```

Sépare les colonnes catégorielles à tracer de celles qui sont des identifiants.

**Paramètres**

- `df` — Source des données.

**Retour** — Un couple (colonnes à tracer, colonnes écartées comme identifiants).

### `figure_barplot_top`

```python
figure_barplot_top(df: pd.DataFrame, col: str, *, top_n: int = 10, figsize: tuple[float, float] = (10, 4), dpi: int = 120) -> Figure
```

Diagramme en barres des modalités les plus fréquentes d'une colonne.

**Paramètres**

- `df` — Source des données.
- `col` — Nom de la colonne à tracer.
- `top_n` — Nombre de modalités affichées.
- `figsize` — Dimensions en pouces.
- `dpi` — Résolution.

**Retour** — La figure construite.

### `figure_scatter_matrix`

```python
figure_scatter_matrix(df: pd.DataFrame, cols: Sequence[str] | None = None, *, max_cols: int = 6, cell_size: float = 2.2, dpi: int = 100) -> Figure
```

Matrice de dispersion des colonnes numériques.

La grille est construite à la main plutôt qu'avec `pd.plotting.scatter_matrix`,
qui crée sa propre figure via un interne pandas et nous ferait retomber dans
le registre global de pyplot.

Le nombre de colonnes est plafonné : au-delà, la figure devient illisible et
son poids explose (l'ancienne version produisait une image de 25×25 pouces,
soit plusieurs mégaoctets de base64 par rapport).

**Paramètres**

- `df` — Source des données.
- `cols` — Colonnes imposées, ou None pour prendre les colonnes numériques.
- `max_cols` — Nombre maximal de colonnes représentées.
- `cell_size` — Côté d'une cellule de la grille, en pouces.
- `dpi` — Résolution.

**Retour** — La figure construite.

**Exceptions**

- `ValueError` — S'il y a moins de deux colonnes numériques exploitables.

### `figure_correlation_heatmap`

```python
figure_correlation_heatmap(df: pd.DataFrame, cols: Sequence[str] | None = None, *, figsize: tuple[float, float] = (10, 8), dpi: int = 100) -> Figure
```

Carte thermique des corrélations entre colonnes numériques.

**Paramètres**

- `df` — Source des données.
- `cols` — Colonnes imposées, ou None pour prendre les colonnes numériques.
- `figsize` — Dimensions en pouces.
- `dpi` — Résolution.

**Retour** — La figure construite.

**Exceptions**

- `ValueError` — S'il y a moins de deux colonnes numériques exploitables.

### `figure_to_base64_png`

```python
figure_to_base64_png(fig: Figure, *, dpi: int | None = None, bbox_inches: str | None = 'tight') -> str
```

Encode une figure en PNG base64, sans passer par le disque.

**Paramètres**

- `fig` — Figure à encoder.
- `dpi` — Résolution d'export ; celle de la figure par défaut.
- `bbox_inches` — Politique de recadrage passée à `savefig`.

**Retour** — La chaîne base64 du PNG.

### `figure_to_img_tag`

```python
figure_to_img_tag(fig: Figure, alt: str, style: str = '', **kwargs) -> str
```

Produit une balise `<img>` autonome contenant la figure.

**Paramètres**

- `fig` — Figure à intégrer.
- `alt` — Texte alternatif de l'image.
- `style` — Style CSS inline appliqué à la balise.
- `**kwargs` — Transmis à `figure_to_base64_png`.

**Retour** — Le fragment HTML de la balise image.

## `src/validator.py`

Vérification de contraintes saisies par l'utilisateur.

Le validateur **signale, il ne corrige jamais** : le DataFrame reçu n'est pas
modifié, et chaque ligne qui enfreint une règle est restituée à l'utilisateur
avec des exemples. C'est la suite logique de la garantie « pas de perte
silencieuse » : ce que l'outil ne peut pas trancher, il doit au moins le dire.

Une **règle** est un dictionnaire sérialisable en JSON::

{"id": "plage-age-1a2b3c", "type": "plage", "colonnes": ["age"],
"parametres": {"min": 0, "max": 120}, "libelle": "Âge plausible"}

Ce format est le seul contrat du module. Qu'une règle vienne d'un formulaire
web, d'un menu en terminal, d'un fichier enregistré ou, plus tard, d'un
traducteur de phrases en langage courant, `valider` la traite de la même façon.

Types de règle (`TYPES_REGLES`) :

* ``plage`` : valeur minimale et/ou maximale, nombres ou dates.
* ``longueur`` : nombre de caractères minimal et/ou maximal.
* ``format`` : format nommé (``nom``) ou expression régulière (``motif``).
* ``valeurs_autorisees`` : liste fermée de valeurs (``valeurs``).
* ``non_vide`` : une valeur est obligatoire.
* ``unique`` : aucune valeur (ou combinaison de colonnes) répétée.
* ``comparaison_colonnes`` : première colonne ``operateur`` seconde colonne.

Une cellule vide n'enfreint jamais une règle, sauf ``non_vide`` : le manque est
l'affaire du profilage. Une valeur qu'on ne sait pas lire comme un nombre ou
une date n'est pas non plus comptée comme une violation : elle est déclarée à
part (``non_evaluables``), pour qu'aucune valeur ne soit ignorée en silence.

Ce module ne connaît aucune interface : il ne pose aucune question.

### `MotifTropCouteux`

```python
class MotifTropCouteux(…)
```

Un motif personnalisé met trop de temps à s'appliquer ; son calcul est interrompu.

### `nouvelle_regle`

```python
nouvelle_regle(type_regle: str, colonnes: list[str] | str, parametres: dict | None = None, libelle: str | None = None) -> dict
```

Construit une règle avec un identifiant stable.

L'identifiant est déduit du type, des colonnes et des paramètres : la même
règle porte toujours le même identifiant, et deux règles différentes ne
risquent pas de se confondre.

**Paramètres**

- `type_regle` — Un des `TYPES_REGLES`.
- `colonnes` — Nom de colonne, ou liste de noms.
- `parametres` — Paramètres propres au type de règle.
- `libelle` — Nom lisible facultatif, repris dans les rapports.

**Retour** — La règle, prête pour `valider` ou `sauver_regles`. Sa validité n'est pas contrôlée ici : voir `verifier_regle`.

### `verifier_regle`

```python
verifier_regle(regle: object) -> list[str]
```

Contrôle la forme d'une règle, sans regarder les données.

**Paramètres**

- `regle` — La règle à contrôler.

**Retour** — La liste des problèmes, en français. Vide si la règle est bien formée.

### `echapper_markdown`

```python
echapper_markdown(texte: object) -> str
```

Neutralise le Markdown d'un texte venu de l'utilisateur, pour l'afficher tel quel.

Un fichier de règles peut venir d'un tiers : sans cela, un nom de contrainte
comme « [cliquez ici](http://…) » s'afficherait comme un lien, et
« ![](http://…) » ferait charger une image depuis un site externe, au seul
affichage de la page.

**Paramètres**

- `texte` — Texte à afficher (nom de contrainte, de colonne, valeur…).

**Retour** — Le texte, dont les caractères de mise en forme sont protégés.

### `decrire_regle`

```python
decrire_regle(regle: dict) -> str
```

Décrit une règle en une phrase française.

**Paramètres**

- `regle` — Une règle bien formée.

**Retour** — Le libellé de la règle s'il existe, sinon une description déduite de son type et de ses paramètres.

### `regles_vers_texte`

```python
regles_vers_texte(regles: list[dict]) -> str
```

Met des règles en forme de texte JSON, sans rien écrire sur le disque.

C'est ce que consomme l'interface web pour proposer l'export des règles au
téléchargement : le fichier n'existe jamais sur le serveur.

**Paramètres**

- `regles` — Règles à exporter.

**Retour** — Le texte JSON, relisible par `regles_depuis_texte` et `charger_regles`.

### `sauver_regles`

```python
sauver_regles(regles: list[dict], chemin: str | Path) -> Path
```

Enregistre des règles dans un fichier JSON, pour les rejouer plus tard.

**Paramètres**

- `regles` — Règles à enregistrer.
- `chemin` — Fichier de destination ; ses dossiers parents sont créés.

**Retour** — Le chemin du fichier écrit.

### `regles_depuis_texte`

```python
regles_depuis_texte(texte: str) -> list[dict]
```

Lit des règles depuis un texte JSON (contenu d'un fichier de règles).

Accepte le format écrit par `sauver_regles` ou une simple liste de règles.

**Paramètres**

- `texte` — Contenu JSON.

**Retour** — Les règles lues.

**Exceptions**

- `ValueError` — Si le texte dépasse `MAX_TAILLE_FICHIER_REGLES`, s'il n'est pas du JSON valide ou trop imbriqué, s'il contient plus de `MAX_REGLES` règles, ou si une règle est mal formée. Le message dit laquelle et pourquoi.

### `charger_regles`

```python
charger_regles(chemin: str | Path) -> list[dict]
```

Lit un fichier de règles JSON.

**Paramètres**

- `chemin` — Fichier écrit par `sauver_regles` (ou liste JSON de règles).

**Retour** — Les règles lues.

**Exceptions**

- `FileNotFoundError` — Si le fichier n'existe pas.
- `ValueError` — Si le contenu n'est pas valide (voir `regles_depuis_texte`).

### `valider`

```python
valider(df: pd.DataFrame, regles: list[dict]) -> dict
```

Vérifie un DataFrame contre une liste de règles, sans le modifier.

Une règle mal formée, ou qui vise une colonne absente, ne lève pas
d'exception : elle est rapportée en erreur et les autres sont évaluées.

**Paramètres**

- `df` — Données à vérifier. Jamais modifiées.
- `regles` — Règles à appliquer (voir `nouvelle_regle`).

**Retour** — Un dictionnaire ``{"resultats": [...], "total_violations": n, "regles_en_erreur": n, "regles_respectees": n}``. Chaque résultat contient : ``id``, ``type``, ``colonnes``, ``description``, ``statut`` (``"respectee"``, ``"violations"`` ou ``"erreur"``), ``evaluees``, ``violations``, ``pourcentage``, ``non_evaluables``, ``lignes`` (étiquettes d'index des lignes fautives, `MAX_LIGNES` au plus), ``exemples`` (`MAX_EXEMPLES` valeurs au plus) et ``message``.

### `resumer_resultat`

```python
resumer_resultat(resultat: dict | None) -> str
```

Résume en quelques mots le résultat d'une règle, pour une cellule de tableau.

**Paramètres**

- `resultat` — Résultat d'une règle, tel que le renvoie `valider`, ou None si la règle n'a pas été évaluée à ce moment-là.

**Retour** — Un texte court : « ✅ respectée », « ⚠️ 2 (40 %) », « ❌ non évaluable », suivi du nombre de valeurs illisibles s'il y en a ; « — » si la règle n'a pas été évaluée.

### `formater_bilan`

```python
formater_bilan(validation: dict, titre: str = 'Contraintes') -> str
```

Met en forme le résultat de `valider` pour la console ou un rapport texte.

**Paramètres**

- `validation` — Résultat de `valider`.
- `titre` — Intitulé du bilan.

**Retour** — Un texte multiligne. Vide si aucune règle n'a été évaluée.

## `src/saisie_regles.py`

Description du formulaire de création de règles, partagée par les deux façades.

Créer une règle demande toujours les mêmes choses, qu'on soit dans le navigateur
ou dans un terminal : choisir un type, lui donner ses colonnes, remplir quelques
champs, puis contrôler le résultat. Seule la manière d'afficher ces champs
change. Ce module décrit donc **ce qu'on demande**, une fois pour toutes, et
construit la règle à partir de ce qui a été saisi ; chaque interface se borne à
afficher les champs à sa manière (widgets Streamlit, questions en terminal).

Il ne connaît aucune interface et ne pose aucune question. Les saisies lui
arrivent sous forme de textes, tels que l'utilisateur les a tapés : c'est lui qui
les lit (nombre, date, liste séparée par des points-virgules) et qui rapporte,
en français, ce qui ne va pas.

Un champ se décrit par un dictionnaire :

* ``nom`` : clé du paramètre dans la règle (``min``, ``max``, ``operateur``…) ;
* ``libelle`` : intitulé lisible ;
* ``genre`` : ``borne`` (nombre ou date), ``entier``, ``texte``, ``liste``
(valeurs séparées par des points-virgules) ou ``choix`` ;
* ``obligatoire`` : vrai si la règle ne peut pas se passer du champ ;
* ``choix`` : pour le genre ``choix``, la liste des couples (valeur, libellé) ;
* ``aide`` : une phrase d'explication, avec un exemple ;
* ``si_vide`` : nom d'un autre champ ; celui-ci ne se demande que si l'autre est
resté vide (pas de motif personnalisé quand on a choisi un format connu).

### `types_disponibles`

```python
types_disponibles() -> list[tuple[str, str]]
```

Liste les types de règle proposés, dans l'ordre où on les présente.

**Retour** — Des couples (type, libellé lisible), prêts pour une liste de choix.

### `champs_du_type`

```python
champs_du_type(type_regle: str) -> list[dict]
```

Donne les champs à demander pour un type de règle.

**Paramètres**

- `type_regle` — Un des types de `types_disponibles`.

**Retour** — La liste des champs (vide pour une règle sans paramètre), en copie : l'appelant peut la modifier sans toucher à la description.

**Exceptions**

- `KeyError` — Si le type est inconnu.

### `colonnes_attendues`

```python
colonnes_attendues(type_regle: str) -> tuple[int, int | None]
```

Donne le nombre de colonnes qu'un type de règle porte.

**Paramètres**

- `type_regle` — Un des types de `types_disponibles`.

**Retour** — Le couple (minimum, maximum) ; le maximum est None s'il n'y en a pas.

**Exceptions**

- `KeyError` — Si le type est inconnu.

### `lire_borne`

```python
lire_borne(texte: str) -> int | float | str
```

Lit une borne saisie : un nombre si possible, sinon le texte (une date).

**Paramètres**

- `texte` — Saisie de l'utilisateur ; la virgule décimale est acceptée.

**Retour** — Un entier (« 120 »), un flottant (« 0,5 ») ou le texte tel quel (« 05/01/2024 »), dont la validité de date est contrôlée plus tard.

### `construire_regle`

```python
construire_regle(type_regle: str, colonnes: list[str] | str, saisies: dict | None = None, libelle: str | None = None) -> tuple[dict | None, list[str]]
```

Construit une règle à partir de ce que l'utilisateur a saisi.

Les champs vides sont ignorés (« aucun minimum »). Les problèmes sont
rapportés en français plutôt que levés : l'interface les affiche et laisse
l'utilisateur corriger.

**Paramètres**

- `type_regle` — Un des types de `types_disponibles`.
- `colonnes` — Nom de colonne, ou liste de noms.
- `saisies` — Textes saisis, par nom de champ (voir `champs_du_type`).
- `libelle` — Nom lisible facultatif de la règle.

**Retour** — Le couple (règle, problèmes). La règle est None si les problèmes ne sont pas vides ; sinon elle est valide (`verifier_regle`) et prête pour `valider`.

### `saisies_depuis_regle`

```python
saisies_depuis_regle(regle: dict) -> dict[str, str]
```

Retrouve les textes à saisir pour reconstruire une règle existante.

C'est l'inverse de `construire_regle` : il sert à pré-remplir un formulaire
quand l'utilisateur veut modifier une règle plutôt que la refaire.

**Paramètres**

- `regle` — Une règle bien formée.

**Retour** — Les textes à saisir, par nom de champ. Les champs que la règle ne porte pas sont absents. Reconstruire la règle avec ces textes redonne la même.

## `src/horodatage.py`

Horodatage des fichiers produits.

Tous les fichiers issus d'une même exécution — fichier nettoyé, rapport de
nettoyage, rapports de profilage — portent le même suffixe. On peut ainsi
comparer plusieurs essais (avec et sans écrêtage, avec et sans remplissage)
sans qu'aucun n'écrase le précédent, et retrouver d'un coup d'œil les fichiers
qui vont ensemble.

Le format `AAAAMMJJ_HHMMSS` a deux propriétés voulues :

* l'ordre alphabétique des noms de fichiers est aussi l'ordre chronologique ;
* la précision à la seconde évite qu'un second essai lancé dans la même minute
écrase le premier — ce qui arrivait avec l'ancien format à la minute.

### `horodater`

```python
horodater(moment: datetime | None = None) -> str
```

Produit le suffixe d'horodatage d'un nom de fichier.

**Paramètres**

- `moment` — Instant à représenter ; l'instant présent si omis.

**Retour** — Le suffixe au format `AAAAMMJJ_HHMMSS`, par exemple `20260929_143207`.

## `src/marque.py`

Identité de Quitus : nom, devise et logo, pour l'application et les rapports.

Le logo est intégré aux rapports sous forme d'URI `data:` plutôt que référencé
par un chemin : un rapport téléchargé doit rester autonome, et s'afficher avec
son en-tête où qu'on l'ouvre. C'est aussi ce qu'autorise la politique de
sécurité des rapports HTML (`img-src data:`), qui interdit tout chargement
externe.

Si le fichier du logo est absent — module utilisé hors du dépôt, par exemple —,
les en-têtes retombent sur une version texte : un rapport ne doit jamais
échouer pour une question d'habillage.

### `logo_data_uri`

```python
logo_data_uri() -> str | None
```

Encode le logo en URI `data:` intégrable dans un rapport.

**Retour** — L'URI `data:image/svg+xml;base64,…`, ou None si le logo est introuvable.

### `logo_adaptatif_svg`

```python
logo_adaptatif_svg() -> str | None
```

Fusionne les variantes claire et sombre du logo en un seul SVG.

Chaque couleur qui diffère entre les deux variantes devient une valeur
CSS `light-dark(claire, sombre)`, que le navigateur résout selon le
`color-scheme` de l'élément parent. Streamlit fixe ce `color-scheme` sur
le conteneur de l'application selon le thème réellement affiché : le logo
suit donc le thème, y compris quand le visiteur en change, sans que Python
ait à le deviner.

L'attribut de couleur d'origine est conservé : un navigateur qui ignore
`light-dark()` affiche simplement la variante claire. Une couleur absente
d'une variante s'écrit `transparent` : `light-dark()` n'accepte que des
couleurs, et `none` y invaliderait toute la déclaration.

**Retour** — Le code SVG, ou None si une variante manque ou si leurs structures divergent au point de ne plus pouvoir être appariées.

### `en_tete_html`

```python
en_tete_html() -> str
```

Produit l'en-tête HTML des rapports : le logo, ou son équivalent texte.

**Retour** — Le fragment HTML de l'en-tête.

### `en_tete_markdown`

```python
en_tete_markdown() -> str
```

Produit l'en-tête Markdown des rapports : le logo, ou son équivalent texte.

Le texte alternatif de l'image reprend le nom et la devise : un lecteur
Markdown qui n'affiche pas les images montre alors la marque en clair.

**Retour** — Le fragment Markdown de l'en-tête, suivi d'une ligne vide.

## `src/console_capture.py`

Capture de la sortie console, pour la réafficher dans une interface graphique.

Les modules de `src/` communiquent leur progression par `print()`, ce qui
convient parfaitement en ligne de commande. Dans un navigateur, cette sortie
est simplement perdue : elle part dans la console du serveur, que l'utilisateur
ne voit pas.

Ce module permet de la détourner vers un tampon mémoire, que l'interface web
affiche ensuite dans un volet dépliable. Le pipeline reste ainsi bavard et
traçable, sans qu'aucun module métier n'ait à connaître Streamlit.

### `capture_output`

```python
capture_output(*, capture_logging: bool = True) -> Iterator[io.StringIO]
```

Détourne stdout, stderr et le journal racine vers un tampon mémoire.

Le traitement explicite du module `logging` n'est pas redondant avec la
redirection de `stderr` : un `StreamHandler` créé avant l'entrée dans ce
contexte a capturé la référence à `sys.stderr` à sa construction, et
continuerait donc d'écrire dans la vraie sortie d'erreur. C'est le cas du
journal utilisé par `generate_enhanced_report`.

À utiliser autour d'une étape de pipeline précise, jamais autour d'appels
d'affichage de l'interface : une exception levée dans le bloc verrait sa
trace absorbée par le tampon au lieu de remonter au gestionnaire d'erreurs.

**Paramètres**

- `capture_logging` — Détourne également les messages du journal racine.

**Produit** — Le tampon recevant la sortie ; `getvalue()` en donne le contenu.
