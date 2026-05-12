# bluejay-aai-bridge

Bluejay (CHIRP) <-> AssemblyAI Voice Agent API bridge. Runs the same agent
prompt and tool config as the production homepage agent, so Bluejay
simulations exercise the real conversational surface.

## What it does

- Accepts a CHIRP WebSocket from Bluejay at `/voice` (Basic auth).
- Bridges to `wss://agents.assemblyai.com/v1/realtime`.
- Resamples 16 kHz <-> 24 kHz PCM with `scipy.signal.resample_poly`.
- Translates CHIRP <-> AAI events:
  - Bluejay binary frames → AAI `input.audio`.
  - AAI `reply.audio` → Bluejay binary frames.
  - First `reply.audio` of an utterance → CHIRP `speech.started`.
  - AAI `reply.done` → CHIRP `speech.completed`.
  - AAI `error` / `session.error` → CHIRP `session.error`.
- Reuses the production prompt, voice rotation, and AssemblyAI docs MCP
  tools (`search_docs`, `get_pages`, `list_sections`, `get_api_reference`).

## Configure

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

## Sync with main agent

The agent prompt, voice catalog, tool list, and `session_config()` are
copied from `web-agent-proxy/main.py` into [`agent_config.py`](agent_config.py).
When the upstream prompt changes, re-sync this file.

## Tradeoffs

- **Resampling** uses stdlib `audioop.ratecv` because Bluejay sends 10 ms
  frames (160 samples). Filter-based resamplers like
  `scipy.signal.resample_poly` introduce a transient on every chunk
  boundary at that size, which AAI's STT can't decode. `audioop.ratecv`
  is stateful — filter state is carried across calls so chunk boundaries
  don't produce artifacts. Note: `audioop` was deprecated in Python 3.13
  and removed in 3.14; this project pins Python 3.12.
- **Same random voice rotation** as production — exercises the full voice
  surface. If you want determinism per scenario, accept a `voice` query
  param in `bluejay_handler`.
- **Bluejay user `speech.started` is currently logged-only**. AAI's VAD
  barges in fine from the audio alone, and forwarding could cause
  double interrupts. Easy to wire through if simulations show issues.
