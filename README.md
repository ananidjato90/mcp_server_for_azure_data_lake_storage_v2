# MCP Server – Azure Data Lake Storage Gen2

Ce dépôt contient un serveur MCP minimal permettant de parcourir un conteneur Azure Data Lake Storage Gen2 grâce à l'action `list_files`.

## Prérequis

- Python 3.10+
- Compte Azure Data Lake Storage Gen2 avec accès en lecture
- Authentification configurée pour `DefaultAzureCredential` (variables `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`, Managed Identity, Azure CLI, etc.)

## Installation

1. Créer un environnement virtuel si besoin.
2. Installer les dépendances :

   ```bash
   pip install -r requirements.txt
   ```

   Si vous n'utilisez pas de fichier `requirements.txt`, installez directement :

   ```bash
   pip install mcp azure-identity azure-storage-file-datalake
   ```

3. Exporter l'URL du compte ADLS Gen2 (point de terminaison `dfs`), par exemple :

   ```bash
   export ADLS_ACCOUNT_URL="https://<nom-compte>.dfs.core.windows.net"
   ```

## Démarrage du serveur

Lancer simplement :

```bash
python server.py
```

Le serveur expose une action `list_files` qui accepte :

- `container` (obligatoire) : nom du conteneur ou file system ADLS Gen2
- `path` (optionnel) : chemin à parcourir, `/` par défaut

La réponse contient la liste des éléments trouvés, chaque dossier étant suffixé par `/`. Un chemin vide renvoie `(empty)`.

## Intégration dans un client MCP

Déclarer ce serveur dans votre client MCP favori (Cursor, VSCode, etc.) en pointant vers la commande `python server.py`. Le client découvrira automatiquement la ressource `urn:azure:adlsgen2:list` et pourra appeler l'action `list_files` pour explorer les conteneurs.

## Dépannage

- Vérifier que l'authentification Azure fonctionne (`az login`, variables d'environnement, Managed Identity…).
- Contrôler la valeur de `ADLS_ACCOUNT_URL` et le nom du conteneur passé à l'action.
- Activer la journalisation Azure Storage côté service si besoin d'un diagnostic plus fin.
