from __future__ import annotations

import json
import sys
from typing import Any, Callable

from . import mcp_server


SERVER_NAME = "seo-writer-skill"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2025-11-25"


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


TOOLS: dict[str, dict[str, Any]] = {
    "get_seo_writer_instructions": {
        "description": "Return the workflow, iteration, and final-content rules for using these SEO tools.",
        "handler": mcp_server.get_seo_writer_instructions,
        "inputSchema": _schema({}),
    },
    "discover_serp_urls": {
        "description": "Discover candidate SERP URLs using manual URLs, a configured API provider, or Chrome-backed Google search.",
        "handler": mcp_server.discover_serp,
        "inputSchema": _schema(
            {
                "query": {"type": "string"},
                "urls": {"type": "array", "items": {"type": "string"}, "default": []},
                "serp_provider": {"type": "string", "description": "brave, serper, serpapi, google-chrome, or env default"},
                "geo": {"type": "string"},
                "language": {"type": "string", "default": "en"},
                "top_n": {"type": "integer", "default": 10},
            },
            ["query"],
        ),
    },
    "build_seo_brief": {
        "description": "Build an SEO content brief and writer guidance from source URLs or a configured SERP provider.",
        "handler": mcp_server.build_seo_brief,
        "inputSchema": _schema(
            {
                "query": {"type": "string"},
                "urls": {"type": "array", "items": {"type": "string"}, "default": []},
                "serp_provider": {"type": "string", "description": "brave, serper, serpapi, google-chrome, or env default"},
                "geo": {"type": "string"},
                "language": {"type": "string", "default": "en"},
                "top_n": {"type": "integer", "default": 8},
            },
            ["query"],
        ),
    },
    "analyze_seo_draft": {
        "description": "Analyze a Hugo/markdown draft against a saved or newly built brief.",
        "handler": mcp_server.analyze_seo_draft,
        "inputSchema": _schema(
            {
                "query": {"type": "string"},
                "draft_markdown": {"type": "string"},
                "urls": {"type": "array", "items": {"type": "string"}, "default": []},
                "serp_provider": {"type": "string"},
                "brief": {"type": "string"},
                "title": {"type": "string"},
                "h1": {"type": "string"},
                "top_n": {"type": "integer", "default": 8},
            },
            ["query", "draft_markdown"],
        ),
    },
    "rewrite_seo_draft": {
        "description": "Create scaffold rewrite guidance while preserving Hugo front matter by default.",
        "handler": mcp_server.rewrite_seo_draft,
        "inputSchema": _schema(
            {
                "query": {"type": "string"},
                "draft_markdown": {"type": "string"},
                "urls": {"type": "array", "items": {"type": "string"}, "default": []},
                "serp_provider": {"type": "string"},
                "brief": {"type": "string"},
                "title": {"type": "string"},
                "h1": {"type": "string"},
                "top_n": {"type": "integer", "default": 8},
                "update_frontmatter": {"type": "boolean", "default": False},
            },
            ["query", "draft_markdown"],
        ),
    },
    "optimize_seo_draft": {
        "description": "Run iterative scaffold optimization and return scoring/guidance JSON.",
        "handler": mcp_server.optimize_seo_draft,
        "inputSchema": _schema(
            {
                "query": {"type": "string"},
                "draft_markdown": {"type": "string"},
                "urls": {"type": "array", "items": {"type": "string"}, "default": []},
                "serp_provider": {"type": "string"},
                "brief": {"type": "string"},
                "top_n": {"type": "integer", "default": 8},
                "iterations": {"type": "integer", "default": 3},
                "update_frontmatter": {"type": "boolean", "default": False},
            },
            ["query", "draft_markdown"],
        ),
    },
    "qa_seo_content": {
        "description": "Check final Hugo markdown for scaffold text, metadata leaks, and front matter issues.",
        "handler": mcp_server.qa_seo_content,
        "inputSchema": _schema(
            {
                "query": {"type": "string"},
                "draft_markdown": {"type": "string"},
                "noisy_terms": {"type": "array", "items": {"type": "string"}, "default": []},
            },
            ["query", "draft_markdown"],
        ),
    },
    "launch_chrome_profile": {
        "description": "Launch a persistent Chrome profile for browser-backed SERP discovery.",
        "handler": mcp_server.launch_chrome_profile,
        "inputSchema": _schema(
            {
                "profile_dir": {"type": "string", "default": "data/chrome/seo-writer"},
                "port": {"type": "integer"},
                "start_url": {"type": "string", "default": "about:blank"},
                "headless": {"type": "boolean", "default": False},
            }
        ),
    },
}


def _tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "description": spec["description"],
            "inputSchema": spec["inputSchema"],
        }
        for name, spec in TOOLS.items()
    ]


def _send(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, separators=(",", ":")), flush=True)


def _result(request_id: Any, result: dict[str, Any]) -> None:
    _send({"jsonrpc": "2.0", "id": request_id, "result": result})


def _error(request_id: Any, code: int, message: str) -> None:
    _send({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}})


def _handle_tool_call(request_id: Any, params: dict[str, Any]) -> None:
    name = params.get("name")
    arguments = params.get("arguments") or {}
    if name not in TOOLS:
        _error(request_id, -32602, f"Unknown tool: {name}")
        return
    handler: Callable[[dict[str, Any]], dict[str, Any]] = TOOLS[name]["handler"]
    try:
        result = handler(arguments)
    except Exception as exc:  # noqa: BLE001
        message = f"{name} failed: {exc}"
        _result(
            request_id,
            {
                "content": [{"type": "text", "text": message}],
                "structuredContent": {"ok": False, "error": message},
                "isError": True,
            },
        )
        return
    _result(
        request_id,
        {
            "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
            "structuredContent": result,
            "isError": False,
        },
    )


def handle_message(message: dict[str, Any]) -> None:
    request_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}

    if method == "notifications/initialized":
        return
    if method == "initialize":
        _result(
            request_id,
            {
                "protocolVersion": params.get("protocolVersion") or PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": (
                    "SEO guidance and Hugo content QA tools. Generated drafts are scaffold "
                    "outputs for an AI or human writer, not final publishable prose. "
                    "Call get_seo_writer_instructions first to get the full writer loop, "
                    "stop/iterate criteria, and final Hugo article rules."
                ),
            },
        )
        return
    if method == "tools/list":
        _result(request_id, {"tools": _tool_definitions()})
        return
    if method == "tools/call":
        _handle_tool_call(request_id, params)
        return
    if method == "ping":
        _result(request_id, {})
        return

    if request_id is not None:
        _error(request_id, -32601, f"Method not found: {method}")


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        request_id = None
        try:
            message = json.loads(line)
            request_id = message.get("id")
            handle_message(message)
        except Exception as exc:  # noqa: BLE001
            _error(request_id, -32603, str(exc))


if __name__ == "__main__":
    main()
