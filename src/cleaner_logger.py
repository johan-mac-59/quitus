import pandas as pd
from typing import Dict


class CleanLogger:
    """Gère les logs et l'affichage des statistiques du nettoyage."""
    
    def __init__(self, initial_df: pd.DataFrame, stats: dict):
        self.initial_df = initial_df
        self.stats = stats
        self.final_shape = None
        self.final_columns = None

    def update_final_state(self, final_df: pd.DataFrame):
        """Met à jour les statistiques finales."""
        self.final_shape = final_df.shape
        self.final_columns = list(final_df.columns)

    def get_summary(self) -> str:
        """Génère un résumé des opérations effectuées."""
        if self.final_shape is None or self.final_columns is None:
            return "⚠️ Rapport non finalisé. Veuillez exécuter update_final_state().\n"
        
        summary = f"## RAPPORT DE NETTOYAGE DE DONNÉES\n\n"
        summary += f"📊 Lignes : {self.initial_df.shape[0]} → {self.final_shape[0]}\n"
        summary += f"📑 Colonnes : {self.initial_df.shape[1]} → {self.final_shape[1]}\n\n"
        
        # Ajout des opérations
        if (self.stats.get('empty_cols_dropped') or 0) > 0:
            summary += f"🗑️ Colonnes supprimées (vides) : {self.stats['empty_cols_dropped']}\n"
        if (self.stats.get('whitespace_cleaned') or 0) > 0:
            summary += f"🧼 Espaces nettoyés : {self.stats['whitespace_cleaned']}\n"
        if self.stats.get('case_normalized', {}):
            summary += f"🔤 Casse uniformisée : {len(self.stats['case_normalized'])} colonnes\n"
        if (self.stats.get('duplicates_removed') or 0) > 0:
            summary += f"🔄 Doublons supprimés : {self.stats['duplicates_removed']}\n"
        if self.stats.get('types_fixed_pandas', {}):
            summary += f"🔧 Corrections Pandas Trap : {len(self.stats['types_fixed_pandas'])} colonnes\n"
        if self.stats.get('types_converted', {}):
            summary += f"🎨 Types convertis : {len(self.stats['types_converted'])} colonnes\n"
        if self.stats.get('missing_filled', {}):
            missing_stats = self.stats['missing_filled']
            
            # Vérifier si le traitement a été ignoré par l'utilisateur
            if isinstance(missing_stats, dict) and 'ignored' in missing_stats:
                summary += f"💧 Valeurs manquantes comblées : Traitement ignoré par l'utilisateur\n"
            else:
                # Calcul normal du total de valeurs comblées
                total_missing = 0
                for v in missing_stats.values():
                    if isinstance(v, dict) and 'count' in v:
                        total_missing += v['count']
                    elif isinstance(v, (int, float)):
                        total_missing += v
                summary += f"💧 Valeurs manquantes comblées : {total_missing}\n"
        if self.stats.get('outliers_corrected', {}):
            # Gestion sécurisée des outliers corrigés
            outliers_corr = self.stats['outliers_corrected']
            
            # Si c'est un dictionnaire avec la clé 'ignored', cela signifie que l'utilisateur a ignoré
            if isinstance(outliers_corr, dict) and 'ignored' in outliers_corr:
                summary += f"📈 Outliers corrigés (IQR) : Traitement ignoré par l'utilisateur\n"
            else:
                # Calcul classique des outliers
                total_outliers = 0
                try:
                    # On vérifie que toutes les valeurs sont numériques avant d'additionner
                    if isinstance(outliers_corr, dict):
                        for value in outliers_corr.values():
                            if isinstance(value, (int, float)):
                                total_outliers += value
                    summary += f"📈 Outliers corrigés (IQR) : {total_outliers}\n"
                except (TypeError, ValueError):
                    # En cas d'erreur de type, on indique que les données sont invalides
                    summary += f"📈 Outliers corrigés (IQR) : Données non valides\n"
            
        return summary

    def get_detailed_table(self, final_df: pd.DataFrame = None) -> pd.DataFrame:
        """Retourne un DataFrame résumé des changements (optionnel, pour affichage tabulaire)."""
        
        # On compare les types avant/après si le DataFrame final est fourni
        type_changes = []
        if final_df is not None:
            for col in self.initial_df.columns:
                if col in final_df.columns:
                    before_type = self.initial_df[col].dtype
                    after_type = final_df[col].dtype
                    if str(before_type) != str(after_type):
                        type_changes.append({
                            'Colonne': col,
                            'Type Avant': before_type,
                            'Type Après': after_type
                        })
        
        return pd.DataFrame(type_changes)

    def _format_delta(self, old_val, new_val):
        """Formatte la différence entre deux valeurs."""
        delta = new_val - old_val
        if delta > 0:
            return f"+{delta}"
        elif delta < 0:
            return f"{delta}"
        else:
            return "+0"


def generate_and_print_report(initial_df: pd.DataFrame, stats: Dict, final_df: pd.DataFrame):
    """Fonction utilitaire rapide pour générer et afficher."""
    reporter = CleanLogger(initial_df, stats)
    reporter.update_final_state(final_df)
    print(reporter.get_summary())
