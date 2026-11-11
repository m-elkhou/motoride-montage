# 2. Beat-synced montage

## Planning: `gen_batch.py`

Builds themed montages from `moments.jsonl` + `clip_tags.json`, **drawing only from the intervals the
[privacy gate](privacy.md) cleared** (`scan/privacy_pool.json`, minus the ranges in `scan/privacy_blocklist.json`):

- **Themes**: `pov` and `rider` (counts in `THEMES`). The `crew` theme (group rides, meet-ups) is gone: that footage
  is full of faces and bystanders.
- **Lanes**: every clip belongs to **one** montage (its rank, computed without the blocklist, modulo the number of
  montages), so no clip appears twice and **removing one refused segment changes that montage only**: the
  other renders stay valid. A lane without enough verified material is **skipped** and its identifier is not reused.
- **Verified footage only**: a segment is a clean interval trimmed by 0.15 s at each end and at least 2.6 s long; a clip
  that was never analysed is never used. Clips of the montages listed in `used_montages` and the dates in
  `exclude_dates` (`scan/gen_config.json`) are excluded.
- **Quality gates**: moto score >= 0.6, window score >= 0.42, brightness >= 32, 12 segments per montage (at least 9),
  at most 2 per clip, at least 5 distinct clips.
- **Copy**: rotating hooks, closing lines and titles per theme; rotating music from the phonk set.
- **Schedule**: `publishAt` slots, two per day (`slot_hours`, default 17:00Z then 10:00Z next day) from `schedule_start`.
- **Identifiers**: `safe_<theme>_<nn>` (`id_prefix`), so the upload ledger never mixes them with older montages.

It writes `scan/mont/safe_<theme>_<nn>.json` (only when the content changed, so valid renders are kept) and
`scan/batch_manifest.json`.

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
5. **Master** in **two passes**: the video is encoded alone (grade, hook, outro), then the soundtrack built by
   [`mm_audio.py`](voice.md) (music trimmed from the offset, voice, ducking, two-pass loudnorm, AAC 48 kHz) is
   muxed while the video is **copied**, with `+faststart`. A single video+audio graph froze deterministically with
   ffmpeg 9.x; the two-pass version renders the same file in seconds.
6. **Same length for picture and sound**: the beat grid is extended at the tempo when the tracker stops early, and
   the final length is the **real** length of the assembled video (earlier montages ended 1-3 s before their audio).
7. **Only verified footage**: with `--segments` a window can **never leave** the intervals the
   [privacy gate](privacy.md) cleared. `--plan` writes the segments actually used (clip, source start, time in the
   montage) so a refused frame can be traced back to its source; `--audit-proxy` keeps the stitched video without
   text or grade, which is what the gate analyses (a letter of the hook is not mistaken for a face).

| Flag | Meaning |
|---|---|
| `--segments` | JSON of pre-selected windows `[{clip,start,len,score}]` |
| `--clips` | alternative: let the cutter score each clip itself |
| `--music` | audio file (see [Music](music.md)) |
| `--hook` / `--outro` | opening / closing on-screen text |
| `--target` | length in seconds (default 18) |
| `--voice` | short voice (mp3) mixed in the same pass as the music |
| `--plan` / `--audit-proxy` | segments actually used / footage for the privacy gate |
| `--out` | output mp4 |
