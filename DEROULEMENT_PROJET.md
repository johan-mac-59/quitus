# DEROULEMENT_PROJET.MD

## Contexte du Projet

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

## Étape 3 : Implémentation - Détails techniques

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

## Étape 5 : Concepts techniques abordés

### Typing (from typing import Tuple)
- Permet d'annoter les types des paramètres et retours
- Améliore la lisibilité et aide à détecter les erreurs avant l'exécution

### DataFrame pandas
- Structure de données tabulaire au cœur du traitement
- Méthodes clés : `isnull().sum()`, `drop_duplicates()`, `fillna()`, `to_numeric()`, `to_datetime()`

### Gestion des encodages
- UTF-8 : standard moderne
- Latin1/CP1252 : courants sur fichiers Windows/Excel européens
- Détecter automatiquement évite les caractères bizarres

### Méthode IQR pour les outliers
- Q1 = 25e percentile, Q3 = 75e percentile
- IQR = Q3 - Q1
- Bornes : Q1 - 1.5*IQR et Q3 + 1.5*IQR
- Standard en statistiques pour détecter les valeurs aberrantes

---

## Étape 6 : Limitations et améliorations futures

### Limitations actuelles :
- **One-pass** : le script ne s'exécute qu'une fois (risque de passer à côté de problèmes résiduels)
- **Détection des dates** : heuristique simple (>80% convertis), peut échouer sur des formats rares
- **Outliers** : méthode IQR standard (1.5x), peut être trop agressive ou pas assez selon le cas
- **Pas de validation post-nettoyage** : on ne vérifie pas si le résultat est réellement propre

### Améliorations possibles :
1. **Validation post-nettoyage** : vérifier qu'il n'y a plus de problèmes critiques
2. **Mode multi-passes** : exécuter plusieurs fois jusqu'à stabilisation
3. **Détection de format de date plus robuste** (regex avancée)
4. **Filtrage paramétrable** des outliers selon le contexte métier
5. **Support multi-format** (JSON, Excel, Parquet...)

---

## Récapitulatif final

### Fichiers créés :
- `src/cleaner_auto.py` → Script principal avec toutes les fonctions de nettoyage automatique
- `DEROULEMENT_PROJET.md` → Ce fichier de documentation du projet

### Commande pour tester :
```bash
# Dans le dossier PROJET_NETTOYAGE_AUTO
python src/cleaner_auto.py
```

### Résultats attendus :
Un fichier CSV nettoyé automatiquement avec un rapport détaillé des transformations effectuées. Le script est générique et fonctionne sur n'importe quel CSV sans connaissance préalable du contenu.

---

*Projet en cours de développement - Bootcamp Data Analyst Wild Code School*



---

## Étape 7 : Refactoring et Architecture Modulaire (En cours)

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

## Récapitulatif final (Version Modulaire)

### Fichiers créés :
- `src/file_loader.py` → Chargement intelligent (CSV/Excel), détection encodage/séparateur.
- `src/cleaner_engine.py` → Moteur de transformation des données (Nettoyage pur).
- `src/report_generator.py` → Moteur d'affichage des résultats (Rapports textuels).
- `src/main.py` → Point d'entrée qui lie le tout.

### Commande pour tester :
```bash
# Dans le dossier PROJET_NETTOYAGE_AUTO
python src/main.py
```

*Projet en cours de développement - Bootcamp Data Analyst Wild Code School*

---

## Étape 8 : Optimisations récentes et corrections critiques

Dans les dernières itérations, nous avons corrigé des bugs structurels et optimisé l'ordre logique des opérations pour garantir la fiabilité du nettoyage.

### 1. Correction de la structure du Pipeline (`run_pipeline.py`)
*   **Problème :** L'indentation dans le bloc `try/except` de la sauvegarde CSV était erronée, risquant de faire planter le script.
*   **Solution :** Structuration propre avec des chemins dynamiques via `pathlib`. Le pipeline orchestre maintenant clairement : Chargement → Nettoyage → Sauvegarde → Rapport.

### 2. Révision critique de l'ordre des tâches (Le "Golden Path")
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

## Étape 9 : Structuration du Projet et Début des Tests Unitaires

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

---

## Récapitulatif final (V1.0 - Stable)

## Étape 10 : Stabilisation du Moteur de Nettoyage et Passage aux Tests Unitaires

Cette étape est cruciale car elle marque le passage d'un "script qui fonctionne" à un "programme robuste et testé".

### 1. Résolution des bugs dans `cleaner_engine.py`
Nous avons corrigé plusieurs erreurs logiques persistantes :

*   **Bug sur la `median` (Médiane)** : Le `fillna` de la médiane pour les colonnes numériques n'était pas appliqué directement au DataFrame (`df_cleaned`). Nous avons rectifié en écrivant explicitement `df_cleaned[col] = df_cleaned[col].fillna(median_val)`.
*   **Bug sur le `mode` (Mode)** : La variable `col_mode` était parfois mal indentée ou non définie dans la boucle. Nous avons clarifié la logique pour que les colonnes de type "texte" (comme `'email'`) soient bien détectées, calculées via `.mode()[0]`, et ensuite remplies proprement avec `fillna`.
*   **Gestion des types (`StringDtype`)** : Une colonne contenant du texte dans un fichier moderne Pandas n'est pas toujours de type `'object'`. Nous avons ajusté la logique pour que les conversions numériques (comme `'10.5'` → `float`) se fassent correctement en utilisant `pd.to_numeric()`.

### 2. Premiers Tests Unitaires (`pytest`)
Nous avons commencé à intégrer des tests automatisés pour garantir qu'un changement de code ne "casse" pas les fonctionnalités existantes (régression).

**Résultats des tests sur le moteur de nettoyage (`cleaner_engine`)** :
*   **Clean Missing Values** ✅ : Les fonctions de remplissage par la médiane et le mode fonctionnent.
*   **Clean Types** ✅ : La détection automatique de colonnes à convertir (String → Numérique) est fiable.
*   **Clean Duplicates** ✅ : Le nombre de doublons supprimés est correct.

### 3. Impact sur l'architecture
Grâce aux tests, nous pouvons désormais refactoriser le code en toute sécurité. 
Le fichier `DEROULEMENT_PROJET.md` devient notre source de vérité technique, documentant chaque erreur rencontrée et sa solution.

---

### 4. Résolution des derniers bugs critiques dans cleaner_engine.py
 ⚠️
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

### 5. Stabilisation du Pipeline et Passage aux Tests Unitaires 🛡️
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


### 6. Tentative d'automatisation du nettoyage des Outliers (Boucle IQR itérative)

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

## Étape 11 : Analyse de Régression et Tests Unitaires (`pytest`)

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

### Résultat final de l'étape
Le pipeline global (`test_pipeline_complet`) valide que si l'orchestrateur fait bien son travail, les données finales sont propres. Cependant, pour garantir la robustesse du moteur (`cleaner_engine`), il faut corriger ces 3 points dans les tests unitaires.

## Étape 12 : Correction des Tests Unitaires et Résolution des "Fausses" Négatives 🐛🛠️

Dans cette étape critique, nous avons identifié pourquoi certains tests échouaient malgré un pipeline fonctionnel en production. Les erreurs provenaient de la rigidité des fixtures de test et du comportement mathématique de pandas sur de petits échantillons.

### 1. Analyse de l'échec `test_doublons_exact`
*   **Symptôme :** Le test échouait car le DataFrame retenu contenait toujours 4 lignes.
*   **Analyse technique :** Le DataFrame initial (`dirty_df`) contenait des lignes avec le même ID (2) mais des noms différents ("Bob" et "Alice"). `drop_duplicates()` de pandas considère que ce sont deux lignes *distinctes* car elles ne sont pas identiques caractère pour caractère.
*   **Correctif appliqué :** 
    1. Nous avons créé une fixture dédiée (`dirty_df_with_exact_doublons`) contenant des répétitions parfaites de toutes les colonnes.
    2. Cette approche garantit que le test valide bien la logique de suppression de doublons sans être faussé par d'autres données.

### 2. Analyse de l'échec `test_correction_iqr`
*   **Symptôme :** La valeur -999 n'était pas supprimée/correctement traitée.
*   **Analyse technique :** 
    *   L'algorithme IQR nécessite des colonnes de type numérique pur (`np.number`). Si la présence de NaN ou d'espaces laisse pandas interpréter la colonne comme `object` (string), le calcul `quantile()` échoue silencieusement ou renvoie des valeurs par défaut incohérentes.
    *   De plus, sur un échantillon minuscule (ex: `[25, NaN, 35]`), l'IQR est très faible, rendant la borne inférieure (`Q1 - 1.5*IQR`) autour de 20. La valeur -999 étant bien en dessous, elle est détectée comme aberrante.
*   **Correctif appliqué :** 
    *   Ajout d'une étape explicite `pd.to_numeric(errors='coerce')` avant le calcul des bornes dans `clean_outliers`.
    *   Utilisation de `.fillna(median())` sur une copie temporaire du DataFrame pour calculer les quartiles sans perdre l'information des indices originaux.

---

## Étape 13 : Préparation à la présentation (Audit de professionnalisme)

Dans cette phase finale, l'objectif est de transformer un projet technique en un produit prêt pour une présentation professionnelle (Candidature). L'accent a été mis sur la communication, la clart_ de la documentation et la suppression des traces de travail "brouillon".

### 1. Audit de cohérence structurelle
* **Objectif** : S'assurer que le `README.md` ne promet rien que le code ne puisse réaliser (évitement du syndrome du "Feature Creep" non documenté).
* **Action** : Vérification systématique entre les modules présents dans `src/` et les fonctionnalités annoncées au lecteur.
* **Résultat** : Alignement total de la documentation sur les capacités réelles du pipeline (retrait des mentions de modules inexistants comme `validator`).

### 2. Professionnalisation de la documentation technique
* **Élimination des "traces de chantier"** : Suppression des commentaires de développement, des notes personnelles et des rappels d'erreurs passées à l'intérieur du code source (`src/file_loader.py`) pour ne laisser que une documentation API propre (Docstrings).
* **Refonte de la communication des capacités** : Passage d'une liste de fonctions techniques à une présentation par "Capacités Métier" (ex: "Intelligence de lecture", "Audit & Traçabilité"). L'idée est de mettre en avant la valeur ajoutée pour un utilisateur Data.

### 3. Stratégie de communication sur l'IA (AI-Augmented Engineering)
* **Positionnement** : Transformation de la méthode de travail (utilisation d'agents LLM) en une compétence stratégique : l'orchestration d'intelligence artificielle pour accéliter le cycle de développement et la robustesse du code.
* **Valorisation de l'expertise humaine** : Mise en avant du rôle critique de l'humain dans l'architecture, la conception des processus de convergence (itérations sur les types) et l'audit final du pipeline.

### Résumé de la maturité du projet au terme de cette étape
Le projet est passé d'un script de nettoyage expérimentale à un **systle de pipeline de données structuré, testé et prêt pour une présentation professionnelle**, capable de démontrer à la fois des compétences en Python avancé, en manipulation de données (Pandas/Numpy) et en gestion moderne du cycle de vie logiciel.





---

## Étape 14 : Développement du module de Profilage (`data_profiler`) 📊

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

### 3. Tests Pytest
3 ok et 13 erreurs, essentiellement dues à un module absente mais nécessaire : Tabulate
après installation de ce module, 5 KO sur 16 : un même problème car je faisais une opération sur un Tuple
après correction de cette anomalie, une nouvelle mais unique erreur est apparue suite un correctif dans le fichier de tests
après mise à jour du fichier de tests par l'agent testeur, tous les tests sont OK
je corrige néanmoins les alertes de Pandas

### 4. Intégration au Pipeline
Le flux de travail devient maintenant :
1.  **Chargement** (`file_loader`)
2.  **Profiling** (`data_profiler`) ➡️ *Nouveau* : Génère `data/processed/report_profile.md`
3.  **Nettoyage** (`cleaner_engine`)
4.  **Sauvegarde & Rapport Final** (`cleaner_logger`)

**Défis techniques résolus aujourd'hui :**
*   **Gestion des chemins relatifs :** Utilisation de `Path(__file__).parent.parent` pour que le script fonctionne depuis n'importe quel répertoire (racine ou sous-dossier `src/`).
*   **Correction des imports dynamiques :** Ajout de `sys.path.insert(0, ...)` dans le fichier orchestrator pour éviter les `ModuleNotFoundError` quand le script est lancé depuis l'intérieur d'un package.

### 4. Préparer le terrain pour les futures alertes
La classe `DataProfiler` inclut désormais une méthode预留 (`detect_quality_issues`). Cette structure est prête à accueillir nos prochaines règles métier (ex: "Si une colonne 'Age' a des valeurs < 0, alerter l'utilisateur").

---

## Étape 15 : Renforcement de la Robustesse et Fiabilisation par les Tests Unitaires 🛡️🛠️

Dans cette phase, l'objectif est passé de "faire fonctionner le code" à "garantir qu'il ne cassera jamais lors d'une mise à jour". Nous avons affronté des problèmes complexes liés aux types de données et à la structure même du projet.

### 1. L'enjeu de la robustesse des données (Handling Edge Cases)
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

## Étape 16 : Professionnalisation du Reporting et Sécurisation de l'Audit via `CleanerReporter` 📝🚀

Après avoir stabilisé le moteur de nettoyage (`cleaner_engine`) et les tests unitaires, l'objectif est passé de la simple transformation de données à la **création d'une preuve d'audit**. Un pipeline performant ne sert à rien si l'utilisateur final (le Data Analyst ou le métier) ne peut pas auditer les transformations effectuées.

### 1. Le défi : Transformer des logs techniques en un rapport métier
Jusqu'ici, la visibilité sur le nettoyage reposait sur des sorties textuelles dans la console, volatiles et difficiles à archiver. Le défi était de créer une classe `CleanerReporter` capable de transformer des objets complexes (`DataProfiler` et `CleanLogger`) en un document Markdown structuré, persistant et lisible par des non-développeurs.

### 2. Implémentation de la couche d'Audit (Audit Trail)
Le module a été conçu pour extraire et structurer l'information selon trois piliers critiques :
* **Métadonnées de traçabilité** : Extraction automatique du chemin absolu du fichier source et horodatage précis pour garantir l'origine de la donnée.
* **Indicateurs de performance (KPIs)** : Calcul des ratios de transformation (ex: perte de lignes, suppression de colonnes) sous forme de tableau comparatif "Avant vs Après".
* **Journal d'exécution détaillé** : Transformation du log d'opérations en un tableau Markdown structuré, permettant de vérifier colonne par colonne l'action appliquée et son résultat.

### 3. Ingénierie de la Robustesse (Programmation Défensive)
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

## Étape 17 : Intégration du module de reporting au pipeline global

Cette étape a consisté à orchestrer les modules existants (`file_loader`, `data_profiler`, `cleaner_engine` et `cleaner_reporter`) pour former un pipeline de données complet et automatisé.

### 1. Problématique : L'accès aux données éphémères
Le moteur de nettoyage (`cleaner_engine`) génère des statistiques cruciales (nombre de doublons supprimés, colonnes transformées, etc.) sous forme de dictionnaires temporaires durant l'exécution du script `main.py`. Le module `cleaner_reporter`, quant à lui, est conçu pour lire des objets persistants (`DataProfiler` et `Logger`). 

**Le défi :** Comment transmettre les statistiques de nettoyage (volatiles) au moteur de rapportage sans casser la séparation des responsabilités entre les modules ?

### 2. Méthode de résolution : Le pattern "Adapter"
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

## Étape 18 : Optimisation de l'auditabilité et intelligence du moteur numérique 🛠️🔍

Cette étape cruciale a transformé le pipeline d'un outil de nettoyage simple en un système d'audit professionnel, capable de traiter des formats complexes (monétaires) et de corriger les erreurs structurelles introduites par le chargement initial.

### 1. Intelligence du moteur numérique (Traitement des formats monétaires)
L'un des plus grands défis était la présence de données numériques "sales" qui empêchaient toute conversion (ex: `"1 200,50 €"`). Le moteur ne reconnaissait pas ces valeurs comme des nombres à cause des symboles et des séparateurs hétérogènes.

* **Détection et Nettoyage intelligent** : Mise en place d'une logique capable de :
    * Identifier les colonnes contenant des symboles monétaires (`€`, `$`, `£`).
    * Gérer la dualité des séparateurs (conversion automatique de la virgule `,` en point `.` pour le standard Python).
    * Supprimer les espaces de milliers (ex: `"1 000"` $\rightarrow$ `"1000"`) et les caractères parasites.
* **Résultat** : Une augmentation drastique du taux de succès de la conversion `object -> float` sur des colonnes critiques comme `montant_total`.

### 2. Résolution du "Pandas Type Trap" (Le problème des entiers déguisés)
Une problématique majeure a été identifiée sur les colonnes de comptage (`nb_nuits`, `nb_personnes`).

* **Le Problème** : À cause de la présence de valeurs manquantes (`NaN`) ou de formats texte (`"7.0"`), Pandas charge ces colonnes en `float64`. Cela altère l'intégrité sémantique (on traite des décimaux là où nous avons des quantités entières).
* **La Solution technique** : Implémentation d'une étape de **`fix_numeric_types`** intégrée au pipeline.
    * **Détection** : Le module repère les colonnes `float64` dont la partie décimale est systématiquement nulle (ex: `1.0`, `2.0`).
    * **Correction** : Conversion vers le type **`Int64` (Nullable Integer)** de Pandas. Ce type moderne conserve la nature entière de la donnée tout en supportant les valeurs manquantes (`<NA>`) sans forcer le retour à un format `float`.

### 3. Amélioration de l'auditabilité du rapport (Le "Comment" et le "Combien")
L'objectif était de passer d'une statistique brute à une documentation qualitative pour la reproductibilité.

* **Refonte de la structure des données (`cleaner_engine.py`)** : Passage d'une chaîne descriptive à un objet structuré pour `clean_missing_values` :
    * **Avant :** `{'colonne': 'fill_mode_valeur'}` (impossible de calculer le total global).
    * **Après :** `{'colonne': {'count': 15, 'method': 'fill_mode_valeur'}}` (permet un audit précis des volumes traités).
* **Évolution du reporting (`cleaner_reporter.py`)** : Le rapport Markdown affiche désormais un véritable journal d'audit avec le nom de la colonne, le nombre de cellules traitées (**Combien**) et la méthode utilisée (**Comment**).

### ✅ Résultats
* **Intelligence métier** : Capacité à traiter des formats monétaires complexes sans intervention manuelle.
* **Intégrité sémantique restaurée** : Les colonnes de comptage retrouvent leur nature d'entiers, même avec des valeurs vides.
* **Auditabilité totale** : Le rapport devient un document de traçabilité permettant de vérifier chaque transformation effectuée sur le dataset.

---

## Étape 19 : Tests de non-régression suite aux modifications du moteur

Suite aux optimisations apportées au `cleaner_engine` (notamment sur la gestion des types et des outliers) et au `cleaner_reporter`, il était impératif de valider que ces changements n'ont pas introduit de régressions dans les modules existants.

### 1. Objectif de la phase de test
L'objectif était de s'assurer que les modifications structurelles (passage de `nb_doublons` à `duplicates_count`, refonte des types Pandas) n'aient pas cassé les assertions des tests unitaires déjà en place et que le pipeline d'intégration reste fonctionnel.

### 2. Problématiques rencontrées et résolutions techniques

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

### 3. Résultat final
Après correction des tests pour les mettre en adéquation avec la nouvelle structure du code, la suite de tests `pytest` est passée avec un score de succès total sur l'ensemble des modules (`DataProfiler`, `CleanerEngine`, `CleanerReporter`). Le pipeline est désormais stabilisé et prêt pour l'utilisation.

---

## Étape 20 : Profilage Multidimensionnel : De l'Analyse de Colonnes à l'Audit de Structure 📊🔍

Dans cette phase d'évolution majeure, nous avons transcendé le rôle du `DataProfiler` (simple lecteur de structure) pour en faire un véritable outil d'audit de qualité de données complet, capable d'inspecter la santé des colonnes **et** la complétude des lignes.

### 1. Analyse de la Qualité Structurelle des Lignes (Row Integrity)
Le module a acquis une nouvelle dimension : l'inspection de la densité informationnelle par enregistrement.
* **Détection de la vacuité** : Calcul automatique du pourcentage de valeurs manquantes par ligne.
* **Classification par criticité** : 
    * **Niveau Critique (>90% vide)** : Identification des lignes "fantômes" à supprimer pour nettoyer le bruit.
    * **Niveau Alerte (30-90% vide)** : Identification des lignes nécessitant une inspection manuelle.
* **Reporting granulaire et intelligent** : 
    * Pour éviter l'infobésité, le module regroupe les alertes par **pourcentage exact de valeurs manquantes**, permettant de voir les motifs de structure récurrents.
    * Implémentation d'une **sécurité d'affichage** : limitation à 10 index maximum par groupe pour garantir la lisibilité du rapport Markdown, tout en indiquant le nombre total de lignes impactées.

### 2. Analyse Approfondie des Colonnes (Column Intelligence)
Le moteur continue d'affiner l'audit des données textuelles et numériques selon quatre piliers :
* **Cardinalité Avancée** : Calcul de la cardinalité absolue et relative (ratio par rapport au volume total).
* **Indicateur de Remplissage (Sparsity Ratio)** : Intégration du taux de remplissage spécifique aux colonnes catégorielles.
* **Analyse de la Variance (Skewness de Fréquence)** : Implémentation d'un indicateur de dominance. Si une catégorie représente plus de 90% des données, le module génère une alerte visuelle (⚠️) signalant une faible variance.
* **Audit de Conformité Syntaxique** : Détection automatique des anomalies de formatage (espaces traînants, hétérogénéité de casse).

### 3. Standardisation Terminologique et Présentation
* **Approche Bilingue Professionnelle** : Pour répondre aux standards internationaux, nous avons adopté une nomenclature **"Terme Anglais | Traduction Française"** (*ex: "Sparsity Ratio | Taux de remplissage"*).
* **Stratégie d'Affichage Dynamique** : Pour les colonnes à forte cardinalité, le module se concentre sur le **Top 5 des catégories** les plus représentatives avec leur poids relatif (%), évitant ainsi de surcharger le rapport.

### 4. Impact sur la Fiabilité du Pipeline
Le `DataProfiler` ne se contente plus de décrire ce qui est là ; il prévient l'analyste des risques structurels avant même que le moteur de nettoyage (`cleaner_engine`) ne soit lancé. C'est le passage d'un mode **"Nettoyage aveugle"** à un mode **"Audit & Action"**.

---

---

## Étape 21 : Évolution vers l'Exploration Multimodale : Rapport HTML Autonome & Visual Analytics 📊🚀

Dans cette phase d'évolution majeure, le projet a franchi un nouveau palier en passant d'un pipeline purement textuel à une interface de pilotage interactive et visuelle. L'objectif était de doter l'utilisateur final d'un outil capable de présenter des analyses riches sans aucune contrainte de dépendance de fichiers.

### 1. Introduction de l'Interactivité (Human-in-the-loop)
Le pipeline n'est plus une séquence figée. Nous avons introduit une couche d'interaction au point d'entrée (`main.py`) permettant un choix stratégique lors de l'exécution :
* **Mode Standard (Markdown)** : Pour une documentation technique rapide, légère et optimisée pour le versioning (Git/GitHub).
* **Mode Exploratoire (HTML)** : Pour une analyse riche, visuelle, destinée à être partagée avec des parties prenantes non-techniques.

### 2. Innovation Technique : Le Rapport HTML "Self-Contained"
Le plus grand défi technique de cette étape était la génération d'un rapport HTML qui soit **totalement autonome**. 

**La problématique initiale** : Traditionnellement, un rapport HTML pointe vers des images stockées dans un dossier `/graphs`. Cela crée une dépendance : si l'on déplace le fichier `.html` sans son dossier d'images, le rapport devient "aveugle".

**La solution implémentée (Embedding via Base64)** : 
Pour garantir que le rapport soit portable et s'affiche parfaitement partout (e-mail, navigateur local, cloud), nous avons implémenté une technique d'encodage avancé :
* **Capture en mémoire** : Les graphiques (Histogrammes, Boxplots, Barplots) sont générés par `Matplotlib/Seaborn` et interceptés dans un buffer mémoire (`BytesIO`).
* **Encodage Base64** : Chaque image est convertie en une chaîne de caractères textuelle (Base64) injectée directement dans la balise `<img src="data:image/png;base64,...">` du code HTML.
* **Résultat** : Le fichier `.html` final contient l'intégralité des données et des visuels. Il suffit d'un seul fichier pour transporter toute l'analyse.

### 3. Diversification de l'Analyse Visuelle
L'intégration réussie des graphiques permet désormais une exploration multidimensionnelle :
* **Distribution Numérique** : Utilisation de `Histplots` (avec KDE) pour visualiser la densité et les modes de distribution.
* **Détection visuelle des Outliers** : Utilisation de `Boxplots` pour corroborer les calculs statistiques de l'algorithme IQR par une preuve visuelle immédiat.
* **Analyse de Fréquence** : `Barplots` sur les colonnes catégorielles pour identifier instantanément les catégories dominantes et la structure du dataset.

### 4. Défis d'Ingénierie rencontrés
* **Gestion de la charge mémoire** : L'encodage d'images dans le texte augmente la taille du fichier HTML. Nous avons dû optimener la résolution des graphiques pour maintenir un équilibre entre clarté visuelle et légèreté du document.
* **Robustesse du pipeline de rendu** : Mise en place de blocs `try/except` autour de chaque génération de graphique pour garantir que, même si une colonne pose problème (ex: trop de données), le reste du rapport HTML est généré sans interruption.

### Résumé de la valeur ajoutée
Le projet quitte définitivement le stade de "script de nettoyage" pour devenir un **système d'audit décisionnel et visuel**. L'utilisateur ne subit plus un processus automatique ; il pilote une investigation complète, capable de produire des livrables professionnels, autonomes et prêts à être partagés en entreprise.

---

## Étape 22 : Vers un Nettoyage Piloté par l'Expert (Human-in-the-loop) 🧠👤

Dans cette phase, le projet a connu une mutation philosophique majeure. Nous sommes passés d'un automate de nettoyage "boîte noire" à un **assistant décisionnel interactif**. L'objectif n'est plus que la machine décide seule, mais qu'elle fournisse l'intelligence nécessaire pour que l'analyste valide ou rejette chaque transformation critique.

### 1. Le passage du mode "Batch" au mode "Piloté"
Jusqu'alors, le pipeline exécutait une séquence de tâches prédéfinies sans solliciter l'utilisateur. Si une erreur de logique survenait (ex: suppression trop agressive d'outliers), elle était définitive dans le fichier de sortie.

Nous avons introduit une couche d'**interactivité décisionnelle** à deux points stratégiques du pipeline :
* **Gestion des Valeurs Manquantes** : Avant le remplissage, l'analyste est informé du volume et de la répartition des trous dans les données. Il peut alors décider de maintenir la structure brute ou d'autoriser le comblement (médiane/mode).
* **Gestion des Outliers** : Le système ne se contente plus de "clipper" les valeurs ; il présente un audit préalable des colonnes impactées, laissant le choix final à l'expert.

### 2. L'intelligence contextuelle au service de l'analyste
L'interaction n'est pas une simple boîte de dialogue ; elle est **contextualisée** grâce aux résultats du `DataProfiler` :
* **Aide à la décision (Decision Support)** : Au lieu d'un message générique, le script présente des faits précis (ex: *"150 valeurs manquantes détectées dans la colonne 'Prix'"*). Cela transforme l'utilisateur de simple spectateur en décideur éclairé.
* **Gestion des options par défaut** : Pour préserver la fluidité du workflow, nous avons implémenté des réponses par défaut (ex: `[y/n, entrée par défaut 'y']`). Cela permet une exécution rapide pour les cas standards, tout en offrant un contrôle total pour les cas complexes.

### 3. Transformation de la responsabilité : De la Machine à l'Analyste
Cette évolution change radicalement la nature du projet :
* **Ancien paradigcu** : Le script est un agent autonome qui "fait le travail". Risque de perte de traçabilité métier.
* **Nouveau paradigme** : Le script est un **outil d'aide à la décision (Decision Support System)**. L'analyste reste le maître d'œuvre, tandis que le code s'occupe de l'exécution technique et de la surveillance des anomalies.

### 4. Impact sur la fiabilité du pipeline
L'introduction de ces validations manuelles a renforcé la **résilience** du projet :
* **Réduction du risque de régression métier** : On évite les transformations qui, bien que statistiquement correctes (ex: imputer une médiane), pourraient être sémantiquement fausses dans un contexte métier spécifique.
* **Auditabilité humaine** : Chaque décision prise durant l'exécution est capturée et peut être documentée, renforçant la chaîne de confiance entre la donnée brute et le rapport final.

---

## Étape 23 : Uniformisation de la Casse et Standardisation Textuelle 🔡🔍

Dans cette phase, nous avons intégré une nouvelle brique de nettoyage stratégique pour traiter l'une des sources de bruit les plus insidieuses dans les données catégorielles : l'incohérence de casse (ex: "Paris", "PARIS", "paris").

### 1. Le défi : La fragmentation des catégories
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

## Étape 24 : Résolution de la Fragilité du Reporting et Sécurisation des Types (Bug Fix & Robustness) 🛠️⚠️

Cette étape a marqué un tournant critique dans le projet : le passage d'un système qui "fonctionne sous conditions" à un système capable de gérer l'incertitude et les choix de l'utilisateur sans interruption brutale.

### 1. Analyse de la régression : Le paradoxe du "Type Error"
Lors de l'introduction de l'interactivité (permettant à l'utilisateur d'ignorer certains nettoyages), une erreur fatale est apparue dans le pipeline : `unsupported operand type(s) for +: 'int' and 'str'`.

* **L'origine du problème** : Dans la phase de décision, si l'utilisateur choisissait de ne pas traiter les valeurs aberrantes (outliers), le moteur stockait une chaîne descriptive (`'Corrections ignorées...'`) dans un dictionnaire censé contenir des entiers.
* **La rupture de contrat** : Le module `CleanLogger`, qui générait le résumé textuel, tentait d'agréger (sommer) toutes les valeurs du dictionnaire pour afficher un total. L'addition d'un entier (le nombre d'outliers trouvés) et d'une chaîne de caractères (le message d'annulation) provoquait l'arrêt immédiat du programme.

### 2. Stratégie de résolution : Standardisation et Programmation Défensive
Pour résoudre ce problème, nous n'avons pas seulement corrigé un bug, nous avons refondu la logique de communication entre le moteur (`Engine`) et les rapports (`Logger/Reporter`).

#### A. Refonte du protocole de stockage (Contract-Based Programming)
Nous avons abandonné l'utilisation de messages textuels au sein des structures numériques. Désormais, le moteur utilise un format structuré et prévisible :
* **Pour les cas nominaux** : `{'colonne_A': 10, 'colonne_B': 5}` (uniquement des entiers).
* **Pour les cas d'annulation** : `{'ignored': True}`.
Cette approche garantit que la structure de donnée est toujours prévisible pour les modules suivants.

#### B. Implémentation de l'Audit Sécurisé dans le Logger
Le `CleanLogger` a été doté d'une logique de "vérification de type" (Type Checking) avant toute opération arithmétique :
* **Analyse du contenu** : Avant de sommer, le logger vérifie si la clé `'ignored'` est présente ou si les valeurs sont numériques.
* **Fallback robuste** : En cas de structure inattendue, le système utilise un bloc `try/except` pour afficher `"Données non valides"` au lieu de planter, garantant ainsi que le pipeline termine toujours son exécution et sauvegarde les données.

#### C. Uniformisation du Reporting (Markdown & Terminal)
Nous avons synchronisé les deux modes de rapportage :
* **Rapport Terminal (Textuel)** : Affiche désormais clairement *"Traitement ignoré par l'utilisateur"* au lieu d'un nombre erroné ou d'une erreur système.
* **Rapport Markdown (Audit)** : Le tableau détaillé est capable de switcher entre un mode "comptable" (affichage des quantités) et un mode "informatif" (affichage du motif d'annulation), assurant une traçabilité sans faille pour l'auditeur.

### 3. Impact sur la maturité du projet
Cette étape a apporté trois bénéfices majeurs :
1. **Fiabilité (Reliability)** : Le pipeline est désormais "crash-proof" face aux choix utilisateur imprévus.
2. **Transparence (Observability)** : L'utilisateur a une visibilité totale non seulement sur ce qui a été fait, mais aussi sur ce qui a été délibérément écarté.
3. **Maintenabilité** : La séparation stricte entre les données numériques et les messages de statut facilite l'ajout de nouvelles fonctionnalités sans risque de régression.

---

## Étape 25 : Extension de l'Intelligence de Lecture : Support Multi-Format & Détection de Structure (JSON/JSONL) 📂🚀

Dans cette phase d'évolution, le pipeline a franchi une étape majeure en brisant la barrière du format CSV. L'objectif était d'augmenter la polyvalence du `file_loader` pour qu'il puisse absorber des flux de données modernes (APIs, logs, NoSQL) sans intervention humaine.

### 1. Le défi de l'hétérogénéité des sources
Jusqu'alors, le pipeline était optimisé pour les structures tabulaires classiques (lignes/colonnes). L'introduction du format **JSON** (objet unique) et **JSONL** (flux de lignes) posait deux problèmes critiques :
* **Complexité structurelle** : Un JSON n'est pas qu'une simple liste ; il peut être un d'objet complexe où les données utiles sont cachées sous une clé spécifique (ex: `{"metadata": ..., "data": [...]}`).
* **Détection aveugle** : Comment savoir si un fichier sans extension est un CSV mal formaté ou un flux JSONL sans changer la logique de l'utilisateur ?

### 2. Implémentation de l'Intelligence de Chargement
Nous avons transformé le `file_loader` en un moteur de détection multi-couches :

* **L'architecture de secours (Fallback Strategy) avec analyse de signature** : 
    * Si l'extension est explicite (`.json`, `.jsonl`), le moteur utilise des chargeurs spécialisés.
    * Si l'extension est inconnue ou absente, le moteur active un **scanner de structure** qui analyse les premiers octets du fichier pour identifier les signatures `{` ou `[` caractéristiques du format JSON.
* **Le moteur `_load_json_manual` (Deep Discovery & Unwrapping)** : 
    Pour pallier les limites de `pd.read_json()` face à des structures non-linéaires, nous avons implémenté une logique de "dépliage". Le moteur parcourt les niveaux du dictionnaire pour extraire la première liste d'objets valide, permettant de transformer des JSON complexes (dictionnaires contenant des listes) en un format tabulaire exploitable par Pandas.
* **Le module `_load_jsonl` (Stream Processing)** : 
    Implémentation d'un lecteur de lignes robuste capable de traiter des fichiers massifs (JSON Lines) en ignorant les lignes vides ou corrompues, garantant que le pipeline ne s'arrête pas à la première erreur de syntaxe rencontrée dans un flux de logs.

### 3. Résilience et Robustesse (Error Containment)
L'intégration de nouveaux formats a nécessité un renforcement des mécanismes de protection :
* **Validation de type** : Utilisation de `isinstance(data, list)` et `isinstance(data, dict)` pour éviter les crashs lors de la transformation en DataFrame.
* **Isolation des erreurs** : Le processus de détection automatique est encapsulé dans des blocs `try/except` pour s'assurer que si la détection échoue, le système retourne une erreur métier explicite (ValueError) plutôt qu'une exception Python obscure.

### 4. Impact sur la valeur métier
Le pipeline est passé d'un outil de **nettoyage de fichiers** à un outil de **consommation de données**. L'analyste peut désormais injecter des sorties d'APIs, des exports de bases de données NoSQL ou des fichiers de configuration directement dans le workflow de nettoyage, sans aucune modification du code source.

---

## Étape 26 : Optimisation de l'Efficacité par le Nettoyage Ciblé et l'Intelligence Contextuelle 🎯🧠

Dans cette phase, le pipeline a évolué d'un mode de traitement "aveugle" vers un mode de traitement "piloté par la donnée". L'objectif était de réduire la charge computationnelle et de limiter les risques de transformations inutiles en utilisant les connaissances du module de profilage.

### 1. Le Problème : Le coût du traitement global
Jusqu'alors, le moteur de nettoyage (`clean_case_sensitivity`) analysait systématiquement toutes les colonnes de type `object` ou `string` du DataFrame. Sur des datasets massifs (millions de lignes) comportant des centaines de colonnes, ce scan global présente deux inconvénients :
* **Surcoût computationnel** : Tester chaque colonne pour détecter des variations de casse consomme des ressources CPU et de la mémoire inutilement si la colonne est déjà propre.
* **Risque de régression** : Appliquer des transformations textuelles sur des colonnes qui ne nécessitent aucun traitement augmente la surface d'erreur (ex: altération accidentelle de chaînes complexes).

### 2. La Solution : L'utilisation du Profilage comme Guide de Nettoyage
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

## Étape 27 : Refactoring de l'Orchestrateur : Vers une Modularité Totale et une Haute Maintenabilité 🏗️🚀

Dans cette phase, l'objectif était de transformer le point d'entrée du projet pour atteindre un niveau de maturité logicielle professionnelle, en appliquant les principes de séparation des responsabilités.

### 1. Le passage du "Script" au "Pipeline Orchestré"
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

---

## Étape 28 : Évolution vers l'Analyse Comparative : Programmation Orientée Objet (POO) et Profilage Dual 🧬🔍

Dans cette phase, le projet a franchi un nouveau palier de maturité architecturale en passant d'un outil de profilage générique à un système de **double audit contextuel**. L'enjeu était de distinguer l'analyse de l'état "brut" (erreurs, bruit, anomalies) de l'analyse de l'état "nettoyé" (performance, complétude, intégrité).

### 1. Le défi : Un besoin de dualité analytique
Le pipeline manquait d'une distinction sémantique entre les deux phases critiques du workflow :
* **Phase Pre-Cleaning** : L'objectif est de détecter les anomalies (casse, outliers, doublons) pour guider le nettoyage.
* **Phase Post-Cleaning** : L'objectif est de valider la réussite des transformations et de vérifier la stabilité de la structure (absence de nouveaux biais).

Utiliser une seule et même classe pour ces deux missions risquait de créer un outil trop monolithique et difficile à spécialiser.

### 2. Implémentation : L'héritage et la spécialisation (POO)
Pour répondre à ce besoin, nous avons refondu le module `data_profiler.py` en utilisant les principes de la **Programmation Orientée Objet (POO)**, plus précisément l'**héritage de classes**.

* **La Classe Mère (`DataProfiler`)** : Elle conserve toute l'intelligence fondamentale (calcul des statistiques, génération des graphiques, moteur de reporting HTML/Markdown). Elle est le socle de robustesse.
* **Les Classes Filles (`PreCleaningProfiler` & `ExploratoryProfiler`)** : 
    * Elles héritent de toutes les capacités de la classe mère via `super()`.
    * Elles permettent de spécialiser le comportement métier.
    * **PreCleaningProfiler** : Conçue pour l'audit de détection (focus sur les alertes de qualité).
    * **ExploratoryProfiler** : Conçue pour l'audit de validation (focus sur la distribution et la structure finale).

### 3. Intégration réussie dans le Pipeline
L'implémentation dans `main.py` a transformé le workflow en un véritable processus de **comparaison avant/après** :
1. **Instanciation du `PreCleaningProfiler`** sur le DataFrame brut $\rightarrow$ Génération du rapport de diagnostic.
2. **Exécution du `cleaner_engine`** $\rightarrow$ Transformation des données.
3. **Instanciation de l'`ExploratoryProfiler`** sur le DataFrame nettoyé $\rightarrow$ Génération du rapport de validation.

Cette structure permet désormais au Data Analyst de visualiser non seulement les transformations, mais aussi la **réduction de l'entropie** (le passage du désordre à l'ordre) au sein du dataset.

### 4. Perspectives et Prochaines Étapes
Bien que l'architecture soit désormais robuste et capable de gérer deux phases distinctes, le travail de personnalisation reste ouvert :
* **Personnalisation des alertes** : Adapter les seuils de criticité spécifiquement pour la phase de pré-nettoyage.
* **Enrichissement du mode exploratoire** : Ajouter des tests de corrélation ou de stabilité statistique uniquement dans la phase post-nettoyage.
* **Standardisation de l'interface** : S'assurer que les deux profilers partagent un contrat d'interface identique pour une manipulation simplifiée dans l'orchestrateur.

---

---

## Étape 29 : Expansion de l'Analyse Multivariée et Optimisation du Dashboarding HTML 📊🚀

Dans cette phase majeure, le projet a franchi un nouveau cap : le passage d'un simple outil d'inspection de colonnes à un véritable système d'**analyse exploratoire multidimensionnelle**. L'objectif était d'ajouter de la profondeur statistique tout en optimisant la lisibilité du rapport final.

### 1. Expansion du module `ExploratoryProfiler` : L'analyse de corrélation
L'innovation majeure de cette étape a été l'introduction de visualisations permettant d'étudier les interactions entre les variables numériques, et non plus seulement leurs propriétés isolées.

* **Matrice de Dispersion (Scatter Plot Matrix)** : Implémentation d'une matrice permettant de visualiser simultanément les relations binaires entre toutes les colonues numériques. Cela permet de détecter instantanément des clusters ou des tendances (linéaires/non-linéaires).
* **Heatmap de Corrélation** : Intégration d'une carte thermique basée sur le coefficient de corrélation. L'utilisation de la palette `coolwarm` permet une lecture intuitive : le rouge pour les corrélations positives fortes, le bleu pour les corrélations négatives, et le blanc pour l'absence de lien.
* **Valeur ajoutée métier** : Cette brique permet de repérer les redondances de données (colonnes fortement corrélées) et de comprendre les dépendances entre les indicateurs (ex: lien entre prix et volume).

### 2. Refonte de l'Architecture Visuelle : Vers un "Dashboard" de Pilotage
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

## Étape 30 : Assainissement du Socle : Remise au Vert de la Suite de Tests et Correction de Bugs Silencieux 🧪🩺

Avant d'engager le chantier de l'interface web, une vérification de routine a révélé que la suite de tests comptait **17 échecs préexistants**. Ce constat, inconfortable, était en réalité une chance : un harnais de tests rouge ne peut détecter aucune régression. Impossible de refondre les modules en confiance sans d'abord rétablir ce filet de sécurité.

### 1. Le diagnostic : deux populations d'échecs très différentes
L'analyse des 17 échecs a fait apparaître une distinction essentielle, qu'il aurait été dangereux de traiter uniformément :

* **15 échecs de « dérive de tests »** : le code avait évolué, les assertions non. Un test attendait `"Lignes:"` quand le code produisait `"Lignes : "` (typographie française) ; un autre vérifiait que `describe_categorical` renvoyait au plus 3 éléments, alors qu'il expose désormais 7 indicateurs ; la méthode `generate_report` avait été renommée `generate_md_report` sans mise à jour des appelants.
* **2 échecs révélant de vrais bugs de production** : ceux-là étaient masqués par le bruit des 15 autres, et c'est précisément le danger d'une suite de tests durablement rouge.

### 2. Les bugs silencieux mis au jour
Deux défauts sérieux se cachaient derrière ces échecs, dont un bloquant :

* **`clip_outliers` cassait le pipeline de bout en bout** : écrêter une colonne entière (type `Int64` nullable) avec une borne IQR flottante lève une exception dans pandas, qui refuse d'insérer une valeur non entière dans un `IntegerArray`. Le paradoxe est cruel : c'est `fix_numeric_types` qui produit ces `Int64`, si bien que le moteur se sabotait lui-même dès qu'une colonne entière contenait une valeur aberrante. La correction resserre les bornes vers l'intérieur de la clôture IQR (`ceil` pour la borne basse, `floor` pour la haute), ce qui préserve l'intégrité du type entier.
* **La détection de dates était du code mort** : le garde-fou de performance `_can_be_numeric`, introduit pour éviter d'analyser inutilement les colonnes textuelles, exécutait un `continue` sur toute colonne non numérique. Or une date (`"01/01/2023"`) n'est pas numérique. Le bloc de conversion en `datetime`, situé 90 lignes plus bas, n'était donc **jamais atteint** — une fonctionnalité documentée dans le README mais inopérante depuis l'optimisation de l'Étape 26.

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

## Étape 31 : Industrialisation de la Couche Graphique : Sortie de PyPlot et Figures Réutilisables 🎨🔧

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

*Projet en cours de développement - Capacité d'analyse visuelle et reporting autonome validée.*