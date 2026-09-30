# 🚀 Améliorations du projet

Les améliorations à faire sont classées par ordre d'importance ; les améliorations
livrées suivent, dans l'ordre chronologique. Le détail de chaque livraison se
trouve dans [`DEROULEMENT_PROJET.md`](DEROULEMENT_PROJET.md), à l'étape indiquée.

## 🎯 À faire — par ordre d'importance
1. **Numéros de téléphone tronqués** : une colonne de numéros de téléphone est convertie en `int64`, ce qui supprime le `0` initial. C'est une perte de données silencieuse, contraire à la promesse de l'Étape 36 : ces colonnes doivent rester du texte.
2. **Rapport HTML illisible en mode sombre** : affiché dans l'application Streamlit en thème sombre, le rapport HTML devient illisible. Il doit rester lisible quel que soit le thème choisi par le visiteur.
3. **Traitement colonne par colonne** : dans l'interface web, choisir quelles colonnes écrêter ou combler, au lieu de deux décisions globales.
4. **Seuil des valeurs aberrantes paramétrable** : l'utilisateur décide aujourd'hui d'écrêter ou non, mais le seuil IQR reste fixé à 1,5 pour toutes les colonnes. Il devrait pouvoir s'adapter au contexte métier — plus tolérant pour des montants à forte dispersion, plus strict pour des mesures stables. *Issu de la liste de l'Étape 6.*
5. **Normalisation des notes sur une échelle commune** : `17/20` est converti en `17`, le numérateur, seul choix cohérent quand une colonne mêle `5` et `5/5`. Une colonne mêlant `17/20` et `4/5` resterait toutefois incohérente : une détection de l'échelle dominante serait utile.
6. **Documentation API** : rédaction d'un document technique détaillé décrivant l'interface et les paramètres de chaque fonction. *À moitié fait : toutes les fonctions publiques ont une docstring, et un test l'impose. Reste à assembler le document.*
7. **Module `validator`** : création d'un moteur de vérification des contraintes (types, formats, plages de valeurs).
8. **Support du format Parquet** : CSV, Excel, JSON et JSON Lines sont pris en charge, Parquet non. *Issu de la liste de l'Étape 6.*
9. **Détection assistée par IA** : introduction d'un LLM pour aider à détecter les anomalies orthographiques et les types de colonnes complexes.

## ✅ Livré
- ~~**un vrai rapport de nettoyage**~~ : chaque exécution produit un rapport qui indique la source et l'horodatage, compare l'avant et l'après, et détaille colonne par colonne chaque opération effectuée. Le journal de nettoyage est couvert par des tests. *Étapes 16 et 17.*
- ~~**enrichir le profilage**~~ : le rapport indique le fichier source, distingue colonnes numériques, catégorielles et identifiants par leur cardinalité, analyse les lignes vides, et illustre le tout de graphiques (distributions, boîtes à moustaches, heatmap, corrélations) dans un fichier HTML autonome, images intégrées en base64. *Étapes 20, 21 et 29.*
- ~~**rendre optionnel l'écrêtage des valeurs aberrantes**~~ : l'utilisateur décide d'écrêter ou non, au vu du profilage. *Étape 22 ; la question, qui n'était en fait jamais posée, l'est vraiment depuis l'étape 32.*
- ~~**uniformiser la casse, et seulement là où il le faut**~~ : les variations de casse sont corrigées, uniquement sur les colonnes que le profilage signale comme problématiques. *Étapes 23 et 26.*
- ~~**Support JSON**~~ : les fichiers `.json`, y compris imbriqués, et JSON Lines sont chargés, et un fichier sans extension est reconnu par sa structure. *Étape 25.*
- ~~**un profilage après le nettoyage**~~ : deux classes héritées du profileur distinguent le diagnostic avant nettoyage et le rapport de contrôle après, pour une comparaison avant/après. *Étape 28.*
- ~~**rendre flexible le loader**~~ : l'utilisateur choisit son fichier, en ligne de commande (`--input`) comme dans l'interface web (dépôt). *Étapes 32 et 33.*
- ~~**Séparer profiling et cleaning**~~ : l'interface web permet d'analyser, puis de décider, puis de nettoyer, en trois gestes distincts. *Étape 33.*
- ~~**améliorer la détection des dates**~~ : dix formats explicites sont appliqués **cumulativement**, ce qui permet de traiter une colonne mêlant plusieurs conventions. La détection était par ailleurs du code mort, jamais atteint. *Réparée à l'étape 30, rendue cumulative à l'étape 35.*
- ~~**détecter plus de nombres**~~ : les notes fractionnaires (`17/20`, `5/5`) et les pourcentages (`1,5 %`, `78.9875%`) sont désormais convertis. *Étape 35.*
- ~~**profilage conscient des types**~~ : la question était mal posée. Le profil avant nettoyage doit montrer les types bruts ; c'est le profil après nettoyage qui ne doit plus comporter de colonne mal typée, invariant désormais tenu et testé. *Étape 35.*
- ~~**bouton de soutien**~~ : un bouton « Soutenir le projet » renvoie vers la page [Buy Me a Coffee](https://buymeacoffee.com/johan_mac) — pas de compte à créer pour le donateur, dons ponctuels. Le paiement se fait entièrement chez le prestataire. *Étape 39.*
- ~~**déploiement public**~~ : l'application tourne sur Streamlit Community Cloud, à l'adresse [quitus.streamlit.app](https://quitus.streamlit.app/). *Étape 45.*
