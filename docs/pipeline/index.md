# Pipeline

Each stage reads files written by the previous one. Nothing is passed in memory, so any stage can be
re-run on its own, and `python run_pipeline.py` chains them (stopping at the first failure; the upload only on
request).

| # | Stage | Reads | Writes |
|---|---|---|---|
| 1 | [Scan](scan.md) · `inventory.py` | clip folders | `scan/inventory.json` |
| 1 | [Scan](scan.md) · `moments.py` | `inventory.json` | `scan/moments.jsonl` (resumable) |
| 1 | [Scan](scan.md) · `classify.py` | `moments.jsonl` | `scan/clip_tags.json` |
| 2 | [Privacy](privacy.md) · `privacy_scan.py` | moments + tags | `scan/privacy_pool.json`: intervals with **no visible face, no second person and no car interior** (resumable; `--cars` re-filters) |
| 3 | [Plan](montage.md) · `gen_batch.py` | privacy pool + blocklist | `scan/mont/safe_*.json`, `scan/batch_manifest.json` |
| 4 | [Voice](voice.md) · `gen_vo_clone.py` | manifest | `vo/<id>.wav` (the owner's cloned voice, calm pace), `vo/_cache/` |
| 5 | [Render](montage.md) · `render_batch.py` | manifest + segments + music + voice | `out/<id>.mp4` (video, voice and music in **one pass**), `out/<id>.plan.json`, `out/_cat/<id>.mp4` |
| 6 | [Check](privacy.md) · `privacy_check.py audit` | `out/` | `meta/_privacy/<id>.json`; refused frames go to `scan/privacy_blocklist.json` |
| 6 | [Review and approve](privacy.md) · `privacy_check.py sheets` / `approve` | contact sheets you **look at** | `meta/_privacy_ok.json` |
| 7 | [Metadata](upload.md) · `make_meta.py` | manifest + `out/` | `meta/<id>.json` |
| 7 | [Upload](upload.md) · `upload_short.py` | `meta/*.json` + videos | YouTube + the ledger `meta/_uploaded.json`; **refuses anything not approved** |
| - | [Music](music.md) | — | `public/*.mp3` (yours) |

!!! info "Two render paths"
    The **viral path** (this page) is `viral_cut.py` with ffmpeg. The **[calm path](remotion.md)** is a
    Remotion composition with captions and a narrated voice. Only the viral path is wired end to end.
