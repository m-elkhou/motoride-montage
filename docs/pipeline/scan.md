# 1. Scan and select moments

The scan turns a folder of hours of rushes into a ranked list of **moments** and a **tag** per clip.

## `inventory.py`

Walks the configured clip folders with `ffprobe` (30 s timeout per file) and writes
`scan/inventory.json`: path, size, duration, resolution.

## `moments.py`

For every clip, computes four signals and keeps the best windows:

| Signal | How |
|---|---|
| Motion | ffmpeg `scene` score at 10 fps on a 160 px downscale |
| Sharpness | variance of the Laplacian on 2 fps gray frames (rejects blur and shake) |
| Audio energy | RMS |
| Brightness | mean luma (rejects near-black night clips) |

Output is **one JSON line per clip** in `scan/moments.jsonl`, with `top4` windows of 2 s and 4 s. The file
is appended line by line, so an interrupted scan resumes where it stopped. `SCAN_HW=1` enables CUDA decoding.
A clip whose ffmpeg pass fails is recorded as `ok: false` with the reason, instead of silently producing empty arrays.

## `classify.py`

Zero-shot **CLIP** (`ViT-B-32`, `laion2b_s34b_b79k`) on two frames per clip against ten labels
(`moto_pov`, `rider`, `group_ride`, `bike_meet`, `scenery`, `city_night`, …). It stores a **moto score** and the
top categories in `scan/clip_tags.json`. The planner only keeps clips with `moto ≥ 0.6`.

The classification is **resumable**: the checkpoint is reloaded, so only new clips are processed (`+0 nouveaux`
when nothing changed). CUDA decoding is used only if available (`SCAN_HW=0/1` to force) and every ffmpeg call has a
timeout.

## `check_published.py`

Filters candidates already published on the channel using perceptual hashes (Hamming distance ≤ 10)
against social2shorts' duplicate store. Hashes are cached in `scan/published_hashes.json`, keyed by **name + size + modification date**, so a replaced file
is re-hashed.

!!! note
    Moments are *pre-selected* before the cutter runs: `viral_cut.py --segments` receives the chosen
    windows directly instead of re-analysing each clip. This keeps rendering fast and deterministic.
