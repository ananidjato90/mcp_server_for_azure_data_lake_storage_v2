"""MCP client using Azure OpenAI to drive natural language requests."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from mcp import types
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from openai import AzureOpenAI


PROJECT_ROOT = Path(__file__).parent
SERVER_SCRIPT = PROJECT_ROOT / "server.py"

SYSTEM_PROMPT = (
    "Tu aides l'utilisateur à explorer un compte Azure Data Lake Storage Gen2. "
    "Analyse sa requête et retourne un JSON strict avec deux clés :\n"
    "- container : le filesystem/conteneur à utiliser (null si non précisé)\n"
    "- path : chemin à lister (par défaut '/')\n"
    "Exemple de réponse : {\"container\": null, \"path\": \"/\"}."
)


def load_settings() -> dict[str, str]:
    load_dotenv()

    required_env = ["AZURE_OPENAI_API_KEY", "AZURE_ENDPOINT", "AZURE_VERSION"]
    missing = [name for name in required_env if not os.environ.get(name)]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(f"Missing Azure OpenAI environment variables: {joined}")

    return {
        "api_key": os.environ["AZURE_OPENAI_API_KEY"],
        "endpoint": os.environ["AZURE_ENDPOINT"],
        "api_version": os.environ["AZURE_VERSION"],
        "deployment": os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini"),
        "python_exec": os.environ.get("PYTHON_EXECUTABLE", "python3"),
    }


def build_azure_client(settings: dict[str, str]) -> AzureOpenAI:
    return AzureOpenAI(
        api_key=settings["api_key"],
        azure_endpoint=settings["endpoint"],
        api_version=settings["api_version"],
    )


def parse_server_response(data: types.CallToolResult) -> str:
    if data.isError:
        return "[Erreur] L'outil a signalé une erreur. Consultez les logs serveur."

    lines: list[str] = []
    if data.content:
        for block in data.content:
            if isinstance(block, types.TextContent):
                lines.append(block.text)

    return "\n".join(lines) if lines else "(aucun résultat)"


def to_tool_arguments(model_output: str) -> Dict[str, Any]:
    try:
        payload: Dict[str, Any] = json.loads(model_output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "La réponse du modèle n'est pas un JSON valide.\n"
            f"Contenu reçu : {model_output}"
        ) from exc

    arguments: Dict[str, Any] = {}
    container = payload.get("container")
    path = payload.get("path")

    if container is not None:
        arguments["container"] = container
    if path is not None:
        arguments["path"] = path

    return arguments


async def run_mcp_query(query: str) -> str:
    settings = load_settings()
    client = build_azure_client(settings)

    response = client.responses.create(
        model=settings["deployment"],
        input=[
            {"role": "system", "content": [{"type": "text", "text": SYSTEM_PROMPT}]},
            {"role": "user", "content": [{"type": "text", "text": query}]},
        ],
        response_format={"type": "json_object"},
    )

    tool_arguments = to_tool_arguments(response.output_text)

    server_params = StdioServerParameters(
        command=settings["python_exec"],
        args=[str(SERVER_SCRIPT)],
        cwd=str(PROJECT_ROOT),
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool("list_files", tool_arguments)
            return parse_server_response(result)


async def main(query: str) -> None:
    output = await run_mcp_query(query)
    print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Client MCP propulsé par Azure OpenAI")
    parser.add_argument("query", help="Requête en langage naturel pour explorer ADLS Gen2")
    args = parser.parse_args()

    asyncio.run(main(args.query))
