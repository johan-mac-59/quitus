"""Tests d'intégration de l'interface web, sans navigateur.

Streamlit fournit un harnais (`AppTest`) qui exécute réellement le script de
l'application et permet d'agir sur ses widgets. Ces tests pilotent donc le
parcours complet — dépôt, analyse, options, nettoyage, téléchargements — dans
les mêmes conditions qu'un utilisateur, mais sans navigateur.

Ils couvrent aussi les deux garanties de confidentialité annoncées dans
l'application : rien n'est écrit sur le serveur sans demande explicite, et le
bouton d'effacement vide réellement l'état.
"""

import io
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

RACINE = Path(__file__).parent.parent
APP = RACINE / "app.py"
ECHANTILLON = RACINE / "data" / "samples" / "reservations_exemple.csv"

# Le rendu des figures et le profilage sont lents : on laisse de la marge.
DELAI = 120


@pytest.fixture
def app():
    """Application chargée, avant première exécution."""
    return AppTest.from_file(str(APP), default_timeout=DELAI)


@pytest.fixture
def csv_sale():
    """Petit CSV portant toutes les anomalies que le pipeline doit corriger."""
    rng = np.random.default_rng(seed=3)
    lignes = ["id;ville;montant;note"]
    for i in range(40):
        ville = ["Lille", "lille", "LILLE ", " Paris", "Paris"][i % 5]
        # Distribution resserree, plus quelques valeurs extremes : un IQR nul
        # (deux valeurs distinctes seulement) ne permettrait aucune detection.
        brut = 48000.0 if i % 13 == 0 else float(rng.normal(100, 8))
        montant = f"{brut:.2f} €".replace(".", ",")
        note = "" if i % 9 == 0 else str(i % 5 + 1)
        lignes.append(f"R{1000 + i};{ville};{montant};{note}")
    # Deux doublons exacts
    lignes.append(lignes[1])
    lignes.append(lignes[2])
    return "\n".join(lignes).encode("utf-8")


def _deposer(app, contenu: bytes, nom: str):
    """Simule le dépôt d'un fichier dans le composant d'envoi.

    Args:
        app: Instance d'AppTest déjà exécutée une première fois.
        contenu: Octets du fichier.
        nom: Nom du fichier.

    Returns:
        L'application après réexécution.
    """
    types = {
        ".csv": "text/csv",
        ".json": "application/json",
        ".jsonl": "application/x-ndjson",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    mime = types.get(Path(nom).suffix.lower(), "application/octet-stream")
    app.file_uploader[0].upload(nom, contenu, mime)
    return app.run()


class TestDemarrage:
    def test_l_application_demarre_sans_exception(self, app):
        """Le script s'exécute de bout en bout sur un état vierge."""
        app.run()
        assert not app.exception

    def test_affiche_le_titre(self, app):
        """Le titre principal est présent."""
        app.run()
        assert any("Nettoyage automatique" in t.value for t in app.title)

    def test_propose_le_depot_de_fichier(self, app):
        """Le composant d'envoi de fichier est offert d'emblée."""
        app.run()
        assert len(app.file_uploader) == 1

    def test_encart_confidentialite_present(self, app):
        """La note de transparence est visible avant tout dépôt."""
        app.run()
        titres = [e.label for e in app.expander]
        assert any("Confidentialité" in t for t in titres)

    def test_aucun_bouton_de_nettoyage_sans_fichier(self, app):
        """Les actions de nettoyage n'apparaissent pas prématurément."""
        app.run()
        libelles = [b.label for b in app.button]
        assert not any("Nettoyer" in lib for lib in libelles)


class TestParcoursComplet:
    """Parcours nominal : déposer, analyser, nettoyer, télécharger."""

    def test_depot_affiche_les_indicateurs(self, app, csv_sale):
        """Après dépôt, les métriques du fichier brut sont affichées."""
        app.run()
        app = _deposer(app, csv_sale, "sale.csv")
        assert not app.exception

        etiquettes = [m.label for m in app.metric]
        assert "Lignes" in etiquettes
        assert "Colonnes" in etiquettes
        assert "Doublons" in etiquettes

    def test_depot_charge_les_donnees_en_session(self, app, csv_sale):
        """Le DataFrame brut est bien rangé en session."""
        app.run()
        app = _deposer(app, csv_sale, "sale.csv")
        df = app.session_state["df_brut"]
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 42
        assert list(df.columns) == ["id", "ville", "montant", "note"]

    def test_separateur_point_virgule_detecte(self, app, csv_sale):
        """La détection du séparateur fonctionne via l'interface."""
        app.run()
        app = _deposer(app, csv_sale, "sale.csv")
        # Un séparateur mal détecté donnerait une colonne unique.
        assert app.session_state["df_brut"].shape[1] == 4

    def test_analyse_puis_nettoyage(self, app, csv_sale):
        """Le parcours complet aboutit à un DataFrame nettoyé."""
        app.run()
        app = _deposer(app, csv_sale, "sale.csv")

        # Étape 1 : analyser
        bouton_analyse = [b for b in app.sidebar.button if "Analyser" in b.label]
        assert bouton_analyse, "Le bouton d'analyse devrait être proposé"
        app = bouton_analyse[0].click().run()
        assert not app.exception
        assert app.session_state["profil"] is not None
        assert "shape" in app.session_state["profil"]

        # Étape 2 : cocher les deux traitements lourds puis nettoyer
        for case in app.sidebar.checkbox:
            if "Écrêter" in case.label or "Combler" in case.label:
                case.set_value(True)
        boutons = [b for b in app.sidebar.button if "Nettoyer" in b.label]
        if not boutons:
            # Le bouton de soumission d'un formulaire est exposé séparément.
            boutons = [b for b in app.button if "Nettoyer" in b.label]
        assert boutons, "Le bouton de nettoyage devrait être proposé"
        app = boutons[0].click().run()

        assert not app.exception
        propre = app.session_state["df_propre"]
        assert isinstance(propre, pd.DataFrame)
        assert app.session_state["stats"] is not None

    def test_le_nettoyage_supprime_les_doublons(self, app, csv_sale):
        """Le nettoyage produit un effet mesurable sur les données."""
        app = _apres_nettoyage(app, csv_sale, ecreter=True, combler=True)
        brut = app.session_state["df_brut"]
        propre = app.session_state["df_propre"]
        assert len(propre) < len(brut), "Les doublons devaient disparaître"
        assert app.session_state["stats"]["duplicates_removed"] >= 2

    def test_le_nettoyage_uniformise_la_casse(self, app, csv_sale):
        """Les variations de casse et les espaces sont corrigés."""
        app = _apres_nettoyage(app, csv_sale, ecreter=False, combler=False)
        villes = set(app.session_state["df_propre"]["ville"].dropna())
        # « Lille », « lille » et « LILLE  » doivent avoir fusionné.
        assert len([v for v in villes if v.strip().lower() == "lille"]) == 1

    def test_le_nettoyage_convertit_les_montants(self, app, csv_sale):
        """Une colonne monétaire textuelle devient numérique."""
        app = _apres_nettoyage(app, csv_sale, ecreter=False, combler=False)
        montant = app.session_state["df_propre"]["montant"]
        assert pd.api.types.is_numeric_dtype(montant)

    def test_l_ecretage_est_honore(self, app, csv_sale):
        """Cocher l'écrêtage produit effectivement des corrections."""
        app = _apres_nettoyage(app, csv_sale, ecreter=True, combler=True)
        corriges = app.session_state["stats"]["outliers_corrected"]
        assert "ignored" not in corriges, "L'écrêtage demandé ne doit pas être ignoré"

    def test_l_ecretage_refuse_est_signale(self, app, csv_sale):
        """Ne pas cocher l'écrêtage laisse la sentinelle d'abandon."""
        app = _apres_nettoyage(app, csv_sale, ecreter=False, combler=False)
        assert "ignored" in app.session_state["stats"]["outliers_corrected"]

    def test_boutons_de_telechargement_proposes(self, app, csv_sale):
        """Le CSV nettoyé et les rapports sont offerts au téléchargement."""
        app = _apres_nettoyage(app, csv_sale, ecreter=True, combler=True)
        libelles = [b.label for b in app.download_button]
        assert any("CSV nettoyé" in lib for lib in libelles)
        assert any("Profilage" in lib for lib in libelles)
        assert any("Rapport de nettoyage" in lib for lib in libelles)

    def test_le_csv_telechargeable_est_relisible(self, app, csv_sale):
        """Le contenu proposé au téléchargement est un CSV valide."""
        app = _apres_nettoyage(app, csv_sale, ecreter=True, combler=True)
        propre = app.session_state["df_propre"]
        relu = pd.read_csv(io.StringIO(propre.to_csv(index=False)))
        assert list(relu.columns) == list(propre.columns)
        assert len(relu) == len(propre)

    def test_journaux_console_captures(self, app, csv_sale):
        """La sortie console du pipeline est captée pour affichage."""
        app = _apres_nettoyage(app, csv_sale, ecreter=True, combler=True)
        journaux = app.session_state["journaux"]
        assert "chargement" in journaux
        assert "nettoyage" in journaux
        assert journaux["chargement"].strip()


class TestFormats:
    """Les quatre formats annoncés doivent tous fonctionner via l'interface."""

    def test_json(self, app):
        """Un JSON déposé est chargé."""
        app.run()
        app = _deposer(app, b'[{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]', "d.json")
        assert not app.exception
        assert len(app.session_state["df_brut"]) == 2

    def test_jsonl(self, app):
        """Un JSON Lines déposé est chargé."""
        app.run()
        app = _deposer(app, b'{"a": 1}\n{"a": 2}\n{"a": 3}\n', "d.jsonl")
        assert not app.exception
        assert len(app.session_state["df_brut"]) == 3

    def test_excel(self, app):
        """Un classeur Excel déposé est chargé."""
        tampon = io.BytesIO()
        pd.DataFrame({"x": [1, 2, 3], "y": ["a", "b", "c"]}).to_excel(tampon, index=False)
        app.run()
        app = _deposer(app, tampon.getvalue(), "classeur.xlsx")
        assert not app.exception
        assert list(app.session_state["df_brut"].columns) == ["x", "y"]

    @pytest.mark.skipif(not ECHANTILLON.exists(),
                        reason="échantillon versionné absent")
    def test_echantillon_du_depot(self, app):
        """L'échantillon versionné passe dans l'interface."""
        app.run()
        app = _deposer(app, ECHANTILLON.read_bytes(), ECHANTILLON.name)
        assert not app.exception
        assert len(app.session_state["df_brut"]) == 312


class TestChangementDeFichier:
    def test_le_second_depot_efface_l_aval(self, app, csv_sale):
        """Déposer un autre fichier ne laisse aucune donnée périmée.

        Sans cette remise à zéro, on afficherait le dataset nettoyé du premier
        fichier à côté du profilage du second.
        """
        app = _apres_nettoyage(app, csv_sale, ecreter=True, combler=True)
        assert app.session_state["df_propre"] is not None

        app = _deposer(app, b"z\n1\n2\n", "autre.csv")
        assert app.session_state["df_propre"] is None
        assert app.session_state["profil"] is None
        assert app.session_state["stats"] is None
        assert list(app.session_state["df_brut"].columns) == ["z"]


class TestConfidentialite:
    def test_aucune_ecriture_disque_par_defaut(self, app, csv_sale, tmp_path,
                                               monkeypatch):
        """Un parcours complet n'écrit rien dans data/ sans demande explicite."""
        rapports = RACINE / "data" / "reports"
        avant = set(rapports.glob("*")) if rapports.exists() else set()

        app = _apres_nettoyage(app, csv_sale, ecreter=True, combler=True)

        apres = set(rapports.glob("*")) if rapports.exists() else set()
        assert apres == avant, "Aucun fichier ne doit apparaître sans demande"

    def test_bouton_effacer_vide_l_etat(self, app, csv_sale):
        """Le bouton d'effacement remet réellement la session à zéro."""
        app = _apres_nettoyage(app, csv_sale, ecreter=True, combler=True)
        assert app.session_state["df_brut"] is not None

        boutons = [b for b in app.sidebar.button if "Effacer" in b.label]
        assert boutons, "Le bouton d'effacement devrait être proposé"
        app = boutons[0].click().run()

        assert app.session_state["df_brut"] is None
        assert app.session_state["profil"] is None
        assert app.session_state["signature"] is None


class TestRobustesse:
    def test_fichier_vide(self, app):
        """Un fichier vide ne fait pas planter l'application."""
        app.run()
        app = _deposer(app, b"", "vide.csv")
        assert not app.exception

    def test_une_seule_colonne(self, app):
        """Un fichier à une colonne, sans numérique, reste exploitable."""
        app.run()
        app = _deposer(app, "nom\nAlice\nBob\nAlice\n".encode("utf-8"), "noms.csv")
        assert not app.exception
        boutons = [b for b in app.sidebar.button if "Analyser" in b.label]
        app = boutons[0].click().run()
        assert not app.exception

    def test_colonnes_toutes_vides(self, app):
        """Des colonnes entièrement vides ne bloquent pas le profilage."""
        app.run()
        app = _deposer(app, b"a;b;c\n1;;\n2;;\n3;;\n", "trouee.csv")
        assert not app.exception
        boutons = [b for b in app.sidebar.button if "Analyser" in b.label]
        app = boutons[0].click().run()
        assert not app.exception


# --------------------------------------------------------------------------
# Utilitaire de parcours
# --------------------------------------------------------------------------

def _apres_nettoyage(app, contenu: bytes, *, ecreter: bool, combler: bool):
    """Déroule le parcours complet jusqu'au nettoyage inclus.

    Args:
        app: Instance d'AppTest vierge.
        contenu: Octets du fichier à déposer.
        ecreter: Coche l'écrêtage des valeurs aberrantes.
        combler: Coche le remplissage des valeurs manquantes.

    Returns:
        L'application après nettoyage.
    """
    app.run()
    app = _deposer(app, contenu, "donnees.csv")

    analyse = [b for b in app.sidebar.button if "Analyser" in b.label]
    app = analyse[0].click().run()

    for case in app.sidebar.checkbox:
        if "Écrêter" in case.label:
            case.set_value(ecreter)
        elif "Combler" in case.label:
            case.set_value(combler)

    nettoyer = [b for b in app.sidebar.button if "Nettoyer" in b.label]
    if not nettoyer:
        nettoyer = [b for b in app.button if "Nettoyer" in b.label]
    return nettoyer[0].click().run()
