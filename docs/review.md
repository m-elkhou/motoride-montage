# Architecture review

Review of the repository as published on **2026-11-09**, covering the scan, planning, rendering, voice and
upload stages and the Remotion path. Findings come from **reading the code**. The behaviours marked
**confirmed** were also seen failing or working during real runs on the author's footage; the rest were not
exercised against fresh data.

## Verdict

The pipeline is **coherent and produces results**: 26 unique montages were generated, rendered, voiced and
queued for upload in one session. The design (file-based stages, pre-selected moments, zero clip reuse,
claim-free music) is sound and worth keeping.

What holds it back from being a reusable tool is **portability and operability**, not the algorithm:
hard-coded paths, an implicit stage order, one missing step, a few non-idempotent or destructive scripts, and
no tests.

## Strengths

| | |
|---|---|
| Stage isolation | every stage reads and writes plain files, so any stage can be re-run or inspected alone |
| Pre-selected moments | `--segments` decouples *choosing* from *cutting*, making renders fast and deterministic |
| Zero reuse | a global `used` set prevents the same clip appearing in two montages |
| Quality gates | moto score, window score, brightness and distinct-clip thresholds filter weak material early |
| Rights-aware | claim-free music only; perceptual-hash filter against already-published clips |
| Resumable scan | `moments.py` appends one JSON line per clip and resumes after an interruption |
| Hang protection | renders have a timeout after a real ffmpeg hang (**confirmed**) |
| Robust upload loop | resumable chunks, quota retry, network retry, scheduled `publishAt` (**confirmed**) |

## Findings

Severity: **P1** fix before others reuse it · **P2** fix soon · **P3** polish.

### P1

| ID | Finding | Evidence | Fix |
|---|---|---|---|
| R1 | **Hard-coded absolute paths** (`C:/workdir/...`, `C:/Users/<name>/...`, `C:/ffmpeg/bin`, a separate venv) in about 14 files. The repository cannot run elsewhere. (The one occurrence of a Windows user name was already replaced by `Path.home()`.) | `grep` over `*.py`, `*.ps1` | one `paths` module reading a git-ignored local file and environment variables, with defaults relative to the repo |
| R2 | **Missing step: manifest → `meta/*.json`.** `gen_batch.py` writes the manifest, `upload_short.py` needs meta files, and no script converts one into the other. It was done by hand once. | no writer of `meta/` in the repo | add `scan/make_meta.py` (skip existing files unless `--force`) |
| R3 | **`render_batch.py` kills every ffmpeg on the machine** (`taskkill /IM ffmpeg.exe /F`) after a timeout. A concurrent job elsewhere is destroyed. (**confirmed**: another job's ffmpeg was in the way during a hang.) | `render_batch.py:16` | run ffmpeg as a child with `subprocess.run(timeout=)` / process group and kill only that process tree |
| R4 | **`overlay_vo.py` is not idempotent.** It replaces `out/<id>.mp4` in place; a second run mixes the voice twice. | `overlay_vo.py` (`shutil.move(tmp, vid)`) | write to `out_voiced/` or keep a marker file per id |
| R5 | **Upload results written only at the end.** `done` is dumped after the loop, so a crash or kill loses every id uploaded so far; a bad meta file stops the whole batch (`assert` outside `try`); the catch-all `except (..., Exception)` hides real bugs. | `upload_short.py:21,39,44` | append each success to the results file immediately; validate all metas up front; narrow the exceptions |
| R6 | **Hidden dependency on social2shorts** (credentials, token path, duplicate store) is declared nowhere; the uploader only works under `uv run` from the other project. | `upload_short.py:10-11,18` | document it (done) and, better, make the sibling path and import explicit and testable |

### P2

| ID | Finding | Fix |
|---|---|---|
| R7 | **Implicit stage order**, relative paths that require the repo root as working directory, no orchestrator. | a small `run_pipeline.py` or Makefile with named stages and a `--from/--to` |
| R8 | **Three voice generators** with incompatible outputs (`.mp3` edge-tts vs `.wav` Chatterbox) and overlapping roles. | keep one generator behind a common interface, archive the rest |
| R9 | **Duplicate / obsolete scripts**: `prune_render.py` is superseded by `rerender_phonk.py`; exclusion lists differ between `build_montages.py` and `gen_batch.py`. | delete or move to `legacy/`; share one exclusion source |
| R10 | **Two montage engines**: social2shorts has its own `montage` package; this repository has `viral_cut.py`. Same job, two code paths, two sets of bugs. | decide a home for the engine and share it |
| R11 | **`containsSyntheticMedia` hard-coded `false`** while a text-to-speech voice is mixed in. | read it from the meta file; re-check YouTube's current disclosure rules |
| R12 | **`classify.py`** writes a checkpoint it never reloads, forces `-hwaccel cuda`, has no timeout and ignores ffmpeg's return code. **`moments.py`** parses ffmpeg output with a regex and silently yields empty arrays if ffmpeg fails. | reload the checkpoint, check return codes, make CUDA optional |
| R13 | **`check_published.py` caches by file name**, so a replaced file keeps a stale hash. | key by size + mtime or content hash |
| R14 | **Inline editorial data**: personal-footage dates (`EXCL_DATE`), hooks, titles and the schedule start date live inside `gen_batch.py`. | move to a git-ignored `copy.toml` / `config.toml`; ship a sample |
| R15 | **No tests and no CI** beyond the docs build. The beat grid, window picking and manifest generation are pure functions that are easy to test. | add `pytest` for `music_grid`, `best_window`, `gen_batch` invariants (no reused clip) |

### P3

| ID | Finding | Fix |
|---|---|---|
| R16 | **Windows-only**: `NUL`, `taskkill`, `C:/Windows/Fonts/arialbd.ttf`, PowerShell launcher. | `os.devnull`, process-tree kill, a font path setting |
| R17 | **Remotion path is disconnected**: nothing in the viral path calls it; `captions` defaults empty; template placeholders remain in `Root.tsx`. | either wire it or move it under `calm/` |
| R18 | **Launcher lists 26 meta files by hand** in `_upload_launch.ps1`. | accept a glob or a folder |
| R19 | **`gen_batch.py` is not seeded**; the "unique clip" guarantee holds per run but not across runs unless old montage files are present. | persist the used-clip set |
| R20 | Style: dense one-line code in `viral_cut.py` and `upload_short.py`, bare `except:`, `tempfile.mktemp`. | lint with `ruff`, use `NamedTemporaryFile` |

## Risks to watch

1. **Cadence depends on the PC being on**: the detached uploader needs the machine awake for up to 30 hours.
2. **Platform rules change**: music claims, upload quotas and disclosure requirements evolve; re-verify before each large batch.
3. **Single source of OAuth truth**: all uploads depend on one token in the sibling project.

## Suggested order

R1 + R2 + R3 + R4 + R5 first (one afternoon, no change in behaviour for the owner thanks to defaults),
then R7 + R15 (an orchestrator and a safety net), then the rest. See the [roadmap](roadmap.md).
