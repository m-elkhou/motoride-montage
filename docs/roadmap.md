# Roadmap

Ordered by value for the effort. IDs refer to the [architecture review](review.md).

## Done (2026-11-09)

- [x] Central paths module with a git-ignored local override (R1, R16)
- [x] `scan/make_meta.py`: manifest to `meta/*.json`, signature always included (R2)
- [x] Safe ffmpeg timeout that kills only its own process tree (R3)
- [x] Idempotent voice mix with markers (R4)
- [x] Upload ledger written after each upload, up-front validation (R5, R6)
- [x] `containsSyntheticMedia` from the meta file (R11)
- [x] Orchestrator `run_pipeline.py` (R7); tests and CI on Linux and Windows (R15)
- [x] Editorial settings in `scan/gen_config.json` (R14, partly)
- [x] Resumable classification, checked return codes (R12); one voice generator (R8); duplicates archived (R9)
- [x] Render freeze fixed with a two-pass final encode (R21)

## Next

- [ ] Move the remaining **default copy** (hooks, titles, descriptions) out of the code (R14)
- [ ] A portable launcher replacing the PowerShell script (R16)
- [ ] Lint the dense one-line style in `viral_cut.py` and `upload_short.py` (R20)

## Later: growth

- [ ] Decide where the montage engine lives and share it with social2shorts (R10)
- [ ] Weekly **analytics loop**: hook retention, average view duration and subscribers per Short feed back into
  the hook and music rotation ([Growth plan](growth-plan.md))
- [ ] Multi-language voice and subtitles
- [ ] Wire or retire the Remotion path (R17)
- [ ] Cross-post the same renders to Instagram Reels and TikTok
