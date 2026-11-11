# Handoff

Where the project stands, for whoever picks it up next. Updated 2026-11-11.

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
  (`mm_voicecheck.py`): no repetition, no cut word, exactly the intended words. The 22 hooks of the planner are
  validated. The audit re-listens to the voice file and the final mix.
- **Descriptions** ([Upload](pipeline/upload.md)): detailed text, signature with the Instagram (from the local
  configuration only), hashtags last; the uploader refuses anything else. Same rule in social2shorts.

## How to run

```console
python run_pipeline.py --list
python run_pipeline.py --from plan --to check     # plan, voice, render, audit
python scan/privacy_check.py sheets <id>          # then LOOK at the sheets
```

The voice stage needs the render venv (Chatterbox) and the social2shorts venv (faster-whisper); the two models
run in separate processes because they do not fit in memory together.

## Watch out

- The PC has 16 GB; a social2shorts continuous run next to the voice or audit stage can exhaust memory (Windows
  error 1455).
- The repository is public: no channel name, handle or Instagram in code, docs or tests.

## Open decisions (owner)

- Relax "no other person in frame" (a helmeted rider far away), or film new footage.
- What to do with the Shorts already on the channel that show a face.

See the [TODO](todo.md) for the ordered list.
