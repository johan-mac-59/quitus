"""Interface web du pipeline de nettoyage automatique.

Seconde façade du projet, l'autre étant `main.py` (ligne de commande). Ce
module ne contient **aucune logique de nettoyage** : il se contente de
présenter des widgets, d'en transmettre le résultat aux modules de `src/` sous
forme de paramètres, et d'afficher ce qui revient.

Lancement :
    streamlit run app.py

Confidentialité : rien n'est écrit sur le serveur par défaut. Les fichiers
déposés vivent en mémoire pour la durée de la session et repartent vers le
navigateur via les boutons de téléchargement. Voir `encart_confidentialite()`.
"""

from __future__ import annotations

import hashlib
import logging
from types import SimpleNamespace

import pandas as pd
import streamlit as st

from src import plot_factory as pf
from src.cleaner_engine import (
    run_all_cleaning_steps,
    summarize_missing_values,
    summarize_outliers,
)
from src.cleaner_logger import CleanLogger
from src.cleaner_reporter import CleanerReporter
from src.console_capture import capture_output
from src.data_profiler import ExploratoryProfiler, PreCleaningProfiler
from src.file_loader import load_dataframe

# Lien de soutien ; laisser à None pour masquer le bouton.
LIEN_DON = None

EXTENSIONS = ["csv", "xlsx", "xls", "json", "jsonl"]

# Étiquettes lisibles des statistiques de nettoyage, et leur unité.
LIBELLES_STATS = {
    "empty_cols_dropped": ("Colonnes vides supprimées", "colonnes"),
    "whitespace_cleaned": ("Espaces superflus nettoyés", "valeurs"),
    "case_normalized": ("Casse uniformisée", "colonnes"),
    "types_fixed_pandas": ("Types entiers restaurés", "colonnes"),
    "types_converted": ("Types convertis", "colonnes"),
    "duplicates_removed": ("Doublons supprimés", "lignes"),
    "missing_filled": ("Valeurs manquantes comblées", "valeurs"),
    "outliers_corrected": ("Valeurs aberrantes écrêtées", "valeurs"),
}

ETAT_INITIAL = {
    "signature": None,     # empreinte du fichier déposé, détecte un changement
    "nom_source": None,
    "df_brut": None,
    "profil": None,        # le dictionnaire de résultats SEUL, jamais le profileur
    "df_propre": None,
    "stats": None,
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
    for cle in ("profil", "df_propre", "stats"):
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


# ==========================================================================
# Fragments d'interface
# ==========================================================================

def encart_confidentialite() -> None:
    """Affiche la note de transparence sur le traitement des données."""
    with st.expander("🔒 Confidentialité — que devient votre fichier ?"):
        st.markdown(
            """
**Rien n'est enregistré.** Votre fichier est traité en mémoire le temps de
votre session, puis oublié. Aucune copie n'est écrite sur le serveur, sauf si
vous cochez explicitement l'option d'enregistrement local.

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


def barre_laterale() -> dict:
    """Construit la barre latérale et retourne les options choisies.

    Returns:
        Les options de nettoyage et de rapport sélectionnées.
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
        octets = fichier.getvalue()
        signature = hashlib.sha256(octets).hexdigest() + fichier.name

        if signature != st.session_state["signature"]:
            df, journal = charger(octets, fichier.name)
            st.session_state["signature"] = signature
            st.session_state["nom_source"] = fichier.name
            st.session_state["df_brut"] = df
            reinitialiser_aval()
            st.session_state["journaux"]["chargement"] = journal

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

    Les décisions sont présentées comme des cases à cocher plutôt que reprises
    du dialogue terminal : les fonctions `summarize_*` de `cleaner_engine`
    fournissent les données, l'interface choisit sa présentation.

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

        nb_out = sum(res_out["columns"].values())
        ecreter = st.checkbox(
            f"Écrêter les valeurs aberrantes ({nb_out})" if res_out["has_outliers"]
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
            f"Combler les valeurs manquantes ({res_manq['total']})"
            if res_manq["total"] else "Combler les valeurs manquantes",
            value=False,
            disabled=res_manq["total"] == 0,
            help="Médiane pour les colonnes numériques, mode pour les "
                 "catégorielles.",
        )

        iterations = st.number_input(
            "Passes de nettoyage", min_value=1, max_value=10, value=5,
            help="Le nettoyage est itératif : il s'arrête dès que plus rien ne "
                 "change.",
        )

        st.markdown("**Rapports**")
        formats = st.multiselect(
            "Profilage à télécharger", ["Markdown", "HTML"],
            default=["HTML"],
            help="Le HTML embarque les graphiques ; il est autonome et "
                 "partageable par courriel.",
        )
        rapport_nettoyage = st.checkbox("Rapport de nettoyage (Markdown)",
                                        value=True)
        post_profilage = st.selectbox(
            "Analyse après nettoyage", ["Aucune", "Exploratoire"],
            help="L'analyse exploratoire ajoute matrice de dispersion et "
                 "corrélations, utiles pour valider le résultat.",
        )

        enregistrer_disque = st.checkbox(
            "Enregistrer aussi dans data/reports/", value=False,
            help="Décoché, rien n'est écrit sur le serveur. À n'activer qu'en "
                 "usage local.",
        )

        lancer = st.form_submit_button("🧹 Nettoyer", width="stretch",
                                       type="primary")

    return {
        "ecreter": ecreter, "combler": combler, "iterations": int(iterations),
        "formats": formats, "rapport_nettoyage": rapport_nettoyage,
        "post_profilage": post_profilage,
        "enregistrer_disque": enregistrer_disque, "lancer": lancer,
    }


# ==========================================================================
# Onglets
# ==========================================================================

def onglet_apercu() -> None:
    """Affiche un aperçu du fichier brut et ses indicateurs de base."""
    df = st.session_state["df_brut"]
    st.subheader(f"Aperçu de « {st.session_state['nom_source']} »")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Lignes", f"{len(df):,}".replace(",", " "))
    c2.metric("Colonnes", df.shape[1])
    c3.metric("Valeurs manquantes", f"{int(df.isnull().sum().sum()):,}".replace(",", " "))
    c4.metric("Doublons", f"{int(df.duplicated().sum()):,}".replace(",", " "))

    st.dataframe(df.head(50), height=380)
    st.caption(f"50 premières lignes sur {len(df)}.")

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


def onglet_profilage() -> None:
    """Affiche le diagnostic pré-nettoyage."""
    profil = st.session_state["profil"]
    if not profil:
        st.info("Lancez l'analyse depuis la barre latérale pour voir le diagnostic.")
        return

    st.subheader("Diagnostic avant nettoyage")

    forme = profil.get("shape", {})
    c1, c2, c3 = st.columns(3)
    c1.metric("Lignes analysées", forme.get("nb_lignes", "—"))
    c2.metric("Colonnes", forme.get("nb_colonnes", "—"))
    c3.metric("Doublons exacts", profil.get("nb_doublons", 0))

    alertes = (profil.get("row_quality") or {}).get("alerts") or []
    for alerte in alertes:
        message = alerte.get("message", "")
        nombre = alerte.get("count", 0)
        if alerte.get("type") == "row_full_empty":
            st.error(f"{nombre} ligne(s) entièrement vide(s) — {message}")
        else:
            st.warning(f"{nombre} ligne(s) partiellement vide(s) — {message}")

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

    if profil.get("sample_preview"):
        with st.expander("Échantillon des données"):
            # sample_preview est déjà une table Markdown produite par le profileur.
            st.markdown(profil["sample_preview"])

    volet_console("profilage", "Détail du profilage")


def onglet_nettoyage() -> None:
    """Affiche le bilan du nettoyage, avant et après."""
    if st.session_state["df_propre"] is None:
        st.info("Réglez les options dans la barre latérale, puis lancez le nettoyage.")
        return

    brut = st.session_state["df_brut"]
    propre = st.session_state["df_propre"]
    stats = st.session_state["stats"]

    st.subheader("Résultat du nettoyage")

    c1, c2, c3 = st.columns(3)
    c1.metric("Lignes", f"{len(propre):,}".replace(",", " "),
              delta=len(propre) - len(brut))
    c2.metric("Colonnes", propre.shape[1], delta=propre.shape[1] - brut.shape[1])
    manquantes_avant = int(brut.isnull().sum().sum())
    manquantes_apres = int(propre.isnull().sum().sum())
    c3.metric("Valeurs manquantes", f"{manquantes_apres:,}".replace(",", " "),
              delta=manquantes_apres - manquantes_avant, delta_color="inverse")

    st.markdown("**Opérations effectuées**")
    lignes = []
    for cle, (libelle, unite) in LIBELLES_STATS.items():
        valeur = stats.get(cle)
        if not valeur:
            continue
        if isinstance(valeur, dict):
            if "ignored" in valeur:
                detail = "ignoré à votre demande"
            else:
                total = 0
                for v in valeur.values():
                    if isinstance(v, dict):
                        total += int(v.get("count", 0))
                    elif isinstance(v, (int, float)):
                        total += int(v)
                    else:
                        total += 1
                detail = f"{total} {unite}" if total else f"{len(valeur)} {unite}"
        else:
            detail = f"{int(valeur)} {unite}"
        lignes.append({"Opération": libelle, "Résultat": detail})

    if lignes:
        st.dataframe(pd.DataFrame(lignes), hide_index=True)
    else:
        st.caption("Aucune opération n'a été nécessaire.")

    changements = [
        {"Colonne": col, "Avant": str(brut[col].dtype), "Après": str(propre[col].dtype)}
        for col in brut.columns
        if col in propre.columns and str(brut[col].dtype) != str(propre[col].dtype)
    ]
    if changements:
        with st.expander(f"Types modifiés ({len(changements)} colonnes)"):
            st.dataframe(pd.DataFrame(changements), hide_index=True)

    st.dataframe(propre.head(50), height=340)
    volet_console("nettoyage", "Détail du nettoyage")
    volet_console("bilan", "Rapport console")


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


def onglet_telechargements(options: dict) -> None:
    """Propose le dataset nettoyé et les rapports au téléchargement.

    Tout est produit en mémoire : aucune écriture sur le serveur.

    Args:
        options: Options choisies dans le formulaire, notamment les formats
            de rapport demandés.
    """
    st.subheader("Téléchargements")

    if st.session_state["df_propre"] is None:
        st.info("Lancez le nettoyage pour obtenir les fichiers à télécharger.")
        return

    propre = st.session_state["df_propre"]
    racine = (st.session_state["nom_source"] or "donnees").rsplit(".", 1)[0]
    formats = options.get("formats") or []

    st.markdown("**Données nettoyées**")
    st.download_button(
        "⬇️ CSV nettoyé",
        # utf-8-sig : Excel a besoin de la marque d'ordre pour afficher les
        # accents correctement. La ligne de commande, elle, reste en utf-8 nu.
        data=propre.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{racine}_nettoye.csv",
        mime="text/csv",
        width="stretch",
    )

    st.markdown("**Rapports**")
    exploratoire = options.get("post_profilage") == "Exploratoire"

    if "Markdown" in formats:
        st.download_button(
            "⬇️ Profilage (Markdown)",
            data=rendre_rapport(propre, exploratoire, "md").encode("utf-8"),
            file_name=f"profiling_{racine}.md",
            mime="text/markdown",
            width="stretch",
        )

    if "HTML" in formats:
        st.download_button(
            "⬇️ Profilage (HTML, graphiques inclus)",
            data=rendre_rapport(propre, exploratoire, "html").encode("utf-8"),
            file_name=f"profiling_{racine}.html",
            mime="text/html",
            width="stretch",
        )

    if options.get("rapport_nettoyage"):
        # CleanerReporter ne lit qu'un attribut du profileur : un objet factice
        # suffit, ce qui évite de conserver un profileur complet en session.
        factice = SimpleNamespace(profile_results=st.session_state["profil"] or {})
        reporter = CleanerReporter(factice, logging.getLogger("app"),
                                  source_file_path=st.session_state["nom_source"])
        st.download_button(
            "⬇️ Rapport de nettoyage (Markdown)",
            data=reporter.render(st.session_state["stats"]).encode("utf-8"),
            file_name=f"cleaning_report_{racine}.md",
            mime="text/markdown",
            width="stretch",
        )

    if not formats and not options.get("rapport_nettoyage"):
        st.caption("Aucun rapport sélectionné dans les options.")


# ==========================================================================
# Orchestration
# ==========================================================================

def lancer_nettoyage(options: dict) -> None:
    """Exécute le nettoyage et range les résultats en session.

    Args:
        options: Options choisies dans le formulaire.
    """
    brut = st.session_state["df_brut"]

    try:
        propre, stats = executer_etape(
            "nettoyage", run_all_cleaning_steps,
            brut.copy(),
            profile_info=st.session_state["profil"],
            max_iterations=options["iterations"],
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

    # Rapport console comparatif, capté pour affichage.
    def _bilan():
        journal = CleanLogger(brut, stats)
        journal.update_final_state(propre)
        print(journal.get_summary())

    executer_etape("bilan", _bilan)

    if options.get("enregistrer_disque"):
        _enregistrer_sur_disque(options)


def _enregistrer_sur_disque(options: dict) -> None:
    """Écrit les livrables dans `data/` — uniquement sur demande explicite.

    Args:
        options: Options choisies, dont les formats de rapport.
    """
    from pathlib import Path

    base = Path(__file__).parent
    racine = (st.session_state["nom_source"] or "donnees").rsplit(".", 1)[0]

    try:
        sortie = base / "data" / "processed"
        sortie.mkdir(parents=True, exist_ok=True)
        chemin_csv = sortie / f"{racine}_nettoye.csv"
        st.session_state["df_propre"].to_csv(chemin_csv, index=False, encoding="utf-8")

        rapports = base / "data" / "reports"
        rapports.mkdir(parents=True, exist_ok=True)
        ecrits = [chemin_csv]

        exploratoire = options.get("post_profilage") == "Exploratoire"
        for libelle, fmt in (("Markdown", "md"), ("HTML", "html")):
            if libelle in (options.get("formats") or []):
                cible = rapports / f"profiling_{racine}.{fmt}"
                cible.write_text(
                    rendre_rapport(st.session_state["df_propre"], exploratoire, fmt),
                    encoding="utf-8",
                )
                ecrits.append(cible)

        st.success("Enregistré sur le serveur :\n"
                   + "\n".join(f"- `{c.relative_to(base)}`" for c in ecrits))
    except Exception as e:
        st.warning(f"Enregistrement local impossible : {e}")


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
        st.markdown(
            """
Déposez un fichier dans la barre latérale pour commencer.

**Ce que fait cet outil :** il inspecte votre fichier, vous montre ses défauts,
puis les corrige sous votre contrôle — doublons, espaces superflus, casse
incohérente, types mal détectés, formats monétaires, valeurs manquantes et
valeurs aberrantes. Vous repartez avec le fichier propre et un rapport d'audit.

**Formats acceptés :** CSV, Excel (`.xlsx`, `.xls`), JSON et JSON Lines. Le
séparateur et l'encodage sont détectés automatiquement.
"""
        )
        encart_confidentialite()
        return

    if options.get("lancer"):
        lancer_nettoyage(options)

    onglets = st.tabs(["📋 Aperçu", "🔍 Profilage", "🧹 Nettoyage",
                       "📊 Graphiques", "⬇️ Téléchargements"])
    with onglets[0]:
        onglet_apercu()
    with onglets[1]:
        onglet_profilage()
    with onglets[2]:
        onglet_nettoyage()
    with onglets[3]:
        onglet_graphiques()
    with onglets[4]:
        onglet_telechargements(options)

    st.divider()
    encart_confidentialite()


if __name__ == "__main__":
    main()
