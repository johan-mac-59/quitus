# Glossaire

Un aide-mémoire pour comprendre les mots et les notions que l'on croise dans Quitus : ceux du traitement de données, ceux de Python et de pandas, et ceux propres au projet. Pour la description exacte de chaque fonction (paramètres, retour), voir [API.md](API.md).

## Les données

**DataFrame** : le tableau de pandas, des lignes et des colonnes nommées. Toute la logique de Quitus travaille sur des DataFrames.

**Encodage** : la façon dont un fichier code ses caractères en octets. UTF-8 est le standard actuel. Latin-1 et CP1252 sont courants sur les fichiers produits par Excel ou Windows en Europe ; un mauvais encodage affiche des caractères parasites (`Ã©` au lieu de `é`). Quitus le détecte tout seul.

**Séparateur** : le caractère qui sépare les colonnes d'un CSV (`;`, `,`, tabulation, `|`). Quitus le détecte en vérifiant que le nombre de colonnes reste le même sur plusieurs lignes.

**Valeur manquante (NaN, `<NA>`)** : une cellule sans valeur. Le texte « N/A », « NULL » ou « - » en est une écriture.

**Cardinalité** : le nombre de valeurs distinctes d'une colonne. Une cardinalité proche du nombre de lignes désigne un identifiant ; une cardinalité faible, une catégorie.

**Int64 (entier nullable)** : le type entier de pandas qui accepte les valeurs manquantes. Avec le type `int64` classique de NumPy, une seule cellule vide obligerait la colonne à passer en décimaux.

**Zéro initial** : le `0` en tête d'un code (téléphone `0612345678`, code postal `01000`). Il n'a de sens qu'en texte : converti en nombre, il disparaît. Quitus laisse ces colonnes en texte.

**Parquet** : un format de fichier colonne par colonne, qui conserve les types et se compresse bien. Il demande la bibliothèque `pyarrow`.

**JSON Lines (JSONL)** : un fichier avec un objet JSON par ligne, courant pour les journaux et les exports d'API.

## Les statistiques

**Quartiles (Q1, Q3)** : les valeurs sous lesquelles se trouvent 25 % puis 75 % des données. La médiane est le deuxième quartile, au milieu.

**IQR (écart interquartile)** : Q3 moins Q1. C'est la largeur de la zone centrale des données.

**Valeur aberrante (outlier)** : une valeur très éloignée des autres. Quitus la repère avec la règle de Tukey : au-delà de Q1 moins 1,5 fois l'IQR, ou de Q3 plus 1,5 fois l'IQR. Le coefficient 1,5 est le **seuil**, réglable par colonne.

**Écrêtage (winsorisation)** : remplacer une valeur aberrante par la borne la plus proche, au lieu de la supprimer. Il modifie la distribution, donc il n'est jamais appliqué sans accord de l'utilisateur.

**Imputation (remplissage)** : combler une valeur manquante, ici par la médiane (colonnes numériques) ou le mode (texte). Le **mode** est la valeur la plus fréquente. Là encore, jamais sans accord : une absence peut avoir un sens.

**Corrélation** : la mesure de la force du lien entre deux colonnes numériques, de -1 à 1. La heatmap la représente en couleurs.

## Le nettoyage dans Quitus

**Profilage** : l'inspection d'un fichier avant de toucher à quoi que ce soit : types, valeurs manquantes, doublons, valeurs aberrantes, incohérences de casse.

**Double profilage** : un profil avant nettoyage, qui constate le désordre, et un profil après, qui atteste qu'il a disparu. Aucune colonne mal typée ne doit subsister dans le second (l'invariant de l'Étape 29).

**Conversion de types** : transformer en nombres ou en dates les colonnes qui en ont l'apparence, comme `1 200,50 €`, `78 %`, `17/20` ou `13/09/2024`.

**Perte silencieuse** : une valeur présente qui devient manquante sans que personne ne le sache. Quitus la déclare toujours : colonne, nombre de valeurs et exemples.

**Note fractionnaire** : une note écrite `17/20`. Quand une colonne mêle plusieurs échelles, toutes les notes sont ramenées à l'échelle dominante, et chaque note ramenée est signalée.

**Cellule structurée** : une cellule qui contient une liste ou un objet (JSON, Parquet). Quitus l'écrit en texte JSON pour pouvoir la comparer et la profiler.

**Piloté par l'utilisateur (human-in-the-loop)** : les traitements qui changent les valeurs (écrêtage, remplissage) sont proposés colonne par colonne, jamais appliqués d'office.

**Rapport d'audit** : le document qui justifie chaque correction : source, horodatage, avant et après, détail des opérations.

## Python et l'outillage

**Annotation de type (typing)** : l'indication du type attendu d'un paramètre ou d'un retour dans une signature, comme `df: pd.DataFrame`. Elle documente le code et aide l'éditeur à repérer des erreurs.

**Docstring** : le texte entre triples guillemets sous une fonction. Il décrit ce qu'elle fait, ses paramètres et son retour. `docs/API.md` en est généré.

**Fonction pure** : une fonction qui ne modifie pas ses arguments et renvoie un résultat. Dans `cleaner_engine`, chaque étape reçoit un DataFrame et en renvoie un nouveau.

**pytest** : l'outil qui lance les tests (`uv run python -m pytest`). Un test échoue quand le code ne fait plus ce qu'il garantit.

**uv** : l'outil qui installe l'environnement Python du projet (`uv sync`) et y lance les commandes.

**Streamlit** : la bibliothèque qui fabrique l'interface web de Quitus. Elle réexécute le script à chaque interaction ; la **session** garde l'état d'un visiteur, le **cache** est commun au serveur.

**Base64** : une façon d'écrire des octets (une image) sous forme de texte. C'est ce qui permet d'intégrer les graphiques dans le fichier HTML du rapport, qui reste ainsi autonome.

**CSP (politique de sécurité de contenu)** : une consigne placée dans l'en-tête d'un document HTML qui interdit au navigateur d'exécuter des scripts. Les rapports de Quitus en portent une.

**Échappement** : remplacer les caractères spéciaux d'une donnée (`<`, `|`, guillemet) pour qu'elle soit affichée comme du texte et jamais interprétée comme du code ou de la mise en forme.

**SHA-256** : une empreinte du contenu d'un fichier. Deux fichiers identiques octet pour octet ont la même. L'interface s'en sert pour savoir si le fichier déposé a changé.

**Horodatage** : la marque `AAAAMMJJ_HHMMSS` ajoutée au nom des fichiers produits. L'ordre alphabétique est l'ordre chronologique, et les essais successifs ne s'écrasent pas.
