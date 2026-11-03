"""Vérification de contraintes saisies par l'utilisateur.

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
"""

from __future__ import annotations

import hashlib
import json
import operator
import re
from pathlib import Path
from typing import Callable

import pandas as pd

TYPES_REGLES = (
    "plage",
    "longueur",
    "format",
    "valeurs_autorisees",
    "non_vide",
    "unique",
    "comparaison_colonnes",
)

# Opérateurs de `comparaison_colonnes`, avec le texte qui les décrit.
OPERATEURS = {
    "<": (operator.lt, "strictement inférieur à"),
    "<=": (operator.le, "inférieur ou égal à"),
    "==": (operator.eq, "égal à"),
    ">=": (operator.ge, "supérieur ou égal à"),
    ">": (operator.gt, "strictement supérieur à"),
    "!=": (operator.ne, "différent de"),
}

# Expressions des formats nommés, appliquées à la valeur entière une fois les
# séparateurs usuels (espaces, points, tirets) retirés quand ils n'ont pas de sens.
_MOTIFS_FORMATS = {
    "email": (r"[^@\s]+@[^@\s]+\.[^@\s.]{2,}", False),
    "code_postal": (r"\d{5}", False),
    "telephone_fr": (r"(?:(?:\+|00)33|0)[1-9]\d{8}", True),
    "siren": (r"\d{9}", True),
    "siret": (r"\d{14}", True),
}
# Formats dont la validité comprend en plus une somme de contrôle de Luhn.
_FORMATS_LUHN = {"siren", "siret"}
FORMATS_NOMMES = tuple(_MOTIFS_FORMATS)

LIBELLES_FORMATS = {
    "email": "adresse e-mail",
    "code_postal": "code postal français",
    "telephone_fr": "numéro de téléphone français",
    "siren": "numéro SIREN",
    "siret": "numéro SIRET",
}

MAX_LIGNES = 100
MAX_EXEMPLES = 5
_VERSION_FORMAT_FICHIER = 1


# ---------------------------------------------------------------------------
# Construction, description et enregistrement des règles
# ---------------------------------------------------------------------------

def nouvelle_regle(type_regle: str, colonnes: list[str] | str,
                   parametres: dict | None = None,
                   libelle: str | None = None) -> dict:
    """Construit une règle avec un identifiant stable.

    L'identifiant est déduit du type, des colonnes et des paramètres : la même
    règle porte toujours le même identifiant, et deux règles différentes ne
    risquent pas de se confondre.

    Args:
        type_regle: Un des `TYPES_REGLES`.
        colonnes: Nom de colonne, ou liste de noms.
        parametres: Paramètres propres au type de règle.
        libelle: Nom lisible facultatif, repris dans les rapports.

    Returns:
        La règle, prête pour `valider` ou `sauver_regles`. Sa validité n'est
        pas contrôlée ici : voir `verifier_regle`.
    """
    liste = [colonnes] if isinstance(colonnes, str) else list(colonnes)
    parametres = dict(parametres or {})
    empreinte = hashlib.sha1(
        json.dumps([type_regle, liste, parametres], sort_keys=True,
                   ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()[:6]
    regle = {
        "id": f"{type_regle}-{'+'.join(liste)}-{empreinte}",
        "type": type_regle,
        "colonnes": liste,
        "parametres": parametres,
    }
    if libelle:
        regle["libelle"] = libelle
    return regle


def verifier_regle(regle: object) -> list[str]:
    """Contrôle la forme d'une règle, sans regarder les données.

    Args:
        regle: La règle à contrôler.

    Returns:
        La liste des problèmes, en français. Vide si la règle est bien formée.
    """
    if not isinstance(regle, dict):
        return ["la règle doit être un dictionnaire"]
    problemes = []
    type_regle = regle.get("type")
    if type_regle not in TYPES_REGLES:
        return [f"type de règle inconnu : {type_regle!r} "
                f"(attendu : {', '.join(TYPES_REGLES)})"]
    colonnes = regle.get("colonnes")
    if (not isinstance(colonnes, list) or not colonnes
            or not all(isinstance(c, str) and c for c in colonnes)):
        return ["« colonnes » doit être une liste non vide de noms de colonnes"]
    parametres = regle.get("parametres", {})
    if not isinstance(parametres, dict):
        return ["« parametres » doit être un dictionnaire"]

    if type_regle != "unique" and type_regle != "comparaison_colonnes" and len(colonnes) != 1:
        problemes.append(f"la règle « {type_regle} » porte sur une seule colonne")

    if type_regle in ("plage", "longueur"):
        if parametres.get("min") is None and parametres.get("max") is None:
            problemes.append("indiquez au moins un minimum ou un maximum")
        elif type_regle == "longueur":
            for borne in ("min", "max"):
                valeur = parametres.get(borne)
                if valeur is not None and (
                        isinstance(valeur, bool) or not isinstance(valeur, int) or valeur < 0):
                    problemes.append(f"« {borne} » doit être un entier positif ou nul")
        else:
            problemes.extend(_verifier_bornes_plage(parametres))
        mini, maxi = parametres.get("min"), parametres.get("max")
        if not problemes and type_regle == "longueur" and None not in (mini, maxi) and mini > maxi:
            problemes.append("le minimum dépasse le maximum")
    elif type_regle == "format":
        nom, motif = parametres.get("nom"), parametres.get("motif")
        if (nom is None) == (motif is None):
            problemes.append("indiquez soit « nom » (format nommé), soit « motif » (expression régulière)")
        elif nom is not None and nom not in _MOTIFS_FORMATS:
            problemes.append(f"format nommé inconnu : {nom!r} (attendu : {', '.join(FORMATS_NOMMES)})")
        elif motif is not None:
            try:
                re.compile(str(motif))
            except re.error as erreur:
                problemes.append(f"expression régulière invalide : {erreur}")
    elif type_regle == "valeurs_autorisees":
        valeurs = parametres.get("valeurs")
        if not isinstance(valeurs, list) or not valeurs:
            problemes.append("« valeurs » doit être une liste non vide")
    elif type_regle == "comparaison_colonnes":
        if len(colonnes) != 2:
            problemes.append("la comparaison porte sur exactement deux colonnes")
        if parametres.get("operateur") not in OPERATEURS:
            problemes.append(f"opérateur inconnu : {parametres.get('operateur')!r} "
                             f"(attendu : {', '.join(OPERATEURS)})")
    return problemes


def _verifier_bornes_plage(parametres: dict) -> list[str]:
    """Contrôle les bornes d'une règle `plage` (nombres ou dates).

    Args:
        parametres: Paramètres de la règle.

    Returns:
        La liste des problèmes constatés.
    """
    bornes = {b: parametres.get(b) for b in ("min", "max") if parametres.get(b) is not None}
    if _bornes_numeriques(bornes) is not None:
        valeurs = list(_bornes_numeriques(bornes).values())
    else:
        dates = {b: _lire_date(v) for b, v in bornes.items()}
        invalides = [b for b, d in dates.items() if pd.isna(d)]
        if invalides:
            return [f"borne « {b} » illisible : {bornes[b]!r} (nombre ou date attendus)"
                    for b in invalides]
        valeurs = list(dates.values())
    if len(valeurs) == 2 and valeurs[0] > valeurs[1]:
        return ["le minimum dépasse le maximum"]
    return []


def _bornes_numeriques(bornes: dict) -> dict | None:
    """Lit les bornes comme des nombres, si elles le sont toutes.

    Args:
        bornes: Bornes non nulles, par nom (`min`, `max`).

    Returns:
        Les bornes converties en nombres, ou None si l'une n'en est pas un.
    """
    convertis = {}
    for nom, valeur in bornes.items():
        if isinstance(valeur, bool):
            return None
        try:
            convertis[nom] = float(str(valeur).replace(",", ".").strip())
        except ValueError:
            return None
    return convertis


def decrire_regle(regle: dict) -> str:
    """Décrit une règle en une phrase française.

    Args:
        regle: Une règle bien formée.

    Returns:
        Le libellé de la règle s'il existe, sinon une description déduite de
        son type et de ses paramètres.
    """
    if regle.get("libelle"):
        return str(regle["libelle"])
    colonnes = regle.get("colonnes", [])
    colonne = colonnes[0] if colonnes else "?"
    parametres = regle.get("parametres", {}) or {}
    type_regle = regle.get("type")
    mini, maxi = parametres.get("min"), parametres.get("max")

    def _bornes(unite: str = "") -> str:
        if mini is not None and maxi is not None:
            return f"entre {mini} et {maxi}{unite}"
        if mini is not None:
            return f"au moins {mini}{unite}"
        return f"au plus {maxi}{unite}"

    if type_regle == "plage":
        return f"{colonne} : valeur {_bornes()}"
    if type_regle == "longueur":
        return f"{colonne} : longueur {_bornes(' caractères')}"
    if type_regle == "format":
        if parametres.get("nom") in LIBELLES_FORMATS:
            return f"{colonne} : {LIBELLES_FORMATS[parametres['nom']]} valide"
        return f"{colonne} : respecte le motif {parametres.get('motif')}"
    if type_regle == "valeurs_autorisees":
        valeurs = parametres.get("valeurs") or []
        apercu = ", ".join(str(v) for v in valeurs[:5]) + (" …" if len(valeurs) > 5 else "")
        return f"{colonne} : l'une des valeurs {apercu}"
    if type_regle == "non_vide":
        return f"{colonne} : valeur obligatoire"
    if type_regle == "unique":
        return f"{' + '.join(colonnes)} : valeurs toutes différentes"
    if type_regle == "comparaison_colonnes" and len(colonnes) == 2:
        texte = OPERATEURS.get(parametres.get("operateur"), (None, "?"))[1]
        return f"{colonnes[0]} {texte} {colonnes[1]}"
    return f"règle {regle.get('id', '?')}"


def regles_vers_texte(regles: list[dict]) -> str:
    """Met des règles en forme de texte JSON, sans rien écrire sur le disque.

    C'est ce que consomme l'interface web pour proposer l'export des règles au
    téléchargement : le fichier n'existe jamais sur le serveur.

    Args:
        regles: Règles à exporter.

    Returns:
        Le texte JSON, relisible par `regles_depuis_texte` et `charger_regles`.
    """
    contenu = {"version": _VERSION_FORMAT_FICHIER, "regles": list(regles)}
    return json.dumps(contenu, ensure_ascii=False, indent=2)


def sauver_regles(regles: list[dict], chemin: str | Path) -> Path:
    """Enregistre des règles dans un fichier JSON, pour les rejouer plus tard.

    Args:
        regles: Règles à enregistrer.
        chemin: Fichier de destination ; ses dossiers parents sont créés.

    Returns:
        Le chemin du fichier écrit.
    """
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(regles_vers_texte(regles), encoding="utf-8")
    return chemin


def regles_depuis_texte(texte: str) -> list[dict]:
    """Lit des règles depuis un texte JSON (contenu d'un fichier de règles).

    Accepte le format écrit par `sauver_regles` ou une simple liste de règles.

    Args:
        texte: Contenu JSON.

    Returns:
        Les règles lues.

    Raises:
        ValueError: Si le texte n'est pas du JSON valide, ou si une règle est
            mal formée. Le message dit laquelle et pourquoi.
    """
    try:
        brut = json.loads(texte)
    except json.JSONDecodeError as erreur:
        raise ValueError(f"fichier de règles illisible (JSON invalide) : {erreur}") from erreur
    regles = brut.get("regles") if isinstance(brut, dict) else brut
    if not isinstance(regles, list):
        raise ValueError("fichier de règles invalide : une liste de règles est attendue")
    for position, regle in enumerate(regles, start=1):
        problemes = verifier_regle(regle)
        if problemes:
            raise ValueError(f"règle n° {position} invalide : {' ; '.join(problemes)}")
    return regles


def charger_regles(chemin: str | Path) -> list[dict]:
    """Lit un fichier de règles JSON.

    Args:
        chemin: Fichier écrit par `sauver_regles` (ou liste JSON de règles).

    Returns:
        Les règles lues.

    Raises:
        FileNotFoundError: Si le fichier n'existe pas.
        ValueError: Si le contenu n'est pas valide (voir `regles_depuis_texte`).
    """
    chemin = Path(chemin)
    if not chemin.exists():
        raise FileNotFoundError(f"fichier de règles introuvable : {chemin}")
    return regles_depuis_texte(chemin.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Lecture tolérante des valeurs
# ---------------------------------------------------------------------------

def _non_vides(serie: pd.Series) -> pd.Series:
    """Repère les cellules renseignées (ni manquantes, ni blanches).

    Args:
        serie: Colonne à examiner.

    Returns:
        Un masque booléen, vrai là où la cellule contient quelque chose.
    """
    return serie.notna() & (serie.astype(str).str.strip() != "")


def _en_texte(serie: pd.Series) -> pd.Series:
    """Convertit une colonne en texte, sans le « .0 » des entiers lus en flottants.

    Args:
        serie: Colonne à convertir.

    Returns:
        La colonne en texte, sans espaces aux extrémités.
    """
    if pd.api.types.is_float_dtype(serie):
        entiers = serie.notna() & (serie == serie.round())
        texte = serie.astype(str)
        texte[entiers] = serie[entiers].astype("int64").astype(str)
        return texte.str.strip()
    return serie.astype(str).str.strip()


def _vers_nombres(serie: pd.Series) -> pd.Series:
    """Lit une colonne comme des nombres, de façon tolérante.

    Accepte l'espace des milliers, la virgule décimale, les symboles monétaires
    et le signe pour cent. Ce qui n'est pas lisible devient manquant.

    Args:
        serie: Colonne à lire.

    Returns:
        Une colonne de flottants, NaN là où la lecture a échoué.
    """
    if pd.api.types.is_numeric_dtype(serie) and not pd.api.types.is_bool_dtype(serie):
        return pd.to_numeric(serie, errors="coerce")
    texte = (serie.astype(str)
             .str.replace(r"[\s  €$£%]", "", regex=True)
             .str.replace(",", ".", regex=False))
    return pd.to_numeric(texte, errors="coerce")


def _vers_dates(serie: pd.Series) -> pd.Series:
    """Lit une colonne comme des dates, de façon tolérante (jour d'abord).

    Args:
        serie: Colonne à lire.

    Returns:
        Une colonne de dates, NaT là où la lecture a échoué.
    """
    if pd.api.types.is_datetime64_any_dtype(serie):
        return serie
    texte = serie.astype(str).str.strip()
    # Les dates ISO (2024-01-05) se lisent sans l'option « jour d'abord », qui
    # les inverserait : 2024-01-05 deviendrait le 1er mai.
    dates = pd.to_datetime(texte, format="ISO8601", errors="coerce")
    restantes = dates.isna() & serie.notna()
    if restantes.any():
        dates[restantes] = pd.to_datetime(texte[restantes], dayfirst=True,
                                          format="mixed", errors="coerce")
    return dates


def _lire_date(valeur: object) -> pd.Timestamp:
    """Lit une borne de date saisie par l'utilisateur.

    Args:
        valeur: Date écrite en ISO (2024-01-05) ou jour d'abord (05/01/2024).

    Returns:
        La date, ou NaT si elle est illisible.
    """
    return _vers_dates(pd.Series([str(valeur)])).iloc[0]


def _luhn_valide(chiffres: str) -> bool:
    """Vérifie la somme de contrôle de Luhn d'une suite de chiffres.

    Args:
        chiffres: Texte composé uniquement de chiffres.

    Returns:
        Vrai si la somme de contrôle est correcte.
    """
    total = 0
    for rang, chiffre in enumerate(reversed(chiffres)):
        n = int(chiffre)
        if rang % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


# ---------------------------------------------------------------------------
# Évaluation
# ---------------------------------------------------------------------------

def valider(df: pd.DataFrame, regles: list[dict]) -> dict:
    """Vérifie un DataFrame contre une liste de règles, sans le modifier.

    Une règle mal formée, ou qui vise une colonne absente, ne lève pas
    d'exception : elle est rapportée en erreur et les autres sont évaluées.

    Args:
        df: Données à vérifier. Jamais modifiées.
        regles: Règles à appliquer (voir `nouvelle_regle`).

    Returns:
        Un dictionnaire ``{"resultats": [...], "total_violations": n,
        "regles_en_erreur": n, "regles_respectees": n}``. Chaque résultat
        contient : ``id``, ``type``, ``colonnes``, ``description``, ``statut``
        (``"respectee"``, ``"violations"`` ou ``"erreur"``), ``evaluees``,
        ``violations``, ``pourcentage``, ``non_evaluables``, ``lignes``
        (étiquettes d'index des lignes fautives, `MAX_LIGNES` au plus),
        ``exemples`` (`MAX_EXEMPLES` valeurs au plus) et ``message``.
    """
    resultats = [_evaluer_regle(df, regle) for regle in regles]
    return {
        "resultats": resultats,
        "total_violations": sum(r["violations"] for r in resultats),
        "regles_en_erreur": sum(1 for r in resultats if r["statut"] == "erreur"),
        "regles_respectees": sum(1 for r in resultats if r["statut"] == "respectee"),
    }


def _resultat_vide(regle: object) -> dict:
    """Prépare la structure d'un résultat, avant évaluation.

    Args:
        regle: La règle évaluée (éventuellement mal formée).

    Returns:
        Un résultat sans violation, à compléter.
    """
    bien_formee = isinstance(regle, dict)
    return {
        "id": regle.get("id", "?") if bien_formee else "?",
        "type": regle.get("type") if bien_formee else None,
        "colonnes": regle.get("colonnes", []) if bien_formee else [],
        "description": "",
        "statut": "respectee",
        "evaluees": 0,
        "violations": 0,
        "pourcentage": 0.0,
        "non_evaluables": 0,
        "lignes": [],
        "exemples": [],
        "message": "",
    }


def _evaluer_regle(df: pd.DataFrame, regle: object) -> dict:
    """Évalue une règle et construit son résultat.

    Args:
        df: Données à vérifier.
        regle: La règle à appliquer.

    Returns:
        Le résultat de la règle (voir `valider`).
    """
    resultat = _resultat_vide(regle)
    problemes = verifier_regle(regle)
    if problemes:
        resultat.update(statut="erreur", message="règle invalide : " + " ; ".join(problemes))
        return resultat
    resultat["description"] = decrire_regle(regle)
    absentes = [c for c in regle["colonnes"] if c not in df.columns]
    if absentes:
        resultat.update(statut="erreur",
                        message="colonne absente du fichier : " + ", ".join(absentes))
        return resultat

    evaluateur = _EVALUATEURS[regle["type"]]
    try:
        evaluees, fautives, non_evaluables = evaluateur(df, regle["colonnes"],
                                                        regle.get("parametres", {}) or {})
    except Exception as erreur:  # une règle ne doit jamais faire échouer les autres
        resultat.update(statut="erreur", message=f"évaluation impossible : {erreur}")
        return resultat

    nb_evaluees = int(evaluees.sum())
    nb_violations = int((fautives & evaluees).sum())
    colonnes = regle["colonnes"]
    en_faute = df.loc[fautives & evaluees]
    exemples = (en_faute[colonnes[0]] if len(colonnes) == 1
                else en_faute[colonnes].astype(str).agg(" | ".join, axis=1))
    resultat.update(
        evaluees=nb_evaluees,
        violations=nb_violations,
        pourcentage=round(100 * nb_violations / nb_evaluees, 2) if nb_evaluees else 0.0,
        non_evaluables=int(non_evaluables.sum()),
        lignes=[_natif(i) for i in en_faute.index[:MAX_LIGNES]],
        exemples=[_natif(v) for v in exemples.head(MAX_EXEMPLES).tolist()],
        statut="violations" if nb_violations else "respectee",
    )
    resultat["message"] = _message(resultat)
    return resultat


def _natif(valeur: object) -> object:
    """Ramène une valeur numpy ou pandas à un type Python simple.

    Args:
        valeur: Valeur lue dans un DataFrame.

    Returns:
        La valeur, utilisable telle quelle en JSON ou en affichage.
    """
    if hasattr(valeur, "item"):
        try:
            valeur = valeur.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(valeur, float) and valeur.is_integer():
        return int(valeur)  # 2.0 s'affiche 2 : une colonne d'entiers lue en flottants
    return str(valeur) if isinstance(valeur, pd.Timestamp) else valeur


def _message(resultat: dict) -> str:
    """Rédige la phrase qui résume le résultat d'une règle.

    Args:
        resultat: Résultat évalué, avec ses compteurs.

    Returns:
        Une phrase en français.
    """
    if resultat["violations"]:
        phrase = (f"{resultat['violations']} valeur(s) hors règle "
                  f"sur {resultat['evaluees']} ({resultat['pourcentage']:g} %)")
    else:
        phrase = f"respectée ({resultat['evaluees']} valeur(s) vérifiée(s))"
    if resultat["non_evaluables"]:
        phrase += f" ; {resultat['non_evaluables']} valeur(s) illisible(s), non vérifiée(s)"
    return phrase


def _eval_plage(df: pd.DataFrame, colonnes: list[str], p: dict):
    """Évalue une règle `plage`.

    Args:
        df: Données à vérifier.
        colonnes: Colonne visée (une seule).
        p: Paramètres (`min`, `max`).

    Returns:
        Le triplet de masques (évaluées, fautives, non évaluables).
    """
    serie = df[colonnes[0]]
    renseignee = _non_vides(serie)
    bornes = {b: p[b] for b in ("min", "max") if p.get(b) is not None}
    numeriques = _bornes_numeriques(bornes)
    if numeriques is not None:
        valeurs, bornes_lues = _vers_nombres(serie), numeriques
    else:
        valeurs = _vers_dates(serie)
        bornes_lues = {b: _lire_date(v) for b, v in bornes.items()}
    lisible = valeurs.notna()
    fautive = pd.Series(False, index=df.index)
    if "min" in bornes_lues:
        fautive |= valeurs < bornes_lues["min"]
    if "max" in bornes_lues:
        fautive |= valeurs > bornes_lues["max"]
    return renseignee & lisible, fautive, renseignee & ~lisible


def _eval_longueur(df: pd.DataFrame, colonnes: list[str], p: dict):
    """Évalue une règle `longueur`.

    Args:
        df: Données à vérifier.
        colonnes: Colonne visée (une seule).
        p: Paramètres (`min`, `max`), en nombre de caractères.

    Returns:
        Le triplet de masques (évaluées, fautives, non évaluables).
    """
    serie = df[colonnes[0]]
    renseignee = _non_vides(serie)
    longueurs = _en_texte(serie).str.len()
    fautive = pd.Series(False, index=df.index)
    if p.get("min") is not None:
        fautive |= longueurs < p["min"]
    if p.get("max") is not None:
        fautive |= longueurs > p["max"]
    return renseignee, fautive, pd.Series(False, index=df.index)


def _eval_format(df: pd.DataFrame, colonnes: list[str], p: dict):
    """Évalue une règle `format`.

    Args:
        df: Données à vérifier.
        colonnes: Colonne visée (une seule).
        p: Paramètres (`nom` ou `motif`).

    Returns:
        Le triplet de masques (évaluées, fautives, non évaluables).
    """
    serie = df[colonnes[0]]
    renseignee = _non_vides(serie)
    texte = _en_texte(serie)
    if p.get("nom") is not None:
        motif, sans_separateurs = _MOTIFS_FORMATS[p["nom"]]
        if sans_separateurs:
            texte = texte.str.replace(r"[\s.\-  ]", "", regex=True)
        conforme = texte.str.fullmatch(motif).fillna(False).astype(bool)
        if p["nom"] in _FORMATS_LUHN:
            conforme &= texte.map(
                lambda t: isinstance(t, str) and t.isdigit() and _luhn_valide(t)
            ).astype(bool)
    else:
        conforme = texte.str.fullmatch(str(p["motif"])).fillna(False).astype(bool)
    return renseignee, ~conforme, pd.Series(False, index=df.index)


def _eval_valeurs_autorisees(df: pd.DataFrame, colonnes: list[str], p: dict):
    """Évalue une règle `valeurs_autorisees`.

    Args:
        df: Données à vérifier.
        colonnes: Colonne visée (une seule).
        p: Paramètres (`valeurs`).

    Returns:
        Le triplet de masques (évaluées, fautives, non évaluables).
    """
    serie = df[colonnes[0]]
    renseignee = _non_vides(serie)
    admises = {str(v).strip() for v in p["valeurs"]}
    fautive = ~_en_texte(serie).isin(admises)
    return renseignee, fautive, pd.Series(False, index=df.index)


def _eval_non_vide(df: pd.DataFrame, colonnes: list[str], p: dict):
    """Évalue une règle `non_vide`.

    Args:
        df: Données à vérifier.
        colonnes: Colonne visée (une seule).
        p: Paramètres (aucun).

    Returns:
        Le triplet de masques (évaluées, fautives, non évaluables).
    """
    toutes = pd.Series(True, index=df.index)
    return toutes, ~_non_vides(df[colonnes[0]]), pd.Series(False, index=df.index)


def _eval_unique(df: pd.DataFrame, colonnes: list[str], p: dict):
    """Évalue une règle `unique`, sur une colonne ou une combinaison de colonnes.

    Toutes les lignes d'un groupe répété sont signalées, pas seulement les
    suivantes : l'outil ne sait pas laquelle est la bonne.

    Args:
        df: Données à vérifier.
        colonnes: Colonne(s) dont la valeur ou la combinaison doit être unique.
        p: Paramètres (aucun).

    Returns:
        Le triplet de masques (évaluées, fautives, non évaluables).
    """
    renseignee = pd.Series(True, index=df.index)
    for colonne in colonnes:
        renseignee &= _non_vides(df[colonne])
    clef = pd.DataFrame({c: _en_texte(df[c]) for c in colonnes})
    fautive = clef.duplicated(keep=False) & renseignee
    return renseignee, fautive, pd.Series(False, index=df.index)


def _eval_comparaison(df: pd.DataFrame, colonnes: list[str], p: dict):
    """Évalue une règle `comparaison_colonnes`.

    Les deux colonnes sont lues comme des nombres si elles s'y prêtent, sinon
    comme des dates.

    Args:
        df: Données à vérifier.
        colonnes: Les deux colonnes comparées, dans l'ordre.
        p: Paramètres (`operateur`).

    Returns:
        Le triplet de masques (évaluées, fautives, non évaluables).
    """
    gauche, droite = df[colonnes[0]], df[colonnes[1]]
    renseignee = _non_vides(gauche) & _non_vides(droite)
    nombres_g, nombres_d = _vers_nombres(gauche), _vers_nombres(droite)
    taux = lambda lues, brut: (lues.notna() & _non_vides(brut)).sum() / max(_non_vides(brut).sum(), 1)
    if min(taux(nombres_g, gauche), taux(nombres_d, droite)) >= 0.8:
        a, b = nombres_g, nombres_d
    else:
        a, b = _vers_dates(gauche), _vers_dates(droite)
    lisible = a.notna() & b.notna()
    comparer: Callable = OPERATEURS[p["operateur"]][0]
    fautive = ~comparer(a, b)
    return renseignee & lisible, fautive, renseignee & ~lisible


_EVALUATEURS = {
    "plage": _eval_plage,
    "longueur": _eval_longueur,
    "format": _eval_format,
    "valeurs_autorisees": _eval_valeurs_autorisees,
    "non_vide": _eval_non_vide,
    "unique": _eval_unique,
    "comparaison_colonnes": _eval_comparaison,
}


def resumer_resultat(resultat: dict | None) -> str:
    """Résume en quelques mots le résultat d'une règle, pour une cellule de tableau.

    Args:
        resultat: Résultat d'une règle, tel que le renvoie `valider`, ou None
            si la règle n'a pas été évaluée à ce moment-là.

    Returns:
        Un texte court : « ✅ respectée », « ⚠️ 2 (40 %) », « ❌ non évaluable »,
        suivi du nombre de valeurs illisibles s'il y en a ; « — » si la règle
        n'a pas été évaluée.
    """
    if resultat is None:
        return "—"
    if resultat["statut"] == "erreur":
        return "❌ non évaluable"
    if resultat["statut"] == "respectee":
        texte = "✅ respectée"
    else:
        texte = f"⚠️ {resultat['violations']} ({resultat['pourcentage']:g} %)"
    if resultat["non_evaluables"]:
        texte += f", {resultat['non_evaluables']} illisible(s)"
    return texte


def formater_bilan(validation: dict, titre: str = "Contraintes") -> str:
    """Met en forme le résultat de `valider` pour la console ou un rapport texte.

    Args:
        validation: Résultat de `valider`.
        titre: Intitulé du bilan.

    Returns:
        Un texte multiligne. Vide si aucune règle n'a été évaluée.
    """
    resultats = validation["resultats"]
    if not resultats:
        return ""
    icones = {"respectee": "✅", "violations": "⚠️", "erreur": "❌"}
    lignes = [f"🔎 {titre} : {validation['regles_respectees']} règle(s) respectée(s) sur "
              f"{len(resultats)}, {validation['total_violations']} violation(s)"]
    for r in resultats:
        nom = r["description"] or r["id"]
        lignes.append(f"   {icones[r['statut']]} {nom} : {r['message']}")
        if r["statut"] == "violations":
            if r["type"] == "non_vide":
                # Une cellule vide n'a pas de valeur à citer : on donne les lignes.
                reperes = ", ".join(str(i) for i in r["lignes"][:MAX_EXEMPLES])
                lignes.append(f"      lignes (index) : {reperes}")
            else:
                lignes.append(f"      exemples : {', '.join(str(e) for e in r['exemples'])}")
    return "\n".join(lignes)
