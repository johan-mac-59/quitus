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
APP = RACINE / "streamlit_app.py"
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
    app.file_uploader(key=f"envoi_{app.session_state['generation_envoi']}").upload(
        nom, contenu, mime)
    return app.run()


class TestDemarrage:
    def test_l_application_demarre_sans_exception(self, app):
        """Le script s'exécute de bout en bout sur un état vierge."""
        app.run()
        assert not app.exception

    def test_affiche_le_logo_quitus(self, app):
        """Le logo Quitus, inséré en SVG, tient lieu de titre en tête de page.

        Jamais par st.html : son filtre DOMPurify, en profil « HTML seul »,
        supprime tout SVG côté navigateur, et le logo disparaissait.
        """
        app.run()
        assert any("<svg" in m.value and 'aria-label="Quitus' in m.value
                   for m in app.markdown)
        assert not any("<svg" in h.proto.body for h in app.get("html"))

    def test_logo_agrandi(self):
        """Le logo s'affiche à 450 px de large, sans dépasser la page."""
        import streamlit_app

        assert streamlit_app.LARGEUR_LOGO == 450
        assert "width: 450px; max-width: 100%" in streamlit_app.STYLE_HAUT_DE_PAGE

    def test_fichiers_du_logo_valides_et_sans_script(self):
        """Les deux SVG existent, sont bien formés, et n'embarquent aucun code."""
        import xml.etree.ElementTree as ET

        for nom in ("quitus-logo-light.svg", "quitus-logo-dark.svg", "quitus-icon.svg"):
            chemin = RACINE / "assets" / nom
            assert ET.parse(chemin).getroot().tag.endswith("svg"), nom
            contenu = chemin.read_text(encoding="utf-8").lower()
            assert "<script" not in contenu and "onload" not in contenu, nom

    def test_logo_adaptatif_suit_le_theme(self):
        """Les couleurs propres à chaque variante deviennent light-dark(claire, sombre)."""
        from src import marque

        svg = marque.logo_adaptatif_svg()
        assert svg and svg.startswith("<svg")
        assert "fill: light-dark(#12304A, #FFFFFF)" in svg       # le nom
        assert "fill: light-dark(#4A6378, #9FB4C7)" in svg       # la devise
        assert "stroke: light-dark(transparent, #2C5474)" in svg  # le contour
        assert "none" not in svg.split("light-dark")[1].split(")")[0]
        assert "<script" not in svg.lower()

    def test_logo_adaptatif_repli_si_variante_absente(self, monkeypatch, tmp_path):
        """Sans variante sombre, pas de fusion : l'app retombe sur le logo clair."""
        from src import marque

        monkeypatch.setattr(marque, "CHEMIN_LOGO_SOMBRE", tmp_path / "absent.svg")
        marque.logo_adaptatif_svg.cache_clear()
        try:
            assert marque.logo_adaptatif_svg() is None
        finally:
            marque.logo_adaptatif_svg.cache_clear()

    def test_theme_laisse_au_choix_du_visiteur(self):
        """Aucun thème imposé : le menu Settings propose clair, sombre ou automatique."""
        import tomllib

        with open(RACINE / ".streamlit" / "config.toml", "rb") as f:
            assert "base" not in tomllib.load(f).get("theme", {})

    def test_texte_agrandi_d_un_pixel(self):
        """Texte courant 17 px, libellés et légendes 15 px, déclarés après."""
        import streamlit_app

        style = streamlit_app.STYLE_TEXTE
        assert "font-size: 17px" in style and "font-size: 15px" in style
        assert style.index("17px") < style.index("stWidgetLabel") < style.index("stCaptionContainer")

    def test_mot_quitus_comme_dans_le_logo(self):
        """La barre latérale écrit « quitus » en minuscules, couleur selon le thème."""
        import streamlit_app

        html = streamlit_app.mot_quitus_html()
        assert ">quitus</div>" in html and "font-weight: 700" in html
        assert "color: light-dark(#12304A, #FFFFFF)" in html

    def test_limite_de_depot_annoncee_et_configuree(self):
        """La limite affichée à l'utilisateur est celle réellement configurée."""
        import tomllib

        with open(RACINE / ".streamlit" / "config.toml", "rb") as f:
            limite = tomllib.load(f)["server"]["maxUploadSize"]
        assert limite == 20
        source = (RACINE / "streamlit_app.py").read_text(encoding="utf-8")
        assert f"{limite} Mo au plus" in source

    def test_icone_carree(self):
        """L'icône d'onglet du navigateur doit être carrée."""
        import xml.etree.ElementTree as ET

        racine = ET.parse(RACINE / "assets" / "quitus-icon.svg").getroot()
        assert racine.get("viewBox") == "0 0 64 64"

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


def _boutons_soutien(conteneur):
    """Les boutons de soutien d'un conteneur, à l'exclusion des boutons de contact."""
    return [b for b in conteneur.get("link_button") if "soutien_" in b.proto.id]


def _boutons_contact(conteneur):
    """Les boutons de contact (GitHub, LinkedIn) d'un conteneur."""
    return [b for b in conteneur.get("link_button") if "contact_" in b.proto.id]


class TestBoutonDeSoutien:
    """Le bouton de soutien renvoie vers la page Buy Me a Coffee du projet."""

    URL = "https://buymeacoffee.com/johan_mac"

    def test_tous_les_boutons_pointent_vers_la_bonne_page(self, app, csv_sale):
        """Où qu'il apparaisse, le bouton renvoie vers la même page, en https."""
        app = _apres_nettoyage(app, csv_sale, ecreter=True, combler=True)
        liens = _boutons_soutien(app)
        assert liens, "Au moins un bouton de soutien devrait être affiché"
        for lien in liens:
            assert "Soutenir" in lien.proto.label
            assert lien.proto.url == self.URL

    def test_present_dans_la_barre_et_sur_l_accueil(self, app):
        """Dès l'arrivée : barre latérale, présentation et onglet Téléchargements."""
        app.run()
        assert len(_boutons_soutien(app.sidebar)) == 1
        assert len(_boutons_soutien(app.tabs[0])) == 1
        textes = " ".join(m.value for m in app.markdown)
        assert "Un coup de pouce" in textes

    def test_coup_de_pouce_sous_les_telechargements_sans_fichier(self, app):
        """Même sans fichier, l'onglet Téléchargements propose retours et soutien."""
        app.run()
        onglet = [o for o in app.tabs if "Téléchargements" in o.label][0]
        assert len(_boutons_soutien(onglet)) == 1
        textes = " ".join(m.value for m in onglet.markdown)
        assert "Un coup de pouce" in textes
        assert "remarque constructive ou anomalie" in textes
        # Pas de remerciement tant que rien n'a été fait.
        assert "Merci d'avoir utilisé" not in textes

    def test_coup_de_pouce_apres_analyse_seule(self, app, csv_sale):
        """Fichier chargé mais pas encore analysé : le bloc reste présent."""
        app.run()
        app = _deposer(app, csv_sale, "sale.csv")
        onglet = [o for o in app.tabs if "Téléchargements" in o.label][0]
        assert len(_boutons_soutien(onglet)) == 1

    def test_present_dans_l_onglet_presentation(self, app, csv_sale):
        """Une fois un fichier chargé, la présentation garde son bouton."""
        app.run()
        app = _deposer(app, csv_sale, "sale.csv")
        assert len(_boutons_soutien(app.tabs[0])) == 1

    def test_present_sous_les_telechargements(self, app, csv_sale):
        """L'onglet Téléchargements se termine par un merci et le bouton."""
        app = _apres_nettoyage(app, csv_sale, ecreter=True, combler=True)
        onglet = [o for o in app.tabs if "Téléchargements" in o.label][0]
        assert len(_boutons_soutien(onglet)) == 1
        textes = " ".join(m.value for m in onglet.markdown)
        assert "Merci d'avoir utilisé Quitus" in textes

    def test_bloc_contact_sur_l_accueil(self, app):
        """La présentation invite aux retours, avec les boutons de contact."""
        app.run()
        textes = " ".join(m.value for m in app.markdown)
        assert "remarque constructive ou anomalie" in textes
        assert "johan-mac-59/quitus/issues" in textes
        urls = [b.proto.url for b in _boutons_contact(app.tabs[0])]
        assert urls == ["https://github.com/johan-mac-59",
                        "https://www.linkedin.com/in/johan-machu/"]

    def test_bloc_contact_sous_les_telechargements(self, app, csv_sale):
        """L'onglet Téléchargements invite aussi aux retours."""
        app = _apres_nettoyage(app, csv_sale, ecreter=True, combler=True)
        onglet = [o for o in app.tabs if "Téléchargements" in o.label][0]
        textes = " ".join(m.value for m in onglet.markdown)
        assert "remarque constructive ou anomalie" in textes
        assert "johan-mac-59/quitus/issues" in textes

    def test_contact_distinct_du_signalement(self, app):
        """GitHub et LinkedIn ne partagent pas la ligne du signalement d'anomalie."""
        app.run()
        for m in app.markdown:
            if "johan-mac-59/quitus/issues" in m.value:
                assert "linkedin" not in m.value and "(https://github.com/johan-mac-59)" not in m.value

    def test_contact_en_fin_de_presentation_et_de_telechargements(self, app, csv_sale):
        """« Me contacter » clôt la présentation et l'onglet Téléchargements."""
        app = _apres_nettoyage(app, csv_sale, ecreter=True, combler=True)
        for nom in ("Présentation", "Téléchargements"):
            onglet = [o for o in app.tabs if nom in o.label][0]
            textes = [m.value for m in onglet.markdown]
            assert "Me contacter" in textes[-1], nom
            contact = _boutons_contact(onglet)
            assert [b.proto.label for b in contact] == ["💻 GitHub", "💼 LinkedIn"], nom
            assert onglet.get("link_button")[-1].proto.id == contact[-1].proto.id, nom

    def test_avertissement_confidentialite_des_signalements(self, app):
        """Les signalements étant publics, on déconseille d'y joindre ses données."""
        app.run()
        legendes = " ".join(c.value for c in app.caption)
        assert "ne publiez jamais votre fichier de données" in legendes

    def test_boutons_agrandis_de_20_pourcent(self, app):
        """Le style qui agrandit les boutons de soutien est bien injecté.

        Le rendu visuel ne se teste pas sans navigateur ; on vérifie que la
        règle est émise, et qu'elle cible le préfixe des clés de ces boutons.
        """
        app.run()
        styles = " ".join(e.proto.body for e in app.get("html"))
        assert 'st-key-soutien_' in styles
        assert 'st-key-contact_' in styles
        assert "zoom: 1.2" in styles

    def test_boutons_colores_lisibles_dans_les_deux_themes(self, app):
        """Soutien, contact et dépôt portent leurs couleurs, GitHub s'inverse en sombre.

        Le rendu a été vérifié dans Chrome, en thème clair puis sombre ; on
        s'assure ici que les règles restent émises.
        """
        app.run()
        styles = " ".join(e.proto.body for e in app.get("html"))
        assert "#FFDD00" in styles              # Buy Me a Coffee
        assert "#0A66C2" in styles              # LinkedIn
        assert "light-dark(#24292F, #F0F6FC)" in styles  # GitHub, selon le thème
        assert "stFileUploaderDropzone" in styles and "#3DDC97" in styles

    def test_cles_des_boutons_commencent_par_soutien_ou_contact(self, app, csv_sale):
        """Le style repose sur ces préfixes : tout bouton-lien doit porter l'un d'eux."""
        import streamlit_app

        assert "soutien_" in streamlit_app.STYLE_BOUTONS_SOUTIEN
        assert "contact_" in streamlit_app.STYLE_BOUTONS_SOUTIEN
        app = _apres_nettoyage(app, csv_sale, ecreter=True, combler=True)
        liens = app.get("link_button")
        assert liens
        for lien in liens:
            # L'identifiant d'un widget à clé embarque cette clé.
            assert "soutien_" in lien.proto.id or "contact_" in lien.proto.id, (
                f"bouton sans clé « soutien_… » ni « contact_… » : "
                f"il ne serait pas agrandi ({lien.proto.id})"
            )

    def test_message_facultatif(self, app):
        """Le message ne culpabilise pas : le soutien est dit facultatif."""
        app.run()
        textes = " ".join(m.value for m in app.markdown)
        assert "facultatif" in textes

    def test_confidentialite_mentionne_le_prestataire(self, app):
        """L'encart de confidentialité explique où se fait le paiement."""
        app.run()
        textes = " ".join(m.value for m in app.markdown)
        assert "Buy Me a Coffee" in textes
        assert "aucune donnée de paiement" in textes


class TestPageAccueil:
    """La page d'accueil présente le projet et permet de l'essayer sans fichier."""

    def test_presente_le_projet(self, app):
        """Le parcours, les principes et l'histoire sont présentés."""
        app.run()
        textes = " ".join(m.value for m in app.markdown)
        assert "Comment ça marche" in textes
        assert "Trois principes" in textes
        assert any("histoire du projet" in e.label for e in app.expander)

    def test_montre_des_exemples_concrets(self, app):
        """Un tableau avant / après illustre ce que l'outil corrige."""
        app.run()
        assert len(app.dataframe) >= 1

    def test_onglets_visibles_des_l_arrivee(self, app):
        """Les huit onglets sont là avant tout dépôt, Présentation en premier.

        Sans fichier, la page d'accueil n'avait pas d'onglets : après un
        relancement du serveur, on croyait qu'ils avaient disparu.
        """
        app.run()
        assert not app.exception
        assert len(app.tabs) == 8
        assert app.tabs[0].label == "🏠 Présentation"
        textes = " ".join(m.value for m in app.tabs[0].markdown)
        assert "Trois principes" in textes

    def test_onglets_sans_fichier_invitent_a_deposer(self, app):
        """Avant tout dépôt, les autres onglets expliquent quoi faire."""
        app.run()
        for onglet in app.tabs[1:]:
            messages = " ".join(i.value for i in onglet.info)
            assert "une fois un fichier chargé" in messages, onglet.label

    def test_encart_confidentialite_une_seule_fois(self, app):
        """L'encart de confidentialité n'apparaît qu'une fois, en bas de page."""
        app.run()
        encarts = [e for e in app.expander if "Confidentialité" in e.label]
        assert len(encarts) == 1

    def test_presentation_reste_visible_apres_depot(self, app, csv_sale):
        """Une fois un fichier chargé, la présentation occupe le premier onglet."""
        app.run()
        app = _deposer(app, csv_sale, "sale.csv")
        assert app.tabs[0].label == "🏠 Présentation"
        textes = " ".join(m.value for m in app.tabs[0].markdown)
        assert "Trois principes" in textes

    def test_pas_de_bouton_d_essai_une_fois_un_fichier_charge(self, app, csv_sale):
        """Le bouton d'essai disparaît : il remplacerait le fichier en cours."""
        app.run()
        app = _deposer(app, csv_sale, "sale.csv")
        assert not any("exemple" in b.label.lower() for b in app.button)

    @pytest.mark.skipif(not ECHANTILLON.exists(), reason="échantillon versionné absent")
    def test_bouton_exemple_propose(self, app):
        """Le bouton d'essai est offert dès l'arrivée."""
        app.run()
        assert any("exemple" in b.label.lower() for b in app.button)

    @pytest.mark.skipif(not ECHANTILLON.exists(), reason="échantillon versionné absent")
    def test_l_exemple_se_charge_sans_fichier(self, app):
        """Un clic suffit pour explorer l'outil, sans rien déposer."""
        app.run()
        bouton = [b for b in app.button if "exemple" in b.label.lower()][0]
        app = bouton.click().run()
        assert not app.exception
        assert len(app.session_state["df_brut"]) == 312
        assert app.session_state["nom_source"] == ECHANTILLON.name
        # Un bandeau signale qu'on explore l'exemple, et comment en sortir.
        assert any("exemple fourni" in i.value for i in app.info)

    @pytest.mark.skipif(not ECHANTILLON.exists(), reason="échantillon versionné absent")
    def test_parcours_complet_sur_l_exemple(self, app):
        """L'exemple se profile et se nettoie comme un fichier déposé."""
        app.run()
        app = [b for b in app.button if "exemple" in b.label.lower()][0].click().run()
        app = [b for b in app.sidebar.button if "Analyser" in b.label][0].click().run()
        nettoyer = [b for b in app.sidebar.button if "Nettoyer" in b.label]
        app = nettoyer[0].click().run()
        assert not app.exception
        assert app.session_state["df_propre"] is not None
        # Sur l'exemple, l'invariant doit tenir : aucune colonne mal typée.
        assert any("correctement typées" in s.value for s in app.success)


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

        # Étape 2 : choisir toutes les colonnes des deux traitements lourds,
        # puis nettoyer
        for liste in app.sidebar.multiselect:
            _choisir(liste, None)
        boutons = [b for b in app.sidebar.button if "Nettoyer" in b.label]
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

    def test_les_graphiques_montrent_d_abord_le_fichier_nettoye(self, app, csv_sale):
        """Une fois nettoyé, le jeu affiché par défaut est le fichier nettoyé."""
        app = _apres_nettoyage(app, csv_sale, ecreter=False, combler=False)
        jeu = [r for r in app.radio if r.label == "Jeu de données"]
        assert jeu and jeu[0].value == "Données nettoyées"

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
        """Le fichier nettoyé et tous les rapports sont offerts au téléchargement."""
        app = _apres_nettoyage(app, csv_sale, ecreter=True, combler=True)
        cles = {b.key for b in app.download_button}
        assert "dl_csv" in cles
        assert "dl_rapport_nettoyage" in cles
        # Profilage avant ET après nettoyage, chacun en HTML et en Markdown.
        for prefixe in ("profilage_avant", "profilage_apres"):
            assert f"dl_{prefixe}_html" in cles
            assert f"dl_{prefixe}_md" in cles

    def test_le_rapport_de_profilage_est_telechargeable_des_l_analyse(self, app, csv_sale):
        """Le rapport avant nettoyage est proposé là où on le consulte, dès l'analyse."""
        app.run()
        app = _deposer(app, csv_sale, "sale.csv")
        app = [b for b in app.sidebar.button if "Analyser" in b.label][0].click().run()
        cles = {b.key for b in app.download_button}
        assert "dl_profilage_avant_html" in cles
        assert "dl_profilage_avant_md" in cles
        # Rien de ce qui dépend du nettoyage n'est encore proposé.
        assert "dl_csv" not in cles

    def test_formulaire_reduit_aux_deux_decisions(self, app, csv_sale):
        """Seules les deux décisions qui altèrent les valeurs sont demandées.

        Le nombre de passes, le choix des rapports et l'enregistrement sur le
        serveur ont été retirés : le premier est géré par le moteur, le second
        par les boutons de téléchargement, le troisième n'a pas de sens en ligne.
        """
        app.run()
        app = _deposer(app, csv_sale, "sale.csv")
        app = [b for b in app.sidebar.button if "Analyser" in b.label][0].click().run()
        libelles = [m.label for m in app.sidebar.multiselect]
        assert len(libelles) == 2
        assert any("Écrêter" in lib for lib in libelles)
        assert any("Combler" in lib for lib in libelles)
        assert len(app.sidebar.checkbox) == 0
        assert len(app.sidebar.number_input) == 0

    def test_chaque_decision_propose_ses_colonnes(self, app, csv_sale):
        """Chaque traitement propose les colonnes concernées, avec leur nombre."""
        app.run()
        app = _deposer(app, csv_sale, "sale.csv")
        app = [b for b in app.sidebar.button if "Analyser" in b.label][0].click().run()
        ecreter, combler = _listes(app)
        # Les montants, encore en texte, ne révèlent leurs extrêmes qu'après
        # correction des types : ils doivent être proposés quand même.
        assert [_colonne(o) for o in ecreter.options] == ["montant"]
        assert [_colonne(o) for o in combler.options] == ["note"]
        # Cinq notes absentes, plus une dans la ligne dupliquée.
        assert combler.options[0] == "note (6)"
        # Rien n'est choisi d'office.
        assert ecreter.value == [] and combler.value == []

    def test_un_seuil_par_colonne_choisie(self, app, csv_sale):
        """Chaque colonne choisie reçoit son curseur de seuil et son décompte."""
        app.run()
        app = _deposer(app, csv_sale, "sale.csv")
        app = [b for b in app.sidebar.button if "Analyser" in b.label][0].click().run()
        assert len(app.sidebar.slider) == 0

        ecreter, _ = _listes(app)
        _choisir(ecreter, ["montant"])
        app = app.run()
        assert [s.label for s in app.sidebar.slider] == ["Seuil IQR · montant"]
        assert app.sidebar.slider[0].value == 1.5
        assert any("hors bornes à ce seuil" in c.value for c in app.sidebar.caption)

    def test_le_seuil_choisi_est_applique(self, app):
        """Un seuil tolérant épargne un extrême modéré, pas un extrême massif."""
        valeurs = [100, 101, 102, 103, 104, 105, 106, 102, 103, 120, 900]
        contenu = ("a;b\n" + "\n".join(f"{v};{v}" for v in valeurs)).encode("utf-8")
        app.run()
        app = _deposer(app, contenu, "seuils.csv")
        app = [b for b in app.sidebar.button if "Analyser" in b.label][0].click().run()
        ecreter, _ = _listes(app)
        _choisir(ecreter, ["a", "b"])
        app = app.run()
        [s for s in app.sidebar.slider if s.label.endswith("· a")][0].set_value(5.0)
        app = app.run()
        app = [b for b in app.sidebar.button if "Nettoyer" in b.label][0].click().run()
        assert not app.exception

        propre = app.session_state["df_propre"]
        assert 120 in propre["a"].tolist() and propre["a"].max() < 900
        assert 120 not in propre["b"].tolist()
        assert app.session_state["stats"]["outlier_thresholds"] == {"a": 5.0, "b": 1.5}

    def test_notes_ramenees_signalees(self, app):
        """Des notes sur plusieurs échelles sont ramenées, et l'onglet le dit."""
        notes = ["17/20", "4/5", "12/20", "15/20", "3/5", "18/20"]
        contenu = ("id;note\n" + "\n".join(f"{i};{n}" for i, n in enumerate(notes))).encode("utf-8")
        app = _apres_nettoyage(app, contenu, ecreter=False, combler=False)
        assert not app.exception
        assert app.session_state["df_propre"]["note"].tolist() == [17, 16, 12, 15, 12, 18]
        assert any("échelle commune" in i.value for i in app.info)

    def test_seules_les_colonnes_choisies_sont_traitees(self, app):
        """Une colonne non choisie garde ses extrêmes et ses absences."""
        lignes = ["a;b;c;d"]
        for i in range(40):
            extreme = i % 13 == 0
            lignes.append(";".join([
                str(9000 if extreme else 100 + i % 7),
                str(9000 if extreme else 100 + i % 7),
                "" if i % 9 == 0 else str(i % 5),
                "" if i % 9 == 0 else str(i % 5),
            ]))
        contenu = "\n".join(lignes).encode("utf-8")
        app = _apres_nettoyage(app, contenu, ecreter=["a"], combler=["c"])
        assert not app.exception

        propre = app.session_state["df_propre"]
        assert propre["a"].max() < 9000
        assert propre["b"].max() == 9000
        assert propre["c"].isna().sum() == 0
        assert propre["d"].isna().sum() == 5

        stats = app.session_state["stats"]
        assert set(stats["outliers_corrected"]) == {"a"}
        assert set(stats["missing_filled"]) == {"c"}

    def test_onglet_telechargements_present(self, app, csv_sale):
        """L'onglet récapitulatif des téléchargements existe."""
        app.run()
        app = _deposer(app, csv_sale, "sale.csv")
        assert any("Téléchargements" in o.label for o in app.tabs)

    def test_recapitulatif_apres_analyse(self, app, csv_sale):
        """Après l'analyse seule, le récapitulatif ne propose que le rapport avant."""
        app.run()
        app = _deposer(app, csv_sale, "sale.csv")
        app = [b for b in app.sidebar.button if "Analyser" in b.label][0].click().run()
        cles = {b.key for b in app.download_button}
        assert "dl_profilage_avant_recap_html" in cles
        assert "dl_profilage_avant_recap_md" in cles
        assert "dl_csv_recap" not in cles

    def test_recapitulatif_apres_nettoyage(self, app, csv_sale):
        """Après le nettoyage, le récapitulatif réunit tous les fichiers.

        Les mêmes boutons restent aussi proposés dans leur onglet respectif :
        les clés doivent donc être distinctes, sans quoi Streamlit lèverait
        une erreur de clé dupliquée.
        """
        app = _apres_nettoyage(app, csv_sale, ecreter=True, combler=True)
        assert not app.exception
        cles = {b.key for b in app.download_button}
        for cle in ("dl_csv_recap", "dl_rapport_nettoyage_recap",
                    "dl_profilage_avant_recap_html", "dl_profilage_avant_recap_md",
                    "dl_profilage_apres_recap_html", "dl_profilage_apres_recap_md"):
            assert cle in cles, f"{cle} manquant dans le récapitulatif"
        # Les boutons contextuels subsistent.
        assert "dl_csv" in cles

    def test_horodatages_poses_a_chaque_etape(self, app, csv_sale):
        """L'analyse et le nettoyage posent chacun leur marque de nommage."""
        import re

        motif = re.compile(r"^\d{8}_\d{6}$")
        app = _apres_nettoyage(app, csv_sale, ecreter=True, combler=True)
        assert motif.match(app.session_state["horodatage_analyse"])
        assert motif.match(app.session_state["horodatage_nettoyage"])

    def test_nouveau_fichier_efface_les_horodatages(self, app, csv_sale):
        """Un nouveau dépôt repart sans marque : elles appartiennent à l'ancien fichier."""
        app = _apres_nettoyage(app, csv_sale, ecreter=True, combler=True)
        app = _deposer(app, b"z\n1\n2\n", "autre.csv")
        assert app.session_state["horodatage_analyse"] is None
        assert app.session_state["horodatage_nettoyage"] is None

    def test_ouvrir_un_rapport_en_grand(self, app, csv_sale):
        """Le bouton « Ouvrir en grand » ouvre le rapport sans erreur."""
        app.run()
        app = _deposer(app, csv_sale, "sale.csv")
        app = [b for b in app.sidebar.button if "Analyser" in b.label][0].click().run()
        bouton = [b for b in app.button if b.key == "fenetre_profilage_avant"]
        assert bouton, "Le bouton d'ouverture en grand devrait être proposé"
        app = bouton[0].click().run()
        assert not app.exception

    def test_controle_apres_nettoyage(self, app, csv_sale):
        """Le profil de contrôle est calculé d'office après le nettoyage."""
        app = _apres_nettoyage(app, csv_sale, ecreter=True, combler=True)
        assert app.session_state["profil_post"] is not None
        textes = [s.value for s in app.success]
        assert any("correctement typées" in t for t in textes)

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
    """Tous les formats annoncés doivent fonctionner via l'interface."""

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

    def test_parquet(self, app):
        """Un fichier Parquet déposé est chargé, puis profilé sans erreur.

        Ses cellules structurées (liste, objet) sont écrites en texte JSON : le
        profilage, qui compare des valeurs, échouait sur une liste.
        """
        tampon = io.BytesIO()
        pd.DataFrame({"x": [1, 2, 3], "tags": [["a"], ["b", "c"], []],
                      "tel": ["0612345678", "0798765432", "0601020304"]}).to_parquet(tampon)
        app.run()
        app = _deposer(app, tampon.getvalue(), "donnees.parquet")
        assert not app.exception
        df = app.session_state["df_brut"]
        assert df["tags"].tolist() == ['["a"]', '["b", "c"]', "[]"]
        app = [b for b in app.sidebar.button if "Analyser" in b.label][0].click().run()
        assert not app.exception
        assert app.session_state["profil"] is not None

    def test_extension_parquet_acceptee(self, app):
        """Le composant de dépôt accepte l'extension .parquet."""
        app.run()
        envoi = app.file_uploader(key=f"envoi_{app.session_state['generation_envoi']}")
        assert "parquet" in envoi.proto.type or ".parquet" in envoi.proto.type

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

def _colonne(option: str) -> str:
    """Retrouve le nom de colonne d'une option affichée « nom (nombre) ».

    Args:
        option: Libellé de l'option, tel que la liste l'affiche.

    Returns:
        Le nom de la colonne.
    """
    return option.rsplit(" (", 1)[0]


def _listes(app):
    """Retourne les listes de colonnes des deux traitements.

    Args:
        app: Application après analyse.

    Returns:
        Le couple (liste d'écrêtage, liste de remplissage).
    """
    listes = {m.label: m for m in app.sidebar.multiselect}
    return (next(m for lib, m in listes.items() if "Écrêter" in lib),
            next(m for lib, m in listes.items() if "Combler" in lib))


def _choisir(liste, colonnes) -> None:
    """Choisit des colonnes dans la liste d'un traitement.

    Args:
        liste: Liste de colonnes (multiselect) du traitement.
        colonnes: Colonnes à choisir ; None pour toutes celles proposées.
    """
    if colonnes is None:
        colonnes = [_colonne(o) for o in liste.options]
    # Une liste sans colonne à proposer est désactivée : rien à y choisir.
    if colonnes or not liste.disabled:
        liste.set_value(list(colonnes))


def _apres_nettoyage(app, contenu: bytes, *, ecreter, combler):
    """Déroule le parcours complet jusqu'au nettoyage inclus.

    Args:
        app: Instance d'AppTest vierge.
        contenu: Octets du fichier à déposer.
        ecreter: Colonnes à écrêter : True pour toutes celles proposées,
            False pour aucune, ou une liste de noms.
        combler: Colonnes à combler, sur le même modèle.

    Returns:
        L'application après nettoyage.
    """
    app.run()
    app = _deposer(app, contenu, "donnees.csv")

    analyse = [b for b in app.sidebar.button if "Analyser" in b.label]
    app = analyse[0].click().run()

    for liste, choix in zip(_listes(app), (ecreter, combler)):
        _choisir(liste, None if choix is True else (choix or []))

    nettoyer = [b for b in app.sidebar.button if "Nettoyer" in b.label]
    return nettoyer[0].click().run()


class TestCacheCible:
    """L'effacement ne retire du cache partagé que les calculs de la session.

    Le cache de Streamlit est commun à tous les visiteurs : le vider en bloc
    obligerait les autres à tout recalculer. On compte ici les constructions de
    profileur pour savoir si un appel a été servi par le cache ou recalculé.
    """

    @pytest.fixture
    def compteur(self, monkeypatch):
        import streamlit_app

        appels = []

        class ProfileurCompte(streamlit_app.PreCleaningProfiler):
            def __init__(self, *args, **kwargs):
                appels.append(1)
                super().__init__(*args, **kwargs)

        monkeypatch.setattr(streamlit_app, "PreCleaningProfiler", ProfileurCompte)
        streamlit_app.profiler.clear()
        streamlit_app.rendre_rapport.clear()
        yield appels
        streamlit_app.profiler.clear()
        streamlit_app.rendre_rapport.clear()

    def test_purge_ne_touche_que_les_donnees_visees(self, compteur):
        """Mes entrées disparaissent, celles d'un autre visiteur restent."""
        import streamlit_app

        mien = pd.DataFrame({"prix": [1.0, 2.0, 3.0]})
        autre = pd.DataFrame({"prix": [7.0, 8.0, 9.0]})
        for df in (mien, autre):
            streamlit_app.profiler(df, exploratoire=False)
            streamlit_app.rendre_rapport(df, False, "md")
        assert len(compteur) == 4

        streamlit_app.purger_cache(mien)

        streamlit_app.profiler(autre, exploratoire=False)
        streamlit_app.rendre_rapport(autre, False, "md")
        assert len(compteur) == 4, "les calculs de l'autre visiteur doivent rester en cache"

        streamlit_app.profiler(mien, exploratoire=False)
        streamlit_app.rendre_rapport(mien, False, "md")
        assert len(compteur) == 6, "mes calculs doivent avoir été retirés du cache"

    def test_purge_ignore_l_absence_de_donnees(self, compteur):
        """Rien à purger (aucun fichier, jamais calculé) : aucune erreur."""
        import streamlit_app

        streamlit_app.purger_cache(None, pd.DataFrame({"x": [1]}))

    def test_plus_aucun_vidage_global(self):
        """L'application ne vide plus jamais le cache de tout le monde."""
        source = (RACINE / "streamlit_app.py").read_text(encoding="utf-8")
        assert "st.cache_data.clear()" not in source

    def test_le_fichier_depose_n_est_pas_mis_en_cache(self):
        """Le chargement, dont la clé serait le fichier brut, reste hors cache."""
        import streamlit_app

        assert not hasattr(streamlit_app.charger, "clear")


class TestGuideTelechargements:
    """L'onglet Téléchargements explique chaque partie et chaque document."""

    def test_introduction_et_legendes(self, app, csv_sale):
        app = _apres_nettoyage(app, csv_sale, ecreter=True, combler=True)
        onglet = [o for o in app.tabs if "Téléchargements" in o.label][0]
        textes = " ".join(m.value for m in onglet.markdown)
        legendes = " ".join(c.value for c in onglet.caption)
        assert "Tout ce que Quitus a produit" in textes
        for attendu in ("Le résultat", "Le constat de départ", "La vérification"):
            assert attendu in legendes, attendu
        # Un nouveau nettoyage remplace le précédent : la page ne doit pas
        # laisser croire qu'elle accumule les essais.
        assert "dernier nettoyage" in legendes

    def test_chaque_telechargement_a_une_infobulle(self, app, csv_sale):
        app = _apres_nettoyage(app, csv_sale, ecreter=True, combler=True)
        boutons = app.get("download_button")
        assert boutons
        for bouton in boutons:
            assert bouton.proto.help, f"sans infobulle : {bouton.proto.label}"


class TestRelanceDuNettoyage:
    """Relancer un nettoyage identique est inutile : le bouton s'éteint et le dit."""

    def test_bouton_eteint_apres_nettoyage_avec_confirmation(self, app, csv_sale):
        app = _apres_nettoyage(app, csv_sale, ecreter=False, combler=False)
        bouton = [b for b in app.sidebar.button if "Nettoyer" in b.label][0]
        assert bouton.disabled
        assert any("Nettoyage effectué" in s.value for s in app.sidebar.success)

    def test_bouton_rallume_quand_les_choix_changent(self, app, csv_sale):
        app = _apres_nettoyage(app, csv_sale, ecreter=False, combler=False)
        liste = next(m for m in app.sidebar.multiselect
                     if m.label.startswith("Combler"))
        _choisir(liste, None)
        app = app.run()
        bouton = [b for b in app.sidebar.button if "Nettoyer" in b.label][0]
        assert not bouton.disabled


# --------------------------------------------------------------------------
# Onglet « Contraintes »
# --------------------------------------------------------------------------

def _onglet_contraintes(app):
    """Retourne l'onglet « Contraintes » de l'application.

    Args:
        app: Application exécutée.

    Returns:
        L'onglet.
    """
    return [o for o in app.tabs if "Contraintes" in o.label][0]


def _cles(app, type_widget: str) -> set:
    """Liste les clés des widgets d'un type, pour vérifier qu'ils sont affichés ou non.

    Args:
        app: Application exécutée.
        type_widget: Type de widget (`"selectbox"`, `"text_input"`…).

    Returns:
        L'ensemble des clés présentes.
    """
    return {w.key for w in app.get(type_widget)}


def _ajouter_plage(app, colonne: str = "montant", **bornes):
    """Ajoute une contrainte de plage par le formulaire de l'onglet.

    Args:
        app: Application après nettoyage.
        colonne: Colonne visée.
        **bornes: Bornes saisies (`min`, `max`), en texte.

    Returns:
        L'application après l'ajout.
    """
    generation = app.session_state["generation_regles"]
    app.selectbox(key=f"regle_{generation}_type").set_value("plage").run()
    app.selectbox(key=f"regle_{generation}_col").set_value(colonne)
    for nom, valeur in bornes.items():
        app.text_input(key=f"regle_{generation}_plage_{nom}").set_value(valeur)
    return app.button(key=f"regle_{generation}_ajouter").click().run()


@pytest.fixture
def app_nettoyee(app, csv_sale):
    """Application après un nettoyage sans écrêtage : les montants extrêmes restent."""
    return _apres_nettoyage(app, csv_sale, ecreter=False, combler=False)


class TestOngletContraintes:
    """L'onglet Contraintes : saisie, verdict, import et export, sans rien écrire."""

    def test_avant_nettoyage_l_onglet_invite_a_nettoyer(self, app, csv_sale):
        app.run()
        app = _deposer(app, csv_sale, "donnees.csv")
        onglet = _onglet_contraintes(app)
        assert any("Lancez le nettoyage" in i.value for i in onglet.info)
        assert not app.get("selectbox") or "regle_0_type" not in _cles(app, "selectbox")

    def test_apres_nettoyage_le_formulaire_est_propose(self, app_nettoyee):
        onglet = _onglet_contraintes(app_nettoyee)
        legendes = " ".join(c.value for c in onglet.caption)
        assert "Il ne corrige rien" in legendes
        assert "Aucune contrainte pour l'instant" in legendes
        assert "regle_0_type" in _cles(app_nettoyee, "selectbox")

    def test_ajouter_une_contrainte_la_signale_sans_rien_corriger(self, app_nettoyee):
        propre_avant = app_nettoyee.session_state["df_propre"].copy()
        app = _ajouter_plage(app_nettoyee, "montant", max="500")
        assert not app.exception

        regles = app.session_state["regles"]
        assert len(regles) == 1 and regles[0]["parametres"] == {"max": 500}
        attendu = int((propre_avant["montant"] > 500).sum())
        assert attendu > 0
        assert app.session_state["contraintes"]["apres"]["total_violations"] == attendu
        # Le fichier nettoyé n'a pas bougé : on signale, on ne corrige pas.
        pd.testing.assert_frame_equal(app.session_state["df_propre"], propre_avant)

        onglet = _onglet_contraintes(app)
        assert any("enfreignent encore" in w.value for w in onglet.warning)
        assert any("Contrainte ajoutée" in s.value for s in onglet.success)

    def test_les_champs_sont_vides_apres_un_ajout(self, app_nettoyee):
        app = _ajouter_plage(app_nettoyee, "montant", max="500")
        assert app.session_state["generation_regles"] == 1
        assert app.text_input(key="regle_1_plage_max").value == ""

    def test_une_saisie_invalide_est_expliquee_et_n_ajoute_rien(self, app_nettoyee):
        app = _ajouter_plage(app_nettoyee, "montant")  # aucune borne
        assert app.session_state["regles"] == []
        assert any("minimum ou un maximum" in e.value for e in _onglet_contraintes(app).error)

    def test_une_contrainte_deja_presente_n_est_pas_doublee(self, app_nettoyee):
        app = _ajouter_plage(app_nettoyee, "montant", max="500")
        app = _ajouter_plage(app, "montant", max="500")
        assert len(app.session_state["regles"]) == 1
        assert any("déjà dans la liste" in w.value for w in _onglet_contraintes(app).warning)

    def test_supprimer_une_contrainte(self, app_nettoyee):
        app = _ajouter_plage(app_nettoyee, "montant", max="500")
        identifiant = app.session_state["regles"][0]["id"]
        app = app.button(key=f"suppr_regle_{identifiant}").click().run()
        assert app.session_state["regles"] == []
        assert app.session_state["contraintes"] is None

    def test_le_formulaire_suit_le_type_choisi(self, app_nettoyee):
        app = app_nettoyee
        app.selectbox(key="regle_0_type").set_value("comparaison_colonnes").run()
        cles = _cles(app, "selectbox")
        assert {"regle_0_col1", "regle_0_col2", "regle_0_comparaison_colonnes_operateur"} <= cles
        app.selectbox(key="regle_0_type").set_value("unique").run()
        assert "regle_0_cols" in _cles(app, "multiselect")
        assert "regle_0_col1" not in _cles(app, "selectbox")

    def test_motif_masque_quand_un_format_connu_est_choisi(self, app_nettoyee):
        app = app_nettoyee
        app.selectbox(key="regle_0_type").set_value("format").run()
        assert "regle_0_format_motif" in _cles(app, "text_input")
        app.selectbox(key="regle_0_format_nom").set_value("email").run()
        assert "regle_0_format_motif" not in _cles(app, "text_input")

    def test_unicite_sur_une_colonne(self, app_nettoyee):
        app = app_nettoyee
        app.selectbox(key="regle_0_type").set_value("unique").run()
        app.multiselect(key="regle_0_cols").set_value(["ville"])
        app = app.button(key="regle_0_ajouter").click().run()
        regle = app.session_state["regles"][0]
        assert regle["type"] == "unique" and regle["colonnes"] == ["ville"]
        assert app.session_state["contraintes"]["apres"]["total_violations"] > 0

    def test_comparaison_de_deux_colonnes(self, app_nettoyee):
        app = app_nettoyee
        app.selectbox(key="regle_0_type").set_value("comparaison_colonnes").run()
        app.selectbox(key="regle_0_col1").set_value("id")
        app.selectbox(key="regle_0_col2").set_value("ville")
        app.selectbox(key="regle_0_comparaison_colonnes_operateur").set_value("!=")
        app = app.button(key="regle_0_ajouter").click().run()
        assert app.session_state["regles"][0]["colonnes"] == ["id", "ville"]

    def test_la_contrainte_figure_dans_le_rapport_de_nettoyage(self, app_nettoyee):
        app = _ajouter_plage(app_nettoyee, "montant", max="500")
        textes = " ".join(m.value for m in app.markdown)
        assert "## 3. Contraintes" in textes
        assert "montant : valeur au plus 500" in textes

    def test_pas_de_section_sans_contrainte(self, app_nettoyee):
        textes = " ".join(m.value for m in app_nettoyee.markdown)
        assert "## 3. Contraintes" not in textes

    def test_relancer_le_nettoyage_recalcule_le_verdict(self, app_nettoyee):
        app = _ajouter_plage(app_nettoyee, "montant", max="500")
        assert app.session_state["contraintes"]["apres"]["total_violations"] > 0
        # Avec écrêtage, les montants extrêmes sont ramenés : la contrainte est respectée.
        _choisir(_listes(app)[0], None)
        app = app.run()
        app = [b for b in app.sidebar.button if "Nettoyer" in b.label][0].click().run()
        assert app.session_state["contraintes"]["apres"]["total_violations"] == 0
        assert any("respecte toutes vos contraintes" in s.value
                   for s in _onglet_contraintes(app).success)

    def test_export_desactive_sans_contrainte_puis_actif(self, app_nettoyee):
        assert app_nettoyee.get("download_button")  # l'export est proposé
        export = [b for b in app_nettoyee.get("download_button") if b.proto.label.endswith("(JSON)")]
        assert export and export[0].proto.disabled
        app = _ajouter_plage(app_nettoyee, "montant", max="500")
        export = [b for b in app.get("download_button") if b.proto.label.endswith("(JSON)")]
        assert export and not export[0].proto.disabled
        assert all(b.proto.help for b in export)

    def test_l_export_est_aussi_dans_telechargements(self, app_nettoyee):
        app = _ajouter_plage(app_nettoyee, "montant", max="500")
        onglet = [o for o in app.tabs if "Téléchargements" in o.label][0]
        legendes = " ".join(c.value for c in onglet.caption)
        assert "Vos contraintes" in legendes
        assert "dl_regles_recap" in {b.key for b in app.get("download_button")}

    def test_import_d_un_fichier_de_regles(self, app_nettoyee):
        from src.validator import nouvelle_regle, regles_vers_texte
        texte = regles_vers_texte([nouvelle_regle("plage", "montant", {"max": 500}),
                                   nouvelle_regle("non_vide", "ville")])
        app = app_nettoyee
        envoi = [u for u in app.get("file_uploader") if "Importer" in u.label][0]
        envoi.upload("regles.json", texte.encode("utf-8"), "application/json")
        app = app.run()
        assert [r["type"] for r in app.session_state["regles"]] == ["plage", "non_vide"]
        assert any("2 contrainte(s) importée(s)" in s.value for s in _onglet_contraintes(app).success)

    def test_import_ignore_les_regles_deja_presentes(self, app_nettoyee):
        from src.validator import regles_vers_texte
        app = _ajouter_plage(app_nettoyee, "montant", max="500")
        texte = regles_vers_texte(app.session_state["regles"])
        envoi = [u for u in app.get("file_uploader") if "Importer" in u.label][0]
        envoi.upload("regles.json", texte.encode("utf-8"), "application/json")
        app = app.run()
        assert len(app.session_state["regles"]) == 1
        assert any("déjà présente" in s.value for s in _onglet_contraintes(app).success)

    def test_import_invalide_est_refuse_clairement(self, app_nettoyee):
        envoi = [u for u in app_nettoyee.get("file_uploader") if "Importer" in u.label][0]
        envoi.upload("regles.json", b'{"regles": [{"type": "zzz"}]}', "application/json")
        app = app_nettoyee.run()
        assert app.session_state["regles"] == []
        assert any("Import impossible" in e.value and "n° 1" in e.value
                   for e in _onglet_contraintes(app).error)

    def test_import_d_un_fichier_qui_n_est_pas_du_json(self, app_nettoyee):
        envoi = [u for u in app_nettoyee.get("file_uploader") if "Importer" in u.label][0]
        envoi.upload("regles.json", "pas du json".encode("utf-8"), "application/json")
        app = app_nettoyee.run()
        assert app.session_state["regles"] == []
        assert any("Import impossible" in e.value for e in _onglet_contraintes(app).error)

    def test_une_regle_sur_une_colonne_absente_est_signalee(self, app_nettoyee):
        from src.validator import nouvelle_regle, regles_vers_texte
        texte = regles_vers_texte([nouvelle_regle("plage", "inexistante", {"min": 0})])
        envoi = [u for u in app_nettoyee.get("file_uploader") if "Importer" in u.label][0]
        envoi.upload("regles.json", texte.encode("utf-8"), "application/json")
        app = app_nettoyee.run()
        onglet = _onglet_contraintes(app)
        assert any("n'ont pas pu être évaluées" in w.value for w in onglet.warning)

    def test_un_nouveau_fichier_efface_les_contraintes(self, app_nettoyee):
        app = _ajouter_plage(app_nettoyee, "montant", max="500")
        assert app.session_state["regles"]
        autre = "id;prix\n1;10\n2;20\n3;30\n".encode("utf-8")
        app = _deposer(app, autre, "autre.csv")
        assert app.session_state["regles"] == []
        assert app.session_state["contraintes"] is None

    def test_effacer_mes_donnees_vide_les_contraintes_et_les_widgets(self, app_nettoyee):
        app = _ajouter_plage(app_nettoyee, "montant", max="500")
        app = [b for b in app.sidebar.button if "Effacer" in b.label][0].click().run()
        assert app.session_state["regles"] == []
        assert app.session_state["contraintes"] is None
        assert app.session_state["generation_regles"] == 0
        # Les clés de widgets de la génération précédente ne survivent pas à l'effacement.
        for cle in ("regle_1_type", "regle_1_col", "regle_1_plage_max", "import_regles_1"):
            assert cle not in app.session_state

    def test_les_sessions_ne_partagent_pas_leurs_contraintes(self, app_nettoyee, csv_sale):
        """La liste initiale est copiée à chaque session : pas d'état partagé."""
        _ajouter_plage(app_nettoyee, "montant", max="500")
        autre = _apres_nettoyage(AppTest.from_file(str(APP), default_timeout=DELAI),
                                 csv_sale, ecreter=False, combler=False)
        assert autre.session_state["regles"] == []

    def test_aucune_ecriture_disque(self, app_nettoyee):
        """Saisie et import n'écrivent rien sur le serveur."""
        from src.validator import nouvelle_regle, regles_vers_texte
        rapports = RACINE / "data" / "reports"
        avant = set(rapports.glob("*")) if rapports.exists() else set()
        app = _ajouter_plage(app_nettoyee, "montant", max="500")
        texte = regles_vers_texte([nouvelle_regle("non_vide", "ville")])
        envoi = [u for u in app.get("file_uploader") if "Importer" in u.label][0]
        envoi.upload("regles.json", texte.encode("utf-8"), "application/json")
        app.run()
        apres = set(rapports.glob("*")) if rapports.exists() else set()
        assert apres == avant
