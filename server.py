"""Minimal MCP server exposing Azure Data Lake Storage Gen2 listing."""

from __future__ import annotations

import os
from typing import List

from azure.core.credentials import AzureNamedKeyCredential
from azure.storage.filedatalake import DataLakeServiceClient

from mcp.server import MCPServer, Message, Resource

from dotenv import load_dotenv


load_dotenv()


ACCOUNT_NAME_ENV = "AZURE_STORAGE_ACCOUNT_NAME"
ACCOUNT_KEY_ENV = "AZURE_STORAGE_ACCOUNT_KEY"
FILESYSTEM_ENV = "AZURE_STORAGE_FILESYSTEM_NAME"


server = MCPServer("adls-gen2")


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


@server.action("list_files")
async def list_files(container: str | None = None, path: str = "/") -> Message:
    """List files within a filesystem/path in Azure Data Lake Storage Gen2."""

    filesystem_name = container or os.environ.get(FILESYSTEM_ENV)
    if not filesystem_name:
        raise RuntimeError(
            "Filesystem not provided. Pass 'container' parameter or set AZURE_STORAGE_FILESYSTEM_NAME"
        )

    client = _get_service_client()
    filesystem = client.get_file_system_client(filesystem_name)

    entries: List[str] = []
    for item in filesystem.get_paths(path=path):
        suffix = "/" if item.is_directory else ""
        entries.append(f"{item.name}{suffix}")

    content = "\n".join(entries) if entries else "(empty)"
    return Message(content=content)


@server.list_resources
async def resources() -> List[Resource]:
    """Describe available resources for the MCP host."""

    return [
        Resource(
            urn="urn:azure:adlsgen2:list",
            name="ADLS Gen2 file listing",
            description="Expose le contenu d'un conteneur ADLS Gen2 via l'action list_files.",
        )
    ]


if __name__ == "__main__":
    server.run()
