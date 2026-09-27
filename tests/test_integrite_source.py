"""Contrôles structurels sur les sources du projet.

Ces tests ne valident aucun comportement métier : ils détectent les accidents
d'édition qu'une suite de tests fonctionnels laisse passer sans broncher.

Le cas qui a motivé ce fichier : lors d'un refactor, `generate_enhanced_report`
s'est retrouvée définie deux fois dans `cleaner_reporter.py`. Python retient
silencieusement la dernière définition — en l'occurrence l'ancienne version,
celle qu'on venait de remplacer. Aucun test fonctionnel n'a échoué, parce
qu'aucun ne couvrait cette fonction. Une redéfinition au niveau module est
toujours une erreur, jamais une intention.
"""

import ast
from collections import Counter
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).parent.parent / "src"
RACINE = Path(__file__).parent.parent

FICHIERS_SOURCE = sorted(SRC_DIR.glob("*.py"))
FICHIERS_RACINE = [f for f in (RACINE / "main.py", RACINE / "app.py") if f.exists()]


def _arbre(fichier: Path) -> ast.Module:
    """Analyse syntaxiquement un fichier source.

    Args:
        fichier: Chemin du fichier à analyser.

    Returns:
        L'arbre syntaxique du module.
    """
    return ast.parse(fichier.read_text(encoding="utf-8"), filename=str(fichier))


@pytest.mark.parametrize("fichier", FICHIERS_SOURCE + FICHIERS_RACINE,
                         ids=lambda f: f.name)
class TestIntegriteModule:
    def test_syntaxe_valide(self, fichier):
        """Le fichier doit être syntaxiquement correct."""
        _arbre(fichier)

    def test_pas_de_definition_dupliquee_au_niveau_module(self, fichier):
        """Aucune fonction ni classe ne doit être définie deux fois.

        Une redéfinition masque silencieusement la première version.
        """
        arbre = _arbre(fichier)
        noms = [
            n.name for n in arbre.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        doublons = [nom for nom, count in Counter(noms).items() if count > 1]
        assert doublons == [], (
            f"{fichier.name} définit plusieurs fois : {doublons}. "
            "Python ne retient que la dernière définition."
        )

    def test_pas_de_methode_dupliquee_dans_une_classe(self, fichier):
        """Aucune méthode ne doit être définie deux fois dans la même classe."""
        arbre = _arbre(fichier)
        fautifs = {}
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.ClassDef):
                continue
            noms = [
                n.name for n in noeud.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            doublons = [nom for nom, count in Counter(noms).items() if count > 1]
            if doublons:
                fautifs[noeud.name] = doublons
        assert fautifs == {}, f"{fichier.name} : méthodes dupliquées {fautifs}"

    def test_toute_fonction_publique_est_documentee(self, fichier):
        """Chaque fonction et classe publique porte une docstring."""
        arbre = _arbre(fichier)
        sans_doc = []
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if noeud.name.startswith("_"):
                continue
            if ast.get_docstring(noeud) is None:
                sans_doc.append(noeud.name)
        assert sans_doc == [], f"{fichier.name} : sans docstring {sans_doc}"


class TestArchitecture:
    """Vérifie que les frontières du modèle mixte CLI/web sont respectées."""

    def test_src_ne_depend_pas_de_streamlit(self):
        """Aucun module de src/ ne doit importer streamlit.

        `src/` doit rester agnostique de l'interface : c'est ce qui garantit que
        la ligne de commande et l'application web partagent réellement le même
        code métier, et que `src/` reste testable sans serveur.
        """
        fautifs = []
        for fichier in FICHIERS_SOURCE:
            arbre = _arbre(fichier)
            for noeud in ast.walk(arbre):
                if isinstance(noeud, ast.Import):
                    if any(a.name.split(".")[0] == "streamlit" for a in noeud.names):
                        fautifs.append(fichier.name)
                elif isinstance(noeud, ast.ImportFrom):
                    if noeud.module and noeud.module.split(".")[0] == "streamlit":
                        fautifs.append(fichier.name)
        assert fautifs == [], (
            f"Ces modules de src/ importent streamlit : {sorted(set(fautifs))}. "
            "La logique métier doit rester indépendante de l'interface."
        )

    def test_aucun_input_hors_fonction_interactive(self):
        """Tout appel à input() doit être gardé contre la fin de flux.

        Sans garde `EOFError`, un module devient impossible à importer depuis un
        contexte sans terminal : serveur web, intégration continue, ou simple
        sortie redirigée.
        """
        non_gardes = []
        for fichier in FICHIERS_SOURCE:
            texte = fichier.read_text(encoding="utf-8")
            if "input(" not in texte:
                continue
            arbre = _arbre(fichier)
            for noeud in ast.walk(arbre):
                if not (isinstance(noeud, ast.Call)
                        and isinstance(noeud.func, ast.Name)
                        and noeud.func.id == "input"):
                    continue
                # On remonte les Try englobants pour chercher une garde EOFError.
                garde = any(
                    isinstance(parent, ast.Try) and any(
                        _attrape_eof(handler) for handler in parent.handlers
                    )
                    for parent in ast.walk(arbre)
                    if isinstance(parent, ast.Try) and _contient(parent, noeud)
                )
                if not garde:
                    non_gardes.append(f"{fichier.name}:{noeud.lineno}")

        assert non_gardes == [], (
            f"Appels à input() sans garde EOFError : {non_gardes}. "
            "Envelopper dans un try/except (EOFError, KeyboardInterrupt)."
        )


def _attrape_eof(handler: ast.ExceptHandler) -> bool:
    """Indique si un gestionnaire d'exception intercepte EOFError.

    Args:
        handler: Le gestionnaire à inspecter.

    Returns:
        True si EOFError est intercepté.
    """
    if handler.type is None:
        return True
    noms = []
    if isinstance(handler.type, ast.Name):
        noms = [handler.type.id]
    elif isinstance(handler.type, ast.Tuple):
        noms = [e.id for e in handler.type.elts if isinstance(e, ast.Name)]
    return "EOFError" in noms


def _contient(parent: ast.AST, cible: ast.AST) -> bool:
    """Indique si un noeud est contenu dans le bloc `try` d'un autre.

    Args:
        parent: Le noeud englobant candidat.
        cible: Le noeud recherché.

    Returns:
        True si la cible se trouve dans le corps du try.
    """
    return any(cible is n for bloc in (parent.body,) for stmt in bloc for n in ast.walk(stmt))
