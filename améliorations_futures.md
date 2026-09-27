# 🚀 Roadmap du Projet

## ✅ Livré en V1.0
- ~~**rendre flexible le loader**~~ : l'utilisateur choisit son fichier, en ligne de commande (`--input`) comme dans l'interface web (dépôt).
- ~~**Séparer profiling et cleaning**~~ : l'interface web permet d'analyser, puis de décider, puis de nettoyer, en trois gestes distincts.
- ~~**améliorer la détection des dates**~~ : six formats explicites sont essayés avant l'inférence automatique. La détection était par ailleurs du code mort, jamais atteint (voir Étape 30).

## 🛠️ Développement Technique (En cours)
- **Module `validator`** : Création d'un moteur de vérification des contraintes (types, formats, plages de valeurs).
- **Documentation API** : Rédaction d'un document technique détaillé décrivant l'interface et les paramètres de chaque fonction.
- **Profilage conscient des types** : le profilage précède la correction des types, si bien qu'une colonne de montants en texte n'y révèle aucune valeur aberrante. Un complément d'estimation a été ajouté (Étape 32), mais l'ordre du pipeline mériterait d'être revu.
- **Traitement colonne par colonne** : dans l'interface web, choisir quelles colonnes écrêter ou combler, au lieu de deux décisions globales.

## 📊 Améliorations Fonctionnelles
- **détecter plus de nombres** : gérer les notes (5/10, 17/20) et les pourcentages (1.5%, 78.9875%)
- **déploiement public** : mise en ligne sur Streamlit Community Cloud ou Hugging Face Spaces
- **bouton de soutien** : lien externe vers un prestataire de don (variable `LIEN_DON` dans `app.py`)




