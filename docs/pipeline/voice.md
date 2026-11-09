# 4. Voice and on-screen text

Viral moto Shorts mostly have **no voice-over** ([Viral DNA](../viral-dna.md)). This engine keeps the voice
**short and light**: the hook line, spoken once, under the music.

## Generating the voice

`scan/gen_vo_edge.py` reads each manifest `hook` and writes `vo/<id>.mp3` with **edge-tts**
(`en-US-GuyNeural`, rate +8 %). It needs network access.

- **Resumable**: a voice that already exists is kept; `--force` regenerates everything.
- **Retries**: 3 attempts per montage (waiting 2 s then 4 s). A montage that still fails is reported and the
  batch carries on; the exit code is `1` if any failed.

Two older Chatterbox generators (cloned voice, `.wav`) are not part of the pipeline:

| Script | Voice | Output | Status |
|---|---|---|---|
| `scan/gen_vo_edge.py` | edge-tts (neural) | `vo/<id>.mp3` | **used** |
| `scan/legacy/gen_vo_hooks.py` | Chatterbox (cloned) | `vo/<id>.wav` | experimental, archived |
| `gen_batch_vo.py` | Chatterbox, multi-sentence + timings | `vo/*.wav`, `specs/*.json` | calm path only |

!!! warning "Chatterbox environment"
    Chatterbox failed on import (`LlamaModel`) after unrelated packages changed the `transformers` version.
    Keep it in its own venv.

## Mixing: `scan/overlay_vo.py`

Delays the voice by 0.4 s, boosts it by 1.35, and mixes it over the music with `amix normalize=0` so the music
keeps its level. The video stream is copied (no re-encode) and the file is replaced in place.

!!! success "Idempotent"
    After mixing, the script writes a marker `out/<id>.voiced` holding the file's signature (size and date).
    Running it again does **not** add the voice twice. If you re-render a montage, the signature changes and the
    voice is mixed again automatically.

| Option | Use |
|---|---|
| *(none)* | mix only what is not already voiced |
| `--assume-done` | write markers for videos that are **already** voiced, without mixing (migration) |
| `--force` | mix even if marked: this **doubles** the voice on an already-voiced file |

A montage whose video is missing or invalid is reported as a warning, not as a failure.
