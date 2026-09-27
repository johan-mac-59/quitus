"""Tests du découplage entre la logique de nettoyage et l'interface.

Ces tests verrouillent le contrat du modèle mixte : les modules de `src/` ne
posent plus de questions, ils reçoivent des réponses. La ligne de commande
interroge le terminal, l'interface web interroge des widgets, et tous deux
transmettent le résultat par les mêmes paramètres.
"""

import numpy as np
import pandas as pd

from src.cleaner_engine import (
    ask_user_missing_values_correction,
    ask_user_outlier_correction,
    get_user_decisions,
    summarize_missing_values,
    summarize_outliers,
)


class TestSummarizeOutliers:
    """summarize_outliers doit être pure : aucune entrée/sortie, aucun état."""

    def test_profil_vide_et_donnees_propres(self):
        """Sans outlier nulle part, le résumé est négatif."""
        df = pd.DataFrame({"a": [1, 2, 3, 4]})
        res = summarize_outliers(df, {}, {})
        assert res["has_outliers"] is False
        assert res["columns"] == {}
        assert any("Aucune valeur aberrante" in ligne for ligne in res["lines"])

    def test_lit_le_profil_complet(self):
        """Le résumé exploite la clé outliers du profil, au format dictionnaire."""
        df = pd.DataFrame({"prix": [10, 11, 12, 9999]})
        profil = {"outliers": {"prix": {"count": 1, "lower_bound": 5.0,
                                        "upper_bound": 20.0, "outlier_values": [9999]}}}
        res = summarize_outliers(df, {}, profil)
        assert res["has_outliers"] is True
        assert res["columns"]["prix"] == 1

    def test_accepte_l_ancien_format_scalaire(self):
        """Un profil au format colonne vers nombre reste compris."""
        df = pd.DataFrame({"prix": [1, 2, 3]})
        res = summarize_outliers(df, {}, {"outliers": {"prix": 4}})
        assert res["columns"]["prix"] == 4

    def test_ignore_la_sentinelle_ignored(self):
        """La sentinelle ignored n'est pas prise pour un nom de colonne."""
        df = pd.DataFrame({"a": [1, 2, 3]})
        res = summarize_outliers(df, {"outliers_corrected": {"ignored": True}}, {})
        assert "ignored" not in res["columns"]

    def test_detecte_les_outliers_des_colonnes_textuelles_numerisables(self):
        """Une colonne de montants en texte doit être vue malgré son type.

        Le profilage précède la correction des types : sans ce complément,
        l'utilisateur ne se verrait jamais proposer d'écrêter la colonne qui en
        a le plus besoin.
        """
        df = pd.DataFrame({
            "montant": ["100,50 €", "102,00 €", "98,75 €", "101,25 €",
                        "99,00 €", "50000,00 €"],
        })
        res = summarize_outliers(df, {}, {})
        assert res["has_outliers"] is True
        assert "montant" in res["columns"]
        assert any("après correction des types" in ligne for ligne in res["lines"])

    def test_ne_recompte_pas_une_colonne_deja_vue(self):
        """Une colonne déjà signalée par le profil n'est pas comptée deux fois."""
        df = pd.DataFrame({"m": ["1", "2", "3", "4", "500"]})
        res = summarize_outliers(df, {}, {"outliers": {"m": 1}})
        assert res["columns"]["m"] == 1

    def test_ignore_les_identifiants_alphanumeriques(self):
        """Un identifiant mixte ne doit pas être pris pour du numérique."""
        df = pd.DataFrame({"id": ["R123", "R456", "R789", "R001", "R999"]})
        res = summarize_outliers(df, {}, {})
        assert res["columns"] == {}

    def test_tolere_un_dataframe_vide(self):
        """Un DataFrame vide ne fait pas échouer le résumé."""
        assert summarize_outliers(pd.DataFrame(), {}, {})["has_outliers"] is False


class TestSummarizeMissingValues:
    def test_aucune_valeur_manquante(self):
        """Un DataFrame complet donne un total nul."""
        res = summarize_missing_values(pd.DataFrame({"a": [1, 2, 3]}))
        assert res["total"] == 0
        assert res["by_column"] == {}

    def test_compte_et_pourcentage_par_colonne(self):
        """Chaque colonne trouée est décrite par un nombre et un pourcentage."""
        df = pd.DataFrame({"a": [1, np.nan, 3, np.nan], "b": [1, 2, 3, 4]})
        res = summarize_missing_values(df)
        assert res["total"] == 2
        assert res["by_column"]["a"] == (2, 50.0)
        assert "b" not in res["by_column"]

    def test_dataframe_vide(self):
        """Un DataFrame vide ne fait pas échouer le résumé."""
        assert summarize_missing_values(pd.DataFrame())["total"] == 0


class TestDecisionsParametrables:
    """Une réponse transmise doit court-circuiter toute invite terminal."""

    def test_outliers_reponse_imposee_vraie(self):
        """Une réponse vraie est honorée sans rien demander."""
        df = pd.DataFrame({"a": [1, 2, 3, 100]})
        assert ask_user_outlier_correction(df, {}, {}, answer=True) is True

    def test_outliers_reponse_imposee_fausse(self):
        """Une réponse fausse est honorée sans rien demander."""
        df = pd.DataFrame({"a": [1, 2, 3, 100]})
        assert ask_user_outlier_correction(df, {}, {}, answer=False) is False

    def test_outliers_consigne_prime_sur_le_prediagnostic(self):
        """Une consigne explicite l'emporte même si le profil ne voit rien.

        Le profilage précède la correction des types : refuser ici annulerait
        silencieusement une demande explicite de l'utilisateur.
        """
        df = pd.DataFrame({"a": [1, 1, 1, 1]})
        assert ask_user_outlier_correction(df, {}, {}, answer=True) is True

    def test_missing_reponse_imposee(self):
        """La réponse est honorée pour les valeurs manquantes aussi."""
        df = pd.DataFrame({"a": [1, np.nan, 3]})
        assert ask_user_missing_values_correction(df, {}, {}, answer=True) is True
        assert ask_user_missing_values_correction(df, {}, {}, answer=False) is False

    def test_get_user_decisions_avec_les_deux_reponses(self):
        """Les deux décisions transmises sont restituées telles quelles."""
        df = pd.DataFrame({"a": [1, np.nan, 3, 100]})
        assert get_user_decisions(df, {}, correct_outliers=True,
                                 fill_missing=False) == (True, False)
        assert get_user_decisions(df, {}, correct_outliers=False,
                                 fill_missing=True) == (False, True)

    def test_get_user_decisions_non_interactif(self):
        """Sans consigne et sans interactivité, tout est refusé."""
        df = pd.DataFrame({"a": [1, np.nan, 3, 100]})
        assert get_user_decisions(df, {}, interactive=False) == (False, False)

    def test_get_user_decisions_profil_sans_missing_values(self):
        """Un profil dépourvu de la clé missing_values ne lève pas.

        L'ancien code l'indexait sans garde, ce qui provoquait un KeyError.
        """
        df = pd.DataFrame({"a": [1, np.nan, 3]})
        profil = {"outliers": {}}
        assert get_user_decisions(df, profil, interactive=False) == (False, False)

    def test_get_user_decisions_profil_none(self):
        """Un profil absent est toléré."""
        df = pd.DataFrame({"a": [1, 2, 3]})
        assert get_user_decisions(df, None, interactive=False) == (False, False)

    def test_transmet_le_profil_complet_et_non_son_sous_dictionnaire(self):
        """Le profil complet doit parvenir au résumé.

        C'est le bug historique : passer `profiler_results['outliers']` faisait
        conclure « aucun outlier » et désactivait silencieusement l'écrêtage dès
        qu'un profilage existait.
        """
        df = pd.DataFrame({"prix": [10, 11, 12, 9999]})
        profil = {"outliers": {"prix": {"count": 1}},
                  "missing_values": {"count": {}, "percent": {}}}
        correct, _ = get_user_decisions(df, profil, correct_outliers=True,
                                       fill_missing=False)
        assert correct is True
        assert summarize_outliers(df, {}, profil)["has_outliers"] is True


class TestGardeFinDeFlux:
    """Sans terminal, les invites doivent retomber sur leur défaut.

    C'est ce qui rend les modules importables depuis un serveur web, une
    intégration continue, ou simplement avec une sortie redirigée.
    """

    @staticmethod
    def _leve(exception):
        """Fabrique un remplaçant de input() qui lève l'exception donnée.

        Args:
            exception: La classe d'exception à lever.

        Returns:
            Une fonction utilisable en remplacement de `input`.
        """
        def _faux_input(*args, **kwargs):
            raise exception

        return _faux_input

    def test_outliers_sur_stdin_ferme(self, monkeypatch):
        """Une fin de flux donne la valeur par défaut, sans lever."""
        monkeypatch.setattr("builtins.input", self._leve(EOFError))
        df = pd.DataFrame({"prix": [10, 11, 12, 9999]})
        profil = {"outliers": {"prix": {"count": 1}}}
        assert ask_user_outlier_correction(df, {}, profil, default=False) is False
        assert ask_user_outlier_correction(df, {}, profil, default=True) is True

    def test_missing_sur_stdin_ferme(self, monkeypatch):
        """Idem pour les valeurs manquantes."""
        monkeypatch.setattr("builtins.input", self._leve(EOFError))
        df = pd.DataFrame({"a": [1, np.nan, 3]})
        assert ask_user_missing_values_correction(df, {}, {}, default=False) is False
        assert ask_user_missing_values_correction(df, {}, {}, default=True) is True

    def test_interruption_clavier(self, monkeypatch):
        """Un Ctrl-C est traité comme une absence de réponse."""
        monkeypatch.setattr("builtins.input", self._leve(KeyboardInterrupt))
        df = pd.DataFrame({"a": [1, np.nan, 3]})
        assert ask_user_missing_values_correction(df, {}, {}, default=True) is True
