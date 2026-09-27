import pytest
import pandas as pd
from unittest.mock import Mock
from src.cleaner_logger import CleanLogger, generate_and_print_report
from src.cleaner_reporter import CleanerReporter

class TestCleanLogger:
    """Tests unitaires pour la classe CleanLogger."""
    
    def test_init_with_valid_data(self):
        """Test de l'initialisation avec des données valides."""
        # Données de test
        initial_df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
        stats = {'empty_cols_dropped': 0, 'duplicates_removed': 0, 'types_converted': {}, 
                'missing_filled': {}, 'outliers_corrected': {}, 'whitespace_cleaned': 0}
        
        # Création de l'objet
        logger = CleanLogger(initial_df, stats)
        
        # Vérifications
        assert logger.initial_df is initial_df
        assert logger.stats is stats
        assert logger.final_shape is None
        assert logger.final_columns is None
    
    def test_update_final_state(self):
        """Test de la méthode update_final_state."""
        # Données de test
        initial_df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
        stats = {'empty_cols_dropped': 0, 'duplicates_removed': 0, 'types_converted': {}, 
                'missing_filled': {}, 'outliers_corrected': {}, 'whitespace_cleaned': 0}
        final_df = pd.DataFrame({'A': [1, 2], 'B': [4, 5]})
        
        # Création et mise à jour
        logger = CleanLogger(initial_df, stats)
        logger.update_final_state(final_df)
        
        # Vérifications
        assert logger.final_shape == (2, 2)
        assert logger.final_columns == ['A', 'B']
    
    def test_get_summary_without_update(self):
        """Test du résumé sans appel à update_final_state."""
        initial_df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
        stats = {'empty_cols_dropped': 0, 'duplicates_removed': 0, 'types_converted': {}, 
                'missing_filled': {}, 'outliers_corrected': {}, 'whitespace_cleaned': 0}
        
        logger = CleanLogger(initial_df, stats)
        
        # Doit retourner un message d'erreur
        summary = logger.get_summary()
        assert "⚠️ Rapport non finalisé" in summary
    
    def test_get_summary_with_all_operations(self):
        """Test du résumé avec toutes les opérations."""
        initial_df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6], 'C': [7, 8, 9]})
        stats = {
            'empty_cols_dropped': 1,
            'duplicates_removed': 2,
            'types_converted': {'A': 'int64 -> float64'},
            'missing_filled': {'B': 'mean'},
            'outliers_corrected': {'C': 'IQR method'},
            'whitespace_cleaned': 1
        }
        final_df = pd.DataFrame({'A': [1, 2], 'B': [4, 5]})
        
        logger = CleanLogger(initial_df, stats)
        logger.update_final_state(final_df)
        summary = logger.get_summary()
        
        # Vérifications basiques
        assert "RAPPORT DE NETTOYAGE DE DONNÉES" in summary
        assert "📊 Lignes :" in summary
        assert "📑 Colonnes :" in summary
        assert "🗑️ Colonnes supprimées (vides) : 1" in summary
        assert "🔄 Doublons supprimés : 2" in summary
        assert "🎨 Types convertis :" in summary
        assert "💧 Valeurs manquantes comblées :" in summary
        assert "📈 Outliers corrigés (IQR) :" in summary
        assert "🧼 Espaces nettoyés : 1" in summary
    
    def test_get_summary_with_no_operations(self):
        """Test du résumé sans opérations."""
        initial_df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
        stats = {
            'empty_cols_dropped': 0,
            'duplicates_removed': 0,
            'types_converted': {},
            'missing_filled': {},
            'outliers_corrected': {},
            'whitespace_cleaned': 0
        }
        final_df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
        
        logger = CleanLogger(initial_df, stats)
        logger.update_final_state(final_df)
        summary = logger.get_summary()
        
        # Vérifications
        assert "RAPPORT DE NETTOYAGE DE DONNÉES" in summary
        assert "📊 Lignes : 3 → 3" in summary
        assert "📑 Colonnes : 2 → 2" in summary
    
    def test_get_summary_with_type_conversions(self):
        """Test du résumé avec conversions de types."""
        initial_df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
        stats = {
            'empty_cols_dropped': 0,
            'duplicates_removed': 0,
            'types_converted': {'A': 'int64 -> float64', 'B': 'int64 -> str'},
            'missing_filled': {},
            'outliers_corrected': {},
            'whitespace_cleaned': 0
        }
        final_df = pd.DataFrame({'A': [1.0, 2.0, 3.0], 'B': ['4', '5', '6']})
        
        logger = CleanLogger(initial_df, stats)
        logger.update_final_state(final_df)
        summary = logger.get_summary()
        
        # Vérifications
        assert "🎨 Types convertis :" in summary
    
    def test_get_detailed_table(self):
        """Test de la méthode get_detailed_table."""
        initial_df = pd.DataFrame({'A': [1, 2, 3], 'B': [4.0, 5.0, 6.0]})
        final_df = pd.DataFrame({'A': [1.0, 2.0, 3.0], 'B': [4, 5, 6]})
        
        stats = {'empty_cols_dropped': 0, 'duplicates_removed': 0, 'types_converted': {}, 
                'missing_filled': {}, 'outliers_corrected': {}, 'whitespace_cleaned': 0}
        
        logger = CleanLogger(initial_df, stats)
        logger.update_final_state(final_df)
        table = logger.get_detailed_table(final_df)
        
        # Vérifications
        assert isinstance(table, pd.DataFrame)
    
    def test_get_detailed_table_empty(self):
        """Test de la méthode get_detailed_table avec des types identiques."""
        initial_df = pd.DataFrame({'A': [1, 2, 3], 'B': [4.0, 5.0, 6.0]})
        final_df = pd.DataFrame({'A': [1, 2, 3], 'B': [4.0, 5.0, 6.0]})
        
        stats = {'empty_cols_dropped': 0, 'duplicates_removed': 0, 'types_converted': {}, 
                'missing_filled': {}, 'outliers_corrected': {}, 'whitespace_cleaned': 0}
        
        logger = CleanLogger(initial_df, stats)
        logger.update_final_state(final_df)
        table = logger.get_detailed_table(final_df)
        
        # Vérifications
        assert isinstance(table, pd.DataFrame)
        assert len(table) == 0
    
    def test_format_delta(self):
        """Test de la méthode _format_delta."""
        initial_df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
        stats = {'empty_cols_dropped': 0, 'duplicates_removed': 0, 'types_converted': {}, 
                'missing_filled': {}, 'outliers_corrected': {}, 'whitespace_cleaned': 0}
        
        logger = CleanLogger(initial_df, stats)
        
        # Tests
        assert logger._format_delta(10, 15) == "+5"
        assert logger._format_delta(10, 5) == "-5"
        assert logger._format_delta(5, 5) == "+0"
    
    def test_generate_and_print_report(self, capsys):
        """Test de la fonction utilitaire generate_and_print_report."""
        initial_df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
        stats = {
            'empty_cols_dropped': 0,
            'duplicates_removed': 0,
            'types_converted': {},
            'missing_filled': {},
            'outliers_corrected': {},
            'whitespace_cleaned': 0
        }
        final_df = pd.DataFrame({'A': [1, 2], 'B': [4, 5]})
        
        # Doit s'exécuter sans erreur
        generate_and_print_report(initial_df, stats, final_df)
        
        # Vérification que la sortie est produite
        captured = capsys.readouterr()
        assert "RAPPORT DE NETTOYAGE DE DONNÉES" in captured.out

class TestCleanLoggerEdgeCases:
    """Tests de cas limites pour CleanLogger."""
    
    def test_empty_dataframe(self):
        """Test avec un DataFrame vide."""
        initial_df = pd.DataFrame()
        stats = {'empty_cols_dropped': 0, 'duplicates_removed': 0, 'types_converted': {}, 
                'missing_filled': {}, 'outliers_corrected': {}, 'whitespace_cleaned': 0}
        final_df = pd.DataFrame()
        
        logger = CleanLogger(initial_df, stats)
        logger.update_final_state(final_df)
        summary = logger.get_summary()
        
        assert "📊 Lignes : 0 → 0" in summary
        assert "📑 Colonnes : 0 → 0" in summary
    
    def test_single_column_dataframe(self):
        """Test avec un DataFrame à une seule colonne."""
        initial_df = pd.DataFrame({'A': [1, 2, 3]})
        stats = {'empty_cols_dropped': 0, 'duplicates_removed': 0, 'types_converted': {}, 
                'missing_filled': {}, 'outliers_corrected': {}, 'whitespace_cleaned': 0}
        final_df = pd.DataFrame({'A': [1, 2]})
        
        logger = CleanLogger(initial_df, stats)
        logger.update_final_state(final_df)
        summary = logger.get_summary()
        
        assert "📊 Lignes : 3 → 2" in summary
        assert "📑 Colonnes : 1 → 1" in summary
    
    def test_with_nan_values_in_stats(self):
        """Test avec des valeurs NaN dans les statistiques."""
        initial_df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
        stats = {
            'empty_cols_dropped': None,
            'duplicates_removed': None,
            'types_converted': {},
            'missing_filled': {},
            'outliers_corrected': {},
            'whitespace_cleaned': None
        }
        final_df = pd.DataFrame({'A': [1, 2], 'B': [4, 5]})
        
        logger = CleanLogger(initial_df, stats)
        logger.update_final_state(final_df)
        summary = logger.get_summary()
        
        # Doit fonctionner sans erreur
        assert "RAPPORT DE NETTOYAGE DE DONNÉES" in summary
    
    def test_missing_keys_in_stats(self):
        """Test avec des clés manquantes dans les statistiques."""
        initial_df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
        # Statistiques incomplètes
        stats = {'empty_cols_dropped': 0, 'duplicates_removed': 0}
        final_df = pd.DataFrame({'A': [1, 2], 'B': [4, 5]})
        
        logger = CleanLogger(initial_df, stats)
        logger.update_final_state(final_df)
        summary = logger.get_summary()
        
        # Doit fonctionner sans erreur (les clés manquantes seront traitées comme vides)
        assert "RAPPORT DE NETTOYAGE DE DONNÉES" in summary
    
    def test_different_column_names(self):
        """Test avec des noms de colonnes spéciaux."""
        initial_df = pd.DataFrame({'col with space': [1, 2, 3], 'col-with-dash': [4, 5, 6]})
        stats = {'empty_cols_dropped': 0, 'duplicates_removed': 0, 'types_converted': {}, 
                'missing_filled': {}, 'outliers_corrected': {}, 'whitespace_cleaned': 0}
        final_df = pd.DataFrame({'col with space': [1, 2], 'col-with-dash': [4, 5]})
        
        logger = CleanLogger(initial_df, stats)
        logger.update_final_state(final_df)
        summary = logger.get_summary()
        
        # Doit fonctionner sans erreur
        assert "RAPPORT DE NETTOYAGE DE DONNÉES" in summary
        
def test_get_summary_section_with_none_values():
    """Test de _get_summary_section avec valeurs None"""
    mock_profiler = Mock()
    mock_logger = Mock()
    
    mock_profiler.has_profile.return_value = True
    mock_profiler.get_profile.return_value = {
        'total_rows': None,
        'missing_values': 50
    }
    
    reporter = CleanerReporter(mock_profiler, mock_logger)
    summary = reporter._get_summary_section()
    assert "Résumé des Métriques" in summary

def test_get_operations_table_with_special_characters():
    """Test de _get_operations_table avec caractères spéciaux"""
    mock_profiler = Mock()
    mock_logger = Mock()
    
    mock_logger.operations_log = [
        {
            'column': 'nom|avec|pipes',
            'action': 'suppression*',
            'details': 'valeurs vides',
            'status': 'terminé'
        }
    ]
    
    reporter = CleanerReporter(mock_profiler, mock_logger)
    operations = reporter._get_operations_table({})
    assert "Détail des Opérations" in operations    

if __name__ == "__main__":
    pytest.main([__file__, "-v"])