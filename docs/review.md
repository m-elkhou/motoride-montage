# Architecture review

Review of the repository on **2026-11-09**, covering the scan, planning, rendering, voice and upload stages and
the Remotion path. The findings came from **reading the code**; most were then **fixed the same day**, and each
fix was checked against the author's real data (see [Verification](#verification)).

## Verdict

The pipeline is **coherent and produces results**: the design (file-based stages, pre-selected moments, zero
clip reuse, claim-free music) is sound. The first review (9 November) found **portability and operability** problems
and they were fixed. A **second review on 10 November**, after the owner pulled most of the scheduled videos,
found three problems that matter more: the footage **showed faces and bystanders** that nothing checked (R25), the
**soundtrack was badly built** (R22, R24) and the **video was shorter than its audio** (R23). Of the 26 uploaded
montages, 18 showed a visible face or left a real doubt, and 12 of the 28 rendered files had a corrupt audio stream.
All four are fixed below; two earlier items stay open because they are design decisions, not defects.

## Strengths

| | |
|---|---|
| Stage isolation | every stage reads and writes plain files, so any stage can be re-run or inspected alone |
| Pre-selected moments | `--segments` decouples *choosing* from *cutting*, making renders fast and deterministic |
| Zero reuse | a global `used` set prevents the same clip appearing in two montages |
| Quality gates | moto score, window score, brightness and distinct-clip thresholds filter weak material early |
| Rights-aware | claim-free music only; perceptual-hash filter against already-published clips |
| Resumable | scan, classification, voice, mix and renders all skip finished work |
| Safe upload loop | validated up front, per-upload ledger, quota and network retry, scheduled `publishAt` |

## Status of the findings

**Fixed** · **Partly** (improved, a remainder is listed) · **Open** (a decision, not a defect).

### P1

| ID | Finding | Status | What changed |
|---|---|---|---|
| R1 | Hard-coded absolute paths in ~14 files | **Fixed** | `mm_paths.py`: environment variable → `local_paths.json` → default. No absolute path left in the code ([Configuration](configuration.md)) |
| R2 | Manifest → `meta/*.json` step missing | **Fixed** | `scan/make_meta.py` (never overwrites, **refuses to run without a signature**) |
| R3 | `render_batch.py` killed every ffmpeg on the machine | **Fixed** | `mm_run.run_tree` kills only the render's own process tree and deletes the partial file |
| R4 | `overlay_vo.py` mixed the voice twice on a re-run | **Fixed** | `out/<id>.voiced` marker holding the file signature; a re-render invalidates it automatically |
| R5 | Upload results written only at the end; bad meta stopped the batch; catch-all `except` | **Fixed** | all metas validated first; ledger written after **each** upload; narrow exception handling |
| R6 | Hidden dependency on social2shorts | **Fixed** | explicit import with a clear message, `MM_S2S_ROOT`, documented |
| R22 | Corrupt audio stream in 12 of 28 files, 96 kHz audio in all | **Fixed** | the soundtrack is built once from the original files by `mm_audio.py`, AAC 48 kHz; every render is checked (packets against duration) |
| R23 | Video 1-3 s shorter than its audio (the outro text barely showed) | **Fixed** | beat grid extended at the tempo; the final length is the real length of the video; the check requires equal durations |
| R24 | Voice about 6 dB under the music, mix peaking at -0.4 dBFS | **Fixed** | voice treated and fitted to -13.5 LUFS, music ducked under it, two-pass loudnorm to -14 LUFS / -1 dBTP |
| R25 | Visible faces and bystanders in the footage, never checked | **Fixed** | [privacy gate](pipeline/privacy.md): clean-interval pool, planner limited to it, frame-by-frame audit, human review, approval required to upload |

### P2

| ID | Finding | Status | What changed |
|---|---|---|---|
| R7 | Implicit stage order, relative paths | **Fixed** | `run_pipeline.py` (`--from/--to/--only`, upload only on request and dry-run by default); scripts run from any folder |
| R8 | Three voice generators, incompatible outputs | **Fixed** | one generator in the pipeline (`gen_vo_edge.py`, resumable, retries); the cloned-voice script moved to `scan/legacy/` |
| R9 | Duplicate scripts, diverging exclusion lists | **Fixed** | obsolete scripts in `scan/legacy/`; one `exclude_dates` list shared by `gen_batch.py` and `build_montages.py` |
| R10 | Two montage engines (social2shorts and `viral_cut.py`) | **Open** | decision needed on where the engine lives |
| R11 | `containsSyntheticMedia` hard-coded `false` | **Fixed** | read from the meta file |
| R12 | `classify.py` and `moments.py` fragile | **Fixed** | checkpoint reloaded, CUDA only if available, return codes checked, timeouts, failures recorded instead of empty arrays |
| R13 | Published-hash cache keyed by file name | **Fixed** | key = name + size + modification date |
| R14 | Editorial data inline | **Partly** | excluded dates, used montages, schedule, themes and texts now come from `scan/gen_config.json`; the **default** hooks, titles and descriptions remain in the code |
| R15 | No tests, no CI | **Fixed** | 34 tests, ruff, CI on Linux and Windows |

### P3

| ID | Finding | Status | What changed |
|---|---|---|---|
| R16 | Windows-only calls | **Partly** | `os.devnull`, configurable font, process-tree kill that also works on POSIX. Remaining: the PowerShell launcher |
| R17 | Remotion path disconnected | **Open** | kept as the secondary "calm" path and documented as such; wire it or retire it |
| R18 | Launcher listed 26 files by hand | **Fixed** | pattern parameter; the uploader also accepts quoted patterns |
| R19 | `gen_batch.py` used-clip set | **Partly** | the used montages are now configurable (`used_montages`); the planner is already deterministic (verified byte for byte), so there is nothing to seed |
| R20 | Style: bare `except`, `mktemp`, dead imports | **Partly** | bare excepts, `mktemp` and unused imports/variables fixed; the dense one-line style is left, only real errors are enforced |

### R21: renders that never finished (found while fixing)

Two montages (`g_pov_05`, `g_pov_07`) had been abandoned after repeated hangs. **Root cause**, found by bisecting
the final ffmpeg command: encoding video and audio in **one filter graph** froze deterministically (same frame,
same output size every time) with ffmpeg 9.0.2. Encoding the video alone takes about 10 s, so the filters were
not at fault; `-t`, the muxing queue size and filter threads made no difference.

**Fix**: the final step now runs in two passes: video only, then audio mixed in while **copying** the video
(about 1 s). The output is the same (same codecs, size, hook and outro text) and both montages now render in
seconds. `viral_cut.py` also stopped leaving ~5 GB of temporary folders behind.

### R22-R25: found on 10 November

- **R22 and R23, the audio.** `ffprobe -count_packets` showed AAC streams holding 1.3 to 3.8 times more packets than
  their declared duration (a player then skips pieces of voice and music), always at 96 kHz because `loudnorm`
  outputs 192 kHz and nothing resampled it. Every video track was also shorter than the 18 s audio. The soundtrack is
  now built in **one pass** and `mm_audio.stream_problems` rejects any render with a wrong rate, an incoherent
  packet count or unequal durations.
- **R24, the voice.** The music was normalised to -14 LUFS first, then the voice added at +2.6 dB on top: the voice
  sat well under the music and the sum peaked at -0.4 dBFS. See [Voice](pipeline/voice.md) for the new chain.
- **R25, the footage.** A camera on a pole films the rider's face through open or transparent visors; group rides
  show many people. Automatic detection plus visual review found a visible face in most montages. The planner now
  draws only from intervals cleared frame by frame, and a montage cannot be uploaded until it is audited, reviewed and
  approved. The first generation of montages was **moved to `PRIVATE/`** (nothing deleted). The review loop (flag, replan one
  lane, re-render, audit, review again) found what the detectors cannot: a pedestrian or cyclist with no visible face,
  another person's legs on the bike, skin showing through a tinted visor, a readable motorcycle plate or sticker,
  Instagram stickers and Arabic quotes burnt into the source clips, a name written on a helmet, a reflection in a teapot.

### R26-R31: found on 10 November, second round

The owner watched the approved montages and found five problems that the first round had not covered.

- **R26, the car.** Some shots were filmed from inside a car (windscreen, dashboard, mirror) under a title promising
  two wheels. A face or person detector cannot see a cabin. A zero-shot CLIP classifier (`mm_scene.py`: car interior
  against motorcycle prompts, threshold 0.30) now filters the clean pool, the planner's inputs and the final audit, and
  the reviewers look for it too. On a sample of 37 motorcycle frames it wrongly refused 2: accepted on purpose, because
  losing a motorcycle shot is better than keeping a car shot. The pool lost about 30 % of its clean seconds.
- **R27, the voice.** The neural voice was robotic, too fast and not the owner's. `scan/gen_vo_clone.py` now clones the
  owner's voice (Chatterbox Multilingual from a reference recording). A generative model's pace varies from 1 to 4 words
  per second on the same sentence, so each line gets several candidates, scored on the **final result**: pace against a
  calm target of 2.1 words per second, the slowdown that would be needed (a voice stretched by 30 % sounds artificial),
  silence inside the sentence, and **speaker similarity** to the reference (the model's own voice-encoder embedding,
  target 0.90). Measured similarity of the first generation: 0.81 to 0.91, mean 0.88. `--refine` redoes the weak lines
  with 12 candidates.
- **R28, the description.** Every upload description must be detailed (at least 150 characters over two paragraphs), then
  the signature that carries the owner's Instagram, then a **last line made only of hashtags**. The rule is enforced by
  both repositories, by `mm_description.py` in this one and by `description_problems` in social2shorts: an upload that
  breaks it is refused. The signature comes from the local configuration, never from the code.
- **R29, the raw originals.** `scan/raw_audit.py` audits the original rushes and **moves** (never copies, never deletes)
  those that show a face or several people to `PRIVATE/row/`, plus the ones with a single detection to `PRIVATE/row/doute/`,
  with a restore command and a thumbnail page. See [Privacy](pipeline/privacy.md).
- **R30, the music.** The soundtrack had to be modern and motivating, and still claim-free. The YouTube Audio Library
  tracks are ranked by level, drop strength and mood; dark, melancholic or angry moods are dropped. See
  [Music](pipeline/music.md).
- **R31, the planner and the review.** Three independent reviewers rejected all five montages of the first batch for
  things no detector had flagged: other riders far ahead on the road, two readable licence plates, a paper insurance
  certificate taped on a mudguard, a sticker carrying the channel handle, a poster printing family faces, a beach seen
  through a windscreen, a shot from inside a funicular. They also found that the planner played the **same shot twice in
  a row**: 103 rushes exist under two paths (`inbox` and `camera_roll`, same name and size) and were counted as two clips.
  The fixes: identical copies are planned once and share their blocked ranges; a source with black bars inside its own
  frame is excluded (`scan/letterbox_scan.py`); a POV montage with a motionless shot fails the audit and the whole source
  segment is blocked (`STATIC_MIN`); lanes are sized in **verified seconds** (`lane_seconds`) and a montage that keeps fewer
  than `min_seconds` after the blocklist is dropped rather than padded. The honest consequence: once the duplicates, the
  raw originals moved, the cars and the reviewers' findings are removed, the footage supports far fewer montages.

### R32: the voice repeated itself and was cut (found by the owner, 10 November)

The owner listened to the montages: phrases said twice and voices cut short. Whisper confirmed it on the files:
"Wait for the turn. Wait for the turn.", "Which bike would you pick? ... would you pick" cut in the middle of a word,
"This road hits different and". The root cause was in the selection itself: takes were chosen on **duration only**
(closest to a slow target of 2.1 words per second), and a sentence said twice lasts about as long as that target, so the
rule **favoured** the faulty takes; when the model runs past the sentence, its own analyser forces the end mid-word,
hence the cut. Nothing listened to what was said. Every take is now **re-listened** (`mm_voicecheck.py`: repetition
warning of the model, cut signal, exact words heard by Whisper, speech resumed after the sentence), a line with no valid take is
refused, the slowdown is capped at 15 %, and the audit re-listens to the voice file and to the final mix. See
[Voice](pipeline/voice.md).

## Verification

| Check | Result |
|---|---|
| `moments.py` re-scan of a real clip vs the stored result | all 8 measured values identical; a missing file is now reported |
| `gen_batch.py` on the real data | manifest and 28 segment files **identical byte for byte** |
| `make_meta.py` vs the 26 queued metadata files | **26 / 26 identical**, signature included |
| `overlay_vo.py` after migrating markers | second run mixes nothing (`0 OK, 26 already done`); only the 2 new videos were voiced afterwards |
| Process-tree timeout | a test kills a child **and** its grandchild while an unrelated process survives; a negative control shows the test detects orphans; a real hang was killed without touching the running uploader |
| End-to-end render | 1080x1920, 30 fps, H.264 + AAC, 18.0 s, hook and outro text visible |
| Audio stream of the 28 first montages | 12 corrupt (1.27 to 3.76 times too many AAC packets), 28 at 96 kHz, 28 with video shorter than audio |
| Face audit of the 26 uploaded montages | 18 with a visible face or a real doubt (confirmed on crops), 2 with a corrupt stream, 6 already deleted by the owner |
| Clean-footage pool | 550 clips analysed at 3 images per second; 312 have no clean passage at all, 238 have some (326 intervals); 80 more source ranges were blocked by the audit and the human review |
| New montages (first round, withdrawn the same day: see the second round) | 16 planned from the pool; **7 survive** the audit (10 images per second), the review of contact sheets (every 0.8 s, three independent AI reviewers plus zooms) and the stream check; the others lost their lanes to blocked ranges and were moved to `PRIVATE/` |
| New soundtrack | 48 kHz, packets ratio 1.00, -14.0 LUFS, voice about 9 dB over the ducked music in the speech band |
| Raw originals (second round) | 1,645 rushes audited at one key frame per 2 s; 736 flagged (155 GB) and 315 in doubt (32 GB) **moved**, not copied, to `PRIVATE/row/`: originals gone from their place, sizes identical to the audit, no extra disk space used, 594 left |
| Cloned voice | 23 hook lines; pace 1.8 to 2.5 words per second (mean 2.1), 6 slowed by at most 30 %; speaker similarity to the reference recording 0.86 to 0.92 (mean 0.89) |
| Second batch | 5 montages: audit 4 PASS and 1 FAIL, 5 PASS after replanning; three independent reviewers (contact sheets, half-step frames, dense sheets every 0.25 s) **rejected all 5** |
| Third batch | 2 montages rebuilt (identical copies planned once, black bars and static shots excluded): audit PASS, but the same three reviewers rejected both: other riders ahead, people at a fuel station and a car park, a person reflected in a visor, and a shot taken from a car that the CLIP filter had missed (a door mirror in the corner). What is left is 34 s of POV and 16 s of bikes, next to windows already rejected: **no montage is approved** |
| Voice re-listening (R32) | 12 of the 23 cached voices were faulty and set aside; regenerated with the validation, **22 of 22 hooks validated** after up to three rounds (about 100 takes refused for a repetition, a cut end, extra words or speech resumed after the sentence); an independent re-check of the whole cache: 22 of 22; 22 voice-plus-music previews re-listened in the mix: 22 of 22 |
| Test suite | unit tests for the privacy rules, the audio checks, the upload gate and the planner; CI runs on Linux and Windows |

## Risks to watch

1. **Cadence depends on the PC being on**: the detached uploader needs the machine awake for up to 30 hours.
2. **Platform rules change**: music claims, upload quotas and disclosure requirements evolve; re-verify before each large batch.
3. **Single source of OAuth truth**: all uploads depend on one token in the sibling project.
4. **ffmpeg upgrades**: a major version can change scheduling behaviour; the render timeout and the failure report are the safety net.

## What is left

See the [roadmap](roadmap.md): the engine-ownership decision (R10), wiring or retiring Remotion (R17), moving the
remaining default copy out of the code (R14), a portable launcher (R16), and the analytics loop.
