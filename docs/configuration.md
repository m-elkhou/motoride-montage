# Configuration and data layout

There is no config file yet: settings live as constants at the top of each script (see the
[review](review.md) for the plan to centralise them).

## Folder layout

Everything marked **local** is created on your machine and is **git-ignored**.

```text
motoride-montage/
├── viral_cut.py            beat-synced cutter
├── upload_short.py         YouTube uploader
├── make_one.py             Remotion calm path driver
├── gen_batch_vo.py         multi-sentence voice (calm path)
├── build_preview_sheet.py  contact sheet of rendered videos
├── src/                    Remotion composition (Root.tsx, Composition.tsx)
├── scan/                   analysis + planning + batch scripts
│   ├── *.py, _upload_launch.ps1
│   ├── inventory.json      local
│   ├── moments.jsonl       local
│   ├── clip_tags.json      local
│   ├── batch_manifest.json local
│   └── mont/               local  segment files per montage
├── public/                 local  music (claim-free), staged clips
├── out/                    local  rendered videos
├── vo/                     local  voice files
├── meta/                   local  upload metadata + upload logs
├── specs/, props/          local  calm-path inputs
└── docs/, mkdocs.yml       this site
```

## Settings to change for your setup

| Setting | Where | Default (author's machine) |
|---|---|---|
| ffmpeg / ffprobe | top of `viral_cut.py`, `scan/*.py` | `C:/ffmpeg/bin/ffmpeg` |
| Python venv for rendering | `scan/render_batch.py`, `prune_render.py`, `rerender_phonk.py` | a separate venv with librosa/torch |
| Clip folders | `scan/inventory.py` | social2shorts `inbox/`, `camera_roll/`, a Desktop folder |
| social2shorts location | `upload_short.py`, `scan/check_published.py`, `gen_batch_vo.py` | sibling folder |
| Themes and counts | `THEMES` in `scan/gen_batch.py` | pov 12, rider 10, crew 6 |
| Music rotation | `MUSIC` in `scan/gen_batch.py` | nine `ph_*.mp3` |
| Schedule start | `start=` in `scan/gen_batch.py` | a fixed date: update it |
| Voice | `scan/gen_vo_edge.py` | `en-US-GuyNeural`, +8 % |
| Voice level and delay | `scan/overlay_vo.py` | volume 1.35, delay 400 ms |
| Target length | manifest `target` | 18 s |
| Uploader pacing | `upload_short.py` flags | retry 10 min, 6 h (launcher uses 45 min / 30 h) |

## Environment variables

| Variable | Effect |
|---|---|
| `SCAN_HW=1` | decode with CUDA in `moments.py` |
