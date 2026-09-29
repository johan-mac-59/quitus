"""Fabrique de graphiques, indépendante de toute interface.

Ce module est le point unique de création des figures du projet. Il alimente
aussi bien les rapports HTML (qui ont besoin d'un PNG encodé en base64) que
l'interface Streamlit (qui a besoin d'un objet `Figure` à passer à `st.pyplot`).

**Pourquoi ne pas utiliser pyplot ?**

`plt.figure()` enregistre chaque figure dans le registre global de pyplot
(`Gcf`), d'où elle ne sort que par un `plt.close()` explicite. Dans un processus
de longue durée — un serveur Streamlit qui vit des heures et réexécute le script
à chaque interaction — ce registre grossit indéfiniment, et matplotlib finit par
émettre `RuntimeWarning: More than 20 figures have been opened`. Un `plt.close()`
oublié, ou sauté par une exception, suffit à créer la fuite.

On utilise donc l'API d'embarquement documentée (`Figure` + `FigureCanvasAgg`).
Une figure construite ainsi n'entre jamais dans le registre global : elle est
libérée par le ramasse-miettes dès que plus personne ne la référence. La fuite
devient structurellement impossible au lieu d'être évitée par discipline.

**Règles de cycle de vie à respecter :**

1. Ne jamais importer `matplotlib.pyplot` ailleurs dans `src/`. Un test le
   vérifie (`tests/test_plot_factory.py`).
2. Ne jamais stocker une `Figure` dans `st.session_state` : elle serait retenue
   pendant toute la session, pour chaque session. Stocker les données d'entrée
   et reconstruire la figure à l'affichage.
3. Côté Streamlit, afficher via un helper unique qui libère les artistes
   immédiatement après le rendu (voir `afficher_figure` dans `streamlit_app.py`).
"""

from __future__ import annotations

import base64
import html
from io import BytesIO
from typing import Sequence

import matplotlib

# Doit précéder tout import de backend : aucun backend graphique n'est
# disponible côté serveur, et nous n'en voulons pas non plus en ligne de commande.
matplotlib.use("Agg")

import pandas as pd  # noqa: E402  (après matplotlib.use, volontairement)
import seaborn as sns  # noqa: E402
from matplotlib.backends.backend_agg import FigureCanvasAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402


def new_figure(figsize: tuple[float, float], dpi: int = 100) -> Figure:
    """Crée une figure détachée du registre global de pyplot.

    Args:
        figsize: Dimensions en pouces (largeur, hauteur).
        dpi: Résolution en points par pouce.

    Returns:
        Une figure vierge, munie d'un canevas Agg.
    """
    fig = Figure(figsize=figsize, dpi=dpi)
    # Attacher explicitement le canevas : sans lui, savefig échouerait.
    FigureCanvasAgg(fig)
    return fig


# --------------------------------------------------------------------------
# Constructeurs de figures
# --------------------------------------------------------------------------

def figure_histogram(df: pd.DataFrame, col: str, *,
                     figsize: tuple[float, float] = (7, 3.89),
                     dpi: int = 150) -> Figure:
    """Histogramme avec estimation de densité pour une colonne numérique.

    Args:
        df: Source des données.
        col: Nom de la colonne à tracer.
        figsize: Dimensions en pouces.
        dpi: Résolution.

    Returns:
        La figure construite.
    """
    fig = new_figure(figsize, dpi)
    ax = fig.subplots()
    sns.histplot(df[col].dropna(), kde=True, ax=ax)
    ax.set_title(f"Distribution de {col}")
    fig.tight_layout()
    return fig


def figure_boxplot(df: pd.DataFrame, col: str, *,
                   figsize: tuple[float, float] = (3.5, 3.5),
                   dpi: int = 100) -> Figure:
    """Boîte à moustaches verticale pour une colonne numérique.

    Args:
        df: Source des données.
        col: Nom de la colonne à tracer.
        figsize: Dimensions en pouces.
        dpi: Résolution.

    Returns:
        La figure construite.
    """
    fig = new_figure(figsize, dpi)
    ax = fig.subplots()
    sns.boxplot(y=df[col].dropna(), ax=ax)
    ax.set_title(f"Boxplot de {col}")
    fig.tight_layout()
    return fig


def figure_barplot_top(df: pd.DataFrame, col: str, *, top_n: int = 10,
                       figsize: tuple[float, float] = (10, 4),
                       dpi: int = 120) -> Figure:
    """Diagramme en barres des modalités les plus fréquentes d'une colonne.

    Args:
        df: Source des données.
        col: Nom de la colonne à tracer.
        top_n: Nombre de modalités affichées.
        figsize: Dimensions en pouces.
        dpi: Résolution.

    Returns:
        La figure construite.
    """
    fig = new_figure(figsize, dpi)
    ax = fig.subplots()
    value_counts = df[col].value_counts().head(top_n)
    sns.barplot(x=value_counts.values, y=value_counts.index, ax=ax)
    ax.set_title(f"Répartition de {col}")
    ax.set_xlabel("Nombre d'occurrences")
    fig.tight_layout()
    return fig


def _numeric_columns(df: pd.DataFrame, cols: Sequence[str] | None,
                     max_cols: int | None = None) -> list[str]:
    """Sélectionne les colonnes numériques à représenter.

    Args:
        df: Source des données.
        cols: Colonnes imposées, ou None pour détecter automatiquement.
        max_cols: Plafond du nombre de colonnes retenues.

    Returns:
        La liste des noms de colonnes retenus.
    """
    selected = list(cols) if cols is not None else list(df.select_dtypes(include=["number"]).columns)
    return selected[:max_cols] if max_cols else selected


def figure_scatter_matrix(df: pd.DataFrame, cols: Sequence[str] | None = None, *,
                          max_cols: int = 6, cell_size: float = 2.2,
                          dpi: int = 100) -> Figure:
    """Matrice de dispersion des colonnes numériques.

    La grille est construite à la main plutôt qu'avec `pd.plotting.scatter_matrix`,
    qui crée sa propre figure via un interne pandas et nous ferait retomber dans
    le registre global de pyplot.

    Le nombre de colonnes est plafonné : au-delà, la figure devient illisible et
    son poids explose (l'ancienne version produisait une image de 25×25 pouces,
    soit plusieurs mégaoctets de base64 par rapport).

    Args:
        df: Source des données.
        cols: Colonnes imposées, ou None pour prendre les colonnes numériques.
        max_cols: Nombre maximal de colonnes représentées.
        cell_size: Côté d'une cellule de la grille, en pouces.
        dpi: Résolution.

    Returns:
        La figure construite.

    Raises:
        ValueError: S'il y a moins de deux colonnes numériques exploitables.
    """
    selected = _numeric_columns(df, cols, max_cols)
    if len(selected) < 2:
        raise ValueError("La matrice de dispersion requiert au moins 2 colonnes numériques.")

    data = df[selected].dropna()
    if data.empty:
        raise ValueError("Aucune ligne complète disponible pour la matrice de dispersion.")

    n = len(selected)
    fig = new_figure((cell_size * n, cell_size * n), dpi)
    axes = fig.subplots(n, n, sharex="col")

    for i, y_col in enumerate(selected):
        for j, x_col in enumerate(selected):
            ax = axes[i][j]
            if i == j:
                ax.hist(data[x_col], bins=20)
            else:
                ax.scatter(data[x_col], data[y_col], alpha=0.7, s=6)
            if j == 0:
                ax.set_ylabel(y_col, fontsize=8)
            if i == n - 1:
                ax.set_xlabel(x_col, fontsize=8)
            ax.tick_params(labelsize=6)

    fig.suptitle("Matrice de dispersion", fontsize=12)
    fig.tight_layout()
    return fig


def figure_correlation_heatmap(df: pd.DataFrame, cols: Sequence[str] | None = None, *,
                               figsize: tuple[float, float] = (10, 8),
                               dpi: int = 100) -> Figure:
    """Carte thermique des corrélations entre colonnes numériques.

    Args:
        df: Source des données.
        cols: Colonnes imposées, ou None pour prendre les colonnes numériques.
        figsize: Dimensions en pouces.
        dpi: Résolution.

    Returns:
        La figure construite.

    Raises:
        ValueError: S'il y a moins de deux colonnes numériques exploitables.
    """
    selected = _numeric_columns(df, cols)
    if len(selected) < 2:
        raise ValueError("La heatmap de corrélation requiert au moins 2 colonnes numériques.")

    correlation_matrix = df[selected].corr()

    fig = new_figure(figsize, dpi)
    ax = fig.subplots()
    sns.heatmap(correlation_matrix, annot=True, cmap="coolwarm", center=0,
                square=True, linewidths=0.5, vmin=-1, vmax=1, ax=ax)
    ax.set_title("Heatmap de corrélation")
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------
# Conversion vers le HTML
# --------------------------------------------------------------------------

def figure_to_base64_png(fig: Figure, *, dpi: int | None = None,
                         bbox_inches: str | None = "tight") -> str:
    """Encode une figure en PNG base64, sans passer par le disque.

    Args:
        fig: Figure à encoder.
        dpi: Résolution d'export ; celle de la figure par défaut.
        bbox_inches: Politique de recadrage passée à `savefig`.

    Returns:
        La chaîne base64 du PNG.
    """
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi or fig.dpi, bbox_inches=bbox_inches)
    return base64.b64encode(buffer.getvalue()).decode()


def figure_to_img_tag(fig: Figure, alt: str, style: str = "", **kwargs) -> str:
    """Produit une balise `<img>` autonome contenant la figure.

    Args:
        fig: Figure à intégrer.
        alt: Texte alternatif de l'image.
        style: Style CSS inline appliqué à la balise.
        **kwargs: Transmis à `figure_to_base64_png`.

    Returns:
        Le fragment HTML de la balise image.
    """
    encoded = figure_to_base64_png(fig, **kwargs)
    # Le texte alternatif reprend souvent un nom de colonne, donc une donnée
    # fournie par l'utilisateur : un guillemet y fermerait l'attribut et
    # permettrait d'injecter un gestionnaire d'événement (onerror=...).
    return (f'<img src="data:image/png;base64,{encoded}" '
            f'alt="{html.escape(str(alt), quote=True)}" '
            f'style="{html.escape(str(style), quote=True)}">')
