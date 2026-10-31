"""Verrouille la garantie : un code écrit avec un zéro initial reste du texte.

Un numéro de téléphone (« 0612345678 »), un code postal (« 01000 ») ou un
matricule (« 00042 ») ont l'air de nombres, mais n'en sont pas : les convertir
en entier supprime leur zéro initial. La perte est silencieuse, aucune valeur ne
devient manquante, et le profil de contrôle n'y voit qu'une colonne bien typée.

Le zéro se perdait à trois endroits, tous couverts ici :

* au chargement d'un CSV, que pandas lit directement en `int64` ;
* au chargement d'un JSON, où `read_json` convertit les chaînes en nombres ;
* au nettoyage, quand `clean_types` convertit une colonne restée textuelle
  (cas d'un JSON Lines ou d'un classeur Excel aux cellules de type texte).
"""

import json
from io import BytesIO

import pandas as pd
import pytest

from src.cleaner_engine import (
    clean_types,
    find_mistyped_columns,
    has_leading_zero,
    run_all_cleaning_steps,
)
from src.file_loader import load_dataframe

_ENREGISTREMENTS = [
    {"nom": "A", "tel": "0612345678", "cp": "01000", "montant": 12},
    {"nom": "B", "tel": "0798765432", "cp": "75001", "montant": 13},
]


def _csv() -> bytes:
    """Fichier CSV des enregistrements de référence.

    Returns:
        Le contenu du fichier, en octets.
    """
    return ("nom;tel;cp;montant\n" + "\n".join(
        f"{r['nom']};{r['tel']};{r['cp']};{r['montant']}" for r in _ENREGISTREMENTS
    ) + "\n").encode("utf-8")


def _excel() -> bytes:
    """Classeur Excel des enregistrements, codes saisis en cellules texte.

    Returns:
        Le contenu du classeur, en octets.
    """
    tampon = BytesIO()
    pd.DataFrame(_ENREGISTREMENTS).to_excel(tampon, index=False)
    return tampon.getvalue()


_FICHIERS = {
    "t.csv": _csv,
    "t.json": lambda: json.dumps(_ENREGISTREMENTS).encode("utf-8"),
    "t.jsonl": lambda: "\n".join(json.dumps(r) for r in _ENREGISTREMENTS).encode("utf-8"),
    "t.xlsx": _excel,
}


class TestDetection:
    """La règle commune au chargement et au nettoyage."""

    @pytest.mark.parametrize("valeurs", [
        ["0612345678", "0798765432"],
        ["01000", "75001"],
        ["06 12 34 56 78"],
        ["12", "007"],
    ])
    def test_zero_initial_reconnu(self, valeurs):
        assert has_leading_zero(pd.Series(valeurs))

    @pytest.mark.parametrize("valeurs", [
        ["0", "1", "10"],
        ["0.5", "0,25", "12"],
        ["-0.5", "100"],
        [None, "42"],
        ["01/02/2024", "2024-02-01"],
        ["0216-03-02T00:00:00"],
    ])
    def test_nombres_ordinaires_non_concernes(self, valeurs):
        assert not has_leading_zero(pd.Series(valeurs))

    def test_toute_la_colonne_est_examinee(self):
        """Un code au-delà de la centième ligne doit protéger la colonne."""
        valeurs = [str(n) for n in range(1, 500)] + ["0612345678"]
        assert has_leading_zero(pd.Series(valeurs))


class TestChargement:
    """Aucun format ne doit perdre le zéro au chargement."""

    @pytest.mark.parametrize("nom", list(_FICHIERS))
    def test_zero_conserve(self, nom):
        df = load_dataframe(_FICHIERS[nom](), nom)
        assert df["tel"].tolist() == ["0612345678", "0798765432"]
        assert df["cp"].tolist() == ["01000", "75001"]

    def test_csv_les_autres_colonnes_restent_typees(self):
        """La protection ne concerne que les colonnes à zéro initial."""
        df = load_dataframe(_csv(), "t.csv")
        assert pd.api.types.is_integer_dtype(df["montant"])

    def test_csv_valeurs_manquantes_toujours_reconnues(self):
        df = load_dataframe(b"tel;n\n0612345678;1\n;2\n", "t.csv")
        assert df["tel"].tolist()[0] == "0612345678"
        assert pd.isna(df["tel"].tolist()[1])


class TestNettoyage:
    """Le nettoyage ne doit pas convertir ce que le chargement a protégé."""

    def test_clean_types_laisse_le_texte(self):
        df = pd.DataFrame({"tel": ["0612345678", "0798765432"], "n": ["1", "2"]})
        nettoye, conversions = clean_types(df)
        assert nettoye["tel"].tolist() == ["0612345678", "0798765432"]
        assert "tel" not in conversions
        assert "n" in conversions

    @pytest.mark.parametrize("nom", list(_FICHIERS))
    def test_bout_en_bout(self, nom):
        df = load_dataframe(_FICHIERS[nom](), nom)
        nettoye, _ = run_all_cleaning_steps(df, correct_outliers=False, fill_missing=False)
        assert nettoye["tel"].tolist() == ["0612345678", "0798765432"]
        assert nettoye["cp"].tolist() == ["01000", "75001"]

    def test_invariant_post_nettoyage_respecte(self):
        """Une colonne protégée n'est pas signalée comme mal typée."""
        df = pd.DataFrame({"tel": ["0612345678", "0798765432"]})
        assert find_mistyped_columns(df) == {}
