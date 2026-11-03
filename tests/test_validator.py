"""Tests du validateur de contraintes (`src/validator.py`)."""

import json

import pandas as pd
import pytest

from src.validator import (
    TYPES_REGLES,
    charger_regles,
    decrire_regle,
    formater_bilan,
    nouvelle_regle,
    regles_depuis_texte,
    sauver_regles,
    valider,
    verifier_regle,
)


def _un_resultat(df, type_regle, colonnes, parametres=None):
    """Évalue une seule règle et renvoie son résultat."""
    return valider(df, [nouvelle_regle(type_regle, colonnes, parametres)])["resultats"][0]


class TestPlage:
    def test_nombres_hors_bornes(self):
        df = pd.DataFrame({"age": [25, -3, 130, 40]})
        r = _un_resultat(df, "plage", "age", {"min": 0, "max": 120})
        assert r["violations"] == 2
        assert r["lignes"] == [1, 2]
        assert r["exemples"] == [-3, 130]

    def test_une_seule_borne(self):
        df = pd.DataFrame({"prix": [1, 5, 20]})
        assert _un_resultat(df, "plage", "prix", {"max": 10})["violations"] == 1
        assert _un_resultat(df, "plage", "prix", {"min": 2})["violations"] == 1

    def test_ecritures_francaises_lues(self):
        df = pd.DataFrame({"montant": ["1 200,50 €", "12,5", "3 000"]})
        r = _un_resultat(df, "plage", "montant", {"max": 2000})
        assert r["violations"] == 1
        assert r["non_evaluables"] == 0

    def test_valeur_illisible_declaree_non_comptee(self):
        df = pd.DataFrame({"age": ["25", "abc", "-4"]})
        r = _un_resultat(df, "plage", "age", {"min": 0})
        assert r["violations"] == 1
        assert r["non_evaluables"] == 1
        assert r["evaluees"] == 2

    def test_cellule_vide_jamais_une_violation(self):
        df = pd.DataFrame({"age": [None, "", "  ", 30]})
        r = _un_resultat(df, "plage", "age", {"min": 0, "max": 120})
        assert r["violations"] == 0
        assert r["evaluees"] == 1

    def test_dates_iso_et_francaises(self):
        df = pd.DataFrame({"naissance": ["2024-01-05", "05/01/2024", "1850-01-01"]})
        r = _un_resultat(df, "plage", "naissance", {"min": "1900-01-01", "max": "2025-01-01"})
        assert r["violations"] == 1
        assert r["lignes"] == [2]

    def test_date_iso_non_inversee(self):
        """2024-01-05 est le 5 janvier, pas le 1er mai (piège du « jour d'abord »)."""
        df = pd.DataFrame({"d": ["2024-01-05"]})
        r = _un_resultat(df, "plage", "d", {"max": "2024-02-01"})
        assert r["violations"] == 0


class TestLongueur:
    def test_longueur_exacte(self):
        df = pd.DataFrame({"cp": ["75001", "1234", "750011", None]})
        r = _un_resultat(df, "longueur", "cp", {"min": 5, "max": 5})
        assert r["violations"] == 2
        assert r["evaluees"] == 3

    def test_entiers_lus_en_flottants_sans_point_zero(self):
        df = pd.DataFrame({"cp": [75001.0, None, 1234.0]})
        r = _un_resultat(df, "longueur", "cp", {"min": 5})
        assert r["exemples"] == [1234]
        assert r["violations"] == 1


class TestFormat:
    @pytest.mark.parametrize("nom, bons, mauvais", [
        ("email", ["a@b.fr", "jean.dupont@exemple.com"], ["a@b", "sans arobase", "a@@b.fr"]),
        ("code_postal", ["75001", "01000"], ["1234", "ABCDE", "750011"]),
        ("telephone_fr", ["0612345678", "06 12 34 56 78", "+33612345678"], ["061234", "0012345678"]),
        ("siren", ["732829320", "732 829 320"], ["732829321", "12345"]),
        ("siret", ["73282932000074", "732 829 320 00074"], ["73282932000075", "x"]),
    ])
    def test_formats_nommes(self, nom, bons, mauvais):
        df = pd.DataFrame({"c": bons + mauvais})
        r = _un_resultat(df, "format", "c", {"nom": nom})
        assert r["violations"] == len(mauvais)
        assert sorted(r["lignes"]) == list(range(len(bons), len(bons) + len(mauvais)))

    def test_motif_personnalise(self):
        df = pd.DataFrame({"ref": ["AB-123", "ab-12", "AB-999"]})
        r = _un_resultat(df, "format", "ref", {"motif": r"[A-Z]{2}-\d{3}"})
        assert r["violations"] == 1

    def test_motif_invalide_est_une_erreur_de_regle(self):
        df = pd.DataFrame({"ref": ["a"]})
        r = _un_resultat(df, "format", "ref", {"motif": "([a"})
        assert r["statut"] == "erreur"


class TestAutresTypes:
    def test_valeurs_autorisees(self):
        df = pd.DataFrame({"statut": ["Payé", "En attente", "paye", None]})
        r = _un_resultat(df, "valeurs_autorisees", "statut", {"valeurs": ["Payé", "En attente"]})
        assert r["violations"] == 1
        assert r["exemples"] == ["paye"]

    def test_non_vide_compte_les_blancs(self):
        df = pd.DataFrame({"nom": ["Ana", None, "  ", ""]})
        r = _un_resultat(df, "non_vide", "nom")
        assert r["violations"] == 3
        assert r["evaluees"] == 4

    def test_unique_signale_toutes_les_lignes_du_groupe(self):
        df = pd.DataFrame({"id": [1, 2, 2, 3, None, None]})
        r = _un_resultat(df, "unique", "id")
        assert r["lignes"] == [1, 2]
        assert r["violations"] == 2

    def test_unique_sur_combinaison_de_colonnes(self):
        df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "x"]})
        r = _un_resultat(df, "unique", ["a", "b"])
        assert r["lignes"] == [0, 1]

    def test_comparaison_de_nombres(self):
        df = pd.DataFrame({"min": [1, 5, 3], "max": [2, 4, 3]})
        r = _un_resultat(df, "comparaison_colonnes", ["min", "max"], {"operateur": "<="})
        assert r["lignes"] == [1]

    def test_comparaison_de_dates_en_formats_mixtes(self):
        df = pd.DataFrame({
            "debut": ["2024-01-05", "2024-03-01", "05/02/2024", None],
            "fin": ["2024-02-01", "2024-02-01", "01/02/2024", "2024-01-01"],
        })
        r = _un_resultat(df, "comparaison_colonnes", ["debut", "fin"], {"operateur": "<="})
        assert r["lignes"] == [1, 2]
        assert r["evaluees"] == 3  # la ligne dont le début est vide n'est pas évaluée


class TestRobustesse:
    def test_colonne_absente_est_une_erreur_pas_une_exception(self):
        df = pd.DataFrame({"a": [1]})
        r = _un_resultat(df, "plage", "absente", {"min": 0})
        assert r["statut"] == "erreur"
        assert "absente" in r["message"]

    def test_une_regle_en_erreur_n_empeche_pas_les_autres(self):
        df = pd.DataFrame({"a": [1, -1]})
        bilan = valider(df, [
            {"type": "zzz"},
            nouvelle_regle("plage", "a", {"min": 0}),
        ])
        assert bilan["regles_en_erreur"] == 1
        assert bilan["total_violations"] == 1

    def test_liste_de_regles_vide(self):
        bilan = valider(pd.DataFrame({"a": [1]}), [])
        assert bilan["resultats"] == []
        assert formater_bilan(bilan) == ""

    def test_dataframe_vide(self):
        df = pd.DataFrame({"a": pd.Series([], dtype="float64")})
        r = _un_resultat(df, "plage", "a", {"min": 0})
        assert r["statut"] == "respectee"
        assert r["pourcentage"] == 0.0

    def test_les_lignes_sont_plafonnees(self):
        df = pd.DataFrame({"a": [-1] * 500})
        r = _un_resultat(df, "plage", "a", {"min": 0})
        assert r["violations"] == 500
        assert len(r["lignes"]) <= 100
        assert len(r["exemples"]) <= 5

    def test_resultat_serialisable_en_json(self):
        df = pd.DataFrame({"a": [1.0, -2.0], "d": pd.to_datetime(["2024-01-01", "2024-02-01"])})
        bilan = valider(df, [
            nouvelle_regle("plage", "a", {"min": 0}),
            nouvelle_regle("plage", "d", {"max": "2024-01-15"}),
        ])
        json.dumps(bilan)


class TestRegles:
    def test_identifiant_stable_et_distinct(self):
        a = nouvelle_regle("plage", "age", {"min": 0})
        assert a == nouvelle_regle("plage", "age", {"min": 0})
        assert a["id"] != nouvelle_regle("plage", "age", {"min": 1})["id"]

    @pytest.mark.parametrize("regle, fragment", [
        ({"type": "plage", "colonnes": ["a"], "parametres": {}}, "minimum ou un maximum"),
        ({"type": "plage", "colonnes": ["a"], "parametres": {"min": 5, "max": 1}}, "dépasse"),
        ({"type": "plage", "colonnes": ["a"], "parametres": {"min": "bientôt"}}, "illisible"),
        ({"type": "longueur", "colonnes": ["a"], "parametres": {"min": -1}}, "entier"),
        ({"type": "format", "colonnes": ["a"], "parametres": {}}, "nom"),
        ({"type": "format", "colonnes": ["a"], "parametres": {"nom": "x"}}, "inconnu"),
        ({"type": "valeurs_autorisees", "colonnes": ["a"], "parametres": {"valeurs": []}}, "liste"),
        ({"type": "comparaison_colonnes", "colonnes": ["a"], "parametres": {"operateur": "<"}}, "deux colonnes"),
        ({"type": "comparaison_colonnes", "colonnes": ["a", "b"], "parametres": {"operateur": "~"}}, "opérateur"),
        ({"type": "plage", "colonnes": [], "parametres": {"min": 0}}, "colonnes"),
        ({"type": "plage", "colonnes": ["a", "b"], "parametres": {"min": 0}}, "une seule colonne"),
        ("pas un dictionnaire", "dictionnaire"),
    ])
    def test_regles_mal_formees(self, regle, fragment):
        problemes = verifier_regle(regle)
        assert problemes and any(fragment in p for p in problemes)

    def test_chaque_type_a_une_description(self):
        exemples = {
            "plage": {"min": 0}, "longueur": {"max": 3}, "format": {"nom": "email"},
            "valeurs_autorisees": {"valeurs": ["a"]}, "non_vide": {}, "unique": {},
            "comparaison_colonnes": {"operateur": "<"},
        }
        assert set(exemples) == set(TYPES_REGLES)
        for type_regle, params in exemples.items():
            colonnes = ["a", "b"] if type_regle == "comparaison_colonnes" else ["a"]
            assert decrire_regle(nouvelle_regle(type_regle, colonnes, params))

    def test_libelle_prioritaire(self):
        regle = nouvelle_regle("plage", "age", {"min": 0}, libelle="Âge plausible")
        assert decrire_regle(regle) == "Âge plausible"


class TestFichier:
    def test_aller_retour(self, tmp_path):
        regles = [
            nouvelle_regle("plage", "âge", {"min": 0, "max": 120}, libelle="Âge plausible"),
            nouvelle_regle("format", "email", {"nom": "email"}),
        ]
        chemin = sauver_regles(regles, tmp_path / "sous" / "regles.json")
        assert charger_regles(chemin) == regles

    def test_accepte_une_simple_liste(self):
        regle = nouvelle_regle("non_vide", "a")
        assert regles_depuis_texte(json.dumps([regle])) == [regle]

    def test_fichier_introuvable(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            charger_regles(tmp_path / "absent.json")

    def test_json_invalide(self):
        with pytest.raises(ValueError, match="JSON invalide"):
            regles_depuis_texte("{pas du json")

    def test_regle_mal_formee_nommee_par_son_rang(self):
        texte = json.dumps({"regles": [nouvelle_regle("non_vide", "a"), {"type": "zzz"}]})
        with pytest.raises(ValueError, match="n° 2"):
            regles_depuis_texte(texte)


class TestBilan:
    def test_bilan_lisible(self):
        df = pd.DataFrame({"age": [10, -1]})
        bilan = formater_bilan(valider(df, [nouvelle_regle("plage", "age", {"min": 0})]),
                               titre="Contraintes avant nettoyage")
        assert "Contraintes avant nettoyage" in bilan
        assert "1 violation" in bilan
        assert "-1" in bilan
