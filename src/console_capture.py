"""Capture de la sortie console, pour la réafficher dans une interface graphique.

Les modules de `src/` communiquent leur progression par `print()`, ce qui
convient parfaitement en ligne de commande. Dans un navigateur, cette sortie
est simplement perdue : elle part dans la console du serveur, que l'utilisateur
ne voit pas.

Ce module permet de la détourner vers un tampon mémoire, que l'interface web
affiche ensuite dans un volet dépliable. Le pipeline reste ainsi bavard et
traçable, sans qu'aucun module métier n'ait à connaître Streamlit.
"""

from __future__ import annotations

import contextlib
import io
import logging
from typing import Iterator


@contextlib.contextmanager
def capture_output(*, capture_logging: bool = True) -> Iterator[io.StringIO]:
    """Détourne stdout, stderr et le journal racine vers un tampon mémoire.

    Le traitement explicite du module `logging` n'est pas redondant avec la
    redirection de `stderr` : un `StreamHandler` créé avant l'entrée dans ce
    contexte a capturé la référence à `sys.stderr` à sa construction, et
    continuerait donc d'écrire dans la vraie sortie d'erreur. C'est le cas du
    journal utilisé par `generate_enhanced_report`.

    À utiliser autour d'une étape de pipeline précise, jamais autour d'appels
    d'affichage de l'interface : une exception levée dans le bloc verrait sa
    trace absorbée par le tampon au lieu de remonter au gestionnaire d'erreurs.

    Args:
        capture_logging: Détourne également les messages du journal racine.

    Yields:
        Le tampon recevant la sortie ; `getvalue()` en donne le contenu.
    """
    buffer = io.StringIO()

    handler = None
    root_logger = logging.getLogger()
    previous_level = root_logger.level

    if capture_logging:
        handler = logging.StreamHandler(buffer)
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        root_logger.addHandler(handler)
        # Sans niveau explicite, un logger racine non configuré filtre les INFO.
        if previous_level > logging.INFO or previous_level == logging.NOTSET:
            root_logger.setLevel(logging.INFO)

    try:
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            yield buffer
    finally:
        if handler is not None:
            root_logger.removeHandler(handler)
            root_logger.setLevel(previous_level)
            handler.close()
