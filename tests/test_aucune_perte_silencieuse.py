"""Verrouille la garantie : le nettoyage ne fait disparaître aucune valeur en silence.

Une conversion de type peut légitimement vider une valeur illisible — une colonne
numérique ne peut pas contenir « abc ». Mais cette perte doit toujours être
recensée dans `stats['values_unparsed']`, avec des exemples, pour que
l'utilisateur voie exactement ce qui a été vidé.

Deux défauts ont motivé ce fichier :

* sur le jeu de référence, 1 849 montants au format « 1 052,23 € » étaient
  vidés sans un mot : le séparateur de milliers (une espace) n'était jamais
  retiré, alors que le README citait précisément cet exemple ;
* sur un fichier de prix de carburants, une date « 0216-03-02 » (l'an 216,
  coquille pour 2016) était vidée par le garde-fou de plausibilité, sans
  qu'aucune interface ne le signale — d'où une valeur manquante « de plus »
  inexpliquée après nettoyage.

La propriété centrale est testée de façon générale : toute valeur présente
devenue manquante doit figurer dans le recensement.
"""

import numpy as np
import pandas as pd
import pytest

from src.cleaner_engine import clean_types, run_all_cleaning_steps
from src.cleaner_logger import CleanLogger
from src.cleaner_reporter import CleanerReporter


def _pertes_reelles(avant: pd.DataFrame, apres: pd.DataFrame) -> dict:
    """Mesure, colonne par colonne, les valeurs présentes devenues manquantes.

    Args:
        avant: DataFrame d'origine.
        apres: DataFrame nettoyé.

    Returns:
        Un dictionnaire nom de colonne -> nombre de valeurs perdues.
    """
    communs = apres.index.intersection(avant.index)
    pertes = {}
    for col in apres.columns:
        if col not in avant.columns:
            continue
        texte = avant.loc[communs, col].astype("string").str.strip().str.lower()
        significatives = avant.loc[communs, col].notna() & ~texte.isin(
            {"", "nan", "none", "null", "na", "n/a", "-", "--"})
        n = int((significatives & apres.loc[communs, col].isna()).sum())
        if n:
            pertes[col] = n
    return pertes


class TestSeparateursDeMilliers:
    """Les montants à la française doivent être lus, pas vidés."""

    @pytest.mark.parametrize("espace", [" ", " ", " "],
                             ids=["espace", "insecable", "fine_insecable"])
    def test_espace_comme_separateur_de_milliers(self, espace):
        """« 1 052,23 € » devient 1052.23, quelle que soit l'espace employée.

        Les exports Excel français utilisent volontiers l'espace insécable ou
        l'espace fine insécable plutôt que l'espace ordinaire.
        """
        valeurs = [f"1{espace}052,23 €", "98,50 €", f"2{espace}076,50 €",
                   "15,00 €", f"12{espace}345,67 €"]
        propre, _ = clean_types(pd.DataFrame({"m": valeurs}))
        assert pd.api.types.is_numeric_dtype(propre["m"])
        assert propre["m"].tolist() == pytest.approx([1052.23, 98.50, 2076.50, 15.00, 12345.67])

    def test_minorite_de_montants_avec_milliers(self):
        """Le cas du jeu de référence : peu de montants dépassent 1 000.

        Assez pour franchir le seuil de conversion, et donc assez pour que les
        autres soient vidés sans bruit si l'espace n'est pas retirée.
        """
        valeurs = [f"{v:.2f} €".replace(".", ",") for v in np.linspace(50, 900, 40)]
        valeurs += ["1 052,23 €", "2 076,50 €"]
        propre, _ = clean_types(pd.DataFrame({"m": valeurs}))
        assert propre["m"].notna().all()
        assert propre["m"].iloc[-1] == pytest.approx(2076.50)

    def test_livre_sterling(self):
        """« £ » est accepté par la détection : il doit aussi être retiré.

        Un symbole accepté mais jamais retiré produit le pire cas — la colonne
        est jugée numérique, puis chaque valeur échoue et se retrouve vidée.
        """
        propre, _ = clean_types(pd.DataFrame({"p": ["£12.50", "£3.99", "£100.00", "£7.25"]}))
        assert pd.api.types.is_numeric_dtype(propre["p"])
        assert propre["p"].tolist() == pytest.approx([12.50, 3.99, 100.00, 7.25])


class TestRecensementDesPertes:
    """Toute valeur vidée par une conversion doit être recensée."""

    def test_valeur_illisible_recensee(self):
        """Une valeur non numérique dans une colonne numérique est signalée."""
        # La détection n'examine que les 100 premières valeurs : une valeur
        # illisible placée au-delà passe le filtre, puis échoue à la conversion.
        valeurs = [str(i) for i in range(1, 120)] + ["douze"]
        pertes = {}
        propre, conversions = clean_types(pd.DataFrame({"n": valeurs}), pertes=pertes)
        assert "n" in conversions
        assert pertes["n"]["count"] == 1
        assert pertes["n"]["examples"] == ["douze"]

    def test_annee_implausible_recensee(self):
        """Le cas de prix.csv : une date en l'an 216 est vidée ET signalée."""
        valeurs = ["2026-09-07T00:44:00", "2017-09-16T09:50:23",
                   "2024-07-23T15:17:23", "0216-03-02T00:00:00",
                   "2018-04-21T15:38:51", "2022-11-24T18:57:55"]
        pertes = {}
        propre, conversions = clean_types(pd.DataFrame({"d": valeurs}), pertes=pertes)
        assert pd.api.types.is_datetime64_any_dtype(propre["d"])
        assert pertes["d"] == {"count": 1, "examples": ["0216-03-02T00:00:00"]}

    def test_marqueurs_de_vide_ne_sont_pas_des_pertes(self):
        """« NULL », « N/A » ou « - » n'étaient pas des données : pas de perte."""
        valeurs = [str(i) for i in range(1, 120)] + ["NULL", "N/A", "-", ""]
        pertes = {}
        clean_types(pd.DataFrame({"n": valeurs}), pertes=pertes)
        assert pertes == {}

    def test_parametre_facultatif(self):
        """Sans dictionnaire fourni, clean_types garde sa signature d'origine."""
        propre, conversions = clean_types(pd.DataFrame({"n": ["1", "2", "3"]}))
        assert "n" in conversions


class TestProprieteGenerale:
    """Toute perte réelle doit figurer dans le recensement du pipeline."""

    @pytest.fixture
    def df_piege(self):
        """DataFrame réunissant toutes les sources de perte connues."""
        n = 150
        montants = [f"{50 + i * 3:.2f} €".replace(".", ",") for i in range(n)]
        montants[140] = "1 234,56 €"          # séparateur de milliers
        montants[145] = "illisible"           # vraie valeur perdue
        dates = ["13/09/2024"] * n
        dates[141] = "2023-09-15"             # autre convention : doit être lue
        dates[146] = "0216-03-02"             # année implausible : perdue
        return pd.DataFrame({"montant": montants, "date": dates,
                             "ville": ["Lille"] * n})

    def test_toute_perte_est_recensee(self, df_piege):
        """Les pertes mesurées et les pertes déclarées coïncident exactement."""
        propre, stats = run_all_cleaning_steps(
            df_piege.copy(), correct_outliers=False, fill_missing=False)

        reelles = _pertes_reelles(df_piege, propre)
        declarees = {c: v["count"] for c, v in stats["values_unparsed"].items()}
        assert reelles == declarees

    def test_seules_les_vraies_pertes_subsistent(self, df_piege):
        """Le séparateur de milliers et l'autre convention de date sont lus."""
        propre, stats = run_all_cleaning_steps(
            df_piege.copy(), correct_outliers=False, fill_missing=False)

        assert propre.loc[140, "montant"] == pytest.approx(1234.56)
        assert pd.notna(propre.loc[141, "date"])
        assert stats["values_unparsed"]["montant"]["examples"] == ["illisible"]
        assert stats["values_unparsed"]["date"]["examples"] == ["0216-03-02"]

    def test_cle_toujours_presente(self):
        """La clé existe même sans perte, pour simplifier les consommateurs."""
        _, stats = run_all_cleaning_steps(pd.DataFrame({"a": [1, 2, 3]}))
        assert stats["values_unparsed"] == {}


class TestRestitution:
    """Les pertes recensées doivent atteindre l'utilisateur."""

    @pytest.fixture
    def stats(self):
        """Statistiques comportant une perte."""
        return {
            "types_converted": {"prix_maj": ["object -> datetime"]},
            "values_unparsed": {"prix_maj": {"count": 1,
                                             "examples": ["0216-03-02T00:00:00"]}},
        }

    def test_rapport_console(self, stats):
        """Le bilan console mentionne les valeurs vidées."""
        journal = CleanLogger(pd.DataFrame({"a": [1]}), stats)
        journal.update_final_state(pd.DataFrame({"a": [1]}))
        assert "illisibles" in journal.get_summary()

    def test_rapport_markdown(self, stats):
        """Le rapport de nettoyage détaille la perte, exemple compris."""
        from types import SimpleNamespace
        import logging

        rapport = CleanerReporter(SimpleNamespace(profile_results={}),
                                  logging.getLogger("t")).render(stats)
        assert "0216-03-02T00:00:00" in rapport
        assert "Valeurs illisibles" in rapport

    def test_rapport_en_tetes_dans_le_bon_ordre(self, stats):
        """Le tableau des conversions nomme d'abord la colonne, puis la conversion.

        Les en-têtes étaient autrefois inversés (« Type converti | Colonnes »).
        """
        from types import SimpleNamespace
        import logging

        rapport = CleanerReporter(SimpleNamespace(profile_results={}),
                                  logging.getLogger("t")).render(stats)
        assert "| Colonne | Conversion |" in rapport
        assert "| prix_maj | object -> datetime |" in rapport
