# Privacy gate

A channel can stay **anonymous** only if nothing in the footage identifies the rider: no visible face (not even
through an open or transparent visor) and no bystander close by. Raw footage often shows both: a camera on a pole
films the rider's face, and group rides or meet-ups show people. So **nothing is planned, rendered or uploaded
without passing this gate**, and in doubt the answer is no: fewer videos, but safe ones.

## The rule

A frame is **refused** when it contains:

| Refused | Detail (`mm_privacy.py`) |
|---|---|
| a visible face | detector score >= 0.55 and width >= 3 % of the frame width (about 32 px on a 1080 px frame; a smaller face cannot identify anyone) |
| a second person | two or more distinct people, each at least 5 % of the frame height |

Every frame is analysed at a **fixed 540x960 resolution** (the pool scan and the final audit see the same pixels), and
thresholds are fractions of the frame. Weaker face detections were checked on crops: below 0.55 they are hands,
dashboards, mirrors, foliage, tail lights, so they are ignored; the **human review** of the contact sheets covers
what is left (a closed full-face helmet can still be flagged by a reflection on the visor, which costs some good
footage and is accepted). Also look for readable licence plates, names and location stickers burnt into the source.

## No car, ever

A motorcycle channel must not show a car interior (steering wheel, dashboard, windscreen) under a title about two
wheels. `mm_scene.py` asks CLIP (zero-shot) whether a frame was shot from inside a car; above 0.30 the frame is
refused like a face. On frames reviewed by hand it found **10 car shots out of 10** and wrongly flagged 2 of 37
motorcycle frames: losing a motorcycle shot is better than keeping a car shot. `python scan/privacy_scan.py --cars`
re-filters an existing pool; the scan and the final audit apply the same rule.

## Raw footage: `PRIVATE/row/`

`scan/raw_audit.py` audits the **original rushes** (not the montages): one key frame every 2 s over the whole frame,
visible faces and a second person. A rush is flagged when a confident face appears on at least 2 frames (or one very
sharp face), or when 2 or more people appear on at least 3 frames. A rush with **a single detection** (one face of
moderate confidence, or 2 people on 1 or 2 frames) is not flagged but is **in doubt**; the rule is strict, so it is
isolated too, in its own sub-folder `PRIVATE/row/doute/`, and many of those are harmless (people far away, a reflection,
foliage). `move` then **moves, never copies or deletes**, both tiers into `PRIVATE/row/<source>/` and
`PRIVATE/row/doute/<source>/` (a same-volume rename: no extra disk space; `--sure-only` leaves the doubtful ones in
place) and writes `PRIVATE/row/_moved.json` and a thumbnail page `PRIVATE/row/index.html` with one section per tier,
to check by hand before deleting; `restore` (or `restore name.mp4`) puts everything back. The planner never draws from a
moved rush.

Result on the owner's footage (10 November): 1,645 rushes analysed, **736 flagged (155 GB) and 315 in doubt (32 GB)
moved**, 594 with no detection left in place. A sample of the doubtful tier showed about a third with real people in
view (a woman on a beach, a child, passengers in a car), the rest harmless: the cost of the strict rule is a longer manual
check, not lost footage, since nothing is deleted.

The same day, at the owner's request and to free disk space, the clips with a **confident face** (639, 145 GB, all in
`PRIVATE/row/`) and the clips with **no motorcycle** in either repository (388, 26.5 GB; CLIP motorcycle score under 0.2
and a non-motorcycle category, a random sample of 40 checked by eye) were **deleted permanently**, together with the
rejected montage renders. Every deleted file is listed with its reason in `PRIVATE/_suppressions_<date>.json`; their
entries in `PRIVATE/row/_moved.json` are marked `deleted` and the planner never plans them. What is left in
`PRIVATE/row/` (70 clips with several people and no face, 210 in doubt) still waits for the owner's manual check.

## Three layers

1. **Pool scan**, `scan/privacy_scan.py`. Decodes every candidate window with the **exact framing of the montage**
   (centre crop, 540x960) at 3 images per second and records the **clean intervals** (at least 2 s, with a 0.4 s
   margin around every refused frame) in `scan/privacy_pool.json`. It is resumable and slow (hours of footage), so run
   it in the background; `--reverse --out <file>` starts a second worker from the end of the list.
2. **Planner**, `scan/gen_batch.py`. Draws **only** from clean intervals (trimmed by 0.15 s at each end) minus the
   ranges listed in `scan/privacy_blocklist.json`. A clip that was never analysed is never used, and the planner
   refuses to run without the pool.
3. **Final check**, `scan/privacy_check.py`:

| Command | What it does |
|---|---|
| `audit [ids]` | analyses the stitched footage (without text or grade) at 10 images per second, checks the audio stream (rate, AAC packets, equal audio and video durations), writes `meta/_privacy/<id>.json`. Refused frames are mapped back to their **source clip and time** and added to the blocklist, so the next plan avoids them |
| `sheets <id>...` | contact sheets of the **final** video, one image every 0.8 s. **Look at them**: detectors miss reflections, partial faces and anything that needs judgement (a bystander's gender, a face in a mirror) |
| `flag <id> <from> <to> --why "text"` | a doubt you spotted **while reviewing** (seconds of the montage): the matching **source clip and time** are blocked for the next plans (`scan/privacy_blocklist.json`), and the audit and approval of that montage are withdrawn. The loop is: `flag`, then `gen_batch.py` (only that montage's lane changes), `render_batch.py`, `audit`, new review |
| `approve <id>... --by NAME` | records the approval **only if the audit passed and the file has not changed** |
| `quarantine <id>...` | **moves** the video, its voice, plan and metadata to `PRIVATE/<date>/`; nothing is deleted |
| `status` | approved / passed but not approved / failed, per montage |

`upload_short.py` **refuses** any montage that is not approved, or that changed after its approval. There is no
bypass flag.

## What the reviewer looks for

The automatic check cannot see everything. On a first batch of reviewed montages the human review still found, beyond
faces: a **pedestrian or cyclist** near the bike (no face visible, so the detector said nothing), **another
person's legs** on the bike, a **visor so tinted that skin showed through**, a **readable plate** on a motorcycle, and
**Instagram stickers** burnt into the source clips. Each one is flagged with `flag`.

## Detectors

Both run locally: **YuNet** (OpenCV) for faces and **RT-DETR** (`transformers`) for people. The face model is
downloaded once with `python mm_privacy.py --fetch-model` into `models/` (git-ignored). The people detector comes
from the Hugging Face hub on first use.

## What stays on your machine

`models/`, `PRIVATE/`, `scan/privacy_pool.json`, `scan/privacy_blocklist.json`, `meta/_privacy*` and `out/_cat/` are all
git-ignored: the repository holds only the code.

## Limits

- Detectors are not perfect: very small or blurred faces, faces in reflections and night footage can slip through
  the automatic check. That is why approval requires a **human look** at the contact sheets.
- A face that is not the rider's is refused as well: a detector cannot tell whose face it is.
