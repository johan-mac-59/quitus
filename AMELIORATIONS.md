# 🚀 Améliorations du projet

Les améliorations à faire sont classées par ordre d'importance ; les améliorations
livrées suivent, dans l'ordre chronologique. Le détail de chaque livraison se
trouve dans [`DEROULEMENT_PROJET.md`](DEROULEMENT_PROJET.md), à l'étape indiquée.

## 🎯 À faire — par ordre d'importance
1. **Module `validator`** : création d'un moteur de vérification des contraintes (types, formats, plages de valeurs). Il accueillerait aussi des règles métier d'alerte, par exemple signaler une colonne d'âge dont des valeurs sont négatives, idée d'une méthode `detect_quality_issues` prévue à l'Étape 9 et jamais écrite.
2. **Détection assistée par IA** : introduction d'un LLM pour aider à détecter les anomalies orthographiques et les types de colonnes complexes.
3. **Seuils d'alerte propres à chaque profil** : adapter les seuils de criticité du profil avant nettoyage, distincts de ceux du profil de contrôle (perspective de l'Étape 22).
4. **Stabilité statistique après nettoyage** : comparer les distributions avant et après pour vérifier que le nettoyage n'a pas déformé les données (perspective de l'Étape 22). Les corrélations, elles, sont livrées (Étape 23).
5. **Interface commune aux deux profileurs** : s'assurer que `PreCleaningProfiler` et `ExploratoryProfiler` partagent le même contrat, pour les manipuler de la même façon dans l'orchestrateur (perspective de l'Étape 22).
6. **Méthode alternative sur les très petits échantillons** : l'écrêtage par IQR est peu fiable avec trois ou quatre valeurs, où les quartiles sont eux-mêmes décalés par l'extrême (piste de l'Étape 8 : détection par écart-type).
7. **Autres sources et destinations** : lire depuis une base SQL, exporter vers une base ou valider un schéma (ouvertures citées aux Étapes 5 et 21).

## ✅ Livré
- ~~**mode multi-passes**~~ : les premières étapes de nettoyage sont répétées jusqu'à stabilisation, le moteur s'arrêtant de lui-même dès que plus rien ne change. *Étapes 7 et 30.*
- ~~**validation après nettoyage**~~ : un profil de contrôle et un verdict colonne par colonne vérifient qu'aucune colonne mal typée ne subsiste. *Étapes 22, 29 et 30.*
- ~~**un vrai rapport de nettoyage**~~ : chaque exécution produit un rapport qui indique la source et l'horodatage, compare l'avant et l'après, et détaille colonne par colonne chaque opération effectuée. Le journal de nettoyage est couvert par des tests. *Étapes 11 et 12.*
- ~~**enrichir le profilage**~~ : le rapport indique le fichier source, distingue colonnes numériques, catégorielles et identifiants par leur cardinalité, analyse les lignes vides, et illustre le tout de graphiques (distributions, boîtes à moustaches, heatmap, corrélations) dans un fichier HTML autonome, images intégrées en base64. *Étapes 14, 15 et 23.*
- ~~**rendre optionnel l'écrêtage des valeurs aberrantes**~~ : l'utilisateur décide d'écrêter ou non, au vu du profilage. *Étape 16 ; la question, qui n'était en fait jamais posée, l'est vraiment depuis l'étape 26.*
- ~~**uniformiser la casse, et seulement là où il le faut**~~ : les variations de casse sont corrigées, uniquement sur les colonnes que le profilage signale comme problématiques. *Étapes 17 et 20.*
- ~~**Support JSON**~~ : les fichiers `.json`, y compris imbriqués, et JSON Lines sont chargés, et un fichier sans extension est reconnu par sa structure. *Étape 19.*
- ~~**un profilage après le nettoyage**~~ : deux classes héritées du profileur distinguent le diagnostic avant nettoyage et le rapport de contrôle après, pour une comparaison avant/après. *Étape 22.*
- ~~**rendre flexible le loader**~~ : l'utilisateur choisit son fichier, en ligne de commande (`--input`) comme dans l'interface web (dépôt). *Étapes 26 et 27.*
- ~~**Séparer profiling et cleaning**~~ : l'interface web permet d'analyser, puis de décider, puis de nettoyer, en trois gestes distincts. *Étape 27.*
- ~~**améliorer la détection des dates**~~ : dix formats explicites sont appliqués **cumulativement**, ce qui permet de traiter une colonne mêlant plusieurs conventions. La détection était par ailleurs du code mort, jamais atteint. *Réparée à l'étape 24, rendue cumulative à l'étape 29.*
- ~~**détecter plus de nombres**~~ : les notes fractionnaires (`17/20`, `5/5`) et les pourcentages (`1,5 %`, `78.9875%`) sont désormais convertis. *Étape 29.*
- ~~**profilage conscient des types**~~ : la question était mal posée. Le profil avant nettoyage doit montrer les types bruts ; c'est le profil après nettoyage qui ne doit plus comporter de colonne mal typée, invariant désormais tenu et testé. *Étape 29.*
- ~~**bouton de soutien**~~ : un bouton « Soutenir le projet » renvoie vers la page [Buy Me a Coffee](https://buymeacoffee.com/johan_mac) — pas de compte à créer pour le donateur, dons ponctuels. Le paiement se fait entièrement chez le prestataire. *Étape 33.*
- ~~**déploiement public**~~ : l'application tourne sur Streamlit Community Cloud, à l'adresse [quitus.streamlit.app](https://quitus.streamlit.app/). *Étape 36.*
- ~~**numéros de téléphone tronqués**~~ : un code écrit avec un zéro initial (téléphone, code postal, matricule) reste du texte, au chargement de chaque format comme au nettoyage. *Étape 39.*
- ~~**rapport HTML lisible en mode sombre**~~ : le rapport fixe son propre fond clair et sa couleur de texte ; il reste lisible dans l'application quel que soit le thème choisi. *Étape 40.*
- ~~**traitement colonne par colonne**~~ : dans l'interface web, l'utilisateur choisit les colonnes à écrêter et celles à combler, au lieu de deux décisions globales. *Étape 41.*
- ~~**seuil des valeurs aberrantes paramétrable**~~ : chaque colonne écrêtée reçoit son seuil IQR, dont l'interface web montre l'effet en direct ; la ligne de commande accepte un seuil commun (`--seuil-iqr`). *Étape 42.*
- ~~**normalisation des notes sur une échelle commune**~~ : une colonne mêlant plusieurs échelles de notation est ramenée à son échelle dominante, et chaque note ramenée est signalée. *Étape 43.*
- ~~**support du format Parquet**~~ : les fichiers `.parquet` sont chargés, y compris sans extension ; les cellules structurées d'un JSON ou d'un Parquet sont écrites en texte JSON, ce qui répare au passage le profilage des JSON imbriqués. *Étape 44.*
- ~~**documentation API**~~ : [`docs/API.md`](docs/API.md) décrit chaque fonction publique ; il est généré depuis le code, et un test interdit qu'il se périme. *Étape 45.*
