"""Identité de Quitus : nom, devise et logo, pour l'application et les rapports.

Le logo est intégré aux rapports sous forme d'URI `data:` plutôt que référencé
par un chemin : un rapport téléchargé doit rester autonome, et s'afficher avec
son en-tête où qu'on l'ouvre. C'est aussi ce qu'autorise la politique de
sécurité des rapports HTML (`img-src data:`), qui interdit tout chargement
externe.

Si le fichier du logo est absent — module utilisé hors du dépôt, par exemple —,
les en-têtes retombent sur une version texte : un rapport ne doit jamais
échouer pour une question d'habillage.
"""

from __future__ import annotations

import base64
from functools import lru_cache
from html import escape
from pathlib import Path

NOM = "Quitus"
DEVISE = "Le fichier propre, et la preuve."

CHEMIN_LOGO = Path(__file__).resolve().parent.parent / "assets" / "quitus-logo-light.svg"
CHEMIN_LOGO_SOMBRE = CHEMIN_LOGO.with_name("quitus-logo-dark.svg")

_ESPACE_SVG = "http://www.w3.org/2000/svg"

# Texte alternatif : ce qu'on lit si l'image ne s'affiche pas.
_TEXTE_ALTERNATIF = f"{NOM} — {DEVISE}"


@lru_cache(maxsize=1)
def logo_data_uri() -> str | None:
    """Encode le logo en URI `data:` intégrable dans un rapport.

    Returns:
        L'URI `data:image/svg+xml;base64,…`, ou None si le logo est introuvable.
    """
    try:
        contenu = CHEMIN_LOGO.read_bytes()
    except OSError:
        return None
    return "data:image/svg+xml;base64," + base64.b64encode(contenu).decode("ascii")


@lru_cache(maxsize=1)
def logo_adaptatif_svg() -> str | None:
    """Fusionne les variantes claire et sombre du logo en un seul SVG.

    Chaque couleur qui diffère entre les deux variantes devient une valeur
    CSS `light-dark(claire, sombre)`, que le navigateur résout selon le
    `color-scheme` de l'élément parent. Streamlit fixe ce `color-scheme` sur
    le conteneur de l'application selon le thème réellement affiché : le logo
    suit donc le thème, y compris quand le visiteur en change, sans que Python
    ait à le deviner.

    L'attribut de couleur d'origine est conservé : un navigateur qui ignore
    `light-dark()` affiche simplement la variante claire. Une couleur absente
    d'une variante s'écrit `transparent` : `light-dark()` n'accepte que des
    couleurs, et `none` y invaliderait toute la déclaration.

    Returns:
        Le code SVG, ou None si une variante manque ou si leurs structures
        divergent au point de ne plus pouvoir être appariées.
    """
    import xml.etree.ElementTree as ET

    try:
        clair = ET.parse(CHEMIN_LOGO).getroot()
        sombre = ET.parse(CHEMIN_LOGO_SOMBRE).getroot()
    except (OSError, ET.ParseError):
        return None

    elements_clairs, elements_sombres = list(clair.iter()), list(sombre.iter())
    if [e.tag for e in elements_clairs] != [e.tag for e in elements_sombres]:
        return None

    for el_clair, el_sombre in zip(elements_clairs, elements_sombres):
        regles = []
        for attribut in ("fill", "stroke"):
            valeur_claire = el_clair.get(attribut, "transparent")
            valeur_sombre = el_sombre.get(attribut, "transparent")
            if valeur_claire != valeur_sombre:
                regles.append(f"{attribut}: light-dark({valeur_claire}, {valeur_sombre})")
        # Un contour propre à la variante sombre garde son épaisseur.
        if "stroke-width" in el_sombre.attrib and "stroke-width" not in el_clair.attrib:
            el_clair.set("stroke-width", el_sombre.get("stroke-width"))
        if regles:
            el_clair.set("style", "; ".join(regles))

    ET.register_namespace("", _ESPACE_SVG)
    clair.set("role", "img")
    clair.set("aria-label", _TEXTE_ALTERNATIF)
    return ET.tostring(clair, encoding="unicode")


def en_tete_html() -> str:
    """Produit l'en-tête HTML des rapports : le logo, ou son équivalent texte.

    Returns:
        Le fragment HTML de l'en-tête.
    """
    uri = logo_data_uri()
    if uri:
        return (f'<div style="margin-bottom: 12px;">'
                f'<img src="{uri}" alt="{escape(_TEXTE_ALTERNATIF, quote=True)}" '
                f'style="height: 56px; width: auto;"></div>')
    return (f'<p style="margin-bottom: 12px;"><strong>{escape(NOM)}</strong> — '
            f'<em>{escape(DEVISE)}</em></p>')


def en_tete_markdown() -> str:
    """Produit l'en-tête Markdown des rapports : le logo, ou son équivalent texte.

    Le texte alternatif de l'image reprend le nom et la devise : un lecteur
    Markdown qui n'affiche pas les images montre alors la marque en clair.

    Returns:
        Le fragment Markdown de l'en-tête, suivi d'une ligne vide.
    """
    uri = logo_data_uri()
    if uri:
        return f"![{_TEXTE_ALTERNATIF}]({uri})\n\n"
    return f"**{NOM}** — *{DEVISE}*\n\n"
