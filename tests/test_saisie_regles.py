"""Tests de la description partagée du formulaire de règles (`src/saisie_regles.py`)."""

import json

import pandas as pd
import pytest

from src.saisie_regles import (
    GENRES_DE_CHAMP,
    TYPES_DE_REGLE,
    champs_du_type,
    colonnes_attendues,
    construire_regle,
    lire_borne,
    types_disponibles,
)
from src.validator import (
    FORMATS_NOMMES,
    OPERATEURS,
    TYPES_REGLES,
    charger_regles,
    regles_depuis_texte,
    regles_vers_texte,
    sauver_regles,
    valider,
)


class TestCoherenceAvecLeMoteur:
    """La description du formulaire ne doit jamais dériver du validateur."""

    def test_chaque_type_du_moteur_a_son_formulaire(self):
        assert set(TYPES_DE_REGLE) == set(TYPES_REGLES)

    def test_l_ordre_de_presentation_suit_celui_du_moteur(self):
        assert [t for t, _ in types_disponibles()] == list(TYPES_REGLES)

    def test_chaque_champ_est_bien_forme(self):
        for type_regle, description in TYPES_DE_REGLE.items():
            noms = [c["nom"] for c in description["champs"]]
            assert len(noms) == len(set(noms)), f"{type_regle} : champ en double"
            for champ in description["champs"]:
                assert champ["genre"] in GENRES_DE_CHAMP
                assert champ["libelle"] and champ["aide"]
                assert (champ["genre"] == "choix") == bool(champ["choix"])
                if champ["si_vide"]:
                    assert champ["si_vide"] in noms and champ["si_vide"] != champ["nom"]

    def test_les_choix_reprennent_les_formats_et_operateurs_du_moteur(self):
        formats = {c["nom"]: c for c in champs_du_type("format")}["nom"]["choix"]
        assert [valeur for valeur, _ in formats] == list(FORMATS_NOMMES)
        operateurs = champs_du_type("comparaison_colonnes")[0]["choix"]
        assert [valeur for valeur, _ in operateurs] == list(OPERATEURS)

    def test_champs_du_type_rend_une_copie(self):
        champs = champs_du_type("plage")
        champs[0]["libelle"] = "modifié"
        champs[0]["choix"].append(("x", "x"))
        assert champs_du_type("plage")[0]["libelle"] == "Minimum"
        assert champs_du_type("plage")[0]["choix"] == []

    def test_type_inconnu(self):
        with pytest.raises(KeyError):
            champs_du_type("zzz")
        with pytest.raises(KeyError):
            colonnes_attendues("zzz")

    def test_colonnes_attendues(self):
        assert colonnes_attendues("plage") == (1, 1)
        assert colonnes_attendues("unique") == (1, None)
        assert colonnes_attendues("comparaison_colonnes") == (2, 2)


class TestSiVide:
    """Un champ « si_vide » ne se demande que si l'autre est resté vide."""

    def test_le_motif_ne_se_demande_que_sans_format_connu(self):
        champs = {c["nom"]: c for c in champs_du_type("format")}
        assert champs["motif"]["si_vide"] == "nom"
        assert champs["nom"]["si_vide"] is None

    def test_les_autres_champs_se_demandent_toujours(self):
        for type_regle in TYPES_DE_REGLE:
            for champ in champs_du_type(type_regle):
                if (type_regle, champ["nom"]) != ("format", "motif"):
                    assert champ["si_vide"] is None


class TestLireBorne:
    @pytest.mark.parametrize("texte, attendu", [
        ("120", 120), ("0", 0), ("-4", -4), ("0,5", 0.5), ("0.5", 0.5), (" 7 ", 7),
        ("12,0", 12), ("05/01/2024", "05/01/2024"), ("2024-01-05", "2024-01-05"),
    ])
    def test_nombres_et_dates(self, texte, attendu):
        assert lire_borne(texte) == attendu
        assert type(lire_borne(texte)) is type(attendu)


class TestConstruireRegle:
    def test_plage_numerique(self):
        regle, problemes = construire_regle("plage", "age", {"min": "0", "max": "120"})
        assert problemes == []
        assert regle["type"] == "plage" and regle["colonnes"] == ["age"]
        assert regle["parametres"] == {"min": 0, "max": 120}

    def test_plage_une_seule_borne_les_champs_vides_sont_ignores(self):
        regle, _ = construire_regle("plage", "age", {"min": "0", "max": "  "})
        assert regle["parametres"] == {"min": 0}

    def test_plage_de_dates(self):
        regle, problemes = construire_regle("plage", "naissance", {"min": "01/01/1900"})
        assert problemes == [] and regle["parametres"] == {"min": "01/01/1900"}

    def test_plage_sans_borne(self):
        regle, problemes = construire_regle("plage", "age", {})
        assert regle is None
        assert any("minimum ou un maximum" in p for p in problemes)

    def test_plage_bornes_inversees(self):
        regle, problemes = construire_regle("plage", "age", {"min": "10", "max": "1"})
        assert regle is None and any("dépasse" in p for p in problemes)

    def test_plage_borne_illisible(self):
        regle, problemes = construire_regle("plage", "age", {"min": "bientôt"})
        assert regle is None and any("illisible" in p for p in problemes)

    def test_longueur(self):
        regle, _ = construire_regle("longueur", "cp", {"min": "5", "max": "5"})
        assert regle["parametres"] == {"min": 5, "max": 5}

    def test_longueur_non_entiere(self):
        regle, problemes = construire_regle("longueur", "cp", {"min": "cinq"})
        assert regle is None
        assert any("nombre entier" in p and "Longueur minimale" in p for p in problemes)

    def test_format_nomme(self):
        regle, problemes = construire_regle("format", "mail", {"nom": "email"})
        assert problemes == [] and regle["parametres"] == {"nom": "email"}

    def test_format_motif(self):
        regle, _ = construire_regle("format", "ref", {"motif": r"[A-Z]{2}-\d{3}"})
        assert regle["parametres"] == {"motif": r"[A-Z]{2}-\d{3}"}

    def test_format_nom_et_motif_ensemble_ou_aucun(self):
        _, ensemble = construire_regle("format", "c", {"nom": "email", "motif": "x"})
        _, aucun = construire_regle("format", "c", {})
        assert ensemble and aucun

    def test_format_inconnu(self):
        regle, problemes = construire_regle("format", "c", {"nom": "imaginaire"})
        assert regle is None and any("pas un choix possible" in p for p in problemes)

    def test_motif_invalide(self):
        regle, problemes = construire_regle("format", "c", {"motif": "([a"})
        assert regle is None and any("expression régulière invalide" in p for p in problemes)

    def test_valeurs_autorisees(self):
        regle, _ = construire_regle("valeurs_autorisees", "statut",
                                    {"valeurs": "Payé ; En attente ;; Annulé "})
        assert regle["parametres"] == {"valeurs": ["Payé", "En attente", "Annulé"]}

    def test_valeurs_autorisees_obligatoires(self):
        regle, problemes = construire_regle("valeurs_autorisees", "statut", {"valeurs": ""})
        assert regle is None and any("obligatoire" in p for p in problemes)
        regle, problemes = construire_regle("valeurs_autorisees", "statut", {"valeurs": " ; ; "})
        assert regle is None and any("au moins une valeur" in p for p in problemes)

    @pytest.mark.parametrize("type_regle", ["non_vide", "unique"])
    def test_types_sans_parametre(self, type_regle):
        regle, problemes = construire_regle(type_regle, "id")
        assert problemes == [] and regle["parametres"] == {}

    def test_unique_sur_plusieurs_colonnes(self):
        regle, _ = construire_regle("unique", ["a", "b", "c"])
        assert regle["colonnes"] == ["a", "b", "c"]

    def test_comparaison(self):
        regle, problemes = construire_regle("comparaison_colonnes", ["debut", "fin"],
                                            {"operateur": "<="})
        assert problemes == [] and regle["colonnes"] == ["debut", "fin"]
        assert regle["parametres"] == {"operateur": "<="}

    def test_comparaison_operateur_obligatoire(self):
        regle, problemes = construire_regle("comparaison_colonnes", ["a", "b"], {})
        assert regle is None and any("obligatoire" in p for p in problemes)

    @pytest.mark.parametrize("type_regle, colonnes", [
        ("plage", []), ("plage", ["a", "b"]), ("unique", []),
        ("comparaison_colonnes", ["a"]), ("comparaison_colonnes", ["a", "b", "c"]),
    ])
    def test_nombre_de_colonnes(self, type_regle, colonnes):
        regle, problemes = construire_regle(type_regle, colonnes,
                                            {"min": "0", "operateur": "<"})
        assert regle is None and any("colonne" in p for p in problemes)

    def test_colonnes_vides_ignorees(self):
        regle, _ = construire_regle("plage", ["", "age", "  "], {"min": "0"})
        assert regle["colonnes"] == ["age"]

    def test_type_inconnu_message_en_francais(self):
        regle, problemes = construire_regle("zzz", "a", {})
        assert regle is None and "type de règle inconnu" in problemes[0]

    def test_libelle_conserve(self):
        regle, _ = construire_regle("plage", "age", {"min": "0"}, libelle="Âge plausible")
        assert regle["libelle"] == "Âge plausible"

    def test_tous_les_problemes_sont_rapportes_ensemble(self):
        regle, problemes = construire_regle("longueur", "c", {"min": "a", "max": "b"})
        assert regle is None and len(problemes) == 2

    def test_aucune_regle_construite_n_est_mal_formee(self):
        """Contrat : ce que renvoie `construire_regle` passe toujours `verifier_regle`."""
        from src.validator import verifier_regle
        cas = [("plage", "a", {"min": "1"}), ("longueur", "a", {"max": "9"}),
               ("format", "a", {"nom": "siret"}), ("non_vide", "a", {}),
               ("comparaison_colonnes", ["a", "b"], {"operateur": "!="})]
        for type_regle, colonnes, saisies in cas:
            regle, problemes = construire_regle(type_regle, colonnes, saisies)
            assert problemes == [] and verifier_regle(regle) == []

    def test_la_regle_construite_s_evalue(self):
        regle, _ = construire_regle("plage", "age", {"min": "0", "max": "120"})
        bilan = valider(pd.DataFrame({"age": [25, -3, 130]}), [regle])
        assert bilan["total_violations"] == 2


class TestExportEnMemoire:
    REGLES = [construire_regle("plage", "âge", {"min": "0", "max": "120"},
                               libelle="Âge plausible")[0],
              construire_regle("format", "mail", {"nom": "email"})[0]]

    def test_aller_retour_en_memoire(self):
        assert regles_depuis_texte(regles_vers_texte(self.REGLES)) == self.REGLES

    def test_texte_json_lisible_et_accentue(self):
        texte = regles_vers_texte(self.REGLES)
        assert json.loads(texte)["version"] == 1
        assert "Âge plausible" in texte  # pas d'échappement Â

    def test_le_fichier_est_identique_au_texte(self, tmp_path):
        chemin = sauver_regles(self.REGLES, tmp_path / "regles.json")
        assert chemin.read_text(encoding="utf-8") == regles_vers_texte(self.REGLES)
        assert charger_regles(chemin) == self.REGLES

    def test_rien_n_est_ecrit_sur_le_disque(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        regles_vers_texte(self.REGLES)
        assert list(tmp_path.iterdir()) == []
