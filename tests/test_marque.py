"""Tests de l'identité de Quitus dans les rapports.

Chaque rapport — profilage HTML, profilage Markdown, rapport de nettoyage —
s'ouvre sur le logo de Quitus, intégré au fichier pour rester autonome. Si le
logo est introuvable, l'en-tête retombe sur le nom et la devise en texte : un
rapport ne doit jamais échouer pour une question d'habillage.
"""

import logging
from types import SimpleNamespace

import pandas as pd
import pytest

from src import marque
from src.cleaner_reporter import CleanerReporter
from src.data_profiler import DataProfiler


@pytest.fixture
def profileur():
    """Profileur analysé sur un petit jeu de données."""
    p = DataProfiler(pd.DataFrame({"prix": [1.0, 2.0, 3.0, 50.0],
                                   "ville": ["Lille", "Paris", "Lyon", "Lille"]}),
                     "source.csv")
    p.run_analysis()
    return p


@pytest.fixture
def logo_absent(monkeypatch, tmp_path):
    """Simule un logo introuvable, en vidant le cache de l'encodage."""
    monkeypatch.setattr(marque, "CHEMIN_LOGO", tmp_path / "absent.svg")
    marque.logo_data_uri.cache_clear()
    yield
    marque.logo_data_uri.cache_clear()


class TestLogo:
    def test_logo_encode_en_data_uri(self):
        """Le logo s'encode en URI data: SVG, intégrable dans un rapport."""
        uri = marque.logo_data_uri()
        assert uri and uri.startswith("data:image/svg+xml;base64,")


class TestEnTeteDesRapports:
    def test_rapport_html(self, profileur):
        """Le rapport HTML s'ouvre sur le logo, avant le titre."""
        rapport = profileur.render_report("html")
        position_logo = rapport.find("data:image/svg+xml;base64,")
        assert position_logo != -1
        assert position_logo < rapport.find("<h1>")

    def test_rapport_html_respecte_la_politique_de_securite(self, profileur):
        """Le logo passe par une URI data:, la seule source d'image autorisée."""
        rapport = profileur.render_report("html")
        assert "img-src data:" in rapport
        assert 'src="assets/' not in rapport and "http://" not in rapport.split("<body>")[1][:500]

    def test_rapport_markdown_de_profilage(self, profileur):
        """Le rapport de profilage Markdown commence par le logo."""
        assert profileur.render_report("md").lstrip().startswith("![Quitus")

    def test_rapport_de_nettoyage(self):
        """Le rapport de nettoyage commence lui aussi par le logo."""
        rapport = CleanerReporter(SimpleNamespace(profile_results={}),
                                  logging.getLogger("t")).render({})
        assert rapport.startswith("![Quitus")
        assert "Rapport de Nettoyage des Données" in rapport

    def test_texte_alternatif_porte_la_marque(self, profileur):
        """Sans affichage d'image, le lecteur voit le nom et la devise."""
        assert "Quitus — Le fichier propre, et la preuve." in profileur.render_report("md")


class TestRepliTexte:
    def test_html_sans_logo(self, logo_absent, profileur):
        """Logo introuvable : l'en-tête HTML devient textuel, sans erreur."""
        rapport = profileur.render_report("html")
        assert "<strong>Quitus</strong>" in rapport
        assert "data:image/svg+xml" not in rapport

    def test_markdown_sans_logo(self, logo_absent):
        """Logo introuvable : l'en-tête Markdown devient textuel."""
        rapport = CleanerReporter(SimpleNamespace(profile_results={}),
                                  logging.getLogger("t")).render({})
        assert rapport.startswith("**Quitus** — *Le fichier propre, et la preuve.*")
