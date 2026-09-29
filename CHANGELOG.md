# Journal des versions

Le détail technique de chaque étape de développement se trouve dans
[`DEROULEMENT_PROJET.md`](DEROULEMENT_PROJET.md).

## [1.1.1] — 2026-09-29

### Modifié

- **L'onglet « Téléchargements » est rétabli**, en récapitulatif : tous les
  fichiers produits y sont réunis, au fil du parcours. Les boutons contextuels
  restent proposés dans chaque onglet.

### Ajouté

- **« Ouvrir en grand »** : les rapports HTML s'affichent dans une fenêtre
  modale large (jusqu'à 1 280 px). C'est l'équivalent sûr d'un nouvel onglet :
  les navigateurs bloquent l'ouverture d'un HTML encodé dans l'URL, et le
  service de fichiers statiques de Streamlit imposerait d'écrire le rapport sur
  le serveur, dans un dossier public.

317 tests passent.

---

## [1.1.0] — 2026-09-29

Première confrontation avec un utilisateur réel, sur un fichier réel. Six
retours, qui ont mené à une faille de sécurité, une perte de données silencieuse
et une interface repensée autour de ses usages.

### Sécurité

- **Le rapport HTML exécutait le contenu du fichier analysé.** Aucune donnée
  issue du fichier (noms de colonnes, modalités, valeurs d'aperçu) n'était
  échappée, et l'aperçu désactivait explicitement l'échappement de pandas
  (`to_html(escape=False)`). Une cellule contenant `<img src=x onerror=…>`
  produisait un rapport qui exécutait ce code à son ouverture. Corrigé par un
  échappement systématique, doublé d'une politique de sécurité (CSP) qui interdit
  toute exécution de script dans le rapport, même si un échappement venait à
  manquer.

### Corrigé

- **1 849 montants étaient silencieusement vidés** sur le jeu de référence : le
  séparateur de milliers (`1 052,23 €`) n'était jamais retiré avant conversion,
  alors que le README citait précisément cet exemple. Les espaces ordinaires,
  insécables (U+00A0) et fines insécables (U+202F) sont désormais retirées.
- **Le symbole `£`** était accepté par la détection mais jamais retiré par la
  conversion : toute colonne en livres sterling aurait été entièrement vidée.
- **Les en-têtes du tableau des conversions** du rapport de nettoyage étaient
  inversés (« Type converti | Colonnes » au-dessus de « colonne | type »).
- **Le test d'intégrité des sources excluait silencieusement l'interface web**
  après le renommage de `app.py` : il filtrait sa liste de fichiers sur leur
  existence.

### Ajouté

- **Aucune perte silencieuse** : toute valeur présente qu'une conversion de type
  ne sait pas lire est recensée dans `stats['values_unparsed']` (colonne, nombre,
  exemples) et restituée dans la console, le rapport de nettoyage et l'interface.
  Sur un fichier de prix, une date en l'an 216 — coquille pour 2016 — est ainsi
  nommée au lieu de disparaître.
- **Page d'accueil** présentant le projet : le problème traité, des exemples
  avant / après, le parcours, trois principes et l'histoire du projet.
- **« Essayer avec un exemple »** : charge l'échantillon versionné, pour éprouver
  l'outil sans fichier.
- **Onglet « Après nettoyage »** : profil de contrôle calculé d'office, avec un
  verdict colonne par colonne sur l'invariant de typage.
- **Aperçu des rapports HTML** dans l'application, à la demande.
- **`find_mistyped_columns`**, fonction publique du moteur, partagée par les
  tests et l'interface.

### Modifié

- **`app.py` devient `streamlit_app.py`**, nom par défaut de Streamlit
  Community Cloud.
- **Chaque rapport se consulte et se récupère là où il s'affiche.** L'onglet
  « Téléchargements » disparaît. Rapports HTML : aperçu et téléchargement.
  Rapports Markdown : téléchargement.
- **Le formulaire se réduit aux deux décisions qui altèrent les valeurs** :
  écrêtage et remplissage. L'aide du remplissage prévient qu'une absence peut
  avoir un sens.
- **Le détail des conversions de types est affiché d'emblée**, et non plus replié.
- **Les rapports ne sont générés qu'au clic** ou à l'ouverture de leur aperçu.

### Retiré

- La case « Rapport de nettoyage » : elle ajoutait un bouton dans un autre onglet,
  sans effet visible là où on la cochait.
- La case « Enregistrer aussi dans data/reports » : sans objet en ligne, et
  contraire à la promesse de confidentialité. L'écriture sur disque reste
  l'affaire de la ligne de commande.
- Le réglage du nombre de passes : le moteur s'arrête de lui-même.

313 tests passent.

---

## [1.0.1] — 2026-09-27

Tient l'invariant du double profilage : le rapport avant nettoyage constate le
désordre, celui d'après atteste sa disparition. Quatre colonnes du jeu de
référence restaient mal typées après nettoyage.

### Corrigé

- **Les conventions de date mélangées dans une même colonne n'étaient pas
  traitées.** Une colonne réelle mêle couramment `13/09/2024` (69 %),
  `2023-09-15` (17 %) et `18-07-2023` (9 %). Les formats étaient mis en
  concurrence et le meilleur retenu : aucun n'atteignait le seuil de 80 %, alors
  que leur cumul couvre 95 % de la colonne. Ils sont désormais appliqués
  cumulativement, chacun ne comblant que ce que les précédents ont laissé vide.
  Le catalogue passe de six à dix formats.
- **Aucune colonne comportant plus de 10 % de valeurs manquantes ne pouvait être
  convertie**, quel que soit son contenu : le taux de validité était mesuré sur
  la hauteur de la colonne plutôt que sur ses valeurs présentes. C'est ce qui
  empêchait `note_satisfaction` (16 % de trous) de devenir numérique.
- **Un plantage sur les colonnes saugrenues.** Une colonne de notes rejetée à
  tort par le filtre numérique poursuivait jusqu'à la branche de conversion en
  date, où un format permissif interprétait `5/5` en une année absurde,
  provoquant une exception `OutOfBoundsDatetime`. Un contrôle de plausibilité des
  années (1900-2100) l'écarte, et l'accumulation passe par `combine_first`, qui
  laisse pandas harmoniser les résolutions temporelles.

### Ajouté

- **Notes fractionnaires et pourcentages** : `17/20` devient `17`, `78.9875%`
  devient `78.9875`. Pour une note, c'est le **numérateur** qui est retenu et non
  le quotient — seul choix cohérent quand une colonne mêle `5` et `5/5`, ce qui
  est le cas dans les exports réels. Limite connue et documentée : une colonne
  mêlant `17/20` et `4/5` resterait incohérente.
- **`tests/test_invariant_post_nettoyage.py`** : 15 tests qui verrouillent
  l'invariant, écrits comme une propriété générale (« aucune colonne textuelle
  restante ne doit être convertible ») et non comme une liste de colonnes
  attendues, afin de résister à l'évolution des jeux de données.

### Effet mesuré

Sur le jeu de référence de 73 810 lignes, le nombre de colonnes correctement
typées passe de 1 à 5, et le nombre de valeurs aberrantes écrêtées de 2 795 à
**5 848**. Cette progression est la conséquence directe du correctif : une
colonne restée en texte est invisible pour la détection IQR.

279 tests passent.

---

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
