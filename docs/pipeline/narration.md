# Narrated montage

A narrated Short is built around a spoken text in the owner's cloned voice, not around a music track: the length
comes from the narration, the shots change on the sentences and on the beat, each word appears as it is spoken, and
the voice sits in front of the music. It is a second path next to the [beat-synced montage](montage.md).

!!! warning "Status on 2026-11-14"
    `narrated_cut.py`, `mm_plates.py` and the cockpit filter of `mm_scene.py` are in the repository and tested. The
    planner, the whole-clip privacy scan, the narration mastering and the audit of the finished video still live
    outside the repository (pilot scripts); bringing them in is on the [TODO](../todo.md).

## What goes in

`narrated_cut.py` renders a **plan** (JSON). Every shot length is a number of frames; their sum is the video.

| Key | Meaning |
|---|---|
| `voice`, `voice_start` | the mastered narration (WAV) and when it starts in the video (seconds) |
| `words` | path of a JSON file with the per-word timings of the narration: `{"dur", "lines": [{"words": [{"w", "a", "b"}]}]}` |
| `music`, `music_offset`, `drop` | optional track, where to start in it, and the video time of its strong beat |
| `shots` | `[{"clip", "src", "frames", "rate", "push", "punch"}]`: source file, start in the source, length in frames, speed, slow zoom, zoom kick on the cut |
| `keywords`, `handle`, `intro_hit` | words shown in the accent colour, the signature of the last seconds, an opening hit |
| `caption` | size of the caption blocks, for example `{"max_words": 2, "max_chars": 13}` (default 3 words, 16 characters) |

```bash
python narrated_cut.py --plan plan.json --out out/name --cache out/_shots
```

`--cache` keeps each cut shot and its plate detections (keyed by source, time, length, speed and zoom): after a
change of a few shots, a second render only redoes those.

| Output | Use |
|---|---|
| `name.mp4` | voice and music: an original sound other creators can reuse |
| `name_voix.mp4` | voice and effects only: add a Shorts catalogue sound in the YouTube app (see [Music](music.md)) |
| `name_proxy.mp4` | the masked shots without text or grade: input of the privacy audit and of the contact sheets |
| `name_plates_masked.jpg`, `name_plates_visible.jpg` | crops of every blurred track and of every track left visible, to review |
| `name_report.json`, `name_captions.ass` | durations, plates per shot (masked and visible tracks, `doubts`), loudness; the subtitle file |

The render refuses a plan whose narration does not end at least 0.3 s before the end of the video, a video longer
than 59.5 s (a Short over one minute with any claim is blocked worldwide), and a music track shorter than the
video needs. Paths in the plan are read from the current folder. The files of an earlier render with the same
name are removed first. With `--no-plates` (a layout trial) everything is written under `name_sans_flou`: such a
render is never published.

## The narration voice

The `voice` file of the plan is prepared before the montage. What the first pilot taught (measures in the
[Handoff](../handoff.md)):

- **Choose each take on its measured quality**, near the speaker's natural pitch and at a steady pace. Preferring
  the deepest of several takes picks the damaged ones: a cloned voice pushed under its natural pitch creaks.
- **No phase-vocoder filter on the voice.** ffmpeg's `rubberband` (pitch or tempo) makes a cloned voice sound
  robotic; `atempo` changes the pace without that damage. A deeper voice comes from the reference recording, not
  from a filter.
- **Light mastering**: a high-pass filter, 2:1 compression, a limiter. Strong equalisation and 4:1 compression
  add to the artificial sound.
- **Same level for every sentence**, and a very faint floor instead of digital silence between sentences.
- **Measure against a real recording of the speaker**, step by step, when the result sounds wrong: nobody on the
  engine's side can hear it.

## Licence plates

The owner's rule is that no plate is readable. `mm_plates.py` finds plates with a small detector (YOLOv9 licence
plate model of the `open-image-models` package, ONNX) and blurs them.

- **Tiles.** A motorcycle plate is 40 to 120 px wide in a 1080x1920 frame and disappears when the whole frame is
  shrunk to the detector's 608 px. The detector therefore runs on overlapping 640 px tiles at full resolution, then
  on the whole frame for close plates.
- **Low threshold.** Confidence 0.12: a false positive costs a small blur, a miss costs a readable plate.
- **Tracks.** Detections are linked over time. A track is masked without a gap (the box is interpolated between two
  detections, because the detector flickers on small plates). In a shot of three seconds or less every mask is
  held from the first frame to the last: a blur that stops before the end of the shot leaves the object sharp on
  the last frames, and reviewers refuse it. In a longer shot the mask is held eight frames before and after, and
  over the whole shot when the object does not move or is present for 40 % of it.
- **Plate or not.** The detector also takes the speedometer, the GPS screen, tank stickers, a logo or a patch of
  sky for plates; blurring them all spoils every handlebar view. `mm_scene.PlateJudge` (CLIP ViT-L/14) compares
  the surroundings of each track with three families of descriptions: a plate on a vehicle, a cockpit part,
  anything else. `mm_scene.must_blur` then decides, in this order: a track made **only** of giant boxes
  (30 % of the width or more: sky, a whole dashboard) is blurred only when CLIP is certain it is a plate (0.95).
  This is the one case where a doubt leaves a track visible: with a score of 0.50 or more it is counted in the
  `doubts` of the report and marked in red on the sheet of visible tracks, to be looked at or the shot replaced. A
  giant box mixed into the track of a smaller one does not decide for it. Then: a tiny box
  (under 38 px, unreadable anyway) always; a small box (under 130 px) passing through the upper half of the frame
  (the road and the horizon) always; otherwise as soon as one sample reaches a plate probability of 0.50. On 158
  tracks of a montage and 100 single-frame detections checked by hand, for boxes of 38 px or more, the real
  plates scored 0.95 or more (one tilted plate 0.84) and the motorcycle's own parts (mirror, switches, logo,
  speedometer) 0.45 or less. The smaller ViT-B/32 confuses a speedometer seen through the windscreen with a
  plate (13 large confusions out of 54 cockpit parts, against 3).
- **Edges and close plates.** A mask that comes within 6 % of a frame edge is extended to that edge: a plate
  half out of frame is detected too short and the part sticking out of the blur stays readable. A shot with a
  close, large plate (200 px or more) should be replaced by the planner rather than trusted to the blur.
- **Review.** The two crop sheets show what was blurred and what was left visible. A detector does not see
  everything: reading the contact sheets stays mandatory.

The detector has its own environment (`onnxruntime`, no torch). Point the engine at it with `MM_PLATES_PYTHON` or
`plates_python` in `local_paths.json`:

```bash
uv venv venv_plates --python 3.12
uv pip install --python venv_plates/Scripts/python.exe "open-image-models[onnx-directml]"   # or [onnx] on CPU
venv_plates/Scripts/python.exe mm_plates.py probe frame.jpg --out probe/      # annotated image, to tune thresholds
```

`narrated_cut.py` itself runs in the render environment (OpenCV, soundfile, torch and open_clip for the plate
judge) and calls the detector through `MM_PLATES_PYTHON`. Boxes whose size differs by more than two times are
never merged or linked (a giant false positive must not absorb the plate it covers), a side of a mask that lies
on the frame border is not feathered, and cached detections are tied to the detector's settings.

The code of `open-image-models` is MIT; the licence of its weights is not stated on its pages. The weights are
downloaded at first use and are not redistributed here.

## Word-by-word captions

Words are grouped in short blocks (three words and 16 characters by default), never across a sentence end. A block stays on
screen while it is spoken; each word appears at its own time (words not yet spoken are transparent, so the line does
not move), the word being spoken is yellow and the keywords are orange. The font size follows the block length so
the text stays inside 800 px, clear of the buttons of the Shorts player, for blocks of 18 characters or fewer
(the size never goes under 62 points: keep `max_chars` at 18 or less). The captions are an ASS file rendered by
ffmpeg (`ass` filter), with the fonts Montserrat Black and ExtraBold installed on the machine.

## Sound

The narration arrives already mastered and is brought to a fixed speech level before mixing, so the final
normalisation stays linear. The music is set 6 dB under the voice in the running passage, ducked while the voice
speaks, and the strong beat is left to rise. A synthesised riser and low hit (no rights involved) mark the
strong beat. Both outputs are normalised in two passes to -14 LUFS, true peak -1 dB.

## Limits

- The whole-clip scan and the planner decide which seconds may be used; `narrated_cut.py` trusts the plan. Never
  feed it a plan made from footage that did not pass the privacy gate.
- Slow motion blends frames (30 fps sources): keep it for wide, slow shots.
- The cut on the strong beat is exact for the track of the plan only. A catalogue sound added in the app is aligned
  by hand.
