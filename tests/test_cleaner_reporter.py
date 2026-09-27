import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile
import os

# Assurez-vous que le chemin d'importation est correct
import sys
sys.path.insert(0, 'src')

from cleaner_reporter import CleanerReporter


# ==========================================
# FIXTURES : Données de test simulées
# ==========================================

@pytest.fixture
def mock_profiler():
    """Mock du profiler pour les tests."""
    profiler = Mock()
    profiler.profile_results = {
        'shape': {'nb_lignes': 100, 'nb_colonnes': 5},
        'nb_doublons': 5,
        'missing_values': {
            'count': {'col1': 10, 'col2': 5},
            'percent': {'col1': 10.0, 'col2': 5.0}
        }
    }
    return profiler

@pytest.fixture
def mock_logger():
    """Mock du logger pour les tests."""
    logger = Mock()
    return logger

@pytest.fixture
def sample_stats():
    """Données d'exemple pour les statistiques de nettoyage."""
    return {
        'empty_cols_dropped': 2,
        'whitespace_cleaned': 15,
        'duplicates_removed': 3,
        'types_converted': {'col1': ['object -> int']},
        'missing_filled': {'col2': {'count': 5, 'method': 'fill_median_30.0'}},
        'outliers_corrected': {'col3': 2}
    }

# ==========================================
# TESTS NOMINAUX (Cas simples)
# ==========================================

class TestCleanerReporterInitialization:
    def test_initialization_with_file_path(self, mock_profiler, mock_logger):
        """Test de l'initialisation du CleanerReporter avec un chemin de fichier."""
        reporter = CleanerReporter(mock_profiler, mock_logger, source_file_path="/chemin/vers/fichier.csv")
        
        assert reporter.profiler == mock_profiler
        assert reporter.logger == mock_logger
        assert reporter.source_file_path == "/chemin/vers/fichier.csv"

    def test_initialization_without_file_path(self, mock_profiler, mock_logger):
        """Test de l'initialisation du CleanerReporter sans chemin de fichier."""
        reporter = CleanerReporter(mock_profiler, mock_logger)
        
        assert reporter.profiler == mock_profiler
        assert reporter.logger == mock_logger
        assert reporter.source_file_path is None


class TestGetHeader:
    def test_get_header_with_valid_file_path(self, mock_profiler, mock_logger):
        """Test de _get_header avec un chemin de fichier valide."""
        reporter = CleanerReporter(mock_profiler, mock_logger, source_file_path="/chemin/vers/fichier.csv")
        header = reporter._get_header()
        
        assert "# Rapport de Nettoyage des Données" in header
        assert "Date de génération :" in header
        assert "`fichier.csv`" in header

    def test_get_header_without_file_path(self, mock_profiler, mock_logger):
        """Test de _get_header sans chemin de fichier."""
        reporter = CleanerReporter(mock_profiler, mock_logger)
        header = reporter._get_header()
        
        assert "# Rapport de Nettoyage des Données" in header
        assert "Date de génération :" in header
        assert "`Inconnu`" in header


class TestGetSummarySection:
    def test_get_summary_section_with_profile(self, mock_profiler, mock_logger):
        """Test de _get_summary_section avec un profil valide."""
        reporter = CleanerReporter(mock_profiler, mock_logger)
        summary = reporter._get_summary_section()
        
        assert "Rapport de Nettoyage des Données" not in summary  # C'est le titre du rapport
        assert "Lignes totales (avant)" in summary
        assert "Colonnes totales" in summary
        assert "Doublons trouvés" in summary
        assert "Valeurs manquantes totales" in summary

    def test_get_summary_section_without_profile(self, mock_logger):
        """Test de _get_summary_section sans profil."""
        profiler = Mock()
        profiler.profile_results = None
        
        reporter = CleanerReporter(profiler, mock_logger)
        summary = reporter._get_summary_section()
        
        assert "Aucun profilage disponible" in summary

    def test_get_summary_section_with_exception(self, mock_logger):
        """Test de _get_summary_section avec une exception."""
        profiler = Mock()
        profiler.profile_results = "not_a_dict"
        
        reporter = CleanerReporter(profiler, mock_logger)
        summary = reporter._get_summary_section()
        
        assert "Erreur lors de la récupération des métriques" in summary


class TestGetOperationsTable:
    def test_get_operations_table_with_valid_stats(self, mock_profiler, mock_logger, sample_stats):
        """Test de _get_operations_table avec des statistiques valides."""
        reporter = CleanerReporter(mock_profiler, mock_logger)
        operations = reporter._get_operations_table(sample_stats)
        
        assert "Détail des Opérations" in operations
        assert "Colonnes vides supprimées" in operations
        assert "Espaces nettoyés" in operations
        assert "Doublons supprimés" in operations
        assert "Conversions de types" in operations
        assert "Valeurs manquantes comblées" in operations
        assert "Valeurs aberrantes corrigées" in operations

    def test_get_operations_table_with_empty_stats(self, mock_profiler, mock_logger):
        """Test de _get_operations_table avec des statistiques vides."""
        reporter = CleanerReporter(mock_profiler, mock_logger)
        operations = reporter._get_operations_table({})
        
        assert "Aucune opération enregistrée" in operations

    def test_get_operations_table_with_none_stats(self, mock_profiler, mock_logger):
        """Test de _get_operations_table avec des statistiques None."""
        reporter = CleanerReporter(mock_profiler, mock_logger)
        operations = reporter._get_operations_table(None)
        
        assert "Aucune opération enregistrée" in operations


class TestGenerateReport:
    def test_generate_with_success(self, mock_profiler, mock_logger, sample_stats):
        """Test de la méthode generate_with_stats avec succès."""
        reporter = CleanerReporter(mock_profiler, mock_logger)
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = os.path.join(tmp_dir, "test_report.md")
            
            result_path = reporter.generate_with_stats(output_path, sample_stats)
            
            # Vérification que le fichier a été créé
            assert os.path.exists(result_path)
            # Vérification du contenu principal
            content = open(result_path, 'r', encoding='utf-8').read()
            assert "Rapport de Nettoyage des Données" in content
            assert "Détail des Opérations" in content

    def test_generate_with_exception(self, mock_profiler, mock_logger):
        """Test de la méthode generate_with_stats avec une exception."""
        reporter = CleanerReporter(mock_profiler, mock_logger)

        # generate_with_stats crée désormais l'arborescence manquante, donc un simple
        # chemin inexistant ne suffit plus à provoquer une erreur. On écrit dans un
        # chemin dont un composant intermédiaire est un fichier : impossible à créer
        # comme répertoire, sur tous les OS.
        with tempfile.TemporaryDirectory() as tmp_dir:
            blocker = os.path.join(tmp_dir, "fichier_bloquant")
            with open(blocker, "w", encoding="utf-8") as f:
                f.write("je ne suis pas un dossier")

            with pytest.raises(RuntimeError):
                reporter.generate_with_stats(os.path.join(blocker, "rapport.md"))


class TestGenerateMethod:
    def test_generate_method(self, mock_profiler, mock_logger):
        """Test de la méthode generate (ancienne version)."""
        reporter = CleanerReporter(mock_profiler, mock_logger)
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = os.path.join(tmp_dir, "test_report.md")
            
            # La méthode generate devrait fonctionner sans erreur
            result_path = reporter.generate(output_path)
            assert os.path.exists(result_path)


# ==========================================
# TESTS LIMITES (Cas spéciaux)
# ==========================================

class TestEdgeCases:
    def test_empty_profile_results(self, mock_logger):
        """Test avec des résultats de profilage vides."""
        profiler = Mock()
        profiler.profile_results = {}
        
        reporter = CleanerReporter(profiler, mock_logger)
        summary = reporter._get_summary_section()
        
        assert "Rapport de Nettoyage des Données" not in summary
        # Vérifie qu'il n'y a pas d'erreur

    def test_invalid_profile_results(self, mock_logger):
        """Test avec des résultats de profilage invalides."""
        profiler = Mock()
        profiler.profile_results = "invalid_data"
        
        reporter = CleanerReporter(profiler, mock_logger)
        summary = reporter._get_summary_section()
        
        assert "Erreur lors de la récupération des métriques" in summary

    def test_partial_stats(self, mock_profiler, mock_logger):
        """Test avec des statistiques partielles."""
        partial_stats = {
            'empty_cols_dropped': 1,
            # Pas toutes les clés
        }
        
        reporter = CleanerReporter(mock_profiler, mock_logger)
        operations = reporter._get_operations_table(partial_stats)
        
        assert "Détail des Opérations" in operations
        # Doit fonctionner sans erreur même avec des stats incomplètes