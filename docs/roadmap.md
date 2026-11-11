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

## Done (2026-11-10)

- [x] Privacy gate: clean-interval pool, planner limited to it, frame-by-frame audit, human review, upload refused
  unless approved, quarantine in `PRIVATE/` (R25)
- [x] Soundtrack rebuilt in one pass with a treated voice, ducked music, 48 kHz and a stream check (R22, R23, R24)
- [x] Second round: no shot from inside a car (CLIP filter in the pool and the audit), the owner's **cloned voice** scored
  on pace and speaker similarity, original rushes with a face or several people **moved** to `PRIVATE/row/`, strict
  description rule in both repositories, modern motivating music ranked by mood (R26-R30)
- [x] Planner: lanes sized in verified seconds, identical copies of a rush planned once, black-bar sources excluded,
  static POV shots refused by the audit (R31)

## Next

- [ ] **More safe footage.** After the strict review only a handful of montages survive: most of the clean pool was
  consumed by other people, plates and cars. Two ways to widen it without relaxing a rule: score more windows of the
  545 unique rushes that have no detection at all (the pool only holds each rush's top four windows), and add a
  scenery theme (roads and landscapes without a bike) to fill POV montages
- [ ] **Catch what the reviewers catch.** The automatic gate misses a rider far ahead (under 5 % of the frame height),
  readable plates, stickers and printed faces. A lower person-height threshold and a plate detector would stop the
  review loop from rejecting the same footage again and again
- [ ] Check by hand what is left in `PRIVATE/row/` after the deletion of 10 November (70 clips with several people,
  210 in doubt): restore the harmless ones with `python scan/raw_audit.py restore name.mp4`, delete the others
- [ ] Re-scan only the windows refused for a **weak** detection with a second opinion (the conservative rule loses
  some clean footage to false positives on foliage and rocks)
- [ ] Audit the footage the channel already published with the same gate

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
