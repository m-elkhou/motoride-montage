# Roadmap

Ordered by value for the effort. IDs refer to the [architecture review](review.md).

## Next: make it reusable

- [ ] **Central paths module** with a git-ignored local override and relative defaults (R1, R16)
- [ ] **`scan/make_meta.py`**: manifest to `meta/*.json`, signature and hashtags always included (R2)
- [ ] **Safe ffmpeg timeout** that kills only its own process tree (R3)
- [ ] **Idempotent voice mix** writing to a separate folder (R4)
- [ ] **Incremental upload results** and up-front validation of all metas (R5)
- [ ] **`containsSyntheticMedia` from the meta file** (R11)

## Then: make it dependable

- [ ] **Orchestrator** `run_pipeline.py` with named stages and `--from/--to` (R7)
- [ ] **Tests** for the beat grid, window selection and manifest invariants, run in CI (R15)
- [ ] **Config file** for themes, copy, schedule and exclusions (R14)
- [ ] Resumable classification, checked ffmpeg return codes (R12)
- [ ] One voice generator, archive the rest (R8); remove duplicate scripts (R9)

## Later: growth

- [ ] Decide where the montage engine lives and share it with social2shorts (R10)
- [ ] Weekly **analytics loop**: hook retention, average view duration and subscribers per Short feed back into
  the hook and music rotation ([Growth plan](growth-plan.md))
- [ ] Multi-language voice and subtitles
- [ ] Wire or retire the Remotion path (R17)
- [ ] Cross-post the same renders to Instagram Reels and TikTok
