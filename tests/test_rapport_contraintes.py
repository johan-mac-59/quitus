"""Tests de la section « Contraintes » du rapport de nettoyage."""

from types import SimpleNamespace

import pandas as pd
import pytest

import main
from src.cleaner_reporter import CleanerReporter
from src.validator import nouvelle_regle, sauver_regles, valider


@pytest.fixture
def reporteur():
    """Un rapporteur minimal, sans profil ni journal réels."""
    profil = SimpleNamespace(profile_results={})
    journal = SimpleNamespace(info=lambda *a, **k: None, error=lambda *a, **k: None)
    return CleanerReporter(profil, journal)


def _bilans():
    regles = [nouvelle_regle("plage", "age", {"min": 0, "max": 120}),
              nouvelle_regle("non_vide", "nom")]
    avant = valider(pd.DataFrame({"age": [10, -1, 200, 5], "nom": ["a", None, "c", "d"]}), regles)
    apres = valider(pd.DataFrame({"age": [10, -1, 5], "nom": ["a", "c", "d"]}), regles)
    return {"avant": avant, "apres": apres}


class TestSectionContraintes:
    def test_sans_contraintes_le_rapport_est_inchange(self, reporteur):
        stats = {"duplicates_removed": 2}
        assert reporteur.render(stats) == reporteur.render(stats, None)
        assert reporteur.render(stats) == reporteur.render(stats, {})
        assert "Contraintes" not in reporteur.render(stats)

    def test_section_presente_avec_avant_et_apres(self, reporteur):
        rapport = reporteur.render({}, _bilans())
        assert "## 3. Contraintes" in rapport
        assert "jamais corrigées" in rapport
        assert "| age : valeur entre 0 et 120 | ⚠️ 2 (50 %) | ⚠️ 1 (33.33 %) |" in rapport

    def test_regle_corrigee_par_le_nettoyage_montre_respectee_apres(self, reporteur):
        rapport = reporteur.render({}, _bilans())
        assert "| nom : valeur obligatoire | ⚠️ 1 (25 %) | ✅ respectée |" in rapport

    def test_detail_porte_sur_l_etat_final(self, reporteur):
        rapport = reporteur.render({}, _bilans())
        assert "### Détail (après nettoyage)" in rapport
        assert "Exemples : -1" in rapport
        # La règle respectée après nettoyage n'a pas de détail.
        assert "**nom : valeur obligatoire**" not in rapport

    def test_avant_seul(self, reporteur):
        rapport = reporteur.render({}, {"avant": _bilans()["avant"]})
        assert "### Détail (avant nettoyage)" in rapport
        assert "| — |" in rapport

    def test_barre_verticale_dans_une_regle_ne_casse_pas_le_tableau(self, reporteur):
        regles = [nouvelle_regle("format", "ref", {"motif": "A|B"})]
        bilan = valider(pd.DataFrame({"ref": ["A", "C"]}), regles)
        rapport = reporteur.render({}, {"apres": bilan})
        assert "A\\|B" in rapport

    def test_regle_en_erreur_expliquee(self, reporteur):
        bilan = valider(pd.DataFrame({"a": [1]}), [nouvelle_regle("plage", "absente", {"min": 0})])
        rapport = reporteur.render({}, {"apres": bilan})
        assert "❌ non évaluable" in rapport
        assert "colonne absente du fichier" in rapport


def test_rapport_ecrit_par_main_contient_la_section(tmp_path):
    csv = tmp_path / "personnes.csv"
    csv.write_text("nom,age\nAna,25\nBob,-4\nCléo,130\nDan,40\nÉli,33\n", encoding="utf-8")
    regles = tmp_path / "regles.json"
    sauver_regles([nouvelle_regle("plage", "age", {"min": 0, "max": 120})], regles)
    code = main.main(["--input", str(csv), "--output", str(tmp_path / "sortie.csv"),
                      "--reports", str(tmp_path / "rapports"), "--non-interactif",
                      "--regles", str(regles)])
    assert code == 0
    rapports = list((tmp_path / "rapports").glob("cleaning_report_*.md"))
    assert len(rapports) == 1
    contenu = rapports[0].read_text(encoding="utf-8")
    assert "## 3. Contraintes" in contenu
    assert "⚠️ 2 (40 %)" in contenu


def test_main_sans_regles_ne_cree_pas_la_section(tmp_path):
    csv = tmp_path / "p.csv"
    csv.write_text("nom,age\nAna,25\nBob,30\n", encoding="utf-8")
    main.main(["--input", str(csv), "--output", str(tmp_path / "s.csv"),
               "--reports", str(tmp_path / "r"), "--non-interactif"])
    contenu = next((tmp_path / "r").glob("cleaning_report_*.md")).read_text(encoding="utf-8")
    assert "Contraintes" not in contenu


def test_un_libelle_piege_ne_devient_ni_lien_ni_image_dans_le_rapport(reporteur):
    regle = nouvelle_regle("non_vide", "nom", {},
                           libelle="[Cliquez ici](http://x.invalid) ![](http://x.invalid/p.png)")
    bilan = valider(pd.DataFrame({"nom": ["a", None]}), [regle])
    rapport = reporteur.render({}, {"avant": bilan, "apres": bilan})
    assert "[Cliquez ici](" not in rapport and "![](" not in rapport
    assert "\\[Cliquez ici\\]" in rapport
