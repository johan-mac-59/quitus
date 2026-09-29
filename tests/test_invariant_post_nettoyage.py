"""Verrouille l'invariant du double profilage.

Le pipeline produit deux rapports, et leurs exigences sont opposées :

* le **profil pré-nettoyage** doit refléter le désordre brut — une colonne de
  montants stockée en texte doit y apparaître comme telle. C'est le constat du
  problème, sa raison d'être. Rien n'y est « incorrect » ;
* le **profil post-nettoyage** ne doit plus contenir aucune colonne mal typée.
  C'est la mesure du travail accompli.

Ces tests contrôlent le second point, qui est la promesse du pipeline. Ils sont
volontairement écrits comme une propriété générale — « aucune colonne textuelle
restante ne doit être convertible » — et non comme une liste de colonnes
attendues : ainsi ils résistent à l'évolution des jeux de données.
"""

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.cleaner_engine import (
    _can_be_numeric,
    clean_types,
    find_mistyped_columns,
    run_all_cleaning_steps,
)
from src.data_profiler import ExploratoryProfiler, PreCleaningProfiler
from src.file_loader import load_file

ECHANTILLON = Path(__file__).parent.parent / "data" / "samples" / "reservations_exemple.csv"

TYPES_TEXTUELS = ("str", "object", "string")

# find_mistyped_columns vit dans src/ et non ici : l'interface web l'utilise
# pour son onglet de contrôle. Tests et application vérifient ainsi exactement
# la même chose.
_colonnes_encore_convertibles = find_mistyped_columns


@pytest.fixture
def df_desordonne():
    """DataFrame reproduisant les désordres typiques d'un export réel."""
    rng = np.random.default_rng(seed=11)
    n = 60
    return pd.DataFrame({
        "identifiant": [f"R{1000 + i}" for i in range(n)],
        # Trois conventions de date mélangées dans une même colonne, comme dans
        # un export réel : aucune ne domine à plus de 80 %.
        "date": [
            ["13/09/2024", "2023-09-15", "18-07-2023", "06/11/23"][i % 4]
            for i in range(n)
        ],
        # Montants monétaires en texte, séparateur décimal français.
        "montant": [f"{rng.normal(100, 12):.2f} €".replace(".", ",") for _ in range(n)],
        # Notes mêlant écriture nue et fractionnaire, avec des trous.
        "note": [None if i % 8 == 0 else ["5", "4/5", "3", "2/5"][i % 4] for i in range(n)],
        # Pourcentages.
        "taux": [f"{rng.uniform(0, 100):.4f}%" for _ in range(n)],
        # Texte véritable : doit rester du texte.
        "ville": [["Lille", "Paris", "Lyon"][i % 3] for i in range(n)],
    })


class TestInvariantSurDonneesSynthetiques:
    def test_aucune_colonne_convertible_apres_nettoyage(self, df_desordonne):
        """Après nettoyage, plus aucune colonne textuelle n'est convertible."""
        propre, _ = run_all_cleaning_steps(
            df_desordonne.copy(), correct_outliers=False, fill_missing=False)
        assert _colonnes_encore_convertibles(propre) == {}

    def test_les_dates_melangees_sont_toutes_converties(self, df_desordonne):
        """Une colonne mêlant plusieurs conventions de date est convertie.

        Chaque format est appliqué cumulativement : retenir le meilleur format
        isolément échouerait, aucun n'atteignant le seuil à lui seul.
        """
        propre, conversions = clean_types(df_desordonne)
        assert pd.api.types.is_datetime64_any_dtype(propre["date"])
        # Les quatre conventions doivent être interprétées, sans perte.
        assert propre["date"].notna().sum() == len(df_desordonne)

    def test_les_montants_monetaires_sont_convertis(self, df_desordonne):
        """Une colonne monétaire textuelle devient numérique."""
        propre, _ = clean_types(df_desordonne)
        assert pd.api.types.is_numeric_dtype(propre["montant"])

    def test_les_notes_fractionnaires_sont_converties(self, df_desordonne):
        """Une colonne mêlant « 5 » et « 4/5 » devient numérique."""
        propre, _ = clean_types(df_desordonne)
        assert pd.api.types.is_numeric_dtype(propre["note"])

    def test_les_pourcentages_sont_convertis(self, df_desordonne):
        """Une colonne de pourcentages devient numérique."""
        propre, _ = clean_types(df_desordonne)
        assert pd.api.types.is_numeric_dtype(propre["taux"])

    def test_le_texte_reste_du_texte(self, df_desordonne):
        """Une colonne de noms de villes ne doit pas être convertie."""
        propre, _ = clean_types(df_desordonne)
        assert str(propre["ville"].dtype) in TYPES_TEXTUELS

    def test_les_identifiants_restent_du_texte(self, df_desordonne):
        """Un identifiant alphanumérique ne doit pas être converti."""
        propre, _ = clean_types(df_desordonne)
        assert str(propre["identifiant"].dtype) in TYPES_TEXTUELS


class TestDistinctionDesDeuxProfils:
    """Les deux profils n'ont pas les mêmes exigences, et c'est voulu."""

    def test_le_profil_pre_nettoyage_reflete_le_desordre(self, df_desordonne):
        """Le profil initial doit montrer les colonnes en texte, sans les corriger.

        C'est le constat du problème : un rapport qui masquerait le désordre
        n'aurait aucune utilité.
        """
        res = PreCleaningProfiler(df_desordonne, "brut.csv").run_analysis()
        assert res["dtypes"]["montant"] in TYPES_TEXTUELS
        assert res["dtypes"]["date"] in TYPES_TEXTUELS

    def test_le_profil_post_nettoyage_est_propre(self, df_desordonne):
        """Le profil final ne doit plus signaler aucun type douteux."""
        propre, _ = run_all_cleaning_steps(
            df_desordonne.copy(), correct_outliers=False, fill_missing=False)
        res = ExploratoryProfiler(propre, "propre.csv").run_analysis()

        for col, dtype in res["dtypes"].items():
            if dtype in TYPES_TEXTUELS:
                assert not _can_be_numeric(propre[col]), (
                    f"{col} est restée en texte alors qu'elle est numérisable"
                )


@pytest.mark.skipif(not ECHANTILLON.exists(), reason="échantillon versionné absent")
class TestInvariantSurEchantillonVersionne:
    def test_invariant_de_bout_en_bout(self):
        """Le pipeline complet, sur l'échantillon du dépôt, respecte l'invariant."""
        df = load_file(str(ECHANTILLON))
        profil = PreCleaningProfiler(df, ECHANTILLON).run_analysis()
        propre, _ = run_all_cleaning_steps(
            df.copy(), profile_info=profil,
            correct_outliers=True, fill_missing=True)

        fautives = _colonnes_encore_convertibles(propre)
        assert fautives == {}, f"Colonnes mal typées après nettoyage : {fautives}"

    def test_les_dates_de_l_echantillon_sont_converties(self):
        """Les trois colonnes de date de l'échantillon deviennent des dates."""
        df = load_file(str(ECHANTILLON))
        propre, _ = run_all_cleaning_steps(
            df.copy(), correct_outliers=False, fill_missing=False)

        for col in ("date_reservation", "date_arrivee", "date_depart"):
            assert pd.api.types.is_datetime64_any_dtype(propre[col]), (
                f"{col} n'a pas été convertie en date"
            )


class TestRobustesseDeLaConversion:
    """Une colonne saugrenue ne doit jamais faire planter la conversion."""

    def test_une_colonne_de_notes_ne_devient_pas_une_date(self):
        """« 5/5 » ressemble à une date pour un format permissif : on l'écarte.

        Sans le garde-fou de plausibilité des années, ce cas produisait une
        exception `OutOfBoundsDatetime` de pandas.
        """
        df = pd.DataFrame({"note": ["5/5", "3/5", "4/5", "2/5", "1/5"]})
        propre, _ = clean_types(df)
        assert not pd.api.types.is_datetime64_any_dtype(propre["note"])
        assert pd.api.types.is_numeric_dtype(propre["note"])

    def test_valeurs_heteroclites(self):
        """Un mélange sans structure ne fait pas échouer le nettoyage."""
        df = pd.DataFrame({"fourre_tout": ["12", "abc", "2024-01-01", "5/5",
                                           "99%", None, "", "  "]})
        propre, _ = clean_types(df)
        assert len(propre) == len(df)

    def test_annees_aberrantes_ecartees(self):
        """Une date hors de toute plausibilité n'est pas retenue."""
        df = pd.DataFrame({"d": ["01/01/1850", "01/01/1851", "01/01/1852",
                                 "01/01/1853", "01/01/1854"]})
        propre, _ = clean_types(df)
        # 1850 est hors des bornes admises : la colonne reste en texte.
        assert str(propre["d"].dtype) in TYPES_TEXTUELS

    def test_colonne_entierement_vide(self):
        """Une colonne sans aucune valeur ne fait pas échouer la conversion."""
        df = pd.DataFrame({"vide": [None, None, None]})
        propre, conversions = clean_types(df)
        assert conversions == {}
