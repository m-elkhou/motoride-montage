---
title: Home
hide:
  - navigation
---

# motoride-montage

**motoride-montage** turns hours of raw moto footage into **viral-style YouTube Shorts**: it scans your
rushes, scores the strongest moments, cuts them **on the beat** of claim-free phonk music, adds a hook, a
closing line and a light voice, then uploads everything at the pace YouTube allows.

It is the **montage engine** that sits next to [social2shorts](https://github.com/m-elkhou/social2shorts)
(which handles catalog re-publishing, OAuth and the YouTube client).

## What it does

| Stage | Script | Result |
|---|---|---|
| Inventory | `scan/inventory.py` | list of every clip (size, duration, resolution) |
| Moments | `scan/moments.py` | best 2 s / 4 s windows per clip (motion, sharpness, audio, light) |
| Classification | `scan/classify.py` | zero-shot CLIP tag + "moto score" per clip |
| Planning | `scan/gen_batch.py` | N themed montages, **zero clip reuse**, hooks, titles, schedule |
| Rendering | `scan/render_batch.py` → `viral_cut.py` | 1080x1920, 30 fps, beat-synced, slow-mo on the drop |
| Voice | `scan/gen_vo_edge.py` + `scan/overlay_vo.py` | short neural voice mixed lightly over the music |
| Upload | `upload_short.py` | scheduled, quota-aware YouTube upload |

```mermaid
flowchart LR
    R[Raw clips] --> I[inventory]
    I --> M[moments]
    M --> C[classify<br/>CLIP]
    C --> P[gen_batch<br/>plan]
    P --> V[render_batch<br/>viral_cut.py]
    P --> T[gen_vo_edge<br/>voice]
    V --> O[overlay_vo]
    T --> O
    O --> U[upload_short<br/>YouTube API]
```

## Design principles

- **Moments over beauty.** Views come from the *moment*, not image quality (see [Viral DNA](viral-dna.md)).
- **Claim-free music only.** Trending commercial tracks get Content ID claims through the API; the
  engine uses royalty-free phonk/drift ([Music](pipeline/music.md)).
- **Never republish.** Clips are used once across all montages; published clips are filtered by perceptual hash.
- **Your data stays yours.** Footage, music, tokens and channel data are never committed ([Security](security.md)).

!!! warning "Status"
    This is a working personal tool, published as-is. Paths are Windows-oriented and a few are still
    hard-coded; the [architecture review](review.md) lists every known gap and the planned fixes.
