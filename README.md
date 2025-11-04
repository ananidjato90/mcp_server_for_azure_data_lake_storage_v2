# MCP Server – Azure Data Lake Storage Gen2

Ce dépôt contient un serveur MCP minimal permettant de parcourir un conteneur Azure Data Lake Storage Gen2 grâce à l'outil MCP `list_files`.

## Prérequis

- Python 3.10+
- Compte Azure Data Lake Storage Gen2 avec clé d'accès
- Fichier `.env` contenant :

  ```env
  AZURE_STORAGE_ACCOUNT_NAME=<nom-du-compte>
  AZURE_STORAGE_ACCOUNT_KEY=<cle-d-acces>
  AZURE_STORAGE_FILESYSTEM_NAME=<filesystem-ou-conteneur>
  ```

## Installation

1. Créer un environnement virtuel si besoin.
2. Installer les dépendances :

   ```bash
   pip install -r requirements.txt
   ```

   Si vous n'utilisez pas de fichier `requirements.txt`, installez directement :

   ```bash
   pip install mcp azure-storage-file-datalake python-dotenv
   ```

3. Vérifier que le fichier `.env` est présent à la racine du projet avec les variables citées plus haut.

## Démarrage du serveur

Lancer simplement :

```bash
python server.py
```

Le serveur expose un outil `list_files` qui accepte :

- `container` (optionnel) : nom du conteneur/file system à interroger. Si absent, la valeur de `AZURE_STORAGE_FILESYSTEM_NAME` est utilisée.
- `path` (optionnel) : chemin à parcourir, `/` par défaut

La réponse contient la liste des éléments trouvés, chaque dossier étant suffixé par `/`. Un chemin vide renvoie `(empty)`.

## Intégration dans un client MCP

Déclarer ce serveur dans votre client MCP favori (Cursor, VSCode, etc.) en pointant vers la commande `python server.py`. Le client découvrira automatiquement la ressource `urn:azure:adlsgen2:list` et pourra appeler l'outil `list_files` pour explorer les conteneurs.

## Dépannage

- Contrôler la présence et la validité des variables dans le fichier `.env`.
- Vérifier que la clé d'accès fournie correspond au compte ADLS ciblé.
- S'assurer que le filesystem renseigné existe et que votre clé dispose des droits en lecture.
