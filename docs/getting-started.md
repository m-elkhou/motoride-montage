# Getting started

## Requirements

| Need | Used by | Notes |
|---|---|---|
| Windows 10/11 (Linux/macOS mostly fine) | whole pipeline | the PowerShell launcher is Windows-only; everything else uses portable calls |
| Python 3.12 | all scripts | one venv for scan/render/voice |
| ffmpeg + ffprobe | everything | on `PATH`, or set `MM_FFMPEG` / `MM_FFPROBE` ([Configuration](configuration.md)) |
| `librosa`, `numpy`, `Pillow` | `viral_cut.py`, `moments.py` | beat tracking and scoring |
| `torch`, `open_clip_torch` | `classify.py` | CLIP ViT-B-32, CUDA optional but fast |
| `chatterbox-tts` | `gen_vo_clone.py` | the owner's cloned voice (a GPU helps) |
| Node 18+ | Remotion calm path | `npm i` then `npm run dev` |
| [social2shorts](https://github.com/m-elkhou/social2shorts) | `upload_short.py` | provides OAuth + `secrets/` ([details](pipeline/upload.md)) |

## Run it end to end

One command runs the stages in order and stops at the first failure:

```console
python run_pipeline.py --list                 # the stages
python run_pipeline.py                        # inventory -> meta (never uploads)
python run_pipeline.py --from plan --to render   # a range
python run_pipeline.py --only render
python run_pipeline.py --to upload            # adds the upload, as a DRY RUN
python run_pipeline.py --to upload --yes-upload   # real upload to YouTube
```

The upload is the only stage that acts outside your machine, so it runs **only when asked** and stays a
simulation without `--yes-upload`. Every stage can also be run on its own, **from any folder**:

```console
python scan/inventory.py && python scan/moments.py && python scan/classify.py
python mm_privacy.py --fetch-model      # once: face-detection model (git-ignored)
python scan/privacy_scan.py             # clean intervals only (resumable, long: run it in the background)
python scan/music_catalog.py --write    # rank the claim-free tracks of public/lib/ (modern, motivating)
python scan/gen_batch.py                # plan N unique montages from the clean intervals
python scan/gen_vo_clone.py             # short voice, cloned
python scan/render_batch.py             # video + voice + music in one pass; needs your claim-free music in public/
python scan/privacy_check.py audit      # frame-by-frame check + audio stream check
python scan/privacy_check.py sheets <id>   # contact sheets: LOOK at them
python scan/privacy_check.py flag <id> 5.3 6.0 --why "cyclist"   # a doubt found while looking: blocks that source, withdraws approval
python scan/privacy_check.py approve <id> --by YOURNAME   # the uploader refuses anything not approved
python scan/make_meta.py                # meta/<id>.json with your signature + hashtags
uv run python upload_short.py "meta/g_*.json" --dry-run    # from the social2shorts folder
```

All stages are **re-runnable**: finished renders, voices and mixes are skipped, so after a failure you simply run
the same command again.

## Tests

```console
pip install -r requirements-dev.txt
python -m pytest tests -q      # no ffmpeg, no network, no YouTube needed
ruff check .
```

## One montage by hand

```console
python viral_cut.py --segments scan/mont/g_pov_00.json \
  --music public/lib/airborne.mp3 --hook "Find your road" --outro "Keep riding" \
  --target 18 --out out/g_pov_00.mp4
```

See the [pipeline](pipeline/index.md) for what each stage reads and writes, and
[Configuration](configuration.md) for the folder layout.
