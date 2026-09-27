"""
Tests unitaires pour la classe DataProfiler.

Ce module vérifie la robustesse de l'analyse descriptive des données,
la gestion des types, les cas limites (valeurs manquantes, vides) 
et la génération de rapports Markdown.
"""

import os
import pytest
import pandas as pd
import numpy as np
from src.data_profiler import DataProfiler


# --- Fixtures ---

@pytest.fixture
def valid_df():
    """Crée un DataFrame valide avec des données variées pour les tests nominatifs."""
    data = {
        'id': [1, 2, 3, 4, 5],
        'nom': ['Alice', 'Bob', 'Charlie', 'David', 'Eve'],
        'age': [25, 30, np.nan, 40, 35],  # Contient un NaN pour tester la gestion des manquants
        'salaire': [50000.0, 60000.0, 70000.0, np.nan, 80000.0], # Contient un NaN float
        'is_active': [True, False, True, True, False]
    }
    return pd.DataFrame(data)


@pytest.fixture
def empty_df():
    """Crée un DataFrame vide pour tester les cas limites."""
    return pd.DataFrame()


# --- Tests d'initialisation ---

class TestDataProfilerInit:
    def test_init_with_dataframe(self, valid_df):
        """Cas nominal : Initialisation avec un DataFrame pandas valide."""
        profiler = DataProfiler(valid_df)
        assert profiler.df is not None
        assert isinstance(profiler.df, pd.DataFrame)
        # Vérifier qu'on travaille sur une copie (mutation safety)
        valid_df.loc[0, 'id'] = 999  # Utilisation de .loc pour éviter l'avertissement pandas
        assert profiler.df['id'][0] == 1

    def test_init_with_invalid_type(self):
        """Cas limite : Initialisation avec un type non DataFrame doit lever ValueError."""
        with pytest.raises(ValueError, match="L'objet fourni n'est pas un DataFrame pandas."):
            DataProfiler([1, 2, 3])
        
        with pytest.raises(ValueError, match="L'objet fourni n'est pas un DataFrame pandas."):
            DataProfiler("une chaine de caracteres")


# --- Tests de l'analyse (run_analysis) ---

class TestDataProfilerRunAnalysis:
    
    def test_run_analysis_structure(self, valid_df):
        """Cas nominal : La méthode retourne un dictionnaire avec les clés attendues."""
        profiler = DataProfiler(valid_df)
        results = profiler.run_analysis()
        
        expected_keys = ['shape', 'dtypes', 'missing_values', 'nb_doublons', 'describe_numeric']
        for key in expected_keys:
            assert key in results, f"La clé '{key}' est absente des résultats."

    def test_shape_accuracy(self, valid_df):
        """Cas nominal : Vérifie que le shape du DataFrame est correct."""
        profiler = DataProfiler(valid_df)
        results = profiler.run_analysis()
        
        # Le shape est maintenant un dictionnaire {nb_lignes: int, nb_colonnes: int}
        assert 'nb_lignes' in results['shape']
        assert 'nb_colonnes' in results['shape']
        assert results['shape']['nb_lignes'] == 5
        assert results['shape']['nb_colonnes'] == 5

    def test_missing_values_calculation(self, valid_df):
        """Cas nominal : Vérifie le calcul des valeurs manquantes."""
        profiler = DataProfiler(valid_df)
        results = profiler.run_analysis()
        
        # 'age' a 1 NaN (sur 5 lignes => 20%)
        assert results['missing_values']['count']['age'] == 1
        assert results['missing_values']['percent']['age'] == 20.0
        
        # 'salaire' a 1 NaN (sur 5 lignes => 20%)
        assert results['missing_values']['count']['salaire'] == 1
        assert results['missing_values']['percent']['salaire'] == 20.0

    def test_duplicated_count(self, valid_df):
        """Cas nominal : Vérifie le comptage des doublons."""
        profiler = DataProfiler(valid_df)
        results = profiler.run_analysis()
        assert results['nb_doublons'] == 0

    def test_duplicates_detection(self):
        """Cas limite : Un DataFrame avec des doublons doit les détecter."""
        data = {
            'col1': [1, 1, 2],
            'col2': ['a', 'a', 'b']
        }
        df_dupes = pd.DataFrame(data)
        profiler = DataProfiler(df_dupes)
        results = profiler.run_analysis()
        # La ligne 1 est un doublon de la ligne 0 par défaut
        assert results['nb_doublons'] == 1

    def test_numeric_stats_presence(self, valid_df):
        """Cas nominal : Les stats numériques doivent être présentes pour les colonnes numériques."""
        profiler = DataProfiler(valid_df)
        results = profiler.run_analysis()
        
        assert 'describe_numeric' in results
        # 'age' et 'salaire' doivent avoir des stats (min, max, mean, std...)
        assert 'age' in results['describe_numeric']
        assert 'salaire' in results['describe_numeric']

    def test_categorical_stats_presence(self, valid_df):
        """Cas nominal : Les stats catégorielles doivent être présentes pour les strings."""
        profiler = DataProfiler(valid_df)
        results = profiler.run_analysis()

        assert 'describe_categorical' in results
        assert 'nom' in results['describe_categorical']

        # Chaque colonne expose le jeu complet d'indicateurs attendus
        expected_keys = {
            'cardinality_absolute', 'cardinality_relative', 'sparsity_ratio',
            'skewness_frequency', 'is_high_skewness', 'top_categories',
            'format_anomalies',
        }
        for col, values in results['describe_categorical'].items():
            assert isinstance(values, dict)
            assert expected_keys <= set(values), f"Indicateurs manquants pour {col}"
            # top_categories est plafonné aux 10 valeurs les plus fréquentes
            assert len(values['top_categories']) <= 10
            assert isinstance(values['format_anomalies'], list)

    def test_run_analysis_empty_df(self, empty_df):
        """Cas critique : Analyser un DataFrame vide doit lever une exception."""
        profiler = DataProfiler(empty_df)
        with pytest.raises(ValueError, match="Impossible de profiler un DataFrame vide."):
            profiler.run_analysis()

    def test_run_analysis_all_nulls_column(self):
        """Cas limite : Une colonne entièrement à NaN ne doit pas faire planter l'analyse."""
        data = {
            'col1': [1, 2, 3],
            'col_null': [None, None, None]
        }
        df_partial_null = pd.DataFrame(data)
        profiler = DataProfiler(df_partial_null)
        # Ne doit pas lever d'exception
        results = profiler.run_analysis()
        assert 'col_null' in results['missing_values']['count']
        assert results['missing_values']['percent']['col_null'] == 100.0


# --- Tests de la génération de rapport (generate_report) ---

class TestDataProfilerReportGeneration:
    
    @pytest.fixture
    def temp_output_path(self, tmp_path):
        """Fixture pour créer un chemin temporaire unique."""
        return os.path.join(str(tmp_path), "test_report.md")

    def test_generate_report_creates_file(self, valid_df, temp_output_path):
        """Cas nominal : Le rapport doit être créé sur le disque."""
        profiler = DataProfiler(valid_df)
        # run_analysis doit avoir été appelé ou l'appeler en interne via generate_report
        result_path = profiler.generate_report(temp_output_path)
        
        assert os.path.exists(result_path)
        assert result_path == temp_output_path

    def test_generate_report_content_structure(self, valid_df, temp_output_path):
        """Cas nominal : Le contenu Markdown doit contenir les sections attendues."""
        profiler = DataProfiler(valid_df)
        profiler.generate_report(temp_output_path)
        
        with open(temp_output_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # On vérifie la présence de l'emoji 🧱 qui a été ajouté dans le code source
        assert "# 📊 Rapport d'Inspection" in content
        assert "## 🧱 Structure" in content  # <-- Correction ici
        assert "## 🏷️ Colonnes et Types" in content
        assert "## ⚠️ Valeurs Manquantes" in content

    def test_generate_report_utf8_encoding(self, valid_df, temp_output_path):
        """Cas limite : Vérifie qu'il n'y a pas d'erreurs d'encodage avec des caractères spéciaux."""
        # Ajout de caractères spéciaux français
        valid_df.loc[0, 'nom'] = "Ångström" 
        
        profiler = DataProfiler(valid_df)
        # Doit fonctionner sans lever UnicodeEncodeError ou UnicodeDecodeError
        try:
            profiler.generate_report(temp_output_path)
        except Exception as e:
            pytest.fail(f"Une erreur est survenue lors de la génération du rapport : {e}")

    def test_generate_report_calls_analysis_if_needed(self, valid_df):
        """Cas limite : Si run_analysis n'a pas été appelé, generate_report doit le faire implicitement."""
        profiler = DataProfiler(valid_df)
        # On vide manuellement les résultats pour forcer l'appel interne
        profiler.profile_results = {} 
        
        # Cela ne doit pas lever d'erreur
        profiler.generate_report()


# --- Tests additionnels pour la robustesse ---

class TestDataProfilerRobustness:
    
    def test_large_dataframe_performance(self):
        """Cas limite : Performance sur un dataset raisonnablement grand."""
        n_rows = 10000
        df_large = pd.DataFrame({
            'num': np.random.randn(n_rows),
            'cat': np.random.choice(['A', 'B', 'C'], n_rows)
        })
        
        profiler = DataProfiler(df_large)
        results = profiler.run_analysis()
        
        assert results['shape']['nb_lignes'] == n_rows
        assert results['shape']['nb_colonnes'] == 2
        
        # Vérifie que la génération de stats ne prend pas un temps déraisonnable (< 1s normalement)
        import time
        start = time.time()
        profiler.generate_report()
        elapsed = time.time() - start
        assert elapsed < 5.0, f"La génération du rapport a pris trop de temps : {elapsed}s"