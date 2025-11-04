"""Minimal MCP server exposing Azure Data Lake Storage Gen2 listing."""

from __future__ import annotations

import os
from typing import List

from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient

from mcp.server import MCPServer, Message, Resource


ACCOUNT_URL_ENV = "ADLS_ACCOUNT_URL"


server = MCPServer("adls-gen2")


def _get_service_client() -> DataLakeServiceClient:
    account_url = os.environ.get(ACCOUNT_URL_ENV)
    if not account_url:
        raise RuntimeError(
            f"Missing {ACCOUNT_URL_ENV} environment variable with the ADLS Gen2 DFS endpoint"
        )

    credential = DefaultAzureCredential()
    return DataLakeServiceClient(account_url=account_url, credential=credential)


@server.action("list_files")
async def list_files(container: str, path: str = "/") -> Message:
    """List files within a container/path in Azure Data Lake Storage Gen2."""

    client = _get_service_client()
    filesystem = client.get_file_system_client(container)

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
