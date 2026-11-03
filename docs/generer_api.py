"""Génère la documentation API du projet, `docs/API.md`, depuis les docstrings.

Le document n'est jamais écrit à la main : il serait périmé au premier
changement de signature. Il est produit à partir du code lui-même — signatures
et docstrings des fonctions et classes publiques de `src/` — et un test vérifie
qu'il reste identique à ce que ce script produirait.

Usage :
    python docs/generer_api.py
"""

from __future__ import annotations

import annotationlib
import importlib
import inspect
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CHEMIN_API = RACINE / "docs" / "API.md"

# Modules documentés, dans l'ordre du parcours d'un fichier : chargement,
# profilage, nettoyage, rapports, puis les utilitaires.
MODULES = (
    "file_loader",
    "data_profiler",
    "cleaner_engine",
    "cleaner_logger",
    "cleaner_reporter",
    "plot_factory",
    "validator",
    "saisie_regles",
    "horodatage",
    "marque",
    "console_capture",
)

# Sections reconnues dans une docstring au format Google, et leur titre.
SECTIONS = {
    "Args": "Paramètres",
    "Attributes": "Attributs",
    "Returns": "Retour",
    "Yields": "Produit",
    "Raises": "Exceptions",
}

_ENTREE = re.compile(r"^(\*{0,2}[\w.]+)(?: \(([^)]*)\))?:\s*(.*)$")

EN_TETE = """# 📚 Documentation API

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
"""


def elements_publics(module) -> list:
    """Liste les fonctions et classes publiques d'un module, dans l'ordre du code.

    Args:
        module: Module importé.

    Returns:
        Les couples (nom, objet), triés par position dans le fichier source.
    """
    elements = []
    for nom, objet in vars(module).items():
        if nom.startswith("_"):
            continue
        # `lru_cache` et consorts enveloppent la fonction : on documente l'originale.
        cible = inspect.unwrap(objet) if callable(objet) else objet
        if not (inspect.isfunction(cible) or inspect.isclass(cible)):
            continue
        if cible.__module__ != module.__name__:
            continue
        elements.append((nom, cible))
    return sorted(elements, key=lambda e: inspect.getsourcelines(e[1])[1])


def methodes_publiques(classe) -> list:
    """Liste les méthodes publiques définies par une classe elle-même.

    Args:
        classe: Classe à parcourir.

    Returns:
        Les couples (nom, fonction), dans l'ordre du code.
    """
    methodes = [(nom, f) for nom, f in vars(classe).items()
                if not nom.startswith("_") and inspect.isfunction(f)]
    return sorted(methodes, key=lambda m: inspect.getsourcelines(m[1])[1])


def signature(objet) -> str:
    """Écrit la signature d'une fonction, annotations telles qu'écrites dans le code.

    Args:
        objet: Fonction ou classe.

    Returns:
        La signature, entre parenthèses.
    """
    try:
        sig = inspect.signature(objet, annotation_format=annotationlib.Format.STRING)
    except (TypeError, ValueError):
        return "(…)"

    # `str(sig)` entourerait chaque annotation d'apostrophes (« 'pd.DataFrame' »),
    # les annotations lues comme texte étant des chaînes : on la réécrit.
    morceaux, etoile_ecrite = [], False
    for param in sig.parameters.values():
        # `self` et `cls` vont de soi dans la documentation d'une méthode.
        if param.name in ("self", "cls"):
            continue
        if param.kind is param.KEYWORD_ONLY and not etoile_ecrite:
            morceaux.append("*")
            etoile_ecrite = True
        nom = {param.VAR_POSITIONAL: "*", param.VAR_KEYWORD: "**"}.get(param.kind, "") + param.name
        if param.kind is param.VAR_POSITIONAL:
            etoile_ecrite = True
        if param.annotation is not param.empty:
            nom += f": {param.annotation}"
        if param.default is not param.empty:
            nom += f" = {param.default!r}" if param.annotation is not param.empty else f"={param.default!r}"
        morceaux.append(nom)
    sans_retour = sig.return_annotation is sig.empty or inspect.isclass(objet)
    retour = "" if sans_retour else f" -> {sig.return_annotation}"
    return f"({', '.join(morceaux)}){retour}"


def rendre_docstring(doc: str) -> str:
    """Convertit une docstring au format Google en Markdown.

    Le texte libre est repris tel quel ; les sections `Args`, `Returns`,
    `Raises`… deviennent des listes titrées.

    Args:
        doc: Docstring nettoyée de son indentation (`inspect.getdoc`).

    Returns:
        Le fragment Markdown.
    """
    blocs, section, entrees, texte = [], None, [], []

    def clore():
        """Ferme la section en cours et l'ajoute aux blocs rendus."""
        if section is None:
            return
        titre = SECTIONS[section]
        if section in ("Returns", "Yields"):
            blocs.append(f"**{titre}** — " + " ".join(l.strip() for l in entrees).strip())
        else:
            lignes = [f"**{titre}**", ""]
            for nom, type_, desc in _entrees_nommees(entrees):
                suffixe = f" *({type_})*" if type_ else ""
                lignes.append(f"- `{nom}`{suffixe} — {desc}")
            blocs.append("\n".join(lignes))

    for ligne in doc.splitlines():
        titre = ligne.strip().rstrip(":")
        if ligne.strip().endswith(":") and titre in SECTIONS and not ligne.startswith(" "):
            if texte:
                blocs.append("\n".join(texte).strip())
                texte = []
            clore()
            section, entrees = titre, []
            continue
        if section is not None and (ligne.startswith(" ") or not ligne.strip()):
            entrees.append(ligne)
            continue
        if section is not None:
            clore()
            section, entrees = None, []
        texte.append(ligne.strip())

    if texte:
        blocs.append("\n".join(texte).strip())
    clore()
    return "\n\n".join(b for b in blocs if b)


def _entrees_nommees(lignes: list) -> list:
    """Regroupe les lignes d'une section en entrées (nom, type, description).

    Args:
        lignes: Lignes indentées de la section.

    Returns:
        Les triplets (nom, type ou chaîne vide, description sur une ligne).
    """
    entrees = []
    for ligne in lignes:
        if not ligne.strip():
            continue
        retrait = len(ligne) - len(ligne.lstrip())
        correspondance = _ENTREE.match(ligne.strip())
        if correspondance and retrait <= 4:
            nom, type_, desc = correspondance.groups()
            entrees.append([nom, type_ or "", desc.strip()])
        elif entrees:
            entrees[-1][2] = (entrees[-1][2] + " " + ligne.strip()).strip()
    return [tuple(e) for e in entrees]


def ancre(texte: str) -> str:
    """Calcule l'ancre GitHub d'un titre Markdown.

    Args:
        texte: Texte du titre.

    Returns:
        L'ancre, sans le croisillon.
    """
    texte = texte.lower().replace("`", "")
    texte = re.sub(r"[^\w\- ]", "", texte)
    return texte.replace(" ", "-")


def generer() -> str:
    """Produit le contenu complet de `docs/API.md`.

    Returns:
        Le document Markdown.
    """
    if str(RACINE) not in sys.path:
        sys.path.insert(0, str(RACINE))

    sommaire, corps = ["## Sommaire", ""], []
    for nom_module in MODULES:
        module = importlib.import_module(f"src.{nom_module}")
        titre_module = f"`src/{nom_module}.py`"
        sommaire.append(f"- [{titre_module}](#{ancre(titre_module)})")

        corps.append(f"## {titre_module}")
        corps.append(rendre_docstring(inspect.getdoc(module) or ""))

        for nom, objet in elements_publics(module):
            genre = "classe" if inspect.isclass(objet) else "fonction"
            titre = f"`{nom}`"
            sommaire.append(f"  - [{titre}](#{ancre(titre)}) — {genre}")
            corps.append(f"### {titre}")
            corps.append(f"```python\n{'class ' if genre == 'classe' else ''}{nom}{signature(objet)}\n```")
            corps.append(rendre_docstring(inspect.getdoc(objet) or ""))

            if inspect.isclass(objet):
                for nom_methode, methode in methodes_publiques(objet):
                    corps.append(f"#### `{nom}.{nom_methode}`")
                    corps.append(f"```python\n{nom_methode}{signature(methode)}\n```")
                    corps.append(rendre_docstring(inspect.getdoc(methode) or ""))

    morceaux = [EN_TETE.strip(), "\n".join(sommaire)] + [c for c in corps if c]
    return "\n\n".join(morceaux) + "\n"


if __name__ == "__main__":
    CHEMIN_API.write_text(generer(), encoding="utf-8", newline="\n")
    print(f"✅ {CHEMIN_API.relative_to(RACINE)} généré.")
