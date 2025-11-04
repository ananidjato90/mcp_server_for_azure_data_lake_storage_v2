"""MCP client using Azure OpenAI to drive natural language requests."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from mcp import types
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from openai import AzureOpenAI


PROJECT_ROOT = Path(__file__).parent
SERVER_SCRIPT = PROJECT_ROOT / "server.py"

SYSTEM_PROMPT_BASE = (
    "Tu aides l'utilisateur à explorer un compte Azure Data Lake Storage Gen2. "
    "Analyse sa requête et produis un JSON strict contenant exactement deux clés :\n"
    "- container : la valeur doit être null si l'utilisateur ne fournit pas explicitement un nom de conteneur.\n"
    "- path : le chemin à lister (par défaut '/').\n"
    "Traite les expressions comme 'racine' ou 'root' comme le chemin '/'."
)


def build_system_prompt(default_filesystem: Optional[str]) -> str:
    prompt = SYSTEM_PROMPT_BASE
    if default_filesystem:
        prompt += (
            f"\nLe filesystem par défaut configuré côté serveur est '{default_filesystem}'. "
            "Si l'utilisateur ne mentionne aucun autre conteneur, laisse 'container' à null pour utiliser cette valeur côté serveur."
        )
    prompt += "\nRéponds uniquement avec un objet JSON valide sans texte supplémentaire."
    return prompt


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
        "default_filesystem": os.environ.get("AZURE_STORAGE_FILESYSTEM_NAME"),
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


def sanitize_model_output(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def normalize_container(value: Any, default_filesystem: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    lowered = text.lower()
    synonyms = {
        "racine",
        "root",
        "default",
        "défaut",
        "conteneur par défaut",
        "filesystem par défaut",
        "conteneur racine",
        "filesystem racine",
        "null",
        "none",
    }

    if lowered in synonyms:
        return None

    return text


def normalize_path(value: Any) -> str:
    if value is None:
        return "/"

    text = str(value).strip()
    if not text:
        return "/"

    lowered = text.lower()
    if lowered in {"racine", "root", "/", "racine du conteneur", "root folder"}:
        return "/"

    if not text.startswith("/"):
        return f"/{text}"

    return text


def to_tool_arguments(model_output: str, default_filesystem: Optional[str]) -> Dict[str, Any]:
    try:
        cleaned = sanitize_model_output(model_output)
        payload: Dict[str, Any] = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "La réponse du modèle n'est pas un JSON valide.\n"
            f"Contenu reçu : {model_output}"
        ) from exc

    arguments: Dict[str, Any] = {}
    container = normalize_container(payload.get("container"), default_filesystem)
    path = normalize_path(payload.get("path"))

    if container is not None:
        arguments["container"] = container
    if path is not None:
        arguments["path"] = path

    return arguments


def extract_model_output(response: Any) -> str:
    """Extract plain text output from the Azure OpenAI response payload."""

    text = getattr(response, "output_text", None)
    if text:
        return text

    candidates = getattr(response, "output", None)
    if candidates:
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if not content and isinstance(candidate, dict):
                content = candidate.get("content")
            if not content:
                continue
            for block in content:
                block_text = getattr(block, "text", None)
                if not block_text and isinstance(block, dict):
                    block_text = block.get("text")
                if block_text:
                    return block_text

    choices = getattr(response, "choices", None)
    if choices:
        for choice in choices:
            message = getattr(choice, "message", None)
            if not message and isinstance(choice, dict):
                message = choice.get("message")
            if not message:
                continue
            content = getattr(message, "content", None)
            if not content and isinstance(message, dict):
                content = message.get("content")
            if isinstance(content, str) and content:
                return content
            if isinstance(content, list):
                for block in content:
                    block_text = getattr(block, "text", None)
                    if not block_text and isinstance(block, dict):
                        block_text = block.get("text")
                    if block_text:
                        return block_text

    raise RuntimeError("Impossible d'extraire la réponse du modèle Azure OpenAI.")


async def run_mcp_query(query: str) -> str:
    settings = load_settings()
    client = build_azure_client(settings)
    default_filesystem = settings.get("default_filesystem")
    system_prompt = build_system_prompt(default_filesystem)

    response = client.chat.completions.create(
        model=settings["deployment"],
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ],
        temperature=0,
    )

    model_output = extract_model_output(response)
    tool_arguments = to_tool_arguments(model_output, default_filesystem)

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
    parser.add_argument("query", nargs="?", help="Requête en langage naturel pour explorer ADLS Gen2")
    args = parser.parse_args()

    user_query = args.query or input("Entrez votre requête pour ADLS Gen2 : ")

    asyncio.run(main(user_query))
