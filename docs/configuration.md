# Configuration and data layout

Settings live in three places, from most to least specific. Nothing personal is ever committed.

| Where | What | Committed? |
|---|---|---|
| **Environment variables** | tools and external folders (`MM_FFMPEG`, `MM_S2S_ROOT`, …) | no |
| **`local_paths.json`** (repo root) | the same settings, written once for your machine | **no** (git-ignored) |
| **`scan/gen_config.json`** | editorial choices: excluded dates, schedule, texts, themes | **no** (git-ignored); a sample is provided |
| Code defaults | repo-relative paths, `ffmpeg` from `PATH`, the current Python | yes |

## Paths and tools: `mm_paths.py`

Every script gets its paths from `mm_paths.py`, so there is no absolute path in the code. Priority for each
setting: **environment variable → `local_paths.json` → default**.

| Setting | Environment variable | `local_paths.json` key | Default |
|---|---|---|---|
| ffmpeg | `MM_FFMPEG` | `ffmpeg` | `ffmpeg` found on `PATH` |
| ffprobe | `MM_FFPROBE` | `ffprobe` | `ffprobe` found on `PATH` |
| Python for scan/render/voice | `MM_RENDER_PYTHON` | `render_python` | the Python running the script |
| social2shorts location | `MM_S2S_ROOT` | `s2s_root` | `../social2shorts` (sibling folder) |
| Cloned-voice reference | `MM_VOICE_REF` | `voice_ref` | `<social2shorts>/work/voiceover/ref_en_clean.wav` |
| Action-cam folder | `MM_INSTA360_DIR` | `insta360_dir` | `~/Desktop/insta360` |
| Text font | `MM_FONT` | `font` | Arial Bold on Windows, DejaVu Sans Bold on Linux |

```json
{
  "ffmpeg": "C:/tools/ffmpeg/bin/ffmpeg",
  "render_python": "C:/venvs/render/Scripts/python.exe",
  "s2s_root": "D:/projects/social2shorts"
}
```

Scripts in `scan/` use repo-relative paths; `mm_paths.use_root()` moves to the repository root, so you can launch
them **from any folder**.

## Editorial settings: `scan/gen_config.json`

Read by `gen_batch.py`, `build_montages.py` and `make_meta.py` through `mm_config.py`. Copy
`scan/gen_config.example.json` and adapt it.

| Key | Meaning | Default |
|---|---|---|
| `exclude_dates` | clip-name prefixes never used (personal footage) | none |
| `used_montages` | earlier montages whose clips are forbidden (`scan/mont/<name>.json`) | none |
| `schedule_start` | first publication slot, ISO 8601 UTC | tomorrow at the first slot hour |
| `slot_hours` | the two daily slot hours (UTC) | `[17, 10]` |
| `themes` | `{"pov": [["moto_pov"], 12], …}` category list and count per theme | pov 12, rider 10, crew 6 |
| `music`, `hooks`, `outros`, `titles`, `tagset` | override the built-in lists | built-in |
| `descriptions` | `{"about": "…", "intro": {"pov": "…"}}` for `make_meta.py` | built-in |

!!! tip "One exclusion list for all scripts"
    `gen_batch.py` and `build_montages.py` read the same `exclude_dates`, so they can no longer disagree.

## Other settings

| Setting | Where | Default |
|---|---|---|
| Render timeout per montage | `MM_RENDER_TIMEOUT` (seconds) | 240 |
| CUDA decoding | `SCAN_HW=1` (or `0` to force off) | on for classification if CUDA is available |
| Scan workers | `SCAN_WORKERS` | 3 |
| Voice | `VOICE`, `RATE` in `scan/gen_vo_edge.py` | `en-US-GuyNeural`, `+8%` |
| Voice level and delay | `FC` in `scan/overlay_vo.py` | volume 1.35, delay 400 ms |
| Target length | manifest `target` | 18 s |
| Uploader pacing | `upload_short.py` flags | retry 10 min, 6 h (launcher: 45 min, 30 h) |

## Folder layout

Everything marked **local** is created on your machine and is **git-ignored**.

```text
motoride-montage/
├── mm_paths.py  mm_run.py  mm_config.py   shared paths, safe process runner, editorial config
├── run_pipeline.py         orchestrator (named stages, --from / --to / --only)
├── viral_cut.py            beat-synced cutter
├── upload_short.py         YouTube uploader (ledger, validation)
├── make_one.py  gen_batch_vo.py  build_preview_sheet.py   calm path and contact sheet
├── src/                    Remotion composition
├── scan/                   inventory, moments, classify, plan, render, voice, mix, meta
│   ├── legacy/             obsolete or experimental scripts, kept for reference
│   ├── gen_config.example.json
│   ├── gen_config.json     local
│   └── *.json, *.jsonl, mont/   local  analysis results and segments
├── tests/                  pytest suite (no ffmpeg, no network, no YouTube)
├── local_paths.json        local
├── public/                 local  music (claim-free), staged clips
├── out/                    local  rendered videos and their *.voiced markers
├── vo/                     local  voice files
├── meta/                   local  upload metadata, the upload ledger and logs
└── docs/, mkdocs.yml       this site
```
