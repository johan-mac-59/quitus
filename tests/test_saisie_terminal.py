"""Tests de la création de règles par questions en terminal (`saisie_terminal.py`)
et de son branchement dans `main.py` (`--creer-regles`).

Le dialogue ne décide de rien : les champs viennent de `src/saisie_regles.py`.
Ici, on vérifie qu'il les pose bien, et que le terminal reste facultatif.
"""

import json

import pandas as pd
import pytest

import main
import saisie_terminal
from src.validator import charger_regles, nouvelle_regle, sauver_regles

COLONNES = ["nom", "age", "debut", "fin"]
# Ordre des types : 1 plage, 2 longueur, 3 format, 4 valeurs autorisées,
# 5 valeur obligatoire, 6 valeurs uniques, 7 comparaison entre deux colonnes.


def _reponses(*valeurs):
    """Fabrique une fonction de saisie qui rejoue des réponses dans l'ordre."""
    suite = iter(valeurs)

    def saisir(_invite=""):
        try:
            return next(suite)
        except StopIteration:
            raise EOFError
    return saisir


class TestDialogue:
    def test_refuser_n_ajoute_rien(self):
        assert saisie_terminal.demander_regles(COLONNES, _reponses("")) == []
        assert saisie_terminal.demander_regles(COLONNES, _reponses("n")) == []

    def test_sans_terminal_ne_plante_pas(self):
        assert saisie_terminal.demander_regles(COLONNES, _reponses()) == []

    def test_plage_sur_une_colonne(self):
        regles = saisie_terminal.demander_regles(COLONNES, _reponses(
            "o", "1", "2", "0", "120", "n"))
        assert regles == [nouvelle_regle("plage", "age", {"min": 0, "max": 120})]

    def test_plusieurs_contraintes_de_suite(self):
        regles = saisie_terminal.demander_regles(COLONNES, _reponses(
            "o", "5", "1",               # valeur obligatoire sur « nom »
            "o", "2", "2", "", "3",      # longueur sur « age », sans minimum, maximum 3
            "n"))
        assert [r["type"] for r in regles] == ["non_vide", "longueur"]
        assert regles[1]["parametres"] == {"max": 3}

    def test_format_connu_ne_demande_pas_de_motif(self):
        regles = saisie_terminal.demander_regles(COLONNES, _reponses("o", "3", "1", "1", "n"))
        assert regles[0]["parametres"] == {"nom": "email"}

    def test_format_personnalise(self):
        regles = saisie_terminal.demander_regles(COLONNES, _reponses(
            "o", "3", "1", "", "[A-Z]{2}", "n"))
        assert regles[0]["parametres"] == {"motif": "[A-Z]{2}"}

    def test_comparaison_de_deux_colonnes(self):
        regles = saisie_terminal.demander_regles(COLONNES, _reponses(
            "o", "7", "3",   # comparaison, première colonne « debut »
            "3",             # seconde : la 3e des autres colonnes, « fin »
            "2",             # « inférieur ou égal à »
            "n"))
        assert regles[0]["colonnes"] == ["debut", "fin"]
        assert regles[0]["parametres"] == {"operateur": "<="}

    def test_valeurs_autorisees(self):
        regles = saisie_terminal.demander_regles(COLONNES, _reponses(
            "o", "4", "1", "Payé ; En attente ;", "n"))
        assert regles[0]["parametres"] == {"valeurs": ["Payé", "En attente"]}

    def test_unicite_sur_une_combinaison_de_colonnes(self):
        regles = saisie_terminal.demander_regles(COLONNES, _reponses(
            "o", "6", "1",   # valeurs uniques, première colonne « nom »
            "o", "1",        # une autre colonne : la 1re des restantes, « age »
            "n",             # pas d'autre colonne
            "n"))
        assert regles[0]["colonnes"] == ["nom", "age"]

    def test_annuler_au_choix_du_type_ou_de_la_colonne(self):
        assert saisie_terminal.demander_regles(COLONNES, _reponses("o", "", "n")) == []
        assert saisie_terminal.demander_regles(COLONNES, _reponses("o", "1", "", "n")) == []

    def test_choix_invalide_redemande(self):
        regles = saisie_terminal.demander_regles(COLONNES, _reponses(
            "o", "9", "x", "5", "1", "n"))
        assert regles[0]["type"] == "non_vide"

    def test_regle_invalide_expliquee_et_abandonnee(self, capsys):
        regles = saisie_terminal.demander_regles(COLONNES, _reponses(
            "o", "1", "2", "", "", "n"))  # plage sans aucune borne
        sortie = capsys.readouterr().out
        assert regles == []
        assert "abandonnée" in sortie and "minimum ou un maximum" in sortie

    def test_choix_obligatoire_abandonne_annule_la_regle(self):
        regles = saisie_terminal.demander_regles(COLONNES, _reponses(
            "o", "7", "3", "3", "", "n"))  # comparaison sans opérateur
        assert regles == []

    def test_interruption_conserve_les_regles_deja_definies(self):
        regles = saisie_terminal.demander_regles(COLONNES, _reponses("o", "5", "1", "o", "2"))
        assert len(regles) == 1

    def test_invite_personnalisee(self):
        invites = []

        def saisir(invite=""):
            invites.append(invite)
            return ""
        saisie_terminal.demander_regles(COLONNES, saisir, invite="Une anomalie ? ")
        assert invites == ["Une anomalie ? "]

    def test_retour_immediat_apres_chaque_regle(self):
        vues = []
        regles = saisie_terminal.demander_regles(
            COLONNES, _reponses("o", "5", "1", "o", "5", "2", "n"), apres_ajout=vues.append)
        assert vues == regles and len(vues) == 2

    def test_retour_immediat_affiche_le_resultat_sur_les_donnees(self, capsys):
        df = pd.DataFrame({"age": [10, -1]})
        saisie_terminal.retour_immediat(df, "Aperçu")(
            nouvelle_regle("plage", "age", {"min": 0}))
        sortie = capsys.readouterr().out
        assert "Aperçu" in sortie and "1 valeur(s) hors règle" in sortie


@pytest.fixture
def fichier_de_test(tmp_path):
    """Un petit CSV avec deux valeurs hors plage, et un fichier de règles."""
    csv = tmp_path / "personnes.csv"
    csv.write_text("nom,age\nAna,25\nBob,-4\nCléo,130\nDan,40\nÉli,33\n", encoding="utf-8")
    regles = tmp_path / "regles.json"
    sauver_regles([nouvelle_regle("longueur", "nom", {"max": 10})], regles)
    return csv, regles, tmp_path


def _lancer(csv, tmp, *extra):
    return main.main(["--input", str(csv), "--output", str(tmp / "s.csv"),
                      "--reports", str(tmp / "r"), "--format-rapport", "md", *extra])


class TestCreerRegles:
    """`--creer-regles` : facultatif, à la fin, et sans surcharger `main.py`."""

    def test_incompatible_avec_les_modes_sans_question(self, fichier_de_test):
        csv, _, tmp = fichier_de_test
        for mode in ("--oui-a-tout", "--non-interactif"):
            with pytest.raises(SystemExit) as sortie:
                _lancer(csv, tmp, "--creer-regles", mode)
            assert sortie.value.code == 2

    def test_sans_l_option_aucune_question_sur_les_contraintes(self, fichier_de_test,
                                                                monkeypatch):
        csv, _, tmp = fichier_de_test
        monkeypatch.setattr(main, "get_user_decisions", lambda *a, **k: (False, False))
        monkeypatch.setattr(main, "demander_regles",
                            lambda *a, **k: pytest.fail("question posée sans --creer-regles"))
        monkeypatch.setattr("builtins.input", lambda *a: "")
        assert _lancer(csv, tmp) == 0

    def test_la_question_vient_apres_le_nouveau_profilage(self, fichier_de_test, monkeypatch):
        csv, _, tmp = fichier_de_test
        evenements = []
        profilage_post = main.ExploratoryProfiler.run_profiling_workflow

        def post(self, *a, **k):
            evenements.append("profilage_post")
            return profilage_post(self, *a, **k)

        def questions(colonnes, *a, **k):
            evenements.append("question")
            return []

        monkeypatch.setattr(main.ExploratoryProfiler, "run_profiling_workflow", post)
        monkeypatch.setattr(main, "demander_regles", questions)
        monkeypatch.setattr(main, "get_user_decisions", lambda *a, **k: (False, False))
        monkeypatch.setattr("builtins.input", lambda *a: "")
        _lancer(csv, tmp, "--creer-regles")
        assert evenements == ["profilage_post", "question"]

    def test_de_bout_en_bout_regle_saisie_enregistree_et_dans_le_rapport(self, fichier_de_test,
                                                                         monkeypatch, capsys):
        csv, _, tmp = fichier_de_test
        monkeypatch.setattr(main, "get_user_decisions", lambda *a, **k: (False, False))
        # Rapport : réponse par défaut ; puis une plage sur « age », seule colonne
        # numérique donc seule proposée (choix 1), puis fin.
        reponses = iter(["", "o", "1", "1", "0", "120", "n"])
        monkeypatch.setattr("builtins.input", lambda *a: next(reponses))
        assert _lancer(csv, tmp, "--creer-regles") == 0
        sortie = capsys.readouterr().out
        assert "Contraintes avant nettoyage" in sortie and "2 valeur(s) hors règle" in sortie

        enregistrees = list((tmp / "r").glob("regles_*.json"))
        assert len(enregistrees) == 1
        assert charger_regles(enregistrees[0])[0]["parametres"] == {"min": 0, "max": 120}
        rapport = next((tmp / "r").glob("cleaning_report_*.md")).read_text(encoding="utf-8")
        assert "## 3. Contraintes" in rapport and "age : valeur entre 0 et 120" in rapport

    def test_s_ajoute_aux_regles_du_fichier(self, fichier_de_test, monkeypatch):
        csv, regles, tmp = fichier_de_test
        monkeypatch.setattr(main, "get_user_decisions", lambda *a, **k: (False, False))
        reponses = iter(["", "o", "1", "1", "0", "120", "n"])
        monkeypatch.setattr("builtins.input", lambda *a: next(reponses))
        assert _lancer(csv, tmp, "--regles", str(regles), "--creer-regles") == 0
        enregistrees = charger_regles(next((tmp / "r").glob("regles_*.json")))
        assert [r["type"] for r in enregistrees] == ["longueur", "plage"]

    def test_aucune_regle_saisie_aucun_fichier_enregistre(self, fichier_de_test, monkeypatch):
        csv, _, tmp = fichier_de_test
        monkeypatch.setattr(main, "get_user_decisions", lambda *a, **k: (False, False))
        reponses = iter(["", "n"])
        monkeypatch.setattr("builtins.input", lambda *a: next(reponses))
        assert _lancer(csv, tmp, "--creer-regles") == 0
        assert list((tmp / "r").glob("regles_*.json")) == []

    def test_fichier_de_regles_invalide_pas_de_question(self, fichier_de_test, monkeypatch):
        csv, _, tmp = fichier_de_test
        mauvais = tmp / "mauvais.json"
        mauvais.write_text(json.dumps({"regles": [{"type": "zzz"}]}), encoding="utf-8")
        monkeypatch.setattr(main, "get_user_decisions", lambda *a, **k: (False, False))
        monkeypatch.setattr(main, "demander_regles",
                            lambda *a, **k: pytest.fail("question posée malgré un fichier invalide"))
        monkeypatch.setattr("builtins.input", lambda *a: "")
        assert _lancer(csv, tmp, "--regles", str(mauvais), "--creer-regles") == 1

    def test_main_reste_leger(self):
        """Garde-fou : le dialogue vit dans `saisie_terminal.py`, pas dans `main.py`."""
        source = open(main.__file__, encoding="utf-8").read()
        assert "_choisir" not in source and "_saisir_une_regle" not in source
        assert len(source.splitlines()) < 450


class TestColonnesProposeesParType:
    """Le terminal ne propose que les colonnes qui conviennent au type de règle."""

    @pytest.fixture
    def donnees(self):
        return pd.DataFrame({"ville": ["Lille", "Nice"] * 10, "age": [20, 30] * 10,
                             "poids": [60, 70] * 10})

    def test_plage_ne_propose_pas_le_texte(self, donnees, capsys):
        reponses = iter(["1"])
        propose = saisie_terminal._choisir_colonnes(
            "plage", list(donnees.columns), lambda *a: next(reponses), donnees)
        assert propose == ["age"]
        sortie = capsys.readouterr().out
        assert "ville" not in sortie and "age" in sortie and "poids" in sortie

    def test_seconde_colonne_de_meme_nature(self, donnees, capsys):
        donnees["pays"] = ["France", "Italie"] * 10
        reponses = iter(["1", "1"])
        choisies = saisie_terminal._choisir_colonnes(
            "comparaison_colonnes", list(donnees.columns), lambda *a: next(reponses), donnees)
        assert choisies == ["age", "poids"]
        assert "pays" not in capsys.readouterr().out

    def test_aucune_colonne_compatible_annule_avec_un_message(self, capsys):
        textes = pd.DataFrame({"ville": ["Lille", "Nice"] * 10})
        choisies = saisie_terminal._choisir_colonnes(
            "plage", ["ville"], lambda *a: pytest.fail("question posée"), textes)
        assert choisies is None
        assert "Aucune colonne ne convient" in capsys.readouterr().out
