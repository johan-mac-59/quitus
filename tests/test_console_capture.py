"""Tests de la capture de sortie console."""

import logging
import sys

import pytest

from src.console_capture import capture_output


class TestCaptureOutput:
    def test_capture_stdout(self):
        """Un print effectué dans le contexte atterrit dans le tampon."""
        with capture_output() as buf:
            print("bonjour")
        assert "bonjour" in buf.getvalue()

    def test_capture_stderr(self):
        """Une écriture sur stderr est également captée."""
        with capture_output() as buf:
            print("attention", file=sys.stderr)
        assert "attention" in buf.getvalue()

    def test_capture_logging(self):
        """Les messages du journal racine sont captés, avec leur niveau."""
        with capture_output() as buf:
            logging.getLogger("test").info("message journalise")
        contenu = buf.getvalue()
        assert "message journalise" in contenu
        assert "INFO" in contenu

    def test_logging_non_capte_si_desactive(self):
        """capture_logging=False laisse le journal suivre son cours."""
        with capture_output(capture_logging=False) as buf:
            logging.getLogger("test").info("invisible")
        assert "invisible" not in buf.getvalue()

    def test_restaure_stdout(self):
        """La sortie standard est rendue intacte après le contexte."""
        avant = sys.stdout
        with capture_output():
            pass
        assert sys.stdout is avant

    def test_restaure_stdout_meme_sur_exception(self):
        """La restauration a lieu même si le bloc lève."""
        avant = sys.stdout
        with pytest.raises(ValueError):
            with capture_output():
                raise ValueError("boum")
        assert sys.stdout is avant

    def test_retire_le_handler_de_logging(self):
        """Aucun handler résiduel n'est laissé sur le journal racine."""
        avant = len(logging.getLogger().handlers)
        with capture_output():
            pass
        assert len(logging.getLogger().handlers) == avant

    def test_restaure_le_niveau_de_logging(self):
        """Le niveau du journal racine est restauré."""
        root = logging.getLogger()
        avant = root.level
        with capture_output():
            pass
        assert root.level == avant

    def test_capture_une_etape_de_pipeline(self):
        """Cas d'usage réel : capter la sortie d'une fonction bavarde de src/."""
        import numpy as np
        import pandas as pd

        from src.cleaner_engine import run_all_cleaning_steps

        df = pd.DataFrame({"a": [1, 1, 2], "b": ["  x ", "y", np.nan]})
        with capture_output() as buf:
            run_all_cleaning_steps(df, correct_outliers=False, fill_missing=False)

        # run_all_cleaning_steps annonce chaque itération
        assert "Itération" in buf.getvalue() or "itération" in buf.getvalue()
