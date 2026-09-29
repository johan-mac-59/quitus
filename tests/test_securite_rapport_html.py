"""Le rapport HTML ne doit jamais exécuter le contenu d'un fichier analysé.

Le rapport reproduit des noms de colonnes, des modalités, des valeurs d'aperçu
et des messages d'anomalie, tous issus d'un fichier fourni par l'utilisateur.
Aucune de ces valeurs n'était échappée, et l'aperçu désactivait même
explicitement l'échappement de pandas. Une cellule contenant du balisage était
donc interprétée comme du code à l'ouverture du rapport.

Le risque devenait sérieux avec l'aperçu intégré à l'interface web : `st.iframe`
exécute le HTML fourni avec un accès same-origin à l'application.

Deux protections superposées sont vérifiées ici :

1. l'échappement de toute donnée du fichier ;
2. une politique de sécurité (CSP) qui interdit l'exécution de scripts dans le
   rapport, même si un échappement venait à manquer.
"""

from html.parser import HTMLParser

import pandas as pd
import pytest

from src import plot_factory as pf
from src.data_profiler import ExploratoryProfiler, PreCleaningProfiler


class _Inventaire(HTMLParser):
    """Recense les balises et attributs tels qu'un navigateur les interpréterait.

    Chercher une chaîne dans le rapport ne suffit pas : `"x" onclick="y"` est
    inoffensif en texte entre deux balises, et dangereux dans un attribut. Seule
    l'analyse du document distingue les deux.
    """

    def __init__(self):
        super().__init__()
        self.balises = set()
        self.attributs = set()

    def handle_starttag(self, tag, attrs):
        """Note chaque balise ouverte et chacun de ses attributs.

        Args:
            tag: Nom de la balise.
            attrs: Liste des couples (nom, valeur) de ses attributs.
        """
        self.balises.add(tag.lower())
        self.attributs.update(nom.lower() for nom, _ in attrs)


def _inventorier(document: str) -> _Inventaire:
    """Analyse un document HTML.

    Args:
        document: Le HTML à analyser.

    Returns:
        L'inventaire des balises et attributs interprétés.
    """
    inventaire = _Inventaire()
    inventaire.feed(document)
    return inventaire

CHARGES = [
    "<script>alert('xss')</script>",
    "<img src=x onerror=alert(1)>",
    '"><svg onload=alert(1)>',
    "</td></tr></table><script>alert(2)</script>",
]


@pytest.fixture
def df_malveillant():
    """DataFrame dont les noms de colonnes ET les valeurs portent des charges."""
    n = 20
    return pd.DataFrame({
        # Nom de colonne malveillant, repris en titre, en tableau et en attribut alt.
        '<img src=x onerror=alert("col")>': [CHARGES[i % len(CHARGES)] for i in range(n)],
        # Colonne catégorielle : ses modalités figurent dans le top 10.
        "ville": [CHARGES[i % 2] if i % 3 == 0 else "Lille" for i in range(n)],
        # Colonne numérique au nom piégé : reprise dans le texte alternatif des figures.
        '"prix" onmouseover="alert(3)': [float(i) for i in range(n)],
    })


@pytest.mark.parametrize("classe", [PreCleaningProfiler, ExploratoryProfiler],
                         ids=["avant", "apres"])
class TestRapportHtml:
    def test_aucune_balise_active_injectee(self, classe, df_malveillant):
        """Aucune charge ne doit produire de balise réellement interprétée."""
        rapport = classe(df_malveillant, "source.csv").render_report("html")
        inventaire = _inventorier(rapport)
        assert "script" not in inventaire.balises
        assert "svg" not in inventaire.balises
        # Les seules images sont nos graphiques, jamais un <img src=x> injecté.
        assert "<img src=x" not in rapport.lower()

    def test_aucun_gestionnaire_d_evenement(self, classe, df_malveillant):
        """Aucun attribut on* (onerror, onmouseover…) ne doit exister dans le document.

        C'est la vérification qui compte : le texte d'une charge peut figurer,
        neutralisé, entre deux balises ; il ne doit jamais devenir un attribut.
        """
        rapport = classe(df_malveillant, "source.csv").render_report("html")
        evenements = {a for a in _inventorier(rapport).attributs if a.startswith("on")}
        assert evenements == set()

    def test_les_donnees_restent_lisibles(self, classe, df_malveillant):
        """Échapper n'est pas supprimer : le texte reste affiché, neutralisé."""
        rapport = classe(df_malveillant, "source.csv").render_report("html")
        assert "&lt;script&gt;" in rapport

    def test_politique_de_securite_presente(self, classe, df_malveillant):
        """La CSP interdit tout script, en seconde ligne de défense."""
        rapport = classe(df_malveillant, "source.csv").render_report("html")
        assert "Content-Security-Policy" in rapport
        assert "default-src 'none'" in rapport
        # Aucune directive n'autorise les scripts.
        assert "script-src" not in rapport

    def test_les_images_restent_autorisees(self, classe, df_malveillant):
        """La CSP laisse passer les graphiques, embarqués en base64."""
        rapport = classe(df_malveillant, "source.csv").render_report("html")
        assert "img-src data:" in rapport
        assert 'src="data:image/png;base64,' in rapport


class TestFabriqueDeGraphiques:
    def test_texte_alternatif_echappe(self):
        """Le texte alternatif d'une figure ne peut pas sortir de son attribut."""
        fig = pf.new_figure((2, 2))
        fig.subplots()
        balise = pf.figure_to_img_tag(fig, alt='x" onerror="alert(1)')
        assert 'onerror="alert(1)"' not in balise
        assert "&quot;" in balise
