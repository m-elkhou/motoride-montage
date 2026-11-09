# 4. Voice and on-screen text

Viral moto Shorts mostly have **no voice-over** ([Viral DNA](../viral-dna.md)). This engine keeps the voice
**short and light**: the hook line, spoken once, under the music.

## Generating the voice

`scan/gen_vo_edge.py` reads each manifest `hook` and writes `vo/<id>.mp3` with **edge-tts**
(`en-US-GuyNeural`, rate +8 %). It needs network access and has no retry yet.

Two older generators remain for cloned-voice experiments. They use **Chatterbox** and write `.wav`, which
`overlay_vo.py` does not read:

| Script | Voice | Output | Status |
|---|---|---|---|
| `scan/gen_vo_edge.py` | edge-tts (neural) | `vo/<id>.mp3` | **used** |
| `scan/gen_vo_hooks.py` | Chatterbox (cloned) | `vo/<id>.wav` | experimental |
| `gen_batch_vo.py` | Chatterbox, multi-sentence + timings | `vo/*.wav`, `specs/*.json` | calm path only |

!!! warning "Chatterbox environment"
    Chatterbox failed on import (`LlamaModel`) after unrelated packages changed the `transformers` version.
    Keep it in its own venv.

## Mixing: `overlay_vo.py`

Delays the voice by 0.4 s, boosts it by 1.35, and mixes it over the music with `amix normalize=0` so the
music keeps its level. The video stream is copied (no re-encode) and the file is replaced in place.

!!! danger "Not idempotent"
    Running it twice adds the voice twice. Re-render the montage before mixing again.
