"""Description du formulaire de création de règles, partagée par les deux façades.

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
"""

from __future__ import annotations

from src.validator import (
    FORMATS_NOMMES,
    LIBELLES_FORMATS,
    OPERATEURS,
    TYPES_REGLES,
    nouvelle_regle,
    verifier_regle,
)

GENRES_DE_CHAMP = ("borne", "entier", "texte", "liste", "choix")

_AIDE_BORNE = "Un nombre (120) ou une date (05/01/2024, 2024-01-05)."


def _champ(nom: str, libelle: str, genre: str, *, obligatoire: bool = False,
           choix: list[tuple[str, str]] | None = None, aide: str = "",
           si_vide: str | None = None) -> dict:
    """Fabrique la description d'un champ de formulaire.

    Args:
        nom: Clé du paramètre dans la règle.
        libelle: Intitulé lisible.
        genre: Un des `GENRES_DE_CHAMP`.
        obligatoire: Vrai si la règle ne peut pas se passer de ce champ.
        choix: Couples (valeur, libellé), pour le genre ``choix``.
        aide: Phrase d'explication, avec un exemple.
        si_vide: Nom d'un autre champ dont ce champ n'est demandé que s'il est
            resté vide.

    Returns:
        Le dictionnaire décrivant le champ.
    """
    return {"nom": nom, "libelle": libelle, "genre": genre, "obligatoire": obligatoire,
            "choix": list(choix or []), "aide": aide, "si_vide": si_vide}


# Un type de règle : libellé lisible, nombre de colonnes attendu (mini, maxi ; maxi
# vide pour « autant qu'on veut ») et champs. L'ordre est celui où on les propose.
TYPES_DE_REGLE = {
    "plage": {
        "libelle": "Valeur minimale et/ou maximale",
        "colonnes": (1, 1),
        "champs": [
            _champ("min", "Minimum", "borne", aide=_AIDE_BORNE + " Vide : aucun minimum."),
            _champ("max", "Maximum", "borne", aide=_AIDE_BORNE + " Vide : aucun maximum."),
        ],
    },
    "longueur": {
        "libelle": "Nombre de caractères",
        "colonnes": (1, 1),
        "champs": [
            _champ("min", "Longueur minimale", "entier",
                   aide="Nombre de caractères (5 pour un code postal). Vide : aucun minimum."),
            _champ("max", "Longueur maximale", "entier",
                   aide="Nombre de caractères. Vide : aucun maximum."),
        ],
    },
    "format": {
        "libelle": "Format (e-mail, code postal, téléphone, SIRET…)",
        "colonnes": (1, 1),
        "champs": [
            _champ("nom", "Format connu", "choix",
                   choix=[(nom, LIBELLES_FORMATS[nom]) for nom in FORMATS_NOMMES],
                   aide="Choisissez un format connu, ou laissez vide pour écrire un motif."),
            _champ("motif", "Motif personnalisé", "texte",
                   aide="Expression régulière, si aucun format connu ne convient "
                        "(par exemple [A-Z]{2}-\\d{3}).", si_vide="nom"),
        ],
    },
    "valeurs_autorisees": {
        "libelle": "Liste de valeurs autorisées",
        "colonnes": (1, 1),
        "champs": [
            _champ("valeurs", "Valeurs autorisées", "liste", obligatoire=True,
                   aide="Séparées par des points-virgules : Payé ; En attente ; Annulé."),
        ],
    },
    "non_vide": {
        "libelle": "Valeur obligatoire",
        "colonnes": (1, 1),
        "champs": [],
    },
    "unique": {
        "libelle": "Valeurs toutes différentes",
        "colonnes": (1, None),
        "champs": [],
    },
    "comparaison_colonnes": {
        "libelle": "Comparaison avec une autre colonne",
        "colonnes": (2, 2),
        "champs": [
            _champ("operateur", "La première colonne doit être", "choix", obligatoire=True,
                   choix=[(symbole, texte) for symbole, (_, texte) in OPERATEURS.items()],
                   aide="Par rapport à la seconde colonne (la date de fin après la date de début)."),
        ],
    },
}


def types_disponibles() -> list[tuple[str, str]]:
    """Liste les types de règle proposés, dans l'ordre où on les présente.

    Returns:
        Des couples (type, libellé lisible), prêts pour une liste de choix.
    """
    return [(type_regle, description["libelle"])
            for type_regle, description in TYPES_DE_REGLE.items()]


def champs_du_type(type_regle: str) -> list[dict]:
    """Donne les champs à demander pour un type de règle.

    Args:
        type_regle: Un des types de `types_disponibles`.

    Returns:
        La liste des champs (vide pour une règle sans paramètre), en copie :
        l'appelant peut la modifier sans toucher à la description.

    Raises:
        KeyError: Si le type est inconnu.
    """
    return [dict(champ, choix=list(champ["choix"]))
            for champ in TYPES_DE_REGLE[type_regle]["champs"]]


def colonnes_attendues(type_regle: str) -> tuple[int, int | None]:
    """Donne le nombre de colonnes qu'un type de règle porte.

    Args:
        type_regle: Un des types de `types_disponibles`.

    Returns:
        Le couple (minimum, maximum) ; le maximum est None s'il n'y en a pas.

    Raises:
        KeyError: Si le type est inconnu.
    """
    return TYPES_DE_REGLE[type_regle]["colonnes"]


def _est_vide(saisie: object) -> bool:
    """Dit si une saisie est absente ou ne contient que des blancs.

    Args:
        saisie: Valeur saisie, ou None.

    Returns:
        Vrai si rien n'a été saisi.
    """
    return saisie is None or str(saisie).strip() == ""


def lire_borne(texte: str) -> int | float | str:
    """Lit une borne saisie : un nombre si possible, sinon le texte (une date).

    Args:
        texte: Saisie de l'utilisateur ; la virgule décimale est acceptée.

    Returns:
        Un entier (« 120 »), un flottant (« 0,5 ») ou le texte tel quel
        (« 05/01/2024 »), dont la validité de date est contrôlée plus tard.
    """
    texte = str(texte).strip()
    try:
        nombre = float(texte.replace(",", "."))
    except ValueError:
        return texte
    return int(nombre) if nombre.is_integer() else nombre


def _convertir(champ: dict, saisie: object, problemes: list[str]):
    """Convertit la saisie d'un champ selon son genre.

    Args:
        champ: Description du champ.
        saisie: Texte saisi, non vide.
        problemes: Liste où ajouter les problèmes rencontrés.

    Returns:
        La valeur convertie, ou None si la saisie est inutilisable.
    """
    genre, libelle = champ["genre"], champ["libelle"]
    texte = str(saisie).strip()
    if genre == "borne":
        return lire_borne(texte)
    if genre == "entier":
        try:
            return int(texte)
        except ValueError:
            problemes.append(f"« {libelle} » doit être un nombre entier, pas « {texte} »")
            return None
    if genre == "liste":
        valeurs = [v.strip() for v in texte.split(";") if v.strip()]
        if not valeurs:
            problemes.append(f"« {libelle} » doit contenir au moins une valeur")
            return None
        return valeurs
    if genre == "choix":
        admises = [valeur for valeur, _ in champ["choix"]]
        if texte not in admises:
            problemes.append(f"« {libelle} » : « {texte} » n'est pas un choix possible "
                             f"(attendu : {', '.join(admises)})")
            return None
        return texte
    return texte


def construire_regle(type_regle: str, colonnes: list[str] | str,
                     saisies: dict | None = None,
                     libelle: str | None = None) -> tuple[dict | None, list[str]]:
    """Construit une règle à partir de ce que l'utilisateur a saisi.

    Les champs vides sont ignorés (« aucun minimum »). Les problèmes sont
    rapportés en français plutôt que levés : l'interface les affiche et laisse
    l'utilisateur corriger.

    Args:
        type_regle: Un des types de `types_disponibles`.
        colonnes: Nom de colonne, ou liste de noms.
        saisies: Textes saisis, par nom de champ (voir `champs_du_type`).
        libelle: Nom lisible facultatif de la règle.

    Returns:
        Le couple (règle, problèmes). La règle est None si les problèmes ne
        sont pas vides ; sinon elle est valide (`verifier_regle`) et prête pour
        `valider`.
    """
    if type_regle not in TYPES_DE_REGLE:
        return None, [f"type de règle inconnu : {type_regle!r} "
                      f"(attendu : {', '.join(TYPES_REGLES)})"]
    liste = [colonnes] if isinstance(colonnes, str) else list(colonnes or [])
    liste = [c for c in liste if not _est_vide(c)]
    mini, maxi = colonnes_attendues(type_regle)
    problemes = []
    if len(liste) < mini or (maxi is not None and len(liste) > maxi):
        attendu = (f"{mini} colonne(s)" if mini == maxi else
                   f"au moins {mini} colonne(s)" if maxi is None else
                   f"entre {mini} et {maxi} colonnes")
        problemes.append(f"cette règle porte sur {attendu}, pas {len(liste)}")

    saisies = saisies or {}
    parametres = {}
    for champ in TYPES_DE_REGLE[type_regle]["champs"]:
        saisie = saisies.get(champ["nom"])
        if _est_vide(saisie):
            if champ["obligatoire"]:
                problemes.append(f"« {champ['libelle']} » est obligatoire")
            continue
        valeur = _convertir(champ, saisie, problemes)
        if valeur is not None:
            parametres[champ["nom"]] = valeur
    if problemes:
        return None, problemes

    regle = nouvelle_regle(type_regle, liste, parametres, libelle)
    problemes = verifier_regle(regle)
    return (None, problemes) if problemes else (regle, [])


def saisies_depuis_regle(regle: dict) -> dict[str, str]:
    """Retrouve les textes à saisir pour reconstruire une règle existante.

    C'est l'inverse de `construire_regle` : il sert à pré-remplir un formulaire
    quand l'utilisateur veut modifier une règle plutôt que la refaire.

    Args:
        regle: Une règle bien formée.

    Returns:
        Les textes à saisir, par nom de champ. Les champs que la règle ne porte
        pas sont absents. Reconstruire la règle avec ces textes redonne la même.
    """
    parametres = regle.get("parametres", {}) or {}
    saisies = {}
    for champ in TYPES_DE_REGLE.get(regle.get("type"), {"champs": []})["champs"]:
        valeur = parametres.get(champ["nom"])
        if valeur is None:
            continue
        if champ["genre"] == "liste":
            saisies[champ["nom"]] = " ; ".join(str(v) for v in valeur)
        else:
            saisies[champ["nom"]] = str(valeur)
    return saisies
