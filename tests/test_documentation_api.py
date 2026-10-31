"""Verrouille la documentation API : `docs/API.md` reflète toujours le code.

Le document est généré depuis les signatures et les docstrings par
`docs/generer_api.py`. Un document écrit à la main se serait périmé au premier
changement de signature ; celui-ci ne peut pas l'être sans que ce test échoue.
"""

import importlib.util
import inspect
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
CHEMIN_GENERATEUR = RACINE / "docs" / "generer_api.py"


@pytest.fixture(scope="module")
def generateur():
    """Charge le script de génération, qui n'est pas un paquet importable.

    Returns:
        Le module `generer_api`.
    """
    spec = importlib.util.spec_from_file_location("generer_api", CHEMIN_GENERATEUR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_le_document_est_a_jour(generateur):
    """Le fichier versionné est identique à ce que produit le générateur."""
    attendu = generateur.generer()
    present = generateur.CHEMIN_API.read_text(encoding="utf-8")
    assert present == attendu, (
        "docs/API.md n'est plus à jour : lancez `python docs/generer_api.py`.")


def test_chaque_element_public_est_documente(generateur):
    """Chaque fonction, classe et méthode publique a sa section."""
    document = generateur.CHEMIN_API.read_text(encoding="utf-8")
    for nom_module in generateur.MODULES:
        module = importlib.import_module(f"src.{nom_module}")
        for nom, objet in generateur.elements_publics(module):
            assert f"### `{nom}`" in document, f"{nom_module}.{nom} absent"
            if inspect.isclass(objet):
                for nom_methode, _ in generateur.methodes_publiques(objet):
                    assert f"#### `{nom}.{nom_methode}`" in document


def test_tous_les_modules_de_src_sont_couverts(generateur):
    """Un nouveau module de `src/` doit rejoindre la documentation."""
    modules = {p.stem for p in (RACINE / "src").glob("*.py") if p.stem != "__init__"}
    assert modules == set(generateur.MODULES)


def test_sections_rendues(generateur):
    """Les sections Google deviennent des listes titrées."""
    rendu = generateur.rendre_docstring(
        "Résumé.\n\nArgs:\n    df: Données.\n    seuil (float): Seuil,\n"
        "        sur deux lignes.\n\nReturns:\n    Le résultat.\n\n"
        "Raises:\n    ValueError: Si vide.")
    assert "Résumé." in rendu
    assert "- `df` — Données." in rendu
    assert "- `seuil` *(float)* — Seuil, sur deux lignes." in rendu
    assert "**Retour** — Le résultat." in rendu
    assert "- `ValueError` — Si vide." in rendu
