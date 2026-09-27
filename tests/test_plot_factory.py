"""Tests de la fabrique de graphiques.

Au-delà du bon fonctionnement de chaque constructeur, ces tests verrouillent la
garantie centrale du module : aucune figure ne doit se retrouver dans le registre
global de pyplot, sous peine de fuite mémoire dans un processus Streamlit de
longue durée.
"""

import base64

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure

from src import plot_factory as pf


@pytest.fixture
def df_mixte():
    """DataFrame avec colonnes numériques corrélées et colonnes catégorielles."""
    rng = np.random.default_rng(seed=42)
    n = 120
    base = rng.normal(size=n)
    return pd.DataFrame({
        "prix": base * 10 + 100,
        "quantite": base * 2 + 20,           # corrélée à prix
        "remise": rng.normal(size=n),        # indépendante
        "ville": rng.choice(["Lille", "Paris", "Lyon"], n),
        "statut": rng.choice(["ok", "annule"], n),
    })


@pytest.fixture
def df_une_seule_numerique():
    """DataFrame ne comportant qu'une colonne numérique."""
    return pd.DataFrame({"age": [25, 30, 35, 40], "nom": ["a", "b", "c", "d"]})


@pytest.fixture(autouse=True)
def registre_pyplot_vide():
    """Garantit qu'aucun test ne laisse de figure derrière lui."""
    plt.close("all")
    yield
    assert plt.get_fignums() == [], (
        "Une figure a été enregistrée dans le registre global de pyplot. "
        "plot_factory doit utiliser Figure() + FigureCanvasAgg, jamais plt.figure()."
    )
    plt.close("all")


class TestNewFigure:
    def test_renvoie_une_figure(self):
        """new_figure produit bien une Figure matplotlib."""
        fig = pf.new_figure((4, 3))
        assert isinstance(fig, Figure)

    def test_respecte_dimensions_et_dpi(self):
        """Les dimensions et la résolution demandées sont appliquées."""
        fig = pf.new_figure((6, 2), dpi=150)
        assert tuple(fig.get_size_inches()) == (6.0, 2.0)
        assert fig.dpi == 150

    def test_hors_du_registre_global(self):
        """La figure créée n'est pas enregistrée dans pyplot."""
        pf.new_figure((4, 3))
        assert plt.get_fignums() == []


class TestConstructeurs:
    def test_histogramme(self, df_mixte):
        """L'histogramme se construit et porte le titre attendu."""
        fig = pf.figure_histogram(df_mixte, "prix")
        assert isinstance(fig, Figure)
        assert "prix" in fig.axes[0].get_title()

    def test_boxplot(self, df_mixte):
        """Le boxplot se construit et porte le titre attendu."""
        fig = pf.figure_boxplot(df_mixte, "quantite")
        assert isinstance(fig, Figure)
        assert "quantite" in fig.axes[0].get_title()

    def test_barplot_respecte_top_n(self, df_mixte):
        """Le barplot n'affiche pas plus de modalités que demandé."""
        fig = pf.figure_barplot_top(df_mixte, "ville", top_n=2)
        assert isinstance(fig, Figure)
        assert len(fig.axes[0].get_yticklabels()) <= 2

    def test_matrice_dispersion_grille_carree(self, df_mixte):
        """La matrice produit une grille n×n pour n colonnes numériques."""
        fig = pf.figure_scatter_matrix(df_mixte)
        # 3 colonnes numériques dans la fixture -> 9 sous-graphiques
        assert len(fig.axes) == 9

    def test_matrice_dispersion_plafonne_les_colonnes(self, df_mixte):
        """Le plafond max_cols limite la taille de la grille."""
        fig = pf.figure_scatter_matrix(df_mixte, max_cols=2)
        assert len(fig.axes) == 4

    def test_heatmap_correlation(self, df_mixte):
        """La heatmap se construit sur les colonnes numériques."""
        fig = pf.figure_correlation_heatmap(df_mixte)
        assert isinstance(fig, Figure)

    def test_colonnes_explicites(self, df_mixte):
        """On peut imposer la liste des colonnes à représenter."""
        fig = pf.figure_correlation_heatmap(df_mixte, cols=["prix", "quantite"])
        assert isinstance(fig, Figure)


class TestCasLimites:
    def test_matrice_refuse_une_seule_colonne(self, df_une_seule_numerique):
        """Une seule colonne numérique ne permet pas de matrice de dispersion."""
        with pytest.raises(ValueError, match="au moins 2 colonnes"):
            pf.figure_scatter_matrix(df_une_seule_numerique)

    def test_heatmap_refuse_une_seule_colonne(self, df_une_seule_numerique):
        """Une seule colonne numérique ne permet pas de heatmap."""
        with pytest.raises(ValueError, match="au moins 2 colonnes"):
            pf.figure_correlation_heatmap(df_une_seule_numerique)

    def test_matrice_refuse_donnees_vides(self):
        """Sans aucune ligne complète, la matrice est impossible."""
        df = pd.DataFrame({"a": [1.0, np.nan], "b": [np.nan, 2.0]})
        with pytest.raises(ValueError, match="Aucune ligne complète"):
            pf.figure_scatter_matrix(df)

    def test_histogramme_colonne_avec_nan(self):
        """Les valeurs manquantes sont ignorées sans faire échouer le tracé."""
        df = pd.DataFrame({"a": [1.0, np.nan, 3.0, 4.0, np.nan]})
        assert isinstance(pf.figure_histogram(df, "a"), Figure)


class TestConversionHtml:
    def test_base64_est_un_png_valide(self, df_mixte):
        """L'encodage produit bien un PNG décodable."""
        encoded = pf.figure_to_base64_png(pf.figure_histogram(df_mixte, "prix"))
        raw = base64.b64decode(encoded)
        # Signature d'un fichier PNG
        assert raw.startswith(b"\x89PNG\r\n\x1a\n")

    def test_balise_img_autonome(self, df_mixte):
        """La balise produite embarque l'image et son texte alternatif."""
        tag = pf.figure_to_img_tag(
            pf.figure_boxplot(df_mixte, "prix"),
            alt="boxplot prix",
            style="width: 25%;",
        )
        assert tag.startswith('<img src="data:image/png;base64,')
        assert 'alt="boxplot prix"' in tag
        assert 'style="width: 25%;"' in tag


class TestHygieneMemoire:
    def test_aucune_fuite_apres_nombreuses_figures(self, df_mixte):
        """Construire beaucoup de figures ne remplit pas le registre pyplot."""
        for _ in range(30):
            pf.figure_histogram(df_mixte, "prix")
            pf.figure_boxplot(df_mixte, "quantite")
            pf.figure_barplot_top(df_mixte, "ville")
        assert plt.get_fignums() == []

    def test_src_n_importe_pas_pyplot(self):
        """Aucun module de src/ ne doit importer pyplot (règle de cycle de vie n°1)."""
        import re
        from pathlib import Path

        # On cible les instructions d'import réelles, pas les mentions en commentaire
        # ou en docstring (plot_factory.py explique justement pourquoi il l'évite).
        import_pyplot = re.compile(
            r"^\s*(?:import\s+matplotlib\.pyplot|from\s+matplotlib\s+import\s+pyplot)",
            re.MULTILINE,
        )

        src_dir = Path(__file__).parent.parent / "src"
        fautifs = [
            f.name for f in src_dir.glob("*.py")
            if import_pyplot.search(f.read_text(encoding="utf-8"))
        ]
        assert fautifs == [], (
            f"Ces modules importent pyplot et risquent de fuiter : {fautifs}. "
            "Passer par src/plot_factory.py."
        )
