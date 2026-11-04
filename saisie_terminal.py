"""Création de règles de validation par questions, dans un terminal.

Ce module est facultatif : `main.py` ne l'utilise que si l'utilisateur passe
`--creer-regles`. Il ne décide de rien : ce qu'il faut demander (les champs de
chaque type de règle) et la manière de construire la règle viennent de
`src/saisie_regles.py`, que l'interface web utilise aussi. Il se borne à poser
les questions en terminal.

La fonction de saisie est un paramètre (`input` en usage normal), ce qui permet
de tester le dialogue avec des réponses simulées. Une fin de flux ou une
interruption conserve les règles déjà définies.
"""

from __future__ import annotations

from src.saisie_regles import (
    champs_du_type,
    colonnes_attendues,
    construire_regle,
    types_disponibles,
)
from src.validator import (colonnes_compatibles, colonnes_comparables, decrire_regle,
                           formater_bilan, valider)

_OUI = ("o", "oui", "y", "yes")
_INVITE = ("\n⏳ Voyez-vous des anomalies que le nettoyage ne pouvait pas deviner ? "
           "Ajouter une contrainte ? [o/N] : ")


def _choisir(invite: str, options: list[str], saisir, *, vide: str = "annuler") -> int | None:
    """Fait choisir une option dans une liste numérotée.

    Args:
        invite: Question posée.
        options: Libellés proposés, numérotés à partir de 1.
        saisir: Fonction de saisie (`input` en usage normal).
        vide: Ce que signifie une réponse vide (« annuler », « aucun »).

    Returns:
        L'indice (à partir de 0) de l'option choisie, ou None si l'utilisateur
        valide une réponse vide.
    """
    print(invite)
    for rang, option in enumerate(options, start=1):
        print(f"   {rang}. {option}")
    while True:
        reponse = saisir(f"⏳ Votre choix (entrée pour {vide}) : ").strip()
        if not reponse:
            return None
        if reponse.isdigit() and 1 <= int(reponse) <= len(options):
            return int(reponse) - 1
        print(f"   Entrez un nombre entre 1 et {len(options)}.")


def _demander_champ(champ: dict, saisir) -> str | None:
    """Pose la question d'un champ de règle.

    Args:
        champ: Description du champ (voir `src/saisie_regles.py`).
        saisir: Fonction de saisie (`input` en usage normal).

    Returns:
        Le texte saisi (vide pour « aucun »), ou None si le champ est
        obligatoire et que l'utilisateur a renoncé.
    """
    if champ["genre"] == "choix":
        rang = _choisir(f"\n{champ['libelle']} ?  ({champ['aide']})",
                        [libelle for _, libelle in champ["choix"]], saisir,
                        vide="annuler" if champ["obligatoire"] else "aucun")
        if rang is None:
            return None if champ["obligatoire"] else ""
        return champ["choix"][rang][0]
    if champ["aide"]:
        print(f"   {champ['aide']}")
    return saisir(f"⏳ {champ['libelle']} (entrée pour aucun) : " if not champ["obligatoire"]
                  else f"⏳ {champ['libelle']} : ")


def _choisir_colonnes(type_regle: str, colonnes: list[str], saisir,
                      df=None) -> list[str] | None:
    """Fait choisir la ou les colonnes que porte la règle.

    Args:
        type_regle: Type de règle en cours de définition.
        colonnes: Colonnes du fichier.
        saisir: Fonction de saisie (`input` en usage normal).
        df: Données, facultatives. Si elles sont fournies, seules les colonnes
            qui conviennent au type de règle sont proposées.

    Returns:
        Les colonnes choisies, ou None si l'utilisateur a annulé ou si aucune
        colonne ne convient.
    """
    mini, maxi = colonnes_attendues(type_regle)
    proposees = colonnes
    if df is not None:
        proposees = colonnes_compatibles(df, type_regle)
        if not proposees:
            print("⚠️ Aucune colonne ne convient à cette contrainte "
                  "(il faut des nombres ou des dates).")
            return None
    rang = _choisir("\nSur quelle colonne ?", proposees, saisir)
    if rang is None:
        return None
    choisies = [proposees[rang]]
    if mini == 2:
        autres = ([c for c in colonnes if c != choisies[0]] if df is None
                  else colonnes_comparables(df, choisies[0]))
        rang = _choisir(f"\n« {choisies[0]} » doit être comparée à quelle colonne ?", autres, saisir)
        if rang is None:
            return None
        choisies.append(autres[rang])
    elif maxi is None:
        while len(choisies) < len(colonnes):
            reste = [c for c in colonnes if c not in choisies]
            if saisir("⏳ Ajouter une autre colonne à la combinaison ? [o/N] : "
                      ).strip().lower() not in _OUI:
                break
            rang = _choisir("\nQuelle colonne ?", reste, saisir)
            if rang is None:
                break
            choisies.append(reste[rang])
    return choisies


def saisir_une_regle(colonnes: list[str], saisir=None, df=None) -> dict | None:
    """Pose les questions nécessaires pour définir une règle.

    Args:
        colonnes: Colonnes du fichier, proposées au choix.
        saisir: Fonction de saisie ; `input` si omise, résolu à l'appel.
        df: Données, facultatives : si elles sont fournies, seules les colonnes
            qui conviennent au type de règle sont proposées.

    Returns:
        La règle définie, ou None si l'utilisateur a annulé ou si la règle
        obtenue n'est pas valide (les motifs sont alors affichés).
    """
    saisir = saisir or input
    types = types_disponibles()
    rang = _choisir("\nQuelle contrainte ?", [libelle for _, libelle in types], saisir)
    if rang is None:
        return None
    type_regle = types[rang][0]
    cibles = _choisir_colonnes(type_regle, colonnes, saisir, df)
    if cibles is None:
        return None

    saisies = {}
    for champ in champs_du_type(type_regle):
        autre = champ.get("si_vide")
        if autre and str(saisies.get(autre, "")).strip():
            continue
        texte = _demander_champ(champ, saisir)
        if texte is None:
            return None
        saisies[champ["nom"]] = texte

    regle, problemes = construire_regle(type_regle, cibles, saisies, df=df)
    if regle is None:
        print("⚠️ Contrainte abandonnée :")
        for probleme in problemes:
            print(f"   - {probleme}")
    return regle


def retour_immediat(df, titre: str):
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


def demander_regles(colonnes: list[str], saisir=None, *, invite: str | None = None,
                    apres_ajout=None, df=None) -> list[dict]:
    """Fait définir des contraintes par questions, une à une.

    Une réponse vide, ou l'absence de terminal, termine sans rien ajouter. Les
    contraintes déjà définies sont conservées.

    Args:
        colonnes: Colonnes du fichier nettoyé.
        saisir: Fonction de saisie, injectable pour les tests ; `input` si
            omise, résolu à l'appel.
        invite: Première question, pour la reformuler.
        apres_ajout: Fonction appelée avec chaque règle ajoutée, pour montrer
            tout de suite ce qu'elle donne sur les données.
        df: Données, facultatives : si elles sont fournies, seules les colonnes
            qui conviennent à chaque type de règle sont proposées.

    Returns:
        Les règles définies, éventuellement vides.
    """
    saisir = saisir or input
    regles = []
    premiere = invite or _INVITE
    try:
        while True:
            question = premiere if not regles else "⏳ Ajouter une autre contrainte ? [o/N] : "
            if saisir(question).strip().lower() not in _OUI:
                break
            regle = saisir_une_regle(colonnes, saisir, df)
            if regle is not None:
                regles.append(regle)
                print(f"   ✅ Contrainte ajoutée : {decrire_regle(regle)}")
                if apres_ajout is not None:
                    apres_ajout(regle)
    except (EOFError, KeyboardInterrupt):
        print("\n(saisie interrompue : les contraintes déjà définies sont conservées)")
    return regles
