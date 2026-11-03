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
    python main.py --input mon.csv --seuil-iqr 3       # écrêtage plus tolérant
    python main.py --input mon.csv --regles regles.json  # contraintes à vérifier

Les contraintes (valeur minimale ou maximale, longueur, format, comparaison
entre deux colonnes…) sont signalées avant et après nettoyage, jamais corrigées.
Sans `--regles`, le mode interactif propose de les définir par quelques
questions, au vu d'un aperçu du fichier nettoyé, puis de rouvrir la saisie après
le nettoyage final, et d'enregistrer le fichier de règles pour le rejouer.
"""

import argparse
import logging
import sys
from pathlib import Path

from src.cleaner_engine import SEUIL_IQR, get_user_decisions, run_all_cleaning_steps
from src.cleaner_logger import generate_and_print_report
from src.cleaner_reporter import generate_enhanced_report
from src.console_capture import capture_output
from src.data_profiler import ExploratoryProfiler, PreCleaningProfiler
from src.file_loader import load_file
from src.horodatage import horodater
from src.validator import (
    FORMATS_NOMMES,
    LIBELLES_FORMATS,
    OPERATEURS,
    charger_regles,
    decrire_regle,
    formater_bilan,
    nouvelle_regle,
    sauver_regles,
    valider,
    verifier_regle,
)

# Chemins par défaut, relatifs à la racine du projet.
DEFAUT_INPUT = "data/samples/reservations_exemple.csv"
# Sans --output, le fichier nettoyé est nommé d'après la source et horodaté :
# <source>_nettoye_<AAAAMMJJ_HHMMSS>.csv. Un nom fixe écrasait chaque essai.
DEFAUT_REPERTOIRE_SORTIE = "data/processed"
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
        description="Profile et nettoie un fichier CSV, Excel, JSON ou Parquet, "
                    "puis produit des rapports d'audit.",
        epilog="Interface web équivalente : streamlit run streamlit_app.py",
    )
    parseur.add_argument(
        "--input", "-i", default=DEFAUT_INPUT,
        help=f"Fichier à nettoyer (défaut : {DEFAUT_INPUT})",
    )
    parseur.add_argument(
        "--output", "-o", default=None,
        help=f"Fichier CSV de sortie. Par défaut : {DEFAUT_REPERTOIRE_SORTIE}/"
             "<source>_nettoye_<AAAAMMJJ_HHMMSS>.csv, pour qu'aucun essai "
             "n'écrase le précédent.",
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
    parseur.add_argument(
        "--seuil-iqr", type=_seuil_positif, default=SEUIL_IQR,
        help=f"Seuil de l'écrêtage, en écarts interquartiles (défaut : {SEUIL_IQR:g}). "
             "Plus grand, il tolère une dispersion plus forte ; 3 ne retient "
             "que les valeurs très extrêmes.",
    )
    parseur.add_argument(
        "--regles", default=None, metavar="FICHIER",
        help="Fichier de règles (JSON) à vérifier avant et après nettoyage. Les "
             "violations sont signalées, jamais corrigées. Le mode interactif "
             "peut créer ce fichier par questions.",
    )
    return parseur


def _seuil_positif(valeur: str) -> float:
    """Valide le seuil IQR passé en ligne de commande.

    Args:
        valeur: Texte saisi ; la virgule décimale est acceptée.

    Returns:
        Le seuil, strictement positif.

    Raises:
        argparse.ArgumentTypeError: Si la valeur n'est pas un nombre positif.
    """
    try:
        seuil = float(valeur.replace(",", "."))
    except ValueError:
        raise argparse.ArgumentTypeError(f"seuil invalide : {valeur}")
    if seuil <= 0:
        raise argparse.ArgumentTypeError("le seuil doit être strictement positif")
    return seuil


def _choisir(invite: str, options: list[str], saisir) -> int | None:
    """Fait choisir une option dans une liste numérotée.

    Args:
        invite: Question posée.
        options: Libellés proposés, numérotés à partir de 1.
        saisir: Fonction de saisie (`input` en usage normal).

    Returns:
        L'indice (à partir de 0) de l'option choisie, ou None si l'utilisateur
        abandonne en validant une réponse vide.
    """
    print(invite)
    for rang, option in enumerate(options, start=1):
        print(f"   {rang}. {option}")
    while True:
        reponse = saisir("⏳ Votre choix (entrée pour annuler) : ").strip()
        if not reponse:
            return None
        if reponse.isdigit() and 1 <= int(reponse) <= len(options):
            return int(reponse) - 1
        print(f"   Entrez un nombre entre 1 et {len(options)}.")


def _borne(texte: str):
    """Lit une borne saisie : un nombre si possible, sinon un texte (une date).

    Args:
        texte: Saisie de l'utilisateur ; vide pour « pas de borne ».

    Returns:
        None si la saisie est vide, un nombre, ou le texte tel quel.
    """
    texte = texte.strip()
    if not texte:
        return None
    try:
        nombre = float(texte.replace(",", "."))
    except ValueError:
        return texte
    return int(nombre) if nombre.is_integer() else nombre


_TYPES_MENU = [
    ("plage", "valeur minimale et/ou maximale (nombres ou dates)"),
    ("longueur", "nombre de caractères"),
    ("format", "format (e-mail, code postal, téléphone, SIRET…)"),
    ("valeurs_autorisees", "liste de valeurs autorisées"),
    ("non_vide", "valeur obligatoire"),
    ("unique", "valeurs toutes différentes"),
    ("comparaison_colonnes", "comparaison avec une autre colonne"),
]


def _saisir_une_regle(colonnes: list[str], saisir) -> dict | None:
    """Pose les questions nécessaires pour définir une contrainte.

    Args:
        colonnes: Colonnes du fichier, proposées au choix.
        saisir: Fonction de saisie (`input` en usage normal).

    Returns:
        La règle définie, ou None si l'utilisateur a annulé ou si la règle
        obtenue n'est pas valide (le motif est alors expliqué).
    """
    choix = _choisir("\nSur quelle colonne ?", colonnes, saisir)
    if choix is None:
        return None
    colonne = colonnes[choix]
    choix = _choisir("\nQuelle contrainte ?", [libelle for _, libelle in _TYPES_MENU], saisir)
    if choix is None:
        return None
    type_regle = _TYPES_MENU[choix][0]
    cibles, parametres = [colonne], {}

    if type_regle in ("plage", "longueur"):
        for cle, nom in (("min", "minimum"), ("max", "maximum")):
            valeur = _borne(saisir(f"⏳ {nom.capitalize()} (entrée pour aucun) : "))
            if valeur is not None:
                parametres[cle] = valeur
    elif type_regle == "format":
        libelles = [LIBELLES_FORMATS[n] for n in FORMATS_NOMMES] + ["expression régulière personnalisée"]
        choix = _choisir("\nQuel format ?", libelles, saisir)
        if choix is None:
            return None
        if choix < len(FORMATS_NOMMES):
            parametres["nom"] = FORMATS_NOMMES[choix]
        else:
            parametres["motif"] = saisir("⏳ Expression régulière : ").strip()
    elif type_regle == "valeurs_autorisees":
        texte = saisir("⏳ Valeurs autorisées, séparées par des points-virgules : ")
        parametres["valeurs"] = [v.strip() for v in texte.split(";") if v.strip()]
    elif type_regle == "comparaison_colonnes":
        autres = [c for c in colonnes if c != colonne]
        choix = _choisir(f"\n« {colonne} » doit être comparée à quelle colonne ?", autres, saisir)
        if choix is None:
            return None
        cibles.append(autres[choix])
        symboles = list(OPERATEURS)
        choix = _choisir(f"\n« {colonne} » doit être…",
                         [OPERATEURS[s][1] for s in symboles], saisir)
        if choix is None:
            return None
        parametres["operateur"] = symboles[choix]

    regle = nouvelle_regle(type_regle, cibles, parametres)
    problemes = verifier_regle(regle)
    if problemes:
        print(f"⚠️ Contrainte abandonnée : {' ; '.join(problemes)}")
        return None
    return regle


def demander_regles(colonnes: list[str], saisir=input, *, invite: str | None = None,
                    apres_ajout=None) -> list[dict]:
    """Propose, par quelques questions, de définir des contraintes à vérifier.

    Facultatif : une réponse vide, ou l'absence de terminal, termine sans rien
    ajouter. Les contraintes déjà définies sont conservées.

    Args:
        colonnes: Colonnes du fichier chargé.
        saisir: Fonction de saisie (`input` en usage normal), injectable pour
            les tests.
        invite: Première question, pour la reformuler selon le moment du
            pipeline ; la question habituelle par défaut.
        apres_ajout: Fonction appelée avec chaque règle ajoutée, pour montrer
            tout de suite ce qu'elle donne sur les données.

    Returns:
        Les règles définies, éventuellement vides.
    """
    regles = []
    premiere = invite or ("⏳ Ajouter une contrainte à vérifier (valeur minimale, "
                          "longueur, format…) ? [o/N] : ")
    try:
        while True:
            question = premiere if not regles else "⏳ Ajouter une autre contrainte ? [o/N] : "
            if saisir(question).strip().lower() not in ("o", "oui", "y", "yes"):
                break
            regle = _saisir_une_regle(colonnes, saisir)
            if regle is not None:
                regles.append(regle)
                print(f"   ✅ Contrainte ajoutée : {decrire_regle(regle)}")
                if apres_ajout is not None:
                    apres_ajout(regle)
    except (EOFError, KeyboardInterrupt):
        print("\n(saisie interrompue : les contraintes déjà définies sont conservées)")
    return regles


def _retour_immediat(df, titre: str):
    """Fabrique le retour affiché après chaque contrainte ajoutée.

    Args:
        df: Données sur lesquelles la contrainte est essayée.
        titre: Intitulé du bilan.

    Returns:
        Une fonction qui évalue une règle sur `df` et en affiche le résultat.
    """
    def afficher(regle: dict) -> None:
        """Évalue la règle sur les données et affiche son résultat."""
        print(formater_bilan(valider(df, [regle]), titre))
    return afficher


def resoudre_chemins(args: argparse.Namespace, horodatage: str) -> tuple[Path, Path, Path]:
    """Résout et valide les chemins d'entrée et de sortie.

    Args:
        args: Arguments analysés de la ligne de commande.
        horodatage: Suffixe de l'exécution, repris dans le nom du fichier
            nettoyé quand `--output` n'est pas fourni.

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
    reports_dir = _resoudre(args.reports)

    # Un chemin explicite est respecté tel quel ; sinon, nom horodaté.
    if args.output:
        output_file = _resoudre(args.output)
    else:
        output_file = (_resoudre(DEFAUT_REPERTOIRE_SORTIE)
                       / f"{input_file.stem}_nettoye_{horodatage}.csv")

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


def _resoudre_chemin_regles(valeur: str) -> Path:
    """Résout le chemin du fichier de règles, comme les autres chemins.

    Args:
        valeur: Chemin passé à `--regles`.

    Returns:
        Le chemin tel quel s'il est absolu ou existe depuis le dossier courant,
        sinon relatif à la racine du projet.
    """
    chemin = Path(valeur)
    if chemin.is_absolute() or chemin.exists():
        return chemin
    return Path(__file__).parent / chemin


def _proposer_enregistrement(regles: list[dict], reports_dir: Path, input_file: Path,
                             horodatage: str, saisir=input) -> Path | None:
    """Propose d'enregistrer les règles saisies pour les rejouer plus tard.

    Args:
        regles: Règles définies par l'utilisateur.
        reports_dir: Dossier où écrire le fichier.
        input_file: Fichier source, dont le nom est repris dans celui des règles.
        horodatage: Marque de l'exécution, reprise dans le nom du fichier.
        saisir: Fonction de saisie (`input` en usage normal).

    Returns:
        Le chemin du fichier écrit, ou None si l'utilisateur a refusé.
    """
    try:
        reponse = saisir("⏳ Enregistrer ces contraintes pour les rejouer avec "
                         "--regles ? [O/n] : ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return None
    if reponse in ("n", "non", "no"):
        return None
    chemin = sauver_regles(regles, reports_dir / f"regles_{input_file.stem}_{horodatage}.json")
    print(f"📁 Contraintes enregistrées : {chemin}\n")
    return chemin


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

    # Un seul horodatage pour toute l'exécution : le fichier nettoyé et tous ses
    # rapports portent la même marque, ce qui permet de retrouver ce qui va
    # ensemble et de comparer plusieurs essais sans qu'aucun n'écrase l'autre.
    horodatage = horodater()

    # 1. Configuration des chemins
    try:
        input_file, output_file, reports_dir = resoudre_chemins(args, horodatage)
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
        input_file, reports_dir, report_format=format_rapport, horodatage=horodatage
    )

    # 3b. Contraintes : on les énonce au vu du diagnostic, donc après lui. Le
    # fichier de règles n'est lu qu'ici, au moment de la validation. Sans
    # fichier, le mode interactif propose de les définir par questions, sur un
    # aperçu du fichier après un nettoyage automatique léger (ni écrêtage ni
    # remplissage) : une règle comme « âge entre 0 et 120 » s'écrit alors sur de
    # vrais nombres. Les contraintes ne limitent jamais le nettoyage, et la
    # saisie se rouvre après le nettoyage final (7b).
    regles = []
    saisies = False
    if args.regles:
        try:
            regles = charger_regles(_resoudre_chemin_regles(args.regles))
        except (FileNotFoundError, ValueError) as e:
            print(f"❌ {e}")
            return 1
        print(f"📐 {len(regles)} contrainte(s) lue(s) dans {args.regles}\n")
    elif interactive:
        print("🧹 Nettoyage automatique léger, pour vous montrer les données propres...")
        try:
            with capture_output():
                apercu_df, _ = run_all_cleaning_steps(
                    initial_df.copy(), profile_info=profiler_results,
                    correct_outliers=False, fill_missing=False,
                )
        except Exception as e:
            print(f"⚠️ Aperçu indisponible ({e}) : les contraintes seront essayées sur le fichier brut.")
            apercu_df = initial_df
        regles = demander_regles(
            list(apercu_df.columns),
            apres_ajout=_retour_immediat(apercu_df, "Aperçu après nettoyage automatique"),
        )
        saisies = bool(regles)
    contraintes = {}
    if regles:
        contraintes["avant"] = valider(initial_df, regles)
        print(formater_bilan(contraintes["avant"], "Contraintes avant nettoyage") + "\n")

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
            # La ligne de commande applique le même seuil à toutes les colonnes.
            outlier_thresholds={col: args.seuil_iqr for col in initial_df.columns},
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

    # 7b. Contraintes après nettoyage : signalées, jamais corrigées. La saisie
    # se rouvre ici : le nettoyage peut laisser passer des anomalies, ou en
    # révéler d'autres, et l'utilisateur doit pouvoir en ajouter.
    if regles:
        contraintes["apres"] = valider(cleaned_df, regles)
        print("\n" + formater_bilan(contraintes["apres"], "Contraintes après nettoyage"))
    if interactive:
        nouvelles = demander_regles(
            list(cleaned_df.columns),
            invite="⏳ Une anomalie vous a échappé ? Ajouter une contrainte sur le fichier "
                   "nettoyé ? [o/N] : ",
            apres_ajout=_retour_immediat(cleaned_df, "Fichier nettoyé"),
        )
        if nouvelles:
            regles = regles + nouvelles
            saisies = True
            contraintes["avant"] = valider(initial_df, regles)
            contraintes["apres"] = valider(cleaned_df, regles)
    if saisies:
        _proposer_enregistrement(regles, reports_dir, input_file, horodatage)

    # 8. Rapport de nettoyage Markdown
    try:
        logger = logging.getLogger(__name__)
        chemin_rapport = generate_enhanced_report(
            profiler, logger, reports_dir, input_file, stats,
            generate=generer_rapport, horodatage=horodatage,
            contraintes=contraintes or None,
        )
        if chemin_rapport:
            print(f"📁 Rapport de nettoyage disponible : {chemin_rapport}")
    except Exception as e:
        print(f"⚠️ Erreur lors de la génération du rapport final : {e}")

    # 9. Profilage post-nettoyage (validation)
    # Le rapport est nommé d'après la source suivie de « _nettoye », et non
    # d'après le fichier de sortie : celui-ci porte déjà l'horodatage, qui
    # apparaîtrait sinon deux fois dans le nom.
    post_profiler = ExploratoryProfiler(cleaned_df, output_file)
    post_profiler.run_profiling_workflow(
        input_file.with_name(f"{input_file.stem}_nettoye{input_file.suffix}"),
        reports_dir, report_format=format_rapport, horodatage=horodatage,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
