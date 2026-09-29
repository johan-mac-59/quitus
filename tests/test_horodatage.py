"""Tests de l'horodatage des fichiers produits.

Deux garanties : l'ordre alphabétique des noms est l'ordre chronologique, et
tous les fichiers d'une même exécution partagent la même marque — ce qui permet
de comparer plusieurs essais sans qu'aucun n'écrase le précédent.
"""

import re
from datetime import datetime
from pathlib import Path

from src.cleaner_reporter import build_cleaning_report_path
from src.data_profiler import build_report_path
from src.horodatage import FORMAT_HORODATAGE, horodater

MOTIF = re.compile(r"^\d{8}_\d{6}$")


class TestHorodater:
    def test_format(self):
        """Le suffixe suit le format AAAAMMJJ_HHMMSS."""
        assert MOTIF.match(horodater())

    def test_instant_impose(self):
        """Un instant fourni est représenté exactement."""
        assert horodater(datetime(2026, 9, 29, 14, 32, 7)) == "20260929_143207"

    def test_ordre_alphabetique_egal_ordre_chronologique(self):
        """Trier les noms revient à les classer dans le temps."""
        instants = [datetime(2026, 1, 2, 9, 0, 0), datetime(2025, 12, 31, 23, 59, 59),
                    datetime(2026, 1, 2, 8, 59, 59), datetime(2026, 1, 2, 9, 0, 1)]
        assert sorted(horodater(i) for i in instants) == [horodater(i) for i in sorted(instants)]

    def test_precision_a_la_seconde(self):
        """Deux essais dans la même minute ne produisent pas le même suffixe.

        L'ancien format, à la minute, faisait écraser le premier essai.
        """
        assert (horodater(datetime(2026, 9, 29, 14, 32, 7))
                != horodater(datetime(2026, 9, 29, 14, 32, 8)))

    def test_format_expose(self):
        """Le format est exposé comme constante, pour qui voudrait le relire."""
        assert datetime.strptime(horodater(), FORMAT_HORODATAGE)


class TestMarqueCommuneAUneExecution:
    """Un suffixe imposé est repris tel quel par tous les chemins de rapport."""

    def test_rapport_de_profilage(self):
        """Le rapport de profilage reprend le suffixe imposé."""
        chemin = build_report_path(Path("r"), Path("ventes.csv"), "md",
                                   horodatage="20260929_143207")
        assert chemin.name == "profiling_ventes_20260929_143207.md"

    def test_rapport_de_nettoyage(self):
        """Le rapport de nettoyage reprend le même suffixe."""
        chemin = build_cleaning_report_path(Path("r"), Path("ventes.csv"),
                                            horodatage="20260929_143207")
        assert chemin.name == "cleaning_report_ventes_20260929_143207.md"

    def test_suffixe_par_defaut(self):
        """Sans suffixe imposé, l'instant présent est utilisé."""
        chemin = build_report_path(Path("r"), Path("ventes.csv"), "html")
        assert MOTIF.match(chemin.stem.removeprefix("profiling_ventes_"))


class TestLigneDeCommande:
    """Le fichier nettoyé ne doit plus porter un nom fixe, écrasé à chaque essai."""

    def test_sortie_par_defaut_horodatee(self, tmp_path):
        """Sans --output, le fichier nettoyé porte le nom de la source et la marque."""
        import main

        args = main.construire_parseur().parse_args(
            ["--input", "data/samples/reservations_exemple.csv",
             "--reports", str(tmp_path)])
        _, sortie, _ = main.resoudre_chemins(args, "20260929_143207")
        assert sortie.name == "reservations_exemple_nettoye_20260929_143207.csv"

    def test_sortie_explicite_respectee(self, tmp_path):
        """Un chemin --output explicite est respecté tel quel."""
        import main

        cible = tmp_path / "mon_fichier.csv"
        args = main.construire_parseur().parse_args(
            ["--input", "data/samples/reservations_exemple.csv",
             "--output", str(cible), "--reports", str(tmp_path)])
        _, sortie, _ = main.resoudre_chemins(args, "20260929_143207")
        assert sortie == cible
