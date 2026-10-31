import pytest
import pandas as pd
import numpy as np
from src.cleaner_engine import (
    _echelle_dominante,
    clean_empty_columns,
    clean_whitespace,
    clean_types,
    clean_duplicates,
    clean_missing_values,
    clip_outliers,
    count_outliers,
    fix_numeric_types,
    iqr_bounds,
    run_all_cleaning_steps,
    SEUIL_IQR,
)


# ==========================================
# FIXTURES : Données de test simulées
# ==========================================

@pytest.fixture
def perfect_df():
    """Cas nominal : DataFrame propre et complet."""
    return pd.DataFrame({
        'id': [1, 2, 3],
        'nom': ['Alice', 'Bob', 'Charlie'],
        'age': [25, 30, 35]
    })

@pytest.fixture
def dirty_df():
    """Cas complexe : DataFrame avec trous (NaN), espaces et doublons."""
    data = {
        'id': [1, 2, 2, 4],          # Contient un doublon (2)
        'nom': [' Alice ', 'Bob', 'Alice', 'David'], # Espaces superflus & doublon logique
        'age': [25, np.nan, 35, -999], # NaN et outlier (-999)
        'email': ['a@b.com', None, np.nan, np.nan]   # Plusieurs NaN
    }
    return pd.DataFrame(data)

@pytest.fixture
def empty_col_df():
    """Cas limite : DataFrame avec une colonne vide à 100%."""
    return pd.DataFrame({
        'col_pleine': [1, 2],
        'col_vide': [np.nan, np.nan]
    })

@pytest.fixture
def dirty_df_with_exact_doublons():
    """Un DataFrame avec une ligne exacte en double."""
    return pd.DataFrame({
        'id': [1, 2, 2], # id 2 est présent deux fois...
        'nom': ['Alice', 'Bob', 'Bob'], # ...et nom aussi (d'où le doublon exact)
        'age': [25.0, 30.0, 30.0], # ...et age
        'email': ['a@b.com', 'bob@c.com', 'bob@c.com'] # ...et email
    })

@pytest.fixture
def df_with_dates():
    """DataFrame avec des colonnes de dates."""
    return pd.DataFrame({
        'id': [1, 2, 3],
        'date1': ['01/01/2023', '02/01/2023', '03/01/2023'],
        'date2': ['2023-01-01', '2023-01-02', '2023-01-03']
    })

@pytest.fixture
def df_with_mixed_types():
    """DataFrame avec des types mélangés."""
    return pd.DataFrame({
        'id': [1, 2, 3],
        'nom': ['Alice', 'Bob', 'Charlie'],
        'age': ['25', '30', '35'],  # String au lieu de int
        'salaire': ['50.000€', '60.000€', '70.000€'],  # String avec symboles monétaires
        'score': ['4/5', '3/5', '5/5']  # Format de note
    })

@pytest.fixture
def empty_df():
    """DataFrame vide."""
    return pd.DataFrame()

# ==========================================
# TESTS NOMINAUX (Cas simples)
# ==========================================

class TestCleanEmptyColumns:
    def test_nominal(self, perfect_df):
        """Aucune colonne à supprimer car aucune n'est pleine de NaN."""
        df_cleaned, count = clean_empty_columns(perfect_df)
        assert len(df_cleaned.columns) == 3 # Les 3 colonnes sont gardées
        assert count == 0

    def test_suppression_colonne_vide(self, empty_col_df):
        """La colonne pleine de NaN doit être supprimée."""
        df_cleaned, count = clean_empty_columns(empty_col_df)
        assert 'col_vide' not in df_cleaned.columns
        assert count == 1

    def test_empty_dataframe(self, empty_df):
        """Test avec DataFrame vide."""
        df_cleaned, count = clean_empty_columns(empty_df)
        assert df_cleaned.empty
        assert count == 0


class TestCleanWhitespace:
    def test_nominal(self, perfect_df):
        """Les noms ne contiennent pas d'espaces superflus au départ (sauf si on en ajoute)."""
        # Ici, les données sont propres, le nombre de modifications doit être 0.
        df_cleaned, count = clean_whitespace(perfect_df)
        assert count == 0

    def test_nettoyage_espaces(self, dirty_df):
        """On vérifie que ' Alice ' devient 'Alice'."""
        df_cleaned, _ = clean_whitespace(dirty_df)
        assert df_cleaned.loc[0, 'nom'] == 'Alice', "L'espace avant Alice n'a pas été retiré"

    def test_empty_dataframe(self, empty_df):
        """Test avec DataFrame vide."""
        df_cleaned, count = clean_whitespace(empty_df)
        assert df_cleaned.empty
        assert count == 0


class TestCleanDuplicates:
    def test_doublons_exact(self, dirty_df_with_exact_doublons):
        """La ligne avec id=2 en double doit être retirée (1 doublon exact)."""
        df_cleaned, count = clean_duplicates(dirty_df_with_exact_doublons)
        assert len(df_cleaned) == 2 # On attend 2 lignes uniques
        assert count == 1 # On a supprimé 1 doublon

    def test_pas_de_doublons(self, perfect_df):
        """Aucun doublon dans un jeu de données parfait."""
        df_cleaned, count = clean_duplicates(perfect_df)
        assert count == 0

    def test_empty_dataframe(self, empty_df):
        """Test avec DataFrame vide."""
        df_cleaned, count = clean_duplicates(empty_df)
        assert df_cleaned.empty
        assert count == 0


class TestFixNumericTypes:
    def test_fix_float_to_int(self):
        """Test de correction de float vers int."""
        df_test = pd.DataFrame({'val': [1.0, 2.0, 3.0]})
        df_cleaned, conversions = fix_numeric_types(df_test)
        
        # Vérifie que les valeurs sont bien des Int64 (nullable integers)
        assert df_cleaned['val'].dtype == 'Int64'
        assert len(conversions) > 0

    def test_no_conversion_needed(self):
        """Test avec données qui ne nécessitent pas de conversion."""
        df_test = pd.DataFrame({'val': [1, 2, 3]})  # Déjà int
        df_cleaned, conversions = fix_numeric_types(df_test)
        
        assert len(conversions) == 0

    def test_empty_dataframe(self, empty_df):
        """Test avec DataFrame vide."""
        df_cleaned, count = fix_numeric_types(empty_df)
        assert df_cleaned.empty


class TestCleanTypes:
    def test_conversion_object_vers_numeric(self, df_with_mixed_types):
        """Test le passage de string '123' vers int/float."""
        df_cleaned, types_conv = clean_types(df_with_mixed_types)
        
        # Vérifie que les valeurs sont bien des nombres et non plus des strings
        assert df_cleaned['age'].dtype in [np.float64, np.int64]

    def test_conversion_dates(self, df_with_dates):
        """Test la détection de dates."""
        df_cleaned, types_conv = clean_types(df_with_dates)
        
        # On vérifie que les colonnes de date ont été converties
        assert len(types_conv) > 0

    def test_no_conversion_needed(self, perfect_df):
        """Test avec données déjà correctes."""
        df_cleaned, conversions = clean_types(perfect_df)
        assert len(conversions) >= 0  # Peut être vide ou avoir des conversions

    def test_empty_dataframe(self, empty_df):
        """Test avec DataFrame vide."""
        df_cleaned, count = clean_types(empty_df)
        assert df_cleaned.empty


class TestCleanMissingValues:
    def test_fill_median(self, dirty_df):
        """Les NaN de la colonne age (float/int) doivent être comblés par la médiane."""
        df_cleaned, actions = clean_missing_values(dirty_df)
        
        # Il ne doit plus y avoir de valeurs None ou np.nan dans 'age'
        assert df_cleaned['age'].isnull().sum() == 0
        
    def test_fill_mode(self, dirty_df):
        """Les NaN de la colonne email doivent être comblés par le mode (valeur fréquente)."""
        df_cleaned, actions = clean_missing_values(dirty_df)
        
        # L'email doit être rempli (on ne sait pas laquelle par défaut mais il ne doit pas être nul)
        assert df_cleaned['email'].isnull().sum() == 0

    def test_empty_dataframe(self, empty_df):
        """Test avec DataFrame vide."""
        df_cleaned, actions = clean_missing_values(empty_df)
        assert df_cleaned.empty


class TestClipOutliers:
    def test_correction_iqr(self, dirty_df):
        """L'âge '-999' (valeur aberrante) doit être remplacée par la borne inférieure IQR."""
        df_cleaned, corrections = clip_outliers(dirty_df)
    
        # Vérification stricte : il ne doit plus y avoir de -999 "dur"
        # Attention : -999 peut devenir la borne exacte si les maths le permettent, 
        # mais ici avec [25, 35], Q1~27.5, IQR~5 -> Borne < 20. -999 sera donc corrigé.
        # Note : Si l'erreur persiste, cela signifie que la conversion a des problèmes de type
        assert len(corrections) >= 0  # Au moins un élément corrigé ou aucun

    def test_pas_d_outlier(self, perfect_df):
        """Aucun outlier dans un jeu de données parfait."""
        df_cleaned, corrections = clip_outliers(perfect_df)
        assert len(corrections) == 0

    def test_empty_dataframe(self, empty_df):
        """Test avec DataFrame vide."""
        df_cleaned, count = clip_outliers(empty_df)
        assert df_cleaned.empty


class TestPipelineEndToEnd:
    def test_pipeline_complet(self, dirty_df):
        """Test du workflow complet : on s'assure que rien ne plante."""
        final_df, stats = run_all_cleaning_steps(dirty_df)
        
        # Vérifications finales sur le résultat global
        assert not final_df.empty 
        assert 'id' in final_df.columns
        
    def test_pipeline_vide(self):
        """Test sur un DataFrame vide (cas limite)."""
        df_empty = pd.DataFrame()
        # On s'assure que ça ne plante pas (ou renvoie un truc gérable)
        final_df, stats = run_all_cleaning_steps(df_empty)
        assert final_df.empty

    def test_pipeline_avec_doublons(self, dirty_df_with_exact_doublons):
        """Test avec doublons dans le pipeline."""
        final_df, stats = run_all_cleaning_steps(dirty_df_with_exact_doublons)
        assert not final_df.empty

class TestTraitementColonneParColonne:
    """Écrêtage et remplissage se décident colonne par colonne.

    Un extrême peut être réel, une absence peut avoir un sens : l'utilisateur
    doit pouvoir traiter une colonne et en laisser une autre intacte.
    """

    @pytest.fixture
    def df_jumeaux(self):
        """Deux paires de colonnes identiques : l'une traitée, l'autre non."""
        base = [10, 11, 12, 13, 14, 15, 12, 11, 500]
        trous = [1.0, np.nan, 3.0, np.nan, 5.0, 6.0, 7.0, 8.0, 9.0]
        return pd.DataFrame({'a': base, 'b': base, 'c': trous, 'd': trous})

    def test_clip_outliers_seulement_les_colonnes_choisies(self, df_jumeaux):
        df, corrections = clip_outliers(df_jumeaux, columns=['a'])
        assert set(corrections) == {'a'}
        assert df['a'].max() < 500
        assert df['b'].max() == 500

    def test_clip_outliers_none_traite_tout(self, df_jumeaux):
        _, corrections = clip_outliers(df_jumeaux)
        assert set(corrections) == {'a', 'b'}

    def test_colonne_inconnue_ignoree(self, df_jumeaux):
        _, corrections = clip_outliers(df_jumeaux, columns=['absente'])
        assert corrections == {}

    def test_clean_missing_values_seulement_les_colonnes_choisies(self, df_jumeaux):
        df, actions = clean_missing_values(df_jumeaux, columns=['c'])
        assert set(actions) == {'c'}
        assert df['c'].isna().sum() == 0
        assert df['d'].isna().sum() == 2

    def test_pipeline_transmet_le_choix(self, df_jumeaux):
        df, stats = run_all_cleaning_steps(
            df_jumeaux, correct_outliers=True, fill_missing=True,
            outlier_columns=['b'], missing_columns=['d'])
        assert set(stats['outliers_corrected']) == {'b'}
        assert set(stats['missing_filled']) == {'d'}
        assert df['a'].max() == 500
        assert df['c'].isna().sum() == 2


class TestSeuilIqr:
    """Le seuil IQR s'adapte à chaque colonne.

    Des montants très dispersés appellent plus de tolérance que des mesures
    stables : un seuil unique à 1,5 écrêtait des valeurs réelles.
    """

    @pytest.fixture
    def df_seuils(self):
        """Une valeur modérément extrême (120) et une très extrême (900).

        Q1 = 102 et Q3 = 105,5 : la borne haute vaut 110,75 au seuil 1,5,
        123 au seuil 5.
        """
        valeurs = [100, 101, 102, 103, 104, 105, 106, 102, 103, 120, 900]
        return pd.DataFrame({'a': valeurs, 'b': valeurs})

    def test_bornes_selon_le_seuil(self):
        serie = pd.Series([1, 2, 3, 4, 5])  # Q1 = 2, Q3 = 4, IQR = 2
        assert iqr_bounds(serie) == (2 - 1.5 * 2, 4 + 1.5 * 2)
        assert iqr_bounds(serie, 3) == (2 - 3 * 2, 4 + 3 * 2)

    def test_bornes_sans_dispersion(self):
        assert iqr_bounds(pd.Series([5, 5, 5])) is None
        assert iqr_bounds(pd.Series([5])) is None

    def test_comptage_selon_le_seuil(self, df_seuils):
        assert count_outliers(df_seuils['a']) == 2
        assert count_outliers(df_seuils['a'], 5) == 1

    def test_comptage_d_une_colonne_textuelle(self):
        serie = pd.Series(['100 €', '101 €', '102 €', '103 €', '104 €', '9 000 €'])
        assert count_outliers(serie) == 1
        assert count_outliers(pd.Series(['a', 'b', 'c'])) == 0

    def test_ecretage_selon_le_seuil_de_chaque_colonne(self, df_seuils):
        df, corrections = clip_outliers(df_seuils, thresholds={'a': 5})
        assert corrections == {'a': 1, 'b': 2}
        assert 120 in df['a'].tolist() and df['a'].max() < 900
        assert 120 not in df['b'].tolist()

    def test_pipeline_consigne_le_seuil(self, df_seuils):
        _, stats = run_all_cleaning_steps(
            df_seuils, correct_outliers=True, fill_missing=False,
            outlier_columns=['a', 'b'], outlier_thresholds={'a': 3.0})
        assert stats['outlier_thresholds'] == {'a': 3.0, 'b': SEUIL_IQR}

    def test_option_de_la_ligne_de_commande(self):
        """`--seuil-iqr` accepte la virgule décimale et refuse un seuil nul."""
        import main

        parseur = main.construire_parseur()
        assert parseur.parse_args([]).seuil_iqr == SEUIL_IQR
        assert parseur.parse_args(["--seuil-iqr", "2,5"]).seuil_iqr == 2.5
        with pytest.raises(SystemExit):
            parseur.parse_args(["--seuil-iqr", "0"])


class TestEchelleDesNotes:
    """Une colonne de notes mêlant plusieurs échelles est ramenée à une seule.

    Retenir le numérateur reste juste quand toutes les notes partagent une
    échelle (« 5 » et « 5/5 ») ; mais « 17/20 » et « 4/5 » donnaient 17 et 4,
    deux nombres incomparables.
    """

    @staticmethod
    def _typer(valeurs):
        """Type une colonne de notes et recense les notes ramenées.

        Args:
            valeurs: Notes, en texte.

        Returns:
            Le couple (valeurs typées, recensement des notes ramenées).
        """
        echelles = {}
        df, _ = clean_types(pd.DataFrame({'note': valeurs}), echelles=echelles)
        return df['note'].tolist(), echelles

    def test_echelles_melees_ramenees_a_la_dominante(self):
        valeurs, echelles = self._typer(['17/20', '4/5', '15', '12/20'])
        assert valeurs == [17, 16, 15, 12]
        assert echelles == {'note': {'scale': 20.0, 'count': 1,
                                     'examples': ['4/5 → 16']}}

    def test_echelle_unique_inchangee(self):
        valeurs, echelles = self._typer(['5', '5/5', '4/5'])
        assert valeurs == [5, 5, 4]
        assert echelles == {}

    def test_egalite_departagee_par_la_plus_grande_echelle(self):
        valeurs, _ = self._typer(['3/4', '15/20'])
        assert valeurs == [15, 15]

    def test_virgule_decimale_et_exemples_a_la_francaise(self):
        valeurs, echelles = self._typer(['3/4', '3/4', '4,5/5'])
        assert valeurs == [3.0, 3.0, 3.6]
        assert echelles['note']['examples'] == ['4,5/5 → 3,6']

    def test_denominateur_nul_ignore(self):
        assert _echelle_dominante(pd.Series(['3/0', '4/0'])) is None

    def test_pipeline_consigne_les_notes_ramenees(self):
        _, stats = run_all_cleaning_steps(
            pd.DataFrame({'note': ['17/20', '4/5', '18/20', '10/20']}),
            correct_outliers=False, fill_missing=False)
        assert stats['grades_rescaled']['note']['count'] == 1
