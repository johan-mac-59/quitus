# 🚀 Roadmap du Projet

Chaque élément est rangé selon son état réel. Le détail de ce qui a été livré se
trouve dans [`DEROULEMENT_PROJET.md`](DEROULEMENT_PROJET.md), à l'étape indiquée.

## ✅ Livré
- ~~**rendre flexible le loader**~~ : l'utilisateur choisit son fichier, en ligne de commande (`--input`) comme dans l'interface web (dépôt). *Étapes 32 et 33.*
- ~~**Séparer profiling et cleaning**~~ : l'interface web permet d'analyser, puis de décider, puis de nettoyer, en trois gestes distincts. *Étape 33.*
- ~~**améliorer la détection des dates**~~ : dix formats explicites sont appliqués **cumulativement**, ce qui permet de traiter une colonne mêlant plusieurs conventions. La détection était par ailleurs du code mort, jamais atteint. *Réparée à l'étape 30, rendue cumulative à l'étape 35.*
- ~~**détecter plus de nombres**~~ : les notes fractionnaires (`17/20`, `5/5`) et les pourcentages (`1,5 %`, `78.9875%`) sont désormais convertis. *Étape 35.*

## 🔧 Prêt, reste à activer
- **bouton de soutien** : le bouton et sa mention de confidentialité sont en place dans la barre latérale. Prestataire retenu : **Buy Me a Coffee** — pas de compte à créer pour le donateur, dons ponctuels, 5 % de frais. Reste à créer la page et à renseigner son adresse (variable `LIEN_DON` dans `streamlit_app.py`) pour que le bouton apparaisse.
- **déploiement public** : le dépôt est prêt — `requirements.txt`, configuration `.streamlit/config.toml`, point d'entrée nommé `streamlit_app.py` comme l'attend Streamlit Community Cloud. Reste la mise en ligne elle-même, sur Streamlit Community Cloud ou Hugging Face Spaces.

## 🛠️ À faire — technique
- **Module `validator`** : Création d'un moteur de vérification des contraintes (types, formats, plages de valeurs).
- **Documentation API** : Rédaction d'un document technique détaillé décrivant l'interface et les paramètres de chaque fonction. *À moitié fait : toutes les fonctions publiques ont une docstring, et un test l'impose. Reste à assembler le document.*

## 📊 À faire — fonctionnel
- **Traitement colonne par colonne** : dans l'interface web, choisir quelles colonnes écrêter ou combler, au lieu de deux décisions globales.
- **Seuil des valeurs aberrantes paramétrable** : l'utilisateur décide aujourd'hui d'écrêter ou non, mais le seuil IQR reste fixé à 1,5 pour toutes les colonnes. Il devrait pouvoir s'adapter au contexte métier — plus tolérant pour des montants à forte dispersion, plus strict pour des mesures stables. *Issu de la liste de l'Étape 6, jamais reprise depuis.*
- **Support du format Parquet** : CSV, Excel, JSON et JSON Lines sont pris en charge, Parquet non. *Issu de la liste de l'Étape 6, jamais reprise depuis.*
- **normalisation des notes sur une échelle commune** : `17/20` est converti en `17`, le numérateur, seul choix cohérent quand une colonne mêle `5` et `5/5`. Une colonne mêlant `17/20` et `4/5` resterait toutefois incohérente : une détection de l'échelle dominante serait utile.
- **détection boostée à l'IA** : introduction d'un LLM pour aider à la détection d'anomalie orthographique, détection des types de colonnes complexes...
