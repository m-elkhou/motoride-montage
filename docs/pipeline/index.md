# Pipeline

Each stage reads files written by the previous one. Nothing is passed in memory, so any stage can be
re-run on its own.

| # | Stage | Reads | Writes |
|---|---|---|---|
| 1 | [Scan](scan.md) · `inventory.py` | clip folders | `scan/inventory.json` |
| 1 | [Scan](scan.md) · `moments.py` | `inventory.json` | `scan/moments.jsonl` (resumable) |
| 1 | [Scan](scan.md) · `classify.py` | `moments.jsonl` | `scan/clip_tags.json` |
| 1 | [Scan](scan.md) · `check_published.py` | candidates + hash cache | `*_checked.json` |
| 2 | [Plan](montage.md) · `gen_batch.py` | moments + tags | `scan/mont/g_*.json`, `scan/batch_manifest.json` |
| 2 | [Render](montage.md) · `render_batch.py` | manifest + segments + music | `out/<id>.mp4` |
| 3 | [Music](music.md) | — | `public/*.mp3` (yours) |
| 4 | [Voice](voice.md) · `gen_vo_edge.py` | manifest | `vo/<id>.mp3` |
| 4 | [Voice](voice.md) · `overlay_vo.py` | `out/`, `vo/` | `out/<id>.mp4` (overwritten) |
| 5 | [Upload](upload.md) | `meta/*.json` + videos | YouTube + `meta/_uploaded_*.json` |

!!! info "Two render paths"
    The **viral path** (this page) is `viral_cut.py` with ffmpeg. The **[calm path](remotion.md)** is a
    Remotion composition with captions and a narrated voice. Only the viral path is wired end to end.
