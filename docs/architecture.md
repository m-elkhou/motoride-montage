# Architecture

## Shape of the system

motoride-montage is a **file-based batch pipeline**. There is no server, database or long-running process.
Every stage is a standalone script that reads files from the previous stage and writes files for the next one,
which makes each stage re-runnable and easy to inspect, and also means the order is implicit
(see the [review](review.md)).

```mermaid
flowchart TB
    subgraph Inputs["Inputs (never committed)"]
        CL[Raw clips<br/>phone / action cam]
        MU[public/*.mp3<br/>claim-free music]
    end

    subgraph Scan["scan/ : analysis"]
        INV[inventory.py] --> MOM[moments.py]
        MOM --> CLS[classify.py<br/>CLIP]
        CHK[check_published.py<br/>pHash filter]
    end

    subgraph Plan["Planning"]
        GEN[gen_batch.py] --> MAN[(batch_manifest.json<br/>mont/g_*.json)]
    end

    subgraph Render["Rendering"]
        RB[render_batch.py] --> VC[viral_cut.py<br/>librosa + ffmpeg]
        VO[gen_vo_clone.py] --> RB
        PS[privacy_scan.py] --> GEN
        RB --> CK[privacy_check.py<br/>audit + approve]
    end

    subgraph Publish["Publishing"]
        UP[upload_short.py]
    end

    S2S[[social2shorts<br/>OAuth, YouTube client,<br/>duplicate store]]

    CL --> INV
    CLS --> GEN
    CHK -.-> GEN
    MAN --> RB
    MAN --> VO
    MU --> VC
    VC --> OV
    OV --> UP
    S2S -. get_credentials .-> UP
    S2S -. hashes .-> CHK
    UP --> YT[(YouTube)]
```

## Layers

| Layer | Code | Responsibility |
|---|---|---|
| Analysis | `scan/inventory.py`, `moments.py`, `classify.py`, `check_published.py` | turn footage into scored, tagged moments |
| Planning | `scan/gen_batch.py` | choose unique clips, copy, music and a publication schedule |
| Rendering | `viral_cut.py`, `scan/render_batch.py` | beat-synced cut, text, master |
| Audio | `scan/gen_vo_clone.py`, `mm_voicecheck.py`, `mm_audio.py` | the owner's cloned voice, every take re-listened by Whisper, treated and mixed with the music in one pass |
| Scene and copy rules | `mm_scene.py`, `mm_description.py` | no car shots; strict description (detailed, signature, hashtags last) |
| Privacy gate | `mm_privacy.py`, `scan/privacy_scan.py`, `scan/privacy_check.py` | no visible face, no bystander; nothing is uploaded unapproved |
| Publishing | `upload_short.py`, `scan/_upload_launch.ps1` | quota-aware scheduled upload |
| Metadata | `scan/make_meta.py` | `meta/<id>.json` with signature and hashtags |
| Orchestration | `run_pipeline.py` | named stages, `--from/--to/--only`, upload only on request |
| Shared | `mm_paths.py`, `mm_run.py`, `mm_config.py` | paths and tools, safe process runner, editorial config |
| Calm path | `src/`, `make_one.py`, `gen_batch_vo.py` | Remotion narrated renderer (secondary) |

## Contracts between stages

The JSON files are the interfaces:

| File | Producer | Consumers | Key fields |
|---|---|---|---|
| `scan/moments.jsonl` | `moments.py` | `classify.py`, `gen_batch.py` | `path`, `name`, `top4[{t,score}]`, `mean_bright`, `ok` |
| `scan/clip_tags.json` | `classify.py` | `gen_batch.py` | per path: `top`, `moto` |
| `scan/mont/<id>.json` | `gen_batch.py` | `viral_cut.py` | `[{clip,start,len,score}]` |
| `scan/batch_manifest.json` | `gen_batch.py` | `render_batch.py`, `gen_vo_clone.py` | `id,theme,music,hook,outro,title,tags,target,publishAt` |
| `meta/<id>.json` | `make_meta.py` | `upload_short.py` | `video,title,description,tags,categoryId,lang,privacy,publishAt` |

## Boundary with social2shorts

The two projects are **sibling repositories** with a one-way dependency: `motoride-montage` imports
`social2shorts.publish.youtube.get_credentials` and reads its `secrets/` and duplicate store.
social2shorts never imports this repository. Keep it that way: the OAuth token and the YouTube client live in
one place.

## Operating model

- **Every stage is re-runnable**: renders skip valid outputs, the voice is regenerated only when the hook changes, a render is redone when its plan, voice, music or code is newer, `moments.py` and `classify.py` resume, `make_meta.py` never overwrites, the uploader keeps a ledger.
- **Timeouts everywhere**: every ffmpeg call is bounded; a render that exceeds its timeout has **its own process tree**
  killed (never other jobs) and its partial file removed.
- **Portable**: paths come from `mm_paths.py` (environment, `local_paths.json`, defaults); only the PowerShell
  launcher is Windows-specific.
- **Unattended uploads**: the PowerShell launcher starts `upload_short.py` detached so it survives the
  terminal closing; it retries on quota limits for up to 30 h. The PC must stay on.
