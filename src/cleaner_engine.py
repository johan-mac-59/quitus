import math
import warnings

import pandas as pd
import numpy as np
from typing import Tuple

def clean_empty_columns(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """Supprime les colonnes avec >95% de valeurs manquantes."""
    if df.empty:
        return df, 0
    # On compte les NA (NaN, None, etc.)
    na_ratio = df.isna().mean()
    cols_to_drop = na_ratio[na_ratio >= 0.95].index.tolist()
    
    n_dropped = len(cols_to_drop)
    if n_dropped > 0:
        df_cleaned = df.drop(columns=cols_to_drop)
    else:
        df_cleaned = df.copy() # Sûr de retourner une copie si rien ne change
        
    return df_cleaned, n_dropped

def clean_whitespace(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """Nettoie les espaces superflus dans les colonnes de type string."""
    if df.empty:
        return df, 0
    
    n_modified = 0
    df_cleaned = df.copy()
    
    # On cible les colonnes string (object ou new StringDtype)
    cols_to_process = df_cleaned.select_dtypes(include=['object', 'string']).columns

    for col in cols_to_process:
        original = df_cleaned[col]

        # Les valeurs manquantes doivent rester manquantes. Un astype(str) global
        # les transformerait en la chaîne littérale "nan", que le reste du
        # pipeline traiterait ensuite comme une vraie catégorie textuelle.
        null_mask = original.isna()

        cleaned_values = (
            original.astype(str)
            .str.strip()
            .str.replace(r'\s+', ' ', regex=True)
        )
        cleaned_values = cleaned_values.where(~null_mask, original)

        # On ne compte que les valeurs réellement présentes ET réellement modifiées.
        # Comparer deux NaN renverrait toujours « différent ».
        changed_mask = (~null_mask) & (original.astype(str) != cleaned_values)

        n_modified += int(changed_mask.sum())

        df_cleaned[col] = cleaned_values

    return df_cleaned, n_modified

def fix_numeric_types(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    """
    Corrige les colonnes que Pandas a chargées en float à tort (ex: '1.0' au lieu de 1)
    pour les passer en entier nullable si possible.
    """
    conversions = {}
    df_cleaned = df.copy()

    for col in df_cleaned.columns:
        # Si la colonne est déjà un entier standard ou un objet, on ne touche pas
        if pd.api.types.is_integer_dtype(df_cleaned[col]) or df_cleaned[col].dtype == 'object':
            continue
            
        # On cible uniquement les colonnes Float chargées automatiquement
        if not pd.api.types.is_float_dtype(df_cleaned[col]):
            continue

        series = df_cleaned[col]
        
        # Vérifier si toutes les valeurs non nulles sont des entiers (ex: 2.0, 5.0)
        non_na = series.dropna()
        if len(non_na) == 0:
            continue
            
        # Si la partie décimale est toujours 0, c'est un entier déguisé
        if (non_na % 1 == 0).all():
            try:
                # On convertit en Entier Nullable (Int64 avec 'I' majuscule)
                # Ce type accepte les NaN sous forme de <NA>
                df_cleaned[col] = series.astype('Int64')
                conversions[col] = 'float64 -> Int64 (correction Pandas)'
            except Exception as e:
                # Si l'overflow ou autre erreur, on laisse en float
                pass

    return df_cleaned, conversions

def _can_be_numeric(series: pd.Series) -> bool:
    """
    Détermine si une colonne de type string/objet peut être convertie en nombre.
    
    Règles de filtrage (Heuristiques) :
    1. Ignorer les identifiants alphanumériques mixtes (ex: 'R43873', 'AB-12').
       Si le contenu contient des lettres isolées (pas juste dans des mots comme 'euro'), on garde en string.
    2. Ignorer les formats complexes non numériques purs (ex: '4/5', '10%').
       On ne touche que ce qui ressemble strictement à un nombre (chiffres, signes, séparateurs décimaux).
    3. Accepter les nombres avec symboles monétaires (€, $, £) ou espaces de milliers.
    """
    # On ignore les colonnes vides
    valid_data = series.dropna()
    if len(valid_data) == 0:
        return False

    # On prend un échantillon significatif pour la détection (plus rapide et robuste)
    sample = valid_data.head(100) 
    non_numeric_count = 0
    
    for val in sample:
        val_str = str(val).strip()
        
        # Si la valeur est vide après strip, on continue
        if not val_str:
            continue
            
        # Règle 1 : Détection d'ID alphanumérique mixte
        # Si on trouve des lettres qui ne sont pas dans un mot complet (ex 'euro' est OK si c'est rare, 
        # mais 'R43873' non plus. Ici on veut éviter les IDs type 'A12B').
        # On vérifie si la chaine contient à la fois des chiffres et des lettres alphabétiques pures.
        if any(c.isalpha() for c in val_str) and any(c.isdigit() for c in val_str):
            # Est-ce que c'est un mot complet (comme 'euro') ou un mélange ID-like ?
            # On considère qu'un ID mixte est valide si les lettres et chiffres sont collés ou séparés par des tirets simples
            # Mais pour être sûr, on va utiliser une regex simple : si il y a des lettres ET des chiffres, 
            # on vérifie si c'est du type "Lettres+Chiffres" pur.
            if not val_str.replace('-', '').replace('_', '').isalpha() and \
               not val_str.replace('-', '').replace('_', '').isdigit():
                return False

        # Règle 2 : Détection de formats complexes ('/', '%', etc.)
        # On accepte uniquement les caractères autorisés pour un nombre : chiffres, signes, points, virgules, espaces, $, €
        allowed_chars = set("0123456789+-.,;€$£ ")
        if any(c not in allowed_chars for c in val_str):
            return False
            
    # Si on est là, tous les échantillons valides sont "proches" d'un nombre.
    return True

def clean_types(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    """Convertit automatiquement les types de colonnes en toute sécurité."""
    if df.empty:
        return df.copy(), {} 
    
    conversions = {}
    df_cleaned = df.copy()

    for col in df_cleaned.columns:
        # 1. Si déjà numeric/datetime on passe (sauf si on veut ré-analyser, mais on suppose que c'est propre)
        if pd.api.types.is_numeric_dtype(df_cleaned[col]) or pd.api.types.is_datetime64_any_dtype(df_cleaned[col]):
            continue

        # On force en string pour uniformiser le traitement des "objets"
        if df_cleaned[col].dtype == 'object':
            df_cleaned[col] = df_cleaned[col].astype('string')

        # 2. Filtrage rapide : est-ce que cette colonne a CHANCE d'être numérique ?
        # Si non (ex: notes "4/5", IDs "A12-B", dates "01/01/2023"), on saute
        # uniquement la branche numérique — la détection de date reste à tenter
        # plus bas. (Un `continue` ici rendrait le bloc date inatteignable.)
        if _can_be_numeric(df_cleaned[col]):
            df_cleaned, conversions = _try_numeric_conversion(df_cleaned, col, conversions)

        # --- Tentative Date (seulement si la colonne n'a PAS été convertie en nombre) ---
        if col not in conversions:
            df_cleaned, conversions = _try_datetime_conversion(df_cleaned, col, conversions)

    # Pour garder trace des colonnes concernées dans les conversions
    conversions_with_cols = {}
    for col, conv_type in conversions.items():
        if col not in conversions_with_cols:
            conversions_with_cols[col] = []
        conversions_with_cols[col].append(conv_type)

    return df_cleaned, conversions_with_cols


def _try_numeric_conversion(df_cleaned: pd.DataFrame, col: str, conversions: dict) -> Tuple[pd.DataFrame, dict]:
    """Tente de convertir une colonne texte en numérique (monnaies, séparateurs).

    Args:
        df_cleaned: DataFrame en cours de nettoyage.
        col: Nom de la colonne à convertir.
        conversions: Dictionnaire des conversions déjà effectuées.

    Returns:
        Le DataFrame et le dictionnaire de conversions, mis à jour.
    """
    # 3. Nettoyage spécifique NUMÉRIQUE AVANT conversion
    # On prépare les données pour que pd.to_numeric fonctionne à 100%
    cleaned_series = df_cleaned[col].copy()

    # A. Suppression des symboles monétaires et espaces inutiles (séparateurs de milliers)
    cleaned_series = cleaned_series.str.replace('€', '', regex=False)
    cleaned_series = cleaned_series.str.replace('$', '', regex=False)
    # Les espaces ne sont supprimés que si la colonne est susceptible d'être numérique
    # On vérifie d'abord si la colonne peut être numérique avant de supprimer les espaces

    # B. Gestion intelligente des séparateurs : Virgule vs Point

    # Cas A : La colonne contient des virgules ET des points.
    # Règle : On suppose le format Européen/Américain mixte où la virgule est le décimal et le point est le millier.
    # Ex: "1.234,50" -> "1234.50"
    if cleaned_series.str.contains(',', regex=False).any() and cleaned_series.str.contains(r'\.', regex=False).any():
        cleaned_series = cleaned_series.str.replace('.', '', regex=False) # Supprime les milliers
        cleaned_series = cleaned_series.str.replace(',', '.', regex=False) # Transforme le décimal en point standard

    # Cas B : La colonne contient UNE virgule mais PAS de point.
    # Règle : La virgule est le séparateur décimal.
    # Ex: "1234,50" -> "1234.50"
    elif cleaned_series.str.contains(',', regex=False).any():
        cleaned_series = cleaned_series.str.replace(',', '.', regex=False)

    # Cas C : La colonne contient UN point mais PAS de virgule.
    # Règle : On ne touche à rien par défaut. pd.to_numeric gère nativement les décimales US (point).
    # Ex: "715.90" reste "715.90" et sera converti en 715.9.
    # C'est crucial : si tu supprimes le point ici, "715.90" devient "71590".

    # C. Remplacement des NaN textuels éventuels par np.nan
    cleaned_series = cleaned_series.replace(['', 'nan', 'None', 'NULL'], np.nan)

    # 4. Tentative de conversion numérique
    numeric_data = pd.to_numeric(cleaned_series, errors='coerce')

    # Si après nettoyage, on a encore trop de NaN, c'est que la colonne n'était pas si
    # numérique que ça (peut-être des erreurs de format). Seuil de validité : 90%.
    cleaned_valid_rate = numeric_data.notna().sum() / len(numeric_data)

    if cleaned_valid_rate > 0.9:
        non_na_values = numeric_data.dropna()

        # Vérification robuste pour les entiers : sont-ce vraiment des entiers ?
        is_likely_int = (
            len(non_na_values) > 0 and
            # Les valeurs sont égales à leur version entière
            (non_na_values == non_na_values.astype(int)).all() and
            # Pas de NaN restants après conversion int (rare mais possible si overflow ou erreur)
            not numeric_data.isna().any()
        )

        if is_likely_int:
            # ON GARDE DES INTS SI POSSIBLE
            df_cleaned[col] = numeric_data.astype(np.int64)
            conversions[col] = 'object -> int'
        else:
            # SINON FLOAT
            df_cleaned[col] = numeric_data.astype(np.float64)
            conversions[col] = 'object -> float'

    return df_cleaned, conversions


# Formats de date testés explicitement, dans l'ordre de priorité.
# Les essayer nommément évite les avertissements de pandas et les mauvaises
# interprétations jour/mois que l'inférence automatique peut produire.
_DATE_FORMATS = (
    '%d/%m/%Y',
    '%Y-%m-%d',
    '%d-%m-%Y',
    '%Y/%m/%d',
    '%d/%m/%Y %H:%M:%S',
    '%Y-%m-%d %H:%M:%S',
)


def _try_datetime_conversion(df_cleaned: pd.DataFrame, col: str, conversions: dict,
                             min_valid_rate: float = 0.8) -> Tuple[pd.DataFrame, dict]:
    """Tente de convertir une colonne texte en datetime.

    Essaie d'abord chaque format explicite de `_DATE_FORMATS`, puis retombe sur
    l'inférence de pandas. Le meilleur taux de réussite l'emporte, à condition de
    dépasser `min_valid_rate`.

    Args:
        df_cleaned: DataFrame en cours de nettoyage.
        col: Nom de la colonne à convertir.
        conversions: Dictionnaire des conversions déjà effectuées.
        min_valid_rate: Proportion minimale de valeurs correctement interprétées.

    Returns:
        Le DataFrame et le dictionnaire de conversions, mis à jour.
    """
    series = df_cleaned[col]
    if series.notna().sum() == 0:
        return df_cleaned, conversions

    best_data = None
    best_rate = 0.0

    for fmt in _DATE_FORMATS:
        try:
            date_data = pd.to_datetime(series, format=fmt, errors='coerce')
        except (ValueError, TypeError):
            continue
        rate = date_data.notna().sum() / len(date_data)
        if rate > best_rate:
            best_data, best_rate = date_data, rate
        # Format parfait : inutile de tester les suivants
        if best_rate == 1.0:
            break

    # Repli sur l'inférence de pandas si aucun format explicite ne convainc.
    # On accepte ici sciemment l'inférence, donc on tait l'avertissement
    # « Could not infer format » qui n'apporte rien à l'utilisateur.
    if best_rate < min_valid_rate:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                date_data = pd.to_datetime(series, errors='coerce')
            rate = date_data.notna().sum() / len(date_data)
            if rate > best_rate:
                best_data, best_rate = date_data, rate
        except (ValueError, TypeError):
            pass

    if best_data is not None and best_rate > min_valid_rate:
        df_cleaned[col] = best_data
        conversions[col] = 'object -> datetime'

    return df_cleaned, conversions


def clean_duplicates(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """Supprime les doublons exacts."""
    if df.empty:
        return df, 0
    
    df_cleaned = df.copy() 
    n_before = len(df_cleaned)
    
    # On garde la première occurrencee
    df_cleaned = df_cleaned.drop_duplicates(keep='first')
    
    n_removed = n_before - len(df_cleaned)
    return df_cleaned, n_removed

def prepare_target_columns_for_case_cleaning(profiler_results: dict) -> list:
    """
    Détermine les colonnes cibles pour le nettoyage de la casse basé sur les résultats du profiler.
    
    Args:
        profiler_results (dict): Résultats du DataProfiler
        
    Returns:
        list: Liste des noms de colonnes à traiter
    """
    target_cols = []
    if profiler_results and 'describe_categorical' in profiler_results:
        for col, stats in profiler_results['describe_categorical'].items():
            anomalies = stats.get('format_anomalies', [])
            # On cible les colonnes qui ont des problèmes de casse OU d'espaces détectés par le profiler
            if any("Variations de casse" in str(a) or "Espaces" in str(a) for a in anomalies):
                target_cols.append(col)
    return target_cols

def clean_case_sensitivity(df: pd.DataFrame, target_columns: list = None) -> Tuple[pd.DataFrame, dict]:
    """
    Unifie la casse des colonnes catégorielles en minuscules.
    
    Args:
        df: DataFrame à nettoyer
        target_columns: Liste optionnelle de colonnes spécifiques à traiter.
                        Si None, analyse toutes les colonnes string (comportement par défaut).
    """
    if df.empty:
        return df.copy(), {}
    
    df_cleaned = df.copy()
    corrections = {}
    
    # 1. Identification des colonnes candidates
    if target_columns:
        # On garde seulement celles qui existent dans le DF et qui sont de type string/object
        cols_to_process = [c for c in target_columns if c in df_cleaned.columns and df_cleaned[c].dtype in ['object', 'string']]
    else:
        # Comportement par défaut : tout scanner
        cols_to_process = df_cleaned.select_dtypes(include=['object', 'string']).columns

    print(f"🔍 Traitement de la casse sur {len(cols_to_process)} colonne(s) ciblée(s)...")

    for col in cols_to_process:
        # ... (ton code actuel commence ici) ...
        
        # 1. Créer un masque des valeurs NON manquantes
        valid_mask = df_cleaned[col].notna()
        
        if not valid_mask.any():
            continue
            
        sample = df_cleaned[col][valid_mask].head(10)
        
        # --- Filtre de sécurité : Ignorer les IDs alphanumériques ou non-textes ---
        is_id_like = False
        for val in sample:
            val_str = str(val)
            # Si l'échantillon contient des chiffres et des lettres, c'est suspect (ID, code postal mixte, etc.)
            if any(c.isalpha() for c in val_str) and any(c.isdigit() for c in val_str):
                if len(val_str) < 10: 
                    is_id_like = True
                    break 
        
        if is_id_like:
            continue

        # Si l'échantillon ne contient aucune lettre (ex: codes postaux "75001"), pas besoin de lower()
        has_letters = sample.astype(str).str.contains('[a-zA-Z]').any()
        if not has_letters:
            continue

        # 2. Appliquer lower() UNIQUEMENT sur les valeurs valides
        original_valid = df_cleaned[col][valid_mask].astype(str)
        lowered = original_valid.str.lower()
        
        # On ne retient que les vraies différences de casse (ex: "Paris" -> "paris")
        # On exclut les cas comme "NaN" -> "nan" qui sont des artefacts de conversion
        changed_mask = original_valid != lowered
        
        # Filtre : on ignore les changements purement liés aux mots vides/textuels standards ("NaN", "None")
        nan_text_mask = original_valid.str.lower().isin(['nan', 'none', 'na', 'null'])
        
        # La correction est réelle si elle change la chaîne ET qu'elle contient des lettres alphabétiques visibles
        real_change_mask = changed_mask & ~nan_text_mask & (original_valid.str.contains('[a-zA-Z]').fillna(False))

        n_changes = real_change_mask.sum()
        
        if n_changes > 0:
            df_cleaned.loc[df_cleaned[col].notna(), col] = lowered.where(real_change_mask, df_cleaned[col][valid_mask])
            corrections[col] = int(n_changes)
    
    return df_cleaned, corrections

def clean_missing_values(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    """Nettoie les valeurs manquantes de manière intelligente."""
    if df.empty:
        return df.copy(), {}
    
    actions = {}
    df_cleaned = df.copy()

    for col in df_cleaned.columns:
        null_count = df_cleaned[col].isna().sum()
        if null_count > 0:
            if pd.api.types.is_numeric_dtype(df_cleaned[col]):
                median_val = df_cleaned[col].median()
                # On remplit uniquement les NaN, sans changer le type de la colonne
                mask = df_cleaned[col].isna()
                df_cleaned.loc[mask, col] = median_val
                actions[col] = {
                    'count': null_count,
                    'method': f"fill_median_{median_val}"  # Correction : on n'utilise pas mode_val ici
    }
            
            else:
                mode_val = df_cleaned[col].mode()[0] if not df_cleaned[col].mode().empty else 'Inconnu'
                # On force le type string pour éviter les erreurs lors du fillna
                mask = df_cleaned[col].isna()
                df_cleaned.loc[mask, col] = str(mode_val)
                actions[col] = {
                    'count': null_count,
                    'method': f"fill_mode_{str(mode_val)}"
                }

    return df_cleaned, actions

def clip_outliers(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    """Corrige les valeurs aberrantes avec la méthode IQR (Cliping)."""
    if df.empty:
        return df.copy(), {}

    # Copie défensive : sans elle, les affectations df[col] = ... plus bas
    # modifieraient le DataFrame de l'appelant.
    df = df.copy()

    corrections = {}
    # On s'assure de prendre uniquement les colonnes numériques actives
    numeric_cols = df.select_dtypes(include=[np.number]).columns

    for col in numeric_cols:
        non_null_data = df[col].dropna()
        
        # Cas limite : si on a trop peu de données, l'IQR n'est pas fiable
        if non_null_data.empty or len(non_null_data) < 2: 
            continue
            
        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1
        
        # Si l'IQR est 0 (toutes les valeurs sont identiques), on ne peut pas calculer de borne standard
        if IQR == 0:
            continue

        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR

        n_outliers = ((df[col] < lower_bound) | (df[col] > upper_bound)).sum()

        if n_outliers > 0:
            # Sur une colonne entière (dont Int64 nullable), écrêter avec une borne
            # flottante lève une erreur : pandas refuse d'insérer
            # une valeur non entière dans un IntegerArray.
            # On resserre donc les bornes vers l'intérieur de la clôture IQR.
            if pd.api.types.is_integer_dtype(df[col].dtype):
                clip_low = int(math.ceil(lower_bound))
                clip_high = int(math.floor(upper_bound))
            else:
                clip_low, clip_high = lower_bound, upper_bound

            df_cleaned_col = df[col].clip(lower=clip_low, upper=clip_high)

            # Mise à jour en préservant le type numérique standard si possible
            if df_cleaned_col.dtype != df[col].dtype:
                df[col] = df_cleaned_col.astype(np.float64)
            else:
                df[col] = df_cleaned_col

            corrections[col] = int(n_outliers)

    return df, corrections

SEPARATEUR = "=" * 60


def summarize_outliers(df: pd.DataFrame, stats: dict = None,
                       profiler_results: dict = None) -> dict:
    """Résume les valeurs aberrantes détectées, sans aucune entrée/sortie.

    Fonction pure : l'interface en ligne de commande s'en sert pour composer son
    affichage, l'interface web pour remplir le texte d'aide de ses widgets.

    Args:
        df: DataFrame analysé.
        stats: Statistiques de nettoyage déjà collectées, éventuellement porteuses
            d'une clé `outliers_corrected`.
        profiler_results: Résultats complets du profileur, porteurs d'une clé
            `outliers`.

    Returns:
        Un dictionnaire à trois clés : `has_outliers` (bool), `columns`
        (nom de colonne -> nombre d'outliers) et `lines` (lignes de texte
        prêtes à afficher).
    """
    stats = stats or {}
    profiler_results = profiler_results or {}

    raw = profiler_results.get('outliers') or stats.get('outliers_corrected') or {}

    # Le profileur renvoie {col: {'count': n, ...}} ; d'anciens formats
    # renvoyaient directement {col: n}. On normalise les deux.
    columns = {}
    if isinstance(raw, dict):
        for col, info in raw.items():
            if col == 'ignored':
                continue
            if isinstance(info, dict):
                columns[col] = info.get('count', 0)
            elif isinstance(info, (int, float)):
                columns[col] = int(info)

    # Le profilage a lieu AVANT la correction des types : une colonne de montants
    # encore stockée en texte (« 1 200,50 € ») n'y apparaît pas comme numérique et
    # ne révèle donc aucun outlier. Sans ce complément, l'utilisateur ne se verrait
    # jamais proposer d'écrêter la colonne qui en a le plus besoin.
    latents = _outliers_apres_typage(df, deja_vues=set(columns))
    columns.update(latents)

    lines = []
    if not columns:
        lines.append("✅ Aucune valeur aberrante détectée dans les données.")
    else:
        lines.append(f"🔍 {len(columns)} colonne(s) contient(ent) des valeurs aberrantes :")
        for col, count in columns.items():
            suffixe = " (après correction des types)" if col in latents else ""
            lines.append(f"   • {col}: {count} outliers détectés{suffixe}")
        lines.append("Les valeurs aberrantes sont corrigées par la méthode IQR (clipping).")
        lines.append("Cela peut modifier les bornes statistiques et altérer les distributions.")

    return {'has_outliers': bool(columns), 'columns': columns, 'lines': lines}


def _outliers_apres_typage(df: pd.DataFrame, deja_vues: set = None) -> dict:
    """Compte les outliers des colonnes textuelles convertibles en numérique.

    Complète le diagnostic du profileur, qui ne voit que les colonnes déjà
    typées. Le comptage est indicatif : c'est `clip_outliers` qui tranchera, sur
    des types définitivement corrigés.

    Args:
        df: DataFrame analysé.
        deja_vues: Colonnes déjà comptabilisées, à ne pas recompter.

    Returns:
        Un dictionnaire nom de colonne -> nombre d'outliers estimé.
    """
    deja_vues = deja_vues or set()
    resultats = {}

    if df is None or df.empty:
        return resultats

    for col in df.select_dtypes(include=['object', 'string']).columns:
        if col in deja_vues or not _can_be_numeric(df[col]):
            continue

        # Même normalisation que clean_types, en version condensée : on veut une
        # estimation, pas une conversion définitive.
        serie = (
            df[col].astype('string')
            .str.replace('€', '', regex=False)
            .str.replace('$', '', regex=False)
            .str.replace(',', '.', regex=False)
        )
        numerique = pd.to_numeric(serie, errors='coerce').dropna()
        if len(numerique) < 4:
            continue

        q1, q3 = numerique.quantile(0.25), numerique.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue

        n = int(((numerique < q1 - 1.5 * iqr) | (numerique > q3 + 1.5 * iqr)).sum())
        if n > 0:
            resultats[col] = n

    return resultats


def summarize_missing_values(df: pd.DataFrame) -> dict:
    """Résume les valeurs manquantes du DataFrame, sans aucune entrée/sortie.

    Args:
        df: DataFrame analysé.

    Returns:
        Un dictionnaire à trois clés : `total` (nombre total de valeurs
        manquantes), `by_column` (nom de colonne -> (nombre, pourcentage)) et
        `lines` (lignes de texte prêtes à afficher).
    """
    total = int(df.isnull().sum().sum())

    by_column = {}
    if len(df) > 0:
        counts = df.isnull().sum()
        for col, count in counts[counts > 0].items():
            by_column[col] = (int(count), round(count / len(df) * 100, 1))

    lines = []
    if total == 0:
        lines.append("✅ Aucune valeur manquante détectée dans les données.")
    else:
        lines.append(f"🔍 {total} valeurs manquantes détectées dans l'ensemble du dataset")
        if by_column:
            lines.append("Répartition par colonne :")
            for col, (count, pct) in by_column.items():
                lines.append(f"   • {col}: {count} ({pct}%)")
        lines.append("Les valeurs manquantes sont comblées automatiquement :")
        lines.append("- Pour les colonnes numériques : médiane")
        lines.append("- Pour les colonnes catégorielles : mode")

    return {'total': total, 'by_column': by_column, 'lines': lines}


def _colonnes_numerisables(df: pd.DataFrame) -> list:
    """Liste les colonnes textuelles convertibles en numérique.

    Sert à avertir l'utilisateur que le décompte d'outliers issu du profilage
    est incomplet : le profilage précède la correction des types, donc une
    colonne de montants encore stockée en texte (« 1 200,50 € ») n'y figure pas
    comme numérique.

    Args:
        df: DataFrame analysé.

    Returns:
        Les noms des colonnes textuelles susceptibles de devenir numériques.
    """
    candidates = []
    for col in df.select_dtypes(include=['object', 'string']).columns:
        if _can_be_numeric(df[col]):
            candidates.append(col)
    return candidates


def _prompt_yes_no(question: str, default: bool) -> bool:
    """Pose une question fermée en ligne de commande, avec garde de fin de flux.

    La garde sur `EOFError` est ce qui rend ce module importable depuis un
    contexte sans terminal (serveur web, intégration continue, sortie
    redirigée) : au lieu de lever ou de boucler indéfiniment, la valeur par
    défaut est retenue.

    Args:
        question: Libellé de la question.
        default: Valeur retenue sur réponse vide, fin de flux ou interruption.

    Returns:
        La décision de l'utilisateur.
    """
    defaut_txt = 'y' if default else 'n'
    print(f"{question}")
    print(f"(Répondez par 'y' (oui) ou 'n' (non). Par défaut : '{defaut_txt}')")

    while True:
        try:
            reponse = input(f"⏳ Votre choix [y/n, entrée par défaut '{defaut_txt}'] : ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(f"\nℹ️ Aucune réponse lisible : choix par défaut ('{defaut_txt}').")
            return default

        if reponse == "":
            print(f"ℹ️ Choix par défaut : '{defaut_txt}'.")
            return default
        if reponse in ['y', 'yes', 'o', 'oui']:
            return True
        if reponse in ['n', 'no', 'non']:
            return False

        print("⚠️ Veuillez répondre par 'y' (oui) ou 'n' (non).")
        print(f"⏳  Appuyez sur Entrée pour choisir '{defaut_txt}' par défaut.")


def ask_user_outlier_correction(df: pd.DataFrame, stats: dict, profiler_results: dict = None,
                                *, answer: bool = None, default: bool = False) -> bool:
    """Décide s'il faut écrêter les valeurs aberrantes.

    Args:
        df: DataFrame à nettoyer.
        stats: Statistiques de nettoyage actuelles.
        profiler_results: Résultats complets du profileur.
        answer: Réponse imposée ; court-circuite l'invite si elle est fournie.
            C'est par ce paramètre que l'interface web transmet le choix fait
            dans un widget.
        default: Valeur retenue sur réponse vide ou absence de terminal.

    Returns:
        True s'il faut écrêter, False sinon.
    """
    print("\n" + SEPARATEUR)
    print("⚠️  Gestion des Valeurs Aberrantes (Outliers)")
    print(SEPARATEUR)

    summary = summarize_outliers(df, stats, profiler_results)
    for line in summary['lines']:
        print(line)

    # Une consigne explicite prime sur le pré-diagnostic. C'est essentiel ici :
    # le profilage a lieu AVANT la correction des types, donc une colonne encore
    # stockée en texte (montants avec « € » ou virgule décimale) n'est pas vue
    # comme numérique et ne révèle aucun outlier à ce stade. Sortir sur False
    # annulerait silencieusement la demande de l'utilisateur, alors que
    # clip_outliers, lui, travaille sur des types déjà corrigés.
    if answer is not None:
        print(f"➡️ Écrêtage des outliers : {'OUI' if answer else 'NON'} (choix transmis).")
        return answer

    # Rien à corriger et aucune consigne : la question n'a pas lieu d'être posée.
    if not summary['has_outliers']:
        if _colonnes_numerisables(df):
            print("ℹ️ Certaines colonnes textuelles pourraient devenir numériques "
                  "après correction des types : des valeurs aberrantes peuvent "
                  "encore apparaître à ce moment-là.")
        return False

    decision = _prompt_yes_no("Souhaitez-vous corriger ces valeurs aberrantes ?", default)
    print("✅ Vous avez choisi de corriger les valeurs aberrantes."
          if decision else "❌ Vous avez choisi de ne pas corriger les outliers.")
    return decision


def ask_user_missing_values_correction(df: pd.DataFrame, stats: dict, profiler_results: dict = None,
                                       *, answer: bool = None, default: bool = False) -> bool:
    """Décide s'il faut combler les valeurs manquantes.

    Args:
        df: DataFrame à nettoyer.
        stats: Statistiques de nettoyage actuelles.
        profiler_results: Résultats complets du profileur (non utilisé, conservé
            pour la symétrie de signature avec `ask_user_outlier_correction`).
        answer: Réponse imposée ; court-circuite l'invite si elle est fournie.
        default: Valeur retenue sur réponse vide ou absence de terminal.

    Returns:
        True s'il faut combler, False sinon.
    """
    print("\n" + SEPARATEUR)
    print("⚠️  Gestion des Valeurs Manquantes")
    print(SEPARATEUR)

    summary = summarize_missing_values(df)
    for line in summary['lines']:
        print(line)

    # Comme pour les outliers, une consigne explicite prime sur le pré-diagnostic.
    if answer is not None:
        print(f"➡️ Remplissage des valeurs manquantes : {'OUI' if answer else 'NON'} (choix transmis).")
        return answer

    # Rien à combler et aucune consigne : la question n'a pas lieu d'être posée.
    if summary['total'] == 0:
        return False

    decision = _prompt_yes_no("Souhaitez-vous combler ces valeurs manquantes ?", default)
    print("✅ Vous avez choisi de combler les valeurs manquantes."
          if decision else "❌ Vous avez choisi de ne pas combler les valeurs manquantes.")
    return decision


def get_user_decisions(initial_df: pd.DataFrame, profiler_results: dict, *,
                       correct_outliers: bool = None, fill_missing: bool = None,
                       interactive: bool = True) -> Tuple[bool, bool]:
    """Collecte les deux décisions de nettoyage avancé.

    Ordre de priorité : une valeur booléenne explicite l'emporte ; à défaut, et
    si `interactive` est vrai, la question est posée en terminal ; sinon la
    réponse est négative. C'est ce qui permet au même code de servir la ligne
    de commande (qui questionne) et l'interface web (qui transmet).

    Args:
        initial_df: DataFrame initial.
        profiler_results: Résultats du profileur.
        correct_outliers: Décision imposée pour l'écrêtage.
        fill_missing: Décision imposée pour le remplissage.
        interactive: Autorise l'interrogation du terminal.

    Returns:
        Le couple (correct_outliers, fill_missing).
    """
    print("\n" + SEPARATEUR)
    print("🔧 Décisions de Nettoyage Avancé")
    print(SEPARATEUR)

    profiler_results = profiler_results or {}

    # `answer=None` laisse la fonction appelée poser la question ; sinon elle
    # se contente de confirmer la valeur transmise.
    outliers_answer = correct_outliers if correct_outliers is not None else (None if interactive else False)
    missing_answer = fill_missing if fill_missing is not None else (None if interactive else False)

    # On transmet le profil COMPLET, pas son sous-dictionnaire 'outliers' :
    # summarize_outliers y cherche la clé 'outliers', et lui passer un niveau
    # trop bas faisait conclure « aucun outlier » et désactivait silencieusement
    # l'écrêtage dès qu'un profilage existait.
    decided_outliers = ask_user_outlier_correction(
        initial_df, {}, profiler_results, answer=outliers_answer)
    decided_missing = ask_user_missing_values_correction(
        initial_df, {}, profiler_results, answer=missing_answer)

    print(f"\n➡️ Configuration finale : "
          f"\nEcrêtage des Outliers = {'OUI' if decided_outliers else 'NON'}"
          f"\nRemplacement des valeurs manquantes = {'OUI' if decided_missing else 'NON'}")

    return decided_outliers, decided_missing


def run_all_cleaning_steps(df: pd.DataFrame, profile_info: dict = None, max_iterations: int = 5, correct_outliers: bool = True, fill_missing: bool = True) -> Tuple[pd.DataFrame, dict]:
    """
    Applique les nettoyages de manière itérative et ordonnée.
    
    Args:
        df: DataFrame à nettoyer
        max_iterations: Nombre maximum d'itérations
        correct_outliers: Booléen pour décider si on corrige les outliers
        fill_missing: Booléen pour décider si on remplit les valeurs manquantes
    
    Ordre stratégique pour éviter les erreurs en cascade :
    1. Forme (espaces) -> Pour préparer la conversion de types
    2. Types fixes (Pandas Trap) -> Pour corriger les float64 -> Int64 si possible
    3. Conversion Types stricte -> Pour pouvoir faire des calculs statistiques
    4. Structure (doublons/vides) -> Une fois qu'on connaît les vrais types
    5. Stats (Missing/Outliers) -> En dernier, sur des données propres
    """
    stats = {
        'empty_cols_dropped': 0,
        'whitespace_cleaned': 0,
        'case_normalized': {},
        'types_fixed_pandas': {},
        'types_converted': {},
        'duplicates_removed': 0,
        'missing_filled': {},
        'outliers_corrected': {}
    }

    current_df = df.copy()
    
    # ÉTAPE PRÉLIMINAIRE : Utilisation du Profile pour filtrer les cibles
    target_cols_for_case = []
    if profile_info and 'describe_categorical' in profile_info:
        for col, col_stats in profile_info['describe_categorical'].items():
            # Si le profiler a détecté des anomalies de format (donc casse probable)
            if col_stats.get('format_anomalies') and any("Variations de casse" in s or "Espaces" in s for s in col_stats['format_anomalies']):
                target_cols_for_case.append(col)

    # Boucle de nettoyage automatique (sans interaction utilisateur)
    for iteration in range(max_iterations):
        print(f"\n🔄 Itération {iteration + 1}/{max_iterations}")
        
        # Sauvegarder l'état avant le nettoyage
        previous_shape = current_df.shape
        
        # 1. Nettoyage Forme (AVANT les types ! " 45" doit devenir 45)
        current_df, n_spaces = clean_whitespace(current_df)
        if n_spaces > 0:
            stats['whitespace_cleaned'] += n_spaces

        # 2. Correction des types "Pandas Trap" 
        current_df, fix_stats = fix_numeric_types(current_df)
        if fix_stats:
            stats['types_fixed_pandas'].update(fix_stats)

        # 3. Conversion Types (CRITIQUE : on transforme " 45" en int/float maintenant)
        current_df, conversions = clean_types(current_df)
        if conversions:
            stats['types_converted'].update(conversions)

        # 4. Nettoyage Structurel (Colonnes vides)
        current_df, n_dropped = clean_empty_columns(current_df)
        if n_dropped > 0:
            stats['empty_cols_dropped'] += n_dropped

        # 5. Nettoyage de la casse CIBLÉ ou GLOBAL
        if target_cols_for_case:
            current_df, case_corrections = clean_case_sensitivity(current_df, target_columns=target_cols_for_case)
        else:
            current_df, case_corrections = clean_case_sensitivity(current_df) # Fallback global
            
        if case_corrections:
            stats['case_normalized'].update(case_corrections)

        # 6. Doublons (Avant IQR/Median pour ne pas fausser les bornes)
        current_df, n_dups = clean_duplicates(current_df)
        if n_dups > 0:
            stats['duplicates_removed'] += n_dups

        # 7. Vérification si on continue ou non
        # Si aucune modification n'a été faite (ni ligne ni colonne ni type), on arrête
        current_shape = current_df.shape
        
        # Vérifier s'il y a eu des changements dans la structure
        changes_detected = (
            n_spaces > 0 or 
            len(fix_stats) > 0 or 
            len(conversions) > 0 or 
            n_dropped > 0 or 
            sum(case_corrections.values()) > 0 or 
            n_dups > 0 or
            current_shape != previous_shape  # Si le nombre de lignes ou colonnes a changé
        )
        
        if not changes_detected:
            print("✅ Aucune modification détectée. Arrêt anticipé du nettoyage.")
            break
    
    # 8. Missing Values (Remplissage) - Exécuté ici de manière explicite
    if fill_missing:
        current_df, fillings = clean_missing_values(current_df)
        if fillings:
            stats['missing_filled'].update(fillings)
        else:
            # Si le traitement est actif mais qu'il n'y avait pas de valeurs à combler, 
            # on garde un dictionnaire vide (cohérent avec le cas où il y en avait)
            pass 
    else:
        print("🧐 Remplissage des valeurs manquantes ignoré par l'utilisateur.")
        # Format cohérent : on indique explicitement que c'est ignoré
        stats['missing_filled'] = {'ignored': True}

    # 9. Outliers IQR (En dernier, sur données numérées et propres) 
    if correct_outliers:
        current_df, outliers = clip_outliers(current_df)
        if outliers:
            for col, count in outliers.items():
                stats['outliers_corrected'][col] = stats['outliers_corrected'].get(col, 0) + count
    else:
        print("🧐 Correction des outliers ignorée par l'utilisateur.")
        # On indique simplement dans les stats que c'est ignoré avec un format cohérent
        stats['outliers_corrected'] = {'ignored': True}  # Format cohérent
    
    return current_df, stats

