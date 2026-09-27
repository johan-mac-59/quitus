# Journal des versions

Le détail technique de chaque étape de développement se trouve dans
[`DEROULEMENT_PROJET.md`](DEROULEMENT_PROJET.md).

## [1.0.0] — 2026-09-27

Première version stable. Le projet passe d'un script de terminal à une
application utilisable par deux interfaces, au-dessus d'une logique métier
unique.

### Ajouté

- **Interface web Streamlit** (`app.py`) : dépôt de fichier, profilage, réglage
  des options, nettoyage, graphiques et téléchargements, en cinq onglets.
  Aucune logique de nettoyage n'y est dupliquée.
- **Ligne de commande outillée** : `--input`, `--output`, `--reports`,
  `--format-rapport`, plus deux modes non interactifs (`--oui-a-tout`,
  `--non-interactif`) utilisables en automatisation. Code de sortie exploitable.
- **`src/plot_factory.py`** : les cinq graphiques du projet deviennent des
  objets réutilisables, consommés à la fois par les rapports HTML et par
  l'interface web.
- **`src/console_capture.py`** : détourne la sortie console du pipeline vers
  l'interface web, pour que sa traçabilité reste visible dans le navigateur.
- **`load_dataframe(octets, nom)`** : chargement depuis la mémoire, sans fichier
  temporaire, pour consommer un fichier déposé dans un navigateur.
- **Mesures de confidentialité** : aucune écriture serveur par défaut, cache
  borné (1 h, 8 entrées), bouton d'effacement des données, télémétrie Streamlit
  désactivée, encart de transparence.
- **Échantillon de démonstration** synthétique versionné dans `data/samples/`,
  qui rend le dépôt utilisable immédiatement après un clone.
- **`requirements.txt`** pour les installations pip, en complément de `uv.lock`.
- **Tests** : 264 au total, contre 103. Dont 27 tests d'intégration qui pilotent
  réellement l'interface web sans navigateur, un garde-fou anti-fuite de figures,
  et des contrôles structurels sur les sources.

### Corrigé

- **L'écrêtage des valeurs aberrantes ne fonctionnait pas.** Un décalage d'un
  niveau de profondeur dans un dictionnaire faisait conclure « aucune valeur
  aberrante » et renvoyer un refus **sans poser la question**. La réponse de
  l'utilisateur était en réalité consommée par la question suivante, d'où
  l'illusion que tout fonctionnait. Sur le jeu de référence, 2 795 valeurs
  aberrantes sont désormais écrêtées là où l'ancien code en corrigeait zéro.
- **Le pipeline plantait sur toute colonne entière.** Écrêter une colonne `Int64`
  avec une borne IQR fractionnaire lève une exception dans pandas — or
  `fix_numeric_types` produit justement des `Int64`. Le moteur se sabotait
  lui-même.
- **La détection de dates était du code mort.** Un garde-fou de performance
  interrompait la boucle avant le bloc de conversion, jamais atteint pour une
  date. Six formats explicites sont désormais essayés avant l'inférence.
- **Les rapports HTML exploratoires étaient malformés** : le contenu de la
  sous-classe était ajouté après la fermeture du document, refermé une seconde
  fois.
- **Les valeurs manquantes devenaient la chaîne `"nan"`** dans les colonnes
  textuelles, fabriquant de fausses modalités qui faussaient cardinalités et
  graphiques.
- **Fuite de figures matplotlib** : une figure était abandonnée à chaque rapport,
  et toute exception de tracé en laissait une de plus. Rendu impossible par
  construction, en sortant de `plt.figure()`.
- **`clip_outliers` mutait le DataFrame de l'appelant**, faute de copie défensive.
- **`CleanLogger.get_summary` levait un `TypeError`** si les statistiques
  contenaient `None`.
- **La sortie console échouait dès qu'elle était redirigée** : sous Windows,
  Python retombe sur cp1252, incapable d'encoder les emojis du pipeline.
- **`generate_md_report` levait sur un nom de fichier nu.**
- **`generate_enhanced_report` ne retournait pas le chemin** du rapport produit.
- **17 tests étaient en échec** avant ce chantier, masquant les deux premiers
  bugs de cette liste.

### Modifié

- **Rendu des rapports HTML** : les figures surdimensionnées sont ramenées à des
  tailles raisonnables (matrice de dispersion plafonnée à 6 colonnes, heatmap en
  10×8 au lieu de 25×20). Un rapport exploratoire complet pèse 186 Ko contre
  plusieurs mégaoctets.
- **Les questions posées par `src/` deviennent des paramètres** (`answer=`,
  `choice=`, `generate=`, `report_format=`). Les signatures et le comportement
  en terminal sont inchangés, mais chaque invite gagne une garde contre
  l'absence de terminal.
- **Le diagnostic des valeurs aberrantes est complété** par une estimation sur
  les colonnes textuelles convertibles en numérique, signalée comme telle. Le
  profilage précédant la correction des types, une colonne de montants au format
  `"1 200,50 €"` n'y apparaissait pas comme numérique.
- **18 méthodes passe-plat supprimées** dans les sous-classes de profileur.

### Retiré

- Les dépendances PyPI `typing` et `pathlib` : deux backports abandonnés,
  `pathlib` installant un module qui masque celui de la bibliothèque standard.
- Les chemins codés en dur dans `main.py`.

---

## [0.1.0] — 2026-08-20

Pipeline de nettoyage en ligne de commande : chargement multi-format, double
profilage avant et après nettoyage, moteur de transformation, rapports Markdown
et HTML. Voir les Étapes 1 à 29 de [`DEROULEMENT_PROJET.md`](DEROULEMENT_PROJET.md).
