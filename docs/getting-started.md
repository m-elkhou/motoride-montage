# Getting started

## Requirements

| Need | Used by | Notes |
|---|---|---|
| Windows 10/11 | whole pipeline | a few paths and `taskkill`/`NUL` calls are Windows-only today |
| Python 3.12 | all scripts | one venv for scan/render/voice |
| ffmpeg + ffprobe | everything | currently expected at `C:/ffmpeg/bin/` |
| `librosa`, `numpy`, `Pillow` | `viral_cut.py`, `moments.py` | beat tracking and scoring |
| `torch`, `open_clip_torch` | `classify.py` | CLIP ViT-B-32, CUDA optional but fast |
| `edge-tts` | `gen_vo_edge.py` | online neural voice, needs network |
| Node 18+ | Remotion calm path | `npm i` then `npm run dev` |
| [social2shorts](https://github.com/m-elkhou/social2shorts) | `upload_short.py` | provides OAuth + `secrets/` ([details](pipeline/upload.md)) |

## Run it end to end

All scripts expect the **repository root as working directory** (they use relative paths).

```console
# 1. find and score the footage
python scan/inventory.py
python scan/moments.py
python scan/classify.py

# 2. plan N unique montages (hooks, titles, schedule)
python scan/gen_batch.py

# 3. put your claim-free music in public/ (see Music), then render
python scan/render_batch.py

# 4. voice, then mix it in (run overlay ONCE, see the review)
python scan/gen_vo_edge.py
python scan/overlay_vo.py

# 5. write meta/<id>.json (see Upload) and send
python upload_short.py meta/g_pov_00.json --dry-run
```

!!! danger "Run `overlay_vo.py` once"
    It rewrites `out/<id>.mp4` in place. Running it twice mixes the voice in twice. Re-render first.

## One montage by hand

```console
python viral_cut.py --segments scan/mont/g_pov_00.json \
  --music public/ph_drift.mp3 --hook "Find your road" --outro "Keep riding" \
  --target 18 --out out/g_pov_00.mp4
```

See the [pipeline](pipeline/index.md) for what each stage reads and writes, and
[Configuration](configuration.md) for the folder layout.
