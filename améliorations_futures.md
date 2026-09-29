# 🚀 Roadmap du Projet

## ✅ Livré en V1.0
- ~~**rendre flexible le loader**~~ : l'utilisateur choisit son fichier, en ligne de commande (`--input`) comme dans l'interface web (dépôt).
- ~~**Séparer profiling et cleaning**~~ : l'interface web permet d'analyser, puis de décider, puis de nettoyer, en trois gestes distincts.
- ~~**améliorer la détection des dates**~~ : dix formats explicites sont appliqués **cumulativement**, ce qui permet de traiter une colonne mêlant plusieurs conventions. La détection était par ailleurs du code mort, jamais atteint (voir Étape 30).
- ~~**détecter plus de nombres**~~ : les notes fractionnaires (`17/20`, `5/5`) et les pourcentages (`1,5 %`, `78.9875%`) sont désormais convertis (Étape 35).

## 🛠️ Développement Technique (En cours)
- **Module `validator`** : Création d'un moteur de vérification des contraintes (types, formats, plages de valeurs).
- **Documentation API** : Rédaction d'un document technique détaillé décrivant l'interface et les paramètres de chaque fonction.
- **Traitement colonne par colonne** : dans l'interface web, choisir quelles colonnes écrêter ou combler, au lieu de deux décisions globales.

## 📊 Améliorations Fonctionnelles
- **normalisation des notes sur une échelle commune** : `17/20` est converti en `17`, le numérateur, seul choix cohérent quand une colonne mêle `5` et `5/5`. Une colonne mêlant `17/20` et `4/5` resterait toutefois incohérente : une détection de l'échelle dominante serait utile.
- **déploiement public** : mise en ligne sur Streamlit Community Cloud ou Hugging Face Spaces
- **bouton de soutien** : lien externe vers un prestataire de don (variable `LIEN_DON` dans `streamlit_app.py`)
- **détection boostée à l'IA** : introduction d'un LLM pour aider à la détection d'anomalie orthographique, détection des types de colonnes complexes...  




