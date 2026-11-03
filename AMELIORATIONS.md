# 🚀 Améliorations du projet

Les améliorations à faire sont classées par ordre d'importance ; les améliorations livrées suivent, dans l'ordre chronologique. Le détail de chaque livraison se trouve dans [`DEROULEMENT_PROJET.md`](DEROULEMENT_PROJET.md), à l'étape indiquée.

## 🎯 À faire — par ordre d'importance
1. **Contraintes en langage courant** : traduire des conditions énoncées en phrases (« l'âge doit être entre 0 et 120 ») en règles du validateur, que l'utilisateur confirme une à une. Grammaire française simple, ou petit modèle hébergé ; aucun LLM obligatoire, ni dans le navigateur, ni dans Streamlit. La description du formulaire, partagée par les deux façades, sert déjà de cible commune. *Voir l'étape 48.*
2. **Règles suggérées par le profil** : proposer des contraintes d'après les données (« trois valeurs négatives dans une colonne qui ressemble à un âge »), que l'utilisateur accepte ou refuse.
3. **Détection assistée des anomalies orthographiques** : regrouper les valeurs proches d'une colonne par similarité de chaînes, sans modèle ; sens des colonnes complexes par un modèle léger hébergé, en option.
4. **Corrections proposées par le validateur** : vider, écrêter ou retirer une ligne en violation, sous accord explicite (visée : version 1.3).
5. **Contraintes, suites** : télécharger les lignes en anomalie (CSV, avec la règle enfreinte), pour corriger à la source ; règles conditionnelles (« si le pays est la France, le code postal a 5 chiffres ») ; formats supplémentaires, à condition qu'ils ne portent pas sur des données très sensibles (IBAN, numéro de sécurité sociale : pas de contrôle dédié, l'utilisateur écrit lui-même son motif) ; dates relatives (« pas dans le futur ») ; évaluation plus économe sur de gros fichiers. *Voir l'étape 48.*
6. **Doublons d'identifiant** : la règle `unique` du validateur les signale quand l'utilisateur la déclare ; reste la détection automatique d'un identifiant répété sur des lignes différentes, que la suppression des doublons exacts ne retire pas. *Voir les étapes 46 et 47.*
7. **Seuils d'alerte propres à chaque profil** : seuils de criticité distincts avant et après nettoyage. *Voir l'étape 22.*
8. **Stabilité statistique après nettoyage** : comparer les distributions avant et après. *Voir l'étape 23.*
9. **Très petits échantillons** : méthode alternative à l'IQR, peu fiable avec quelques valeurs. *Voir l'étape 8.*
10. **Autres sources et destinations** : lecture depuis une base SQL, export vers une base, validation de schéma. *Voir les étapes 5 et 21.*

## ✅ Livré
- ~~**Mode multi-passes**~~ : nettoyage répété jusqu'à stabilisation. *Étapes 7 et 30.*
- ~~**Validation après nettoyage**~~ : profil de contrôle et verdict colonne par colonne. *Étapes 22, 29 et 30.*
- ~~**Rapport de nettoyage**~~ : source, horodatage, comparaison avant et après, détail des opérations par colonne. *Étapes 11 et 12.*
- ~~**Profilage enrichi**~~ : types de colonnes, cardinalité, lignes vides, graphiques dans un rapport HTML autonome. *Étapes 14, 15 et 23.*
- ~~**Écrêtage optionnel**~~ : l'utilisateur décide au vu du profilage. *Étapes 16 et 26.*
- ~~**Casse uniformisée ciblée**~~ : uniquement sur les colonnes que le profilage signale. *Étapes 17 et 20.*
- ~~**Support JSON**~~ : `.json` (y compris imbriqué) et JSON Lines, reconnus même sans extension. *Étape 19.*
- ~~**Profilage après nettoyage**~~ : un profileur pour l'avant, un pour l'après. *Étape 22.*
- ~~**Loader flexible**~~ : fichier choisi par `--input` ou par dépôt dans l'interface web. *Étapes 26 et 27.*
- ~~**Profilage et nettoyage séparés**~~ : analyser, décider, nettoyer en trois gestes. *Étape 27.*
- ~~**Détection des dates**~~ : dix formats appliqués cumulativement. *Étapes 24 et 29.*
- ~~**Notes et pourcentages**~~ : `17/20`, `5/5` et `1,5 %` convertis en nombres. *Étape 29.*
- ~~**Profilage conscient des types**~~ : le profil après nettoyage ne comporte plus de colonne mal typée. *Étape 29.*
- ~~**Bouton de soutien**~~ : lien vers la page [Buy Me a Coffee](https://buymeacoffee.com/johan_mac). *Étape 33.*
- ~~**Déploiement public**~~ : [quitus.streamlit.app](https://quitus.streamlit.app/). *Étape 36.*
- ~~**Zéros initiaux conservés**~~ : téléphones, codes postaux et matricules restent du texte. *Étape 39.*
- ~~**Rapport HTML en thème sombre**~~ : fond clair propre au rapport. *Étape 40.*
- ~~**Traitement colonne par colonne**~~ : colonnes à écrêter et à combler choisies une à une. *Étape 41.*
- ~~**Seuil IQR paramétrable**~~ : un seuil par colonne dans l'interface web, `--seuil-iqr` en ligne de commande. *Étape 42.*
- ~~**Notes sur une échelle commune**~~ : échelle dominante de la colonne, notes ramenées signalées. *Étape 43.*
- ~~**Format Parquet**~~ : lecture des `.parquet`, cellules structurées écrites en texte JSON. *Étape 44.*
- ~~**Documentation API**~~ : [`docs/API.md`](docs/API.md), générée depuis le code et verrouillée par un test. *Étape 45.*
- ~~**Corrections de l'essai local**~~ : graphiques sur le fichier nettoyé et sans identifiants, bouton « Nettoyer » confirmé et éteint après usage. *Étape 46.*
- ~~**Validateur de contraintes**~~ : règles saisies par l'utilisateur (plage, longueur, format, valeurs autorisées, valeur obligatoire ou unique, comparaison entre colonnes), signalées sans correction, dans le rapport, l'interface web et le terminal. *Étapes 47 et 48.*
