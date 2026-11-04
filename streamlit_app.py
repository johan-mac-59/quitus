"""Interface web de Quitus, le pipeline de nettoyage automatique de données.

Seconde façade du projet, l'autre étant `main.py` (ligne de commande). Ce
module ne contient **aucune logique de nettoyage** : il se contente de
présenter des widgets, d'en transmettre le résultat aux modules de `src/` sous
forme de paramètres, et d'afficher ce qui revient.

Lancement :
    streamlit run streamlit_app.py

Parcours : chaque étape s'affiche d'abord, et se télécharge ensuite depuis
l'endroit même où on la consulte — le profilage dans son onglet, le fichier
nettoyé et son rapport dans le leur.

Confidentialité : rien n'est jamais écrit sur le serveur. Les fichiers déposés
vivent en mémoire pour la durée de la session et repartent vers le navigateur
via les boutons de téléchargement. Voir `encart_confidentialite()`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import streamlit as st

from src import marque
from src import plot_factory as pf
from src.cleaner_engine import (
    SEUIL_IQR,
    count_outliers,
    find_mistyped_columns,
    run_all_cleaning_steps,
    summarize_missing_values,
    summarize_outliers,
)
from src.cleaner_logger import CleanLogger
from src.cleaner_reporter import CleanerReporter
from src.console_capture import capture_output
from src.data_profiler import ExploratoryProfiler, PreCleaningProfiler
from src.file_loader import load_dataframe
from src.horodatage import horodater
from src.saisie_regles import (
    champs_du_type,
    colonnes_attendues,
    construire_regle,
    saisies_depuis_regle,
    types_disponibles,
)
from src.validator import (
    MAX_REGLES,
    MAX_TAILLE_FICHIER_REGLES,
    colonnes_comparables,
    colonnes_compatibles,
    decrire_regle,
    echapper_markdown,
    regles_depuis_texte,
    regles_vers_texte,
    regles_non_realisables,
    resumer_resultat,
    valider,
)

# Lien de soutien (page Buy Me a Coffee) ; mettre None pour masquer le bouton.
# Le paiement se fait entièrement chez le prestataire : l'application ne voit
# passer aucune donnée de paiement.
LIEN_DON = "https://buymeacoffee.com/johan_mac"

EXTENSIONS = ["csv", "xlsx", "xls", "json", "jsonl", "parquet"]

# Échantillon synthétique versionné avec le dépôt : il permet d'essayer l'outil
# sans avoir de fichier sous la main. Aucune donnée personnelle.
CHEMIN_EXEMPLE = Path(__file__).parent / "data" / "samples" / "reservations_exemple.csv"

# Identité visuelle de Quitus : le logo complet (pictogramme, nom et devise) en
# tête de page, le pictogramme seul comme icône de l'onglet du navigateur.
# Deux variantes du logo, « light » et « dark » (texte blanc), fusionnées par
# marque.logo_adaptatif_svg() en un seul SVG qui suit le thème affiché.
CHEMIN_LOGO = marque.CHEMIN_LOGO
CHEMIN_ICONE = Path(__file__).parent / "assets" / "quitus-icon.svg"

LIEN_DEPOT = "https://github.com/johan-mac-59/quitus"

# Contact et retours. Les anomalies se signalent sur la page Issues du dépôt ;
# le lien LinkedIn n'est affiché que s'il est renseigné.
LIEN_GITHUB = "https://github.com/johan-mac-59"
LIEN_ANOMALIES = f"{LIEN_DEPOT}/issues"
LIEN_LINKEDIN = "https://www.linkedin.com/in/johan-machu/"

# Étiquettes lisibles des statistiques de nettoyage, et leur unité.
LIBELLES_STATS = {
    "empty_cols_dropped": ("Colonnes vides supprimées", "colonnes"),
    "whitespace_cleaned": ("Espaces superflus nettoyés", "valeurs"),
    "case_normalized": ("Casse uniformisée", "colonnes"),
    "types_fixed_pandas": ("Types entiers restaurés", "colonnes"),
    "types_converted": ("Types convertis", "colonnes"),
    "values_unparsed": ("Valeurs illisibles vidées", "valeurs"),
    "grades_rescaled": ("Notes ramenées à une échelle commune", "valeurs"),
    "duplicates_removed": ("Doublons supprimés", "lignes"),
    "missing_filled": ("Valeurs manquantes comblées", "valeurs"),
    "outliers_corrected": ("Valeurs aberrantes écrêtées", "valeurs"),
}

ETAT_INITIAL = {
    "signature": None,     # empreinte du fichier déposé, détecte un changement
    "nom_source": None,
    "df_brut": None,
    "profil": None,        # profil AVANT nettoyage — le dictionnaire seul, jamais le profileur
    "df_propre": None,
    "stats": None,
    "profil_post": None,   # profil APRÈS nettoyage, pour contrôler le résultat
    "choix_nettoye": None,  # choix du dernier nettoyage : relancer à l'identique est inutile
    "annonce_nettoyage": False,  # un nettoyage vient de finir, à confirmer par un toast
    # Suffixes des noms de fichiers téléchargés. Un par analyse, un par
    # nettoyage : tester avec puis sans écrêtage produit deux jeux de fichiers
    # distincts, et tous les fichiers d'un même essai portent la même marque.
    "horodatage_analyse": None,
    "horodatage_nettoyage": None,
    "journaux": {},        # nom d'étape -> sortie console capturée
    "etape": "vide",       # vide -> charge -> profile -> nettoye
    # Entre dans la clé du composant d'envoi. L'incrémenter force Streamlit à
    # en recréer un neuf, donc vide : c'est le seul moyen de faire oublier un
    # fichier déjà déposé, sans quoi il serait rechargé au rafraîchissement
    # suivant et l'effacement des données n'aurait aucun effet.
    "generation_envoi": 0,
    # Contraintes définies par l'utilisateur, au vu des données nettoyées. Elles
    # dépendent des noms de colonnes : un nouveau fichier les efface (on les
    # reprend en les important). Les résultats, eux, se recalculent seulement
    # quand les règles ou les données changent : `st.tabs` exécute tous les
    # onglets à chaque interaction.
    "regles": [],
    "contraintes": None,    # {"cle", "avant", "apres"} : résultats de `valider`
    "message_regles": None,  # confirmation à afficher après un ajout ou un import
    "avertissement_regles": None,  # règles importées qui ne s'appliquent pas au fichier
    "regle_en_edition": None,  # identifiant de la contrainte en cours de modification
    # Entrent dans les clés des widgets de saisie et d'import : les incrémenter
    # les recrée vides, comme pour `generation_envoi`.
    "generation_regles": 0,
    "generation_import_regles": 0,
}

# Préfixes des clés de widgets du validateur, purgés par « Effacer mes données ».
PREFIXES_WIDGETS_REGLES = ("regle_", "import_regles_", "suppr_regle_", "modif_regle_")


# ==========================================================================
# État de session
# ==========================================================================

def initialiser_etat() -> None:
    """Installe les clés d'état manquantes, sans écraser l'existant."""
    for cle, valeur in ETAT_INITIAL.items():
        if cle not in st.session_state:
            st.session_state[cle] = valeur.copy() if isinstance(valeur, (dict, list)) else valeur


def reinitialiser_aval() -> None:
    """Efface tout ce qui découle du fichier chargé.

    Appelé dès qu'un nouveau fichier est déposé : sans cela, on afficherait le
    dataset nettoyé du fichier précédent à côté du profilage du nouveau.
    """
    for cle in ("profil", "df_propre", "stats", "profil_post",
                "horodatage_analyse", "horodatage_nettoyage"):
        st.session_state[cle] = None
    st.session_state["journaux"] = {}
    st.session_state["etape"] = "charge"
    # Les contraintes portent sur des noms de colonnes : elles ne survivent pas
    # au changement de fichier.
    st.session_state["regles"] = []
    st.session_state["contraintes"] = None
    st.session_state["message_regles"] = None
    st.session_state["avertissement_regles"] = None
    st.session_state["regle_en_edition"] = None


def purger_cache(*dfs: pd.DataFrame | None) -> None:
    """Retire du cache partagé les seules entrées calculées sur ces DataFrames.

    Le cache de Streamlit est commun à toutes les sessions : le vider en bloc
    effacerait aussi les calculs des autres visiteurs. On retire donc entrée
    par entrée — profils et rapports, sous toutes leurs variantes — ce qui a
    été calculé sur les données de cette session, et rien d'autre.

    Args:
        dfs: DataFrames dont les entrées sont à retirer ; `None` est ignoré.
    """
    for df in dfs:
        if df is None:
            continue
        for exploratoire in (False, True):
            profiler.clear(df, exploratoire)
            for fmt in ("md", "html"):
                rendre_rapport.clear(df, exploratoire, fmt)


def tout_effacer() -> None:
    """Vide l'état de session, les entrées de cache de la session et le fichier déposé.

    C'est le droit à l'effacement rendu opérationnel en un clic : le cache de
    Streamlit est global au processus, donc une entrée survit à la session qui
    l'a créée si on ne la purge pas explicitement. Seules les entrées de cette
    session sont purgées : les calculs des autres visiteurs restent en place.

    Le composant d'envoi doit être renouvelé, et non seulement l'état vidé :
    il conserve sinon le fichier déposé, qui serait rechargé au rafraîchissement
    suivant — l'effacement n'aurait alors aucun effet visible.
    """
    generation = st.session_state.get("generation_envoi", 0) + 1
    purger_cache(st.session_state.get("df_brut"), st.session_state.get("df_propre"))

    for cle in ETAT_INITIAL:
        st.session_state.pop(cle, None)
    # La clé du composant d'envoi lui-même, désormais orpheline.
    st.session_state.pop(f"envoi_{generation - 1}", None)
    # Les widgets de saisie des contraintes, dont les clés ne sont pas dans l'état initial.
    for cle in [c for c in st.session_state if str(c).startswith(PREFIXES_WIDGETS_REGLES)]:
        st.session_state.pop(cle, None)

    initialiser_etat()
    st.session_state["generation_envoi"] = generation


def installer_fichier(octets: bytes, nom: str) -> None:
    """Charge un fichier et en fait la source de la session.

    Point d'entrée commun au dépôt et à l'exemple. Un fichier identique à celui
    déjà chargé est ignoré : sans cela, chaque réexécution du script — donc
    chaque clic — effacerait le profilage et le nettoyage déjà faits.

    Args:
        octets: Contenu brut du fichier.
        nom: Nom du fichier, dont l'extension détermine le format.
    """
    signature = hashlib.sha256(octets).hexdigest() + nom
    if signature == st.session_state["signature"]:
        return

    df, journal = charger(octets, nom)
    # Le fichier précédent de la session est abandonné : ses calculs aussi.
    purger_cache(st.session_state["df_brut"], st.session_state["df_propre"])
    st.session_state["signature"] = signature
    st.session_state["nom_source"] = nom
    st.session_state["df_brut"] = df
    reinitialiser_aval()
    st.session_state["journaux"]["chargement"] = journal


def executer_etape(nom: str, fonction, *args, **kwargs):
    """Exécute une étape du pipeline en capturant sa sortie console.

    La capture est volontairement resserrée autour du seul appel métier : elle
    n'englobe aucun appel d'affichage, faute de quoi une exception verrait sa
    trace absorbée par le tampon au lieu de remonter à Streamlit.

    Args:
        nom: Clé sous laquelle ranger le journal capturé.
        fonction: Fonction à exécuter.
        *args: Arguments positionnels transmis.
        **kwargs: Arguments nommés transmis.

    Returns:
        Ce que renvoie la fonction.
    """
    with capture_output() as tampon:
        try:
            return fonction(*args, **kwargs)
        finally:
            st.session_state["journaux"][nom] = tampon.getvalue()


def volet_console(nom: str, libelle: str) -> None:
    """Affiche le journal console d'une étape dans un volet dépliable.

    Args:
        nom: Clé du journal dans l'état de session.
        libelle: Titre du volet.
    """
    journal = st.session_state["journaux"].get(nom)
    if journal and journal.strip():
        with st.expander(f"🖨️ {libelle}"):
            st.code(journal, language="text")


def afficher_figure(fig) -> None:
    """Affiche une figure puis libère ses artistes.

    Les figures ne sont jamais conservées en session : on stocke les données
    d'entrée et on reconstruit à l'affichage. Voir `src/plot_factory.py`.

    Args:
        fig: Figure matplotlib à afficher.
    """
    st.pyplot(fig)
    fig.clf()


def racine_fichier() -> str:
    """Retourne le nom du fichier déposé, sans son extension.

    Returns:
        Le nom de base, utilisé pour nommer les fichiers téléchargés.
    """
    return (st.session_state["nom_source"] or "donnees").rsplit(".", 1)[0]


def nom_fichier(base: str, horodatage: str | None, extension: str) -> str:
    """Compose le nom d'un fichier téléchargé, suffixé de son horodatage.

    Le suffixe `AAAAMMJJ_HHMMSS` classe les fichiers par ordre chronologique et
    empêche un second essai d'écraser le premier dans le dossier de
    téléchargement.

    Args:
        base: Début du nom, sans extension.
        horodatage: Suffixe de l'étape qui a produit le fichier ; omis s'il n'y
            en a pas encore.
        extension: Extension, sans le point.

    Returns:
        Le nom de fichier complet.
    """
    return f"{base}_{horodatage}.{extension}" if horodatage else f"{base}.{extension}"


def formater(n: int) -> str:
    """Formate un entier avec un espace comme séparateur de milliers.

    Args:
        n: Entier à formater.

    Returns:
        La chaîne formatée, à la française.
    """
    return f"{int(n):,}".replace(",", " ")


# ==========================================================================
# Étapes coûteuses, mises en cache
# ==========================================================================

# ttl et max_entries ne sont pas seulement des réglages de performance : le
# cache de Streamlit est partagé entre toutes les sessions du processus, donc
# les borner limite la durée de conservation des données des visiteurs.
CACHE = dict(ttl=3600, max_entries=8)


def charger(octets: bytes, nom: str) -> tuple[pd.DataFrame, str]:
    """Charge un fichier déposé, avec détection du format et de l'encodage.

    Délibérément hors cache : sa clé serait le contenu brut du fichier, qu'il
    faudrait garder en session pour pouvoir retirer l'entrée ensuite. Un
    fichier n'est de toute façon chargé qu'une fois par session, la signature
    évitant tout rechargement à chaque clic.

    Args:
        octets: Contenu brut du fichier.
        nom: Nom du fichier, dont l'extension détermine le format.

    Returns:
        Le DataFrame chargé et la sortie console de l'opération.
    """
    with st.spinner("Chargement du fichier…"), capture_output() as tampon:
        df = load_dataframe(octets, nom)
    return df, tampon.getvalue()


@st.cache_data(show_spinner="Profilage en cours…", **CACHE)
def profiler(df: pd.DataFrame, exploratoire: bool) -> tuple[dict, str]:
    """Profile un DataFrame sans rien écrire sur le disque.

    Le profileur est construit ici et non conservé : seul son dictionnaire de
    résultats est retourné, ce qui évite de garder en session une copie
    complète du DataFrame par profileur.

    Args:
        df: DataFrame à analyser.
        exploratoire: Utilise le profileur exploratoire plutôt que celui d'audit.

    Returns:
        Les résultats d'analyse et la sortie console.
    """
    classe = ExploratoryProfiler if exploratoire else PreCleaningProfiler
    with capture_output() as tampon:
        instance = classe(df, "fichier_depose")
        resultats = instance.run_profiling_workflow(
            "fichier_depose", None, generate_report=False, raise_on_error=True
        )
    return resultats, tampon.getvalue()


@st.cache_data(show_spinner="Rendu du rapport…", **CACHE)
def rendre_rapport(df: pd.DataFrame, exploratoire: bool, fmt: str) -> str:
    """Produit un rapport de profilage en mémoire.

    Args:
        df: DataFrame à documenter.
        exploratoire: Utilise le profileur exploratoire.
        fmt: Format du rapport, `"md"` ou `"html"`.

    Returns:
        Le contenu du rapport.
    """
    classe = ExploratoryProfiler if exploratoire else PreCleaningProfiler
    with capture_output():
        return classe(df, "fichier_depose").render_report(fmt)


def rapport_nettoyage() -> str:
    """Produit le rapport de nettoyage Markdown en mémoire.

    `CleanerReporter` ne lit qu'un attribut du profileur : un objet factice
    suffit, ce qui évite de conserver un profileur complet en session.

    Returns:
        Le contenu Markdown du rapport.
    """
    factice = SimpleNamespace(profile_results=st.session_state["profil"] or {})
    reporter = CleanerReporter(factice, logging.getLogger("app"),
                               source_file_path=st.session_state["nom_source"])
    resultats = contraintes_courantes()
    contraintes = ({"avant": resultats["avant"], "apres": resultats["apres"]}
                   if resultats else None)
    return reporter.render(st.session_state["stats"], contraintes)


def contraintes_courantes() -> dict | None:
    """Évalue les contraintes sur le fichier brut et sur le fichier nettoyé.

    Le résultat est gardé en session et ne se recalcule que si les règles ou
    les données ont changé : `st.tabs` exécute le corps de tous les onglets à
    chaque interaction, et `valider` parcourt les données.

    Returns:
        ``{"cle", "avant", "apres"}`` (résultats de `valider`), ou None s'il n'y
        a aucune règle ou pas encore de fichier nettoyé.
    """
    regles = st.session_state["regles"]
    propre = st.session_state["df_propre"]
    if not regles or propre is None:
        return None
    cle = json.dumps([st.session_state["signature"], st.session_state["horodatage_nettoyage"],
                      regles], sort_keys=True, ensure_ascii=False, default=str)
    actuel = st.session_state["contraintes"]
    if actuel is not None and actuel["cle"] == cle:
        return actuel
    resultats = {"cle": cle,
                 "avant": valider(st.session_state["df_brut"], regles),
                 "apres": valider(propre, regles)}
    st.session_state["contraintes"] = resultats
    return resultats


# Hauteur de l'aperçu HTML : au-delà, l'iframe défile sur elle-même, ce qui
# évite qu'un long rapport repousse le reste de l'onglet hors de vue.
HAUTEUR_APERCU_HTML = 800


@st.dialog("Rapport HTML", width="large")
def fenetre_rapport(df: pd.DataFrame, exploratoire: bool) -> None:
    """Affiche un rapport HTML dans une fenêtre modale large.

    C'est l'équivalent le plus proche d'une « nouvelle fenêtre » qui reste sûr.
    Ouvrir le rapport dans un vrai onglet supposerait soit une URL `data:`, que
    Chrome et Firefox bloquent en navigation, soit le service de fichiers
    statiques de Streamlit — qui exigerait d'écrire le rapport sur le serveur,
    dans un dossier public, lisible par quiconque en connaît l'adresse.

    Args:
        df: DataFrame documenté par le rapport.
        exploratoire: Utilise le profileur exploratoire.
    """
    st.iframe(rendre_rapport(df, exploratoire, "html"), height=HAUTEUR_APERCU_HTML)


def boutons_rapport_profilage(df: pd.DataFrame, exploratoire: bool, prefixe: str,
                              horodatage: str | None, apercu: bool = True,
                              emplacement: str = "") -> None:
    """Propose un rapport de profilage : HTML à afficher ou télécharger, Markdown à télécharger.

    Le HTML est le rapport de consultation — tableau de bord autonome,
    graphiques intégrés — d'où l'aperçu. Le Markdown est un format d'archive
    ou de réutilisation : un simple téléchargement suffit.

    Rien n'est calculé tant qu'on ne le demande pas. Les téléchargements
    reçoivent une fonction, exécutée au clic seulement ; l'aperçu n'est produit
    qu'à l'activation de son interrupteur. Sans cela, tous les onglets
    s'exécutant à chaque interaction, le rapport HTML et ses graphiques
    seraient recalculés en permanence. `on_click="ignore"` évite en outre de
    relancer toute l'application après un téléchargement.

    L'aperçu s'affiche dans une iframe, qui isole les styles du rapport de ceux
    de l'application. Le rapport échappe toutes les données du fichier et
    interdit l'exécution de scripts par sa politique de sécurité : c'est ce qui
    rend cet affichage sûr, le fichier étant fourni par l'utilisateur.

    Args:
        df: DataFrame documenté par le rapport.
        exploratoire: Utilise le profileur exploratoire.
        prefixe: Préfixe du nom de fichier, et discriminant des clés de widget.
        horodatage: Suffixe du nom de fichier — celui de l'analyse pour le
            rapport avant nettoyage, celui du nettoyage pour le rapport après.
        apercu: Propose l'aperçu du rapport HTML en plus des téléchargements.
        emplacement: Suffixe des clés de widget. Les mêmes boutons figurent dans
            l'onglet du rapport et dans l'onglet Téléchargements ; Streamlit
            refuse deux widgets de même clé.
    """
    racine = racine_fichier()
    cle = f"{prefixe}{emplacement}"

    if apercu:
        interrupteur, fenetre = st.columns([3, 1], vertical_alignment="center")
        with interrupteur:
            afficher_ici = st.toggle("👁️ Afficher le rapport HTML ici", key=f"apercu_{cle}")
        with fenetre:
            if st.button("🔎 Ouvrir en grand", key=f"fenetre_{cle}", width="stretch"):
                fenetre_rapport(df, exploratoire)
        if afficher_ici:
            st.iframe(rendre_rapport(df, exploratoire, "html"), height=HAUTEUR_APERCU_HTML)

    gauche, droite = st.columns(2)
    with gauche:
        st.download_button(
            "⬇️ Rapport HTML (graphiques inclus)",
            data=lambda: rendre_rapport(df, exploratoire, "html").encode("utf-8"),
            file_name=nom_fichier(f"{prefixe}_{racine}", horodatage, "html"),
            mime="text/html",
            on_click="ignore",
            key=f"dl_{cle}_html",
            width="stretch",
            help="Autonome et partageable par courriel : les graphiques sont intégrés.",
        )
    with droite:
        st.download_button(
            "⬇️ Rapport Markdown",
            data=lambda: rendre_rapport(df, exploratoire, "md").encode("utf-8"),
            file_name=nom_fichier(f"{prefixe}_{racine}", horodatage, "md"),
            mime="text/markdown",
            on_click="ignore",
            key=f"dl_{cle}_md",
            width="stretch",
            help="Même contenu que le rapport HTML, sans les graphiques, en texte brut.",
        )


# ==========================================================================
# Fragments d'interface
# ==========================================================================

def encart_confidentialite() -> None:
    """Affiche la note de transparence sur le traitement des données."""
    with st.expander("🔒 Confidentialité — que devient votre fichier ?"):
        st.markdown(
            """
**Rien n'est enregistré.** Votre fichier est traité en mémoire le temps de
votre session, puis oublié. Aucune copie n'est jamais écrite sur le serveur :
tout ce que vous récupérez passe par les boutons de téléchargement.

**Ce qui se passe, étape par étape :**

| Étape | Où vivent les données | Durée |
|---|---|---|
| Dépôt du fichier | mémoire du serveur | la session |
| Analyse et nettoyage | mémoire du serveur | la session |
| Cache de calcul | mémoire du serveur, partagé | 1 heure au plus |
| Téléchargements | votre navigateur | vous décidez |

**Cookies :** aucun traceur. La télémétrie de Streamlit est désactivée dans la
configuration du projet ; seul subsiste un cookie technique de sécurité,
indispensable au fonctionnement.

Le bouton **« Effacer mes données »** de la barre latérale vide immédiatement
la session et retire du cache tout ce qui a été calculé sur votre fichier.
Remplacer le fichier ou relancer le nettoyage retire aussi les calculs devenus inutiles.

**Soutien :** le bouton « Soutenir le projet » ouvre une page Buy Me a Coffee
dans un nouvel onglet. Le paiement s'y déroule entièrement : cette application
ne voit passer aucune donnée de paiement, et ne sait pas qui a donné.

⚠️ Par prudence, évitez de déposer des données personnelles sensibles.
"""
        )


# Agrandit de 20 % les boutons de soutien et de contact, et eux seuls. Streamlit
# n'offre pas de réglage de taille pour st.link_button, mais donne à chaque
# widget muni d'une clé la classe CSS « st-key-<clé> » : ces boutons, dont les
# clés commencent par « soutien_ » ou « contact_ », sont ainsi ciblés sans
# toucher aux autres. `zoom` plutôt que `transform: scale` : il agrandit ET
# décale ce qui suit, là où une mise à l'échelle ferait déborder le bouton sur
# le texte voisin.
#
# Ces boutons, et la zone de dépôt, portent aussi leurs couleurs : celles de
# chaque service, et le vert de Quitus pour le dépôt. Un fond plein et un texte
# fixé explicitement restent lisibles dans les deux thèmes. Seul le noir de
# GitHub disparaîtrait sur fond sombre : il s'inverse par `light-dark()`, que le
# navigateur résout d'après le thème réel, comme pour le logo. Le survol de
# Streamlit, qui recolore texte et bordure, est neutralisé au profit d'un
# simple assombrissement.
STYLE_BOUTONS_SOUTIEN = """
<style>
[class*="st-key-soutien_"], [class*="st-key-contact_"] { zoom: 1.2; }
[class*="st-key-soutien_"] a, [class*="st-key-contact_"] a,
[data-testid="stFileUploaderDropzone"] button {
    background: var(--fond-bouton); border: 1px solid var(--fond-bouton);
}
:is([class*="st-key-soutien_"], [class*="st-key-contact_"]) a :is(p, div),
[data-testid="stFileUploaderDropzone"] button :is(p, div, span) {
    color: var(--texte-bouton);
}
:is([class*="st-key-soutien_"], [class*="st-key-contact_"]) a:hover,
[data-testid="stFileUploaderDropzone"] button:hover {
    border-color: var(--fond-bouton); filter: brightness(0.92);
}
[class*="st-key-soutien_"] { --fond-bouton: #FFDD00; --texte-bouton: #000000; }
[class*="st-key-contact_"][class*="_linkedin"] {
    --fond-bouton: #0A66C2; --texte-bouton: #FFFFFF;
}
[class*="st-key-contact_"][class*="_github"] {
    --fond-bouton: light-dark(#24292F, #F0F6FC);
    --texte-bouton: light-dark(#FFFFFF, #24292F);
}
[data-testid="stFileUploaderDropzone"] {
    --fond-bouton: #3DDC97; --texte-bouton: #12304A;
    border: 2px dashed #3DDC97; background: rgba(61, 220, 151, 0.10);
}
[data-testid="stFileUploaderDropzone"] button { width: 100%; }
</style>
"""

# Texte courant et petit texte agrandis d'un pixel : 16 → 17 px et 14 → 15 px.
# Par CSS plutôt que par l'option baseFontSize de la configuration : celle-ci
# crée un thème personnalisé, qui priverait le visiteur du choix clair/sombre,
# et agrandirait aussi les titres. À spécificité égale, la dernière règle
# l'emporte : les libellés de champs et les légendes, écrits en petit, sont donc
# déclarés après le texte courant.
STYLE_TEXTE = """
<style>
[data-testid="stMarkdownContainer"] :is(p, li) { font-size: 17px; }
[data-testid="stWidgetLabel"] [data-testid="stMarkdownContainer"] p { font-size: 15px; }
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] :is(p, li) { font-size: 15px; }
</style>
"""

# Streamlit réserve 6rem au-dessus du contenu pour sa barre d'en-tête, qui ne
# porte pourtant que le menu, à droite : le logo flottait sous un grand vide.
# La marge est réduite, et l'en-tête rendu transparent, sans quoi son fond
# couvrirait le haut du logo. Le logo, agrandi, occupe l'espace ainsi libéré ;
# il ne dépasse jamais la largeur de la page, sur un écran étroit.
LARGEUR_LOGO = 450
STYLE_HAUT_DE_PAGE = f"""
<style>
[data-testid="stMainBlockContainer"] {{ padding-top: 2rem; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stMain"] svg[aria-label^="Quitus"] {{
    width: {LARGEUR_LOGO}px; max-width: 100%; height: auto; display: block;
    margin-bottom: 0.75rem;
}}
</style>
"""


def bloc_retours() -> None:
    """Invite aux remarques et au signalement d'anomalies.

    Les signalements passent par la page Issues du dépôt GitHub, qui est
    publique : d'où l'avertissement de ne jamais y joindre un fichier de
    données, mais une description ou un extrait anonymisé.
    """
    st.markdown("#### 💬 Une remarque, une anomalie ?")
    st.markdown(
        "Toute remarque constructive ou anomalie détectée est la bienvenue : "
        "c'est ainsi que Quitus progresse. Plusieurs de ses corrections "
        "récentes sont d'ailleurs nées de retours d'utilisation."
    )
    st.markdown(f"[🐞 Signaler une anomalie]({LIEN_ANOMALIES})")
    st.caption("🔒 Les signalements sont publics : décrivez le problème ou joignez "
               "un extrait anonymisé, mais ne publiez jamais votre fichier de données.")


def bloc_contact(emplacement: str) -> None:
    """Les boutons pour contacter l'auteur, de la taille du bouton de soutien.

    Distinct du signalement d'anomalies : on ne contacte pas une personne
    comme on remonte un défaut.

    Args:
        emplacement: Discriminant des clés des boutons, qui commencent par
            « contact_ » pour recevoir le même agrandissement que le soutien.
    """
    st.markdown("#### 📇 Me contacter")
    with st.container(horizontal=True):
        st.link_button("💻 GitHub", LIEN_GITHUB, key=f"contact_{emplacement}_github")
        if LIEN_LINKEDIN:
            st.link_button("💼 LinkedIn", LIEN_LINKEDIN,
                           key=f"contact_{emplacement}_linkedin")


def soutien_et_contact(emplacement: str, message: str) -> None:
    """Pied de page : coup de pouce et contact, côte à côte.

    Séparé des retours par un trait. Sans lien de soutien configuré, le
    contact reste seul, dans la première colonne.

    Args:
        emplacement: Discriminant de la clé du bouton de soutien.
        message: Texte accompagnant le bouton de soutien.
    """
    st.divider()
    colonne_soutien, colonne_contact = st.columns(2, gap="large")
    if LIEN_DON:
        with colonne_soutien:
            st.markdown("#### ☕ Un coup de pouce ?")
            bouton_soutien(emplacement, message)
    else:
        colonne_contact = colonne_soutien
    with colonne_contact:
        bloc_contact(emplacement)


def bouton_soutien(emplacement: str, message: str, message_avant: bool = True) -> None:
    """Affiche le bouton de soutien, accompagné d'un message.

    Le bouton figure à plusieurs endroits — barre latérale, présentation,
    téléchargements —, chacun avec un message adapté au moment. Streamlit
    refusant deux widgets de même clé, chaque emplacement a la sienne.

    Ne fait rien si aucun lien de soutien n'est configuré.

    Args:
        emplacement: Discriminant de la clé du widget.
        message: Texte accompagnant le bouton.
        message_avant: Place le message au-dessus du bouton plutôt qu'en dessous.
    """
    if not LIEN_DON:
        return
    if message_avant:
        st.markdown(message)
    st.link_button("☕ Soutenir le projet", LIEN_DON, key=f"soutien_{emplacement}")
    if not message_avant:
        st.caption(message)


def page_accueil(accueil: bool = True) -> None:
    """Présente le projet : sur la page d'accueil, puis dans le premier onglet.

    Une page d'accueil vide laisse le visiteur sans prise. Celle-ci explique le
    problème traité, montre ce que l'outil corrige sur des exemples concrets,
    énonce ses principes, raconte comment il est né — et propose de l'essayer
    immédiatement sur un exemple, sans fichier à fournir.

    Elle occupe toujours le premier onglet, « Présentation », avant comme après
    le dépôt d'un fichier : elle ne disparaît jamais.

    Args:
        accueil: Vrai tant qu'aucun fichier n'est chargé : le bouton d'essai
            est proposé. Faux ensuite : il est remplacé par un simple rappel,
            puisqu'il remplacerait le fichier en cours.
    """
    st.markdown(
        "### Déposez un fichier dont vous ne savez rien.\n"
        "### Repartez avec un fichier propre — et la preuve qu'il l'est."
    )
    st.markdown(
        "Encodage, séparateur, types, doublons, formats monétaires, dates "
        "incohérentes : Quitus inspecte votre fichier sans rien savoir de lui "
        "à l'avance, vous montre ses défauts, les corrige sous votre contrôle, "
        "puis **vérifie son propre travail**."
    )

    if accueil:
        gauche, droite = st.columns([1, 2], vertical_alignment="center")
        with gauche:
            if CHEMIN_EXEMPLE.exists():
                if st.button("▶️ Essayer avec un exemple", type="primary", width="stretch",
                             help="312 réservations d'hôtel fictives, truffées des défauts "
                                  "d'un vrai export : dates en trois formats, montants en "
                                  "« 1 200,50 € », casse incohérente, doublons…"):
                    installer_fichier(CHEMIN_EXEMPLE.read_bytes(), CHEMIN_EXEMPLE.name)
                    st.rerun()
        with droite:
            st.caption("… ou déposez votre propre fichier dans la barre latérale : "
                       "CSV, Excel, JSON, JSON Lines ou Parquet, 20 Mo au plus.")
    else:
        st.caption(f"Fichier en cours : « {st.session_state['nom_source']} ». "
                   "Suivez les onglets de gauche à droite : aperçu, diagnostic, "
                   "nettoyage, contrôle, graphiques, téléchargements.")

    st.divider()

    # --- Le problème -----------------------------------------------------------
    st.markdown("#### 🤔 Pourquoi un fichier « qui s'ouvre bien » ment souvent")
    st.markdown(
        "Un export de données a presque toujours l'air correct. Ses défauts sont "
        "silencieux : ils ne font rien planter, ils **faussent les résultats**. "
        "Trois villes « Nice », « nice » et « NICE » se comptent séparément. Un "
        "montant « 1 200,50 € » est du texte, donc absent de toute moyenne. Une "
        "colonne de dates mêlant trois conventions n'est plus triable."
    )

    exemples = pd.DataFrame([
        {"Dans le fichier reçu": '"  Nice ", "nice", "NICE"',
         "Après nettoyage": "Nice", "Ce qui a été fait": "Espaces et casse uniformisés"},
        {"Dans le fichier reçu": '"1 200,50 €"',
         "Après nettoyage": "1200.50", "Ce qui a été fait": "Montant lu comme un nombre"},
        {"Dans le fichier reçu": "13/09/2024 · 2023-09-15 · 18-07-2023",
         "Après nettoyage": "Trois vraies dates", "Ce qui a été fait": "Conventions mêlées, toutes reconnues"},
        {"Dans le fichier reçu": '"17/20", "4/5" · "78,5 %"',
         "Après nettoyage": "17 · 16 · 78.5",
         "Ce qui a été fait": "Notes ramenées sur 20, pourcentage chiffré"},
        {"Dans le fichier reçu": "Deux lignes identiques",
         "Après nettoyage": "Une seule", "Ce qui a été fait": "Doublon exact supprimé"},
    ])
    st.dataframe(exemples, hide_index=True, width="stretch")

    # --- Le parcours -----------------------------------------------------------
    st.markdown("#### 🧭 Comment ça marche")
    etapes = [
        ("1 · Déposer", "Format, encodage et séparateur sont détectés tout seuls. "
                        "Rien à configurer."),
        ("2 · Diagnostiquer", "Un premier rapport dresse l'état des lieux, défauts "
                              "compris. C'est le constat de départ."),
        ("3 · Décider", "Deux traitements modifient vos valeurs. Ils ne s'appliquent "
                        "qu'avec votre accord, colonne par colonne."),
        ("4 · Vérifier", "Un second rapport contrôle le résultat : plus aucune "
                         "colonne ne doit rester mal typée."),
    ]
    for colonne, (titre, texte) in zip(st.columns(4), etapes):
        with colonne:
            with st.container(border=True, height="stretch"):
                st.markdown(f"**{titre}**")
                st.caption(texte)

    # --- Les principes ---------------------------------------------------------
    st.markdown("#### 🧱 Trois principes")
    principes = [
        ("🙋 Rien ne change sans vous",
         "Doublons, espaces, casse et types sont corrigés d'office : ce sont des "
         "erreurs. Mais écrêter une valeur extrême ou combler un trou, c'est "
         "**modifier une donnée** — et une absence peut avoir un sens. Un "
         "carburant en rupture n'a pas de prix ; lui en inventer un fausserait "
         "tout. Ces deux traitements restent donc votre décision."),
        ("🔎 Rien ne disparaît en silence",
         "Quand une valeur ne peut pas être lue dans le type de sa colonne — une "
         "date en l'an 216, un « abc » parmi des nombres —, elle est vidée, et "
         "**vous le savez** : colonne, nombre, exemples. Aucune perte n'est "
         "jamais passée sous silence."),
        ("⚖️ Deux rapports, deux rôles",
         "Le rapport **avant** nettoyage décrit le désordre tel qu'il est : c'est "
         "sa raison d'être. Le rapport **après** atteste sa disparition. L'un "
         "constate, l'autre prouve."),
    ]
    for colonne, (titre, texte) in zip(st.columns(3), principes):
        with colonne:
            with st.container(border=True, height="stretch"):
                st.markdown(f"**{titre}**")
                st.markdown(texte)

    # --- L'histoire ------------------------------------------------------------
    with st.expander("📖 L'histoire du projet — d'un script de terminal à cette application"):
        st.markdown(
            f"""
Tout est parti d'une contrainte simple, écrite au premier jour : **nettoyer un
fichier CSV sans rien savoir de lui à l'avance** — ni son encodage, ni son
séparateur, ni ses types. Un script, une poignée de fonctions, et une question :
dans quel ordre corriger, pour qu'une correction n'en fausse pas une autre ?

**Du script à l'architecture.** Les fonctions sont devenues des modules, chacun
avec sa responsabilité : lire, profiler, nettoyer, journaliser, rapporter. Les
tests unitaires sont arrivés, et avec eux les premières surprises — un moteur
qui semblait fonctionner, jusqu'à ce qu'on lui pose les bonnes questions.

**L'humain dans la boucle.** Un tournant, à l'étape 22 : l'outil cesse d'être
un automate qui décide seul pour devenir un **assistant de décision**. Imputer
une médiane est statistiquement correct ; ce peut être sémantiquement faux.
Alors c'est l'analyste qui tranche, avec les faits sous les yeux.

**Le double regard.** Un profileur avant, un profileur après — le premier pour
constater, le second pour prouver. C'est devenu la colonne vertébrale du projet.

**L'application web, et l'audit qui l'a précédée.** Avant de construire cette
interface, tout le code a été passé au crible. Ce fut édifiant : l'écrêtage des
valeurs aberrantes **ne s'était jamais appliqué** — la question n'était même pas
posée —, la détection des dates était du code que rien n'atteignait, et 1 849
montants au format « 1 052,23 € » disparaissaient sans un mot. Sur le jeu de
référence de 73 810 réservations, l'outil écrêtait **zéro** valeur aberrante ;
quand on le lui demande, il en traite aujourd'hui **5 848**.

Chaque étape — erreurs comprises — est consignée dans le journal de bord du
projet. Le code est ouvert : **[consulter le dépôt]({LIEN_DEPOT})**.
"""
        )

    # --- Retours, puis soutien -------------------------------------------------
    # Placés après l'histoire : c'est là que le lecteur mesure le travail
    # accompli. Les retours d'abord, qui comptent plus qu'un don. La page
    # d'accueil et l'onglet Présentation ne sont jamais affichés ensemble :
    # une seule clé de bouton suffit.
    bloc_retours()
    soutien_et_contact(
        "presentation",
        "Quitus est gratuit, sans publicité, et ne conserve aucune de vos "
        "données. S'il vous fait gagner du temps, vous pouvez encourager son "
        "développement en offrant un café. C'est entièrement facultatif — et "
        "déjà, merci de l'avoir essayé !",
    )


def mot_quitus_html() -> str:
    """Le mot « quitus » tel qu'il est écrit dans le logo.

    Même police, même graisse, même approche serrée ; la couleur suit le
    thème, comme le logo : bleu marine sur fond clair, blanc sur fond sombre.
    C'est le navigateur qui choisit, via `light-dark()` (cf.
    `marque.logo_adaptatif_svg`) : la couleur change dès que le visiteur
    change de thème.
    """
    couleur = "light-dark(#12304A, #FFFFFF)"
    return (
        '<div style="font-family: \'Segoe UI\', Inter, \'Helvetica Neue\', Arial, '
        f'sans-serif; font-size: 2.4rem; font-weight: 700; letter-spacing: -1px; '
        f'line-height: 1; color: {couleur};">quitus</div>'
    )


def barre_laterale() -> dict:
    """Construit la barre latérale et retourne les options choisies.

    Returns:
        Les options de nettoyage sélectionnées.
    """
    st.sidebar.html(mot_quitus_html())

    fichier = st.sidebar.file_uploader(
        "Déposez un fichier",
        type=EXTENSIONS,
        key=f"envoi_{st.session_state['generation_envoi']}",
        help="CSV, Excel, JSON, JSON Lines ou Parquet. Le séparateur et l'encodage sont "
             "détectés automatiquement.",
    )

    if fichier is not None:
        # getvalue() et non read() : le tampon d'un fichier déposé ne se lit
        # qu'une fois par réexécution du script.
        installer_fichier(fichier.getvalue(), fichier.name)

    options = {}

    if st.session_state["df_brut"] is not None:
        df = st.session_state["df_brut"]
        st.sidebar.divider()

        if st.sidebar.button("🔍 Analyser le fichier", width="stretch",
                             type="primary"):
            try:
                profil, journal = profiler(df, exploratoire=False)
                st.session_state["profil"] = profil
                st.session_state["journaux"]["profilage"] = journal
                st.session_state["etape"] = "profile"
                st.session_state["horodatage_analyse"] = horodater()
            except Exception as e:
                st.sidebar.error(f"Le profilage a échoué : {e}")

        if st.session_state["profil"] is not None:
            options = formulaire_options(df)

        st.sidebar.divider()
        if st.sidebar.button("🗑️ Effacer mes données", width="stretch"):
            tout_effacer()
            st.rerun()

    if LIEN_DON:
        st.sidebar.divider()
        with st.sidebar:
            bouton_soutien("barre",
                           "Redirige vers un prestataire externe. "
                           "Cette application ne voit aucune donnée de paiement.",
                           message_avant=False)

    return options


def formulaire_options(df: pd.DataFrame) -> dict:
    """Construit le formulaire des options de nettoyage.

    Seules les deux décisions qui altèrent les données sont exposées, et
    chacune se prend colonne par colonne : on peut écrêter des mesures et
    laisser intacts des montants dont les extrêmes sont réels, combler une
    colonne et respecter les absences d'une autre. Tout le reste — doublons,
    espaces, casse, types — est corrigé d'office, et le nombre de passes est
    laissé au moteur, qui s'arrête dès que plus rien ne change.

    Args:
        df: DataFrame brut, pour calculer les diagnostics affichés en aide.

    Returns:
        Les colonnes choisies pour chaque traitement, le seuil IQR de chaque
        colonne à écrêter et un drapeau indiquant si le nettoyage est demandé.
    """
    profil = st.session_state["profil"]
    res_out = summarize_outliers(df, {}, profil)
    res_manq = summarize_missing_values(df)

    # Un conteneur et non un formulaire : chaque seuil affiche aussitôt le
    # nombre de valeurs qu'il écrêterait, ce qu'un formulaire, figé jusqu'à
    # sa soumission, ne permettrait pas.
    with st.sidebar.container(border=True):
        st.markdown("**Options de nettoyage**")
        st.caption("Doublons, espaces, casse et types sont corrigés d'office. "
                   "Les deux traitements ci-dessous modifient les valeurs : "
                   "ils ne sont appliqués qu'avec votre accord.")

        # Chaque colonne est proposée avec son nombre de valeurs concernées.
        aberrantes = res_out["columns"]
        ecreter = st.multiselect(
            "Écrêter les valeurs aberrantes",
            options=list(aberrantes),
            format_func=lambda c: f"{c} ({formater(aberrantes[c])})",
            disabled=not aberrantes,
            placeholder="Choisir des colonnes" if aberrantes
            else "Aucune valeur aberrante",
            help="Méthode IQR. Ramène les valeurs extrêmes dans les bornes "
                 "statistiques, dans les seules colonnes choisies. Modifie "
                 "les distributions. Le nombre indiqué est celui du seuil "
                 f"standard, {SEUIL_IQR:g}.\n\nUn extrême peut être réel : un "
                 "gros montant n'est pas forcément une erreur de saisie.",
        )

        # Un seuil par colonne choisie : des montants très dispersés appellent
        # plus de tolérance que des mesures stables.
        seuils = {}
        for col in ecreter:
            seuils[col] = st.slider(
                f"Seuil IQR · {col}",
                min_value=0.5, max_value=5.0, value=SEUIL_IQR, step=0.5,
                key=f"seuil_{col}",
                help="Nombre d'écarts interquartiles tolérés au-delà des "
                     f"quartiles. {SEUIL_IQR:g} est le seuil standard ; 3 ne "
                     "retient que les valeurs très extrêmes.",
            )
            n = count_outliers(df[col], seuils[col])
            st.caption(f"{formater(n)} valeur(s) hors bornes à ce seuil.")

        manquantes = res_manq["by_column"]
        combler = st.multiselect(
            "Combler les valeurs manquantes",
            options=list(manquantes),
            format_func=lambda c: f"{c} ({formater(manquantes[c][0])})",
            disabled=not manquantes,
            placeholder="Choisir des colonnes" if manquantes
            else "Aucune valeur manquante",
            help="Médiane pour les colonnes numériques, mode pour les "
                 "catégorielles, dans les seules colonnes choisies.\n\n⚠️ "
                 "Une absence peut avoir un sens : un produit en rupture n'a "
                 "pas de prix, un champ non applicable est vide à dessein. La "
                 "combler invente une valeur.",
        )

        # Relancer le même nettoyage ne produirait rien de nouveau : le bouton
        # reste éteint tant que les choix n'ont pas changé depuis le dernier.
        deja = (st.session_state["df_propre"] is not None
                and st.session_state["choix_nettoye"]
                == signature_choix(ecreter, seuils, combler))
        lancer = st.button("🧹 Nettoyer", width="stretch", type="primary",
                           disabled=deja)
        if deja:
            st.success("Nettoyage effectué avec ces choix. Résultat dans les "
                       "onglets Nettoyage et Après nettoyage. Modifiez les choix "
                       "pour relancer.", icon="✅")

    return {"ecreter": ecreter, "seuils": seuils, "combler": combler,
            "lancer": lancer}


# ==========================================================================
# Onglets
# ==========================================================================

def onglet_apercu() -> None:
    """Affiche un aperçu du fichier brut et ses indicateurs de base."""
    df = st.session_state["df_brut"]
    st.subheader(f"Aperçu de « {st.session_state['nom_source']} »")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Lignes", formater(len(df)))
    c2.metric("Colonnes", df.shape[1])
    c3.metric("Valeurs manquantes", formater(df.isnull().sum().sum()))
    c4.metric("Doublons", formater(df.duplicated().sum()))

    st.dataframe(df.head(50), height=380)
    st.caption(f"50 premières lignes sur {formater(len(df))}.")

    with st.expander("Types détectés par colonne"):
        st.dataframe(
            pd.DataFrame({
                "Colonne": df.columns,
                "Type": [str(t) for t in df.dtypes],
                "Valeurs manquantes": [int(df[c].isnull().sum()) for c in df.columns],
                "Valeurs distinctes": [int(df[c].nunique()) for c in df.columns],
            }),
            hide_index=True,
        )

    volet_console("chargement", "Détail du chargement")


def afficher_profil(profil: dict) -> None:
    """Affiche le contenu d'un profil : métriques, manques, outliers, catégories.

    Partagé par les onglets avant et après nettoyage, qui affichent la même
    structure de résultats.

    Args:
        profil: Dictionnaire de résultats d'un profileur.
    """
    forme = profil.get("shape", {})
    c1, c2, c3 = st.columns(3)
    c1.metric("Lignes analysées", formater(forme.get("nb_lignes", 0)))
    c2.metric("Colonnes", forme.get("nb_colonnes", "—"))
    c3.metric("Doublons exacts", formater(profil.get("nb_doublons", 0)))

    alertes = (profil.get("row_quality") or {}).get("alerts") or []
    for alerte in alertes:
        message = alerte.get("message", "")
        nombre = alerte.get("count", 0)
        if alerte.get("type") == "row_full_empty":
            st.error(f"{formater(nombre)} ligne(s) entièrement vide(s) — {message}")
        else:
            st.warning(f"{formater(nombre)} ligne(s) partiellement vide(s) — {message}")

    manquantes = profil.get("missing_values", {})
    comptes = manquantes.get("count", {})
    trouees = {c: n for c, n in comptes.items() if n}
    if trouees:
        st.markdown("**Valeurs manquantes**")
        st.dataframe(
            pd.DataFrame({
                "Colonne": list(trouees),
                "Manquantes": list(trouees.values()),
                "Part (%)": [manquantes.get("percent", {}).get(c, 0) for c in trouees],
            }).sort_values("Manquantes", ascending=False),
            hide_index=True,
        )
    else:
        st.success("Aucune valeur manquante.")

    outliers = profil.get("outliers") or {}
    if outliers:
        st.markdown("**Valeurs aberrantes (méthode IQR)**")
        st.dataframe(
            pd.DataFrame([
                {"Colonne": c, "Outliers": info.get("count", 0),
                 "Borne basse": round(info.get("lower_bound", 0), 2),
                 "Borne haute": round(info.get("upper_bound", 0), 2)}
                for c, info in outliers.items()
            ]),
            hide_index=True,
        )

    if profil.get("describe_numeric"):
        with st.expander("Statistiques descriptives (colonnes numériques)"):
            st.dataframe(pd.DataFrame(profil["describe_numeric"]))

    categorielles = profil.get("describe_categorical") or {}
    if categorielles:
        with st.expander("Analyse des colonnes catégorielles"):
            for col, infos in categorielles.items():
                st.markdown(
                    f"**{col}** — {infos.get('cardinality_absolute', 0)} "
                    f"modalités ({infos.get('cardinality_relative', 0)} % du total)"
                )

    formats = profil.get("format_text") or {}
    if formats:
        with st.expander("Qualité du format des colonnes de texte"):
            fautives = {c: i.get("format_anomalies") for c, i in formats.items()
                        if i.get("format_anomalies")}
            if not fautives:
                st.markdown("✅ Aucun espace superflu ni variation de casse.")
            for col, anomalies in fautives.items():
                st.markdown(f"⚠️ **{col}**")
                for anomalie in anomalies:
                    st.caption(f"　• {anomalie}")


def onglet_profilage() -> None:
    """Affiche le diagnostic avant nettoyage, puis propose son rapport."""
    profil = st.session_state["profil"]
    if not profil:
        st.info("Lancez l'analyse depuis la barre latérale pour voir le diagnostic.")
        return

    st.subheader("Diagnostic avant nettoyage")
    st.caption("Ce diagnostic décrit les données telles qu'elles sont reçues, "
               "défauts compris : c'est le constat de départ.")

    afficher_profil(profil)

    if profil.get("sample_preview"):
        with st.expander("Échantillon des données"):
            # sample_preview est déjà une table Markdown produite par le profileur.
            st.markdown(profil["sample_preview"])

    st.divider()
    st.markdown("**📄 Rapport de profilage avant nettoyage**")
    boutons_rapport_profilage(st.session_state["df_brut"], exploratoire=False,
                              prefixe="profilage_avant",
                              horodatage=st.session_state["horodatage_analyse"])

    volet_console("profilage", "Détail du profilage")


def onglet_nettoyage() -> None:
    """Affiche le bilan du nettoyage, puis propose le fichier et son rapport."""
    if st.session_state["df_propre"] is None:
        st.info("Réglez les options dans la barre latérale, puis lancez le nettoyage.")
        return

    brut = st.session_state["df_brut"]
    propre = st.session_state["df_propre"]
    stats = st.session_state["stats"]
    illisibles = stats.get("values_unparsed") or {}

    st.subheader("Résultat du nettoyage")

    c1, c2, c3 = st.columns(3)
    c1.metric("Lignes", formater(len(propre)), delta=len(propre) - len(brut))
    c2.metric("Colonnes", propre.shape[1], delta=propre.shape[1] - brut.shape[1])
    manquantes_avant = int(brut.isnull().sum().sum())
    manquantes_apres = int(propre.isnull().sum().sum())
    c3.metric("Valeurs manquantes", formater(manquantes_apres),
              delta=manquantes_apres - manquantes_avant, delta_color="inverse")

    # Une valeur présente devenue manquante ne doit jamais passer inaperçue.
    if illisibles:
        total = sum(int(v.get("count", 0)) for v in illisibles.values())
        st.warning(
            f"**{formater(total)} valeur(s) illisible(s) vidée(s)** lors de la conversion "
            "des types. Elles étaient présentes dans le fichier, mais n'ont pu être "
            "lues dans le type de leur colonne — elles expliquent la hausse du nombre "
            "de valeurs manquantes. Vérifiez-les dans la source :"
        )
        st.dataframe(
            pd.DataFrame([
                {"Colonne": col, "Valeurs vidées": perte.get("count", 0),
                 "Exemples": ", ".join(perte.get("examples", []))}
                for col, perte in illisibles.items()
            ]),
            hide_index=True,
        )

    # Le détail des conversions est affiché d'emblée : c'est l'opération la
    # plus structurante du nettoyage, et la plus susceptible de surprendre.
    conversions = [
        {
            "Colonne": col,
            "Type avant": str(brut[col].dtype),
            "Type après": str(propre[col].dtype),
            "Valeurs illisibles vidées": int((illisibles.get(col) or {}).get("count", 0)),
        }
        for col in brut.columns
        if col in propre.columns and str(brut[col].dtype) != str(propre[col].dtype)
    ]
    st.markdown("**Conversions de types**")
    if conversions:
        st.dataframe(pd.DataFrame(conversions), hide_index=True)
    else:
        st.caption("Aucune colonne n'a changé de type.")

    # Une note ramenée à une autre échelle change de valeur affichée : on le dit.
    echelles = stats.get("grades_rescaled") or {}
    if echelles:
        st.info(
            "**Notes ramenées à une échelle commune.** Ces colonnes mêlaient "
            "plusieurs échelles de notation : chaque note a été exprimée sur "
            "l'échelle la plus fréquente de sa colonne."
        )
        st.dataframe(
            pd.DataFrame([
                {"Colonne": col,
                 "Échelle": f"sur {info.get('scale', 0):g}".replace(".", ","),
                 "Notes ramenées": info.get("count", 0),
                 "Exemples": ", ".join(info.get("examples", []))}
                for col, info in echelles.items()
            ]),
            hide_index=True,
        )

    st.markdown("**Opérations effectuées**")
    lignes = []
    for cle, (libelle, unite) in LIBELLES_STATS.items():
        valeur = stats.get(cle)
        if not valeur:
            continue
        if isinstance(valeur, dict):
            if "ignored" in valeur:
                detail = "non demandé"
            elif cle in ("types_converted", "case_normalized", "types_fixed_pandas"):
                detail = f"{len(valeur)} {unite}"
            else:
                total = 0
                for v in valeur.values():
                    if isinstance(v, dict):
                        total += int(v.get("count", 0))
                    elif isinstance(v, (int, float)):
                        total += int(v)
                    else:
                        total += 1
                detail = f"{formater(total)} {unite}"
        else:
            detail = f"{formater(valeur)} {unite}"
        lignes.append({"Opération": libelle, "Résultat": detail})

    if lignes:
        st.dataframe(pd.DataFrame(lignes), hide_index=True)
    else:
        st.caption("Aucune opération n'a été nécessaire.")

    st.markdown("**Données nettoyées**")
    st.dataframe(propre.head(50), height=340)

    st.divider()
    st.markdown("**📦 Récupérer le résultat**")
    boutons_resultat()

    with st.expander("📄 Lire le rapport de nettoyage"):
        st.markdown(rapport_nettoyage())

    volet_console("nettoyage", "Détail du nettoyage")
    volet_console("bilan", "Rapport console")


def boutons_resultat(emplacement: str = "") -> None:
    """Propose le fichier nettoyé et le rapport de nettoyage au téléchargement.

    Args:
        emplacement: Suffixe des clés de widget, pour placer les mêmes boutons
            dans l'onglet Nettoyage et dans l'onglet Téléchargements.
    """
    propre = st.session_state["df_propre"]
    racine = racine_fichier()
    horodatage = st.session_state["horodatage_nettoyage"]
    gauche, droite = st.columns(2)
    with gauche:
        st.download_button(
            "⬇️ Fichier nettoyé (CSV)",
            # utf-8-sig : Excel a besoin de la marque d'ordre pour afficher les
            # accents correctement. La ligne de commande, elle, reste en utf-8 nu.
            data=lambda: propre.to_csv(index=False).encode("utf-8-sig"),
            file_name=nom_fichier(f"{racine}_nettoye", horodatage, "csv"),
            mime="text/csv",
            on_click="ignore",
            key=f"dl_csv{emplacement}",
            width="stretch",
            type="primary",
            help="Vos données corrigées. Encodé pour qu'Excel affiche correctement les accents.",
        )
    with droite:
        st.download_button(
            "⬇️ Rapport de nettoyage (Markdown)",
            data=lambda: rapport_nettoyage().encode("utf-8"),
            file_name=nom_fichier(f"rapport_nettoyage_{racine}", horodatage, "md"),
            mime="text/markdown",
            on_click="ignore",
            key=f"dl_rapport_nettoyage{emplacement}",
            width="stretch",
            help="Bilan avant/après et détail de chaque opération, colonne par colonne.",
        )


def onglet_telechargements() -> None:
    """Réunit en un seul endroit tout ce qui peut être téléchargé.

    Les mêmes fichiers restent proposés dans leur onglet respectif, là où on
    les consulte ; celui-ci est le récapitulatif, pour tout récupérer d'un coup
    d'œil. Chaque section n'apparaît que lorsque l'étape correspondante a eu lieu.
    """
    st.subheader("Téléchargements")
    st.markdown("Tout ce que Quitus a produit pour votre fichier, réuni ici. Les "
                "rapports existent en deux formats : **HTML** pour les lire, "
                "graphiques inclus, dans n'importe quel navigateur ; **Markdown** "
                "pour les archiver ou les réutiliser, en texte brut, sans graphiques.")

    if st.session_state["profil"] is None:
        st.info("Lancez l'analyse depuis la barre latérale : les rapports "
                "apparaîtront ici au fur et à mesure.")
        section_retours_et_soutien(fichiers_disponibles=False)
        return

    suffixe = "_recap"
    nettoye = st.session_state["df_propre"] is not None

    if nettoye:
        st.markdown("**🧹 Données nettoyées**")
        st.caption("**Le résultat** : vos données corrigées, prêtes à être ouvertes "
                   "dans Excel ou réutilisées (bouton rouge). Le rapport de nettoyage "
                   "l'accompagne. Il compare l'avant et l'après, puis détaille chaque "
                   "opération effectuée, colonne par colonne : doublons supprimés, "
                   "espaces, casse, conversions de types, valeurs comblées ou "
                   "écrêtées. C'est la preuve de ce qui a changé.")
        boutons_resultat(emplacement=suffixe)
        if st.session_state["regles"]:
            st.caption("**Vos contraintes**, au format JSON : à réimporter dans l'onglet "
                       "Contraintes, ou à rejouer en ligne de commande avec `--regles`. "
                       "Leur verdict figure dans le rapport de nettoyage.")
            bouton_export_regles(emplacement=suffixe)
        st.divider()

    st.markdown("**🔍 Rapport avant nettoyage**")
    st.caption("**Le constat de départ** : les données telles qu'elles ont été "
               "reçues, défauts compris. Structure, types détectés, valeurs "
               "manquantes, lignes suspectes, statistiques, valeurs aberrantes et "
               "répartition de chaque colonne.")
    boutons_rapport_profilage(st.session_state["df_brut"], exploratoire=False,
                              prefixe="profilage_avant",
                              horodatage=st.session_state["horodatage_analyse"],
                              apercu=False, emplacement=suffixe)

    if nettoye and st.session_state["profil_post"] is not None:
        st.divider()
        st.markdown("**✅ Rapport après nettoyage**")
        st.caption("**La vérification** : le même examen, refait sur les données "
                   "nettoyées, pour constater que les défauts ont disparu. Il ajoute "
                   "une matrice de dispersion et une carte des corrélations entre "
                   "colonnes numériques.")
        boutons_rapport_profilage(st.session_state["df_propre"], exploratoire=True,
                                  prefixe="profilage_apres",
                                  horodatage=st.session_state["horodatage_nettoyage"],
                                  apercu=False, emplacement=suffixe)
    elif not nettoye:
        st.divider()
        st.caption("Le fichier nettoyé et les rapports de nettoyage et de contrôle "
                   "apparaîtront ici une fois le nettoyage lancé.")

    # Rappel de la convention de nommage : c'est elle qui permet de comparer
    # plusieurs essais sans qu'aucun n'écrase l'autre.
    st.divider()
    st.caption("🕒 Seuls les fichiers du **dernier nettoyage** sont proposés ici : "
               "relancer le nettoyage remplace les précédents sur cette page. "
               "Téléchargez-les avant si vous voulez comparer plusieurs essais. "
               "Sur votre ordinateur, rien ne s'écrase : chaque nom se termine par "
               "la date et l'heure de l'étape qui l'a produit (`AAAAMMJJ_HHMMSS`), "
               "et le fichier nettoyé porte la même marque que ses rapports.")

    section_retours_et_soutien(fichiers_disponibles=True)


def section_retours_et_soutien(fichiers_disponibles: bool) -> None:
    """Termine l'onglet Téléchargements : merci, retours, coup de pouce, contact.

    Toujours affichée, fichier chargé ou non : les moyens de faire un retour
    ou de soutenir le projet ne doivent pas dépendre de l'avancement du
    parcours. Le merci, lui, n'apparaît qu'une fois des fichiers produits —
    remercier quelqu'un qui n'a encore rien fait sonnerait faux.

    Args:
        fichiers_disponibles: Vrai si des fichiers sont déjà proposés au
            téléchargement.
    """
    st.divider()
    if fichiers_disponibles:
        st.markdown("**Merci d'avoir utilisé Quitus !**")
    bloc_retours()
    soutien_et_contact(
        "telechargements",
        "S'il vous a rendu service, un café aide à le faire vivre et à "
        "l'améliorer. C'est entièrement facultatif."
        if fichiers_disponibles else
        "Quitus est gratuit, sans publicité, et ne conserve aucune de vos "
        "données. Si vous voulez encourager son développement, un café "
        "fait toujours plaisir. C'est entièrement facultatif.",
    )


def onglet_controle() -> None:
    """Affiche le profil après nettoyage et vérifie qu'aucun type ne reste douteux.

    C'est la contrepartie du diagnostic initial : le profil avant nettoyage
    constate le désordre, celui-ci atteste sa disparition.
    """
    profil_post = st.session_state["profil_post"]
    if profil_post is None:
        st.info("Lancez le nettoyage pour contrôler le résultat.")
        return

    propre = st.session_state["df_propre"]

    st.subheader("Contrôle après nettoyage")
    st.caption("Ce profil vérifie le travail accompli : après nettoyage, plus "
               "aucune colonne ne devrait rester mal typée.")

    suspectes = find_mistyped_columns(propre)
    if suspectes:
        st.warning(
            f"**{len(suspectes)} colonne(s) semblent encore mal typées.** "
            "Leurs valeurs sont probablement trop hétérogènes pour être converties "
            "sans risque : vérifiez-les dans la source."
        )
    else:
        st.success("✅ Toutes les colonnes sont correctement typées.")

    st.dataframe(
        pd.DataFrame([
            {"Colonne": col, "Type": str(propre[col].dtype),
             "Contrôle": f"⚠️ {suspectes[col]}" if col in suspectes else "✅"}
            for col in propre.columns
        ]),
        hide_index=True,
    )

    afficher_profil(profil_post)

    st.divider()
    st.markdown("**📄 Rapport de profilage après nettoyage**")
    st.caption("Version exploratoire : ajoute la matrice de dispersion et les "
               "corrélations entre colonnes numériques.")
    boutons_rapport_profilage(propre, exploratoire=True, prefixe="profilage_apres",
                              horodatage=st.session_state["horodatage_nettoyage"])

    volet_console("profilage_post", "Détail du profilage")


def supprimer_regle(identifiant: str) -> None:
    """Retire une contrainte de la liste.

    Appelée comme rappel de bouton : l'état est modifié avant la réexécution du
    script, qui affiche donc déjà la liste à jour. Si la contrainte était en
    cours de modification, la modification est abandonnée.

    Args:
        identifiant: Identifiant de la règle à retirer.
    """
    st.session_state["regles"] = [r for r in st.session_state["regles"]
                                  if r["id"] != identifiant]
    st.session_state["contraintes"] = None
    if st.session_state["regle_en_edition"] == identifiant:
        annuler_modification()


def ajouter_regles(nouvelles: list[dict]) -> int:
    """Ajoute des règles à la liste, sans doublon et dans la limite de `MAX_REGLES`.

    Args:
        nouvelles: Règles à ajouter.

    Returns:
        Le nombre de règles réellement ajoutées (les règles déjà présentes ou
        répétées dans le lot, reconnues à leur identifiant, sont ignorées, de
        même que celles qui dépasseraient la limite).
    """
    # Le dédoublonnage porte aussi sur le lot lui-même : deux règles de même
    # identifiant donneraient deux boutons de même clé, et l'affichage échouerait.
    vues = {r["id"] for r in st.session_state["regles"]}
    place = max(MAX_REGLES - len(st.session_state["regles"]), 0)
    ajoutees = []
    for regle in nouvelles:
        if regle["id"] not in vues:
            vues.add(regle["id"])
            ajoutees.append(regle)
    ajoutees = ajoutees[:place]
    st.session_state["regles"] = st.session_state["regles"] + ajoutees
    st.session_state["contraintes"] = None
    return len(ajoutees)


def annuler_modification() -> None:
    """Abandonne la modification en cours et remet le formulaire d'ajout à zéro.

    Appelée comme rappel de bouton, ou quand la contrainte modifiée disparaît.
    """
    st.session_state["regle_en_edition"] = None
    st.session_state["generation_regles"] += 1


def demarrer_modification(identifiant: str) -> None:
    """Passe le formulaire en mode modification, pré-rempli avec la contrainte.

    Appelée comme rappel de bouton : les clés des widgets sont renseignées avant
    la réexécution du script, et le formulaire repart d'une génération neuve
    pour qu'aucune saisie en cours ne se mêle à la contrainte choisie. Une
    colonne qui n'existe plus dans le fichier, ou qui ne convient pas au type de
    règle, n'est pas pré-sélectionnée.

    Args:
        identifiant: Identifiant de la règle à modifier.
    """
    regle = next((r for r in st.session_state["regles"] if r["id"] == identifiant), None)
    if regle is None:
        return
    generation = st.session_state["generation_regles"] + 1
    st.session_state["generation_regles"] = generation
    st.session_state["regle_en_edition"] = identifiant

    type_regle = regle["type"]
    propre = st.session_state["df_propre"]
    # Une colonne absente du fichier, ou qui ne convient plus au type de règle,
    # n'est pas pré-sélectionnée : le formulaire ne propose que des colonnes valides.
    possibles = colonnes_compatibles(propre, type_regle)
    cibles = [c for c in regle["colonnes"] if c in possibles]
    st.session_state[f"regle_{generation}_type"] = type_regle
    mini, maxi = colonnes_attendues(type_regle)
    if mini == 2:
        if len(cibles) == 2 and cibles[1] in colonnes_comparables(propre, cibles[0]):
            st.session_state[f"regle_{generation}_col1"] = cibles[0]
            st.session_state[f"regle_{generation}_col2"] = cibles[1]
    elif maxi is None:
        st.session_state[f"regle_{generation}_cols"] = cibles
    elif cibles:
        st.session_state[f"regle_{generation}_col"] = cibles[0]
    for nom, texte in saisies_depuis_regle(regle).items():
        st.session_state[f"regle_{generation}_{type_regle}_{nom}"] = texte
    if regle.get("libelle"):
        st.session_state[f"regle_{generation}_libelle"] = regle["libelle"]


def champ_de_regle(champ: dict, generation: int, type_regle: str):
    """Affiche le widget d'un champ de règle et renvoie ce qui y est saisi.

    La description du champ vient de `src/saisie_regles.py`, partagée avec le
    terminal : ici, on se borne à choisir le widget qui convient à son genre.

    Args:
        champ: Description du champ.
        generation: Compteur qui entre dans la clé, pour vider les widgets.
        type_regle: Type de règle, qui entre aussi dans la clé : changer de type
            ne doit pas faire survivre une saisie du type précédent.

    Returns:
        Le texte saisi, ou la valeur choisie (chaîne vide pour « aucun »).
    """
    cle = f"regle_{generation}_{type_regle}_{champ['nom']}"
    if champ["genre"] == "choix":
        libelles = dict(champ["choix"])
        options = list(libelles) if champ["obligatoire"] else [""] + list(libelles)
        return st.selectbox(champ["libelle"], options, key=cle, help=champ["aide"],
                            format_func=lambda v: libelles.get(v, "(aucun)"))
    return st.text_input(champ["libelle"], key=cle, help=champ["aide"],
                         placeholder="Payé ; En attente" if champ["genre"] == "liste" else None)


def formulaire_regle(df: pd.DataFrame) -> None:
    """Affiche le formulaire d'ajout, ou de modification, d'une contrainte.

    Ni `st.form` ni autre conteneur qui figerait l'affichage : les champs
    dépendent du type choisi et doivent suivre ce choix immédiatement.

    Seules les colonnes qui conviennent au type choisi sont proposées : une plage
    porte sur des nombres ou des dates, une comparaison sur deux colonnes de même
    nature, jamais sur du texte.

    Args:
        df: Données nettoyées, dont les colonnes sont proposées au choix.
    """
    generation = st.session_state["generation_regles"]
    en_edition = st.session_state["regle_en_edition"]
    if en_edition is None and len(st.session_state["regles"]) >= MAX_REGLES:
        st.info(f"Limite de {MAX_REGLES} contraintes atteinte : retirez-en une pour en ajouter.")
        return

    types = dict(types_disponibles())
    with st.container(border=True):
        st.markdown("**✏️ Modifier la contrainte**" if en_edition else "**➕ Ajouter une contrainte**")
        type_regle = st.selectbox("Quelle contrainte ?", list(types), format_func=types.get,
                                  key=f"regle_{generation}_type")
        mini, maxi = colonnes_attendues(type_regle)
        colonnes = colonnes_compatibles(df, type_regle)
        if not colonnes:
            st.info("Aucune colonne de ce fichier ne convient à cette contrainte : "
                    "elle demande des nombres ou des dates.")
            return
        if mini == 2:
            premiere = st.selectbox("Première colonne", colonnes, key=f"regle_{generation}_col1")
            autres = colonnes_comparables(df, premiere)
            cibles = [premiere, st.selectbox("Seconde colonne", autres,
                                             key=f"regle_{generation}_col2")]
        elif maxi is None:
            cibles = st.multiselect("Colonnes dont la combinaison doit être unique", colonnes,
                                    key=f"regle_{generation}_cols")
        else:
            cibles = [st.selectbox("Colonne", colonnes, key=f"regle_{generation}_col")]

        saisies = {}
        for champ in champs_du_type(type_regle):
            # Un champ « si vide » n'a pas de sens quand l'autre est renseigné.
            if champ["si_vide"] and str(saisies.get(champ["si_vide"], "")).strip():
                continue
            saisies[champ["nom"]] = champ_de_regle(champ, generation, type_regle)
        libelle = st.text_input("Nom de la contrainte (facultatif)",
                                key=f"regle_{generation}_libelle",
                                help="Remplace la description automatique dans les rapports.")

        gauche, droite = st.columns([3, 1])
        if en_edition:
            valider_saisie = gauche.button("Enregistrer les modifications", type="primary",
                                           key=f"regle_{generation}_enregistrer")
            droite.button("Annuler", key=f"regle_{generation}_annuler",
                          on_click=annuler_modification)
        else:
            valider_saisie = gauche.button("Ajouter la contrainte", type="primary",
                                           key=f"regle_{generation}_ajouter")
        if valider_saisie:
            regle, problemes = construire_regle(type_regle, cibles, saisies,
                                                libelle.strip() or None, df=df)
            for probleme in problemes:
                st.error(echapper_markdown(probleme))
            if regle is not None:
                enregistrer_regle(regle, en_edition)


def enregistrer_regle(regle: dict, en_edition: str | None) -> None:
    """Ajoute une contrainte, ou remplace celle qu'on modifie, puis relance l'affichage.

    La contrainte modifiée garde sa place dans la liste. Une contrainte
    identique à une autre déjà présente est refusée, puisque l'identifiant d'une
    règle découle de son contenu.

    Args:
        regle: La contrainte construite, valide.
        en_edition: Identifiant de la contrainte remplacée, ou None pour un ajout.
    """
    regles = st.session_state["regles"]
    if en_edition is None:
        if not ajouter_regles([regle]):
            st.warning("Cette contrainte est déjà dans la liste.")
            return
        message = f"Contrainte ajoutée : {echapper_markdown(decrire_regle(regle))}"
    else:
        position = next((i for i, r in enumerate(regles) if r["id"] == en_edition), None)
        if position is None:  # la contrainte a disparu entre-temps : on l'ajoute
            return enregistrer_regle(regle, None)
        if any(r["id"] == regle["id"] for i, r in enumerate(regles) if i != position):
            st.warning("Une contrainte identique existe déjà dans la liste.")
            return
        st.session_state["regles"] = regles[:position] + [regle] + regles[position + 1:]
        st.session_state["contraintes"] = None
        st.session_state["regle_en_edition"] = None
        message = f"Contrainte modifiée : {echapper_markdown(decrire_regle(regle))}"
    st.session_state["message_regles"] = message
    st.session_state["generation_regles"] += 1
    st.rerun()


def importer_regles() -> None:
    """Propose d'importer des contraintes depuis un fichier JSON exporté plus tôt.

    Le contenu est lu en mémoire : `regles_depuis_texte`, et non
    `charger_regles`, qui lit un chemin sur le disque du serveur.
    """
    generation = st.session_state["generation_import_regles"]
    fichier = st.file_uploader(
        "Importer des contraintes (JSON)", type=["json"], key=f"import_regles_{generation}",
        help="Un fichier exporté depuis cet onglet, ou créé par la ligne de commande. "
             "Les contraintes importées s'ajoutent à celles déjà définies.")
    if fichier is None:
        return
    try:
        # La taille se vérifie avant de lire : un fichier énorme n'est pas chargé.
        if fichier.size > MAX_TAILLE_FICHIER_REGLES:
            raise ValueError(f"fichier de règles trop volumineux ({fichier.size / 1e6:.1f} Mo) : "
                             f"{MAX_TAILLE_FICHIER_REGLES / 1e6:g} Mo au plus")
        nouvelles = regles_depuis_texte(fichier.getvalue().decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        st.error(echapper_markdown(f"Import impossible : {e}"))
        return
    ajoutees = ajouter_regles(nouvelles)
    # Les règles non réalisables restent dans la liste : on prévient seulement
    # l'utilisateur, une fois, à l'entrée.
    st.session_state["avertissement_regles"] = (
        regles_non_realisables(st.session_state["df_propre"], nouvelles) or None)
    st.session_state["message_regles"] = (
        f"{ajoutees} contrainte(s) importée(s)"
        + (f", {len(nouvelles) - ajoutees} déjà présente(s) ignorée(s)." if ajoutees < len(nouvelles) else "."))
    st.session_state["generation_import_regles"] += 1
    st.rerun()


def bouton_export_regles(emplacement: str = "") -> None:
    """Propose les contraintes au téléchargement, en JSON.

    Le fichier est produit en mémoire et part directement vers le navigateur :
    rien n'est écrit sur le serveur.

    Args:
        emplacement: Suffixe de la clé du widget, pour placer le bouton à
            plusieurs endroits.
    """
    regles = st.session_state["regles"]
    st.download_button(
        "⬇️ Contraintes (JSON)",
        data=lambda: regles_vers_texte(regles).encode("utf-8"),
        file_name=nom_fichier(f"contraintes_{racine_fichier()}",
                              st.session_state["horodatage_nettoyage"], "json"),
        mime="application/json",
        on_click="ignore",
        key=f"dl_regles{emplacement}",
        disabled=not regles,
        width="stretch",
        help="Vos contraintes, à réimporter ici une autre fois ou à rejouer en ligne "
             "de commande avec --regles.",
    )


def liste_des_regles(propre: pd.DataFrame) -> None:
    """Affiche les contraintes définies, leur verdict avant et après nettoyage.

    Args:
        propre: Fichier nettoyé, sur lequel s'affichent les lignes en cause.
    """
    regles = st.session_state["regles"]
    if not regles:
        st.caption("Aucune contrainte pour l'instant. Parcourez les données nettoyées "
                   "dans les onglets précédents : une anomalie que vous remarquez, "
                   "une date de fin avant la date de début par exemple, devient une "
                   "contrainte en quelques clics.")
        return

    resultats = contraintes_courantes()
    avant = {r["id"]: r for r in resultats["avant"]["resultats"]}
    apres = {r["id"]: r for r in resultats["apres"]["resultats"]}

    total = resultats["apres"]["total_violations"]
    if total:
        st.warning(f"**{formater(total)} valeur(s) enfreignent encore vos contraintes** "
                   "dans le fichier nettoyé. Quitus les signale sans rien corriger : "
                   "c'est à vous de trancher, dans la source.")
    elif resultats["apres"]["regles_en_erreur"]:
        st.warning("Certaines contraintes n'ont pas pu être évaluées, voir ci-dessous.")
    else:
        st.success("✅ Le fichier nettoyé respecte toutes vos contraintes.")

    entetes = st.columns([6, 2, 2, 1, 1])
    for colonne, titre in zip(entetes, ("Contrainte", "Avant nettoyage", "Après nettoyage", "", "")):
        colonne.caption(titre)
    en_edition = st.session_state["regle_en_edition"]
    for regle in regles:
        nom, rangee_avant, rangee_apres, modif, retrait = st.columns([6, 2, 2, 1, 1])
        nom.markdown(f"**{echapper_markdown(decrire_regle(regle))}**"
                     + ("  \n*(en cours de modification)*" if regle["id"] == en_edition else ""))
        rangee_avant.write(resumer_resultat(avant.get(regle["id"])))
        rangee_apres.write(resumer_resultat(apres.get(regle["id"])))
        modif.button("✏️", key=f"modif_regle_{regle['id']}", on_click=demarrer_modification,
                     args=(regle["id"],), help="Modifier cette contrainte.")
        retrait.button("🗑️", key=f"suppr_regle_{regle['id']}", on_click=supprimer_regle,
                       args=(regle["id"],), help="Retirer cette contrainte.")

    for regle in regles:
        resultat = apres.get(regle["id"])
        if resultat is None or resultat["statut"] == "respectee":
            continue
        with st.expander(f"{'❌' if resultat['statut'] == 'erreur' else '⚠️'} "
                         f"{echapper_markdown(decrire_regle(regle))} : détail"):
            st.write(echapper_markdown(resultat["message"]))
            if resultat["statut"] == "violations":
                lignes = [i for i in resultat["lignes"] if i in propre.index]
                suite = (f" (les {len(lignes)} premières sur {formater(resultat['violations'])})"
                         if resultat["violations"] > len(lignes) else "")
                st.caption(f"Lignes du fichier nettoyé concernées{suite} :")
                st.dataframe(propre.loc[lignes])


def onglet_contraintes() -> None:
    """Définit des contraintes sur les données nettoyées et en montre le verdict.

    Les contraintes viennent en dernier : c'est sur des données propres, déjà
    lues, qu'on repère les anomalies métier qu'aucune machine ne peut deviner.
    Elles sont signalées, jamais corrigées, et ne limitent pas le nettoyage.
    """
    propre = st.session_state["df_propre"]
    if propre is None:
        st.info("Lancez le nettoyage : les contraintes se définissent sur des données "
                "propres, une fois repérées les anomalies que seul un œil humain voit.")
        return

    st.subheader("Contraintes")
    st.caption("Ce que le nettoyage ne peut pas deviner : une date de fin avant la date "
               "de début, un âge de 130 ans, un code postal trop court. Dites à Quitus "
               "ce qui est normal pour vos données, il vous signale ce qui ne l'est pas. "
               "**Il ne corrige rien** : les contraintes n'ont aucun effet sur le "
               "nettoyage. Une case vide n'enfreint jamais une contrainte, sauf « valeur "
               "obligatoire ».")

    message = st.session_state["message_regles"]
    if message:
        st.session_state["message_regles"] = None
        st.success(message, icon="✅")
    alerte = st.session_state["avertissement_regles"]
    if alerte:
        st.session_state["avertissement_regles"] = None
        st.warning(
            f"{len(alerte)} contrainte(s) importée(s) non réalisable(s) sur ce fichier. "
            "Elles restent dans la liste :\n\n"
            + "\n".join(f"- {echapper_markdown(ligne)}" for ligne in alerte),
            icon="⚠️")

    formulaire_regle(propre)
    st.divider()
    liste_des_regles(propre)

    st.divider()
    gauche, droite = st.columns(2)
    with gauche:
        importer_regles()
    with droite:
        st.markdown("&nbsp;")
        bouton_export_regles()
    st.caption("Les contraintes sont aussi reprises dans le rapport de nettoyage "
               "(onglet Nettoyage), à la section « Contraintes ».")


def onglet_graphiques() -> None:
    """Affiche les graphiques, construits à la demande."""
    st.subheader("Visualisations")

    sources = {"Données brutes": st.session_state["df_brut"]}
    if st.session_state["df_propre"] is not None:
        sources["Données nettoyées"] = st.session_state["df_propre"]

    # Une fois le nettoyage fait, c'est le fichier nettoyé qu'on veut voir d'abord.
    choix = st.radio("Jeu de données", list(sources), index=len(sources) - 1,
                     horizontal=True)
    df = sources[choix]

    numeriques = list(df.select_dtypes(include="number").columns)
    categorielles, identifiants = pf.split_categorical_columns(df)

    if not numeriques and not categorielles:
        st.info("Aucune colonne représentable dans ce jeu de données.")
        return

    if numeriques:
        st.markdown("**Colonnes numériques**")
        # Défaut limité à 3 colonnes : un dataset large produirait sinon des
        # dizaines de figures au premier affichage.
        selection = st.multiselect("Colonnes à tracer", numeriques,
                                   default=numeriques[:3], key="sel_num")
        for col in selection:
            st.markdown(f"##### {col}")
            gauche, droite = st.columns([3, 1])
            with gauche:
                afficher_figure(pf.figure_histogram(df, col))
            with droite:
                afficher_figure(pf.figure_boxplot(df, col))

    if categorielles:
        st.markdown("**Colonnes catégorielles**")
        selection = st.multiselect("Colonnes à tracer", categorielles,
                                   default=categorielles[:2], key="sel_cat")
        for col in selection:
            afficher_figure(pf.figure_barplot_top(df, col))

    if identifiants:
        st.caption("Colonnes non tracées, car presque toutes leurs valeurs sont "
                   "distinctes (identifiants) : " + ", ".join(identifiants) + ".")

    if len(numeriques) > 1:
        st.divider()
        st.markdown("**Analyses multivariées**")
        st.caption("Ces graphiques sont coûteux : ils ne sont produits qu'à la demande.")
        gauche, droite = st.columns(2)
        with gauche:
            if st.button("Matrice de dispersion", width="stretch"):
                try:
                    afficher_figure(pf.figure_scatter_matrix(df))
                except ValueError as e:
                    st.warning(str(e))
        with droite:
            if st.button("Corrélations", width="stretch"):
                try:
                    afficher_figure(pf.figure_correlation_heatmap(df))
                except ValueError as e:
                    st.warning(str(e))


# ==========================================================================
# Orchestration
# ==========================================================================

def signature_choix(ecreter, seuils: dict, combler) -> tuple:
    """Résume les choix de nettoyage, pour savoir s'ils ont changé.

    Args:
        ecreter: Colonnes choisies pour l'écrêtage.
        seuils: Seuil IQR de chaque colonne choisie.
        combler: Colonnes choisies pour le remplissage.

    Returns:
        Un tuple comparable, insensible à l'ordre de sélection.
    """
    return (tuple(sorted(ecreter)), tuple(sorted(seuils.items())),
            tuple(sorted(combler)))


def lancer_nettoyage(options: dict) -> None:
    """Exécute le nettoyage, puis le profil de contrôle, et range tout en session.

    Args:
        options: Options choisies dans le formulaire.
    """
    brut = st.session_state["df_brut"]

    try:
        # Le nombre de passes est laissé à la valeur par défaut du moteur : il
        # s'arrête de lui-même dès que plus rien ne change.
        propre, stats = executer_etape(
            "nettoyage", run_all_cleaning_steps,
            brut.copy(),
            profile_info=st.session_state["profil"],
            correct_outliers=bool(options["ecreter"]),
            fill_missing=bool(options["combler"]),
            outlier_columns=options["ecreter"],
            missing_columns=options["combler"],
            outlier_thresholds=options["seuils"],
        )
    except Exception as e:
        st.error(f"Le nettoyage a échoué : {e}")
        volet_console("nettoyage", "Détail de l'échec")
        return

    # Un nouveau nettoyage remplace le précédent : ses calculs sont retirés.
    purger_cache(st.session_state["df_propre"])
    st.session_state["df_propre"] = propre
    st.session_state["stats"] = stats
    st.session_state["etape"] = "nettoye"
    st.session_state["horodatage_nettoyage"] = horodater()
    st.session_state["choix_nettoye"] = signature_choix(
        options["ecreter"], options["seuils"], options["combler"])
    st.session_state["annonce_nettoyage"] = True
    st.session_state["contraintes"] = None  # les données ont changé : à recalculer

    # Rapport console comparatif, capté pour affichage.
    def _bilan():
        journal = CleanLogger(brut, stats)
        journal.update_final_state(propre)
        print(journal.get_summary())

    executer_etape("bilan", _bilan)

    # Profil de contrôle, calculé d'office : c'est lui qui atteste le résultat.
    try:
        profil_post, journal = profiler(propre, exploratoire=True)
        st.session_state["profil_post"] = profil_post
        st.session_state["journaux"]["profilage_post"] = journal
    except Exception as e:
        st.warning(f"Le profilage de contrôle a échoué : {e}")


def afficher_logo() -> None:
    """Affiche le logo en tête de page, lisible sur les deux thèmes.

    Le SVG est inséré dans la page plutôt que chargé comme image : c'est ce
    qui permet à ses couleurs d'hériter du thème de l'application. Si la
    fusion des deux variantes échoue, la variante claire est affichée.

    Par st.markdown et non st.html : ce dernier filtre son contenu avec
    DOMPurify en profil « HTML seul », qui supprime tout SVG — le logo
    disparaissait. Le SVG est mis sur une seule ligne, faute de quoi le
    Markdown prendrait ses lignes indentées pour un bloc de code.
    """
    svg = marque.logo_adaptatif_svg()
    if svg:
        svg = re.sub(r">\s+<", "><", svg)
        st.markdown(f'<div>{svg}</div>',
                    unsafe_allow_html=True)
    else:
        st.image(str(CHEMIN_LOGO), width=LARGEUR_LOGO)


def main() -> None:
    """Point d'entrée de l'application Streamlit."""
    st.set_page_config(
        page_title="Quitus",
        page_icon=str(CHEMIN_ICONE),
        layout="wide",
    )
    # Une balise <style> seule ne prend aucune place dans la page : Streamlit
    # l'envoie dans un conteneur invisible.
    st.html(STYLE_BOUTONS_SOUTIEN)
    st.html(STYLE_TEXTE)
    st.html(STYLE_HAUT_DE_PAGE)

    initialiser_etat()
    options = barre_laterale()

    # Le logo porte le nom et la devise de Quitus : il tient lieu de titre.
    afficher_logo()

    fichier_charge = st.session_state["df_brut"] is not None

    # Les onglets sont affichés dès l'arrivée, fichier chargé ou non : la
    # structure de l'application reste la même d'un bout à l'autre du parcours.
    # Sans cela, un relancement du serveur ou un « Effacer mes données »
    # ramenait sur une page sans onglets, qu'on prenait pour une panne.
    noms_onglets = ["🏠 Présentation", "📋 Aperçu", "🔍 Avant nettoyage",
                    "🧹 Nettoyage", "✅ Après nettoyage", "📐 Contraintes",
                    "📊 Graphiques", "⬇️ Téléchargements"]

    if not fichier_charge:
        onglets = st.tabs(noms_onglets)
        with onglets[0]:
            page_accueil(accueil=True)
        for onglet in onglets[1:]:
            with onglet:
                st.info("Cet onglet s'affichera une fois un fichier chargé : "
                        "déposez-en un dans la barre latérale, ou essayez "
                        "l'exemple fourni depuis l'onglet Présentation.",
                        icon="📂")
        # Retours et soutien restent accessibles au bas de l'onglet
        # Téléchargements, même sans fichier.
        with onglets[-1]:
            section_retours_et_soutien(fichiers_disponibles=False)
        st.divider()
        encart_confidentialite()
        return

    if st.session_state["nom_source"] == CHEMIN_EXEMPLE.name:
        st.info("Vous explorez l'**exemple fourni** : 312 réservations d'hôtel "
                "fictives. Lancez l'analyse depuis la barre latérale, puis le "
                "nettoyage. Pour repartir de zéro, utilisez « Effacer mes données ».",
                icon="🧪")

    if options.get("lancer"):
        lancer_nettoyage(options)
        if st.session_state["annonce_nettoyage"]:
            # Relance le script pour que le bouton, déjà dessiné, s'éteigne.
            st.rerun()

    if st.session_state["annonce_nettoyage"]:
        st.session_state["annonce_nettoyage"] = False
        st.toast("Nettoyage terminé. Résultat dans l'onglet Nettoyage.", icon="✅")

    # La présentation reste le premier onglet : elle ne disparaît pas au
    # premier dépôt de fichier.
    onglets = st.tabs(noms_onglets)
    with onglets[0]:
        page_accueil(accueil=False)
    with onglets[1]:
        onglet_apercu()
    with onglets[2]:
        onglet_profilage()
    with onglets[3]:
        onglet_nettoyage()
    with onglets[4]:
        onglet_controle()
    with onglets[5]:
        onglet_contraintes()
    with onglets[6]:
        onglet_graphiques()
    with onglets[7]:
        onglet_telechargements()

    st.divider()
    encart_confidentialite()


if __name__ == "__main__":
    main()
