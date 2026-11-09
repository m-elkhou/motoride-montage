# motoride-montage

[![Docs](https://img.shields.io/badge/docs-m--elkhou.github.io-orange)](https://m-elkhou.github.io/motoride-montage/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

Viral-style **moto Shorts engine**. It scans raw footage, scores the strongest moments, cuts them **on the beat**
of claim-free phonk music with a hook and a closing line, adds a short voice, and uploads at the pace
YouTube allows.

Companion to [social2shorts](https://github.com/m-elkhou/social2shorts), which provides the YouTube client and OAuth.

**Documentation: <https://m-elkhou.github.io/motoride-montage/>**

## Pipeline

```text
raw clips -> inventory -> moments -> classify (CLIP) -> gen_batch (plan)
          -> render_batch (viral_cut.py) -> gen_vo_edge -> overlay_vo -> upload_short -> YouTube
```

| Stage | Script |
|---|---|
| Inventory, moments, tags | `scan/inventory.py`, `scan/moments.py`, `scan/classify.py` |
| Plan N unique montages | `scan/gen_batch.py` |
| Beat-synced render | `scan/render_batch.py`, `viral_cut.py` |
| Voice and mix | `scan/gen_vo_edge.py`, `scan/overlay_vo.py` |
| Upload | `upload_short.py` |
| Narrated "calm" path | `src/` (Remotion), `make_one.py` |

## Quick start

Requires Windows, Python 3.12, ffmpeg, and for the full pipeline `librosa`, `torch` + `open_clip_torch`,
`edge-tts`. See [Getting started](https://m-elkhou.github.io/motoride-montage/getting-started/).

```console
python scan/inventory.py && python scan/moments.py && python scan/classify.py
python scan/gen_batch.py
python scan/render_batch.py
python scan/gen_vo_edge.py && python scan/overlay_vo.py   # overlay: run once
python upload_short.py meta/<id>.json --dry-run
```

## What is NOT in this repository

Your **footage, music, rendered videos, voice files, upload metadata, caches and every credential** are
git-ignored by design. You bring your own clips and your own claim-free music. See
[Security and privacy](https://m-elkhou.github.io/motoride-montage/security/).

## Status

A working personal tool published as-is. Paths are Windows-oriented and some are still hard-coded.
The [architecture review](https://m-elkhou.github.io/motoride-montage/review/) lists every known gap and the
[roadmap](https://m-elkhou.github.io/motoride-montage/roadmap/) the planned fixes.

## Licences

Code: [MIT](LICENSE). The Remotion path depends on [Remotion](https://www.remotion.dev/license), which has its
own licence (free for individuals and small teams, paid for larger companies). Music is **not** distributed here:
check the licence of every track you use.
