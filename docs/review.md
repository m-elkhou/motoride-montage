# Architecture review

Review of the repository on **2026-11-09**, covering the scan, planning, rendering, voice and upload stages and
the Remotion path. The findings came from **reading the code**; most were then **fixed the same day**, and each
fix was checked against the author's real data (see [Verification](#verification)).

## Verdict

The pipeline is **coherent and produces results**: 28 unique montages were generated, rendered, voiced and
queued for upload. The design (file-based stages, pre-selected moments, zero clip reuse, claim-free music) is
sound. What held it back from being reusable was **portability and operability**, not the algorithm. Those are
now addressed; two items stay open because they are design decisions, not defects.

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

## Verification

| Check | Result |
|---|---|
| `moments.py` re-scan of a real clip vs the stored result | all 8 measured values identical; a missing file is now reported |
| `gen_batch.py` on the real data | manifest and 28 segment files **identical byte for byte** |
| `make_meta.py` vs the 26 queued metadata files | **26 / 26 identical**, signature included |
| `overlay_vo.py` after migrating markers | second run mixes nothing (`0 OK, 26 already done`); only the 2 new videos were voiced afterwards |
| Process-tree timeout | a test kills a child **and** its grandchild while an unrelated process survives; a negative control shows the test detects orphans; a real hang was killed without touching the running uploader |
| End-to-end render | 1080x1920, 30 fps, H.264 + AAC, 18.0 s, hook and outro text visible |
| Test suite | 34 passed locally; CI runs on Linux and Windows |

## Risks to watch

1. **Cadence depends on the PC being on**: the detached uploader needs the machine awake for up to 30 hours.
2. **Platform rules change**: music claims, upload quotas and disclosure requirements evolve; re-verify before each large batch.
3. **Single source of OAuth truth**: all uploads depend on one token in the sibling project.
4. **ffmpeg upgrades**: a major version can change scheduling behaviour; the render timeout and the failure report are the safety net.

## What is left

See the [roadmap](roadmap.md): the engine-ownership decision (R10), wiring or retiring Remotion (R17), moving the
remaining default copy out of the code (R14), a portable launcher (R16), and the analytics loop.
