# Handoff

Where the project stands, for whoever picks it up next. Updated 2026-11-13.

The next working session has a ready-made brief: [Next session](next-session.md).

## State

- **Nothing is approved for upload.** Two batches (5, then 2 montages) passed the automatic audit and were all
  rejected by three independent reviewers: other riders far ahead, people at a fuel station and a car park,
  readable plates, a paper on a mudguard, a sticker with the channel name, a reflection of the person filming, a
  shot taken from a car. The planner now has too little verified footage left for a new montage.
- **Anonymity gate** ([Privacy](pipeline/privacy.md)): clean-interval pool (faces, other people, car interior),
  frame-by-frame audit, contact sheets reviewed, approval required by the uploader. Raw originals with a face
  or no motorcycle were deleted on the owner's request on 10 November; the journal is
  `PRIVATE/_suppressions_<date>.json`.
- **Voice** ([Voice](pipeline/voice.md)): the owner's cloned voice, every take re-listened by Whisper
  (`mm_voicecheck.py`): no repetition, no cut word, exactly the intended words. The 22 English hooks of the
  planner are validated (`vo/_cache/`). The audit re-listens to the voice file and the final mix.
- **Descriptions** ([Upload](pipeline/upload.md)): detailed text, signature with the Instagram (from the local
  configuration), hashtags last; the uploader refuses anything else. Same rule in social2shorts.

## Environment, checked on 2026-11-13

- **The render venv is gone**: `C:\workdir\_s2s_cb\venv` (Chatterbox, torch, open_clip, librosa, opencv) no longer
  exists, while `local_paths.json` still points `render_python` at it. It must be rebuilt before any voice,
  scan or audit stage.
- **The model weights were emptied from the Hugging Face cache** (Chatterbox, Whisper large-v3, RT-DETR, CLIP):
  only the folder skeletons remain, so the first run downloads them again (several GB).
- Still in place: the music library (`public/lib/`, 52 files), the 23 validated voices (`vo/_cache/`), the owner's
  French and English voice references (`social2shorts/work/voiceover/ref_fr*.wav`, `ref_en*.wav`), 225 GB free.
- The voice stage and the re-listening are written for **English**: `language_id="en"` in `scan/gen_vo_clone.py`
  and `language="en"` in `mm_voicecheck.py`. A French narration needs both made configurable.

## How to run

```console
python run_pipeline.py --list
python run_pipeline.py --from plan --to check     # plan, voice, render, audit
python scan/privacy_check.py sheets <id>          # then LOOK at the sheets
```

The voice stage needs the render venv (Chatterbox) and the social2shorts venv (faster-whisper); the two models
run in separate processes because they do not fit in memory together.

## Watch out

- The PC has 16 GB; a social2shorts run (scheduled every hour at hh:05) next to the voice or audit stage can
  exhaust memory (Windows error 1455).
- Trending commercial music uploaded through the API is claimed by Content ID ([Music](pipeline/music.md)): the
  owner decides how trending tracks are licensed before any montage uses them.

## Open decisions (owner)

- Relax "no other person in frame" (a helmeted rider far away), or film new footage.
- How to use trending music (commercial tracks and their claims, the in-app Shorts sounds, or a licensed
  library).
- What to do with the Shorts already on the channel that show a face.

See the [TODO](todo.md) for the ordered list.
