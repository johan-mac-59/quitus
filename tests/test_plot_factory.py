"""Tests de la fabrique de graphiques.

Au-delà du bon fonctionnement de chaque constructeur, ces tests verrouillent la
garantie centrale du module : aucune figure ne doit se retrouver dans le registre
global de pyplot, sous peine de fuite mémoire dans un processus Streamlit de
longue durée.
"""

import base64
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure

from src import plot_factory as pf
from src.data_profiler import DataProfiler


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


class TestColonnesIdentifiants:
    """Une colonne presque entièrement distincte n'a pas de répartition à tracer."""

    def test_colonne_d_identifiants_ecartee(self):
        df = pd.DataFrame({"id": [f"R{i}" for i in range(50)],
                           "ville": ["Lille", "Nice"] * 25})
        a_tracer, ecartees = pf.split_categorical_columns(df)
        assert a_tracer == ["ville"]
        assert ecartees == ["id"]

    def test_identifiant_avec_quelques_doublons_ecarte(self):
        valeurs = [f"R{i}" for i in range(48)] + ["R0", "R1"]
        assert pf.is_identifier_column(pd.Series(valeurs))

    def test_petite_colonne_jamais_ecartee(self):
        assert not pf.is_identifier_column(pd.Series(list("abcdefghij")))

    def test_categorie_repetee_conservee(self):
        assert not pf.is_identifier_column(pd.Series(["a", "b", "c"] * 20))


# --- Définition unique d'une colonne catégorielle ---

ECHANTILLON = Path(__file__).resolve().parent.parent / "data" / "samples" / "reservations_exemple.csv"

@pytest.fixture
def echantillon():
    return pd.read_csv(ECHANTILLON, sep=";")


class TestEchantillon:
    """La définition donne, sur l'échantillon versionné, le verdict attendu."""

    @pytest.mark.parametrize("col", ["statut", "hotel", "ville", "region", "canal",
                                     "nb_personnes", "note_satisfaction", "nb_nuits"])
    def test_colonnes_categorielles(self, echantillon, col):
        assert pf.is_categorical_column(echantillon[col])

    @pytest.mark.parametrize("col", ["id_reservation", "date_reservation", "date_arrivee",
                                     "date_depart", "montant_total"])
    def test_colonnes_non_categorielles(self, echantillon, col):
        assert not pf.is_categorical_column(echantillon[col])

    def test_statut_compte_ses_modalites_apres_normalisation(self, echantillon):
        assert pf.count_modalities(echantillon["statut"]) == 2


class TestTypes:
    def test_flottant_a_decimales_jamais_categoriel(self):
        assert not pf.is_categorical_column(pd.Series([1.5, 2.5] * 50))

    def test_flottant_a_valeurs_entieres_categoriel(self):
        assert pf.is_categorical_column(pd.Series([1.0, 2.0, np.nan, 3.0] * 50))

    def test_booleen_categoriel(self):
        assert pf.is_categorical_column(pd.Series([True, False] * 50))

    def test_annee_entiere_categorielle_et_non_date(self):
        annees = pd.Series([2023, 2024, 2025] * 40)
        assert not pf.is_date_column(annees)
        assert pf.is_categorical_column(annees)

    def test_colonne_de_type_date_exclue(self):
        dates = pd.Series(pd.to_datetime(["2025-01-01", "2025-01-02"] * 50))
        assert pf.is_date_column(dates)
        assert not pf.is_categorical_column(dates)

    def test_dates_en_texte_formats_mixtes_exclues(self):
        dates = pd.Series(["2025-01-01", "02/01/2025"] * 50)
        assert pf.is_date_column(dates)
        assert not pf.is_categorical_column(dates)

    def test_colonne_vide_non_categorielle(self):
        assert not pf.is_categorical_column(pd.Series([np.nan] * 10))

    def test_type_category_pris_en_charge(self):
        assert pf.is_categorical_column(pd.Series(["a", "b"] * 50, dtype="category"))


class TestSeuils:
    def test_plafond_de_modalites(self):
        # 25 modalités sur 1000 valeurs : 2,5 %, au plafond.
        ok = pd.Series([f"m{i}" for i in range(25)] * 40)
        trop = pd.Series([f"m{i}" for i in range(26)] * 40)
        assert pf.is_categorical_column(ok)
        assert not pf.is_categorical_column(trop)

    def test_taux_maximal_de_valeurs_distinctes(self):
        # 10 modalités sur 100 valeurs : 10 %, accepté ; 11 sur 100 : refusé.
        assert pf.is_categorical_column(pd.Series([f"m{i}" for i in range(10)] * 10))
        valeurs = [f"m{i}" for i in range(11)] * 9 + ["m0"]
        assert not pf.is_categorical_column(pd.Series(valeurs))

    def test_petit_fichier_soumis_aux_memes_regles(self):
        # Une modalité unique ne passe sous 10 % qu'à partir de 10 lignes.
        assert not pf.is_categorical_column(pd.Series(["a", "b", "a", "b"]))
        assert not pf.is_categorical_column(pd.Series(["a"] * 9))
        assert pf.is_categorical_column(pd.Series(["a"] * 10))


class TestBranchement:
    """Les graphiques reprennent la définition, y compris les entiers."""

    def test_split_reprend_la_definition(self, echantillon):
        a_tracer, ecartees = pf.split_categorical_columns(echantillon)
        assert a_tracer == pf.categorical_columns(echantillon)
        assert "statut" in a_tracer and "nb_personnes" in a_tracer
        assert ecartees == ["id_reservation", "montant_total"]

    def test_repartition_d_une_colonne_entiere_se_construit(self, echantillon):
        figure = pf.figure_barplot_top(echantillon, "note_satisfaction")
        etiquettes = [t.get_text() for t in figure.axes[0].get_yticklabels()]
        assert sorted(etiquettes) == ["1", "2", "3", "4", "5"]

    def test_plots_du_profiler_suivent_la_definition(self, echantillon):
        specs = DataProfiler(echantillon).iter_plot_specs()
        barres = {s.key.removeprefix("bar::") for s in specs if s.key.startswith("bar::")}
        assert barres == set(pf.categorical_columns(echantillon))
