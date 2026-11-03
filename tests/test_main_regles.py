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
