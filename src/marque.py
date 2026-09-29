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
