"""Chargement intelligent de fichiers tabulaires, quelle que soit leur origine.

Le module expose deux portes d'entrée équivalentes :

* `load_file(chemin)` — pour la ligne de commande, qui part d'un fichier sur disque ;
* `load_dataframe(octets, nom)` — pour l'interface web, qui reçoit un fichier
  déposé dans le navigateur et n'a jamais de chemin à lui offrir.

Toute la logique de détection (format, encodage, séparateur) vit dans le coeur
orienté octets. Les fonctions orientées chemin ne sont que des enveloppes, ce
qui garantit un comportement identique dans les deux modes.
"""

import json
import os
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Union

import numpy as np
import pandas as pd

from src.cleaner_engine import has_leading_zero


# --------------------------------------------------------------------------
# Portes d'entrée publiques
# --------------------------------------------------------------------------

def load_dataframe(source: Union[bytes, bytearray, BinaryIO], filename: str) -> pd.DataFrame:
    """Charge un DataFrame depuis des octets en mémoire.

    Args:
        source: Contenu du fichier, en octets ou sous forme de flux binaire.
        filename: Nom du fichier, dont l'extension détermine le format. Le
            fichier lui-même n'a pas besoin d'exister sur le disque.

    Returns:
        Le DataFrame chargé.

    Raises:
        ValueError: Si le format ne peut être ni déduit ni détecté.
    """
    data = bytes(source) if isinstance(source, (bytes, bytearray)) else source.read()

    ext = os.path.splitext(filename)[1].lower()
    print(f"📂 Chargement du fichier : {filename}")

    if ext == '.csv':
        df = _csv_from_bytes(data)
    elif ext in ('.xlsx', '.xls'):
        print("   -> Format Excel détecté.")
        df = _excel_from_bytes(data)
    elif ext == '.json':
        df = _json_from_bytes(data)
    elif ext == '.jsonl':
        df = _jsonl_from_bytes(data)
    elif ext == '.parquet':
        df = _parquet_from_bytes(data)
    else:
        df = _sniff_from_bytes(data, ext)
    return _serialiser_cellules_imbriquees(df)


def _serialiser_cellules_imbriquees(df: pd.DataFrame) -> pd.DataFrame:
    """Écrit en texte JSON les cellules qui contiennent une structure.

    Un JSON imbriqué ou un fichier Parquet peut porter, dans une cellule, une
    liste ou un objet. Le profilage et le nettoyage comparent et comptent des
    valeurs : une liste n'est pas comparable, et le profilage échouait. Écrite
    en texte JSON, la cellule garde tout son contenu, lisible et comparable.

    Args:
        df: DataFrame chargé.

    Returns:
        Le même DataFrame, cellules structurées écrites en texte JSON.
    """
    for col in df.columns:
        if df[col].dtype != object:
            continue
        structurees = df[col].map(lambda v: isinstance(v, (list, tuple, dict, np.ndarray)))
        if not structurees.any():
            continue
        df[col] = df[col].map(lambda v: json.dumps(_vers_python(v), ensure_ascii=False, default=str)
                              if isinstance(v, (list, tuple, dict, np.ndarray)) else v)
        print(f"   -> Colonne « {col} » : contenu structuré écrit en texte JSON.")
    return df


def _vers_python(valeur):
    """Convertit récursivement une structure en types Python sérialisables.

    Args:
        valeur: Cellule ou élément de cellule.

    Returns:
        La même donnée, tableaux NumPy convertis en listes.
    """
    if isinstance(valeur, np.ndarray):
        valeur = valeur.tolist()
    if isinstance(valeur, (list, tuple)):
        return [_vers_python(v) for v in valeur]
    if isinstance(valeur, dict):
        return {str(k): _vers_python(v) for k, v in valeur.items()}
    return valeur


def load_file(file_path: str) -> pd.DataFrame:
    """Charge un fichier du disque dans un DataFrame, selon son extension.

    Args:
        file_path: Chemin vers le fichier à charger.

    Returns:
        Le DataFrame chargé.

    Raises:
        FileNotFoundError: Si le fichier n'existe pas.
        ValueError: Si l'extension n'est pas supportée et que le format ne peut
            être détecté.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Le fichier {file_path} est introuvable.")

    try:
        data = Path(file_path).read_bytes()
        return load_dataframe(data, file_path)
    except Exception as e:
        print(f"❌ Erreur lors du chargement : {e}")
        raise


# --------------------------------------------------------------------------
# Coeur orienté octets
# --------------------------------------------------------------------------

def _csv_from_bytes(data: bytes) -> pd.DataFrame:
    """Charge un CSV en détectant automatiquement l'encodage et le séparateur.

    Args:
        data: Contenu brut du fichier.

    Returns:
        Le DataFrame chargé, vide si le contenu l'est.
    """
    if not data:
        print("   -> ⚠️ Fichier vide détecté")
        return pd.DataFrame()

    encoding = _detect_encoding_bytes(data)
    sample_text = data[:4096].decode(encoding, errors='replace')
    delimiter = _detect_delimiter(sample_text)
    print(f"   -> Séparateur : '{delimiter}' | Encodage : {encoding}")

    try:
        return _lire_en_protegeant_les_codes(
            lambda **options: pd.read_csv(BytesIO(data), sep=delimiter, encoding=encoding, **options))
    except pd.errors.EmptyDataError:
        # Fichier non strictement vide, mais sans colonne exploitable.
        return pd.DataFrame()


def _lire_en_protegeant_les_codes(lire) -> pd.DataFrame:
    """Lit un fichier tabulaire sans retirer le zéro initial de ses codes.

    pandas lit « 0612345678 » comme l'entier 612345678, y compris dans une
    cellule Excel de type texte. Une première lecture, tout en texte, repère les
    colonnes concernées (téléphones, codes postaux, matricules) ; la lecture
    définitive les garde en texte et laisse pandas typer toutes les autres.

    Args:
        lire: Fonction de lecture pandas, appelée avec ses seules options de
            typage (`dtype`).

    Returns:
        Le DataFrame chargé.
    """
    texte = lire(dtype=str)
    codes = {col: str for col in texte.columns if has_leading_zero(texte[col])}
    if not codes:
        return lire()
    print(f"   -> Codes à zéro initial conservés en texte : {', '.join(map(str, codes))}")
    return lire(dtype=codes)


def _excel_from_bytes(data: bytes) -> pd.DataFrame:
    """Charge un fichier Excel depuis des octets.

    Aucun contrôle de vacuité ici, contrairement aux autres formats : un classeur
    Excel sans aucune ligne reste un fichier structurellement valide, qu'openpyxl
    sait lire.

    Args:
        data: Contenu brut du fichier.

    Returns:
        Le DataFrame de la première feuille.
    """
    return _lire_en_protegeant_les_codes(
        lambda **options: pd.read_excel(BytesIO(data), engine='openpyxl', **options))


def _json_from_bytes(data: bytes) -> pd.DataFrame:
    """Charge un JSON standard depuis des octets.

    Args:
        data: Contenu brut du fichier.

    Returns:
        Le DataFrame chargé, vide si le contenu l'est.

    Raises:
        ValueError: Si le JSON est invalide.
    """
    if not data:
        print("   -> ⚠️ Fichier JSON vide détecté")
        return pd.DataFrame()

    try:
        # `dtype=False` : les nombres du JSON restent des nombres, et ses chaînes
        # des chaînes. Sans cela, pandas convertit « "0612345678" » en entier et
        # lui retire son zéro initial. Les autres chaînes numériques sont
        # converties ensuite par le nettoyage, qui recense ce qu'il ne peut lire.
        df = pd.read_json(BytesIO(data), dtype=False)
        print("   -> Format JSON détecté et chargé avec succès.")
        return df
    except Exception as e:
        # pandas est strict sur les structures imbriquées : on retente à la main.
        print(f"   -> Échec du chargement avec pandas, tentative de lecture manuelle : {e}")
        encoding = _detect_encoding_bytes(data)
        return _parse_json_text(data.decode(encoding, errors='replace'))


def _jsonl_from_bytes(data: bytes) -> pd.DataFrame:
    """Charge un fichier JSON Lines depuis des octets.

    Les lignes invalides sont signalées et ignorées, afin qu'un enregistrement
    corrompu ne fasse pas perdre tout le fichier.

    Args:
        data: Contenu brut du fichier.

    Returns:
        Le DataFrame chargé, vide si aucun enregistrement n'est valide.

    Raises:
        ValueError: Si le décodage échoue de manière irrécupérable.
    """
    if not data:
        print("   -> ⚠️ Fichier JSONL vide détecté")
        return pd.DataFrame()

    try:
        encoding = _detect_encoding_bytes(data)
        records = []
        for line_num, line in enumerate(data.decode(encoding, errors='replace').splitlines(), 1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"   -> Erreur de décodage JSON à la ligne {line_num}: {e}")
                continue

        if not records:
            print("   -> Aucun enregistrement valide trouvé dans le fichier JSONL")
            return pd.DataFrame()

        print(f"   -> Format JSONL détecté et chargé avec succès ({len(records)} enregistrements).")
        return pd.DataFrame(records)

    except Exception as e:
        print(f"   -> Erreur lors du chargement du fichier JSONL : {e}")
        raise ValueError(f"Impossible de charger le fichier JSONL : {e}")


def _parse_json_text(content: str) -> pd.DataFrame:
    """Interprète un JSON à la main, quand pandas a renoncé.

    Args:
        content: Texte JSON complet.

    Returns:
        Le DataFrame reconstitué, vide si la structure est inexploitable.

    Raises:
        ValueError: Si le JSON est syntaxiquement invalide.
    """
    try:
        data = json.loads(content)

        # Liste d'objets : cas le plus courant, directement tabulaire.
        if isinstance(data, list) and len(data) > 0:
            if all(isinstance(item, dict) for item in data):
                return pd.DataFrame(data)
            return pd.DataFrame(data)

        # Objet unique : on cherche les clés porteuses de listes, qui font office
        # de colonnes ; à défaut on en fait une ligne unique.
        if isinstance(data, dict):
            colonnes = {}
            for key, value in data.items():
                if isinstance(value, list) and len(value) > 0:
                    if all(isinstance(item, (str, int, float, bool, type(None))) for item in value):
                        colonnes[key] = value

            if colonnes:
                return pd.DataFrame(colonnes)
            return pd.DataFrame([data])

        print(f"   -> Format JSON non reconnu : {type(data)}")
        return pd.DataFrame()

    except json.JSONDecodeError as e:
        print(f"   -> Erreur de décodage JSON : {e}")
        raise ValueError(f"Format JSON invalide : {e}")


# Signature d'un fichier Parquet : ces quatre octets l'ouvrent et le ferment.
_SIGNATURE_PARQUET = b'PAR1'


def _parquet_from_bytes(data: bytes) -> pd.DataFrame:
    """Charge un fichier Parquet depuis des octets.

    Parquet stocke ses types : un nombre y est déjà un nombre, une date une
    date. Le nettoyage n'a donc à corriger que ce qui est resté du texte.

    Args:
        data: Contenu brut du fichier.

    Returns:
        Le DataFrame chargé, vide si le contenu l'est.

    Raises:
        ValueError: Si le contenu n'est pas un fichier Parquet valide.
    """
    if not data:
        print("   -> ⚠️ Fichier Parquet vide détecté")
        return pd.DataFrame()
    try:
        df = pd.read_parquet(BytesIO(data))
    except Exception as e:
        raise ValueError(f"Fichier Parquet illisible : {e}")
    print("   -> Format Parquet détecté et chargé avec succès.")
    # Une colonne catégorielle n'accepte que ses modalités d'origine : la
    # casse uniformisée ou une valeur comblée y seraient refusées.
    for col in df.select_dtypes(include='category').columns:
        df[col] = df[col].astype(object)
    return df


def _sniff_from_bytes(data: bytes, ext: str) -> pd.DataFrame:
    """Tente de détecter le format quand l'extension n'est pas reconnue.

    Args:
        data: Contenu brut du fichier.
        ext: Extension d'origine, reprise dans le message d'erreur.

    Returns:
        Le DataFrame chargé si le format a pu être identifié.

    Raises:
        ValueError: Si le format demeure indéterminé.
    """
    if not data:
        raise ValueError("Impossible de déterminer le format du fichier")

    # Parquet se reconnaît à sa signature, en tête comme en fin de fichier.
    if data[:4] == _SIGNATURE_PARQUET and data[-4:] == _SIGNATURE_PARQUET:
        print("   -> Format Parquet détecté automatiquement.")
        return _parquet_from_bytes(data)

    encoding = _detect_encoding_bytes(data)
    sample = data[:1024].decode(encoding, errors='replace').strip()

    if sample.startswith('{') or sample.startswith('['):
        try:
            json.loads(sample)
            print("   -> Format JSON détecté automatiquement.")
            return _json_from_bytes(data)
        except json.JSONDecodeError:
            # Échantillon tronqué au milieu d'une structure : on tente quand même
            # le document entier avant d'abandonner.
            try:
                return _json_from_bytes(data)
            except Exception:
                pass

    raise ValueError(f"Format de fichier non supporté : {ext}")


def _detect_encoding_bytes(data: bytes) -> str:
    """Détecte l'encodage en essayant les plus courants.

    Args:
        data: Contenu brut du fichier.

    Returns:
        Le nom de l'encodage retenu, `'utf-8'` par défaut.
    """
    echantillon = data[:4096]
    for enc in ('utf-8', 'latin1', 'cp1252'):
        try:
            echantillon.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return 'utf-8'


def _detect_delimiter(sample_text: str) -> str:
    """Détecte le séparateur d'un CSV à partir d'un échantillon de texte.

    Args:
        sample_text: Premières lignes du fichier.

    Returns:
        Le séparateur retenu, la virgule par défaut.
    """
    delimiters = [';', ',', '\t', '|']
    for delim in delimiters:
        lines = sample_text.strip().split('\n')[:3]
        # Le séparateur doit être présent partout ET découper un nombre constant
        # de colonnes : c'est ce qui distingue un vrai séparateur d'un caractère
        # qui se trouve dans les données.
        if lines and all(delim in line for line in lines):
            parts = [line.split(delim) for line in lines]
            if len(set(len(p) for p in parts)) == 1:
                return delim
    return ','


# --------------------------------------------------------------------------
# Enveloppes orientées chemin, conservées pour la compatibilité
# --------------------------------------------------------------------------

def _load_csv(file_path: str) -> pd.DataFrame:
    """Charge un CSV depuis un chemin.

    Args:
        file_path: Chemin du fichier.

    Returns:
        Le DataFrame chargé.
    """
    return _csv_from_bytes(Path(file_path).read_bytes())


def _load_excel(file_path: str) -> pd.DataFrame:
    """Charge un fichier Excel depuis un chemin.

    Args:
        file_path: Chemin du fichier.

    Returns:
        Le DataFrame chargé.
    """
    print("   -> Format Excel détecté.")
    return _excel_from_bytes(Path(file_path).read_bytes())


def _load_json(file_path: str) -> pd.DataFrame:
    """Charge un JSON depuis un chemin.

    Args:
        file_path: Chemin du fichier.

    Returns:
        Le DataFrame chargé.
    """
    return _json_from_bytes(Path(file_path).read_bytes())


def _load_jsonl(file_path: str) -> pd.DataFrame:
    """Charge un JSON Lines depuis un chemin.

    Args:
        file_path: Chemin du fichier.

    Returns:
        Le DataFrame chargé.
    """
    return _jsonl_from_bytes(Path(file_path).read_bytes())


def _load_parquet(file_path: str) -> pd.DataFrame:
    """Charge un fichier Parquet depuis un chemin.

    Args:
        file_path: Chemin du fichier.

    Returns:
        Le DataFrame chargé.
    """
    return _parquet_from_bytes(Path(file_path).read_bytes())


def _load_json_manual(file_path: str) -> pd.DataFrame:
    """Interprète un JSON à la main depuis un chemin.

    Args:
        file_path: Chemin du fichier.

    Returns:
        Le DataFrame reconstitué.
    """
    return _parse_json_text(Path(file_path).read_text(encoding='utf-8'))


def _detect_encoding(file_path: str) -> str:
    """Détecte l'encodage d'un fichier depuis son chemin.

    Args:
        file_path: Chemin du fichier.

    Returns:
        Le nom de l'encodage retenu.
    """
    return _detect_encoding_bytes(Path(file_path).read_bytes())


def _detect_and_load_format(file_path: str) -> pd.DataFrame:
    """Détecte le format d'un fichier depuis son chemin, puis le charge.

    Args:
        file_path: Chemin du fichier.

    Returns:
        Le DataFrame chargé.

    Raises:
        ValueError: Si le format demeure indéterminé.
    """
    return _sniff_from_bytes(Path(file_path).read_bytes(),
                             os.path.splitext(file_path)[1])
