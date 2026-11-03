"""Tests de la vérification de contraintes en ligne de commande (`main.py`).

Le terminal se borne à rejouer un fichier de règles : la création interactive
des règles vit dans l'interface web.
"""

import pytest

import main
from src.validator import nouvelle_regle, sauver_regles


@pytest.fixture
def fichier_de_test(tmp_path):
    """Un petit CSV avec deux valeurs hors plage, et un fichier de règles."""
    csv = tmp_path / "personnes.csv"
    csv.write_text("nom,age\nAna,25\nBob,-4\nCléo,130\nDan,40\nÉli,33\n", encoding="utf-8")
    regles = tmp_path / "regles.json"
    sauver_regles([nouvelle_regle("plage", "age", {"min": 0, "max": 120})], regles)
    return csv, regles, tmp_path


def _lancer(csv, tmp_path, *extra):
    return main.main(["--input", str(csv), "--output", str(tmp_path / "sortie.csv"),
                      "--reports", str(tmp_path / "rapports"), "--non-interactif", *extra])


class TestOrdre:
    """Les contraintes viennent en dernier : après nettoyage, rapport et nouveau profilage."""

    @staticmethod
    def _espions(monkeypatch):
        """Enregistre l'ordre des étapes."""
        evenements = []
        profilage = main.PreCleaningProfiler.run_profiling_workflow
        profilage_post = main.ExploratoryProfiler.run_profiling_workflow
        nettoyage = main.run_all_cleaning_steps
        rapport = main.generate_enhanced_report
        validation = main.valider

        def profilage_espion(self, *a, **k):
            evenements.append("profilage")
            return profilage(self, *a, **k)

        def profilage_post_espion(self, *a, **k):
            evenements.append("profilage_post")
            return profilage_post(self, *a, **k)

        def nettoyage_espion(df, *a, **k):
            evenements.append("nettoyage")
            return nettoyage(df, *a, **k)

        def rapport_espion(*a, **k):
            evenements.append("rapport_avec_contraintes" if k.get("contraintes") else "rapport")
            return rapport(*a, **k)

        def validation_espion(*a, **k):
            if "validation" not in evenements:
                evenements.append("validation")
            return validation(*a, **k)

        monkeypatch.setattr(main.PreCleaningProfiler, "run_profiling_workflow", profilage_espion)
        monkeypatch.setattr(main.ExploratoryProfiler, "run_profiling_workflow", profilage_post_espion)
        monkeypatch.setattr(main, "run_all_cleaning_steps", nettoyage_espion)
        monkeypatch.setattr(main, "generate_enhanced_report", rapport_espion)
        monkeypatch.setattr(main, "valider", validation_espion)
        return evenements

    def test_validation_apres_nettoyage_rapport_et_nouveau_profilage(self, fichier_de_test,
                                                                      monkeypatch):
        csv, regles, tmp = fichier_de_test
        evenements = self._espions(monkeypatch)
        assert _lancer(csv, tmp, "--regles", str(regles)) == 0
        assert evenements == ["profilage", "nettoyage", "rapport", "profilage_post",
                              "validation", "rapport_avec_contraintes"]

    def test_sans_regles_aucune_validation_et_rapport_inchange(self, fichier_de_test,
                                                                monkeypatch, capsys):
        csv, _, tmp = fichier_de_test
        evenements = self._espions(monkeypatch)
        assert _lancer(csv, tmp) == 0
        assert evenements == ["profilage", "nettoyage", "rapport", "profilage_post"]
        assert "Contraintes" not in capsys.readouterr().out

    def test_aucune_question_sur_les_contraintes(self, fichier_de_test, monkeypatch):
        """Le terminal ne dialogue plus pour les contraintes : il rejoue un fichier."""
        csv, regles, tmp = fichier_de_test
        monkeypatch.setattr("builtins.input",
                            lambda *a: pytest.fail("question posée sur les contraintes"))
        assert _lancer(csv, tmp, "--regles", str(regles)) == 0

    def test_rapport_refuse_pas_de_rapport_cree_par_les_contraintes(self, fichier_de_test,
                                                                     monkeypatch):
        csv, regles, tmp = fichier_de_test
        monkeypatch.setattr(main, "get_user_decisions", lambda *a, **k: (False, False))
        monkeypatch.setattr("builtins.input", lambda *a: "n")  # on refuse le rapport
        code = main.main(["--input", str(csv), "--output", str(tmp / "s.csv"),
                          "--reports", str(tmp / "r"), "--format-rapport", "md",
                          "--regles", str(regles)])
        assert code == 0
        assert list((tmp / "r").glob("cleaning_report_*.md")) == []


class TestBoutEnBout:
    def test_regles_signalees_avant_et_apres_sans_rien_corriger(self, fichier_de_test, capsys):
        csv, regles, tmp = fichier_de_test
        assert _lancer(csv, tmp, "--regles", str(regles)) == 0
        sortie = capsys.readouterr().out
        assert "Contraintes avant nettoyage" in sortie
        assert "Contraintes après nettoyage" in sortie
        assert "2 valeur(s) hors règle" in sortie
        # Le validateur signale : les valeurs hors règle sont toujours dans le fichier nettoyé.
        propre = (tmp / "sortie.csv").read_text(encoding="utf-8")
        assert "-4" in propre and "130" in propre

    def test_le_nettoyage_est_identique_avec_ou_sans_regles(self, fichier_de_test):
        csv, regles, tmp = fichier_de_test
        _lancer(csv, tmp)
        sans = (tmp / "sortie.csv").read_text(encoding="utf-8")
        (tmp / "sortie.csv").unlink()
        _lancer(csv, tmp, "--regles", str(regles))
        assert (tmp / "sortie.csv").read_text(encoding="utf-8") == sans

    def test_rapport_reecrit_une_seule_fois_avec_la_section(self, fichier_de_test):
        csv, regles, tmp = fichier_de_test
        _lancer(csv, tmp, "--regles", str(regles))
        rapports = list((tmp / "rapports").glob("cleaning_report_*.md"))
        assert len(rapports) == 1  # même fichier, réécrit : aucun doublon
        assert "## 3. Contraintes" in rapports[0].read_text(encoding="utf-8")

    def test_fichier_de_regles_introuvable_signale_a_la_fin(self, fichier_de_test, capsys):
        csv, _, tmp = fichier_de_test
        assert _lancer(csv, tmp, "--regles", str(tmp / "absent.json")) == 1
        sortie = capsys.readouterr().out
        assert "introuvable" in sortie
        assert (tmp / "sortie.csv").exists()  # le nettoyage est fait et sauvegardé
        assert "seules les contraintes n'ont pas pu être vérifiées" in sortie

    def test_fichier_de_regles_invalide(self, fichier_de_test, capsys):
        csv, _, tmp = fichier_de_test
        mauvais = tmp / "mauvais.json"
        mauvais.write_text('{"regles": [{"type": "zzz"}]}', encoding="utf-8")
        assert _lancer(csv, tmp, "--regles", str(mauvais)) == 1
        assert "n° 1" in capsys.readouterr().out
