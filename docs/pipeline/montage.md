# 2. Beat-synced montage

## Planning: `gen_batch.py`

Builds `N` themed montages from `moments.jsonl` + `clip_tags.json`:

- **Themes**: `pov`, `rider`, `crew` (counts configured in `THEMES`).
- **Unique clips**: a global `used` set guarantees no clip appears in two montages. Clips of the montages listed
  in `used_montages` are excluded, as are the footage dates in `exclude_dates` (both in `scan/gen_config.json`).
- **Quality gates**: moto score ≥ 0.6, window score ≥ 0.42, brightness ≥ 32, max 2 windows per clip,
  at least 4 distinct clips per montage.
- **Copy**: rotating hooks, closing lines and titles per theme; rotating music from the phonk set.
- **Schedule**: `publishAt` slots, two per day (`slot_hours`, default 17:00Z then 10:00Z next day) from `schedule_start`
  in `scan/gen_config.json`.

It writes `scan/mont/g_<theme>_<nn>.json` (segments) and `scan/batch_manifest.json`.

## Rendering: `render_batch.py` → `viral_cut.py`

`render_batch.py` renders each manifest entry sequentially. Valid outputs (over 200 KB) are skipped (`--force`
re-renders everything). `MM_RENDER_TIMEOUT` (default 240 s) caps each render: on timeout it kills **only that
render's process tree** (never other ffmpeg jobs on the machine), deletes the partial file and moves on; the exit
code is `1` if any montage failed. `viral_cut.py` does the cut:

1. **Beat grid**: `librosa` tempo + beats; the loudest 8-beat window is the **drop**; the music is offset so
   the drop lands at ~35 % of the target length.
2. **Plan**: phrases before the drop use 2 beats per cut; at the drop a **hero** shot of 4 beats plays at
   **0.5× speed (slow-mo)**; after the drop, 4 beats per cut. Tempo above 140 BPM doubles the beat count.
3. **Segments**: each is cropped to 1080x1920, 30 fps, from the pre-selected windows (round-robin over clips).
4. **Grade + text**: contrast/saturation grade with vignette; **hook** text in the first 3 s, **outro** text
   in the last 3 s (`drawtext`, bold, black outline and box).
5. **Master** in **two passes**: the video is encoded alone (grade, hook, outro), then the music (trimmed from the
   offset, fades, **loudnorm** to −14 LUFS, AAC 192 kbit/s) is mixed in while the video is **copied**, with `+faststart`.
   A single video+audio graph froze deterministically with ffmpeg 9.x; the two-pass version renders the same file
   in seconds.

| Flag | Meaning |
|---|---|
| `--segments` | JSON of pre-selected windows `[{clip,start,len,score}]` |
| `--clips` | alternative: let the cutter score each clip itself |
| `--music` | audio file (see [Music](music.md)) |
| `--hook` / `--outro` | opening / closing on-screen text |
| `--target` | length in seconds (default 18) |
| `--out` | output mp4 |
