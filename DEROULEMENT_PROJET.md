# DEROULEMENT_PROJET.MD

## Contexte du projet

**Objectif principal** : Créer un script Python capable de détecter automatiquement les problèmes courants dans un fichier CSV et d'y remédier sans connaître à l'avance le contenu ni la structure du fichier.

**Contraintes clés** :
- Ne pas savoir comment est le fichier initialement (encodage, séparateur, types...)
- Manipuler des données sous forme de DataFrame pandas
- Fournir un rapport détaillé des transformations effectuées

---

## Étape 1 : Analyse des besoins et planification

### Problématiques identifiées dans les CSV bruts :
1. **Encodage** : UTF-8, Latin1, CP1252... (caractères spéciaux mal affichés)
2. **Séparateur** : Point-virgule (';'), virgule (','), tabulation ('\t'), pipe ('|')...
3. **Valeurs manquantes** : NaN, vides, "NA"...
4. **Doubons exacts** : lignes identiques
5. **Types incohérents** : dates/numéros stockés en texte, espaces superflus...
6. **Colonnes vides** : >95% de valeurs manquantes
7. **Valeurs aberrantes (outliers)** : écarts importants dans les données numériques

### Solutions envisagées :
- Créer des fonctions dédiées pour chaque problème
- Ordonner intelligemment les nettoyages (ordre logique)
- Détecter automatiquement encodage et séparateur
- Fournir un rapport exhaustif

---

## Étape 2 : Conception du cleaner automatique

### Architecture choisie initialement

```
cleaner_auto.py
├── detect_delimiter()     → Détecte le séparateur (; , \t |)
├── detect_encoding()      → Détecte l'encodage (UTF-8, Latin1...)
├── clean_empty_columns()  → Supprime les colonnes >95% vides
├── clean_whitespace()     → Nettoie espaces superflus
├── clean_types()          → Convertit automatique string→num/datetime
├── clean_duplicates()     → Supprime doublons exacts
├── clean_missing_values() → Remplit NaN (médiane/mode)
├── clean_outliers()       → Corrige valeurs aberrantes (IQR)
└── clean_csv_file()       → Fonction principale qui orchestre tout
```

### Logique d'orchestration (ordre du nettoyage)

1. **Suppression colonnes vides** → Réduire le bruit dès le début
2. **Nettoyage espaces** → Préparer les textes avant tout traitement
3. **Conversion types** → Numérique et dates à leurs bons formats
4. **Suppression doublons** → Éviter de fausser les stats après conversion
5. **Valeurs manquantes** → Remplir avec médiane (num) ou mode (text)
6. **Traitement outliers** → En dernier pour ne pas fausser les calculs

---

## Étape 3 : Implémentation - détails techniques

### Fonction `detect_delimiter()`
- Teste les séparateurs courants (;, ,, \t, |)
- Vérifie que le nombre de colonnes est cohérent sur plusieurs lignes
- Retourne ',' par défaut si rien ne correspond

### Fonction `detect_encoding()`
- Essaie successivement UTF-8, Latin1, CP1252
- Si l'encodage marche (lecture sans erreur) → c'est le bon
- Ne nécessite pas de dépendance externe (pas de chardet nécessaire)
- Fallback sur UTF-8 si tout échoue

### Fonction `clean_missing_values()`
- **Colonnes numériques** → Médiane (plus robuste que la moyenne face aux outliers)
- **Colonnes textuelles** → Mode (valeur la plus fréquente)
- Supprime les colonnes si >50% de NaN restants

### Fonction `clean_types()`
- **Numérique** : Essaie `pd.to_numeric()`, vérifie que les valeurs sont cohérentes
- **Date** : Essaie `pd.to_datetime()`, accepte si >80% des valeurs converties correctement
- Garde le texte inchangé sinon (éviter de fausser codes postaux, numéros de téléphone...)

### Fonction `clean_outliers()`
- Utilise la méthode **IQR (Interquartile Range)**
- Bornes = Q1 - 1.5*IQR et Q3 + 1.5*IQR
- Remplace les valeurs par les bornes (winsorization)
- Appliqué en dernier pour ne pas influencer les autres calculs

### Fonction `clean_duplicates()`
- Utilise `drop_duplicates()` de pandas
- Retourne le nombre exact de lignes supprimées

### Fonction `clean_empty_columns()`
- Supprime les colonnes avec ≥95% de valeurs manquantes
- Garde les données avec au moins 5% d'information

---

## Étape 4 : Fonction principale `clean_csv_file()`

Cette fonction est le point d'entrée qui :
1. **Charge** le fichier en détectant automatiquement séparateur et encodage
2. **Applique** les nettoyages dans l'ordre logique
3. **Sauvegarde** le résultat propre
4. **Retourne un rapport** avec toutes les transformations effectuées

### Exemple d'utilisation :

```python
# Dans le terminal ou IDLE :
python src/cleaner_auto.py

# Output attendu :
# 📂 Chargement : data/raw/reservation_rivage_brut.csv
#    Séparateur : ';' | Encodage : latin-1
#
# 🧹 Nettoyage en cours...
# ✓ Colonnes vides supprimées
# ✓ Espaces nettoyés
# ✓ Types convertis
# ✓ 42 doublons supprimés
# ✓ Valeurs manquantes traitées
# ✓ Outliers corrigés
#
# ✅ Fichier sauvegardé : data/processed/reservation_nettoye.csv
# 📊 Résultat : 1500→1458 lignes, 12→10 colonnes
```

---

## Étape 5 : Refactoring et architecture modulaire (en cours)

Dans une version plus avancée et professionnelle, nous avons refactorisé le projet pour le rendre plus robuste et maintenable. 

### Nouvelle architecture du projet
Au lieu d'un seul fichier monolithique (`cleaner_auto.py`), le projet est maintenant découpé en modules distincts :

```
src/
├── __init__.py          → Marque le dossier comme un package Python
├── file_loader.py       → Chargement et détection (encodage, séparateur)
├── cleaner_engine.py    → Moteur de nettoyage (logique pure)
├── report_generator.py  → Génération des rapports
└── main.py              → Orchestrateur principal (point d'entrée)
```

### Apports de la modularité

1.  **Détachement du chargement (`file_loader`)** :
    *   Permet de supporter plusieurs formats (CSV, Excel, JSON) sans toucher à la logique de nettoyage.
    *   Utilise `os.path` importé globalement pour respecter les bonnes pratiques d'importation Python.

2.  **Séparation des responsabilités** :
    *   Le `cleaner_engine.py` manipule uniquement des `DataFrames`. Il ne sait pas d'où viennent les données ni où elles vont. C'est une fonction pure.
    *   Le `report_generator.py` s'occupe de la présentation, sans effectuer de calculs lourds sur les données brutes.

3.  **Orchestration via `main.py`** :
    *   Le script principal devient très lisible et orienté "workflow" : Charger → Nettoyer → Sauvegarder → Rapporter.
    *   Facilite les tests unitaires : on peut tester le moteur de nettoyage sans avoir besoin d'un fichier CSV physique.

### Commandes pour la version modulaire

```bash
# Pour exécuter le projet refactored
python src/main.py

# Résultat attendu (extrait du rapport généré) :
# ============================================================
# RAPPORT DE NETTOYAGE DE DONNÉES
# ============================================================
# 📊 Lignes: 1500 → 1458 (-42)
# 📑 Colonnes: 12 → 10 (+2)
# 🗑️ Colonnes supprimées (vides): 1
# ... etc
```

### Notes pour l'entretien technique
*   **Pourquoi avoir refactorisé ?** Pour respecter le principe de responsabilité unique (SRP - Single Responsibility Principle). Chaque fichier a une tâche précise.
*   **Gestion des imports :** Attention à toujours importer les dépendances au début du fichier (`import os`, `import pandas`) et non dans les fonctions, pour garantir la lisibilité et l'ordre d'exécution.
*   **Évolutivité :** Cette structure permet d'ajouter le support de JSON (via `pd.read_json`) ou d'une base SQL très facilement sans casser le cœur du programme.

---

## Étape 6 : Optimisations récentes et corrections critiques

Dans les dernières itérations, nous avons corrigé des bugs structurels et optimisé l'ordre logique des opérations pour garantir la fiabilité du nettoyage.

### 1. Correction de la structure du pipeline (`run_pipeline.py`)
*   **Problème :** L'indentation dans le bloc `try/except` de la sauvegarde CSV était erronée, risquant de faire planter le script.
*   **Solution :** Structuration propre avec des chemins dynamiques via `pathlib`. Le pipeline orchestre maintenant clairement : Chargement → Nettoyage → Sauvegarde → Rapport.

### 2. Révision critique de l'ordre des tâches (le "golden path")
L'ordre d'exécution a été redéfini pour éviter les faux négatifs en Data Science :
1.  **`clean_empty_columns`** : On retire le bruit dès le début.
2.  **`clean_whitespace`** : Crucial avant toute comparaison (ex: " Paris" vs "Paris").
3.  **`clean_types`** : **Point clé !** Les conversions doivent avoir lieu *avant* de chercher les doublons. Sans ça, " 10.5" et "10.5" seraient vus comme différents.
4.  **`clean_duplicates`** : Maintenant que les types sont homogènes, la détection est fiable.
5.  **`clean_missing_values`** : On remplit les trous une fois la structure figée.
6.  **`clean_outliers`** : En dernier pour ne pas fausser les calculs de bornes ou de stats.

### 3. Renforcement de `clean_types` dans `cleaner_engine.py`
*   **Robustesse accrue :** Utilisation de `errors='coerce'` dans `pd.to_numeric` et `pd.to_datetime`. Cela permet de transformer les erreurs en `NaN` plutôt que de faire planter le script.
*   **Protection des IDs :** Ajout d'une heuristique pour éviter de convertir des numéros de téléphone ou ID clients longs (>= 1e6) en float, ce qui entraînerait une perte de précision (ex: fin du nombre transformée en `.0`).
*   **Détection Date/Floating Point :** Une colonne n'est convertie en date que si >80% des valeurs sont valides.

### Impact sur le projet
Ces ajustements rendent le script "Data Analyst" beaucoup plus résilient face à des fichiers réels, sales et mal formatés (comme ceux qu'on trouve souvent en entreprise). Le pipeline ne "plante" plus silencieusement sur des formats inattendus.

---

## Étape 7 : Structuration du projet, tests unitaires et stabilisation du moteur de nettoyage

Dans cette phase, nous avons professionnalisé l'architecture du projet et commencé à garantir sa fiabilité grâce aux tests automatisés.

### 1. Résolution des conflits d'environnement (uv) pour les tests
Pour que pytest puisse importer nos modules correctement, deux ajustements cruciaux ont été faits :
*   **Configuration de `pyproject.toml`** : Ajout de la section `[tool.pytest.ini_options]` avec `pythonpath = ["."]`. Cela dit explicitement à Python de regarder dans le dossier racine pour trouver les dossiers `src` et `tests`.
*   **Nettoyage des fichiers markers** : Le fichier `src/__init__.py` (qui n'est qu'un marqueur de package) a été vidé. Il ne doit contenir aucun code, seulement indiquer à Python que le dossier est importable.

### 2. Organisation du système de tests
Nous utilisons **pytest**, la référence en matière de tests Python. 
*   **Dossier `tests/`** : Tous les fichiers de test (`test_*.py`) sont isolés dans ce dossier.
*   **Tests sur `file_loader.py`** : Nous avons créé des tests pour valider les fonctions de base :
    *   Chargement nominal (CSV et Excel).
    *   Détection automatique du séparateur et de l'encodage.
    *   Gestion des erreurs (fichier inexistant, format non supporté).

Résultats des tests sur file_loader
Les tests ont permis de valider plusieurs points clés :

Chargement CSV : Le fichier est bien lu et les colonnes détectées.
Chargement Excel : Support du format .xlsx intégré.
Gestion d'erreurs : Si on passe un fichier inexistant ou un format non supporté (ex: .txt), la fonction renvoie une erreur claire (FileNotFoundError ou ValueError) au lieu de planter le script silencieusement.
tests/test_file_loader.py::TestLoadFile::test_chargement_csv_nominal PASSED            [ 10%]
tests/test_file_loader.py::TestLoadFile::test_chargement_excel PASSED                  [ 20%]
tests/test_file_loader.py::TestLoadFile::test_detection_separateur_virgule PASSED      [ 30%]
tests/test_file_loader.py::TestLoadFileErrors::test_fichier_inexistant PASSED          [ 40%]
tests/test_file_loader.py::TestLoadFileErrors::test_format_non_soutenu PASSED          [ 50%]
tests/test_file_loader.py::TestLoadFileErrors::test_fichier_vide FAILED                [ 60%]
tests/test_file_loader.py::TestHelpers::test_detect_encoding_utf8 PASSED               [ 70%]
tests/test_file_loader.py::TestHelpers::test_detect_delimiter_semicolon PASSED         [ 80%]
tests/test_file_loader.py::TestHelpers::test_detect_delimiter_tab PASSED               [ 90%]
tests/test_file_loader.py::TestHelpers::test_detect_delimiter_default PASSED           [100%]


### 3. Résolution du bug sur les fichiers vides (`test_fichier_vide FAILED`)

**Problème initial :**
Le test échouait car `pd.read_csv()` levait une exception `EmptyDataError` non capturée dès que le fichier était vide (0 octet ou seulement des sauts de ligne). Cela bloquait le chargement.

**Correctif appliqué dans `file_loader.py` :**
1.  **Vérification proactive :** Ajout d'un contrôle `os.path.getsize(file_path) == 0` au tout début de la fonction pour détecter les fichiers vides instantanément.
2.  **Sécurité supplémentaire (try/except) :** Enveloppons l'appel à `pd.read_csv()` dans un bloc de capture spécifique :
    ```python
    try:
        df = pd.read_csv(file_path, sep=delimiter, encoding=encoding)
    except pd.errors.EmptyDataError:
        # Retourne un DataFrame vide proprement au lieu de planter
        return pd.DataFrame()
    ```

**Résultat final :** 
La fonction `load_file` ne plante plus. Si le fichier est vide, elle retourne calmement un objet `pd.DataFrame()` vide (qui fait 0 ligne et 0 colonne). Le test passe donc avec succès.

Cette étape est cruciale car elle marque le passage d'un "script qui fonctionne" à un "programme robuste et testé".

### 4. Résolution des bugs dans `cleaner_engine.py`
Nous avons corrigé plusieurs erreurs logiques persistantes :

*   **Bug sur la `median` (Médiane)** : Le `fillna` de la médiane pour les colonnes numériques n'était pas appliqué directement au DataFrame (`df_cleaned`). Nous avons rectifié en écrivant explicitement `df_cleaned[col] = df_cleaned[col].fillna(median_val)`.
*   **Bug sur le `mode` (Mode)** : La variable `col_mode` était parfois mal indentée ou non définie dans la boucle. Nous avons clarifié la logique pour que les colonnes de type "texte" (comme `'email'`) soient bien détectées, calculées via `.mode()[0]`, et ensuite remplies proprement avec `fillna`.
*   **Gestion des types (`StringDtype`)** : Une colonne contenant du texte dans un fichier moderne Pandas n'est pas toujours de type `'object'`. Nous avons ajusté la logique pour que les conversions numériques (comme `'10.5'` → `float`) se fassent correctement en utilisant `pd.to_numeric()`.

### 5. Premiers tests unitaires (`pytest`)
Nous avons commencé à intégrer des tests automatisés pour garantir qu'un changement de code ne "casse" pas les fonctionnalités existantes (régression).

**Résultats des tests sur le moteur de nettoyage (`cleaner_engine`)** :
*   **Clean Missing Values** ✅ : Les fonctions de remplissage par la médiane et le mode fonctionnent.
*   **Clean Types** ✅ : La détection automatique de colonnes à convertir (String → Numérique) est fiable.
*   **Clean Duplicates** ✅ : Le nombre de doublons supprimés est correct.

### 6. Impact sur l'architecture
Grâce aux tests, nous pouvons désormais refactoriser le code en toute sécurité. 
Le fichier `DEROULEMENT_PROJET.md` devient notre source de vérité technique, documentant chaque erreur rencontrée et sa solution.

### 7. Résolution des derniers bugs critiques dans cleaner_engine.py
Le pipeline fonctionnait globalement mais restait bloqué par 3 erreurs de type ("TypeErrors" ou "Logique"). Voici comment elles ont été résolues pour garantir la compatibilité avec les versions récentes de pandas (2.x et 3.x) :

Erreur sur les Types (
clean_types
) :

Problème : Int64 est le type nullable de pandas, mais le test cherchait np.int64. Le test plantait.
Solution : On a adapté la logique pour que les colonnes converties soient compatibles avec les vérifications de types standards tout en gardant la gestion des NaN.
Erreur sur les Doubles (
clean_duplicates
) :

Problème : Le test test_doublons_exact échouait (le DataFrame n'était pas modifié). C'était un problème d'ordre de nettoyage ou de copie du DataFrame.
Solution : On a sécurisé l'appel avec .copy() et vérifié que les colonnes étaient bien traitées avant de supprimer les doublons.
Erreur sur les Outliers (
clean_outliers
) :

Problème : Tentative d'écriture de valeurs à virgule (la borne IQR) dans des colonnes entières (int64), ce qui provoque une erreur LossySetitemError.
Solution : On convertit systématiquement les colonnes numériques en Float64 (qui accepte les NaN et les virgules) avant d'appliquer la logique IQR.

### 8. Stabilisation du pipeline et passage aux tests unitaires
Nous avons maintenant un ensemble de tests automatisés qui s'assurent que chaque brique du nettoyage fonctionne individuellement :

clean_empty_columns
 ✅ : Supprime les colonnes avec >95% de NaN.
clean_whitespace
 ✅ : Nettoie les espaces superflus sans casser les données.
clean_types
 ✅ : Transforme automatiquement les strings en numbers/dates quand c'est pertinent.
clean_duplicates
 ✅ : Gère correctement les lignes identiques.
clean_missing_values
 ✅ : Remplit les trous avec la médiane (pour les chiffres) ou le mode (pour le texte).


### 9. Tentative d'automatisation du nettoyage des outliers (boucle IQR itérative)

**Pourquoi cette fonctionnalité ?**
Le test de régression (`test_correction_iqr`) a révélé une faille critique de l'algorithme IQR simple sur les petits échantillons. 
*   *Le problème :* Si on a `[0, 1, 2, -999]`, Q1 est à 0 (ou 0.25). La borne inférieure devient $0 - 1.5 \times 1.2 = -1.8$. Or, **-999 est plus grand que -1.8**. L'algorithme pense donc que le "monstre" est valide.

**Ce qu'on essaie de faire :**
Au lieu d'appliquer les bornes une seule fois (One-pass), nous implémentons une fonction `clean_outliers_robust` qui :
1.  Calcule les bornes IQR actuelles.
2.  Repère si des valeurs se trouvent à l'extérieur de ces bornes.
3.  Si c'est le cas, **remplace** temporairement ces valeurs aberrantes par la borne la plus proche (winsorisation stricte).
4.  Recommence le calcul des bornes sur les nouvelles données "assainies".
5.  Boucle tant que toutes les valeurs sont comprises dans les bornes ou qu'on a atteint un seuil de sécurité (10 itérations max pour éviter les boucles infinies).

**État actuel :** En cours d'intégration avec des tests unitaires spécifiques (`test_iqr_multi_pass`).

---

## Étape 8 : Analyse de régression et correction des tests unitaires

### Contexte
En lançant les tests unitaires (`pytest`) pour valider l'architecture modulaire, nous avons constaté une régression inattendue. Le script principal (`main.py`) fonctionne car il utilise correctement le retour des fonctions (assignation), mais les fonctions isolées dans `cleaner_engine.py` posent problème dans un contexte de test pur.

### Résultats des tests (14 collectés)
- **11 Passed** ✅ (La logique globale et le pipeline d'intégration passent).
- **3 Failed** ❌ (Des anomalies persistantes dans les fonctions isolées).

### 1. Échec sur `clean_duplicates` (`test_doublons_exact`)
*   **Symptôme :** Le test s'attend à ce que la longueur du DataFrame passe de 4 à 3, mais elle reste à 4.
*   **Analyse technique :** Cette fonction est une "fonction pure" : elle retourne un tuple `(df_cleaned, count)` mais ne modifie pas le DataFrame d'origine. Dans `main.py`, l'appel est correct (`df = clean(df)[0]`), mais dans le test unitaire, il faut impérativement récupérer le premier élément du retour.
*   **Leçon :** L'intégration via `main.py` masque parfois les erreurs si on n'affecte pas bien la variable de retour.

### 2. Échec sur `clean_outliers` (`test_correction_iqr`)
*   **Symptôme :** La valeur aberrante `-999` est toujours présente dans le DataFrame nettoyé.
*   **Analyse technique :** L'algorithme IQR calcule des bornes basées sur Q1 et Q3. Avec un échantillon très petit (3 ou 4 points) et une outlier si extrême, les quartiles sont décalés. La borne inférieure calculée est parfois *plus basse* que -999 (ex: Q1=-600), rendant la valeur "valide" aux yeux du script.
*   **Piste de correction :** Ajouter un filtre préalable ou une logique de détection par écart-type si le DataFrame est trop petit pour être représentatif des quartiles.

### 3. Échec sur `clean_types` (`test_conversion_object_vers_numeric`)
*   **Symptôme :** Assertion échouée : `assert df['col'].dtype in [np.float64, np.int64]` retourne `Int64Dtype()`.
*   **Analyse technique :** Pandas 2.x utilise par défaut le type `Int64` (int nullable avec support des NaN) plutôt que le standard NumPy `np.int64`. Les données sont correctes, mais la vérification du test est trop rigide.
*   **Correction requise :** Utiliser `pd.api.types.is_integer_dtype()` ou vérifier que le type appartient aux types pandas (`Int64`, `Float64`) et non uniquement à NumPy.

Dans cette étape critique, nous avons identifié pourquoi certains tests échouaient malgré un pipeline fonctionnel en production. Les erreurs provenaient de la rigidité des fixtures de test et du comportement mathématique de pandas sur de petits échantillons.

### 4. Analyse de l'échec `test_doublons_exact`
*   **Symptôme :** Le test échouait car le DataFrame retenu contenait toujours 4 lignes.
*   **Analyse technique :** Le DataFrame initial (`dirty_df`) contenait des lignes avec le même ID (2) mais des noms différents ("Bob" et "Alice"). `drop_duplicates()` de pandas considère que ce sont deux lignes *distinctes* car elles ne sont pas identiques caractère pour caractère.
*   **Correctif appliqué :** 
    1. Nous avons créé une fixture dédiée (`dirty_df_with_exact_doublons`) contenant des répétitions parfaites de toutes les colonnes.
    2. Cette approche garantit que le test valide bien la logique de suppression de doublons sans être faussé par d'autres données.

### 5. Analyse de l'échec `test_correction_iqr`
*   **Symptôme :** La valeur -999 n'était pas supprimée/correctement traitée.
*   **Analyse technique :** 
    *   L'algorithme IQR nécessite des colonnes de type numérique pur (`np.number`). Si la présence de NaN ou d'espaces laisse pandas interpréter la colonne comme `object` (string), le calcul `quantile()` échoue silencieusement ou renvoie des valeurs par défaut incohérentes.
    *   De plus, sur un échantillon minuscule (ex: `[25, NaN, 35]`), l'IQR est très faible, rendant la borne inférieure (`Q1 - 1.5*IQR`) autour de 20. La valeur -999 étant bien en dessous, elle est détectée comme aberrante.
*   **Correctif appliqué :** 
    *   Ajout d'une étape explicite `pd.to_numeric(errors='coerce')` avant le calcul des bornes dans `clean_outliers`.
    *   Utilisation de `.fillna(median())` sur une copie temporaire du DataFrame pour calculer les quartiles sans perdre l'information des indices originaux.

---

## Étape 9 : Développement du module de profilage (`data_profiler`)

Dans cette étape, nous avons ajouté une brique essentielle au pipeline : **la phase d'inspection**. Avant même de penser à nettoyer, il est impératif de comprendre la structure et la qualité des données brutes.

### 1. Objectif du module `DataProfiler`
Créer un outil autonome (`src/data_profiler.py`) capable de produire un rapport structuré (format Markdown) sans dépendre de lourdes librairies tierces comme `ydata-profiling`. 

**Pourquoi "from scratch" ?**
*   **Légèreté :** Aucune dépendance externe complexe (matplotlib, scipy...) à gérer.
*   **Transparence :** Comprendre les statistiques de base (IQR, médiane, top-N) est une compétence clé d'analyste.
*   **Intégration facile :** Le rapport `.md` peut être consulté directement sur GitHub ou GitLab pour un partage rapide des findings.

### 2. Fonctionnalités implémentées
Le moteur `DataProfiler` analyse le DataFrame et génère les sections suivantes :

1.  **🧱 Vue d'ensemble** : Dimensions (Lignes/Colonnes) et poids estimé.
2.  **🏷️ Types de colonnes** : Identification précise des types (`Int64`, `Float64`, `object`...) pour anticiper les conversions nécessaires.
3.  **⚠️ Matrice de Qualité (NaN)** : 
    *   Calcul du compte et du pourcentage de valeurs manquantes par colonne.
    *   Focalisation sur les colonnes critiques (> 0%).
4.  **📈 Statistiques Numériques** :
    *   Utilisation de `describe()` pour les min, max, moyennes et percentiles (Q1, Q3).
    *   Cela permet d'identifier visuellement les outliers potentiels avant même le nettoyage.
5.  **🔤 Top Catégorielles** :
    *   Pour les colonnes texte/categ, on affiche le "Top 3" des valeurs les plus fréquentes (au lieu de tout lister, ce qui serait illisible).
6.  **👀 Aperçu Brut** : Les 5 premières lignes formatées en tableau Markdown.

### 3. Tests pytest
3 ok et 13 erreurs, essentiellement dues à un module absente mais nécessaire : Tabulate
après installation de ce module, 5 KO sur 16 : un même problème car je faisais une opération sur un Tuple
après correction de cette anomalie, une nouvelle mais unique erreur est apparue suite un correctif dans le fichier de tests
après mise à jour du fichier de tests par l'agent testeur, tous les tests sont OK
je corrige néanmoins les alertes de Pandas

### 4. Intégration au pipeline
Le flux de travail devient maintenant :
1.  **Chargement** (`file_loader`)
2.  **Profiling** (`data_profiler`) ➡️ *Nouveau* : Génère `data/processed/report_profile.md`
3.  **Nettoyage** (`cleaner_engine`)
4.  **Sauvegarde & Rapport Final** (`cleaner_logger`)

**Défis techniques résolus aujourd'hui :**
*   **Gestion des chemins relatifs :** Utilisation de `Path(__file__).parent.parent` pour que le script fonctionne depuis n'importe quel répertoire (racine ou sous-dossier `src/`).
*   **Correction des imports dynamiques :** Ajout de `sys.path.insert(0, ...)` dans le fichier orchestrator pour éviter les `ModuleNotFoundError` quand le script est lancé depuis l'intérieur d'un package.

### 4. Préparer le terrain pour les futures alertes
La classe `DataProfiler` inclut désormais une méthode réservée (`detect_quality_issues`). Cette structure est prête à accueillir nos prochaines règles métier (ex: "Si une colonne 'Age' a des valeurs < 0, alerter l'utilisateur").

---

## Étape 10 : Renforcement de la robustesse et fiabilisation par les tests unitaires

Dans cette phase, l'objectif est passé de "faire fonctionner le code" à "garantir qu'il ne cassera jamais lors d'une mise à jour". Nous avons affronté des problèmes complexes liés aux types de données et à la structure même du projet.

### 1. L'enjeu de la robustesse des données (handling edge cases)
Les tests unitaires ont révélé que notre `CleanLogger` était trop "optimiste". Il supposait que les statistiques fournies étaient toujours parfaites. Nous avons corrigé deux vulnérabilités majeures :
* **Le piège du `NoneType`** : Si une statistique (ex: `empty_cols_dropped`) était absente ou `None`, le script plantait avec une `TypeError`. Nous avons implémenté l'utilisation de `.get(key, default)` pour garantir que le rapport se génère même avec des données incomplètes.
* **L'absence de clés (`KeyError`)** : Si le dictionnaire `stats` ne contenait pas toutes les clés attendues (cas fréquent lors de nettoyages partiels), le processus s'arrêtait. Nous avons sécurisé chaque accès aux statistiques pour assurer la continuité du pipeline.

### 3. Vers un environnement de test professionnel
* **Configuration Pytest** : Utilisation de `pyproject.toml` avec la configuration `pythonpath = ["."]` pour permettre à `pytest` de découvrir les modules `src/` sans manipulation manuelle du `sys.path`.
* **Résultat final** : Un passage de **13 tests réussis / 2 échecs** à un score parfait de **15/15 tests réussis**.

### Résumé des compétences démontrées dans cette étape
* **Debug avancé** : Capacité à identifier et résoudre des `TypeError` et `KeyError` complexes.
* **Engineering de test** : Mise en place d'une suite de tests couvrant les cas nominaux, les cas limites (données vides, types incohérents) et les erreurs structurelles.
* **Qualité Logicielle** : Transformation d'un script "fragile" en un module industriel "robuste".

---

## Étape 11 : Professionnalisation du reporting et sécurisation de l'audit via `CleanerReporter`

Après avoir stabilisé le moteur de nettoyage (`cleaner_engine`) et les tests unitaires, l'objectif est passé de la simple transformation de données à la **création d'une preuve d'audit**. Un pipeline performant ne sert à rien si l'utilisateur final (le Data Analyst ou le métier) ne peut pas auditer les transformations effectuées.

### 1. Le défi : transformer des logs techniques en un rapport métier
Jusqu'ici, la visibilité sur le nettoyage reposait sur des sorties textuelles dans la console, volatiles et difficiles à archiver. Le défi était de créer une classe `CleanerReporter` capable de transformer des objets complexes (`DataProfiler` et `CleanLogger`) en un document Markdown structuré, persistant et lisible par des non-développeurs.

### 2. Implémentation de la couche d'audit (audit trail)
Le module a été conçu pour extraire et structurer l'information selon trois piliers critiques :
* **Métadonnées de traçabilité** : Extraction automatique du chemin absolu du fichier source et horodatage précis pour garantir l'origine de la donnée.
* **Indicateurs de performance (KPIs)** : Calcul des ratios de transformation (ex: perte de lignes, suppression de colonnes) sous forme de tableau comparatif "Avant vs Après".
* **Journal d'exécution détaillé** : Transformation du log d'opérations en un tableau Markdown structuré, permettant de vérifier colonne par colonne l'action appliquée et son résultat.

### 3. Ingénierie de la robustesse (programmation défensive)
La création de ce module a nécessité l'application de concepts avancés pour garantir que le reporting ne devienne pas un point de rupture du pipeline :

* **Sécurisation des données (Protection contre l'injection Markdown)** : 
  Un problème critique a été identifié : les données sources peuvent contenir des caractères réservés au formatage Markdown (comme `|`, `*` ou `_`). Si une colonne nommée `Prix | Promo` est traitée, le caractère `|` risque de briser la structure du tableau dans le rapport final. J'ai donc implémenté un mécanisme d'échappement systématique (`replace('|', '\\|')`) pour garantir l'intégrité visuelle du document, peu importe la "saleté" des données sources.

* **Gestion de l'incertitude des interfaces (Interface Resilience)** : 
  Le `CleanerReporter` interagit avec des modules dont la structure peut varier (`profiler` et `logger`). Pour éviter que le pipeline ne plante en cas de donnée manquante, j'ai implémenté :
    * **L'accès sécurisé** via l'utilisation de `.get()` pour les dictionnaires, garantissant des valeurs par défaut (ex: `'N/A'`) au lieu d'une `KeyError`.
    * **La validation de type** (`isinstance`) avant tout traitement, pour prévenir les erreurs de manipulation sur des structures inattendues.
    * **Le blocage des exceptions critiques** : Utilisation de blocs `try/except AttributeError` pour capturer les erreurs si un module ne renvoie pas l'information attendue (ex: une colonne manquante dans le profilage).

### 4. Compétences techniques mobilisées
* **Python Avancé** : Manipulation de structures de données complexes et utilisation de `pathlib` pour une gestion moderne des chemins de fichiers.
* **Sécurité des données** : Mise en place d'un mécanisme de nettoyage (sanitization) pour prévenir la corruption du format de sortie.
* **Design Pattern "Reporter"** : Séparation stricte entre la logique métier (Engine) et la couche de présentation (Reporter), respectant le principe de responsabilité unique (SRP).

---

## Étape 12 : Intégration du module de reporting au pipeline global

Cette étape a consisté à orchestrer les modules existants (`file_loader`, `data_profiler`, `cleaner_engine` et `cleaner_reporter`) pour former un pipeline de données complet et automatisé.

### 1. Problématique : l'accès aux données éphémères
Le moteur de nettoyage (`cleaner_engine`) génère des statistiques cruciales (nombre de doublons supprimés, colonnes transformées, etc.) sous forme de dictionnaires temporaires durant l'exécution du script `main.py`. Le module `cleaner_reporter`, quant à lui, est conçu pour lire des objets persistants (`DataProfiler` et `Logger`). 

**Le défi :** Comment transmettre les statistiques de nettoyage (volatiles) au moteur de rapportage sans casser la séparation des responsabilités entre les modules ?

### 2. Méthode de résolution : le pattern "adapter"
Pour résoudre ce problème d'interface, une fonction utilitaire `generate_enhanced_report` a été implémentée au niveau du module `src/cleaner_reporter.py`. 

**Fonctionnement technique :**
* **Rôle d'adaptateur :** Cette fonction agit comme une couche intermédiaire qui prend en entrée les objets de structure (le profiler et le logger) ainsi que le dictionnaire de statistiques brutes (`stats`) issu du nettoyage.
* **Encapsulation :** Elle gère l'instanciation du `CleanerReporter` et l'injection des paramètres complexes, évitant ainsi de polluer la logique métier de `main.py` avec des détails d'implémentation liés au reporting.
* **Standardisation du rendu :** Elle assure que les statistiques de transformation (ex: nombre de lignes supprimées) sont formatées selon le même standard Markdown que les résultats du profilage initial, garantant l'homogénéité des rapports produits.

### 3. Défis d'orchestration et robustesse
L'intégration a nécessité la résolution de deux points critiques :
* **Gestion de la persistance des chemins :** Utilisation de `pathlib` pour garantir que le pipeline puisse localiser les dossiers `data/reports` et `data/processed` quel que soit l'endroit d'où le script est lancé (racine ou dossier `src/`).
* **Continuité du flux (Pipeline Resilience) :** Mise en place de blocs `try/except` spécifiques autour de la génération du rapport final. L'objectif est de garantir que si une erreur survient lors de la création du document Markdown (ex: erreur d'écriture), le processus de sauvegarde des données nettoyées (`dataset_nettoye.csv`) ne soit pas interrompu.

### 4. État de l'architecture finale
Le pipeline suit désormais un flux de données unidirectionnel et structuré :
`Fichier Brut` $\rightarrow$ `Détection (Encodage/Séparateur)` $\rightarrow$ `Profilage Initial` $\rightarrow$ `Nettoyage (Transformations)` $\rightarrow$ `Sauvegarde du Dataset` $\rightarrow$ `Génération du Rapport d'Audit`.

---

## Étape 13 : Intelligence du moteur numérique, auditabilité et non-régression

Cette étape cruciale a transformé le pipeline d'un outil de nettoyage simple en un système d'audit professionnel, capable de traiter des formats complexes (monétaires) et de corriger les erreurs structurelles introduites par le chargement initial.

### 1. Intelligence du moteur numérique (traitement des formats monétaires)
L'un des plus grands défis était la présence de données numériques "sales" qui empêchaient toute conversion (ex: `"1 200,50 €"`). Le moteur ne reconnaissait pas ces valeurs comme des nombres à cause des symboles et des séparateurs hétérogènes.

* **Détection et Nettoyage intelligent** : Mise en place d'une logique capable de :
    * Identifier les colonnes contenant des symboles monétaires (`€`, `$`, `£`).
    * Gérer la dualité des séparateurs (conversion automatique de la virgule `,` en point `.` pour le standard Python).
    * Supprimer les espaces de milliers (ex: `"1 000"` $\rightarrow$ `"1000"`) et les caractères parasites.
* **Résultat** : Une augmentation drastique du taux de succès de la conversion `object -> float` sur des colonnes critiques comme `montant_total`.

### 2. Résolution du "pandas type trap" (le problème des entiers déguisés)
Une problématique majeure a été identifiée sur les colonnes de comptage (`nb_nuits`, `nb_personnes`).

* **Le Problème** : À cause de la présence de valeurs manquantes (`NaN`) ou de formats texte (`"7.0"`), Pandas charge ces colonnes en `float64`. Cela altère l'intégrité sémantique (on traite des décimaux là où nous avons des quantités entières).
* **La Solution technique** : Implémentation d'une étape de **`fix_numeric_types`** intégrée au pipeline.
    * **Détection** : Le module repère les colonnes `float64` dont la partie décimale est systématiquement nulle (ex: `1.0`, `2.0`).
    * **Correction** : Conversion vers le type **`Int64` (Nullable Integer)** de Pandas. Ce type moderne conserve la nature entière de la donnée tout en supportant les valeurs manquantes (`<NA>`) sans forcer le retour à un format `float`.

### 3. Amélioration de l'auditabilité du rapport (le "comment" et le "combien")
L'objectif était de passer d'une statistique brute à une documentation qualitative pour la reproductibilité.

* **Refonte de la structure des données (`cleaner_engine.py`)** : Passage d'une chaîne descriptive à un objet structuré pour `clean_missing_values` :
    * **Avant :** `{'colonne': 'fill_mode_valeur'}` (impossible de calculer le total global).
    * **Après :** `{'colonne': {'count': 15, 'method': 'fill_mode_valeur'}}` (permet un audit précis des volumes traités).
* **Évolution du reporting (`cleaner_reporter.py`)** : Le rapport Markdown affiche désormais un véritable journal d'audit avec le nom de la colonne, le nombre de cellules traitées (**Combien**) et la méthode utilisée (**Comment**).

### 4. Résultats
* **Intelligence métier** : Capacité à traiter des formats monétaires complexes sans intervention manuelle.
* **Intégrité sémantique restaurée** : Les colonnes de comptage retrouvent leur nature d'entiers, même avec des valeurs vides.
* **Auditabilité totale** : Le rapport devient un document de traçabilité permettant de vérifier chaque transformation effectuée sur le dataset.

Suite aux optimisations apportées au `cleaner_engine` (notamment sur la gestion des types et des outliers) et au `cleaner_reporter`, il était impératif de valider que ces changements n'ont pas introduit de régressions dans les modules existants.

### 5. Objectif de la phase de test
L'objectif était de s'assurer que les modifications structurelles (passage de `nb_doublons` à `duplicates_count`, refonte des types Pandas) n'aient pas cassé les assertions des tests unitaires déjà en place et que le pipeline d'intégration reste fonctionnel.

### 6. Problématiques rencontrées et résolutions techniques

Le passage des tests a mis en lumière trois points de friction liés aux évolutions du code :

* **Désalignement des clés (Regression sur `cleaner_reporter`)** : 
  Le changement de nom de la clé `'nb_doublons'` en `'duplicates_count'` dans le moteur de nettoyage a rendu les tests du rapporteur obsolètes. Les tests échouaient car ils cherchaient une clé qui n'existait plus. 
  * **Résolution** : Mise à jour des fichiers de tests pour s'aligner sur la nouvelle nomenclature du moteur.

* **Conflits de types (Regression sur `clean_outliers`)** : 
  L'introduction de la conversion vers le type `Int64` (nullable) a provo͞te une erreur lors du calcul des outliers. Le moteur tentait d'insérer une valeur décimale (borne IQR) dans une colonne typée en entier, provoant un `TypeError`.
  * **Résance** : Adaptation de la logique pour assurer que les colonnes sont traitées avec une précision suffisante avant l'application des bornes.

* **Erreurs d'importation (`ImportError`)** : 
  La refonte modulaire a entraîné des échecs d'importation dans `test_cleaner_engine.py` (notamment sur la fonction `clean_outliers` qui avait été renommée en `clip_outliers`).
  * **Résolution** : Réalignement des imports dans les fichiers de tests.

### 7. Résultat final
Après correction des tests pour les mettre en adéquation avec la nouvelle structure du code, la suite de tests `pytest` est passée avec un score de succès total sur l'ensemble des modules (`DataProfiler`, `CleanerEngine`, `CleanerReporter`). Le pipeline est désormais stabilisé et prêt pour l'utilisation.

---

## Étape 14 : Profilage multidimensionnel : de l'analyse de colonnes à l'audit de structure

Dans cette phase d'évolution majeure, nous avons transcendé le rôle du `DataProfiler` (simple lecteur de structure) pour en faire un véritable outil d'audit de qualité de données complet, capable d'inspecter la santé des colonnes **et** la complétude des lignes.

### 1. Analyse de la qualité structurelle des lignes (row integrity)
Le module a acquis une nouvelle dimension : l'inspection de la densité informationnelle par enregistrement.
* **Détection de la vacuité** : Calcul automatique du pourcentage de valeurs manquantes par ligne.
* **Classification par criticité** : 
    * **Niveau Critique (>90% vide)** : Identification des lignes "fantômes" à supprimer pour nettoyer le bruit.
    * **Niveau Alerte (30-90% vide)** : Identification des lignes nécessitant une inspection manuelle.
* **Reporting granulaire et intelligent** : 
    * Pour éviter l'infobésité, le module regroupe les alertes par **pourcentage exact de valeurs manquantes**, permettant de voir les motifs de structure récurrents.
    * Implémentation d'une **sécurité d'affichage** : limitation à 10 index maximum par groupe pour garantir la lisibilité du rapport Markdown, tout en indiquant le nombre total de lignes impactées.

### 2. Analyse approfondie des colonnes (column intelligence)
Le moteur continue d'affiner l'audit des données textuelles et numériques selon quatre piliers :
* **Cardinalité Avancée** : Calcul de la cardinalité absolue et relative (ratio par rapport au volume total).
* **Indicateur de Remplissage (Sparsity Ratio)** : Intégration du taux de remplissage spécifique aux colonnes catégorielles.
* **Analyse de la Variance (Skewness de Fréquence)** : Implémentation d'un indicateur de dominance. Si une catégorie représente plus de 90% des données, le module génère une alerte visuelle (⚠️) signalant une faible variance.
* **Audit de Conformité Syntaxique** : Détection automatique des anomalies de formatage (espaces traînants, hétérogénéité de casse).

### 3. Standardisation terminologique et présentation
* **Approche Bilingue Professionnelle** : Pour répondre aux standards internationaux, nous avons adopté une nomenclature **"Terme Anglais | Traduction Française"** (*ex: "Sparsity Ratio | Taux de remplissage"*).
* **Stratégie d'Affichage Dynamique** : Pour les colonnes à forte cardinalité, le module se concentre sur le **Top 5 des catégories** les plus représentatives avec leur poids relatif (%), évitant ainsi de surcharger le rapport.

### 4. Impact sur la fiabilité du pipeline
Le `DataProfiler` ne se contente plus de décrire ce qui est là ; il prévient l'analyste des risques structurels avant même que le moteur de nettoyage (`cleaner_engine`) ne soit lancé. C'est le passage d'un mode **"Nettoyage aveugle"** à un mode **"Audit & Action"**.

---

## Étape 15 : Évolution vers l'exploration multimodale : rapport HTML autonome & visual analytics

Dans cette phase d'évolution majeure, le projet a franchi un nouveau palier en passant d'un pipeline purement textuel à une interface de pilotage interactive et visuelle. L'objectif était de doter l'utilisateur final d'un outil capable de présenter des analyses riches sans aucune contrainte de dépendance de fichiers.

### 1. Introduction de l'interactivité (human-in-the-loop)
Le pipeline n'est plus une séquence figée. Nous avons introduit une couche d'interaction au point d'entrée (`main.py`) permettant un choix stratégique lors de l'exécution :
* **Mode Standard (Markdown)** : Pour une documentation technique rapide, légère et optimisée pour le versioning (Git/GitHub).
* **Mode Exploratoire (HTML)** : Pour une analyse riche, visuelle, destinée à être partagée avec des parties prenantes non-techniques.

### 2. Innovation technique : le rapport HTML "self-contained"
Le plus grand défi technique de cette étape était la génération d'un rapport HTML qui soit **totalement autonome**. 

**La problématique initiale** : Traditionnellement, un rapport HTML pointe vers des images stockées dans un dossier `/graphs`. Cela crée une dépendance : si l'on déplace le fichier `.html` sans son dossier d'images, le rapport devient "aveugle".

**La solution implémentée (Embedding via Base64)** : 
Pour garantir que le rapport soit portable et s'affiche parfaitement partout (e-mail, navigateur local, cloud), nous avons implémenté une technique d'encodage avancé :
* **Capture en mémoire** : Les graphiques (Histogrammes, Boxplots, Barplots) sont générés par `Matplotlib/Seaborn` et interceptés dans un buffer mémoire (`BytesIO`).
* **Encodage Base64** : Chaque image est convertie en une chaîne de caractères textuelle (Base64) injectée directement dans la balise `<img src="data:image/png;base64,...">` du code HTML.
* **Résultat** : Le fichier `.html` final contient l'intégralité des données et des visuels. Il suffit d'un seul fichier pour transporter toute l'analyse.

### 3. Diversification de l'analyse visuelle
L'intégration réussie des graphiques permet désormais une exploration multidimensionnelle :
* **Distribution Numérique** : Utilisation de `Histplots` (avec KDE) pour visualiser la densité et les modes de distribution.
* **Détection visuelle des Outliers** : Utilisation de `Boxplots` pour corroborer les calculs statistiques de l'algorithme IQR par une preuve visuelle immédiat.
* **Analyse de Fréquence** : `Barplots` sur les colonnes catégorielles pour identifier instantanément les catégories dominantes et la structure du dataset.

### 4. Défis d'ingénierie rencontrés
* **Gestion de la charge mémoire** : L'encodage d'images dans le texte augmente la taille du fichier HTML. Nous avons dû optimener la résolution des graphiques pour maintenir un équilibre entre clarté visuelle et légèreté du document.
* **Robustesse du pipeline de rendu** : Mise en place de blocs `try/except` autour de chaque génération de graphique pour garantir que, même si une colonne pose problème (ex: trop de données), le reste du rapport HTML est généré sans interruption.

### Résumé de la valeur ajoutée
Le projet quitte définitivement le stade de "script de nettoyage" pour devenir un **système d'audit décisionnel et visuel**. L'utilisateur ne subit plus un processus automatique ; il pilote une investigation complète, capable de produire des livrables professionnels, autonomes et prêts à être partagés en entreprise.

---

## Étape 16 : Vers un nettoyage piloté par l'expert (human-in-the-loop)

Dans cette phase, le projet a connu une mutation philosophique majeure. Nous sommes passés d'un automate de nettoyage "boîte noire" à un **assistant décisionnel interactif**. L'objectif n'est plus que la machine décide seule, mais qu'elle fournisse l'intelligence nécessaire pour que l'analyste valide ou rejette chaque transformation critique.

### 1. Le passage du mode "batch" au mode "piloté"
Jusqu'alors, le pipeline exécutait une séquence de tâches prédéfinies sans solliciter l'utilisateur. Si une erreur de logique survenait (ex: suppression trop agressive d'outliers), elle était définitive dans le fichier de sortie.

Nous avons introduit une couche d'**interactivité décisionnelle** à deux points stratégiques du pipeline :
* **Gestion des Valeurs Manquantes** : Avant le remplissage, l'analyste est informé du volume et de la répartition des trous dans les données. Il peut alors décider de maintenir la structure brute ou d'autoriser le comblement (médiane/mode).
* **Gestion des Outliers** : Le système ne se contente plus de "clipper" les valeurs ; il présente un audit préalable des colonnes impactées, laissant le choix final à l'expert.

### 2. L'intelligence contextuelle au service de l'analyste
L'interaction n'est pas une simple boîte de dialogue ; elle est **contextualisée** grâce aux résultats du `DataProfiler` :
* **Aide à la décision (Decision Support)** : Au lieu d'un message générique, le script présente des faits précis (ex: *"150 valeurs manquantes détectées dans la colonne 'Prix'"*). Cela transforme l'utilisateur de simple spectateur en décideur éclairé.
* **Gestion des options par défaut** : Pour préserver la fluidité du workflow, nous avons implémenté des réponses par défaut (ex: `[y/n, entrée par défaut 'y']`). Cela permet une exécution rapide pour les cas standards, tout en offrant un contrôle total pour les cas complexes.

### 3. Transformation de la responsabilité : de la machine à l'analyste
Cette évolution change radicalement la nature du projet :
* **Ancien paradigcu** : Le script est un agent autonome qui "fait le travail". Risque de perte de traçabilité métier.
* **Nouveau paradigme** : Le script est un **outil d'aide à la décision (Decision Support System)**. L'analyste reste le maître d'œuvre, tandis que le code s'occupe de l'exécution technique et de la surveillance des anomalies.

### 4. Impact sur la fiabilité du pipeline
L'introduction de ces validations manuelles a renforcé la **résilience** du projet :
* **Réduction du risque de régression métier** : On évite les transformations qui, bien que statistiquement correctes (ex: imputer une médiane), pourraient être sémantiquement fausses dans un contexte métier spécifique.
* **Auditabilité humaine** : Chaque décision prise durant l'exécution est capturée et peut être documentée, renforçant la chaîne de confiance entre la donnée brute et le rapport final.

---

## Étape 17 : Uniformisation de la casse et standardisation textuelle

Dans cette phase, nous avons intégré une nouvelle brique de nettoyage stratégique pour traiter l'une des sources de bruit les plus insidieuses dans les données catégorielles : l'incohérence de casse (ex: "Paris", "PARIS", "paris").

### 1. Le défi : la fragmentation des catégories
Dans les jeux de données réels, les colonnes textuelles souffrent souvent d'une standardisation défaillante. Pour un analyste, cela crée deux problèmes maj :
* **Explosion de la cardinalité** : Une même catégorie est comptée comme plusieurs entités distinctes, faussant les analyses de fréquence (Top-N).
* **Échec des jointures et filtres** : Les recherches ou les regroupements échouent si la casse n'est pas rigoureusement identique.

### 2. Implémentation d'un moteur de normalisation intelligent
L'enjeu n'était pas simplement d'appliquer un `.lower()` massif, ce qui aurait été destructeur pour certains types de données. Nous avons conçu une fonction `clean_case_sensitivity()` dotée d'une intelligence contextuelle :

* **Protection des identifiants (Heuristique ID-like)** : Le moteur analyse l'échantillon de chaque colonne textuelle. Si une colonne présente un mélange de chiffres et de lettres (ex: `"R43873"`), elle est automatiquement exclue du processus de normalisation pour préserver l'intégrité des clés primaires ou des codes clients.
* **Filtrage sémantique** : Le moteur vérunifie la présence de caractères alphabétiques avant d'agir, évitant ainsi des opérations inutiles sur des colonnes purement numériques ou symboliques.
* **Préservation des valeurs manquantes** : Une gestion rigoureuse via un masque booléen (`notna()`) garantit que les `NaN` ne sont pas transformés en chaînes de caractères `"nan"`, préservant ainsi la structure propre du DataFrame.

### 3. Intégration au pipeline et traçabilité
L'intégration a suivi les principes de robustesse établis précédemment :
* **Mise à jour des statistiques** : Le `CleanLogger` et le `CleanerReporter` ont été enrichis pour compter précisément le nombre de colonnes impactées et le volume de modifications effectuées.
* **Ordre d'exécution optimisé** : Cette étape est placée stratégiquement *après* le nettoyage des espaces (`clean_whitespace`) mais *avant* la détection des doublons, car une casse uniforme est indispensable pour que `drop_duplicates()` identifie correctement les lignes identiques.

### 4. Impact sur la qualité du dataset
Cette améliation transforme radicalement la fiabilité de l'analyse :
* **Fiabilité du regroupement (Grouping)** : Les statistiques par région ou par catégorie deviennent exactes et sans doublons fantômes.
* **Auditabilité renforcée** : Le rapport final documente désormais explicitement l'effort de standardisation textuelle, offrant une preuve de la qualité du nettoyage effectué.

---

## Étape 18 : Résolution de la fragilité du reporting et sécurisation des types (bug fix & robustness)

Cette étape a marqué un tournant critique dans le projet : le passage d'un système qui "fonctionne sous conditions" à un système capable de gérer l'incertitude et les choix de l'utilisateur sans interruption brutale.

### 1. Analyse de la régression : le paradoxe du "type error"
Lors de l'introduction de l'interactivité (permettant à l'utilisateur d'ignorer certains nettoyages), une erreur fatale est apparue dans le pipeline : `unsupported operand type(s) for +: 'int' and 'str'`.

* **L'origine du problème** : Dans la phase de décision, si l'utilisateur choisissait de ne pas traiter les valeurs aberrantes (outliers), le moteur stockait une chaîne descriptive (`'Corrections ignorées...'`) dans un dictionnaire censé contenir des entiers.
* **La rupture de contrat** : Le module `CleanLogger`, qui générait le résumé textuel, tentait d'agréger (sommer) toutes les valeurs du dictionnaire pour afficher un total. L'addition d'un entier (le nombre d'outliers trouvés) et d'une chaîne de caractères (le message d'annulation) provoquait l'arrêt immédiat du programme.

### 2. Stratégie de résolution : standardisation et programmation défensive
Pour résoudre ce problème, nous n'avons pas seulement corrigé un bug, nous avons refondu la logique de communication entre le moteur (`Engine`) et les rapports (`Logger/Reporter`).

#### A. Refonte du protocole de stockage (contract-based programming)
Nous avons abandonné l'utilisation de messages textuels au sein des structures numériques. Désormais, le moteur utilise un format structuré et prévisible :
* **Pour les cas nominaux** : `{'colonne_A': 10, 'colonne_B': 5}` (uniquement des entiers).
* **Pour les cas d'annulation** : `{'ignored': True}`.
Cette approche garantit que la structure de donnée est toujours prévisible pour les modules suivants.

#### B. Implémentation de l'audit sécurisé dans le logger
Le `CleanLogger` a été doté d'une logique de "vérification de type" (Type Checking) avant toute opération arithmétique :
* **Analyse du contenu** : Avant de sommer, le logger vérifie si la clé `'ignored'` est présente ou si les valeurs sont numériques.
* **Fallback robuste** : En cas de structure inattendue, le système utilise un bloc `try/except` pour afficher `"Données non valides"` au lieu de planter, garantant ainsi que le pipeline termine toujours son exécution et sauvegarde les données.

#### C. Uniformisation du reporting (Markdown & terminal)
Nous avons synchronisé les deux modes de rapportage :
* **Rapport Terminal (Textuel)** : Affiche désormais clairement *"Traitement ignoré par l'utilisateur"* au lieu d'un nombre erroné ou d'une erreur système.
* **Rapport Markdown (Audit)** : Le tableau détaillé est capable de switcher entre un mode "comptable" (affichage des quantités) et un mode "informatif" (affichage du motif d'annulation), assurant une traçabilité sans faille pour l'auditeur.

### 3. Impact sur la maturité du projet
Cette étape a apporté trois bénéfices majeurs :
1. **Fiabilité (Reliability)** : Le pipeline est désormais "crash-proof" face aux choix utilisateur imprévus.
2. **Transparence (Observability)** : L'utilisateur a une visibilité totale non seulement sur ce qui a été fait, mais aussi sur ce qui a été délibérément écarté.
3. **Maintenabilité** : La séparation stricte entre les données numériques et les messages de statut facilite l'ajout de nouvelles fonctionnalités sans risque de régression.

---

## Étape 19 : Extension de l'intelligence de lecture : support multi-format & détection de structure (JSON/JSONL)

Dans cette phase d'évolution, le pipeline a franchi une étape majeure en brisant la barrière du format CSV. L'objectif était d'augmenter la polyvalence du `file_loader` pour qu'il puisse absorber des flux de données modernes (APIs, logs, NoSQL) sans intervention humaine.

### 1. Le défi de l'hétérogénéité des sources
Jusqu'alors, le pipeline était optimisé pour les structures tabulaires classiques (lignes/colonnes). L'introduction du format **JSON** (objet unique) et **JSONL** (flux de lignes) posait deux problèmes critiques :
* **Complexité structurelle** : Un JSON n'est pas qu'une simple liste ; il peut être un d'objet complexe où les données utiles sont cachées sous une clé spécifique (ex: `{"metadata": ..., "data": [...]}`).
* **Détection aveugle** : Comment savoir si un fichier sans extension est un CSV mal formaté ou un flux JSONL sans changer la logique de l'utilisateur ?

### 2. Implémentation de l'intelligence de chargement
Nous avons transformé le `file_loader` en un moteur de détection multi-couches :

* **L'architecture de secours (Fallback Strategy) avec analyse de signature** : 
    * Si l'extension est explicite (`.json`, `.jsonl`), le moteur utilise des chargeurs spécialisés.
    * Si l'extension est inconnue ou absente, le moteur active un **scanner de structure** qui analyse les premiers octets du fichier pour identifier les signatures `{` ou `[` caractéristiques du format JSON.
* **Le moteur `_load_json_manual` (Deep Discovery & Unwrapping)** : 
    Pour pallier les limites de `pd.read_json()` face à des structures non-linéaires, nous avons implémenté une logique de "dépliage". Le moteur parcourt les niveaux du dictionnaire pour extraire la première liste d'objets valide, permettant de transformer des JSON complexes (dictionnaires contenant des listes) en un format tabulaire exploitable par Pandas.
* **Le module `_load_jsonl` (Stream Processing)** : 
    Implémentation d'un lecteur de lignes robuste capable de traiter des fichiers massifs (JSON Lines) en ignorant les lignes vides ou corrompues, garantant que le pipeline ne s'arrête pas à la première erreur de syntaxe rencontrée dans un flux de logs.

### 3. Résilience et robustesse (error containment)
L'intégration de nouveaux formats a nécessité un renforcement des mécanismes de protection :
* **Validation de type** : Utilisation de `isinstance(data, list)` et `isinstance(data, dict)` pour éviter les crashs lors de la transformation en DataFrame.
* **Isolation des erreurs** : Le processus de détection automatique est encapsulé dans des blocs `try/except` pour s'assurer que si la détection échoue, le système retourne une erreur métier explicite (ValueError) plutôt qu'une exception Python obscure.

### 4. Impact sur la valeur métier
Le pipeline est passé d'un outil de **nettoyage de fichiers** à un outil de **consommation de données**. L'analyste peut désormais injecter des sorties d'APIs, des exports de bases de données NoSQL ou des fichiers de configuration directement dans le workflow de nettoyage, sans aucune modification du code source.

---

## Étape 20 : Optimisation de l'efficacité par le nettoyage ciblé et l'intelligence contextuelle

Dans cette phase, le pipeline a évolué d'un mode de traitement "aveugle" vers un mode de traitement "piloté par la donnée". L'objectif était de réduire la charge computationnelle et de limiter les risques de transformations inutiles en utilisant les connaissances du module de profilage.

### 1. Le problème : le coût du traitement global
Jusqu'alors, le moteur de nettoyage (`clean_case_sensitivity`) analysait systématiquement toutes les colonnes de type `object` ou `string` du DataFrame. Sur des datasets massifs (millions de lignes) comportant des centaines de colonnes, ce scan global présente deux inconvénients :
* **Surcoût computationnel** : Tester chaque colonne pour détecter des variations de casse consomme des ressources CPU et de la mémoire inutilement si la colonne est déjà propre.
* **Risque de régression** : Appliquer des transformations textuelles sur des colonnes qui ne nécessitent aucun traitement augmente la surface d'erreur (ex: altération accidentelle de chaînes complexes).

### 2. La solution : l'utilisation du profilage comme guide de nettoyage
Nous avons implémenté un mécanisme de **filtrage intelligent** en utilisant les résultats du `DataProfiler` comme une "carte routière" pour le `cleaner_engine`.

* **Identification des cibles (Targeting)** : 
    Le pipeline extrait désormais, lors de la phase de profilage, la liste précise des colonnes présentant des anomalies de format (spécifiquement les `"Variations de casse"` et les `"Espaces"` détectés par le moteur d'analyse).
* **Injection de contexte** : 
    Cette liste de colonnes cibles est transmise au moteur de nettoyage via le paramètre `target_columns`. 
* **Exécution sélective** : 
    Si des cibles sont identifiées, le moteur de nettoyage se concentre exclusivement sur celles-ci. Si aucune anomalie n'est détectée, le moteur peut soit s'arrêter, soit passer en mode global par sécurité (fallback).

### 3. Avantages techniques et métier
* **Performance accrue** : Réduction drastique du nombre d'itérations sur les colonnes de type `object` qui ne présentent aucun problème de formatage.
* **Précision chirurgicale** : Le nettoyage n'est appliqué que là où le besoin est prouvé par l'audit initial, garantissant une intégrité maximale des données non impactées.
* **Synergie entre modules** : Renforcement de l'interdépendance positive entre le `DataProfiler` (l'observateur) et le `cleaner_engine` (l'acteur), transformant le pipeline en un système intelligent et réactif.

### 4. Résultat
Le pipeline est devenu **"context-aware"** (conscient de son contexte). Il ne se contente plus d'exécuter une liste de tâches, il adapte sa stratégie de travail en fonction de la qualité réelle des données qu'il est chargé de traiter.

---

## Étape 21 : Refactoring de l'orchestrateur : vers une modularité totale et une haute maintenabilité

Dans cette phase, l'objectif était de transformer le point d'entrée du projet pour atteindre un niveau de maturité logicielle professionnelle, en appliquant les principes de séparation des responsabilités.

### 1. Le passage du "script" au "pipeline orchestré"
Jusqu'ici, la fonction `main()` portait une trop grande partie de la logique de décision et de configuration. Bien que fonctionnelle, cette approche présentait des risques de rigidité. Nous avons procédé à un refactoring majeur pour transformer `main.py` en un véritable **orchestrateur de flux**.

* **Extraction de la logique de décision** : La logique complexe de collecte des préférences utilisateur (Outliers / Missing values) a été extraite de `main.py` pour être encapsulée dans `src/cleaner_engine.py`.
* **Simplification de l'interface** : `main.py` ne gère plus "comment" décider, mais "quand" appeler les modules. Il se contente de piloter la séquence : Charger $\rightarrow$ Profiler $\rightarrow$ Décider $\rightarrow$ Nettoyer $\rightarrow$ Sauvegarder $\rightarrow$ Rapporter.

### 2. Bénéfices de la modularité accrue

Ce refactoring a apporté des avantages critiques pour la vie du projet :

* **Haute Maintenabilité (Separation of Concerns)** : En isolant la logique de décision dans le moteur (`cleaner_engine`), toute modification de la règle métier (ex: ajouter une nouvelle option de nettoyage) se fait dans le module spécialisé sans risquer de casser l'orchestration du pipeline dans `main.php`.
* **Reproductibilité et Testabilité** : En rendant les fonctions de décision et de nettoyage "indépendantes" de l'environnement d'exécution, nous avons facilité la création de tests unitaires isolés. On peut désormais tester la logique de décision sans avoir besoin de simuler un fichier CSV complet.
* **Clarté de l'Architecture** : Le point d'entrée est devenu une lecture "haut niveau" du workflow. Un nouvel arrivant sur le projet peut comprendre le processus métier en quelques secondes de lecture, sans être noyé dans les détails d'implémentation des algorithmes.

### 3. Résultat final
L'architecture est désormais capable d'absorber de nouvelles étapes (comme une étape de validation de schéma ou d'export vers une base de données) sans augmenter la complexité cognitive de l'orchestrateur principal.

---

## Étape 22 : Évolution vers l'analyse comparative : programmation orientée objet (POO) et profilage dual

Dans cette phase, le projet a franchi un nouveau palier de maturité architecturale en passant d'un outil de profilage générique à un système de **double audit contextuel**. L'enjeu était de distinguer l'analyse de l'état "brut" (erreurs, bruit, anomalies) de l'analyse de l'état "nettoyé" (performance, complétude, intégrité).

### 1. Le défi : un besoin de dualité analytique
Le pipeline manquait d'une distinction sémantique entre les deux phases critiques du workflow :
* **Phase Pre-Cleaning** : L'objectif est de détecter les anomalies (casse, outliers, doublons) pour guider le nettoyage.
* **Phase Post-Cleaning** : L'objectif est de valider la réussite des transformations et de vérifier la stabilité de la structure (absence de nouveaux biais).

Utiliser une seule et même classe pour ces deux missions risquait de créer un outil trop monolithique et difficile à spécialiser.

### 2. Implémentation : l'héritage et la spécialisation (POO)
Pour répondre à ce besoin, nous avons refondu le module `data_profiler.py` en utilisant les principes de la **Programmation Orientée Objet (POO)**, plus précisément l'**héritage de classes**.

* **La Classe Mère (`DataProfiler`)** : Elle conserve toute l'intelligence fondamentale (calcul des statistiques, génération des graphiques, moteur de reporting HTML/Markdown). Elle est le socle de robustesse.
* **Les Classes Filles (`PreCleaningProfiler` & `ExploratoryProfiler`)** : 
    * Elles héritent de toutes les capacités de la classe mère via `super()`.
    * Elles permettent de spécialiser le comportement métier.
    * **PreCleaningProfiler** : Conçue pour l'audit de détection (focus sur les alertes de qualité).
    * **ExploratoryProfiler** : Conçue pour l'audit de validation (focus sur la distribution et la structure finale).

### 3. Intégration réussie dans le pipeline
L'implémentation dans `main.py` a transformé le workflow en un véritable processus de **comparaison avant/après** :
1. **Instanciation du `PreCleaningProfiler`** sur le DataFrame brut $\rightarrow$ Génération du rapport de diagnostic.
2. **Exécution du `cleaner_engine`** $\rightarrow$ Transformation des données.
3. **Instanciation de l'`ExploratoryProfiler`** sur le DataFrame nettoyé $\rightarrow$ Génération du rapport de validation.

Cette structure permet désormais au Data Analyst de visualiser non seulement les transformations, mais aussi la **réduction de l'entropie** (le passage du désordre à l'ordre) au sein du dataset.

### 4. Perspectives et prochaines étapes
Bien que l'architecture soit désormais robuste et capable de gérer deux phases distinctes, le travail de personnalisation reste ouvert :
* **Personnalisation des alertes** : Adapter les seuils de criticité spécifiquement pour la phase de pré-nettoyage.
* **Enrichissement du mode exploratoire** : Ajouter des tests de corrélation ou de stabilité statistique uniquement dans la phase post-nettoyage.
* **Standardisation de l'interface** : S'assurer que les deux profilers partagent un contrat d'interface identique pour une manipulation simplifiée dans l'orchestrateur.

---

## Étape 23 : Expansion de l'analyse multivariée et optimisation du dashboarding HTML

Dans cette phase majeure, le projet a franchi un nouveau cap : le passage d'un simple outil d'inspection de colonnes à un véritable système d'**analyse exploratoire multidimensionnelle**. L'objectif était d'ajouter de la profondeur statistique tout en optimisant la lisibilité du rapport final.

### 1. Expansion du module `ExploratoryProfiler` : l'analyse de corrélation
L'innovation majeure de cette étape a été l'introduction de visualisations permettant d'étudier les interactions entre les variables numériques, et non plus seulement leurs propriétés isolées.

* **Matrice de Dispersion (Scatter Plot Matrix)** : Implémentation d'une matrice permettant de visualiser simultanément les relations binaires entre toutes les colonues numériques. Cela permet de détecter instantanément des clusters ou des tendances (linéaires/non-linéaires).
* **Heatmap de Corrélation** : Intégration d'une carte thermique basée sur le coefficient de corrélation. L'utilisation de la palette `coolwarm` permet une lecture intuitive : le rouge pour les corrélations positives fortes, le bleu pour les corrélations négatives, et le blanc pour l'absence de lien.
* **Valeur ajoutée métier** : Cette brique permet de repérer les redondances de données (colonnes fortement corrélées) et de comprendre les dépendances entre les indicateurs (ex: lien entre prix et volume).

### 2. Refonte de l'architecture visuelle : vers un "dashboard" de pilotage
L'ajout de nouveaux graphiques risquait de créer un rapport trop long et illisible. Nous avons donc entrepris une refonte complète de la couche de présentation HTML pour transformer le rapport en un véritable **Dashboard décisionnel**.

* **Optimisation du Layout (Display Flex)** : Abandon du mode "liste verticale" au profit d'un système de conteneurs flexibles. Nous avons regroupé l'Histogramme, le Boxplot et les statistiques dans une **ligne horizontale unique** par variable.
* **L'Encart Statistique "Side-by-Side"** : Création d'un nouveau module d'affichage compact. À côté du Boxplot, nous avons intégré un encart stylisé (fond gris, bordures arrondies) présentant les métriques clés (Médiane, Bornes IQR). Cela permet de croiser la preuve visuelle (le graphique) et la preuve chiffrée (la statistique) sans aucun mouvement d'œil.
* **Répartition des masses visuelles (Grid System)** : Application de proportions strictes pour garantir l'équilibre du rapport :
    * **45%** pour l'Histogramme (vision de la distribution).
    * **25%** pour le Boxplot (vision de la dispersion).
    * **15%** pour l'Encart Statistique (vision de la précision).
    * **15%** de marge pour la clarté et le confort de lecture.

### 3. Impact sur la performance et l'auditabilité
* **Densité d'information** : Le rapport est devenu beaucoup plus compact. Un analyste peut désormais auditer un dataset complet en un seul coup d'œil, sans scrolling excessif.
* **Robustesse du rendu** : Utilisation de l'encodage **Base64** pour injecter les visuels directement dans le HTML, garantissant un rapport "Self-Contained" (autonome), portable par email et sans dépendance de fichiers externes.

---

## Étape 24 : Assainissement du socle : remise au vert de la suite de tests et correction de bugs silencieux

Avant d'engager le chantier de l'interface web, une vérification de routine a révélé que la suite de tests comptait **17 échecs préexistants**. Ce constat, inconfortable, était en réalité une chance : un harnais de tests rouge ne peut détecter aucune régression. Impossible de refondre les modules en confiance sans d'abord rétablir ce filet de sécurité.

### 1. Le diagnostic : deux populations d'échecs très différentes
L'analyse des 17 échecs a fait apparaître une distinction essentielle, qu'il aurait été dangereux de traiter uniformément :

* **15 échecs de « dérive de tests »** : le code avait évolué, les assertions non. Un test attendait `"Lignes:"` quand le code produisait `"Lignes : "` (typographie française) ; un autre vérifiait que `describe_categorical` renvoyait au plus 3 éléments, alors qu'il expose désormais 7 indicateurs ; la méthode `generate_report` avait été renommée `generate_md_report` sans mise à jour des appelants.
* **2 échecs révélant de vrais bugs de production** : ceux-là étaient masqués par le bruit des 15 autres, et c'est précisément le danger d'une suite de tests durablement rouge.

### 2. Les bugs silencieux mis au jour
Deux défauts sérieux se cachaient derrière ces échecs, dont un bloquant :

* **`clip_outliers` cassait le pipeline de bout en bout** : écrêter une colonne entière (type `Int64` nullable) avec une borne IQR flottante lève une exception dans pandas, qui refuse d'insérer une valeur non entière dans un `IntegerArray`. Le paradoxe est cruel : c'est `fix_numeric_types` qui produit ces `Int64`, si bien que le moteur se sabotait lui-même dès qu'une colonne entière contenait une valeur aberrante. La correction resserre les bornes vers l'intérieur de la clôture IQR (`ceil` pour la borne basse, `floor` pour la haute), ce qui préserve l'intégrité du type entier.
* **La détection de dates était du code mort** : le garde-fou de performance `_can_be_numeric`, introduit pour éviter d'analyser inutilement les colonnes textuelles, exécutait un `continue` sur toute colonne non numérique. Or une date (`"01/01/2023"`) n'est pas numérique. Le bloc de conversion en `datetime`, situé 90 lignes plus bas, n'était donc **jamais atteint** — une fonctionnalité documentée dans le README mais inopérante depuis l'optimisation de l'Étape 20.

### 3. La refonte de `clean_types` et l'enrichissement de la détection de dates
La correction a été l'occasion de restructurer la fonction selon le principe de responsabilité unique. La boucle monolithique a été scindée en deux fonctions dédiées :

* **`_try_numeric_conversion`** : gère le nettoyage monétaire et les séparateurs décimaux.
* **`_try_datetime_conversion`** : tente désormais **six formats de date explicites** (`%d/%m/%Y`, `%Y-%m-%d`, `%d-%m-%Y`, `%Y/%m/%d`, et leurs variantes horodatées) avant de retomber sur l'inférence automatique de pandas, en retenant le format au meilleur taux de réussite.

Cette approche répond à un point inscrit à la roadmap (« être plus explicite sur le format ») et supprime au passage l'avertissement `Could not infer format` qui polluait la console — un détail qui prend de l'importance dès lors que cette console sera affichée dans l'interface web.

### 4. Trois correctifs de robustesse complémentaires
* **`CleanLogger.get_summary`** levait un `TypeError` si le dictionnaire de statistiques contenait `None` — une comparaison `None > 0` non gardée.
* **`clip_outliers` mutait le DataFrame de l'appelant** faute de copie défensive. Inoffensif dans le pipeline actuel, mais qui aurait corrompu silencieusement l'état d'une session web.
* **`generate_md_report`** levait sur un nom de fichier nu, `os.path.dirname` renvoyant une chaîne vide à `os.makedirs`. Remplacé par `Path().parent.mkdir()`.

### 5. Résultat
**103 tests passent, contre 86 initialement.** Le harnais est redevenu un instrument de mesure fiable, et le pipeline fonctionne réellement de bout en bout sur le jeu de données de référence (73 810 lignes). Cette étape n'ajoute aucune fonctionnalité : elle rachète une dette technique dont l'ampleur était invisible, et sans laquelle la suite du chantier aurait avancé à l'aveugle.

---

## Étape 25 : Industrialisation de la couche graphique : sortie de PyPlot et figures réutilisables

Cette étape prépare l'interface web en réglant un obstacle structurel : dans l'architecture précédente, **les graphiques n'existaient nulle part en tant qu'objets**. Ils étaient créés, encodés en base64 et détruits à l'intérieur même de la fonction de génération HTML. Impossible d'en afficher un ailleurs que dans un rapport téléchargeable.

### 1. Le problème de fond : le registre global de PyPlot
Le code utilisait `plt.figure()`, l'interface « confort » de matplotlib. Or cette interface inscrit chaque figure créée dans un **registre global** (`Gcf`), d'où elle ne sort que par un appel explicite à `plt.close()`. Dans un script en ligne de commande qui s'achève après quelques secondes, l'oubli est sans conséquence. Dans un serveur web qui vit des heures et réexécute son script à chaque interaction de l'utilisateur, c'est une **fuite mémoire garantie**.

Le code présentait d'ailleurs deux occurrences du défaut :
* La matrice de dispersion créait **deux figures et n'en fermait qu'une** (`plt.figure()` suivi de `pd.plotting.scatter_matrix`, qui construit sa propre figure) : une figure vide de 25×25 pouces était abandonnée à chaque génération de rapport.
* Chaque bloc graphique plaçait son `plt.close()` **à l'intérieur** du `try`, si bien qu'une erreur de tracé sautait la fermeture et laissait la figure derrière elle.

### 2. La solution : l'API d'embarquement plutôt que l'interface confort
Plutôt que de multiplier les `plt.close()` — une correction par la discipline, donc fragile — nous avons abandonné pyplot pour la **création** de figures, au profit de l'API d'embarquement documentée de matplotlib : `Figure` + `FigureCanvasAgg`.

Une figure construite ainsi **n'entre jamais dans le registre global**. Elle est libérée par le ramasse-miettes dès que plus personne ne la référence, exactement comme n'importe quel objet Python. La fuite devient *structurellement impossible* au lieu d'être évitée par vigilance. Le backend `Agg` est en outre imposé dès l'import, ce qui garantit l'absence de toute dépendance à un serveur graphique.

### 3. Le nouveau module `plot_factory.py` : un code, deux consommateurs
Un module dédié centralise désormais la construction des cinq graphiques du projet (histogramme, boxplot, barplot, matrice de dispersion, heatmap de corrélation), chacun exposé par une fonction qui **retourne une figure** au lieu de l'afficher ou de l'encoder.

En aval, un unique convertisseur `figure_to_img_tag()` produit la balise HTML autonome en base64. La même figure peut donc alimenter :
* le **rapport HTML** (via l'encodage base64, comme avant) ;
* l'**interface web** (via `st.pyplot`, qui consomme directement l'objet).

Zéro duplication : le rendu d'un graphique est identique dans les deux canaux, par construction.

La matrice de dispersion, que pandas refusait de construire sur une figure fournie, a été réimplémentée à la main (`fig.subplots(n, n)`, histogrammes sur la diagonale, nuages de points ailleurs), sans recours à une API privée.

### 4. Correction d'un rapport HTML malformé et allègement
La classe `ExploratoryProfiler` ajoutait ses visualisations **après** le `</body></html>` écrit par la classe mère, puis refermait une seconde fois les balises. Tous les rapports exploratoires produits jusqu'ici étaient donc structurellement invalides.

Le document a été découpé en trois méthodes — `_html_head()`, `_html_body()`, `_html_footer()` — et la sous-classe n'étend plus que le **corps**. Le bug disparaît par construction : il n'est plus possible d'ajouter du contenu après la fermeture.

Les dimensions ont par ailleurs été ramenées à des valeurs raisonnables (matrice de dispersion plafonnée à 6 colonnes en 2,2 pouces par cellule, heatmap en 10×8 au lieu de 25×20). Un rapport exploratoire complet pèse désormais **186 Ko**, contre plusieurs mégaoctets auparavant — les anciennes figures de 25×25 pouces produisant à elles seules près de 6 Mo de base64 chacune.

### 5. Allègement de l'héritage et verrouillage par les tests
Les deux classes filles redéclaraient à elles deux **18 méthodes** en pur `return super().X(...)`, sans la moindre différence de comportement. Ces passe-plats ont été supprimés : chaque ligne retirée est un endroit de moins à maintenir en cohérence. Les classes subsistent — elles nomment l'intention dans le pipeline et restent le point d'extension prévu pour des seuils de criticité différenciés.

Un nouveau fichier `tests/test_plot_factory.py` (18 tests) verrouille les garanties acquises, dont deux particulièrement structurantes :
* après la construction de **90 figures**, le registre de pyplot doit être **vide** ;
* **aucun module de `src/` ne doit importer `matplotlib.pyplot`** — le test parcourt les sources et échoue si la règle est enfreinte, empêchant toute régression future vers l'ancienne pratique.

### 6. Résultat
La couche graphique est devenue un **service réutilisable** plutôt qu'un effet de bord de la génération HTML. Cinq rendus exploratoires consécutifs ne laissent aucune figure résiduelle, le HTML produit est valide, et **121 tests** passent. L'interface web peut désormais afficher les mêmes graphiques que les rapports, sans dupliquer une ligne de code de tracé.

---

## Étape 26 : Découplage interface / logique métier : vers une architecture bi-façade

Cette étape est le pivot du chantier. Jusqu'ici, les modules de `src/` **posaient** des questions ; désormais ils **reçoivent** des réponses. Ce renversement est ce qui rend possible une interface web sans dupliquer une ligne de logique métier.

### 1. Le problème : quatre points de blocage invisibles en local
Le pipeline interrogeait l'utilisateur à quatre endroits, via `input()` : deux pour les décisions de nettoyage lourd (outliers, valeurs manquantes), un pour le format du rapport de profilage, un pour la génération du rapport de nettoyage.

Dans un terminal, ce dialogue est un atout. Dans un navigateur, il n'existe pas de terminal : `input()` lève une exception. Et le pipeline se comportait alors de la pire manière possible — non pas en signalant l'erreur, mais en l'avalant : le bloc `try/except` de `run_profiling_workflow` interceptait l'exception et retournait un dictionnaire **vide**. Le profilage disparaissait silencieusement, et le nettoyage se poursuivait sans contexte.

Le même défaut affectait la ligne de commande dans un cas courant : dès que la sortie était redirigée vers un fichier ou un tube, Python retombait sur l'encodage ANSI du système (cp1252 sous Windows), incapable d'encoder les emojis du pipeline. Le script mourait sur son **premier message d'accueil**.

### 2. Le principe retenu : la question devient un paramètre
Plutôt que de dupliquer l'orchestration dans deux points d'entrée, chaque fonction interactive a été transformée selon une règle unique :

* **elle conserve sa signature et son comportement** — la ligne de commande n'est pas affectée ;
* **elle gagne un paramètre nommé de contournement** (`answer=`, `choice=`, `generate=`, `report_format=`) qui court-circuite l'invite ;
* **elle acquiert une garde de fin de flux** (`except EOFError, KeyboardInterrupt`) qui retient la valeur par défaut documentée au lieu de lever ou de boucler sans fin.

Cette troisième propriété est la plus précieuse : elle rend les modules importables depuis n'importe quel contexte dépourvu de terminal — serveur web, intégration continue, ou simple redirection de sortie.

### 3. L'extraction des résumés purs
Pour que l'interface web puisse **présenter la même information** sans hériter d'un affichage conçu pour un terminal, la partie descriptive a été extraite en deux fonctions pures :

* **`summarize_outliers()`** → nombre d'outliers par colonne ;
* **`summarize_missing_values()`** → nombre et pourcentage de valeurs manquantes par colonne.

Elles ne savent rien afficher : elles renvoient des données structurées **et** une liste de lignes de texte prêtes à l'emploi. La ligne de commande imprime les lignes ; l'interface web ignore les lignes et exploite les données brutes pour composer ses propres cases à cocher et menus déroulants. Chaque façade reste maîtresse de sa présentation.

### 4. La chasse aux anomalies : ce que l'audit a révélé
Le paramétrage a servi de révélateur. Cinq anomalies ont été corrigées, dont deux sérieuses.

**a) Le bug de l'écrêtage fantôme, enfin élucidé.**
`get_user_decisions` transmettait `profiler_results['outliers']` — le sous-dictionnaire — à une fonction qui cherchait la clé `'outliers'` *dans* ce qu'elle recevait. La recherche échouait toujours, d'un niveau de profondeur. Conséquence : la fonction concluait « aucune valeur aberrante détectée » et retournait `False` **sans jamais poser la question**. L'écrêtage était silencieusement désactivé dès qu'un profilage existait.

L'illusion était parfaite : la question suivante (valeurs manquantes), elle, fonctionnait. Une réponse `y` donnée pour les outliers était en réalité consommée par cette question suivante, donnant l'impression que tout fonctionnait. Le défaut remontait à bien avant le refactor de l'Étape 21 — il vivait alors dans `main.py` et y avait été déplacé tel quel.

**b) Un constat de conception plus profond : l'ordre du pipeline.**
Le correctif précédent en a révélé un second, structurel. Le profilage a lieu **avant** la correction des types. Or une colonne de montants au format `"1 200,50 €"` est encore du **texte** à ce stade : `select_dtypes(number)` ne la voit pas, et le profileur n'y détecte donc **aucun outlier** — alors que la même colonne, une fois convertie, en révèle plusieurs.

Autrement dit : l'utilisateur ne se voyait jamais proposer d'écrêter précisément la colonne qui en avait le plus besoin. Le diagnostic a été complété par une estimation sur les colonnes textuelles convertibles, explicitement signalée comme telle dans l'affichage (« après correction des types »). Le décompte reste indicatif — c'est `clip_outliers` qui tranche, sur des types définitivement corrigés — mais la question est désormais posée.

**c) La priorité de la consigne sur le pré-diagnostic.**
Corollaire du point précédent : une consigne explicite doit primer sur une vérification heuristique. Si l'utilisateur demande l'écrêtage, le refuser au motif que le profilage n'a rien vu revient à annuler silencieusement sa demande. L'ordre de priorité est désormais strict — consigne explicite, puis question, puis défaut.

**d) `clean_whitespace` fabriquait de fausses catégories.**
La fonction appliquait `astype(str)` à l'ensemble d'une colonne, transformant chaque `NaN` en la chaîne littérale `"nan"`. Le reste du pipeline la traitait ensuite comme une modalité textuelle légitime — elle apparaissait dans les graphiques de répartition et faussait les cardinalités. Les valeurs manquantes sont maintenant masquées et préservées.

**e) L'encodage de la sortie console.**
`main.py` force désormais `stdout` et `stderr` en UTF-8 au démarrage, ce qui rend le script utilisable avec une sortie redirigée.

### 5. Le chargement depuis la mémoire
`load_file()` ne savait partir que d'un chemin sur disque. Or un fichier déposé dans un navigateur n'a pas de chemin : il arrive sous forme d'octets en mémoire.

Le module a été réorganisé autour d'un **coeur orienté octets** (`load_dataframe(octets, nom)`), les fonctions orientées chemin devenant de simples enveloppes. Toute la logique de détection — format, encodage, séparateur — vit désormais en un seul endroit, ce qui garantit un comportement rigoureusement identique entre les deux modes.

L'alternative — écrire le fichier reçu dans un fichier temporaire pour réutiliser `load_file` — a été écartée : elle aurait exigé une logique de nettoyage, échoué sur un système de fichiers en lecture seule, et relu des octets déjà présents en mémoire. Les **29 tests existants du loader passent sans modification**, preuve que le contrat public est intact.

### 6. Deux garde-fous nouveaux
**`src/console_capture.py`** détourne `stdout`, `stderr` et le journal racine vers un tampon mémoire, que l'interface web affichera dans un volet dépliable. Le pipeline reste ainsi bavard et traçable dans le navigateur, sans qu'aucun module métier n'ait à connaître Streamlit. Le traitement explicite du module `logging` n'est pas redondant : un `StreamHandler` construit avant la redirection a capturé la référence à `sys.stderr` et continuerait d'écrire dans la vraie sortie d'erreur.

**`tests/test_integrite_source.py`** ajoute des contrôles structurels, nés d'un incident survenu pendant cette étape : un refactor a laissé `generate_enhanced_report` **définie deux fois** dans le même module. Python retient silencieusement la dernière définition — en l'occurrence l'ancienne version, celle qu'on venait de remplacer. Aucun test fonctionnel n'a échoué, parce qu'aucun ne couvrait cette fonction. Le nouveau fichier détecte désormais :

* toute fonction ou méthode **définie deux fois** ;
* tout module de `src/` qui **importerait streamlit** — la frontière du modèle bi-façade est ainsi vérifiée automatiquement ;
* tout appel à `input()` **dépourvu de garde** de fin de flux ;
* toute fonction publique **sans docstring**.

### 7. Un point d'entrée en ligne de commande digne de ce nom
`main.py` n'impose plus de chemins codés en dur. Il accepte `--input`, `--output`, `--reports`, `--format-rapport`, et deux modes non interactifs (`--oui-a-tout`, `--non-interactif`) précieux pour l'automatisation. Il retourne un code de sortie exploitable et affiche enfin le chemin du rapport de nettoyage, que `generate_enhanced_report` se contentait jusque-là d'imprimer sans le retourner.

Un **échantillon synthétique** de 312 lignes est désormais versionné dans `data/samples/`, reproduisant toutes les anomalies du jeu réel (formats de date mélangés, variations de casse, symboles monétaires, séparateurs décimaux français, doublons, valeurs extrêmes) sans contenir aucune donnée personnelle. Le `.gitignore` a été ajusté pour l'autoriser — avec une subtilité : il fallait écrire `data/*` et non `data/`, car git ne descend pas dans un répertoire ignoré et n'y évaluerait donc jamais une exception.

### 8. Résultat : un audit complet du mode terminal
Six scénarios ont été validés de bout en bout avant tout développement de l'interface web :

| Scénario | Résultat |
|---|---|
| Fin de flux immédiate | Aucun blocage, aucune trace, code de sortie 0 |
| `--oui-a-tout` | **3 outliers écrêtés** sur l'échantillon |
| `--non-interactif` | Traitements lourds refusés, pipeline complet |
| Interactif, réponse `y` | Question posée, **écrêtage effectif** |
| Interactif, réponse `n` | Écrêtage refusé, rapport ignoré |
| Jeu réel, 73 810 lignes | **2 795 outliers écrêtés**, 1 447 doublons, 22 160 valeurs comblées |

Cette dernière ligne mérite d'être soulignée : sur le jeu de référence, l'ancien code corrigeait **zéro** outlier. La fonctionnalité était annoncée, documentée, testée en apparence — et inopérante.

**233 tests passent**, contre 121 à l'étape précédente. La logique métier est désormais totalement agnostique de son interface : c'est le socle sur lequel l'application web peut être bâtie sans rien réécrire.

---

## Étape 27 : Naissance de l'interface web : de l'outil de terminal à l'application

Les trois étapes précédentes avaient préparé le terrain. Celle-ci construit l'application elle-même — et le résultat mérite d'être souligné : `app.py` ne contient **pas une seule ligne de logique de nettoyage**. Il dépose des widgets, transmet leur valeur, affiche ce qui revient.

### 1. Le principe de traduction : du dialogue au widget
L'enjeu n'était pas de transposer les messages du terminal dans une page web. Un dialogue conçu pour une console — « Répondez par 'y' (oui) ou 'n' (non) », « Appuyez sur Entrée pour choisir 'n' par défaut » — n'a aucun sens dans un navigateur, où le geste naturel est de cocher une case.

C'est précisément le rôle des fonctions `summarize_outliers()` et `summarize_missing_values()` extraites à l'étape précédente : elles renvoient **des données**, pas de l'affichage. Chaque façade compose ensuite sa propre présentation :

| Décision | En terminal | Dans le navigateur |
|---|---|---|
| Écrêter les outliers | question fermée `y/n` | case à cocher, désactivée s'il n'y a rien à corriger, avec le décompte par colonne en infobulle |
| Combler les manquants | question fermée `y/n` | case à cocher, avec le nombre total dans l'étiquette |
| Format du rapport | menu numéroté `1` ou `2` | sélection multiple « Markdown / HTML » |
| Générer le rapport | question fermée `y/n` | case à cocher |
| Nombre de passes | non exposé | champ numérique borné de 1 à 10 |

Les cases sont regroupées dans un **formulaire** : cocher une option ne relance aucun calcul avant la validation explicite. C'est une différence de fond avec le modèle par défaut de Streamlit, qui réexécute tout le script à chaque interaction.

### 2. Architecture : cinq onglets, un état, aucune duplication
L'application s'organise en une barre latérale (dépôt du fichier et actions) et cinq onglets : **Aperçu**, **Profilage**, **Nettoyage**, **Graphiques**, **Téléchargements**.

Deux décisions structurent l'état de session, et toutes deux consistent à **refuser de stocker** :

* **Aucun profileur n'est conservé.** Chaque instance détient une copie complète du DataFrame ; en garder deux par session doublerait l'empreinte mémoire. Seul le dictionnaire de résultats est rangé. Et puisque `CleanerReporter` ne lit qu'un seul attribut du profileur, un objet factice porteur de ce dictionnaire suffit pour produire le rapport.
* **Aucune figure n'est conservée.** Une figure en session serait retenue pendant toute la session, pour chaque session. On stocke les données d'entrée et on reconstruit à l'affichage, via un utilitaire unique qui libère les artistes juste après le rendu.

Un mécanisme de remise à zéro se déclenche dès qu'un fichier différent est déposé, identifié par l'empreinte SHA-256 de son contenu. Sans lui, on afficherait le dataset nettoyé du fichier précédent à côté du profilage du nouveau.

### 3. Les graphiques : à la demande, jamais d'office
L'onglet des graphiques illustre un arbitrage d'ergonomie autant que de performance. Un dataset de quarante colonnes produirait quatre-vingts figures au premier affichage — l'application semblerait figée. Deux garde-fous :

* la sélection de colonnes est plafonnée à trois par défaut, l'utilisateur en ajoutant à sa convenance ;
* la matrice de dispersion et la heatmap de corrélation, les deux graphiques coûteux, sont derrière des **boutons explicites**.

Les figures affichées sont rigoureusement celles des rapports HTML : même code de tracé, deux consommateurs.

### 4. La console du pipeline, rapatriée dans le navigateur
Le pipeline reste bavard : il annonce le séparateur détecté, l'encodage, chaque itération de nettoyage, chaque conversion de type. Cette traçabilité disparaissait dans un navigateur.

Le module `console_capture` détourne cette sortie vers un tampon mémoire, affiché dans un volet dépliable sous chaque onglet concerné. L'utilisateur curieux peut ainsi vérifier ce qui s'est réellement passé — la transparence du terminal, sans le terminal.

### 5. Aucune écriture sur le serveur
Tous les livrables — CSV nettoyé, rapport de profilage Markdown, rapport HTML avec graphiques, rapport de nettoyage — sont produits **en mémoire** et proposés au téléchargement. C'est la raison d'être des méthodes `render_report()` et `render()` ajoutées à l'étape précédente.

Trois motifs à ce choix :
* le schéma de nommage horodaté est à la minute, donc deux utilisateurs simultanés s'écraseraient mutuellement ;
* sur un hébergeur, le disque est éphémère et partagé entre sessions ;
* ne rien écrire est la garantie de confidentialité la plus simple à tenir — et à expliquer.

Une case à cocher unique, décochée par défaut, offre l'enregistrement local pour ceux qui utilisent l'outil sur leur propre machine. Le CSV téléchargeable est encodé en `utf-8-sig`, marque d'ordre comprise, pour qu'Excel affiche correctement les accents — divergence assumée avec la ligne de commande, qui reste en UTF-8 nu.

### 6. Confidentialité : ce qui est annoncé doit être vérifiable
Un encart de transparence détaille où vivent les données et combien de temps. Deux mesures techniques le rendent vrai :

* le cache de Streamlit est **borné** (une heure, huit entrées). Ce n'est pas un réglage de performance : le cache est global au processus, donc une entrée survit à la session qui l'a créée. Le borner limite la durée de conservation des données d'un visiteur.
* un bouton **« Effacer mes données »** vide la session et purge le cache.

Ce second point a révélé un bug que seul un test pouvait attraper : **le bouton ne vidait rien**. Le composant d'envoi de fichier conservait le fichier déposé, qui était donc rechargé au rafraîchissement suivant. La fonction annoncée était inopérante. La correction consiste à faire entrer un compteur de génération dans la clé du composant : l'incrémenter force Streamlit à en recréer un neuf, donc vide.

### 7. Tester une application web sans navigateur
Streamlit fournit un harnais, `AppTest`, qui exécute réellement le script et permet d'agir sur ses widgets. **27 tests d'intégration** pilotent ainsi le parcours complet — dépôt, analyse, réglage des options, nettoyage, téléchargement — dans les mêmes conditions qu'un utilisateur, sans navigateur ni capture d'écran.

Ces tests ne vérifient pas seulement que l'application ne plante pas. Ils contrôlent des **effets mesurables** : les doublons disparaissent, la casse est uniformisée, une colonne monétaire textuelle devient numérique, l'écrêtage demandé n'est pas silencieusement ignoré, le second fichier déposé n'hérite d'aucune donnée du premier, et — les deux plus importants — **rien n'est écrit sur le disque sans demande explicite** et **le bouton d'effacement vide réellement l'état**.

Les quatre formats annoncés (CSV, Excel, JSON, JSON Lines) sont éprouvés via l'interface, ainsi que trois cas limites : fichier vide, fichier à une seule colonne non numérique, colonnes entièrement vides.

### 8. Validation de la tenue en charge
L'application a été soumise à **30 cycles complets** consécutifs, mesure mémoire à l'appui. Résultats :

* **aucune figure résiduelle** dans le registre de matplotlib — la garantie de l'Étape 25 tient en conditions réelles ;
* **118 Ko de croissance imputables au projet** sur 15 cycles, soit environ 8 Ko par cycle : négligeable ;
* les 15,5 Mo restants proviennent du cache de polices de matplotlib, cache global et borné par le nombre de polices distinctes, non d'une fuite par requête.

Le serveur a par ailleurs été lancé pour de vrai et répond correctement sur son point de contrôle de santé.

### 9. Résultat
**264 tests passent.** Le projet dispose de deux façades pleinement fonctionnelles au-dessus d'un socle métier unique. La ligne de commande n'a rien perdu — elle a même gagné `argparse` et deux modes non interactifs. L'interface web n'a rien dupliqué : le test structurel qui interdit à `src/` d'importer `streamlit` garantit automatiquement que cette frontière ne se brouillera pas.

---

## Étape 28 : Conformité, documentation et passage en version 1.0

Dernière étape du chantier. Elle ne touche presque pas au code : elle rend le projet **utilisable par quelqu'un d'autre**, et assume les obligations qui naissent dès lors qu'une application accepte des fichiers.

### 1. La question réglementaire : cartographier avant de rassurer
Une application qui reçoit des fichiers traite des données. Avant d'écrire la moindre phrase rassurante, il fallait établir précisément **où ces données vivent et combien de temps**.

| Étape | Emplacement | Persistance |
|---|---|---|
| Dépôt du fichier | mémoire du serveur (en local : la machine de l'utilisateur) | la session |
| Analyse et nettoyage | mémoire du serveur | la session |
| Cache de calcul | mémoire du serveur, **partagé entre sessions** | 1 heure, 8 entrées |
| Téléchargements | navigateur du visiteur | à sa discrétion |
| Enregistrement local | disque du serveur | **persistant — décoché par défaut** |

Le point non évident est le **cache**. Celui de Streamlit est global au processus : une entrée créée par un visiteur survit à sa session et resterait accessible à un autre calcul identique. Le borner en durée et en nombre d'entrées n'est donc pas un réglage de performance mais une **mesure de rétention**.

### 2. Cookies : une position tenable parce qu'elle est méritée
L'application ne dépose aucun cookie applicatif. Deux sources étaient toutefois possibles :

* un **cookie technique de protection CSRF**, strictement nécessaire au fonctionnement, donc exempt de consentement au titre de la doctrine sur les cookies essentiels ;
* la **télémétrie de Streamlit**, qui est un traceur tiers de mesure d'audience.

En désactivant cette télémétrie dans `.streamlit/config.toml`, il ne subsiste que le cookie technique — et **aucune bannière de consentement n'est requise**. La conclusion n'est valable que grâce au réglage : ce fichier doit donc impérativement rester versionné, et un commentaire l'y rappelle explicitement. C'est une mesure de conformité déguisée en fichier de configuration.

### 3. Minimisation : la garantie la plus simple est de ne rien garder
Le principe retenu pour l'interface web est radical : **aucune écriture sur le serveur par défaut**. Tous les livrables sont produits en mémoire et transmis au navigateur.

Ce n'est pas seulement prudent, c'est plus simple à tenir *et* à expliquer. Une case à cocher, décochée, offre l'enregistrement local à ceux qui utilisent l'outil sur leur propre machine. Et un bouton d'effacement vide session et cache en un clic — le droit à l'effacement rendu opérationnel.

Dernière précaution : l'échantillon de démonstration versionné est **entièrement synthétique**. Le jeu de données réel du projet ressemblait à des réservations et aurait pu contenir des informations identifiantes ; plutôt que de l'anonymiser, il a été régénéré de toutes pièces, en conservant toutes ses anomalies (formats de date mélangés, variations de casse, symboles monétaires, séparateurs décimaux français, doublons, valeurs extrêmes) et aucune de ses données.

### 4. Rendre le dépôt clonable : un détail de `.gitignore` qui n'en est pas un
Le fichier `.gitignore` ignorait `data/` en bloc. Conséquence : un clone frais ne contenait **aucune donnée**, et le point d'entrée en ligne de commande — qui pointait vers un chemin codé en dur — échouait au démarrage. Le projet était, littéralement, inutilisable par quiconque d'autre.

La correction a révélé une subtilité de git : il faut écrire `data/*` et non `data/`. Git **ne descend pas dans un répertoire ignoré**, et n'y évalue donc jamais une exception. Avec `data/`, la négation `!data/samples/*.csv` n'est tout simplement jamais lue.

### 5. Un README écrit pour un lecteur extérieur
Le README a été refondu pour répondre aux questions dans l'ordre où elles se posent : comment installer, comment lancer chacun des deux modes, ce que fait l'outil, comment il est architecturé, ce qu'il advient des données, comment lancer les tests.

Deux sections sortent de l'ordinaire :

* **Le principe architectural est énoncé explicitement** — `src/` ne connaît aucune interface, les décisions arrivent par paramètres — avec la précision que cette frontière est **vérifiée automatiquement** par un test, et non seulement recommandée.
* **La section confidentialité est factuelle**, tableau de flux compris, plutôt que rassurante en termes vagues.

Un `CHANGELOG.md` a été créé. Sa section « Corrigé » est longue, et c'est assumé : elle recense treize défauts dont plusieurs rendaient inopérantes des fonctionnalités annoncées et documentées. Les taire aurait été plus flatteur ; les inscrire noir sur blanc dit ce que vaut désormais le harnais de tests.

### 6. La roadmap, mise à jour honnêtement
Trois points inscrits à la feuille de route sont livrés :
* *rendre flexible le loader* — l'utilisateur choisit son fichier, par `--input` ou par dépôt ;
* *séparer profilage et nettoyage* — l'interface web en fait trois gestes distincts ;
* *améliorer la détection des dates* — six formats explicites, la détection ayant par ailleurs été trouvée inopérante.

Deux points y entrent, issus des constats de ce chantier :
* **profilage conscient des types** — le profilage précède la correction des types, si bien qu'une colonne de montants en texte n'y révèle aucune valeur aberrante. Un complément d'estimation a été ajouté à l'Étape 26, mais l'ordre du pipeline mériterait d'être repensé. Il vaut mieux consigner une limite connue que la laisser se redécouvrir.
* **traitement colonne par colonne** dans l'interface web, au lieu de deux décisions globales.

### 7. Version 1.0.0
Le projet quitte son statut « en cours ». Ce que cela signifie concrètement :

* les deux interfaces sont fonctionnelles et éprouvées ;
* **264 tests** passent, contre 86 utilisables au début de ce chantier ;
* le pipeline est validé sur le jeu de référence de 73 810 lignes et sur l'échantillon de démonstration ;
* un clone frais suffit pour utiliser les deux modes, sans manipulation de fichiers ;
* les obligations liées au traitement de données sont identifiées et les mesures correspondantes en place.

Ce qui n'est pas prétendu : l'outil n'est pas déployé publiquement, et la feuille de route reste fournie. La version 1.0 marque un socle stable et documenté, pas une fin.

---

## Étape 29 : L'invariant du double profilage : tenir la promesse du pipeline

Cette étape naît d'une remarque déterminante : **le rapport pré-nettoyage doit contenir des éléments incorrects — c'est tout le but du pipeline — mais le profilage post-nettoyage ne doit plus, en théorie, comporter de colonne mal typée.**

Cette distinction, énoncée simplement, invalidait une conclusion que nous avions inscrite à la feuille de route à l'étape précédente, et ouvrait une vérification qui n'avait jamais été faite.

### 1. Une analyse erronée, corrigée
Nous avions consigné comme limite à revoir le fait que « le profilage précède la correction des types, si bien qu'une colonne de montants en texte n'y révèle aucune valeur aberrante ». C'était mal poser le problème.

Un profil pré-nettoyage qui montre `montant_total` typée en texte est **exact**. C'est le constat du désordre, la raison d'être du rapport. Un rapport qui masquerait le problème pour paraître propre n'aurait aucune utilité.

La véritable distinction est ailleurs :
* le profil pré-nettoyage est un **bon rapport** — il décrit fidèlement les données brutes ;
* il était un **mauvais support de décision** pour la question « voulez-vous écrêter les valeurs aberrantes ? », puisqu'il ne pouvait structurellement pas les voir sur une colonne encore textuelle.

Le complément d'estimation ajouté à l'Étape 26 était donc au bon endroit — dans la fonction de décision, non dans le profileur. Vérification faite, il ne contamine pas le rapport : le profil pré-nettoyage continue d'exposer les types bruts. L'entrée fautive de la feuille de route a été retirée.

### 2. La vérification de l'invariant : quatre colonnes en défaut
Restait à éprouver la seconde moitié de l'affirmation. Le profil post-nettoyage du jeu de référence a été inspecté colonne par colonne. **L'invariant était violé** :

| Colonne | Type après nettoyage | Attendu |
|---|---|---|
| `date_reservation` | `str` | `datetime64` |
| `date_arrivee` | `str` | `datetime64` |
| `date_depart` | `str` | `datetime64` |
| `note_satisfaction` | `str` | numérique |

Fait troublant : sur l'échantillon synthétique, les dates étaient correctement converties. Le défaut ne se manifestait que sur les données réelles — celles dont le désordre n'a pas été inventé.

### 3. Première cause : des conventions de date mélangées dans une même colonne
L'inspection a révélé la nature exacte du désordre. Une seule colonne contenait :

| Convention | Part de la colonne |
|---|---|
| `13/09/2024` | 68,6 % |
| `2023-09-15` | 17,1 % |
| `18-07-2023` | 9,2 % |
| `06/11/23` | le reliquat |

Notre algorithme retenait le **meilleur** format et exigeait 80 % de réussite. Aucun n'y parvenait seul. L'inférence automatique de pandas ne faisait pas mieux : elle se verrouille sur une convention et abandonne les autres, plafonnant à 68,6 %.

Or le **cumul** de ces formats couvre 95 % de la colonne.

La correction change la logique du tout au tout : les formats ne sont plus mis en **concurrence** mais appliqués **cumulativement**. Chaque format ne comble que les valeurs que les précédents ont laissées vides. L'ordre devient dès lors significatif — les formats à année sur quatre chiffres passent avant ceux à deux chiffres, sinon `%d/%m/%y` interpréterait `13/09/2024` de façon fantaisiste. Le catalogue est passé de six à dix formats, horodatages et séparateur point compris.

Résultat : les quatre conventions sont interprétées, **sans perte**, y compris les années à deux chiffres.

### 4. Deuxième cause : les notes fractionnaires
`note_satisfaction` mêlait `5`, `2`, `3,0` et… `5/5`, `3/5`, `1/5`. Le caractère `/` faisait rejeter la colonne entière par le filtre de numérisation.

C'était précisément l'élément « détecter plus de nombres : gérer les notes (5/10, 17/20) » inscrit à la feuille de route. Il a été traité, ainsi que les pourcentages.

Un arbitrage méritait d'être posé explicitement : **que vaut `5/5` ?** Mathématiquement, 1,0. Mais dans une colonne où `5/5` coexiste avec des `5` nus — situation courante dans un export réel — convertir en 1,0 rendrait les deux écritures incomparables. C'est donc le **numérateur** qui est retenu, et la décision est documentée dans le code comme dans la feuille de route, avec sa limite : une colonne mêlant `17/20` et `4/5` resterait incohérente.

Même raisonnement pour les pourcentages : `78.9875 %` devient `78.9875`, et non `0.789875`. Une colonne intitulée « taux » attend la valeur affichée.

### 5. Troisième cause, la plus insidieuse : un seuil mal mesuré
La correction des deux premiers points n'a pas suffi. `note_satisfaction` restait en texte.

La raison est un défaut de raisonnement qui affectait **toutes** les colonnes : le taux de validité était calculé sur la hauteur de la colonne, valeurs manquantes comprises. Or `note_satisfaction` comporte 11 925 valeurs manquantes sur 73 810, soit 16 %. Même avec 100 % des valeurs présentes correctement interprétées, le taux plafonnait à 84 % — sous le seuil de 90 %.

**Aucune colonne comportant plus de 10 % de valeurs manquantes ne pouvait donc jamais être convertie**, quel que soit son contenu. Le taux se mesure désormais sur les valeurs réellement présentes. Le même défaut affectait la conversion de dates et y a été corrigé aussi.

### 6. Un garde-fou né d'un plantage
Au cours de ces corrections, le pipeline s'est mis à lever une exception `OutOfBoundsDatetime` de pandas, sur une date en l'an 1.

L'enchaînement méritait d'être compris : la colonne de notes, rejetée à tort par le filtre numérique, poursuivait son chemin jusqu'à la branche de conversion en date. Là, un format permissif interprétait `5/5` comme une date, produisant une année absurde — et l'affectation de cette valeur hors bornes faisait échouer pandas.

Deux protections en découlent :
* un **contrôle de plausibilité des années** (1900-2100) écarte les interprétations fantaisistes ;
* l'accumulation des résultats passe par `combine_first` plutôt que par une affectation indexée, ce qui laisse pandas harmoniser les résolutions temporelles — deux appels successifs à `to_datetime` peuvent renvoyer des unités différentes.

Le pipeline ne plante plus sur une colonne saugrenue : il la laisse simplement en texte.

### 7. L'invariant, désormais verrouillé par les tests
Un nouveau fichier, `tests/test_invariant_post_nettoyage.py`, transforme l'affirmation en **propriété vérifiée** — 15 tests.

Le choix d'écriture compte : l'invariant n'est pas exprimé comme une liste de colonnes attendues, mais comme une **propriété générale** — « aucune colonne textuelle restante ne doit être convertible, ni en nombre, ni en date ». Le test résiste ainsi à l'évolution des jeux de données, là où une liste figée se périmerait au premier changement de source.

Les deux exigences opposées du double profilage sont contrôlées séparément : le profil pré-nettoyage **doit** montrer les colonnes en texte, le profil post-nettoyage **ne doit plus** en comporter.

### 8. Résultat : l'invariant tient, et l'effet est considérable
Sur les deux jeux de données, la vérification est désormais positive : **zéro colonne mal typée après nettoyage**.

L'effet en aval dépasse la simple cosmétique des types. Sur le jeu de référence de 73 810 lignes :

| Indicateur | Avant l'Étape 29 | Après |
|---|---|---|
| Colonnes correctement typées | 1 | **5** |
| Valeurs aberrantes écrêtées | 2 795 | **5 848** |

La progression des valeurs aberrantes n'est pas un effet de bord mais la conséquence directe du correctif : une colonne restée en texte est invisible pour la détection IQR. Corriger les types, c'est rendre détectable tout ce qu'ils masquaient. Le nombre d'anomalies traitées a plus que doublé.

**279 tests passent.** L'invariant énoncé — le rapport avant nettoyage constate le désordre, celui d'après atteste sa disparition — n'est plus une intention mais une propriété du code, vérifiée à chaque exécution de la suite.

---

## Étape 30 : L'épreuve de l'utilisateur : six retours, une perte silencieuse et une faille de sécurité

Jusqu'ici, l'application avait été testée par ceux qui l'avaient construite. Cette étape commence au moment où elle a été confiée à un utilisateur réel, sur un fichier qu'aucun test n'avait anticipé : un export de prix de carburants, `prix.csv`, 57 073 lignes. Six retours en sont sortis. Chacun a mené plus loin que prévu.

### 1. « J'ai une valeur manquante de plus qu'avant »
Le retour le plus bref était le plus grave. Un nettoyage qui **crée** des valeurs manquantes détruit des données — l'exact contraire de sa mission.

L'enquête a d'abord porté sur le jeu de référence, et y a révélé un défaut bien plus large que celui signalé : **1 849 montants présents étaient vidés** par la conversion de types. Tous avaient la même forme — `1 052,23 €` — avec une espace comme séparateur de milliers. Le code retirait `€` et `$`, jamais les espaces. Le commentaire du code l'annonçait pourtant, et le README citait précisément `"1 200,50 €"` comme exemple vitrine.

Le mécanisme était pernicieux : 97 % de la colonne se convertissant correctement, le seuil de 90 % était franchi, et les 3 % restants étaient silencieusement remplacés par des valeurs manquantes. **`errors='coerce'` combiné à un seuil de tolérance est une destruction silencieuse par conception** : toute conversion réussie à 91 % peut effacer jusqu'à 9 % des valeurs sans le dire.

Un second défaut latent de même nature a été trouvé en chemin : le symbole `£` était accepté par la détection mais jamais retiré par la conversion. Toute colonne en livres sterling aurait été intégralement vidée.

### 2. Le fichier de l'utilisateur : l'an 216
Sur `prix.csv`, la cause était autre. La colonne `prix_maj` contenait la date `0216-03-02T00:00:00` — l'an 216, coquille évidente pour 2016. Le garde-fou de plausibilité des années, ajouté à l'Étape 29, l'avait écartée.

Le vidage était le bon comportement : l'outil ne peut pas deviner s'il fallait lire 2016 ou 2216, et inventer une date serait pire. **Le vrai défaut était son silence.**

### 3. Le principe qui en découle : rien ne disparaît en silence
Corriger les espaces ne suffisait donc pas : la prochaine cause serait différente. Il fallait traiter le principe.

Désormais, chaque conversion de type compare la colonne avant et après, et recense toute valeur présente devenue manquante dans une nouvelle statistique, `values_unparsed` — colonne, nombre et exemples de valeurs d'origine. Les écritures textuelles d'une absence (« NULL », « N/A », « - ») sont exclues du décompte : leur passage à vide n'est pas une perte, elles n'étaient déjà pas des données.

Cette information remonte partout : dans le bilan console, dans le rapport de nettoyage Markdown, et dans l'interface web, sous forme d'un avertissement explicite. Sur `prix.csv`, l'utilisateur lit désormais : *« prix_maj : 1 valeur vidée — exemple : 0216-03-02T00:00:00 »*.

Un test de propriété générale verrouille la garantie : sur un jeu réunissant toutes les sources de perte connues, **les pertes mesurées et les pertes déclarées doivent coïncider exactement**.

En chemin, une observation que le code ne tranche pas mais que l'utilisateur doit connaître : sur ce fichier, cocher « Combler les valeurs manquantes » remplirait les prix des carburants en `rupture_definitive`. On inventerait un prix médian pour un produit qui n'est plus vendu. Une absence peut avoir un sens — l'Étape 16 l'avait pressenti en écrivant qu'imputer une médiane peut être « sémantiquement faux ». L'aide de cette case le dit désormais explicitement.

### 4. L'interface réorganisée autour de ses usages
Quatre retours portaient sur l'ergonomie, et tous pointaient le même travers : l'interface exposait des réglages au lieu de répondre à des besoins.

* **« Je n'ai pas le détail de la colonne convertie »** : il existait, replié au bas de l'onglet. Le détail des conversions est désormais affiché d'emblée — colonne, type avant, type après, valeurs illisibles.
* **« La case Rapport de nettoyage ne fait rien »** : elle ajoutait un bouton dans un autre onglet, invisible depuis celui où l'on se trouvait. Supprimée : le rapport se lit et se télécharge là où s'affiche le nettoyage.
* **« Enregistrer dans data/reports, ça sert à quoi en ligne ? »** : à rien, et c'était même contraire à la promesse de confidentialité. Supprimée. L'écriture de fichiers sur sa propre machine reste l'affaire de la ligne de commande.
* **« Pas de nombre de passes, 5 au maximum c'est bien »** : supprimé. Le moteur s'arrête de lui-même dès que plus rien ne change.

Le formulaire se réduit ainsi aux **deux seules décisions qui altèrent les valeurs**. Tout le reste est corrigé d'office.

L'onglet « Téléchargements » a disparu au profit d'un principe proposé par l'utilisateur : **chaque rapport se consulte, puis se récupère, là où il s'affiche**. Le profilage avant nettoyage dans son onglet, le fichier nettoyé et son rapport dans le leur. Et un nouvel onglet, **« Après nettoyage »**, calcule d'office le profil de contrôle et vérifie l'invariant de l'Étape 29 — plus aucune colonne mal typée — avec un verdict colonne par colonne. La fonction de vérification, `find_mistyped_columns`, a été remontée dans le moteur : les tests et l'interface contrôlent ainsi exactement la même chose.

Rien n'est calculé tant qu'on ne le demande pas : les boutons de téléchargement reçoivent une fonction, exécutée au clic seulement. Sans cela, Streamlit exécutant tous les onglets à chaque interaction, les rapports HTML et leurs graphiques auraient été recalculés en permanence.

### 5. L'aperçu HTML, et la faille qu'il a révélée
Dernier retour : les rapports Markdown se téléchargent, mais les rapports HTML, eux, devraient **s'afficher** avant de se télécharger. C'est un tableau de bord autonome ; le prévisualiser a du sens.

Avant de l'afficher, une lecture de la documentation de `st.iframe` a imposé une vérification : du HTML y est exécuté **avec JavaScript et un accès à l'application**, et la documentation interdit d'y passer du contenu dérivé d'un fichier téléversé. Or le rapport HTML reproduit des noms de colonnes, des modalités, des valeurs d'aperçu.

Vérification faite, **aucune de ces données n'était échappée**. Pire : l'aperçu des données appelait explicitement `to_html(escape=False)`, désactivant la protection que pandas offre par défaut. Une cellule contenant `<img src=x onerror=alert(1)>` produisait un rapport qui **exécutait ce code** — dès avant ce chantier, à la simple ouverture d'un rapport téléchargé. L'aperçu intégré aurait aggravé une faille qui existait déjà.

Deux protections superposées ont été mises en place :

* **l'échappement systématique** de toute donnée issue du fichier, y compris dans le texte alternatif des graphiques, où un guillemet dans un nom de colonne aurait permis d'injecter un attribut ;
* **une politique de sécurité (CSP)** dans l'en-tête du rapport, qui interdit toute exécution de script. Le rapport n'en a aucun besoin — images en base64, styles en ligne — et cette seconde ligne de défense tient même si un échappement venait un jour à manquer.

Les tests de sécurité méritent une remarque. Une première version cherchait des chaînes dans le rapport, et a échoué à tort : le texte `"prix" onmouseover="alert(3)` figurait dans une cellule de tableau, **en texte**, où un guillemet est inoffensif. La version définitive analyse le document avec un vrai analyseur HTML et vérifie ce qu'un navigateur interpréterait réellement : aucune balise `script`, aucun attribut `on…`.

Et pour s'assurer que ces tests ne sont pas de complaisance, ils ont été rejoués contre l'ancien code : **11 échecs**. Ils détectent bien la faille qu'ils sont censés prévenir.

### 6. Une page d'accueil qui raconte le projet
L'application s'ouvrait sur une page presque vide tant qu'aucun fichier n'était déposé. Elle présente désormais le projet : le problème traité (« un fichier qui s'ouvre bien ment souvent »), un tableau avant / après sur des exemples concrets, le parcours en quatre temps, trois principes, et l'histoire du projet, étapes marquantes et erreurs comprises.

Surtout, un bouton **« Essayer avec un exemple »** charge l'échantillon synthétique versionné. Un visiteur peut désormais éprouver l'outil de bout en bout sans avoir de fichier sous la main — ce qui manquait le plus à une page d'accueil vide.

### 7. Un renommage qui aurait pu passer inaperçu
L'utilisateur a renommé `app.py` en `streamlit_app.py`, nom par défaut de Streamlit Community Cloud. Ce renommage a cassé deux choses en silence : les 27 tests d'intégration pointaient vers un fichier disparu, et le test d'intégrité des sources **excluait discrètement** l'interface web, parce qu'il filtrait sa liste de fichiers sur leur existence. La liste est désormais explicite : un renommage de façade fait échouer les tests bruyamment.

### 8. Résultat
**313 tests passent**, contre 279. Sur le jeu de référence, zéro valeur n'est plus détruite en silence. Sur le fichier de l'utilisateur, la valeur vidée est nommée. Le rapport HTML est sûr à ouvrir comme à afficher. Et l'interface ne pose plus que les questions qui comptent.

La leçon de l'étape tient en une phrase : **un utilisateur réel, sur un fichier réel, en une séance, a trouvé ce que 279 tests n'avaient pas vu.** Les tests vérifient ce qu'on a pensé à vérifier ; l'usage révèle le reste.

---

## Étape 31 : Le retour de l'onglet téléchargements et la question de la nouvelle fenêtre

Une étape courte, mais qui illustre deux réflexes utiles : savoir revenir sur une décision quand l'usage la contredit, et vérifier ce qu'une technologie permet réellement avant de promettre une fonctionnalité.

### 1. Revenir sur une suppression
À l'étape précédente, l'onglet « Téléchargements » avait été supprimé au profit d'un principe séduisant : chaque rapport se récupère là où il s'affiche. Le principe était bon, la suppression ne l'était pas. L'utilisateur appréciait de trouver **tous les fichiers réunis au même endroit**.

Les deux ne s'opposent pas. L'onglet est rétabli comme **récapitulatif**, tandis que les boutons contextuels restent dans chaque onglet. Il se construit au fil du parcours : après l'analyse, il propose le rapport avant nettoyage ; après le nettoyage, il ajoute le fichier nettoyé, le rapport de nettoyage et le rapport de contrôle.

Une contrainte technique a structuré la réalisation : Streamlit refuse deux widgets portant la même clé. Les mêmes boutons figurant désormais à deux endroits, les fonctions qui les produisent reçoivent un suffixe d'emplacement. Un test vérifie précisément que boutons contextuels et récapitulatif coexistent sans collision.

### 2. « Streamlit peut-il afficher un fichier HTML dans une nouvelle fenêtre ? »
La réponse honnête est : **pas de façon sûre**. Les trois pistes classiques ont chacune un défaut rédhibitoire :

| Piste | Obstacle |
|---|---|
| Un lien vers le HTML encodé dans l'URL (`data:`) | Chrome et Firefox bloquent ce type de navigation depuis 2017, vecteur connu d'hameçonnage |
| Le service de fichiers statiques de Streamlit | Il faudrait écrire le rapport sur le serveur, dans un dossier **public** : quiconque devinerait l'adresse lirait le rapport d'un autre utilisateur |
| Du JavaScript ouvrant une fenêtre | Fragile, souvent bloqué par les navigateurs, et suppose d'exécuter du script dans l'application |

La deuxième piste mérite d'être soulignée, parce qu'elle est la plus tentante — une option de configuration à activer, et le tour est joué. Elle aurait pourtant détruit la garantie de confidentialité construite aux étapes 27 et 28 : aucune donnée n'est jamais écrite sur le serveur.

L'équivalent sûr retenu est une **fenêtre modale large** (`st.dialog`, jusqu'à 1 280 pixels), qui s'ouvre par-dessus l'application via un bouton « Ouvrir en grand ». Elle bénéficie de toutes les protections du rapport HTML mises en place à l'étape précédente : échappement des données et politique de sécurité interdisant les scripts. Pour un véritable onglet du navigateur, le rapport téléchargé reste autonome et s'ouvre directement. Le README documente ce choix et ses raisons, pour que la question n'ait pas à être redécouverte.

### 3. Résultat
**317 tests passent.** L'interface offre désormais deux façons de récupérer ses fichiers — dans le contexte, ou d'un seul coup d'œil — et trois façons de lire un rapport HTML : dans la page, en grand, ou téléchargé.

---

## Étape 32 : Horodatage des fichiers, présentation permanente et source unique

Trois changements de nature différente, réunis par un même souci : que l'utilisateur ne perde rien — ni un essai écrasé par le suivant, ni la présentation du projet au premier fichier déposé, ni l'historique du projet dispersé entre deux documents.

### 1. Le problème des essais qui s'écrasent
Un usage naturel de l'outil consiste à **comparer plusieurs nettoyages** d'un même fichier : avec et sans écrêtage des valeurs aberrantes, avec et sans remplissage des valeurs manquantes. Or cet usage était impossible sans manipulation manuelle :

| Fichier produit | Nommage avant cette étape | Conséquence |
|---|---|---|
| Fichier nettoyé (ligne de commande) | nom fixe, `dataset_nettoye.csv` | chaque essai écrasait le précédent |
| Rapports (ligne de commande) | horodatés **à la minute** | deux essais dans la même minute s'écrasaient |
| Téléchargements (interface web) | aucun horodatage | le navigateur ajoutait « (1) », « (2) »… sans ordre lisible |

### 2. Un horodatage par exécution, partagé par tous ses fichiers
Chaque nom de fichier se termine désormais par un suffixe `AAAAMMJJ_HHMMSS`. Deux propriétés ont guidé ce choix de format :

* **l'ordre alphabétique est l'ordre chronologique** : un simple tri du dossier range les essais dans le temps ;
* **la précision à la seconde** empêche qu'un second essai lancé dans la même minute écrase le premier.

Surtout, l'horodatage n'est pas calculé fichier par fichier mais **une fois par exécution**, puis transmis à chaque étape qui écrit. Le fichier nettoyé et ses trois rapports portent ainsi exactement la même marque : on retrouve d'un coup d'œil ce qui va ensemble. Vérification faite sur deux essais successifs :

```
reservations_exemple_nettoye_20260929_194212.csv   ← essai sans traitements
reservations_exemple_nettoye_20260929_194215.csv   ← essai avec traitements
```

Dans l'interface web, la logique est la même, à deux niveaux : une marque posée à l'**analyse** pour le rapport avant nettoyage, une marque posée à **chaque nettoyage** pour le fichier nettoyé, son rapport et le rapport de contrôle. Relancer le nettoyage avec d'autres options produit un nouveau jeu complet, sans toucher au précédent. Un chemin de sortie fourni explicitement en ligne de commande (`--output`) reste, lui, respecté tel quel.

Le format vivant désormais à quatre endroits (deux modules de `src/`, la ligne de commande, l'interface web), il a été centralisé dans un petit module, `src/horodatage.py`. Il était jusqu'ici recopié à deux endroits : la garantie, à terme, qu'une des copies diverge.

### 3. La présentation ne disparaît plus
L'Étape 30 avait donné à l'application une page d'accueil racontant le projet. Elle avait un défaut : elle s'effaçait dès le premier fichier déposé. La présentation occupe désormais le **premier onglet**, « 🏠 Présentation », et reste consultable pendant tout le parcours. Seul le bouton « Essayer avec un exemple » en est retiré une fois un fichier chargé — il remplacerait le fichier en cours.

### 4. Une seule source : ce journal
Un `CHANGELOG.md` avait été créé à l'Étape 28, selon une convention répandue : une liste courte, par version, de ce qui a changé. Il faisait largement doublon avec ce journal, qui raconte déjà tout — en plus détaillé, raisonnements et erreurs compris. Le choix a été fait de **n'entretenir qu'une seule source commune**, celle-ci.

La seule information que le CHANGELOG portait en propre était la correspondance entre versions et étapes. Elle a, dans la foulée, été remise en question.

Au fil des étapes 29 à 32, le numéro de version avait été incrémenté quatre fois — 1.0.1, 1.1.0, 1.1.1, 1.2.0 —, chaque fois accompagné d'une étiquette git, et jamais sur décision du porteur du projet. Or celui-ci avait fixé une règle claire dès le départ : **la version 1.0 marque une application déployée et validée**. Aucune de ces versions ne correspondait à un tel jalon : l'application n'avait jamais été mise en ligne.

Les numéros intermédiaires ont donc été retirés. Le projet revient en **version 1.0.0**, qui regroupe l'ensemble des étapes 24 à 32. Le numéro de version relève désormais explicitement de la seule décision du porteur du projet : il marque un jalon réel qu'il choisit, pas l'enchaînement des commits.

L'étiquette git `v1.0.0` a elle aussi été retirée. Elle désignait l'état du code au 27 septembre, antérieur à la correction de la faille de sécurité du rapport HTML : quiconque aurait récupéré « la version 1.0.0 » aurait obtenu un code vulnérable. Elle sera posée le jour où l'application sera déployée et validée, et désignera alors le bon code.

### 5. Une feuille de route remise en accord avec la réalité
La même exigence de cohérence a conduit à relire `améliorations_futures.md`, qui avait dérivé :

* le **bouton de soutien** y figurait comme un projet, alors qu'il est codé et n'attend plus que l'adresse d'un prestataire ;
* une section **« En cours »** annonçait trois chantiers auxquels personne ne travaillait ;
* la rubrique **« Livré en V1.0 »** ne disait pas à quelle étape chaque élément avait été livré ;
* la **documentation API** était présentée comme entièrement à faire, alors que toutes les fonctions publiques sont documentées — un test l'impose — et qu'il ne reste qu'à assembler le document.

La feuille de route est désormais rangée par **état réel** — livré, prêt à activer, à faire — et chaque livraison renvoie à son étape dans ce journal. Une feuille de route qui annonce en projet ce qui est déjà fait trompe le lecteur autant qu'une qui annonce fait ce qui ne l'est pas.

### 6. Résultat
**335 tests passent**, dont 10 consacrés à l'horodatage : format, ordre chronologique, précision à la seconde, marque commune à tous les fichiers d'une exécution, respect d'un `--output` explicite. Et quatre de plus dans l'interface, pour les marques posées à chaque étape et la permanence de l'onglet Présentation.

---

## Étape 33 : Ouvrir le dialogue : retours, soutien, et des onglets toujours visibles

Cette étape tourne l'application vers ses utilisateurs : leur donner les moyens de signaler un problème, de remercier s'ils le souhaitent, et de ne jamais se perdre dans l'interface.

### 1. Inviter aux retours, sans exposer les données
Un bloc « Une remarque, une anomalie ? » figure désormais sur la page de présentation et au bas de l'onglet Téléchargements. Il précise que toute remarque constructive ou anomalie détectée est la bienvenue — et ce n'est pas une formule : plusieurs corrections majeures du projet, à l'Étape 30, sont nées d'un seul test sur un fichier réel.

Il donne trois liens : **signaler une anomalie** (la page Issues du dépôt GitHub), le **profil GitHub** et le **profil LinkedIn** du porteur du projet.

Avant de publier le lien de signalement, il a été vérifié que la page Issues du dépôt était bien activée : un lien mort aurait découragé exactement les retours qu'on sollicitait. Le dépôt est public, la fonctionnalité active.

Une précaution s'imposait : **les signalements GitHub sont publics**. Un utilisateur de bonne volonté pourrait joindre son fichier pour illustrer un problème, et publier ainsi ses données. Le bloc le met en garde explicitement : décrire le problème ou fournir un extrait anonymisé, jamais le fichier lui-même.

### 2. Le soutien, au bon moment et sans insistance
Le bouton « Soutenir le projet » apparaît à trois endroits, chacun avec un message adapté : dans la barre latérale, après l'histoire du projet sur la page de présentation — là où le lecteur mesure le travail accompli —, et au bas des téléchargements, au moment où l'outil vient de rendre service. Tous les messages disent que le soutien est facultatif ; aucun ne culpabilise.

Le bouton a été agrandi de 20 %. Streamlit ne propose aucun réglage de taille pour ce type de bouton, mais attribue à chaque widget muni d'une clé une classe CSS de la forme `st-key-<clé>` — mécanisme vérifié dans le code source de Streamlit avant de s'y fier. Les trois boutons ayant des clés commençant par `soutien_`, une seule règle les cible, sans toucher aux autres. La propriété `zoom` a été préférée à une mise à l'échelle (`transform`) : elle agrandit le bouton **et** décale ce qui suit, là où une mise à l'échelle l'aurait fait déborder sur le texte voisin.

### 3. « Les onglets ont disparu »
Le signalement était sérieux, et il a d'abord fallu établir les faits plutôt que de corriger à l'aveugle. L'application, exécutée dans le harnais de test, générait bien ses sept onglets dès qu'un fichier était chargé, sans la moindre erreur.

La cause était ailleurs : **après un relancement du serveur, la session repart de zéro, sans fichier**. L'application affichait alors sa page d'accueil, qui n'avait pas d'onglets. Rien n'était cassé — mais l'interface changeait de structure selon qu'un fichier était chargé ou non, et cette métamorphose ressemblait à s'y méprendre à une panne.

La correction supprime la cause de la confusion plutôt que de l'expliquer : **les sept onglets sont désormais visibles dès l'arrivée**. « Présentation » s'ouvre en premier ; les autres onglets, tant qu'aucun fichier n'est chargé, indiquent simplement comment en charger un. L'encart de confidentialité, qui apparaissait deux fois sur la page d'accueil, n'y figure plus qu'une fois.

### 4. Résultat
**349 tests passent.** Onze nouveaux tests couvrent les liens de contact et de signalement, l'avertissement sur la publication de données, la présence et l'adresse des trois boutons de soutien, la règle d'agrandissement, la visibilité des onglets dès l'arrivée et l'unicité de l'encart de confidentialité.

---

## Étape 34 : Le projet prend un nom : Quitus

Quarante étapes durant, le projet s'est appelé par ce qu'il faisait : « nettoyage automatique ». Il porte désormais un nom : **Quitus**.

### 1. Un nom qui dit la promesse
En comptabilité, *donner quitus*, c'est attester qu'une gestion est en règle : on a vérifié, on certifie. Le mot rejoint exactement ce que le projet a appris à faire au fil des étapes — ne pas seulement nettoyer un fichier, mais **prouver** qu'il est propre : le profil avant nettoyage constate le désordre, le profil après atteste sa disparition (Étape 29), et aucune valeur ne disparaît sans être déclarée (Étape 30).

La devise qui accompagne le logo le dit en une ligne : **« Le fichier propre, et la preuve. »**

### 2. Un tournant, pas un chantier
Nommer le projet n'imposait pas de tout renommer. Le dossier, le dépôt GitHub et le nom technique du paquet restent inchangés : les modifier n'aurait rien apporté à l'utilisateur, et aurait cassé des liens, des chemins et l'environnement de travail. Ils suivront plus tard, un par un et sans rien casser (Étapes 36 à 38). Le nom apparaît là où il se voit : l'application, sa documentation et ses rapports.

### 3. Le logo, partout où l'on regarde
Le logo — un tableau dont les cellules s'estompent de ligne en ligne, frappé d'une pastille verte cochée — remplace l'emoji balai qui servait jusqu'ici d'identité :

* **en tête de l'application**, où il tient lieu de titre ;
* **dans l'onglet du navigateur**, sous la forme d'une icône carrée tirée du même dessin — le logo complet, en bandeau, serait illisible à cette taille ;
* **en tête du README** ;
* **en tête de chaque rapport** : profilage HTML, profilage Markdown, rapport de nettoyage.

Dans les rapports, le logo est intégré au fichier lui-même, encodé en base64, plutôt que référencé par un chemin : un rapport téléchargé doit s'afficher complet où qu'on l'ouvre. C'est aussi la seule source d'image qu'autorise la politique de sécurité des rapports HTML (Étape 30). Et si le fichier du logo venait à manquer, l'en-tête retombe sur le nom et la devise en texte : un rapport ne doit jamais échouer pour une question d'habillage.

L'onglet du navigateur affiche désormais simplement « Quitus ». La formule descriptive « nettoyage automatique de données », jugée peu parlante, a été retirée des titres, en attendant une formule plus fidèle à ce que fait réellement l'outil.

### 4. Retours et soutien, même sans fichier
Au passage, l'onglet Téléchargements se termine désormais toujours par les moyens de faire un retour et de soutenir le projet, qu'un fichier ait été chargé ou non. Le remerciement, lui, n'apparaît qu'une fois des fichiers produits : remercier quelqu'un qui n'a encore rien fait sonnerait faux.

### 5. Un logo pour chaque thème, un contact à part
Quelques finitions ont suivi :

* **une variante sombre du logo** — nom en blanc, devise éclaircie — rejoint `assets/` : le README la sert aux lecteurs en thème sombre par une balise `<picture>`, et l'application suit son thème. Les rapports, documents sur fond blanc, gardent la variante claire ;
* **signaler n'est pas contacter** : le lien « Signaler une anomalie » ne partage plus sa ligne avec GitHub et LinkedIn. On remonte un défaut dans le suivi public du projet ; on contacte une personne pour échanger. Une section **« Me contacter »** ferme désormais la présentation et l'onglet Téléchargements, à côté du coup de pouce ;
* **le nom dans la barre latérale** s'écrit comme dans le logo : **quitus**, en minuscules, même police, même graisse.

### 6. Résultat
**369 tests passent**, dont de nouveaux qui vérifient la présence du logo en tête de chaque rapport, sa conformité à la politique de sécurité, le repli textuel en son absence, la validité des deux variantes SVG et l'absence de tout script dans celles-ci, ainsi que la séparation du signalement et du contact.

---

## Étape 35 : Mesurer la charge avant d'ouvrir la porte

Avant la mise en ligne, une question simple : combien de personnes l'application peut-elle servir en même temps ? Plutôt que de deviner, la consommation mémoire d'une session complète — dépôt, analyse, nettoyage — a été mesurée sur des fichiers de taille croissante.

### 1. Les mesures

| Fichier CSV | Pic pendant le traitement | Mémoire conservée ensuite |
|---|---|---|
| 1 Mo (20 000 lignes) | ~60 Mo | ~45 Mo |
| 5 Mo (100 000 lignes) | ~90 Mo | ~45 Mo |
| 25 Mo (500 000 lignes) | ~340 Mo | ~235 Mo |

Au-delà de quelques mégaoctets, un fichier coûte environ **dix fois sa taille** au moment du traitement : le fichier lu, le profil, la copie nettoyée et le profil de contrôle coexistent en mémoire.

### 2. Ce que cela veut dire en ligne
Une application gratuite sur Streamlit Community Cloud dispose d'une mémoire limitée, et tous les visiteurs la partagent. Avec de petits fichiers, plusieurs dizaines de personnes peuvent l'utiliser ensemble. Avec des fichiers de 25 Mo, deux ou trois suffiraient à la saturer, et un plantage la redémarrerait pour tout le monde.

Chaque visiteur reste pour autant dans sa propre session : ses données ne sont visibles que de lui. Le cache, commun au serveur, n'est retrouvé que sur un fichier identique octet pour octet, et ne laisse donc rien passer d'un visiteur à l'autre.

### 3. Une limite basse, pour commencer
La taille maximale d'un fichier déposé passe de 200 Mo à **20 Mo**. C'est volontairement prudent : mieux vaut relever la limite une fois la consommation réelle observée en ligne que découvrir la limite de la plateforme par un plantage. Le texte d'aide annonce la même valeur, et un test vérifie qu'ils restent d'accord.

### 4. Un effacement qui ne touche que ses propres données
Le bouton « Effacer mes données » vidait jusqu'ici le cache en entier. Rien n'était perdu pour les autres visiteurs, dont les données vivent dans leur session, mais tous devaient refaire leurs calculs. C'était sûr, mais grossier.

Streamlit permet de retirer une entrée précise du cache, à condition de redonner exactement les arguments du calcul. L'effacement retire désormais, une à une, les entrées calculées sur les données de la session — profils avant et après nettoyage, rapports Markdown et HTML — et rien d'autre. Le même nettoyage ciblé a lieu quand un fichier en remplace un autre, ou quand un nouveau nettoyage remplace le précédent : les calculs devenus inutiles ne restent pas une heure en mémoire.

Le chargement du fichier, lui, sort du cache. Sa clé serait le contenu brut du fichier, qu'il aurait fallu conserver en session pour pouvoir retirer l'entrée ensuite. Il n'y gagnait presque rien : un fichier n'est chargé qu'une fois par session. Le fichier déposé n'entre donc plus jamais dans la mémoire commune.

Un test le démontre en comptant les calculs : après l'effacement, les données d'un autre visiteur sont toujours servies par le cache, celles de la session effacée sont recalculées.

### 5. Résultat
**374 tests passent**.

---

## Étape 36 : Premiers pas en ligne

### 1. D'abord, le dépôt prend le nom du projet
Depuis l'Étape 34, le projet s'appelle Quitus, mais son dépôt GitHub portait encore son nom de travail, `PROJET_NETTOYAGE_AUTO`. Il devient **`johan-mac-59/quitus`**, et le renommage a été fait **avant** la mise en ligne : Streamlit Community Cloud se branche sur le nom du dépôt, et renommer après coup aurait obligé à reconfigurer l'application.

Des CV déjà envoyés portent l'ancienne adresse. Renommer un dépôt ne crée pas de copie : c'est le même dépôt, historique et tickets compris, qui change de nom, et GitHub redirige l'ancienne adresse vers la nouvelle, sans date d'expiration — vérifié après le renommage. La seule précaution est de ne jamais recréer un dépôt portant l'ancien nom : la redirection cesserait. Les liens de l'application, les commandes d'installation du README et le dépôt local pointent désormais vers la nouvelle adresse.

### 2. L'application est déployée
Quitus tourne désormais sur Streamlit Community Cloud, à l'adresse **https://quitus.streamlit.app/**, branchée sur la branche `main` du dépôt `johan-mac-59/quitus`. La version 1.0.0 ne sera confirmée qu'une fois les vérifications en ligne faites.

### 3. Le premier défaut vu en ligne : le logo et le thème
Le premier regard sur l'application en ligne a révélé deux défauts liés :

* **le thème était imposé** : la configuration fixait un thème clair, ce qui retirait au visiteur le choix entre clair, sombre et automatique ;
* **le logo pouvait contredire la page** : la variante était choisie côté Python d'après le thème que Streamlit croyait détecter. Au premier affichage, cette information peut être fausse — la documentation de Streamlit le signale —, et le logo sombre s'est affiché sur une page claire.

Le thème n'est plus imposé : chacun suit son système ou choisit dans le menu Settings.

Pour le logo, le choix a changé de côté. Streamlit applique déjà le thème réel au conteneur de l'application, sous la forme de la propriété CSS `color-scheme` — vérifié dans son code source. La fonction CSS `light-dark(claire, sombre)` permet alors au **navigateur** de choisir la couleur, au moment de l'affichage et à chaque changement de thème, sans attendre Python.

Les deux fichiers du logo ne diffèrent que par trois couleurs : le nom, la devise et un contour. Plutôt que de maintenir un troisième fichier à la main, l'application fusionne les deux variantes : chaque couleur qui diffère devient une valeur `light-dark()`. La couleur claire reste inscrite dans le SVG, si bien qu'un navigateur trop ancien pour `light-dark()` affiche simplement le logo clair. Le nom écrit dans la barre latérale suit la même règle.

Un piège a été évité en chemin : `light-dark()` n'accepte que des couleurs. Un contour absent de la variante claire devait donc s'écrire `transparent`, et non `none`, qui aurait invalidé toute la déclaration.

Un second piège, lui, n'a pas été évité : inséré par `st.html`, le logo a purement disparu. Cette fonction filtre son contenu avec DOMPurify en profil « HTML seul », qui supprime tout SVG. Le test en place ne l'avait pas vu : il vérifiait ce que Python envoyait, pas ce que le navigateur affichait. Le logo passe désormais par `st.markdown`, dont le rendu ne supprime pas le SVG, mis sur une seule ligne pour que le Markdown ne prenne pas ses lignes indentées pour un bloc de code. Un test interdit de revenir à `st.html` pour lui.

Pour ne plus se contenter de ce que Python envoie, le rendu a ensuite été vérifié dans un vrai navigateur : Chrome sans interface, piloté par son protocole de débogage, charge l'application en thème clair puis en thème sombre. Dans les deux cas, le logo est présent, avec les bonnes couleurs, ainsi que le nom de la barre latérale et les nouvelles tailles de texte.

### 4. Un haut de page resserré
Streamlit réserve 6rem au-dessus du contenu pour sa barre d'en-tête, qui ne porte pourtant que le menu, à droite : le logo flottait sous un grand vide. La marge est réduite à 2rem, l'en-tête rendu transparent pour que son fond ne couvre pas le logo, et le logo agrandi de moitié, de 300 à 450 pixels, occupe l'espace libéré. Il ne dépasse jamais la largeur de la page sur un écran étroit.

### 5. Un pixel de plus pour la lecture
Le texte courant passe de 16 à 17 pixels, les libellés et légendes de 14 à 15. Ce réglage passe par une feuille de style ciblée et non par l'option de taille de la configuration, qui aurait créé un thème personnalisé et supprimé de nouveau le choix clair/sombre.

### 6. Résultat
**378 tests passent**.

---

## Étape 37 : La feuille de route retrouve sa mémoire

### 1. Ce que l'historique révélait
Relue à la lumière de ses 23 versions successives dans git, la feuille de route avait perdu la trace de la moitié de ses réussites : **huit améliorations livrées en avaient été retirées sans jamais être inscrites comme livrées**. Le rapport de nettoyage (Étapes 11-12), l'enrichissement du profilage et son rapport HTML autonome (20, 21, 29), l'écrêtage optionnel (22), la casse ciblée (23, 26), le support JSON (25), le profilage après nettoyage (28) et la question du profilage conscient des types (35) avaient simplement disparu une fois faits. Quant au déploiement public, effectif depuis l'Étape 36, il figurait encore comme « prêt, reste à activer ».

Une liste qui efface ce qu'elle accomplit ne rend compte que de ce qui manque : elle sous-estime le projet autant qu'une autre le surestimerait.

### 2. Une nouvelle organisation
* **Les améliorations à faire viennent en tête**, classées par ordre d'importance et non plus selon un découpage technique/fonctionnel. Les deux défauts relevés après la mise en ligne passent en premier : les numéros de téléphone perdent leur `0` initial — une perte silencieuse, précisément ce que l'Étape 30 s'était engagée à ne plus laisser passer —, et le rapport HTML devient illisible en thème sombre.
* **Les améliorations livrées viennent ensuite**, toutes, dans l'ordre chronologique, chacune renvoyant à son étape dans ce journal.

### 3. Un nom qui dit ce que contient le fichier
Un fichier qui recense aussi ce qui est livré ne peut plus s'appeler « améliorations futures ». Il devient **`AMELIORATIONS.md`**, sans accent ni espace, comme `DEROULEMENT_PROJET.md`. Le renommage passe par `git mv`, si bien que l'historique du fichier reste consultable par `git log --follow`. Le README pointe vers le nouveau nom et annonce les vraies priorités, au lieu de la détection des notes et pourcentages, livrée depuis l'Étape 29.

### 4. Le dossier de travail suit le nom du projet
Après le dépôt GitHub (Étape 36), c'est au tour du dossier de travail local de quitter son nom d'origine, `PROJET_NETTOYAGE_AUTO`, pour devenir **`quitus`**. Le dossier a été copié en entier, historique git, données et branches locales compris, et non cloné : un clone n'aurait emporté ni les commits pas encore poussés, ni les données ignorées par git. Seul l'environnement virtuel a été recréé plutôt que copié, ses exécutables gardant en dur le chemin de l'ancien dossier. Les 378 tests passent dans le nouveau dossier.

La configuration de conteneur de développement (`.devcontainer/`) est retirée au passage.

---

## Étape 38 : Version 1.0.0, et premières retouches

### 1. Le jalon est atteint
L'Étape 32 avait fixé la règle : **la version 1.0 marque une application déployée et validée**, et l'étiquette `v1.0.0` ne serait posée qu'à ce moment-là. L'application est en ligne depuis l'Étape 36 ; les vérifications faites, le porteur du projet valide la version 1.0.0.

### 2. Ce qui a été fait
* l'étiquette git **`v1.0.0`** est posée sur ce commit : elle désigne le code réellement déployé, correctifs de sécurité de l'Étape 30 compris ;
* le verrou de dépendances `uv.lock`, resté à `0.1.0`, est remis en accord avec `pyproject.toml`, qui annonçait déjà `1.0.0`.

### 3. Premières retouches
Quelques finitions ont suivi l'étiquette :

* le paquet Python prend lui aussi le nom **`quitus`** : l'environnement virtuel s'affiche désormais sous ce nom dans VS Code ;
* le README donne **le lien de l'application en ligne** dès ses premières lignes et en tête du démarrage rapide, et son arborescence retrouve les fichiers réels du projet ;
* **GitHub et LinkedIn deviennent des boutons**, de la taille du bouton de soutien, et chaque bouton prend la couleur de son service ; la zone de dépôt, le vert de Quitus. Seul le noir de GitHub disparaissait sur fond sombre : il s'inverse par `light-dark()`, comme le logo. Le rendu a été contrôlé dans Chrome, en thème clair puis sombre ;
* l'onglet **Téléchargements guide le visiteur** : une introduction explique les deux formats de rapport (HTML pour lire, Markdown pour archiver), et chaque partie dit ce qu'elle contient — le résultat, le constat de départ, la vérification. Chaque bouton de téléchargement décrit son fichier dans une infobulle. Le rappel sur l'horodatage est aussi clarifié : la page ne propose que les fichiers du dernier nettoyage, et c'est sur l'ordinateur du visiteur que les essais successifs coexistent sans s'écraser.

**381 tests passent.**

---

## Étape 39 : Le zéro qui disparaissait

### 1. Le défaut
Le premier défaut inscrit dans la feuille de route après la mise en ligne : une colonne de numéros de téléphone ressortait du nettoyage en entiers. `0612345678` devenait `612345678`. Les codes postaux de l'Ain (`01000`) et les matricules (`00042`) subissaient le même sort.

C'est exactement le genre de perte que l'Étape 30 s'était engagée à ne plus laisser passer, et c'est la plus sournoise de toutes : **aucune valeur ne devient manquante**. Le recensement des valeurs vidées n'avait donc rien à signaler, et le profil après nettoyage voyait une colonne parfaitement typée. Toutes les garanties en place étaient respectées, et la donnée était pourtant abîmée.

### 2. Trois endroits, pas un
L'enquête, menée format par format, a montré que le zéro se perdait à trois endroits distincts :

* **au chargement d'un CSV** : `read_csv` lit `0612345678` en `int64` avant même que le nettoyage commence ;
* **au chargement d'un JSON ou d'un classeur Excel** : `read_json` convertit en nombres les chaînes qui en ont l'air, et `read_excel` fait de même avec une cellule pourtant saisie en texte ;
* **au nettoyage** : une colonne restée textuelle, comme celle d'un fichier JSON Lines, était convertie par `clean_types`.

Corriger un seul de ces endroits aurait laissé les deux autres ouverts, selon le format déposé.

### 3. Une règle unique
Un code se reconnaît à son écriture : **rien que des chiffres, éventuellement groupés par des espaces, et un zéro suivi d'un autre chiffre en tête**. `0`, `0.5` ou `0,25` ne sont pas concernés, puisque le zéro y est seul ou suivi d'un séparateur décimal. Une date comme `01/02/2024` non plus : la détection des dates doit pouvoir la lire. La première version de la règle s'en tenait au zéro suivi d'un chiffre. Essayée sur les fichiers du dossier `data/`, elle protégeait à tort toutes les colonnes de dates, d'où la précision.

Une seule valeur de ce genre suffit à garder toute la colonne en texte : un code ne se mêle pas à des nombres. Et la colonne est examinée **en entier**, et non sur les cent premières valeurs comme le reste de la détection numérique : un code situé à la ligne 500 doit protéger sa colonne autant qu'un autre.

La règle, `has_leading_zero`, vit dans le moteur, et les deux couches l'appliquent :

* **le chargement** lit d'abord le fichier tout en texte pour repérer les colonnes concernées, puis le relit en ne gardant que celles-ci en texte, pandas typant toutes les autres comme avant. Le CSV et l'Excel partagent ce mécanisme. Le JSON est lu sans inférence de type : ses nombres restent des nombres, ses chaînes des chaînes, et c'est le nettoyage, qui recense ce qu'il ne peut lire, qui convertit le reste ;
* **le nettoyage** écarte ces colonnes de la conversion numérique. Le contrôle après nettoyage applique la même règle : il ne les signale donc pas comme « encore convertibles », et l'invariant de l'Étape 29 reste tenu.

### 4. Ce qui ne peut pas être réparé
Un classeur Excel où le numéro a été saisi comme un nombre, puis simplement affiché avec un format à dix chiffres, ne contient plus le zéro : la cellule stocke `612345678`. Aucun outil ne peut le retrouver sans deviner, et Quitus ne devine pas.

### 5. Résultat
Un nouveau fichier de tests, `test_zero_initial.py`, couvre la règle, chacun des quatre formats au chargement, et le parcours complet jusqu'au fichier nettoyé. **404 tests passent.**

---

## Étape 40 : Un rapport qui garde sa feuille blanche

### 1. Le défaut
Deuxième défaut relevé après la mise en ligne : affiché dans l'application en thème sombre, le rapport HTML devenait illisible. Il a d'abord été reproduit dans Chrome, sur l'application lancée en local, avec un petit fichier déposé : titres, tableau et logo du rapport se fondaient dans le fond sombre de la page.

### 2. La cause
Le rapport ne fixait que la couleur de ses titres et le fond de ses en-têtes de tableau. Ni le fond de la page ni la couleur du texte courant n'étaient définis. Téléchargé et ouvert seul, il héritait du blanc par défaut du navigateur, et le défaut ne se voyait pas. Affiché dans l'iframe de l'interface web, il était **transparent** : derrière lui apparaissait le fond de l'application, sombre en thème sombre, sous un texte resté foncé.

### 3. Une feuille claire, quel que soit le thème
Deux solutions étaient possibles : suivre le thème de la page, ou en être indépendant.

Suivre le thème supposait que le rapport le connaisse. Or une iframe ne voit pas le `color-scheme` de la page qui l'accueille, et la détection côté Python est, l'Étape 36 l'a montré, peu fiable au premier affichage. Surtout, les graphiques du rapport sont des images sur fond blanc, et son logo est la variante claire : un rapport sombre aurait juxtaposé une page noire et des rectangles blancs.

Le rapport fixe donc lui-même **son fond blanc, la couleur de son texte et un `color-scheme: light`**, qui accorde aussi ses barres de défilement. Il se lit comme une feuille posée sur la page : identique en thème clair et en thème sombre, identique dans l'aperçu, dans la fenêtre « Ouvrir en grand » et dans le fichier téléchargé. Les deux rapports, avant et après nettoyage, partagent cet en-tête.

Le résultat a été contrôlé dans Chrome, en thème sombre, sur la même application locale : le rapport est lisible, logo compris. Au passage, la même vérification a confirmé l'Étape 39 dans l'interface web : la colonne de téléphones du fichier déposé garde ses `06`.

### 4. Résultat
Un test vérifie que le document fixe son fond, sa couleur de texte et son schéma de couleurs. **405 tests passent.**

---

## Étape 41 : Décider colonne par colonne

### 1. Le défaut de conception
Depuis l'Étape 16, l'utilisateur décide d'écrêter les valeurs aberrantes et de combler les valeurs manquantes. Mais il en décidait **pour tout le fichier à la fois** : deux cases à cocher, tout ou rien.

Or les deux principes qui justifient ces décisions sont, par nature, propres à chaque colonne. Un extrême peut être une erreur de saisie dans une colonne de poids, et une vente exceptionnelle bien réelle dans une colonne de montants. Une absence peut être un oubli dans une colonne et avoir un sens dans une autre : l'Étape 30 l'avait relevé sur les prix de carburants en rupture. Face à un fichier qui mêlait les deux cas, l'utilisateur n'avait que deux mauvais choix : tout corriger, et abîmer des données justes, ou ne rien corriger.

### 2. Le moteur apprend à cibler
`clip_outliers` et `clean_missing_values` reçoivent un paramètre `columns`, et `run_all_cleaning_steps` les paramètres `outlier_columns` et `missing_columns` qui le leur transmettent. La valeur `None` signifie toutes les colonnes : la ligne de commande, qui pose ses deux questions globales, garde ainsi exactement son comportement. Une colonne choisie mais disparue entre-temps, par exemple une colonne vide supprimée, est simplement ignorée.

Le format des statistiques ne change pas : seules les colonnes réellement traitées y figurent. Les rapports, le bilan console et l'interface n'ont donc rien eu à apprendre.

### 3. Deux listes au lieu de deux cases
Dans la barre latérale, chaque case à cocher devient une **liste de colonnes à choisir**. Chacune ne propose que les colonnes concernées, avec leur nombre de valeurs en cause : `montant (3)`, `note (6)`. Les montants encore stockés en texte y figurent aussi : leurs extrêmes, invisibles avant la correction des types, sont estimés comme ils l'étaient déjà pour l'ancienne case. Rien n'est choisi d'office : le principe « rien ne change sans vous » est inchangé. Quand aucune colonne n'est concernée, la liste est désactivée et le dit.

Le texte d'aide de l'écrêtage rappelle désormais qu'un extrême peut être réel, comme celui du remplissage rappelait déjà qu'une absence peut avoir un sens. Sur la page d'accueil, l'étape « Décider » annonce des traitements appliqués « colonne par colonne », et non plus « case par case ». Le README précise que la ligne de commande, elle, décide pour toutes les colonnes à la fois.

### 4. Vérifié dans le navigateur
Sur l'application locale, avec un fichier comportant un extrême dans les montants, un autre dans les poids, des poids et des villes manquants : seuls les montants ont été écrêtés, et le poids extrême conservé ; seuls les poids ont été comblés, et les villes manquantes laissées vides.

Au passage, un piège du serveur de développement : après une modification du moteur, Streamlit recharge le script de l'application mais peut garder l'ancien module en mémoire, et le premier essai a échoué sur un paramètre « inconnu ». Un redémarrage du serveur a suffi. En ligne, chaque déploiement repart de zéro.

### 5. Résultat
Les tests du moteur vérifient qu'une colonne non choisie reste intacte. Ceux de l'interface vérifient les colonnes proposées et leur nombre, et le résultat d'un parcours où une colonne sur deux est traitée. Les tests existants pilotent désormais les listes au lieu des cases. **412 tests passent.**

---

## Étape 42 : Un seuil à la mesure de chaque colonne

### 1. La limite qui restait
L'Étape 41 permet de choisir les colonnes à écrêter. Mais une colonne choisie était toujours écrêtée au même seuil : **1,5 écart interquartile** au-delà des quartiles, la règle de Tukey, figée dans le code depuis l'Étape 3.

Ce seuil standard convient à des mesures stables. Il est trop sévère pour des montants à forte dispersion, où une grosse commande est rare sans être fausse : à 1,5, elle était ramenée à la borne comme une faute de frappe. L'utilisateur ne pouvait que renoncer à écrêter la colonne, et laisser passer avec elle les vraies erreurs.

### 2. Un seuil par colonne, dans le moteur
Le calcul des bornes, jusque-là écrit deux fois avec son `1.5` en dur, devient une fonction unique, `iqr_bounds`, qui prend le seuil en paramètre. Le seuil standard devient une constante nommée, `SEUIL_IQR`. `clip_outliers` reçoit un seuil par colonne, et `run_all_cleaning_steps` le lui transmet ; une colonne sans seuil précisé garde 1,5. Une nouvelle fonction, `count_outliers`, compte les valeurs hors bornes pour un seuil donné, y compris dans une colonne de montants encore stockée en texte, dont elle estime la valeur numérique.

Au passage, cette estimation retire désormais tous les symboles monétaires et séparateurs de milliers reconnus par la conversion, et non plus seulement `€` et `$` : une colonne en livres sterling ou à espaces de milliers était sous-estimée.

Le profilage, lui, garde le seuil standard. C'est un diagnostic : il doit rester comparable d'un fichier à l'autre et d'un nettoyage à l'autre. Après un écrêtage à 3, le profil de contrôle peut donc encore signaler des valeurs entre 1,5 et 3 écarts : elles ont été conservées volontairement.

### 3. Voir l'effet avant de décider
Dans l'interface web, chaque colonne choisie pour l'écrêtage reçoit un curseur de seuil, de 0,5 à 5. Sous le curseur, le nombre de valeurs hors bornes **se met à jour à chaque déplacement** : l'utilisateur voit ce que son seuil épargne avant de lancer le nettoyage.

Cette réactivité a demandé un changement de structure. Les options vivaient dans un formulaire Streamlit, qui fige ses widgets jusqu'à sa soumission : un curseur n'y aurait rien pu afficher en direct. Le formulaire devient un simple conteneur encadré, au rendu identique, et son bouton de soumission un bouton ordinaire.

### 4. La preuve cite le seuil
Un écrêtage à 3 écarts ne dit pas la même chose qu'un écrêtage à 1,5. Le seuil appliqué est donc consigné dans les statistiques du nettoyage, et le rapport de nettoyage l'affiche dans une nouvelle colonne de son tableau des valeurs aberrantes.

### 5. Et en ligne de commande
La ligne de commande, qui décide pour toutes les colonnes à la fois, reçoit une option `--seuil-iqr` : un seuil commun, 1,5 par défaut, virgule décimale acceptée, valeur nulle ou négative refusée.

### 6. Vérifié dans le navigateur
Sur l'application locale, avec une colonne de montants comportant un extrême massif et un extrême modéré : au seuil 1,5, le curseur annonce deux valeurs hors bornes ; monté à 4, il n'en annonce plus qu'une. Après nettoyage, l'extrême modéré est conservé, l'extrême massif écrêté, et le rapport indique le seuil 4. En ligne de commande, l'échantillon versionné donne trois valeurs écrêtées au seuil 1,5 et aucune au seuil 3.

### 7. Résultat
Les tests couvrent les bornes, le décompte, l'écrêtage colonne par colonne selon des seuils différents, la mention du seuil dans le rapport, l'option de la ligne de commande et, dans l'interface, le curseur de chaque colonne choisie et le seuil effectivement appliqué. **422 tests passent.**

---

## Étape 43 : Toutes les notes sur la même échelle

### 1. La limite de l'étape 29
Depuis l'Étape 29, une note fractionnaire est convertie en son **numérateur** : `17/20` devient `17`. Ce choix avait une bonne raison, toujours valable : une colonne qui mêle `5` et `5/5` doit donner deux fois 5, et non 5 et 1.

Mais il supposait que toutes les notes d'une colonne partagent la même échelle. Une colonne mêlant `17/20` et `4/5` donnait 17 et 4 : deux nombres côte à côte, incomparables, dont la moyenne ne voulait plus rien dire. Le défaut était silencieux, la colonne ressortant parfaitement typée.

### 2. L'échelle dominante
Pour chaque colonne de notes, l'échelle retenue est le **dénominateur le plus fréquent**. À égalité, c'est le plus grand qui l'emporte, car il préserve le mieux la finesse des notes : ramener des notes sur 20 à une échelle sur 4 en écraserait les nuances. Les dénominateurs nuls sont ignorés.

Chaque note est ensuite exprimée sur cette échelle :

* une note déjà sur l'échelle garde son numérateur, comme avant : une colonne à échelle unique ne change pas d'un iota ;
* une note sur une autre échelle y est ramenée : parmi des notes sur 20, `4/5` devient `16` ;
* un nombre nu, sans dénominateur, est tenu pour déjà exprimé sur l'échelle de la colonne, ce qui conserve le comportement voulu pour `5` et `5/5`.

### 3. Rien ne change en silence
Ramener une note à une autre échelle change la valeur affichée. Fidèle au principe posé à l'Étape 30, l'opération est donc toujours déclarée. Pour chaque colonne concernée, le moteur recense l'échelle retenue, le nombre de notes ramenées et des exemples (`4/5 → 16`), dans une nouvelle statistique, `grades_rescaled`. On la retrouve à trois endroits :

* dans le **rapport de nettoyage**, un tableau sous les conversions de types ;
* dans le **bilan console** de la ligne de commande ;
* dans l'**onglet Nettoyage** de l'interface web, un encadré suivi du même tableau, et une ligne dans les opérations effectuées.

Les exemples sont écrits à la française, avec une virgule décimale : `4,5/5 → 3,6`.

Sur la page d'accueil, l'exemple de notes montre désormais le cas mêlé, `"17/20", "4/5"` donnant `17 · 16`, et le README décrit la nouvelle règle.

### 4. Vérifications
Appliqué aux fichiers du dossier `data/`, le nettoyage ne ramène aucune note : aucun d'eux ne mêle plusieurs échelles, et rien n'y change. Dans le navigateur, sur l'application locale, un fichier mêlant notes sur 20, notes sur 5 et un nombre nu ressort entièrement sur 20, et l'onglet Nettoyage affiche l'encadré et le détail des deux notes ramenées.

### 5. Résultat
Les tests couvrent les échelles mêlées, l'échelle unique inchangée, l'égalité de fréquence, la virgule décimale, le dénominateur nul, la statistique transmise par le pipeline, la section du rapport et l'encadré de l'interface. **430 tests passent.**

---

## Étape 44 : Parquet rejoint les formats acceptés

### 1. Le cinquième format
CSV, Excel, JSON et JSON Lines étaient pris en charge ; Parquet, envisagé dès les premières pistes d'amélioration, ne l'était pas. C'est pourtant le format d'échange courant des outils de données modernes : colonnes typées, compression, lecture rapide.

Le chargement suit le modèle des autres formats : une fonction orientée octets, `_parquet_from_bytes`, que l'interface web appelle directement, et une enveloppe orientée chemin pour la ligne de commande. Un fichier sans extension est reconnu à sa signature, `PAR1`, qui l'ouvre et le ferme. Un fichier corrompu lève une erreur explicite plutôt qu'un message de bas niveau.

Parquet stocke ses types : un nombre y est déjà un nombre, une date une date. Le nettoyage n'a donc à corriger que ce qui y est resté du texte, comme des montants écrits `1 200,50 €`, et la protection des codes à zéro initial de l'Étape 39 s'applique à ses colonnes textuelles comme aux autres.

Une seule conversion est faite d'office : une colonne **catégorielle** devient une colonne ordinaire. Une catégorie n'accepte que ses modalités d'origine ; la casse uniformisée ou une valeur comblée y auraient été refusées.

La lecture repose sur `pyarrow`. Il était déjà installé, comme dépendance de Streamlit, mais le projet s'en sert désormais directement : il est donc déclaré dans `pyproject.toml`, `requirements.txt` et le verrou `uv.lock`.

### 2. Un défaut plus ancien, révélé en chemin
Parquet, comme JSON, peut porter dans une cellule une liste ou un objet. En testant ce cas, un défaut antérieur est apparu : **un JSON imbriqué se chargeait, mais son profilage échouait**, sur une erreur `unhashable type: 'list'`. Le profilage compte et compare des valeurs, ce qu'une liste ne permet pas. L'Étape 19 avait annoncé la prise en charge des JSON imbriqués : elle tenait pour le chargement, pas pour la suite du parcours.

La correction est faite une fois, à la sortie du chargement, pour tous les formats : une cellule structurée (liste, objet, tableau) est écrite en **texte JSON**. Son contenu est entièrement conservé, il reste lisible, et il devient comparable : deux lignes identiques sont reconnues comme des doublons.

### 3. Partout où les formats sont cités
La zone de dépôt accepte l'extension `.parquet`, et son aide, la page d'accueil, la description de la ligne de commande, celle du paquet et le README citent le nouveau format. Le tableau de robustesse du README indique le sort des cellules structurées.

### 4. Vérifié dans le navigateur
Sur l'application locale, un fichier Parquet de clients est déposé, analysé puis nettoyé. Les montants en texte deviennent des nombres, les téléphones gardent leur zéro initial, les listes d'étiquettes s'affichent en texte JSON, la date garde son type, et le doublon révélé par l'uniformisation de la casse est supprimé.

### 5. Résultat
Les tests couvrent les types conservés, la catégorie rendue modifiable, les cellules structurées, la détection sans extension, le chargement par chemin, le fichier corrompu ou vide, le profilage d'un JSON imbriqué et, dans l'interface, le dépôt puis l'analyse d'un fichier Parquet. **440 tests passent.**

---

## Étape 45 : Une documentation API qui ne peut pas mentir

### 1. Ce qui restait à faire
La feuille de route demandait un document technique décrivant l'interface et les paramètres de chaque fonction. Elle le disait à moitié fait : toutes les fonctions publiques avaient une docstring, et un test l'imposait. Restait à assembler le document.

### 2. Générer plutôt qu'écrire
Un document écrit à la main aurait été périmé au premier changement de signature. Les étapes précédentes en donnaient la preuve : en quelques heures, `run_all_cleaning_steps` avait reçu trois paramètres, `clip_outliers` deux, `clean_types` un.

Le document, `docs/API.md`, est donc **généré depuis le code** par un script, `docs/generer_api.py`. Pour chacun des neuf modules de `src/`, dans l'ordre du parcours d'un fichier (chargement, profilage, nettoyage, rapports, utilitaires), il reprend la présentation du module, puis chaque fonction, classe et méthode publique : sa signature, telle qu'écrite dans le code, et sa docstring. Les sections au format Google (`Args`, `Returns`, `Raises`) deviennent des listes titrées en français : paramètres, retour, exceptions. Un sommaire relie le tout.

Trois détails de mise en œuvre :

* les annotations sont lues **comme texte**, grâce au module `annotationlib` de Python 3.14 : la signature affiche `pd.DataFrame`, comme le code, et non `pandas.core.frame.DataFrame` ;
* deux fonctions du module `marque` sont enveloppées par un cache (`lru_cache`), qui les masque à un inventaire naïf : le générateur remonte à la fonction d'origine ;
* `self` est omis des méthodes, et les classes n'affichent pas de type de retour.

### 3. Un test qui interdit la dérive
`tests/test_documentation_api.py` vérifie que le fichier versionné est **identique** à ce que produirait le générateur. Une docstring modifiée sans régénérer le document fait échouer la suite, avec la commande à lancer. Le test vérifie aussi que chaque élément public a sa section, et qu'un nouveau module de `src/` ne peut pas être oublié.

### 4. Les docstrings complétées
Assembler le document a rendu visibles les docstrings les plus anciennes, réduites à une ligne. Une docstring existait partout, comme l'imposait le test, mais elle ne disait pas toujours tout. Onze ont été complétées, fidèlement au code : paramètres et retour de `clean_empty_columns`, `clean_whitespace`, `fix_numeric_types`, `clean_duplicates`, retour de `clean_case_sensitivity` et de `DataProfiler.run_analysis`, méthodes de `CleanLogger` et `generate_and_print_report`. Celle de `run_all_cleaning_steps` ne mentionnait ni `profile_info` ni ce que la fonction renvoie ; elle décrit désormais l'un et l'autre, ainsi que la répétition des premières étapes jusqu'à stabilisation.

### 5. Le README à jour
Le README renvoie à la documentation API sous le tableau des modules, et son arborescence fait apparaître le dossier `docs/`. Sa section « Évolutions prévues » citait encore comme priorités les trois défauts corrigés aux Étapes 39 à 41 ; elle annonce désormais ce qui reste à venir.

### 6. Résultat
**444 tests passent.**

---

## Étape 46 : Ce que les tests ne voient pas

Une étape en deux temps : un allègement du journal et de la documentation, puis un essai de l'application en local, avant d'en pousser les dernières étapes en ligne. Le second a produit quatre corrections, et une leçon.

### 1. Un journal plus court, une mémoire mieux gardée
Le journal avait grossi par accumulation : cinquante et une étapes, dont plusieurs ne traitaient ni un choix technique, ni une innovation, ni une modification du projet. Une passe a été faite étape par étape, avec ce seul critère.

* **Supprimé** : un glossaire pédagogique, une liste de limitations déjà couverte par la feuille de route, deux récapitulatifs finaux, et un audit de présentation qui parlait de communication et non du projet.
* **Fondu** : les étapes qui racontaient la même chose en deux temps. Deux étapes de tests unitaires consécutives, le constat d'échecs de tests et sa correction, puis les corrections du moteur numérique et leurs tests de non-régression forment désormais trois étapes au lieu de six.
* **Renuméroté** : le journal compte quarante-cinq étapes avant celle-ci, sans trou, et chaque renvoi à une étape a été recalculé, dans le journal comme dans `AMELIORATIONS.md` et la configuration. Les titres suivent une règle unique : seule la première lettre est en majuscule, hormis sigles et noms propres.

Rien de ce qui était supprimé ne devait se perdre. Les pistes qui y figuraient et que la feuille de route ignorait y ont été reportées, qu'elles soient faites ou non : validation après nettoyage et mode multi-passes (livrés), règles métier d'alerte, seuils d'alerte propres à chaque profil, stabilité statistique après nettoyage, contrat commun aux deux profileurs, méthode alternative sur les très petits échantillons, sources et destinations SQL. Une idée oubliée est une idée perdue : la feuille de route est l'endroit où elle reste visible.

### 2. Un glossaire à part
Le contenu pédagogique retiré du journal (typage, DataFrame, encodages, quartiles) a trouvé sa place : `docs/GLOSSAIRE.md`, un aide-mémoire à l'usage d'un lecteur novice, ou du porteur du projet quand il veut se rappeler à quoi sert une notion. Il couvre les données, les statistiques, le nettoyage propre à Quitus et l'outillage, et renvoie à `docs/API.md` pour la description exacte des fonctions. Le journal raconte des décisions ; le glossaire explique des mots : ce ne sont pas les mêmes lecteurs.

### 3. L'essai local, et ce qu'il a révélé
Avant de pousser les étapes 39 à 45 en ligne, l'application a été lancée en local par le porteur du projet, sur l'échantillon synthétique. Quatre anomalies en sont sorties. **Aucun des 444 tests ne les avait vues.**

**a) Des graphiques qui montraient le désordre après le nettoyage.** Dans l'onglet Graphiques, la répartition de `date_reservation` affichait plusieurs formats de dates, ce qui n'était « pas normal » : le nettoyage convertit bien cette colonne en vraies dates. Vérification faite sur l'échantillon, la colonne passe de texte à `datetime64`. Le graphique montrait en réalité les **données brutes** : le sélecteur « Jeu de données », qui propose les brutes et les nettoyées, s'ouvrait toujours sur les premières, même après un nettoyage. Il s'ouvre désormais sur le fichier nettoyé quand il existe. Aucune erreur de calcul, seulement une présentation qui induisait en erreur, et c'est précisément ce qu'un test fonctionnel ne regarde pas.

**b) Des identifiants tracés comme des catégories.** Les dates ont disparu de la liste des colonnes à représenter une fois converties ; les identifiants, eux, y restaient. Une barre par identifiant, chacun une seule fois : un graphique sans la moindre information. Une colonne dont au moins 90 % des valeurs sont distinctes est désormais écartée des graphiques, avec une ligne qui nomme les colonnes écartées. La règle vit dans `plot_factory`, si bien que l'interface et le rapport HTML la partagent. En deçà de vingt valeurs, elle ne s'applique pas : sur un petit fichier, le jugement serait trop fragile. Effet de bord assumé : une colonne de noms ou de courriels, elle aussi presque toute distincte, est écartée de la même façon.

**c) Un identifiant plus présent que les autres.** En regardant les barres, le porteur du projet a remarqué qu'un identifiant revenait deux fois. L'enquête a montré que ce n'était pas un défaut du graphique : `R37331` figure bien deux fois après nettoyage, sur des lignes **différentes** (autre date, autre ville, autre montant). Le nettoyage ne retire que les doublons exacts, et ne peut pas deviner laquelle des deux lignes est la bonne. C'est une anomalie réelle des données, que Quitus ne signale pas encore. Elle est inscrite à la feuille de route : détecter les identifiants répétés sur des lignes différentes et les déclarer dans le profil, avec les lignes concernées. Même principe qu'à l'Étape 30 : ce que l'outil ne peut pas trancher, il doit au moins le dire.

**d) Un bouton qui ne répondait à rien.** Dernière remarque : on pouvait cliquer sur « Nettoyer » à l'infini, sans que rien n'indique qu'il s'était passé quoi que ce soit. Le nettoyage avait bien lieu, mais le résultat se lisait dans un autre onglet, et rien ne le disait. Deux changements :

* une notification confirme la fin du nettoyage et renvoie à l'onglet du résultat ;
* le bouton s'éteint tant que les choix de colonnes et de seuils sont ceux du dernier nettoyage, et un encadré vert le dit. Il se rallume dès qu'un choix change, ou qu'un nouveau fichier est déposé. Relancer le même nettoyage ne produirait rien de nouveau : le bouton n'a plus à l'offrir.

Le bouton ayant déjà été dessiné quand le nettoyage s'exécute, le script est relancé une fois terminé pour qu'il s'éteigne aussitôt. En cas d'échec, il reste actif, et l'erreur s'affiche comme avant.

### 4. Le rôle de l'humain
Ces anomalies ont une chose en commun : le code faisait exactement ce qu'on lui avait demandé. Le nettoyage convertissait bien les dates ; le sélecteur proposait bien les deux jeux ; le graphique des identifiants était correct ; le bouton nettoyait. Les tests le confirmaient tous, et passaient. Ce qui clochait, c'était l'**usage** : ce qu'une personne comprend en regardant l'écran, et ce qu'elle attend après un clic.

Un test vérifie ce qu'on a pensé à vérifier. Il ne peut pas se demander si un graphique est trompeur, si un message manque, si une barre unique a un sens. C'est la leçon de l'Étape 30, où un utilisateur réel avait trouvé en une séance ce que 279 tests n'avaient pas vu ; elle se confirme ici avec 444. Les tests protègent contre le retour d'un défaut connu ; le regard humain découvre les défauts qu'on ne savait pas chercher. Les deux sont nécessaires, et le second reste primordial.

Chaque anomalie, une fois repérée par l'humain, est devenue un test : le jeu affiché par défaut, l'exclusion des identifiants, l'extinction et le rallumage du bouton. Le porteur du projet détecte, les tests mémorisent.

### 5. Version 1.1.0
Le porteur du projet fait de cette série la **version 1.1.0** : une mise en production qui reprend tout ce qui a changé depuis la 1.0.0, soit les Étapes 39 à 46. La 1.0.0 reste celle de l'Étape 38 et de son étiquette git `v1.0.0`, qui désigne le code déployé à ce moment-là, et n'est pas modifiée. Comme à l'Étape 32, l'étiquette `v1.1.0` ne sera posée qu'une fois l'application mise en ligne et validée : le numéro est inscrit dans `pyproject.toml`, `uv.lock` et le README, l'étiquette attend le déploiement.

### 6. Résultat
**451 tests passent**, contre 444. Rien n'est encore poussé en ligne : l'essai local se poursuit avant la mise en production.

---

## Étape 47 : Le validateur, des contraintes que l'utilisateur énonce

Première étape de la future version 1.2. L'amélioration n°1 de la feuille de route, un module de validation, n'avait jamais été commencée, et la première partie du travail a été de décider ce qu'il devait être.

### 1. Un emplacement qui n'a jamais existé
L'Étape 9 annonçait une méthode `detect_quality_issues` « prête à accueillir nos prochaines règles métier ». Elle n'a jamais été écrite : le code n'en contient aucune trace. Tous les contrôles existants (90 % de manquants pour une ligne à supprimer, 30 % pour une ligne à inspecter, 80 % de dates lues, années 1900 à 2100, seuil IQR de 1,5) sont fixés dans le code, et aucun schéma ni aucune règle fournie par l'utilisateur n'est lu nulle part. La seule structure d'alerte, celle de `_analyze_row_quality`, ne porte que sur les lignes.

### 2. Réfléchir avant d'écrire
Le validateur a d'abord été discuté, sans une ligne de code, selon trois questions.

* **D'où viennent les règles ?** Une première idée était de faire détecter les anomalies par une IA. Le besoin, une fois précisé, est autre : l'utilisateur énonce ses contraintes au vu des données (longueur, minimum, maximum, comparaison entre deux colonnes) et les accumule, et Quitus remonte les anomalies. Des règles écrites à la main restent à la portée d'un utilisateur qui n'est pas développeur si elles se saisissent par formulaire ou par questions, jamais en JSON.
* **Quelle IA, si elle est utile ?** Un tour des options a écarté deux pistes : un modèle dans le navigateur ou dans Streamlit (limites de mémoire de l'hébergement, et un modèle hébergé par le projet ferait de toute façon transiter les données par son serveur). Le besoin étant précis, aucun grand modèle de langage n'est requis : une grammaire, un petit modèle spécialisé ou la similarité de chaînes suffisent pour ce qui est envisagé. Cela reste à une étape ultérieure.
* **Que fait le validateur d'une violation ?** Il la signale, il ne la corrige pas. Les corrections, sous accord explicite, sont repoussées à la version 1.3. C'est la règle « pas de perte silencieuse » prolongée : ce que l'outil ne peut pas trancher, il le dit.

### 3. Une règle est un dictionnaire
Le seul contrat du module est le format de règle : `{id, type, colonnes, parametres, libelle}`, sérialisable en JSON. Un formulaire web, un menu de terminal, un fichier enregistré et, plus tard, un traducteur de phrases en langage courant produisent tous la même chose, et `valider` la traite de la même façon. Sept types : plage (nombres ou dates), longueur, format (e-mail, code postal, téléphone français, SIREN et SIRET avec somme de contrôle de Luhn, ou expression régulière), valeurs autorisées, valeur obligatoire, valeur unique (sur une ou plusieurs colonnes) et comparaison entre deux colonnes.

Les garanties du module sont testées une à une.

* **Il ne modifie rien** : ni le DataFrame, ni les règles reçues (`tests/test_validator_ne_modifie_rien.py`).
* **Une cellule vide n'est jamais une violation**, sauf pour la règle « valeur obligatoire » : le manque relève du profilage.
* **Une valeur illisible n'est pas ignorée en silence** : sur une règle numérique ou de dates, elle n'est ni comptée comme violation, ni oubliée, mais déclarée à part (`non_evaluables`). Valeurs vérifiées, illisibles et vides font toujours le total des lignes.
* **Une règle ne fait jamais échouer les autres** : mal formée, ou visant une colonne absente, elle est rapportée en erreur et le reste est évalué.
* **Les lignes fautives sont des étiquettes d'index**, plafonnées à cent avec cinq exemples, pour rester lisibles et se retrouver dans le fichier d'origine.

### 4. Un choix stratégique : l'ergonomie dans l'interface web
Le terminal a d'abord reçu un menu de questions pour saisir les contraintes. Il a été retiré le jour même, sur décision du porteur du projet, et ce choix est consigné ici parce qu'il oriente la suite.

* **Le validateur complet et interactif vit dans Streamlit.** Formulaire d'ajout, retour immédiat sur chaque règle, accumulation, export du fichier de règles : c'est là que l'ergonomie se travaille, pour un public qui n'est pas forcément technique.
* **Le terminal rejoue un fichier de règles** (`--regles`). Il s'adresse à des développeurs et des informaticiens, pour qui un fichier JSON est un moyen naturel, et à l'automatisation (`--non-interactif`, `--oui-a-tout`). Le fichier se crée dans l'interface web, qui l'exporte : l'utilisateur n'écrit jamais de JSON à la main.
* **Évolution : un module partagé, facultatif dans le terminal.** Une idée du porteur du projet a nuancé le choix : plutôt que de renoncer à toute création de règles en terminal, la description du formulaire (champs de chaque type de règle, lecture des valeurs saisies, construction et contrôle) est écrite une fois dans `src/`, et chaque façade l'affiche à sa manière. Le terminal la propose à la demande, par une option (`--creer-regles`) qui appelle un module à part : `main.py` ne reçoit que quelques lignes, jamais un menu. C'est l'objet de l'étape suivante.
* **Pourquoi.** Maintenir deux saisies interactives en parallèle alourdissait `main.py` (568 lignes, dont 280 pour le seul validateur) et en dégradait la lisibilité, pour un bénéfice faible : l'application web tourne aussi en local (`uv run streamlit run streamlit_app.py`), donc la confidentialité n'exige pas le terminal. La valeur du projet est dans `src/`, que les deux façades se partagent, et qu'on peut réinjecter ailleurs. On concentre l'effort sur l'ergonomie d'une application plutôt que sur la manière de construire la même chose dans un terminal.

Les contraintes viennent **en dernier**, après le nettoyage, son rapport et le nouveau profilage, celui qui permet de lire les données déjà propres et de repérer les anomalies métier qu'aucune machine ne peut deviner (une date de départ avant l'arrivée, un âge de 130 ans). Le rapport de nettoyage, déjà écrit à ce moment, est réécrit au même nom avec la section « Contraintes » ; si l'utilisateur l'avait refusé, aucun fichier n'est créé par ce biais. Un fichier de règles introuvable ou invalide est signalé à la fin, avec un code de sortie 1 ; le nettoyage, lui, est fait et sauvegardé, et le message le dit. Les contraintes ne limitent jamais le nettoyage : un test vérifie que le fichier nettoyé est identique avec ou sans règles.

### 5. Erreurs rencontrées
* **Des dates ISO lues à l'envers.** Le premier essai a signalé une violation de `debut <= fin` sur `2024-01-05` et `2024-02-01`, qui n'en est pas une. Avec l'option « jour d'abord » de pandas, `2024-01-05` est lu comme le 1er mai. Les dates ISO se lisent désormais sans cette option, le reste avec ; les bornes saisies par l'utilisateur suivent le même chemin. Un test dédié nomme ce piège.
* **Une cellule manquante qui n'est plus du texte.** Avec pandas 3, le type texte par défaut conserve les valeurs manquantes au lieu de les transformer en chaîne « nan », et la somme de contrôle d'un SIRET échouait sur un flottant. Le contrôle accepte désormais ce cas.
* **Un `2.0` pour un identifiant.** Une colonne d'entiers avec une valeur manquante est lue en flottants, et les exemples affichaient `2.0`. Ils affichent `2`.
* **Une hypothèse fausse dans le plan.** Le plan supposait qu'il fallait ajouter le module à la liste de `test_integrite_source.py`. Seule la liste des fichiers de la racine est explicite : celle de `src/` est un parcours du dossier. Le module a été pris en compte sans rien changer ; seule la liste de la documentation API (`docs/generer_api.py`) devait l'inclure.

* **Une question posée trop tôt, puis un menu de trop.** Le premier essai en terminal par le porteur du projet a montré que le menu des contraintes s'ouvrait avant même le profilage : on demandait d'énoncer des règles sur des données que l'utilisateur n'avait pas encore vues. Aucun test ne l'avait signalé : le menu fonctionnait comme prévu. Il a été déplacé trois fois (après le profilage, après un nettoyage « léger » calculé sans être montré, puis après le nettoyage, son rapport et le nouveau profilage), avant que la vraie question soit posée : un menu interactif a-t-il sa place dans le terminal ? Réponse : non, voir le choix stratégique ci-dessus. Le menu et ses tests sont supprimés. Le temps passé à le placer est la raison du choix.

Une coquille du journal a aussi été corrigée à l'Étape 9, où un mot chinois s'était glissé dans une phrase.

### 6. Le rapport
Le rapport de nettoyage gagne une section « 3. Contraintes », sous le détail des opérations : un tableau règle par règle, avec les violations avant et après nettoyage, puis le détail de l'état final (lignes et exemples). Elle rappelle que les contraintes sont signalées, jamais corrigées. Le paramètre est facultatif (`contraintes`, de `render` à `generate_enhanced_report`) : sans règle, le rapport est strictement identique à celui d'avant, ce qu'un test vérifie. Le tableau montre aussi ce que le nettoyage a réglé par effet de bord : une valeur obligatoire manquante avant, respectée après la suppression d'une ligne en doublon. Une barre verticale dans une règle (un motif `A|B`) est protégée pour ne pas casser le tableau.

### 7. Ce qui reste
L'onglet de l'interface web, puis les pistes de la feuille de route : contraintes en langage courant, règles suggérées par le profil, détection des anomalies orthographiques, corrections proposées. Le numéro de version n'est pas modifié : la 1.2 attend un validateur opérationnel et déployé.

### 8. Résultat
**545 tests passent**, contre 451 : 94 tests nouveaux, dont ceux de la garantie « ne modifie rien », du menu, de `main()` de bout en bout et de la section du rapport. `docs/API.md` est régénéré et couvre `validator`.

---

## Étape 48 : Créer des règles, une fois, pour deux façades

Suite de l'Étape 47. Le validateur existe et se rejoue par fichier ; il reste à permettre de créer les règles sans écrire de JSON, dans l'interface web et, à la demande, dans le terminal, sans écrire deux fois la même chose.

### 1. Ce qui se partage, et ce qui ne se partage pas
Streamlit et un terminal ne partagent pas leurs widgets. Ils partagent en revanche **ce qu'on demande** : quels champs chaque type de règle exige, comment lire ce qui est saisi (un nombre, une date, une liste séparée par des points-virgules), comment construire la règle et la contrôler. `src/saisie_regles.py` décrit cela une fois ; chaque façade n'a plus qu'à l'afficher à sa manière. Il ne connaît aucune interface et ne pose aucune question.

* **`TYPES_DE_REGLE`** décrit, pour chacun des sept types, un libellé lisible, le nombre de colonnes attendu (une, deux, ou autant qu'on veut pour « valeurs toutes différentes ») et ses champs. Un champ a un nom, un libellé, un genre (borne, entier, texte, liste, choix), un caractère obligatoire ou non, ses choix éventuels et une phrase d'aide avec un exemple.
* **`construire_regle`** convertit les textes saisis, appelle `nouvelle_regle` puis `verifier_regle`, et renvoie des messages en français plutôt qu'une exception : l'interface les affiche et laisse corriger. Tous les problèmes sont rapportés d'un coup, pas un à la fois. Un champ vide signifie « aucun » (aucun minimum, par exemple), jamais une erreur.
* **`regles_vers_texte`**, dans le validateur, produit le JSON en mémoire. L'interface web en a besoin pour proposer l'export au téléchargement sans rien écrire sur le serveur ; `sauver_regles` s'en sert à son tour, si bien que le fichier et le téléchargement sont identiques.

Un test garde la description alignée sur le moteur : un type de règle ajouté au validateur sans formulaire fait échouer la suite, de même que des choix de formats ou d'opérateurs qui divergeraient.

### 2. Le terminal, à la demande
`--creer-regles` propose, à la fin du traitement (après le nettoyage, son rapport et le nouveau profilage), de définir des contraintes par questions. Le dialogue vit dans un module à la racine, `saisie_terminal.py`, et non dans `main.py` : `src/` ne pose aucune question, et `main.py`, qui avait atteint 568 lignes avec un premier menu, n'a reçu que l'option, l'appel et l'enregistrement du fichier.

* **Il ne décide de rien.** Le type de règle, les champs à demander, la lecture des valeurs et la construction viennent de `src/saisie_regles.py` ; le module se borne à poser les questions, avec un retour immédiat sur le fichier nettoyé après chaque règle ajoutée.
* **Il est facultatif.** Sans l'option, aucune question n'est posée sur les contraintes ; avec `--oui-a-tout` ou `--non-interactif`, l'option est refusée par le parseur, puisqu'elle pose des questions. Un fichier de règles invalide, signalé à la fin, ne déclenche aucune question.
* **Il s'ajoute à `--regles`.** Les règles saisies complètent celles du fichier, et l'ensemble est enregistré dans le répertoire des rapports, à rejouer avec `--regles` ; le rapport de nettoyage est réécrit avec la section « Contraintes ». Aucune règle saisie, aucun fichier enregistré.
* **Un champ « si vide ».** En écrivant le dialogue est apparu un détail absurde : demander un motif personnalisé à quelqu'un qui vient de choisir un format connu. L'indication `si_vide` (« ne demander ce champ que si cet autre est resté vide ») a été ajoutée à la description partagée, pour que les deux façades la respectent.
* **Un défaut de test.** La fonction de saisie par défaut était liée au vrai `input` dès la définition de la fonction : les tests qui le remplaçaient n'agissaient pas dessus et se bloquaient sur le clavier. Elle est désormais résolue à l'appel. Un garde-fou vérifie aussi que `main.py` reste léger (plus de fonction de menu, moins de 450 lignes).

### 3. L'onglet « Contraintes » de l'interface web
Huitième onglet, placé après « Après nettoyage » : on y définit des contraintes sur les données déjà propres, puis on lit le verdict. Avant le nettoyage, il invite à nettoyer, comme l'onglet de contrôle : c'est sur des données propres et lisibles qu'on repère les anomalies métier.

* **La saisie suit la description partagée.** Le formulaire choisit un type de règle, puis affiche ses champs d'après `src/saisie_regles.py` : un sélecteur pour un choix, une zone de texte sinon, une sélection multiple de colonnes pour l'unicité, deux listes de colonnes pour une comparaison. Le motif personnalisé disparaît dès qu'un format connu est choisi (`si_vide`). Les messages d'erreur de `construire_regle` s'affichent tels quels. Ni `st.form` ni conteneur figé : les champs doivent suivre le type choisi immédiatement, la même raison que pour les réglages de nettoyage de la barre latérale. Un compteur de génération entre dans les clés des widgets pour les vider après un ajout.
* **Le verdict se lit tout de suite.** Pour chaque règle : son verdict avant et après nettoyage (le résumé est partagé avec le rapport, `resumer_resultat`), un bouton pour la retirer, et, pour celles qui sont enfreintes, un volet avec les lignes concernées du fichier nettoyé. Un bandeau dit en une phrase si le fichier respecte tout. Une règle visant une colonne absente est signalée, pas ignorée.
* **Import et export en mémoire.** L'import lit le JSON par `regles_depuis_texte` (jamais par `charger_regles`, qui ouvre un chemin du disque du serveur) et ignore les règles déjà présentes, reconnues à leur identifiant. L'export passe par `regles_vers_texte` et un bouton de téléchargement, aussi proposé dans l'onglet Téléchargements. Rien n'est écrit sur le serveur, ce qu'un test vérifie.
* **Le rapport de nettoyage en profite.** Son expander de l'onglet Nettoyage et ses téléchargements incluent la section « Contraintes », sans bouton de plus.
* **Un état qui ne se recalcule pas pour rien.** `st.tabs` exécute le corps de tous les onglets à chaque interaction ; les résultats sont donc gardés en session, avec une clé faite du fichier, du nettoyage et des règles, et ne sont recalculés que si l'un des trois change. Un nouveau nettoyage les invalide.
* **Les contraintes ne survivent pas à un nouveau fichier**, puisqu'elles portent sur des noms de colonnes ; on les reprend par l'import. « Effacer mes données » les vide aussi, avec les clés de leurs widgets. La liste initiale est copiée à chaque session : sans cela, deux visiteurs auraient partagé leurs règles.

### 4. Modifier une contrainte
Le crayon à côté de chaque contrainte repasse le formulaire en mode modification, pré-rempli : type, colonnes, champs et nom. « Enregistrer les modifications » remplace la contrainte **en gardant sa place** dans la liste, « Annuler » la laisse intacte, et le formulaire revient en mode ajout. Le verdict est recalculé aussitôt.

* **L'inverse de la construction est dans le module partagé** (`saisies_depuis_regle`) : reconstruire une règle à partir de ses saisies redonne exactement la même, ce que dix cas vérifient. Le terminal pourra la réutiliser.
* **Le pré-remplissage se fait dans un rappel de bouton**, avant la réexécution du script : les clés des widgets sont renseignées, et le formulaire repart d'une génération neuve pour qu'aucune saisie en cours ne se mêle à la contrainte choisie. Une colonne qui n'existe plus dans le fichier (règle importée d'ailleurs) n'est pas pré-sélectionnée : la contrainte reste modifiable, il suffit de choisir une colonne.
* **Les cas limites sont tranchés.** Une modification qui rend la règle identique à une autre est refusée (l'identifiant découle du contenu). Enregistrer sans rien changer est accepté. Une saisie invalide est expliquée et ne fait rien perdre. Retirer la contrainte en cours de modification ferme le formulaire, de même qu'un nouveau fichier ou « Effacer mes données ».

### 5. Des garde-fous, parce que les règles viennent d'ailleurs
Les contraintes sont saisies par l'utilisateur, et un fichier de règles peut venir d'un tiers. Sur le serveur partagé de l'application en ligne, cela ouvre des portes que la suite de tests, qui vérifie surtout le chemin heureux, ne regardait pas. Un audit en a fermé plusieurs.

* **Un motif catastrophique ne fige plus le serveur.** Une expression régulière comme `(\d+)+` oblige le moteur de Python à essayer un nombre de découpages qui double à chaque caractère : mesuré, 2 secondes pour 26 chiffres suivis d'une lettre, le temps quadruplant tous les deux caractères, donc des heures vers 40. Ce moteur ne peut pas être interrompu en cours de route, et Streamlit exécute le calcul dans le processus qui sert les autres visiteurs. L'évaluation d'un motif personnalisé est donc confiée à un **processus séparé**, arrêté net après cinq secondes (`DELAI_MOTIF`), avec seules les valeurs distinctes en entrée. Aucune dépendance de plus. Les valeurs voyagent en JSON sur l'entrée du processus et non dans son programme : une valeur qui ressemble à du code reste une chaîne, ce qu'un test vérifie. Les formats nommés, eux, restent évalués sur place : leurs motifs sont fixes et sûrs.
* **Des plafonds** : motif de 200 caractères au plus, 1 000 valeurs autorisées, 100 règles, fichier de règles de 1 Mo, vérifié avant de le lire (la taille se contrôle sur le fichier déposé avant même de le décoder).
* **Un JSON très imbriqué** faisait échouer la lecture par une erreur que l'interface n'attrapait pas ; c'est désormais un refus expliqué.
* **Pas de lien ni d'image trompeurs.** Le nom d'une contrainte venu d'un fichier tiers s'affichait tel quel en Markdown : `[cliquez ici](http://…)` devenait un lien, et `![](http://…)` une image chargée depuis un site externe au simple affichage, c'est-à-dire un pisteur discret. Le texte venu de l'utilisateur est maintenant neutralisé (`echapper_markdown`), à l'écran comme dans le rapport de nettoyage. Seuls les caractères qui fabriquent un lien, une image ou une mise en forme sont protégés : les rapports restent lisibles.
* **`json.loads` n'exécute aucun code**, contrairement à `pickle` : un champ rempli de code Python n'est jamais qu'une chaîne, ce qu'un test confirme.

### 6. Erreurs rencontrées
* **Un test devenu ambigu.** L'envoi du fichier de règles est un second composant d'envoi : le test utilitaire qui prenait « le premier » (`app.file_uploader[0]`) ouvrait soudain le mauvais, et refusait un `.csv`. L'envoi principal est désormais retrouvé par sa clé. Le défaut était dans le test, pas dans l'application, mais il était révélateur : toute hypothèse sur l'ordre des composants est fragile.
* **Le nombre d'onglets.** Deux tests énuméraient les sept onglets ; ils comptent désormais huit.
* **Un fichier de règles pouvait faire planter l'affichage.** En testant le plafond de règles à l'import avec cent règles identiques, l'application a échoué : deux règles de même identifiant donnent deux boutons de même clé. L'import ne dédoublonnait que par rapport aux règles déjà présentes, pas à l'intérieur du fichier. C'est un fichier qu'un tiers peut envoyer, volontairement ou non. Le dédoublonnage porte désormais aussi sur le lot importé.
* **Une règle à plusieurs colonnes sans violation faisait échouer l'évaluation.** La construction des exemples (« colonne A | colonne B ») utilisait une opération qui renvoie un tableau, et non une série, quand il n'y a aucune ligne en cause. Le test qui aurait dû le voir, une comparaison de deux colonnes, ne vérifiait pas l'absence d'exception : il constatait seulement que la règle avait été ajoutée. Corrigé, avec un test de régression pour la comparaison et pour l'unicité d'une combinaison.
* **Une promesse à moitié tenue.** Le validateur affirmait qu'« une règle ne fait jamais échouer les autres », mais seule l'évaluation proprement dite était protégée, pas le calcul qui la suit, là où le défaut précédent a éclaté. Toute la construction du verdict d'une règle est maintenant protégée : une panne, même imprévue, devient un verdict d'erreur.

### 7. Ce qui reste
L'essai par le porteur du projet, dans un navigateur : les tests pilotent les widgets, ils ne disent pas si le formulaire est agréable. Puis la fusion dans `main` et le déploiement, qui ne se font qu'après cet essai. Les pistes de la feuille de route restent à venir, dont celles que cet audit a fait apparaître : télécharger les lignes en anomalie, règles conditionnelles, formats supplémentaires, dates relatives.

### 8. Résultat
**687 tests passent**, contre 451 avant l'Étape 47. `docs/API.md` couvre `validator` et `saisie_regles`.

---

*Version 1.1.0 — Deux interfaces (ligne de commande et web) au-dessus d'une logique métier unique, en ligne sur https://quitus.streamlit.app/. 687 tests.*