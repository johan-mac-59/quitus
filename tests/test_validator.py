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


class TestGardeFous:
    """Les règles viennent de l'utilisateur : l'application ne doit jamais se figer."""

    def test_motif_catastrophique_interrompu_dans_le_delai(self, monkeypatch):
        """`(\\d+)+` sur 40 chiffres et une lettre prendrait des heures : on l'arrête."""
        import time
        from src import validator
        monkeypatch.setattr(validator, "DELAI_MOTIF", 1.0)
        df = pd.DataFrame({"ref": ["1" * 40 + "x", "123"], "age": [-1, 5]})
        debut = time.perf_counter()
        bilan = valider(df, [nouvelle_regle("format", "ref", {"motif": r"(\d+)+"}),
                             nouvelle_regle("plage", "age", {"min": 0})])
        assert time.perf_counter() - debut < 5
        piege, autre = bilan["resultats"]
        assert piege["statut"] == "erreur" and "trop de temps" in piege["message"]
        # Une règle qui s'emballe ne prive pas les autres de leur verdict.
        assert autre["statut"] == "violations" and autre["violations"] == 1

    def test_motif_raisonnable_sur_les_memes_donnees(self):
        df = pd.DataFrame({"ref": ["1" * 40 + "x", "123", "45"]})
        r = _un_resultat(df, "format", "ref", {"motif": r"\d+"})
        assert r["statut"] == "violations" and r["lignes"] == [0]

    def test_seules_les_valeurs_distinctes_sont_testees_mais_toutes_les_lignes_comptees(self):
        df = pd.DataFrame({"c": ["AB", "AB", "AB", "x", None, "x"]})
        r = _un_resultat(df, "format", "c", {"motif": "[A-Z]+"})
        assert r["evaluees"] == 5 and r["violations"] == 2 and r["lignes"] == [3, 5]

    def test_les_valeurs_manquantes_ne_plantent_pas_le_travailleur(self):
        df = pd.DataFrame({"c": [None, None]})
        r = _un_resultat(df, "format", "c", {"motif": "a"})
        assert r["statut"] == "respectee" and r["evaluees"] == 0

    def test_motif_trop_long_refuse(self):
        regle = nouvelle_regle("format", "c", {"motif": "a" * 201})
        assert any("trop long" in p for p in verifier_regle(regle))
        assert verifier_regle(nouvelle_regle("format", "c", {"motif": "a" * 200})) == []

    def test_trop_de_valeurs_autorisees_refuse(self):
        regle = nouvelle_regle("valeurs_autorisees", "c", {"valeurs": [str(i) for i in range(1001)]})
        assert any("trop de valeurs" in p for p in verifier_regle(regle))

    def test_trop_de_regles_a_l_import_refuse(self):
        regles = [nouvelle_regle("non_vide", f"c{i}") for i in range(101)]
        with pytest.raises(ValueError, match="trop de règles"):
            regles_depuis_texte(json.dumps({"regles": regles}))
        assert len(regles_depuis_texte(json.dumps({"regles": regles[:100]}))) == 100

    def test_une_valeur_ne_peut_pas_injecter_de_code_dans_le_travailleur(self):
        """Les valeurs passent en JSON sur l'entrée du processus, jamais dans son programme."""
        df = pd.DataFrame({"c": ['"); import os; os.system("echo x") #', "ok"]})
        r = _un_resultat(df, "format", "c", {"motif": "ok"})
        assert r["statut"] == "violations" and r["violations"] == 1


class TestFichierDeReglesPiege:
    """Un fichier de règles peut venir d'un tiers : il ne doit rien casser ni rien afficher de trompeur."""

    def test_json_tres_imbrique_refuse_proprement(self):
        with pytest.raises(ValueError, match="imbrication excessive"):
            regles_depuis_texte("[" * 200000 + "]" * 200000)

    def test_fichier_trop_volumineux_refuse_avant_lecture(self, monkeypatch):
        from src import validator

        def interdit(*_a, **_k):
            raise AssertionError("le fichier ne doit pas être lu")

        monkeypatch.setattr(validator.json, "loads", interdit)
        with pytest.raises(ValueError, match="trop volumineux"):
            regles_depuis_texte("x" * (validator.MAX_TAILLE_FICHIER_REGLES + 1))

    def test_json_qui_n_est_pas_une_liste_de_regles(self):
        for texte in ("42", '"texte"', "null", '{"regles": 3}'):
            with pytest.raises(ValueError):
                regles_depuis_texte(texte)

    def test_une_regle_n_est_pas_un_programme(self):
        """Du code dans un champ n'est jamais exécuté : ce n'est qu'une chaîne."""
        piege = {"type": "non_vide", "colonnes": ["__import__('os').system('echo x')"],
                 "parametres": {}, "libelle": "__import__('os').system('echo x')"}
        assert regles_depuis_texte(json.dumps([piege]))[0]["libelle"].startswith("__import__")

    def test_echapper_markdown_neutralise_liens_et_images(self):
        from src.validator import echapper_markdown
        sortie = echapper_markdown("[Cliquez ici](http://x.invalid) ![](http://x.invalid/p.png)")
        assert "](http" not in sortie.replace("\\]\\(http", "")
        assert sortie == "\\[Cliquez ici\\]\\(http://x.invalid\\) \\!\\[\\]\\(http://x.invalid/p.png\\)"

    def test_echapper_markdown_laisse_lisible_un_texte_ordinaire(self):
        from src.validator import echapper_markdown
        assert echapper_markdown("age : valeur entre 0 et 120") == "age : valeur entre 0 et 120"
        assert echapper_markdown(42) == "42"


class TestReglesAPlusieursColonnesSansViolation:
    """Régression : une règle à plusieurs colonnes sans violation faisait échouer l'évaluation."""

    @pytest.mark.parametrize("type_regle, colonnes, parametres", [
        ("comparaison_colonnes", ["a", "b"], {"operateur": "<"}),
        ("unique", ["a", "b"], {}),
    ])
    def test_aucune_violation_ne_plante_pas(self, type_regle, colonnes, parametres):
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        r = _un_resultat(df, type_regle, colonnes, parametres)
        assert r["statut"] == "respectee" and r["violations"] == 0 and r["exemples"] == []

    def test_les_exemples_a_plusieurs_colonnes_sont_plafonnes(self):
        df = pd.DataFrame({"a": range(20), "b": [0] * 20})
        r = _un_resultat(df, "comparaison_colonnes", ["a", "b"], {"operateur": "<"})
        assert r["violations"] == 20 and len(r["exemples"]) == 5
        assert r["exemples"][0] == "0 | 0"


def test_une_regle_ne_fait_jamais_echouer_les_autres_meme_si_son_calcul_echoue(monkeypatch):
    """Toute erreur pendant le calcul d'une règle, y compris après l'évaluation, devient un verdict d'erreur."""
    from src import validator

    def casse(*_a, **_k):
        raise RuntimeError("panne simulée")

    monkeypatch.setitem(validator._EVALUATEURS, "non_vide", casse)
    df = pd.DataFrame({"a": [1, None], "b": [-1, 2]})
    bilan = valider(df, [nouvelle_regle("non_vide", "a"), nouvelle_regle("plage", "b", {"min": 0})])
    casse_r, autre = bilan["resultats"]
    assert casse_r["statut"] == "erreur" and "panne simulée" in casse_r["message"]
    assert autre["statut"] == "violations" and autre["violations"] == 1


class TestCompatibiliteDesColonnes:
    """Une plage ou une comparaison n'ont de sens que sur des nombres ou des dates."""

    @pytest.fixture
    def donnees(self):
        return pd.DataFrame({
            "ville": ["Lille", "Nice", "Lyon"] * 10,
            "region": ["Nord", "Sud", "Rhône"] * 10,
            "age": [20, 30, 40] * 10,
            "montant": ["12,50", "7,00", "130"] * 10,
            "debut": ["2025-01-01", "02/02/2025", "2025-03-03"] * 10,
            "fin": ["2025-02-01", "03/03/2025", "2025-04-04"] * 10,
        })

    def test_nature_des_colonnes(self, donnees):
        from src.validator import nature_colonne
        assert {c: nature_colonne(donnees[c]) for c in donnees} == {
            "ville": "texte", "region": "texte", "age": "nombre",
            "montant": "nombre", "debut": "date", "fin": "date"}

    def test_booleen_et_colonne_vide_sont_du_texte(self):
        from src.validator import nature_colonne
        assert nature_colonne(pd.Series([True, False])) == "texte"
        assert nature_colonne(pd.Series([None, "", " "])) == "texte"

    def test_une_plage_ne_propose_pas_le_texte(self, donnees):
        from src.validator import colonnes_compatibles
        assert colonnes_compatibles(donnees, "plage") == ["age", "montant", "debut", "fin"]

    def test_les_autres_types_proposent_tout(self, donnees):
        from src.validator import colonnes_compatibles
        for type_regle in ("longueur", "format", "valeurs_autorisees", "non_vide", "unique"):
            assert colonnes_compatibles(donnees, type_regle) == list(donnees.columns)

    def test_comparaison_exclut_les_colonnes_sans_partenaire(self, donnees):
        from src.validator import colonnes_compatibles
        assert colonnes_compatibles(donnees, "comparaison_colonnes") == [
            "age", "montant", "debut", "fin"]
        seul = donnees[["ville", "age", "debut"]]
        assert colonnes_compatibles(seul, "comparaison_colonnes") == []

    def test_comparables_meme_nature_seulement(self, donnees):
        from src.validator import colonnes_comparables
        assert colonnes_comparables(donnees, "debut") == ["fin"]
        assert colonnes_comparables(donnees, "age") == ["montant"]
        assert colonnes_comparables(donnees, "ville") == []

    def test_verifier_colonnes_refuse_le_texte_et_les_natures_mixtes(self, donnees):
        from src.validator import verifier_colonnes
        assert verifier_colonnes(donnees, "plage", ["age"]) == []
        assert "est du texte" in verifier_colonnes(donnees, "plage", ["ville"])[0]
        assert verifier_colonnes(donnees, "comparaison_colonnes", ["debut", "fin"]) == []
        assert "est du texte" in verifier_colonnes(
            donnees, "comparaison_colonnes", ["ville", "region"])[0]
        assert "ne se comparent pas" in verifier_colonnes(
            donnees, "comparaison_colonnes", ["debut", "age"])[0]
        assert "absente" in verifier_colonnes(donnees, "plage", ["inconnue"])[0]


class TestReglesNonRealisables:
    """Les règles qui ne peuvent pas s'appliquer sont repérées, pas écartées."""

    @pytest.fixture
    def donnees(self):
        return pd.DataFrame({"ville": ["Lille", "Nice"] * 10, "age": [20, 30] * 10})

    def test_aucune_alerte_quand_tout_s_applique(self, donnees):
        from src.validator import nouvelle_regle, regles_non_realisables
        assert regles_non_realisables(donnees, [
            nouvelle_regle("plage", "age", {"max": 120}),
            nouvelle_regle("non_vide", "ville")]) == []

    def test_plage_sur_du_texte_et_colonne_absente_signalees(self, donnees):
        from src.validator import nouvelle_regle, regles_non_realisables
        phrases = regles_non_realisables(donnees, [
            nouvelle_regle("plage", "ville", {"max": 5}),
            nouvelle_regle("non_vide", "pays"),
            nouvelle_regle("non_vide", "age")])
        assert len(phrases) == 2
        assert "est du texte" in phrases[0] and "absente" in phrases[1]

    def test_la_regle_reste_non_evaluable_au_verdict(self, donnees):
        """L'alerte n'écarte rien : `valider` déclare toujours la règle non évaluable."""
        from src.validator import nouvelle_regle, valider
        bilan = valider(donnees, [nouvelle_regle("plage", "ville", {"max": 5})])
        assert bilan["resultats"][0]["non_evaluables"] == 20
