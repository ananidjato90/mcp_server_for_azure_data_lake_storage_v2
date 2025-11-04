"""Minimal MCP server exposing Azure Data Lake Storage Gen2 listing."""

from __future__ import annotations

import os
from typing import List

from azure.core.credentials import AzureNamedKeyCredential
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.storage.filedatalake import DataLakeServiceClient

from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP


load_dotenv()


ACCOUNT_NAME_ENV = "AZURE_STORAGE_ACCOUNT_NAME"
ACCOUNT_KEY_ENV = "AZURE_STORAGE_ACCOUNT_KEY"
FILESYSTEM_ENV = "AZURE_STORAGE_FILESYSTEM_NAME"


server = FastMCP(name="adls-gen2", instructions="Parcourir un conteneur Azure Data Lake Storage Gen2")


def _get_service_client() -> DataLakeServiceClient:
    account_name = os.environ.get(ACCOUNT_NAME_ENV)
    account_key = os.environ.get(ACCOUNT_KEY_ENV)

    if not account_name or not account_key:
        raise RuntimeError(
            "Missing credentials: ensure AZURE_STORAGE_ACCOUNT_NAME and AZURE_STORAGE_ACCOUNT_KEY are set"
        )

    account_url = f"https://{account_name}.dfs.core.windows.net"
    credential = AzureNamedKeyCredential(account_name, account_key)
    return DataLakeServiceClient(account_url=account_url, credential=credential)


@server.tool(
    name="list_files",
    title="Lister les fichiers ADLS Gen2",
    description="Affiche le contenu d'un filesystem ADLS Gen2 pour un chemin donné."
)
async def list_files(container: str | None = None, path: str = "/") -> str:
    """List files within a filesystem/path in Azure Data Lake Storage Gen2."""

    filesystem_name = container or os.environ.get(FILESYSTEM_ENV)
    if not filesystem_name:
        raise RuntimeError(
            "Filesystem not provided. Pass 'container' parameter or set AZURE_STORAGE_FILESYSTEM_NAME"
        )

    client = _get_service_client()
    filesystem = client.get_file_system_client(filesystem_name)

    try:
        entries: List[str] = []
        for item in filesystem.get_paths(path=path):
            suffix = "/" if item.is_directory else ""
            entries.append(f"{item.name}{suffix}")
    except ResourceNotFoundError:
        return (
            f"[Erreur] Le filesystem '{filesystem_name}' est introuvable ou vous ne disposez pas des autorisations nécessaires."
        )
    except HttpResponseError as exc:
        message = getattr(exc, "message", None) or str(exc)
        return f"[Erreur] Impossible de lister le chemin '{path}': {message}"

    return "\n".join(entries) if entries else "(empty)"


@server.resource(
    "urn:azure:adlsgen2:list",
    name="ADLS Gen2 file listing",
    title="Contenu d'un filesystem ADLS Gen2",
    description="Utiliser l'outil list_files pour parcourir le filesystem configuré."
)
def describe_resource() -> str:
    return (
        "Utilisez l'outil `list_files` avec les paramètres optionnels `container` et `path` "
        "pour énumérer le contenu du compte Azure Data Lake Storage Gen2."
    )


if __name__ == "__main__":
    print("[ADLS MCP] Serveur démarré. En attente de connexions MCP...")
    server.run()
