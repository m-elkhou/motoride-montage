# 2. Beat-synced montage

## Planning: `gen_batch.py`

Builds `N` themed montages from `moments.jsonl` + `clip_tags.json`:

- **Themes**: `pov`, `rider`, `crew` (counts configured in `THEMES`).
- **Unique clips**: a global `used` set guarantees no clip appears in two montages. Clips already used by
  earlier montages are excluded, as are personal-footage dates (`EXCL_DATE`).
- **Quality gates**: moto score ≥ 0.6, window score ≥ 0.42, brightness ≥ 32, max 2 windows per clip,
  at least 4 distinct clips per montage.
- **Copy**: rotating hooks, closing lines and titles per theme; rotating music from the phonk set.
- **Schedule**: `publishAt` slots, two per day (17:00Z then 10:00Z next day) from a start date set in the script.

It writes `scan/mont/g_<theme>_<nn>.json` (segments) and `scan/batch_manifest.json`.

## Rendering: `render_batch.py` → `viral_cut.py`

`render_batch.py` renders each manifest entry sequentially (240 s timeout per montage; existing outputs over
200 KB are skipped). `viral_cut.py` does the cut:

1. **Beat grid**: `librosa` tempo + beats; the loudest 8-beat window is the **drop**; the music is offset so
   the drop lands at ~35 % of the target length.
2. **Plan**: phrases before the drop use 2 beats per cut; at the drop a **hero** shot of 4 beats plays at
   **0.5× speed (slow-mo)**; after the drop, 4 beats per cut. Tempo above 140 BPM doubles the beat count.
3. **Segments**: each is cropped to 1080x1920, 30 fps, from the pre-selected windows (round-robin over clips).
4. **Grade + text**: contrast/saturation grade with vignette; **hook** text in the first 3 s, **outro** text
   in the last 3 s (`drawtext`, bold, black outline and box).
5. **Master**: music trimmed from the offset, fades in/out, **loudnorm** to −14 LUFS, AAC 192 kbit/s, `+faststart`.

| Flag | Meaning |
|---|---|
| `--segments` | JSON of pre-selected windows `[{clip,start,len,score}]` |
| `--clips` | alternative: let the cutter score each clip itself |
| `--music` | audio file (see [Music](music.md)) |
| `--hook` / `--outro` | opening / closing on-screen text |
| `--target` | length in seconds (default 18) |
| `--out` | output mp4 |
