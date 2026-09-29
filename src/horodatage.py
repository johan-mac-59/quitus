"""Horodatage des fichiers produits.

Tous les fichiers issus d'une même exécution — fichier nettoyé, rapport de
nettoyage, rapports de profilage — portent le même suffixe. On peut ainsi
comparer plusieurs essais (avec et sans écrêtage, avec et sans remplissage)
sans qu'aucun n'écrase le précédent, et retrouver d'un coup d'œil les fichiers
qui vont ensemble.

Le format `AAAAMMJJ_HHMMSS` a deux propriétés voulues :

* l'ordre alphabétique des noms de fichiers est aussi l'ordre chronologique ;
* la précision à la seconde évite qu'un second essai lancé dans la même minute
  écrase le premier — ce qui arrivait avec l'ancien format à la minute.
"""

from __future__ import annotations

from datetime import datetime

FORMAT_HORODATAGE = "%Y%m%d_%H%M%S"


def horodater(moment: datetime | None = None) -> str:
    """Produit le suffixe d'horodatage d'un nom de fichier.

    Args:
        moment: Instant à représenter ; l'instant présent si omis.

    Returns:
        Le suffixe au format `AAAAMMJJ_HHMMSS`, par exemple `20260929_143207`.
    """
    return (moment or datetime.now()).strftime(FORMAT_HORODATAGE)
