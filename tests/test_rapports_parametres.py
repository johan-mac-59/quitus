"""Tests du paramétrage des rapports (profilage et nettoyage).

Vérifient que les trois couches — rendu en mémoire, écriture disque, choix du
format — sont utilisables indépendamment, et qu'aucune ne réclame de terminal.
"""

import logging
import tempfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from src.cleaner_reporter import (
    CleanerReporter,
    build_cleaning_report_path,
    generate_enhanced_report,
)
from src.data_profiler import (
    DataProfiler,
    ExploratoryProfiler,
    build_report_path,
)


@pytest.fixture
def df_test():
    """DataFrame réaliste, avec numérique, catégoriel et valeurs manquantes."""
    rng = np.random.default_rng(seed=7)
    return pd.DataFrame({
        "prix": rng.normal(100, 15, 60),
        "quantite": rng.integers(1, 20, 60),
        "ville": rng.choice(["Lille", "Paris", "Lyon"], 60),
        "note": [np.nan if i % 7 == 0 else i % 5 + 1 for i in range(60)],
    })


@pytest.fixture
def profileur(df_test):
    """Profileur déjà analysé."""
    p = DataProfiler(df_test, "source.csv")
    p.run_analysis()
    return p


class TestRenderReport:
    """render_report produit le rapport en mémoire, sans toucher au disque."""

    def test_markdown(self, profileur):
        """Le rendu Markdown contient les sections attendues."""
        contenu = profileur.render_report("md")
        assert isinstance(contenu, str)
        assert len(contenu) > 100

    def test_html(self, profileur):
        """Le rendu HTML est un document complet et bien formé."""
        contenu = profileur.render_report("html")
        assert contenu.strip().startswith("<!DOCTYPE html>") or "<!DOCTYPE html>" in contenu
        assert contenu.count("</body>") == 1
        assert contenu.rstrip().endswith("</body></html>")

    def test_html_exploratoire_bien_forme(self, df_test):
        """Le rapport exploratoire reste valide malgré ses ajouts.

        Ancien bug : la sous-classe ajoutait son contenu après </body></html>
        et refermait les balises une seconde fois.
        """
        p = ExploratoryProfiler(df_test, "source.csv")
        contenu = p.render_report("html")
        assert contenu.count("</body>") == 1
        assert contenu.count("</html>") == 1
        assert contenu.index("Visualisations Exploratoires") < contenu.index("</body>")

    def test_lance_l_analyse_si_besoin(self, df_test):
        """Le rendu déclenche l'analyse si elle n'a pas eu lieu."""
        p = DataProfiler(df_test, "source.csv")
        assert p.profile_results == {}
        p.render_report("md")
        assert "shape" in p.profile_results

    def test_format_inconnu_leve(self, profileur):
        """Un format non reconnu est refusé explicitement."""
        with pytest.raises(ValueError, match="Format de rapport inconnu"):
            profileur.render_report("pdf")

    def test_n_ecrit_rien_sur_le_disque(self, profileur):
        """Le rendu en mémoire ne crée aucun fichier."""
        with tempfile.TemporaryDirectory() as tmp:
            avant = set(Path(tmp).glob("**/*"))
            profileur.render_report("md")
            profileur.render_report("html")
            assert set(Path(tmp).glob("**/*")) == avant


class TestWriteReport:
    def test_ecrit_le_markdown(self, profileur):
        """Le fichier est créé et son chemin retourné."""
        with tempfile.TemporaryDirectory() as tmp:
            cible = Path(tmp) / "rapport.md"
            resultat = profileur.write_report(str(cible), fmt="md")
            assert cible.exists()
            assert Path(resultat) == cible

    def test_cree_les_repertoires_manquants(self, profileur):
        """Une arborescence absente est créée à la volée."""
        with tempfile.TemporaryDirectory() as tmp:
            cible = Path(tmp) / "a" / "b" / "c" / "rapport.md"
            profileur.write_report(str(cible))
            assert cible.exists()

    def test_encodage_utf8(self, profileur):
        """Le contenu est relisible en UTF-8."""
        with tempfile.TemporaryDirectory() as tmp:
            cible = Path(tmp) / "rapport.md"
            profileur.write_report(str(cible))
            cible.read_text(encoding="utf-8")


class TestBuildReportPath:
    def test_compose_un_nom_horodate(self):
        """Le nom reprend celui de la source et porte un horodatage."""
        chemin = build_report_path(Path("/tmp/rapports"), Path("data/ventes.csv"), "md")
        assert chemin.name.startswith("profiling_ventes_")
        assert chemin.suffix == ".md"

    def test_accepte_des_chaines(self):
        """Des chemins fournis en chaîne sont acceptés."""
        chemin = build_report_path("rapports", "ventes.xlsx", "html")
        assert chemin.name.startswith("profiling_ventes_")
        assert chemin.suffix == ".html"


class TestInteractiveReportChoice:
    """Le choix du format doit être imposable, sans aucune invite."""

    @pytest.mark.parametrize("choix,extension", [
        ("1", ".md"), ("md", ".md"), ("markdown", ".md"),
        ("2", ".html"), ("html", ".html"),
    ])
    def test_formats_acceptes(self, profileur, choix, extension):
        """Les alias numériques et textuels donnent le bon format."""
        with tempfile.TemporaryDirectory() as tmp:
            resultat = profileur.interactive_report_choice(
                Path(tmp), Path("source.csv"), choice=choix)
            assert Path(resultat).suffix == extension
            assert Path(resultat).exists()

    def test_choix_invalide_retombe_sur_markdown(self, profileur):
        """Un choix incompris produit un Markdown, comme documenté."""
        with tempfile.TemporaryDirectory() as tmp:
            resultat = profileur.interactive_report_choice(
                Path(tmp), Path("source.csv"), choice="n_importe_quoi")
            assert Path(resultat).suffix == ".md"

    def test_sur_stdin_ferme(self, profileur, monkeypatch):
        """Sans terminal, le format par défaut est retenu sans lever."""
        def _leve_eof(*args, **kwargs):
            raise EOFError

        monkeypatch.setattr("builtins.input", _leve_eof)
        with tempfile.TemporaryDirectory() as tmp:
            resultat = profileur.interactive_report_choice(Path(tmp), Path("s.csv"))
            assert Path(resultat).suffix == ".md"


class TestRunProfilingWorkflow:
    def test_mode_web_sans_ecriture(self, df_test):
        """generate_report=False n'écrit aucun fichier : c'est le mode web."""
        p = DataProfiler(df_test, "source.csv")
        with tempfile.TemporaryDirectory() as tmp:
            resultats = p.run_profiling_workflow(
                Path("source.csv"), Path(tmp),
                generate_report=False, raise_on_error=True)
            assert "shape" in resultats
            assert list(Path(tmp).glob("*")) == []

    def test_mode_cli_avec_format_impose(self, df_test):
        """Un format imposé évite toute invite et écrit le rapport."""
        p = DataProfiler(df_test, "source.csv")
        with tempfile.TemporaryDirectory() as tmp:
            p.run_profiling_workflow(Path("source.csv"), Path(tmp),
                                     report_format="html")
            assert len(list(Path(tmp).glob("*.html"))) == 1

    def test_erreurs_avalees_par_defaut(self):
        """Par défaut, une erreur rend un dictionnaire vide sans tout casser."""
        p = DataProfiler(pd.DataFrame(), "vide.csv")
        with tempfile.TemporaryDirectory() as tmp:
            assert p.run_profiling_workflow(Path("vide.csv"), Path(tmp)) == {}

    def test_erreurs_remontees_si_demande(self):
        """raise_on_error=True fait remonter l'erreur, pour l'afficher dans l'UI."""
        p = DataProfiler(pd.DataFrame(), "vide.csv")
        with tempfile.TemporaryDirectory() as tmp:
            with pytest.raises(ValueError):
                p.run_profiling_workflow(Path("vide.csv"), Path(tmp),
                                         raise_on_error=True)


class TestCleanerReporterParametre:
    @pytest.fixture
    def stats(self):
        """Statistiques de nettoyage représentatives."""
        return {
            "empty_cols_dropped": 1,
            "whitespace_cleaned": 42,
            "case_normalized": {"ville": 3},
            "duplicates_removed": 7,
            "types_converted": {"montant": ["object -> float"]},
            "missing_filled": {"note": {"count": 5, "method": "fill_median_3.0"}},
            "outliers_corrected": {"montant": 2},
        }

    @pytest.fixture
    def reporter(self, profileur):
        """Reporter branché sur un profileur réel."""
        return CleanerReporter(profileur, logging.getLogger("test"),
                               source_file_path="source.csv")

    def test_render_en_memoire(self, reporter, stats):
        """Le rendu produit le Markdown sans écrire sur le disque."""
        contenu = reporter.render(stats)
        assert "Rapport de Nettoyage des Données" in contenu
        assert "Détail des Opérations" in contenu

    def test_render_accepte_la_sentinelle_ignored(self, reporter):
        """La sentinelle ignored est rendue sans faire échouer le rapport."""
        contenu = reporter.render({"outliers_corrected": {"ignored": True},
                                   "missing_filled": {"ignored": True}})
        assert isinstance(contenu, str)

    def test_demander_avec_reponse_imposee(self, reporter):
        """Une réponse transmise court-circuite l'invite."""
        assert reporter.demander_generation_rapport(answer=True) is True
        assert reporter.demander_generation_rapport(answer=False) is False

    def test_demander_sur_stdin_ferme(self, reporter, monkeypatch):
        """Sans terminal, le défaut documenté (générer) est retenu."""
        def _leve_eof(*args, **kwargs):
            raise EOFError

        monkeypatch.setattr("builtins.input", _leve_eof)
        assert reporter.demander_generation_rapport() is True

    def test_fonctionne_avec_un_profileur_factice(self, stats):
        """Un simple objet porteur de profile_results suffit.

        C'est ce qui permet à l'interface web de ne pas conserver un profileur
        complet en session, alors qu'un seul attribut est lu.
        """
        factice = SimpleNamespace(profile_results={
            "shape": {"nb_lignes": 100, "nb_colonnes": 5},
            "nb_doublons": 3,
            "missing_values": {"count": {"a": 2}},
        })
        contenu = CleanerReporter(factice, logging.getLogger("test")).render(stats)
        assert "100" in contenu


class TestGenerateEnhancedReport:
    def test_retourne_le_chemin(self, profileur):
        """La fonction retourne enfin le chemin du rapport écrit."""
        with tempfile.TemporaryDirectory() as tmp:
            chemin = generate_enhanced_report(
                profileur, logging.getLogger("test"), Path(tmp),
                Path("source.csv"), {"duplicates_removed": 2}, generate=True)
            assert chemin is not None
            assert Path(chemin).exists()

    def test_retourne_none_si_refuse(self, profileur):
        """Un refus explicite n'écrit rien et retourne None."""
        with tempfile.TemporaryDirectory() as tmp:
            chemin = generate_enhanced_report(
                profileur, logging.getLogger("test"), Path(tmp),
                Path("source.csv"), {}, generate=False)
            assert chemin is None
            assert list(Path(tmp).glob("*")) == []

    def test_chemin_horodate(self):
        """Le nom du rapport reprend celui de la source."""
        chemin = build_cleaning_report_path(Path("/tmp"), Path("data/ventes.csv"))
        assert chemin.name.startswith("cleaning_report_ventes_")
        assert chemin.suffix == ".md"
