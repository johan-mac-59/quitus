"""Point d'entrée en ligne de commande du pipeline de nettoyage.

Ce script est l'une des deux façades du projet, l'autre étant `streamlit_app.py`
(interface web Streamlit). Toute la logique métier vit dans `src/`, qui ne
connaît ni l'une ni l'autre : les questions posées ici en terminal sont
transmises aux modules sous forme de paramètres explicites.

Usage :
    python main.py
    python main.py --input data/samples/exemple.csv
    python main.py --input mon.csv --output propre.csv --reports rapports/
    python main.py --input mon.csv --oui-a-tout        # aucune question posée
"""

import argparse
import logging
import sys
from pathlib import Path

from src.cleaner_engine import get_user_decisions, run_all_cleaning_steps
from src.cleaner_logger import generate_and_print_report
from src.cleaner_reporter import generate_enhanced_report
from src.data_profiler import ExploratoryProfiler, PreCleaningProfiler
from src.file_loader import load_file

# Chemins par défaut, relatifs à la racine du projet.
DEFAUT_INPUT = "data/samples/reservations_exemple.csv"
DEFAUT_OUTPUT = "data/processed/dataset_nettoye.csv"
DEFAUT_REPORTS = "data/reports"


def _forcer_encodage_utf8() -> None:
    """Force la sortie console en UTF-8.

    Sous Windows, dès que la sortie est redirigée (vers un fichier, un tube,
    un journal d'intégration continue), Python retombe sur l'encodage ANSI du
    système — généralement cp1252, incapable d'encoder les emojis dont le
    pipeline se sert abondamment. Sans cet appel, le script lève un
    `UnicodeEncodeError` dès son premier message.
    """
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            # Flux non reconfigurable (déjà remplacé, ou non textuel) : on
            # laisse tel quel plutôt que de faire échouer le démarrage.
            pass


def construire_parseur() -> argparse.ArgumentParser:
    """Construit le parseur d'arguments de la ligne de commande.

    Returns:
        Le parseur configuré.
    """
    parseur = argparse.ArgumentParser(
        prog="main.py",
        description="Profile et nettoie un fichier CSV, Excel ou JSON, "
                    "puis produit des rapports d'audit.",
        epilog="Interface web équivalente : streamlit run streamlit_app.py",
    )
    parseur.add_argument(
        "--input", "-i", default=DEFAUT_INPUT,
        help=f"Fichier à nettoyer (défaut : {DEFAUT_INPUT})",
    )
    parseur.add_argument(
        "--output", "-o", default=DEFAUT_OUTPUT,
        help=f"Fichier CSV de sortie (défaut : {DEFAUT_OUTPUT})",
    )
    parseur.add_argument(
        "--reports", "-r", default=DEFAUT_REPORTS,
        help=f"Répertoire des rapports (défaut : {DEFAUT_REPORTS})",
    )
    parseur.add_argument(
        "--format-rapport", choices=["md", "html"], default=None,
        help="Format des rapports de profilage. Sans cette option, la question "
             "est posée de manière interactive.",
    )
    parseur.add_argument(
        "--oui-a-tout", action="store_true",
        help="Accepte tous les traitements sans rien demander : écrêtage des "
             "outliers, remplissage des valeurs manquantes et rapports.",
    )
    parseur.add_argument(
        "--non-interactif", action="store_true",
        help="Ne pose aucune question et refuse les traitements lourds "
             "(outliers, valeurs manquantes).",
    )
    return parseur


def resoudre_chemins(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    """Résout et valide les chemins d'entrée et de sortie.

    Args:
        args: Arguments analysés de la ligne de commande.

    Returns:
        Le triplet (fichier d'entrée, fichier de sortie, répertoire des rapports).

    Raises:
        FileNotFoundError: Si le fichier source est introuvable.
    """
    base_dir = Path(__file__).parent

    def _resoudre(valeur: str) -> Path:
        chemin = Path(valeur)
        return chemin if chemin.is_absolute() else base_dir / chemin

    input_file = _resoudre(args.input)
    output_file = _resoudre(args.output)
    reports_dir = _resoudre(args.reports)

    if not input_file.exists():
        raise FileNotFoundError(
            f"❌ ERREUR DE CONFIGURATION :\n"
            f"Le fichier source est introuvable à l'emplacement suivant :\n"
            f"👉 {input_file.resolve()}\n\n"
            f"Indiquez un autre fichier avec l'option --input."
        )

    output_file.parent.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    return input_file, output_file, reports_dir


def main(argv: list[str] = None) -> int:
    """Exécute le pipeline complet : charger, profiler, nettoyer, rapporter.

    Args:
        argv: Arguments de ligne de commande ; `sys.argv` par défaut.

    Returns:
        0 si le pipeline s'est déroulé jusqu'au bout, 1 en cas d'échec bloquant.
    """
    _forcer_encodage_utf8()

    args = construire_parseur().parse_args(argv)

    # Traduction des drapeaux en décisions explicites, transmises aux modules.
    if args.oui_a_tout:
        decisions = {"correct_outliers": True, "fill_missing": True}
        generer_rapport, interactive = True, False
        format_rapport = args.format_rapport or "md"
    elif args.non_interactif:
        decisions = {"correct_outliers": False, "fill_missing": False}
        generer_rapport, interactive = True, False
        format_rapport = args.format_rapport or "md"
    else:
        decisions = {"correct_outliers": None, "fill_missing": None}
        generer_rapport, interactive = None, True
        format_rapport = args.format_rapport

    # 1. Configuration des chemins
    try:
        input_file, output_file, reports_dir = resoudre_chemins(args)
    except FileNotFoundError as e:
        print(e)
        return 1

    # 2. Chargement
    print("⏳ Chargement du fichier...")
    try:
        initial_df = load_file(str(input_file))
    except Exception as e:
        print(f"❌ Impossible de charger le fichier : {e}")
        return 1

    if initial_df.empty:
        print("❌ Le fichier est vide : rien à nettoyer.")
        return 1

    print(f"✅ Fichier chargé ({initial_df.shape[0]} lignes, {initial_df.shape[1]} colonnes)\n")

    # 3. Profilage pré-nettoyage
    profiler = PreCleaningProfiler(initial_df, input_file)
    profiler_results = profiler.run_profiling_workflow(
        input_file, reports_dir, report_format=format_rapport
    )

    # 4. Décisions de nettoyage avancé
    correct_outliers, fill_missing = get_user_decisions(
        initial_df, profiler_results, interactive=interactive, **decisions
    )

    # 5. Nettoyage
    try:
        cleaned_df, stats = run_all_cleaning_steps(
            initial_df.copy(),
            profile_info=profiler_results,
            correct_outliers=correct_outliers,
            fill_missing=fill_missing,
        )
        print("\n✅ Nettoyage terminé.")
    except Exception as e:
        print(f"❌ Erreur lors du nettoyage : {e}")
        import traceback
        traceback.print_exc()
        return 1

    # 6. Sauvegarde
    try:
        cleaned_df.to_csv(output_file, index=False, encoding='utf-8')
        print(f"✅ Données nettoyées sauvegardées dans : {output_file}")
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde : {e}")
        return 1

    # 7. Rapport console (comparaison brut / propre)
    try:
        generate_and_print_report(initial_df, stats, cleaned_df)
    except Exception as e:
        print(f"⚠️ Erreur lors de la génération du rapport console : {e}")

    # 8. Rapport de nettoyage Markdown
    try:
        logger = logging.getLogger(__name__)
        chemin_rapport = generate_enhanced_report(
            profiler, logger, reports_dir, input_file, stats, generate=generer_rapport
        )
        if chemin_rapport:
            print(f"📁 Rapport de nettoyage disponible : {chemin_rapport}")
    except Exception as e:
        print(f"⚠️ Erreur lors de la génération du rapport final : {e}")

    # 9. Profilage post-nettoyage (validation)
    post_profiler = ExploratoryProfiler(cleaned_df, output_file)
    post_profiler.run_profiling_workflow(
        output_file, reports_dir, report_format=format_rapport
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
