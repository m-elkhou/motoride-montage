# motoride-montage

[![Docs](https://img.shields.io/badge/docs-m--elkhou.github.io-orange)](https://m-elkhou.github.io/motoride-montage/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

Viral-style **moto Shorts engine**. It scans raw footage, scores the strongest moments, cuts them **on the beat**
of modern, motivating claim-free music with a hook and a closing line, adds the owner's **cloned voice** (every
take re-listened by Whisper: no repeated phrase, no cut word), refuses anything that could identify the owner or
anyone else, and uploads at the pace YouTube allows with a detailed description.

Companion to [social2shorts](https://github.com/m-elkhou/social2shorts), which provides the YouTube client and OAuth.

**Documentation: <https://m-elkhou.github.io/motoride-montage/>**

## Pipeline

```text
raw clips -> inventory -> moments -> classify (CLIP) -> privacy_scan (clean intervals) -> gen_batch (plan)
          -> gen_vo_clone -> render_batch (viral_cut.py, voice + music in one pass)
          -> privacy_check (audit, review, approve) -> upload_short -> YouTube
```

| Stage | Script |
|---|---|
| Inventory, moments, tags | `scan/inventory.py`, `scan/moments.py`, `scan/classify.py` |
| Plan N unique montages | `scan/gen_batch.py` |
| Beat-synced render | `scan/render_batch.py`, `viral_cut.py` |
| Voice, re-listening and mix | `scan/gen_vo_clone.py`, `mm_voicecheck.py`, `mm_audio.py` |
| Privacy gate | `mm_privacy.py`, `mm_scene.py`, `scan/privacy_scan.py`, `scan/privacy_check.py`, `scan/raw_audit.py` |
| Music ranking | `scan/music_catalog.py` |
| Description rule | `mm_description.py`, `scan/make_meta.py` |
| Upload | `upload_short.py` |
| Narrated "calm" path | `src/` (Remotion), `make_one.py` |

## Quick start

Requires Python 3.12, ffmpeg, and for the full pipeline `librosa`, `torch` + `open_clip_torch`, `edge-tts`.
See [Getting started](https://m-elkhou.github.io/motoride-montage/getting-started/).

```console
python run_pipeline.py --list              # the stages
python run_pipeline.py                     # inventory -> meta (never uploads)
python run_pipeline.py --to upload         # + upload, as a dry run
python run_pipeline.py --to upload --yes-upload   # real upload
```

Every stage is re-runnable (finished work is skipped) and can be run alone from any folder. Settings: paths in
`local_paths.json` / `MM_*` variables, editorial choices in `scan/gen_config.json`
([Configuration](https://m-elkhou.github.io/motoride-montage/configuration/)).

```console
pip install -r requirements-dev.txt && python -m pytest tests -q   # 129 tests, no ffmpeg, network or model needed
```

## What is NOT in this repository

Your **footage, music, rendered videos, voice files, upload metadata, caches and every credential** are
git-ignored by design. You bring your own clips and your own claim-free music. See
[Security and privacy](https://m-elkhou.github.io/motoride-montage/security/).

## Status

A working personal tool. The [architecture review](https://m-elkhou.github.io/motoride-montage/review/) lists each finding with its status and the
[roadmap](https://m-elkhou.github.io/motoride-montage/roadmap/) the planned fixes.

## Licences

Code: [MIT](LICENSE). The Remotion path depends on [Remotion](https://www.remotion.dev/license), which has its
own licence (free for individuals and small teams, paid for larger companies). Music is **not** distributed here:
check the licence of every track you use.
