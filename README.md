# bluejay-aai-bridge

A WebSocket bridge that lets [Bluejay](https://getbluejay.ai) (over the
[CHIRP](https://docs.getbluejay.ai) protocol) run voice simulations against
the [AssemblyAI Voice Agent API](https://www.assemblyai.com/docs/voice-agents/voice-agent-api).

You bring your own system prompt — the bridge is a transport-only adapter.

## What it does

- Accepts a CHIRP WebSocket from Bluejay at `/voice` (HTTP Basic auth).
- Bridges to `wss://agents.assemblyai.com/v1/realtime`.
- Resamples 16 kHz ↔ 24 kHz PCM with stdlib `audioop.ratecv` (stateful).
- Translates CHIRP ↔ AAI events:
  - Bluejay binary frames → AAI `input.audio`.
  - AAI `reply.audio` → Bluejay binary frames.
  - First `reply.audio` of an utterance → CHIRP `speech.started`.
  - AAI `reply.done` → CHIRP `speech.completed`.
  - AAI `error` / `session.error` → CHIRP `session.error`.
- Optional live tool calls into the AssemblyAI docs MCP server
  (`search_docs`, `get_pages`, `list_sections`, `get_api_reference`).

## Configure your agent

Open [`agent_config.py`](agent_config.py) and edit:

- **`SYSTEM_PROMPT_TEMPLATE`** — your agent's system prompt. Empty by
  default. Supports these format keys:
  - `{voice_name}` — randomly picked TTS voice for this session.
  - `{voice_accent}` — e.g. `American` / `British`.
  - `{voice_desc}` — short description of the voice's personality.
  - `{current_datetime}` — current UTC datetime as a readable string.
- **`GREETING`** — what the agent says first. Empty by default (agent
  waits silently until the user speaks).
- **`KEYTERMS`** — words to bias transcription toward (brand names,
  product names). Empty by default.
- **`VOICES`** — voice catalog used by `pick_voice()` for random
  per-session selection. Default includes the eighteen English AAI
  voices; trim to a subset if you only want certain voices.
- **`TOOLS`** — function tools registered on the AAI session. Default
  is the AssemblyAI docs MCP (`search_docs`, `get_pages`, etc.). Set
  to `[]` if you don't want tool calling.

## Configure deployment

| Env var | Required | Notes |
|---|---|---|
| `ASSEMBLYAI_API_KEY` | yes | Bearer token for upstream Voice Agent API. |
| `CHIRP_USER` | yes (prod) | Basic-auth user Bluejay sends. Skip for dev. |
| `CHIRP_PASS` | yes (prod) | Basic-auth password Bluejay sends. Skip for dev. |
| `PORT` | auto | Railway injects. Defaults to 8767 locally. |
| `AAI_WS_URL` | no | Override upstream (e.g. EU endpoint). |

## Run locally

```sh
pip install -r requirements.txt
ASSEMBLYAI_API_KEY=sk_xxx python main.py
```

Then point Bluejay at `ws://localhost:8767/voice` (or `/`) with no auth.

With auth:

```sh
ASSEMBLYAI_API_KEY=sk_xxx CHIRP_USER=tomas CHIRP_PASS=tomas python main.py
```

## Deploy on Railway

1. Push this folder to a Git repo.
2. New Railway service → connect repo.
3. Set env vars: `ASSEMBLYAI_API_KEY`, `CHIRP_USER`, `CHIRP_PASS`.
4. Railway picks up `Procfile` (`web: python main.py`) and `runtime.txt`.
5. Use the generated Railway URL (replace `https://` with `wss://`)
   in your Bluejay agent config.

## Notes

- **Resampling** uses stdlib `audioop.ratecv` because Bluejay sends 10 ms
  frames (160 samples). Filter-based resamplers like
  `scipy.signal.resample_poly` introduce a transient on every chunk
  boundary at that size, which AAI's STT can't decode. `audioop.ratecv`
  is stateful — filter state is carried across calls so chunk boundaries
  don't produce artifacts. `audioop` was deprecated in Python 3.13 and
  removed in 3.14; this project pins Python 3.12.
- **Bluejay user `speech.started` is currently logged-only**. AAI's VAD
  barges in fine from the audio alone, and forwarding could cause
  double interrupts. Easy to wire through if simulations show issues.
