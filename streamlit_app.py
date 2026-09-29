"""Interface web du pipeline de nettoyage automatique.

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
import logging
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import streamlit as st

from src import plot_factory as pf
from src.cleaner_engine import (
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

# Lien de soutien ; laisser à None pour masquer le bouton.
LIEN_DON = None

EXTENSIONS = ["csv", "xlsx", "xls", "json", "jsonl"]

# Échantillon synthétique versionné avec le dépôt : il permet d'essayer l'outil
# sans avoir de fichier sous la main. Aucune donnée personnelle.
CHEMIN_EXEMPLE = Path(__file__).parent / "data" / "samples" / "reservations_exemple.csv"

LIEN_DEPOT = "https://github.com/johan-mac-59/PROJET_NETTOYAGE_AUTO"

# Étiquettes lisibles des statistiques de nettoyage, et leur unité.
LIBELLES_STATS = {
    "empty_cols_dropped": ("Colonnes vides supprimées", "colonnes"),
    "whitespace_cleaned": ("Espaces superflus nettoyés", "valeurs"),
    "case_normalized": ("Casse uniformisée", "colonnes"),
    "types_fixed_pandas": ("Types entiers restaurés", "colonnes"),
    "types_converted": ("Types convertis", "colonnes"),
    "values_unparsed": ("Valeurs illisibles vidées", "valeurs"),
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
}


# ==========================================================================
# État de session
# ==========================================================================

def initialiser_etat() -> None:
    """Installe les clés d'état manquantes, sans écraser l'existant."""
    for cle, valeur in ETAT_INITIAL.items():
        if cle not in st.session_state:
            st.session_state[cle] = valeur.copy() if isinstance(valeur, dict) else valeur


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


def tout_effacer() -> None:
    """Vide l'état de session, le cache partagé et le fichier déposé.

    C'est le droit à l'effacement rendu opérationnel en un clic : le cache de
    Streamlit est global au processus, donc une entrée survit à la session qui
    l'a créée si on ne la purge pas explicitement.

    Le composant d'envoi doit être renouvelé, et non seulement l'état vidé :
    il conserve sinon le fichier déposé, qui serait rechargé au rafraîchissement
    suivant — l'effacement n'aurait alors aucun effet visible.
    """
    generation = st.session_state.get("generation_envoi", 0) + 1

    for cle in ETAT_INITIAL:
        st.session_state.pop(cle, None)
    # La clé du composant d'envoi lui-même, désormais orpheline.
    st.session_state.pop(f"envoi_{generation - 1}", None)

    st.cache_data.clear()
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


@st.cache_data(show_spinner="Chargement du fichier…", **CACHE)
def charger(octets: bytes, nom: str) -> tuple[pd.DataFrame, str]:
    """Charge un fichier déposé, avec détection du format et de l'encodage.

    Args:
        octets: Contenu brut du fichier.
        nom: Nom du fichier, dont l'extension détermine le format.

    Returns:
        Le DataFrame chargé et la sortie console de l'opération.
    """
    with capture_output() as tampon:
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
    return reporter.render(st.session_state["stats"])


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
la session et le cache.

⚠️ Par prudence, évitez de déposer des données personnelles sensibles.
"""
        )


def page_accueil(accueil: bool = True) -> None:
    """Présente le projet : sur la page d'accueil, puis dans le premier onglet.

    Une page d'accueil vide laisse le visiteur sans prise. Celle-ci explique le
    problème traité, montre ce que l'outil corrige sur des exemples concrets,
    énonce ses principes, raconte comment il est né — et propose de l'essayer
    immédiatement sur un exemple, sans fichier à fournir.

    Une fois un fichier chargé, la même présentation reste consultable dans
    l'onglet « Présentation » : elle ne disparaît pas au premier dépôt.

    Args:
        accueil: Vrai sur la page d'accueil, avant tout dépôt. Faux dans
            l'onglet « Présentation » : le bouton d'essai y est remplacé par un
            simple rappel (il remplacerait le fichier en cours), et l'encart de
            confidentialité, déjà affiché en bas de page, n'est pas répété.
    """
    st.markdown(
        "### Déposez un fichier dont vous ne savez rien.\n"
        "### Repartez avec un fichier propre — et la preuve qu'il l'est."
    )
    st.markdown(
        "Encodage, séparateur, types, doublons, formats monétaires, dates "
        "incohérentes : l'outil inspecte votre fichier sans rien savoir de lui "
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
                       "CSV, Excel, JSON ou JSON Lines, 200 Mo au plus.")
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
        {"Dans le fichier reçu": '"5/5", "17/20", "78,5 %"',
         "Après nettoyage": "5 · 17 · 78.5", "Ce qui a été fait": "Notes et pourcentages chiffrés"},
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
                        "qu'avec votre accord, case par case."),
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

    if accueil:
        encart_confidentialite()


def barre_laterale() -> dict:
    """Construit la barre latérale et retourne les options choisies.

    Returns:
        Les options de nettoyage sélectionnées.
    """
    st.sidebar.title("🧹 Nettoyage automatique")

    fichier = st.sidebar.file_uploader(
        "Déposez un fichier",
        type=EXTENSIONS,
        key=f"envoi_{st.session_state['generation_envoi']}",
        help="CSV, Excel, JSON ou JSON Lines. Le séparateur et l'encodage sont "
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
        st.sidebar.link_button("☕ Soutenir le projet", LIEN_DON, width="stretch")
        st.sidebar.caption("Redirige vers un prestataire externe. "
                           "Cette application ne voit aucune donnée de paiement.")

    return options


def formulaire_options(df: pd.DataFrame) -> dict:
    """Construit le formulaire des options de nettoyage.

    Seules les deux décisions qui altèrent les données sont exposées. Tout le
    reste — doublons, espaces, casse, types — est corrigé d'office, et le
    nombre de passes est laissé au moteur, qui s'arrête dès que plus rien ne
    change.

    Args:
        df: DataFrame brut, pour calculer les diagnostics affichés en aide.

    Returns:
        Les options choisies et un drapeau indiquant si le nettoyage est demandé.
    """
    profil = st.session_state["profil"]
    res_out = summarize_outliers(df, {}, profil)
    res_manq = summarize_missing_values(df)

    with st.sidebar.form("options"):
        st.markdown("**Options de nettoyage**")
        st.caption("Doublons, espaces, casse et types sont corrigés d'office. "
                   "Les deux traitements ci-dessous modifient les valeurs : "
                   "ils ne sont appliqués qu'avec votre accord.")

        nb_out = sum(res_out["columns"].values())
        ecreter = st.checkbox(
            f"Écrêter les valeurs aberrantes ({formater(nb_out)})" if res_out["has_outliers"]
            else "Écrêter les valeurs aberrantes",
            value=False,
            disabled=not res_out["has_outliers"],
            help="Méthode IQR. Ramène les valeurs extrêmes dans les bornes "
                 "statistiques. Modifie les distributions."
                 + ("\n\n" + "\n".join(f"- {c} : {n}"
                                       for c, n in res_out["columns"].items())
                    if res_out["has_outliers"] else ""),
        )

        combler = st.checkbox(
            f"Combler les valeurs manquantes ({formater(res_manq['total'])})"
            if res_manq["total"] else "Combler les valeurs manquantes",
            value=False,
            disabled=res_manq["total"] == 0,
            help="Médiane pour les colonnes numériques, mode pour les "
                 "catégorielles.\n\n⚠️ Une absence peut avoir un sens : un "
                 "produit en rupture n'a pas de prix, un champ non applicable "
                 "est vide à dessein. La combler invente une valeur.",
        )

        lancer = st.form_submit_button("🧹 Nettoyer", width="stretch",
                                       type="primary")

    return {"ecreter": ecreter, "combler": combler, "lancer": lancer}


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
                anomalies = infos.get("format_anomalies") or []
                icone = "⚠️" if anomalies else "✅"
                st.markdown(
                    f"{icone} **{col}** — {infos.get('cardinality_absolute', 0)} "
                    f"modalités ({infos.get('cardinality_relative', 0)} % du total)"
                )
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
        )


def onglet_telechargements() -> None:
    """Réunit en un seul endroit tout ce qui peut être téléchargé.

    Les mêmes fichiers restent proposés dans leur onglet respectif, là où on
    les consulte ; celui-ci est le récapitulatif, pour tout récupérer d'un coup
    d'œil. Chaque section n'apparaît que lorsque l'étape correspondante a eu lieu.
    """
    st.subheader("Téléchargements")

    if st.session_state["profil"] is None:
        st.info("Lancez l'analyse depuis la barre latérale : les rapports "
                "apparaîtront ici au fur et à mesure.")
        return

    suffixe = "_recap"
    nettoye = st.session_state["df_propre"] is not None

    if nettoye:
        st.markdown("**🧹 Données nettoyées**")
        boutons_resultat(emplacement=suffixe)
        st.divider()

    st.markdown("**🔍 Rapport avant nettoyage**")
    st.caption("Le diagnostic des données telles qu'elles ont été reçues.")
    boutons_rapport_profilage(st.session_state["df_brut"], exploratoire=False,
                              prefixe="profilage_avant",
                              horodatage=st.session_state["horodatage_analyse"],
                              apercu=False, emplacement=suffixe)

    if nettoye and st.session_state["profil_post"] is not None:
        st.divider()
        st.markdown("**✅ Rapport après nettoyage**")
        st.caption("Le profil de contrôle, avec matrice de dispersion et corrélations.")
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
    st.caption("🕒 Chaque nom de fichier se termine par la date et l'heure de "
               "l'étape qui l'a produit (`AAAAMMJJ_HHMMSS`). Relancez le nettoyage "
               "avec d'autres options : les nouveaux fichiers ne remplaceront pas "
               "les précédents, et le fichier nettoyé partage la marque de ses "
               "rapports.")


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


def onglet_graphiques() -> None:
    """Affiche les graphiques, construits à la demande."""
    st.subheader("Visualisations")

    sources = {"Données brutes": st.session_state["df_brut"]}
    if st.session_state["df_propre"] is not None:
        sources["Données nettoyées"] = st.session_state["df_propre"]

    choix = st.radio("Jeu de données", list(sources), horizontal=True)
    df = sources[choix]

    numeriques = list(df.select_dtypes(include="number").columns)
    categorielles = list(df.select_dtypes(include=["object", "string", "category"]).columns)

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
            correct_outliers=options["ecreter"],
            fill_missing=options["combler"],
        )
    except Exception as e:
        st.error(f"Le nettoyage a échoué : {e}")
        volet_console("nettoyage", "Détail de l'échec")
        return

    st.session_state["df_propre"] = propre
    st.session_state["stats"] = stats
    st.session_state["etape"] = "nettoye"
    st.session_state["horodatage_nettoyage"] = horodater()

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


def main() -> None:
    """Point d'entrée de l'application Streamlit."""
    st.set_page_config(
        page_title="Nettoyage automatique de données",
        page_icon="🧹",
        layout="wide",
    )

    initialiser_etat()
    options = barre_laterale()

    st.title("🧹 Nettoyage automatique de données")

    if st.session_state["df_brut"] is None:
        page_accueil()
        return

    if st.session_state["nom_source"] == CHEMIN_EXEMPLE.name:
        st.info("Vous explorez l'**exemple fourni** : 312 réservations d'hôtel "
                "fictives. Lancez l'analyse depuis la barre latérale, puis le "
                "nettoyage. Pour repartir de zéro, utilisez « Effacer mes données ».",
                icon="🧪")

    if options.get("lancer"):
        lancer_nettoyage(options)

    # La présentation reste le premier onglet : elle ne disparaît pas au
    # premier dépôt de fichier.
    onglets = st.tabs(["🏠 Présentation", "📋 Aperçu", "🔍 Avant nettoyage",
                       "🧹 Nettoyage", "✅ Après nettoyage", "📊 Graphiques",
                       "⬇️ Téléchargements"])
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
        onglet_graphiques()
    with onglets[6]:
        onglet_telechargements()

    st.divider()
    encart_confidentialite()


if __name__ == "__main__":
    main()
