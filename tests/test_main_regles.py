"""Tests de la saisie des contraintes en ligne de commande (`main.py`)."""

import json

import pytest

import main
from src.validator import charger_regles, nouvelle_regle, sauver_regles

COLONNES = ["nom", "age", "debut", "fin"]


def _reponses(*valeurs):
    """Fabrique une fonction de saisie qui rejoue des réponses dans l'ordre."""
    suite = iter(valeurs)

    def saisir(_invite=""):
        try:
            return next(suite)
        except StopIteration:
            raise EOFError
    return saisir


class TestMenu:
    def test_refuser_n_ajoute_rien(self):
        assert main.demander_regles(COLONNES, _reponses("")) == []
        assert main.demander_regles(COLONNES, _reponses("n")) == []

    def test_sans_terminal_ne_plante_pas(self):
        assert main.demander_regles(COLONNES, _reponses()) == []

    def test_plage_sur_une_colonne(self):
        regles = main.demander_regles(COLONNES, _reponses(
            "o", "2", "1", "0", "120",  # colonne « age », plage, min 0, max 120
            "n",
        ))
        assert regles == [nouvelle_regle("plage", "age", {"min": 0, "max": 120})]

    def test_plusieurs_contraintes_de_suite(self):
        regles = main.demander_regles(COLONNES, _reponses(
            "o", "1", "5",                 # colonne « nom », valeur obligatoire
            "o", "2", "2", "", "3",        # colonne « age », longueur, max 3
            "n",
        ))
        assert [r["type"] for r in regles] == ["non_vide", "longueur"]
        assert regles[1]["parametres"] == {"max": 3}

    def test_format_nomme(self):
        regles = main.demander_regles(COLONNES, _reponses("o", "1", "3", "1", "n"))
        assert regles[0]["parametres"] == {"nom": "email"}

    def test_comparaison_de_deux_colonnes(self):
        regles = main.demander_regles(COLONNES, _reponses(
            "o", "3", "7",  # colonne « debut », comparaison
            "3",            # avec la 3e des autres colonnes : « fin »
            "2",            # « inférieur ou égal à »
            "n",
        ))
        assert regles[0]["colonnes"] == ["debut", "fin"]
        assert regles[0]["parametres"]["operateur"] == "<="

    def test_valeurs_autorisees(self):
        regles = main.demander_regles(COLONNES, _reponses("o", "1", "4", "Payé ; En attente ;", "n"))
        assert regles[0]["parametres"] == {"valeurs": ["Payé", "En attente"]}

    def test_annuler_en_validant_une_reponse_vide(self):
        assert main.demander_regles(COLONNES, _reponses("o", "", "n")) == []

    def test_choix_invalide_redemande(self):
        regles = main.demander_regles(COLONNES, _reponses("o", "9", "x", "1", "5", "n"))
        assert regles[0]["type"] == "non_vide"

    def test_regle_invalide_expliquee_et_abandonnee(self, capsys):
        # plage sans aucune borne
        regles = main.demander_regles(COLONNES, _reponses("o", "2", "1", "", "", "n"))
        assert regles == []
        assert "abandonnée" in capsys.readouterr().out

    def test_interruption_conserve_les_regles_deja_definies(self):
        regles = main.demander_regles(COLONNES, _reponses("o", "1", "5", "o", "2"))
        assert len(regles) == 1


class TestEnregistrement:
    def test_enregistre_et_rejouable(self, tmp_path):
        regles = [nouvelle_regle("non_vide", "nom")]
        chemin = main._proposer_enregistrement(
            regles, tmp_path, tmp_path / "source.csv", "20260101_000000", _reponses(""))
        assert chemin == tmp_path / "regles_source_20260101_000000.json"
        assert charger_regles(chemin) == regles

    def test_refus(self, tmp_path):
        assert main._proposer_enregistrement(
            [nouvelle_regle("non_vide", "nom")], tmp_path, tmp_path / "s.csv",
            "x", _reponses("n")) is None
        assert list(tmp_path.iterdir()) == []


@pytest.fixture
def fichier_de_test(tmp_path):
    """Un petit CSV avec une valeur hors plage et un fichier de règles."""
    csv = tmp_path / "personnes.csv"
    csv.write_text("nom,age\nAna,25\nBob,-4\nCléo,130\nDan,40\nÉli,33\n", encoding="utf-8")
    regles = tmp_path / "regles.json"
    sauver_regles([nouvelle_regle("plage", "age", {"min": 0, "max": 120})], regles)
    return csv, regles, tmp_path


def _lancer(csv, tmp_path, *extra):
    return main.main(["--input", str(csv), "--output", str(tmp_path / "sortie.csv"),
                      "--reports", str(tmp_path / "rapports"), "--non-interactif", *extra])


class TestOrdre:
    """Les contraintes viennent en dernier : sur des données propres, déjà lues."""

    @staticmethod
    def _espions(monkeypatch, reponses_questions=None):
        """Enregistre l'ordre des étapes et neutralise les saisies au clavier."""
        evenements = []
        profilage = main.PreCleaningProfiler.run_profiling_workflow
        profilage_post = main.ExploratoryProfiler.run_profiling_workflow
        nettoyage = main.run_all_cleaning_steps
        rapport = main.generate_enhanced_report
        reponses = iter(reponses_questions or [])

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

        def questions_espion(colonnes, *a, **k):
            evenements.append("question")
            return next(reponses, [])

        monkeypatch.setattr(main.PreCleaningProfiler, "run_profiling_workflow", profilage_espion)
        monkeypatch.setattr(main.ExploratoryProfiler, "run_profiling_workflow", profilage_post_espion)
        monkeypatch.setattr(main, "run_all_cleaning_steps", nettoyage_espion)
        monkeypatch.setattr(main, "generate_enhanced_report", rapport_espion)
        monkeypatch.setattr(main, "demander_regles", questions_espion)
        monkeypatch.setattr(main, "get_user_decisions", lambda *a, **k: (False, False))
        monkeypatch.setattr(main, "_proposer_enregistrement", lambda *a, **k: None)
        monkeypatch.setattr("builtins.input", lambda *a: "")  # rapport : réponse par défaut
        return evenements

    @staticmethod
    def _lancer_interactif(csv, tmp, *extra):
        return main.main(["--input", str(csv), "--output", str(tmp / "s.csv"),
                          "--reports", str(tmp / "r"), "--format-rapport", "md", *extra])

    def test_question_apres_nettoyage_rapport_et_nouveau_profilage(self, fichier_de_test,
                                                                    monkeypatch):
        csv, _, tmp = fichier_de_test
        evenements = self._espions(monkeypatch)
        self._lancer_interactif(csv, tmp)
        assert evenements == ["profilage", "nettoyage", "rapport", "profilage_post", "question"]

    def test_pas_de_nettoyage_leger_ni_de_question_avant_le_nettoyage(self, fichier_de_test,
                                                                       monkeypatch):
        csv, _, tmp = fichier_de_test
        evenements = self._espions(monkeypatch)
        self._lancer_interactif(csv, tmp)
        assert evenements.count("nettoyage") == 1
        assert evenements.index("question") > evenements.index("profilage_post")

    def test_rapport_reecrit_avec_les_contraintes(self, fichier_de_test, monkeypatch):
        csv, _, tmp = fichier_de_test
        tardive = nouvelle_regle("longueur", "nom", {"max": 3})
        evenements = self._espions(monkeypatch, reponses_questions=[[tardive]])
        self._lancer_interactif(csv, tmp)
        assert evenements == ["profilage", "nettoyage", "rapport", "profilage_post",
                              "question", "rapport_avec_contraintes"]
        rapports = list((tmp / "r").glob("cleaning_report_*.md"))
        assert len(rapports) == 1  # même fichier, réécrit : aucun doublon
        contenu = rapports[0].read_text(encoding="utf-8")
        assert "## 3. Contraintes" in contenu and "nom : longueur" in contenu
        # Évaluée sur le brut comme sur le nettoyé.
        ligne = next(l for l in contenu.splitlines() if l.startswith("| nom : longueur"))
        assert "—" not in ligne

    def test_rapport_refuse_pas_de_rapport_cree_par_les_contraintes(self, fichier_de_test,
                                                                     monkeypatch):
        csv, _, tmp = fichier_de_test
        tardive = nouvelle_regle("longueur", "nom", {"max": 3})
        evenements = self._espions(monkeypatch, reponses_questions=[[tardive]])
        monkeypatch.setattr("builtins.input", lambda *a: "n")  # on refuse le rapport
        self._lancer_interactif(csv, tmp)
        assert "rapport_avec_contraintes" not in evenements
        assert list((tmp / "r").glob("cleaning_report_*.md")) == []

    def test_avec_un_fichier_de_regles_la_validation_est_en_dernier(self, fichier_de_test,
                                                                     monkeypatch):
        csv, regles, tmp = fichier_de_test
        evenements = self._espions(monkeypatch)
        assert self._lancer_interactif(csv, tmp, "--regles", str(regles)) == 0
        assert evenements == ["profilage", "nettoyage", "rapport", "profilage_post",
                              "question", "rapport_avec_contraintes"]

    def test_non_interactif_ne_pose_aucune_question(self, fichier_de_test, monkeypatch):
        csv, regles, tmp = fichier_de_test
        evenements = self._espions(monkeypatch)
        main.main(["--input", str(csv), "--output", str(tmp / "s.csv"),
                   "--reports", str(tmp / "r"), "--non-interactif", "--regles", str(regles)])
        assert "question" not in evenements

    def test_fichier_de_regles_invalide_signale_a_la_fin_sans_perdre_le_nettoyage(
            self, fichier_de_test, monkeypatch, capsys):
        csv, _, tmp = fichier_de_test
        mauvais = tmp / "mauvais.json"
        mauvais.write_text('{"regles": [{"type": "zzz"}]}', encoding="utf-8")
        self._espions(monkeypatch)
        code = self._lancer_interactif(csv, tmp, "--regles", str(mauvais))
        assert code == 1
        assert (tmp / "s.csv").exists()  # le nettoyage est fait et sauvegardé
        assert "seules les contraintes n'ont pas pu être vérifiées" in capsys.readouterr().out

    def test_les_contraintes_ne_limitent_pas_le_nettoyage(self, fichier_de_test, monkeypatch):
        """Des violations n'arrêtent ni ne modifient le nettoyage."""
        csv, regles, tmp = fichier_de_test
        self._espions(monkeypatch)
        self._lancer_interactif(csv, tmp)
        sans = (tmp / "s.csv").read_text(encoding="utf-8")
        (tmp / "s.csv").unlink()
        self._lancer_interactif(csv, tmp, "--regles", str(regles))
        assert (tmp / "s.csv").read_text(encoding="utf-8") == sans


class TestMenuParametres:
    def test_invite_personnalisee(self):
        invites = []

        def saisir(invite=""):
            invites.append(invite)
            return ""
        main.demander_regles(COLONNES, saisir, invite="Une anomalie vous a échappé ? ")
        assert invites == ["Une anomalie vous a échappé ? "]

    def test_retour_immediat_apres_chaque_regle(self):
        vues = []
        regles = main.demander_regles(
            COLONNES, _reponses("o", "1", "5", "o", "2", "5", "n"), apres_ajout=vues.append)
        assert vues == regles and len(vues) == 2

    def test_retour_immediat_affiche_le_resultat_sur_les_donnees(self, capsys):
        import pandas as pd
        df = pd.DataFrame({"age": [10, -1]})
        main._retour_immediat(df, "Aperçu")(nouvelle_regle("plage", "age", {"min": 0}))
        sortie = capsys.readouterr().out
        assert "Aperçu" in sortie and "1 valeur(s) hors règle" in sortie


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

    def test_sans_regles_rien_de_change(self, fichier_de_test, capsys):
        csv, _, tmp = fichier_de_test
        assert _lancer(csv, tmp) == 0
        assert "Contraintes" not in capsys.readouterr().out

    def test_fichier_de_regles_introuvable(self, fichier_de_test, capsys):
        csv, _, tmp = fichier_de_test
        assert _lancer(csv, tmp, "--regles", str(tmp / "absent.json")) == 1
        assert "introuvable" in capsys.readouterr().out

    def test_fichier_de_regles_invalide(self, fichier_de_test, capsys):
        csv, _, tmp = fichier_de_test
        mauvais = tmp / "mauvais.json"
        mauvais.write_text(json.dumps({"regles": [{"type": "zzz"}]}), encoding="utf-8")
        assert _lancer(csv, tmp, "--regles", str(mauvais)) == 1
        assert "n° 1" in capsys.readouterr().out
