"""
Agent configuration — system prompt, voice catalog, tool definitions, and
session_config builder. Copied from the main web-agent-proxy repo so this
service can be deployed independently. When the upstream prompt changes,
this file should be re-synced.
"""

import json
import random
from datetime import datetime, timezone

from mcp import ClientSession


MCP_URL = "https://mcp.assemblyai.com/docs"


TOOLS = [
    {
        "type": "function",
        "name": "search_docs",
        "description": (
            "Search AssemblyAI documentation across all pages. Use whenever a "
            "user asks something factual about AssemblyAI products, APIs, SDKs, "
            "features, models, languages, pricing, or behavior that isn't "
            "already in your context. Returns relevant snippets and page paths."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural-language query."},
            },
            "required": ["query"],
        },
    },
    {
        "type": "function",
        "name": "get_pages",
        "description": (
            "Retrieve full content of specific AssemblyAI documentation pages "
            "by path. Use after search_docs when a snippet isn't enough."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Page paths returned by search_docs.",
                },
            },
            "required": ["paths"],
        },
    },
    {
        "type": "function",
        "name": "list_sections",
        "description": (
            "Browse the structure of AssemblyAI documentation. Use when you're "
            "not sure what to search for."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "get_api_reference",
        "description": (
            "Get API endpoint details and schemas for AssemblyAI APIs."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "endpoint": {
                    "type": "string",
                    "description": "Endpoint path or topic.",
                },
            },
        },
    },
]


async def execute_mcp_tool(mcp: ClientSession, event: dict) -> dict:
    """Forward a Voice Agent tool.call to the AssemblyAI docs MCP server."""
    name = event.get("name", "")
    args = event.get("arguments", event.get("args", {}))
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {}
    try:
        mcp_result = await mcp.call_tool(name, args)
        text = "\n".join(c.text for c in mcp_result.content if getattr(c, "text", None))
        result = text or "No content returned."
    except Exception as e:
        result = f"Error calling {name}: {e}"
    print(f"  Tool: {name}({json.dumps(args)[:80]}) → {result[:120]}")
    return {"call_id": event.get("call_id", ""), "result": result}


VOICES = {
    # English — US
    "ivy":     {"accent": "American", "desc": "professional, deliberate, smooth"},
    "james":   {"accent": "American", "desc": "conversational, professional, male"},
    "tyler":   {"accent": "American", "desc": "theatrical, energetic, chatty, jagged"},
    "winter":  {"accent": "American", "desc": "empathetic, aesthetic, conversational"},
    "sam":     {"accent": "American", "desc": "soft, conversational, young"},
    "mia":     {"accent": "American", "desc": "smooth, conversational, young"},
    "bella":   {"accent": "American", "desc": "high-pitched, chatty"},
    "david":   {"accent": "American", "desc": "deep, calming, conversational"},
    "jack":    {"accent": "American", "desc": "smooth, direct, clear, fast-paced"},
    "kyle":    {"accent": "American", "desc": "chatty, nasal, expressive"},
    "helen":   {"accent": "American", "desc": "soft, older, calming"},
    "martha":  {"accent": "American", "desc": "Southern, older, warm"},
    "emma":    {"accent": "American", "desc": "lively, young, conversational"},
    "victor":  {"accent": "American", "desc": "deep, older"},
    "eleanor": {"accent": "American", "desc": "deeper, older, calming"},
    # English — UK
    "sophie":  {"accent": "British",  "desc": "clear, smooth, instructive, simple"},
    "oliver":  {"accent": "British",  "desc": "narrative, conversational"},
}


def pick_voice() -> str:
    """Pick a random voice for this session."""
    return random.choice(list(VOICES.keys()))


SYSTEM_PROMPT_TEMPLATE = """\
# Configure your own agent's system prompt here.
#
# This bridge does not ship with a default prompt. Drop whatever
# personality, rules, and behaviour you want the agent to have.
#
# The following format keys are interpolated at session start in
# session_config() below — use them in your prompt or remove them:
#   {voice_name}       — randomly picked TTS voice for this session
#   {voice_accent}     — e.g. "American" / "British"
#   {voice_desc}       — short description of the voice's personality
#   {current_datetime} — current UTC datetime as a readable string
"""


GREETING = ""  # Configure your own greeting, or leave empty for the agent
               # to stay silent until the user speaks first.

KEYTERMS: list[str] = []  # Words to bias transcription toward, e.g. brand
                          # names or product names. Optional.


def session_config(voice: str) -> dict:
    """Build the session.update payload for AssemblyAI Voice Agent API.

    Edit SYSTEM_PROMPT_TEMPLATE, GREETING, and KEYTERMS above to configure
    the agent.
    """
    info = VOICES[voice]
    now = datetime.now(timezone.utc)
    current_datetime = now.strftime("%A, %B %-d, %Y at %-I:%M %p UTC")
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        voice_name=voice,
        voice_accent=info["accent"],
        voice_desc=info["desc"],
        current_datetime=current_datetime,
    )
    session: dict = {
        "system_prompt": system_prompt,
        "tools": TOOLS,
        "input": {"type": "audio"},
        "output": {"type": "audio", "voice": voice},
    }
    if GREETING:
        session["greeting"] = GREETING
    if KEYTERMS:
        session["input"]["keyterms"] = KEYTERMS
    return {"type": "session.update", "session": session}
