from pathlib import Path
from datetime import datetime
import logging

from src.horodatage import horodater

class CleanerReporter:
    """Génère un rapport détaillé du nettoyage des données."""
    
    def __init__(self, profiler, logger, source_file_path=None):
        self.profiler = profiler
        self.logger = logger
        self.source_file_path = source_file_path
        self.report_title = "Rapport de Nettoyage des Données"
    
    def _get_header(self) -> str:
        """Crée l'en-tête Markdown avec la date."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if self.source_file_path:
            source_filename = Path(self.source_file_path).name
            return f"# {self.report_title}\n\n" \
                   f"**Date de génération :** {timestamp}\n\n" \
                   f"**Fichier source :** `{source_filename}`\n\n"
        else:
            return f"# {self.report_title}\n\n" \
                   f"**Date de génération :** {timestamp}\n\n" \
                   f"**Fichier source :** `Inconnu`\n\n"
    
    def _get_summary_section(self) -> str:
        """Résumé des métriques globales (Avant/Après)."""
        try:
            profile_results = self.profiler.profile_results
            
            if not profile_results:
                return "## Résumé Global\n\n*Aucun profilage disponible.*\n\n"
            
            shape = profile_results.get('shape', {})
            nb_lignes_avant = shape.get('nb_lignes', 'N/A')
            nb_colonnes = shape.get('nb_colonnes', 'N/A')
            nb_doublons = profile_results.get('nb_doublons', 0)
            
            missing_values = profile_results.get('missing_values', {})
            total_missing = sum(missing_values.get('count', {}).values()) if missing_values else 0
            
            return f"""## 1. Résumé des Métriques
| Statistique | Valeur |
| :--- | :---: |
| Lignes totales (avant) | {nb_lignes_avant} |
| Colonnes totales | {nb_colonnes} |
| Doublons trouvés | {nb_doublons} |
| Valeurs manquantes totales | {total_missing} |
"""
        except Exception as e:
            return f"## Résumé des Métriques\n\n*Erreur lors de la récupération des métriques : {str(e)}*\n\n"

    def _get_operations_table(self, stats) -> str:
        """Transforme les statistiques de nettoyage en tableau Markdown détaillé."""
        if not stats:
            return "## 2. Détail des Opérations\n\n*Aucune opération enregistrée.*\n\n"
        
        table_content = "## 2. Détail des Opérations\n\n"
        has_operations = False

        # --- Helper sécurisé pour additionner ---
        def safe_add(num1, num2):
            """Additionne deux valeurs en tolérant les types non numériques.

            Args:
                num1: Première valeur.
                num2: Seconde valeur.

            Returns:
                La somme, ou la première valeur si l'addition est impossible.
            """
            try:
                return int(num1) + int(num2)
            except (ValueError, TypeError):
                return 0

        # --- Colonnes vides supprimées ---
        if 'empty_cols_dropped' in stats and stats['empty_cols_dropped']:
            val = int(stats['empty_cols_dropped'])
            if val > 0:
                table_content += f"### Colonnes vides supprimées\n\n"
                table_content += f"Total de colonnes supprimées : {val}\n\n"
                has_operations = True

        # --- Espaces nettoyés ---
        if 'whitespace_cleaned' in stats and stats['whitespace_cleaned']:
            val = int(stats['whitespace_cleaned'])
            if val > 0:
                table_content += f"### Espaces nettoyés\n\n"
                table_content += f"Total d'espaces nettoyés : {val}\n\n"
                has_operations = True
                
        # --- Caisse uniformisée ---
        case_norm = stats.get('case_normalized', {})
        if case_norm:
            total_changes = sum(int(c) for c in case_norm.values() if isinstance(c, (int, float)))
            if total_changes > 0:
                table_content += f"### Uniformisation de la casse\n\n"
                table_content += f"Total de colonnes avec casse corrigée : {len(case_norm)}\n\n"
                table_content += "| Colonne | Modifications |\n"
                table_content += "| :--- | :---: |\n"
                for col, count in case_norm.items():
                    try:
                        table_content += f"| {col} | {int(count)} |\n"
                    except (ValueError, TypeError):
                        table_content += f"| {col} | N/A |\n"
                table_content += "\n"
                has_operations = True
                
        # --- Doublons supprimés ---
        if 'duplicates_removed' in stats and stats['duplicates_removed']:
            val = int(stats['duplicates_removed'])
            if val > 0:
                table_content += f"### Doublons supprimés\n\n"
                table_content += f"Total de doublons supprimés : {val}\n\n"
                has_operations = True
                
        # --- Conversions de types ---
        types_conv = stats.get('types_converted', {})
        if types_conv:
            illisibles = stats.get('values_unparsed', {}) or {}
            table_content += f"### Conversions de types\n\n"
            table_content += f"Total de conversions effectuées : {len(types_conv)}\n\n"
            # Structure réelle : {colonne: ['object -> float']}. Les en-têtes
            # annonçaient autrefois l'inverse (« Type converti | Colonnes »).
            table_content += "| Colonne | Conversion | Valeurs illisibles vidées |\n"
            table_content += "| :--- | :--- | :--- |\n"

            for col_name, conversions in types_conv.items():
                if isinstance(conversions, list):
                    conv_display = ', '.join(str(c) for c in conversions)
                else:
                    conv_display = str(conversions)  # Au cas où c'est un string direct
                perte = illisibles.get(col_name)
                perte_display = str(perte.get('count', 0)) if isinstance(perte, dict) else "0"
                table_content += f"| {col_name} | {conv_display} | {perte_display} |\n"
            table_content += "\n"

            # Détail des valeurs vidées : une conversion ne doit jamais perdre
            # de données sans que l'utilisateur puisse voir lesquelles.
            if illisibles:
                table_content += "#### ⚠️ Valeurs illisibles vidées lors de la conversion\n\n"
                table_content += ("Ces valeurs étaient présentes mais n'ont pu être lues dans le type "
                                  "de la colonne. Elles sont devenues manquantes : vérifiez-les dans "
                                  "la source.\n\n")
                table_content += "| Colonne | Nombre | Exemples |\n| :--- | :--- | :--- |\n"
                for col_name, perte in illisibles.items():
                    if not isinstance(perte, dict):
                        continue
                    exemples = ', '.join(f"`{e}`" for e in perte.get('examples', []))
                    table_content += f"| {col_name} | {perte.get('count', 0)} | {exemples} |\n"
                table_content += "\n"
            has_operations = True
            
        # --- Valeurs manquantes comblées (Missing Values) ---
        missing_filled = stats.get('missing_filled', {})
        
        if missing_filled:
            # Vérifier si le traitement a été ignoré
            is_ignored = False
            ignored_message = ""
            
            if isinstance(missing_filled, dict) and 'ignored' in missing_filled:
                is_ignored = True
                ignored_message = "Traitement ignoré par l'utilisateur"
            else:
                # Calcul normal du total de valeurs comblées
                total_missing = 0
                for info in missing_filled.values():
                    try:
                        if isinstance(info, dict):
                            total_missing += int(info.get('count', 0))
                        elif isinstance(info, (int, float)):
                            total_missing += int(info)
                    except (ValueError, TypeError):
                        pass 

                # Si des valeurs ont été comblées, on affiche le détail
                if total_missing > 0:
                    table_content += f"### Valeurs manquantes comblées\n\n"
                    table_content += f"**Total de valeurs manquantes comblées :** {total_missing}\n\n"
                    table_content += "| Colonne | Nb valeurs comblées | Méthode utilisée |\n"
                    table_content += "| :--- | :---: | :--- |\n"
                    
                    for col, info in missing_filled.items():
                        try:
                            if isinstance(info, dict):
                                c = int(info.get('count', 0))
                                m = str(info.get('method', 'inconnue'))
                            else:
                                c = int(info)
                                m = "inconnue"
                            table_content += f"| {col} | {c} | {m} |\n"
                        except (ValueError, TypeError):
                            table_content += f"| {col} | ? | ? |\n"
                    table_content += "\n"
                    has_operations = True
                else:
                    # Pas de valeurs à combler mais le traitement était actif
                    table_content += f"### Valeurs manquantes comblées\n\n"
                    table_content += f"*Aucune valeur manquante nécessitant un comblement.*\n\n"
                    has_operations = True

            # Si ignoré par l'utilisateur, on affiche le message spécifique
            if is_ignored:
                table_content += f"### Valeurs manquantes comblées\n\n"
                table_content += f"⚠️ **Traitement des valeurs manquantes non effectué.**\n\n"
                table_content += f"*(Raison : {ignored_message})*\n\n"
                
        # --- Valeurs aberrantes corrigées (Outliers) ---
        outliers_corr = stats.get('outliers_corrected', {})
        if outliers_corr:
            # Vérification : Est-ce que l'utilisateur a ignoré le traitement ?
            is_ignored = False
            ignored_message = ""
            
            # Vérifier si c'est un format ignoré (comme dans cleaner_engine.py)
            if isinstance(outliers_corr, dict) and 'ignored' in outliers_corr:
                is_ignored = True
                ignored_message = "Traitement ignoré par l'utilisateur"
            else:
                # Ancienne logique : vérification sur les valeurs
                for msg in outliers_corr.values():
                    if isinstance(msg, str) and ("ignore" in msg.lower() or "non effectuée" in msg.lower()):
                        is_ignored = True
                        ignored_message = msg
                        break

            if is_ignored:
                table_content += f"### Valeurs aberrantes corrigées\n\n"
                table_content += f"⚠️ **Traitement des valeurs aberrantes non effectué.**\n\n"
                table_content += f"*(Raison : {ignored_message})*\n\n"
            else:
                # Le traitement a eu lieu, on affiche le tableau classique
                total_outliers = 0
                for count in outliers_corr.values():
                    try:
                        total_outliers += int(count)
                    except (ValueError, TypeError):
                        pass 
                
                table_content += f"### Valeurs aberrantes corrigées\n\n"
                table_content += f"**Total de valeurs aberrantes traitées :** {total_outliers}\n\n"
                table_content += "| Colonne | Nb outliers / Statut |\n"
                table_content += "| :--- | :---: |\n"
                
                for col, count in outliers_corr.items():
                    try:
                        val = int(count)
                        table_content += f"| {col} | {val} corrigés |\n"
                    except (ValueError, TypeError):
                        table_content += f"| {col} | Données non valides |\n"
                table_content += "\n"
            has_operations = True

        if not has_operations:
            return "## 2. Détail des Opérations\n\n*Aucune opération enregistrée.*\n\n"
        
        return table_content
            
    def demander_generation_rapport(self, *, answer: bool = None) -> bool:
        """Décide s'il faut générer le rapport de nettoyage.

        Args:
            answer: Réponse imposée ; court-circuite l'invite si elle est
                fournie. C'est par ce paramètre que l'interface web transmet le
                choix fait dans une case à cocher.

        Returns:
            True s'il faut générer le rapport, False sinon.
        """
        if answer is not None:
            return answer

        print("\n" + "=" * 60)
        print("📊 Génération du Rapport de Nettoyage")
        print("=" * 60)
        print("Souhaitez-vous générer le rapport détaillé de nettoyage ?")
        print("(Cela créera un fichier avec les statistiques et comparaisons)")
        print("Répondez par 'y' (oui) ou 'n' (non).")
        print("Par défaut : 'y' (générer le rapport)")

        while True:
            try:
                reponse = input("⏳ Votre choix [y/n, entrée par défaut 'y'] : ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                # Sans terminal (serveur web, sortie redirigée, CI), on retient
                # le défaut documenté plutôt que de lever ou de boucler sans fin.
                print("\nℹ️ Aucune réponse lisible : génération du rapport par défaut.")
                return True

            if reponse == "":
                print("✅ Choix par défaut : Générer le rapport")
                return True
            if reponse in ['y', 'yes', 'o', 'oui']:
                return True
            if reponse in ['n', 'no', 'non']:
                return False

            print("⚠️ Veuillez répondre par 'y' (oui) ou 'n' (non).")
            print("⏳  Appuyez sur Entrée pour choisir 'y' par défaut.")

    def render(self, stats: dict = None) -> str:
        """Produit le contenu du rapport en mémoire, sans accès au disque.

        C'est ce que consomme l'interface web pour proposer le rapport au
        téléchargement sans rien écrire sur le serveur.

        Args:
            stats: Statistiques de nettoyage à détailler.

        Returns:
            Le contenu Markdown du rapport.
        """
        return (self._get_header()
                + self._get_summary_section()
                + self._get_operations_table(stats))

    def generate_with_stats(self, output_path: str, stats: dict = None) -> str:
        """Génère le fichier Markdown complet avec les statistiques.

        Args:
            output_path: Chemin du fichier à écrire.
            stats: Statistiques de nettoyage à détailler.

        Returns:
            Le chemin absolu du fichier écrit.

        Raises:
            RuntimeError: Si l'écriture échoue.
        """
        try:
            content = self.render(stats)

            path_obj = Path(output_path)
            # Vérification du répertoire parent
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            path_obj.write_text(content, encoding="utf-8")
            self.logger.info(f"Rapport généré avec succès : {path_obj.absolute()}")
            return str(path_obj.absolute())

        except Exception as e:
            self.logger.error(f"Erreur lors de la génération du rapport : {str(e)}")
            raise RuntimeError(f"Erreur lors de la génération du rapport : {str(e)}")

    def generate(self, output_path: str = "cleaning_report.md") -> str:
        """Génère le fichier Markdown complet (ancienne version).

        Args:
            output_path: Chemin du fichier à écrire.

        Returns:
            Le chemin absolu du fichier écrit.
        """
        return self.generate_with_stats(output_path, {})


def build_cleaning_report_path(reports_dir, input_file, horodatage: str = None) -> Path:
    """Compose le chemin horodaté d'un rapport de nettoyage.

    Args:
        reports_dir: Répertoire de destination.
        input_file: Fichier source, dont le nom de base est réutilisé.
        horodatage: Suffixe imposé, pour que tous les fichiers d'une même
            exécution partagent la même marque ; l'instant présent si omis.

    Returns:
        Le chemin complet du rapport.
    """
    suffixe = horodatage or horodater()
    return Path(reports_dir) / f"cleaning_report_{Path(input_file).stem}_{suffixe}.md"


def generate_enhanced_report(profiler, logger, reports_dir, input_file, stats,
                             *, generate: bool = None, horodatage: str = None):
    """Génère le rapport de nettoyage détaillé.

    Args:
        profiler: Objet exposant un attribut `profile_results`. Un simple
            `SimpleNamespace(profile_results=...)` suffit : c'est le seul
            attribut lu.
        logger: Journal exposant `.info()` et `.error()`.
        reports_dir: Répertoire de destination.
        input_file: Fichier source, dont le nom de base est réutilisé.
        stats: Statistiques de nettoyage à détailler.
        generate: Décision imposée — True génère sans demander, False saute
            l'étape, None pose la question en terminal.
        horodatage: Suffixe commun aux fichiers de l'exécution en cours.

    Returns:
        Le chemin du rapport écrit, ou None si l'étape a été sautée ou a échoué.
    """
    try:
        # Initialisation du reporter avec le chemin du fichier source
        reporter = CleanerReporter(profiler, logger, source_file_path=str(input_file))

        if not reporter.demander_generation_rapport(answer=generate):
            print("✅ Rapport de nettoyage ignoré. Suite du pipeline...")
            return None

        final_report_filename = build_cleaning_report_path(reports_dir, input_file,
                                                           horodatage=horodatage)

        report_path = reporter.generate_with_stats(str(final_report_filename), stats)
        print(f"📝 Rapport de nettoyage généré : {report_path}")
        return report_path

    except Exception as e:
        print(f"⚠️ Erreur lors de la génération du rapport final : {e}")
        return None
