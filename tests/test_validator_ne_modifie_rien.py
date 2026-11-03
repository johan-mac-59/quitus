"""Garantie : le validateur signale, il ne modifie jamais les données.

Le validateur est en lecture seule par conception (les corrections sont une
étape ultérieure, sous accord explicite de l'utilisateur). Cette garantie
doit tenir quelles que soient les règles, y compris mal formées ou en erreur :
un DataFrame abîmé par une vérification serait une perte silencieuse.
"""

import pandas as pd
import pytest

from src.validator import nouvelle_regle, valider


@pytest.fixture
def df_piege():
    """Un fichier désordonné : types mêlés, vides, doublons, dates variées."""
    return pd.DataFrame({
        "age": [25, -3, 130, None, "abc", "40"],
        "cp": ["75001", "1234", None, "", "ABCDE", "75001"],
        "debut": ["2024-01-05", "05/02/2024", None, "x", "2024-03-01", "2024-01-01"],
        "fin": ["2024-02-01", "01/02/2024", "2024-01-01", None, None, "2024-01-02"],
        "id": [1.0, 2.0, 2.0, None, 5.0, 6.0],
    }, index=[10, 11, 12, 13, 14, 15])


@pytest.fixture
def toutes_les_regles():
    """Une règle de chaque type, plus des règles invalides ou sans colonne."""
    return [
        nouvelle_regle("plage", "age", {"min": 0, "max": 120}),
        nouvelle_regle("plage", "debut", {"min": "2024-01-02"}),
        nouvelle_regle("longueur", "cp", {"min": 5, "max": 5}),
        nouvelle_regle("format", "cp", {"nom": "code_postal"}),
        nouvelle_regle("valeurs_autorisees", "cp", {"valeurs": ["75001"]}),
        nouvelle_regle("non_vide", "age"),
        nouvelle_regle("unique", "id"),
        nouvelle_regle("comparaison_colonnes", ["debut", "fin"], {"operateur": "<="}),
        nouvelle_regle("plage", "absente", {"min": 0}),
        {"type": "zzz"},
        "pas une règle",
    ]


def test_le_dataframe_est_identique_apres_validation(df_piege, toutes_les_regles):
    avant = df_piege.copy(deep=True)
    valider(df_piege, toutes_les_regles)
    pd.testing.assert_frame_equal(df_piege, avant)


def test_les_regles_ne_sont_pas_modifiees(df_piege, toutes_les_regles):
    import copy
    avant = copy.deepcopy(toutes_les_regles)
    valider(df_piege, toutes_les_regles)
    assert toutes_les_regles == avant


def test_les_lignes_signalees_sont_des_etiquettes_de_l_index(df_piege):
    """Les lignes fautives se retrouvent dans le fichier d'origine, même après tri ou suppression."""
    r = valider(df_piege, [nouvelle_regle("plage", "age", {"min": 0, "max": 120})])["resultats"][0]
    assert r["lignes"] == [11, 12]
    assert all(i in df_piege.index for i in r["lignes"])


def test_chaque_valeur_ecartee_est_declaree(df_piege):
    """Rien n'est ignoré : valeurs vérifiées + illisibles + vides = toutes les lignes."""
    r = valider(df_piege, [nouvelle_regle("plage", "age", {"min": 0, "max": 120})])["resultats"][0]
    vides = int(df_piege["age"].isna().sum())
    assert r["evaluees"] + r["non_evaluables"] + vides == len(df_piege)
