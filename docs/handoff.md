# Handoff

Where the project stands, for whoever picks it up next. Updated 2026-11-16.

The next working session has a ready-made brief: [Next session](next-session.md).

## State

- **Nothing is approved for upload through the engine.** One narrated pilot was sent by hand as a private video
  on 2026-11-16, on the owner's instruction, outside the approval gate of `upload_short.py` and with one point
  still open (distant riders): see the pilot section below. Two batches (5, then 2 montages) passed the automatic audit and were all
  rejected by three independent reviewers: other riders far ahead, people at a fuel station and a car park,
  readable plates, a paper on a mudguard, a sticker with the channel name, a reflection of the person filming, a
  shot taken from a car. The planner now has too little verified footage left for a new montage.
- **Anonymity gate** ([Privacy](pipeline/privacy.md)): clean-interval pool (faces, other people, car interior),
  frame-by-frame audit, contact sheets reviewed, approval required by the uploader. Raw originals with a face
  or no motorcycle were deleted on the owner's request on 10 November; the journal is
  `PRIVATE/_suppressions_<date>.json`.
- **Voice** ([Voice](pipeline/voice.md)): the owner's cloned voice, every take re-listened by Whisper
  (`mm_voicecheck.py`): no repetition, no cut word, exactly the intended words. The 22 English hooks of the
  planner are validated (`vo/_cache/`). The audit re-listens to the voice file and the final mix.
- **Descriptions** ([Upload](pipeline/upload.md)): detailed text, signature with the Instagram (from the local
  configuration), hashtags last; the uploader refuses anything else. Same rule in social2shorts.

## Narrated Short, pilot 01 (2026-11-14)

The owner's go of 14 November: make the narrated Shorts, be creative, hide the licence plates. The first one is
built.

- **Uploaded as a PRIVATE video on 2026-11-16** (owner: "open YouTube Studio and upload pilote01_voix.mp4"):
  the voice-only file (its link is kept in the owner's local notes), sent through the signed-in Studio (not the API),
  with the title and description of `meta_p01.md`, language French, not made for kids. Studio's copyright and
  community-guideline checks found no problem. The "AI use" question of the form is left unanswered: it is the
  owner's declaration (YouTube's help lists "cloning one's own voice to create voice overs" among the cases that
  need no disclosure). **Publishing it still needs the owner's go**, and the open point on distant riders below is
  not decided.
- **Music for it** (owner, 2026-11-16: pop, rap or jazz "from free musicians" of YouTube): the list of the YouTube
  Audio Library is in `C:\workdir\_s2s_cb\channel\musiques_youtube\` ([Music](pipeline/music.md)). The owner picks;
  nothing has been added to the video.

- **Files**: `C:\workdir\_s2s_cb\pilot01\out\pilote01.mp4` (voice over the library track "Electro Fight": an original sound),
  `pilote01_voix.mp4` (voice alone, for a catalogue sound added in the YouTube app), `pilote01_proxy.mp4` (masked
  shots without text, input of the audit), the plate crop sheets, the report. Title, description and text:
  `C:\workdir\_s2s_cb\pilot01\meta_p01.md`. Contact sheets: `C:\workdir\_s2s_cb\pilot01\audit_p01\`.
- **Text**: an original French monologue of 95 words in 11 lines, second person. Each line is generated four
  times by VoxCPM2 (the 10-second reference recording and its transcript as a prompt) and transcribed by Whisper;
  only takes with exactly the intended words are kept. The narration lasts 33.5 s; the finished file is
  transcribed again and matches the text word for word.
- **What the first run taught**:
    - After every gate, the pool of the repository held 38 s of usable footage (it only scores three 5-second
      windows per clip). Scanning the eligible clips from end to end gives **21 minutes** of clean intervals on
      157 clips (36 minutes of computing).
    - VoxCPM2 leaves about half a second of breath or leftover sound before each sentence, and Whisper's word
      times drift by 0.1 to 0.6 s at sentence starts. The takes are now cut on speech and the words timed by
      forced alignment (torchaudio `MMS_FA`).
    - The scan at 3 images per second lets refusals through between two samples: the planner checks each chosen
      extract at 10 images per second before keeping it, and the audit of the finished video sends any remaining
      refusal back to the planner as a refused range. A refusal is never excused: the extract is replaced.
    - The face detector fires above its threshold on handlebar switches, a brake disc, and on a blurred patch.
    - What the detectors missed and a look at the storyboard caught: a shot filmed from inside a car (the top of the
      dashboard at the bottom of the frame: the car filter gave it 0.03), a ride in a funicular cabin, a car's wing
      mirror, a large plate only half covered by its blur, distant riders and a pedestrian under the size
      threshold, shots in front of a private house, a clip with a burned-in sticker. The planner's check now also
      refuses any small silhouette in the road zone, any person whose box does not reach the bottom of the frame
      (the rider's own arms and legs do), and asks a larger CLIP model (ViT-L/14) for a second opinion on "taken
      from a car or a cabin"; a shot with a close, large plate is replaced, not blurred.
    - With these rules the "handlebar view" footage runs short: about 13 clips carry most of the riding shots of
      the pilot.
- **Review by three independent reviewers** (contact sheets every 0.25 s, one large frame per shot, the crops of
  what was blurred and of what was left visible):
    - Round 1: refused by all three for the opening shot, where the rider faces the camera: a skin-coloured band
      shows at the bottom of the visor and does not move with the reflections. A look at the full-resolution
      frame had judged it a mirror visor; the reviewers were right to doubt. **Any shot where the rider faces the
      camera is now refused** by the planner (CLIP ViT-L/14, 0.96 and 0.80 on the two faulty shots, 0.14 or less
      elsewhere). Second finding: a blur that stopped before the end of a shot.
    - Round 2: no face, no person, no readable plate, no shot from a cabin; two reviewers still saw one small
      screen or label whose blur stopped 0.2 s before the end of its shot. Every mask is now held for the whole
      of a short shot, and that clip is excluded.
    - Round 3: two reviewers passed it; the third doubted the first 0.4 s of one shot (a parked motorcycle cut by
      the right edge, with a pink and white object he could not identify). That shot was trimmed and the next one
      starts earlier; the automatic audit passed again and the three reviewers passed the two changed shots.
    - The final cut has 28 shots from 16 clips, 37.0 s, 36 blurred tracks and 62 left visible (dashboards, GPS and
      phone screens, switches, tank labels).
    - Still open, **the owner's decision**: on a few riding shots another rider is visible very far ahead (1.5 to
      2 % of the frame height, from behind). Earlier batches were refused for that. A magnified check of the road
      zone finds such a silhouette in most group-ride footage: refusing them all leaves too few riding shots to
      fill the end of the montage.
- **In the repository**: `narrated_cut.py`, `mm_plates.py`, the plate judge in `mm_scene.py`,
  `tests/test_plates_and_narration.py`, [Narrated montage](pipeline/narration.md). The other pilot scripts are
  outside it ([TODO](todo.md)).
- **Extra environments and weights**: `C:\workdir\_s2s_cb\venv_plates` (onnxruntime-directml,
  open-image-models 0.6.0; `MM_PLATES_PYTHON` points at its Python), CLIP ViT-L/14 (1.7 GB) for the plate judge
  and torchaudio `MMS_FA` (1.2 GB) for the alignment, both downloaded at first use.

## The pilot's voice sounded robotic: two causes measured (2026-11-16)

The owner, after listening to the pilot: "the sound is still robotic". The pipeline cannot judge a voice by ear, so it
was measured at each step of the chain against real recordings of the owner (`voice_diag.py`: quality and
signal-to-noise estimated without a reference by torchaudio SQUIM, share of voiced frames, range of the melody
inside a sentence). Figures for the same narration:

| Step | Estimated quality (1 to 4.5) | Estimated signal-to-noise | Voiced frames | Melody range in a sentence |
|---|---|---|---|---|
| The owner's real voice (reference recording) | 3.6 | 26 dB | 75 % | 5.9 semitones |
| Takes chosen for the pilot, raw | 2.7 | 20 dB | 58 % | 4.9 |
| After the pitch and tempo filter | 1.3 | 8 dB | 58 % | 4.8 |
| After the equaliser, compressor and limiter (the pilot's voice) | 1.2 | 6 dB | 37 % | 4.0 |
| Same takes, no such filter, light mastering | 2.6 | 19 dB | 57 % | 5.0 |
| Takes chosen on measured quality, light mastering | 3.2 | 22 dB | 64 % | 5.8 |

- **Cause 1: the `rubberband` filter of ffmpeg.** It was used to lower the voice by 1.5 semitones and speed it up
  by 5 %. Tested alone on the raw narration, any use of it (pitch with or without formant preservation, or tempo
  alone) takes the estimated quality from 2.7 to between 1.3 and 1.6. `atempo` leaves it intact (3.0), and so does a
  pitch change made by resampling followed by `atempo` (2.7). Never use `rubberband` on the voice.
- **Cause 2: choosing the deepest take.** To get a deeper voice the selection favoured the lowest pitch among the
  four takes of a sentence. In 9 sentences out of 11 that take was the most damaged one (around 105 Hz, under the
  owner's natural 110 to 120 Hz, where the voice creaks). Choose a take on its measured quality, near the natural
  pitch and a steady pace.
- **The strong mastering made it worse**: octave-band equalisation toward the reference Short, 4:1 compression
  and a limiter. A high-pass filter, 2:1 compression and a limiter are enough.
- One predictor is of no use here: the "subjective" SQUIM score does not separate these versions (3.6 to 4.5 for
  all of them, the damaged ones included). The three other measures agree with each other and with the owner's ear.
- **Redone from the existing takes** (no new generation): `C:\workdir\_s2s_cb\pilot01\scripts\master_clean.py`
  writes `voice2\v3_meilleures_prises_voix.wav` (38.2 s, natural pitch) and its word times. To listen:
  `C:\workdir\_s2s_cb\pilot01\ecoute\` (before, after, and after one semitone deeper, which measures a little
  lower). **The owner's ear decides**; the measures only say which version is closer to a real recording.
- **Not done yet**: the video still carries the old voice, locally and in the private upload. With the new voice
  the narration is 4.7 s longer, so the shots must be planned and rendered again, then audited and read by the
  three reviewers. It was not run on 16 November: the machine had under 1 GB of free memory.
- If the corrected voice is still not natural enough, the raw takes are the limit (3.2 against 3.6 for a real
  recording). Next levers, in order: a prompt recording in the tone of the text (the one used is a cheerful,
  chatty clip), VoxCPM2 fine-tuned on a recording of the owner's voice (its model card speaks of LoRA
  fine-tuning from 5 to 10 minutes of audio: read once on 2026-11-16, not double-checked, procedure not tried;
  the [TODO](todo.md) asks the owner for 10 to 30 minutes to keep a margin), or the owner reading the 35 seconds
  himself. The web research of that day was not finished.

## Independent review before the commit of 2026-11-16

Three reviewers read the pending changes (code defects, public exposure, documentation against the code). What
was corrected, each with a test that failed first:

- **A giant detection could make a detected plate visible again.** One giant box (a dashboard, a patch of sky)
  seen on a single frame joined the track of the plate next to it, and the whole track was then judged as a giant
  box. Boxes whose size differs by more than two times are no longer merged or linked, and in a mixed track the
  giant samples no longer decide for the others.
- **A strip stayed almost sharp along the frame border**: the blur was feathered on every side, including the
  side cut by the border, exactly where a plate half out of the frame passes. A side on the border is now opaque.
- **Detections in the cache survived a change of the detector's settings.** The cache file now carries a
  signature of those settings and is ignored when its number of frames is not the shot's.
- **A render without plate masking took the name of a masked one.** It is now written under `name_sans_flou`, the
  files of an earlier render are removed first, and the report says `plates_masked`.
- **Sound**: a music track shorter than the video needs, or a level that cannot be measured, now stops the render
  instead of being replaced by a guess; the impact follows a strong beat earlier than 1.9 s.
- **Left as it is, and now visible in the report**: a track made only of giant boxes stays visible unless the
  judge is certain (0.95), because a dashboard scores up to 0.88 and blurring it spoils every handlebar view. Such
  a track with a score of 0.50 or more is counted in `doubts`, listed under `visible` in the report and marked in
  red on the sheet of visible tracks. The render does not refuse it: the reviewers read that sheet, and the loop
  that replaces such a shot is still outside the repository ([TODO](todo.md)).

## Environment, rebuilt on 2026-11-13

- **The render venv is back**: `C:\workdir\_s2s_cb\venv` (Python 3.12, torch 2.6.0 with CUDA 12.4 on the
  RTX 4060, chatterbox-tts 0.1.7, transformers 5.2.0, numpy 1.26.4, open_clip_torch, opencv-python 4.11,
  librosa 0.11, faster-whisper 1.2.1). `local_paths.json` points `render_python` at it. The recipe is
  `requirements-render.txt` at the root of the repository; the exact resolved versions are kept beside the venv
  (`render.lock`).
- Two bounds in that recipe matter: `setuptools<81` (the Chatterbox watermarker imports `pkg_resources`; without
  it the model does not load: "'NoneType' object is not callable") and `av<19` (faster-whisper).
- **Weights downloaded again**: Chatterbox Multilingual (checkpoints v2 and v3) and Whisper large-v3. RT-DETR and
  CLIP download on their first use.
- **Whisper runs on the GPU from the render venv**, once torch's `lib` folder is on the DLL search path (it holds
  the cuBLAS and cuDNN libraries CTranslate2 needs): 15 takes re-listened in 10 s. `mm_voicecheck.py` now starts
  its server in the interpreter that runs the script when faster-whisper is installed there, and on the graphics
  card when that interpreter's `torch/lib` holds both `cublas64_12.dll` and a cuDNN 9 library
  (`MM_ASR_DEVICE=cpu` forces the CPU; without faster-whisper it still uses the social2shorts venv). A server
  that stops while working is restarted once on the CPU, and the voice stage prints the processor it uses. This
  switch is covered by tests only: it has not been run with the real model yet.
- Still in place: the music library (`public/lib/`, 52 files), the 22 validated voices (`vo/_cache/`), the owner's
  French and English voice references (`social2shorts/work/voiceover/ref_fr*.wav`, `ref_en*.wav`), 220 GB free.
- The voice stage and the re-listening now take a **language**: `--lang fr` (or `en`, `ar`) on
  `scan/gen_vo_clone.py`, else `voice_lang` in `local_paths.json`, else English as before. It goes to Chatterbox,
  to Whisper and to the word comparison (`mm_lang.py`: French apostrophes, homophones and digits, Arabic vowel
  marks), with one reference recording per language (`voice_ref_fr`) and a separate cache key per language; the
  22 English voices stay valid. Covered by tests only (real Whisper transcripts of 13 November as cases): no
  French voice has been generated through the stage yet. The audit (`scan/privacy_check.py`) re-listens in the
  language of the montage: the `lang` field of its manifest entry, else the default language. The French pace
  target is 3.2 words per second and a French take is never slowed down; a French voice needs its own reference
  (`voice_ref_fr`), the default English recording is not used for it.

## French voice test, 2026-11-13

Five French sentences, reference `ref_fr2_expr.wav` (13 s), every take transcribed by Whisper large-v3 and
compared with the intended words; similarity measured with the same speaker encoder for all engines.

| Engine | Exactly the text | Similarity | Pace | Notes |
|---|---|---|---|---|
| Chatterbox Multilingual, checkpoint v2 (PyPI 0.1.7) | 12 of 15 | 0.89 | 2.3 words/s | one sentence said twice, two homophones ("bat" heard "bas") |
| Chatterbox Multilingual, checkpoint v3 (`master` branch only) | 15 of 15 | 0.89 | 2.8 words/s | 3.9 GB of video memory |
| VoxCPM2, reference clip only | 8 of 10 | 0.87 | 3.9 words/s | too fast, 48 kHz output |
| VoxCPM2, reference clip and its transcript | 8 of 10 | 0.89 | 2.9 words/s | 6.2 GB of video memory, 48 kHz output |

Checkpoint v3 needs the code of the `master` branch of Chatterbox (cloned in
`C:\workdir\_s2s_cb\chatterbox-master`, loaded with `t3_model="v3"`; the voice stage asks for it with
`MM_TTS_T3=v3` and stops if the installed Chatterbox has no such parameter); the publisher retired the project in
August 2026, so it gets no more fixes. VoxCPM2 (Apache-2.0, maintained) is installed in its own venv
(`C:\workdir\_s2s_cb\venv_voxcpm`). Listening samples: `C:\workdir\_s2s_cb\demo\`. The owner chooses by ear.
French homophones are spelt differently by Whisper for the same sound: the French comparison treats two words
with the same sound as the same word.

## How to run

```console
python run_pipeline.py --list
python run_pipeline.py --from plan --to check     # plan, voice, render, audit
python scan/privacy_check.py sheets <id>          # then LOOK at the sheets
```

The voice stage needs the render venv (Chatterbox, and faster-whisper for the re-listening; without
faster-whisper there, Whisper runs from the social2shorts venv); the two models run in separate processes
because they do not fit in memory together.

## Watch out

- The PC has 16 GB; a social2shorts run (scheduled every hour at hh:05) next to the voice or audit stage can
  exhaust memory (Windows error 1455).
- Trending commercial music uploaded through the API is claimed by Content ID ([Music](pipeline/music.md)): the
  owner adds a catalogue sound himself in the YouTube app, on the voice-only file.
- With 16 GB, close what is not needed before a render: the headless Chrome used for YouTube Studio alone holds
  about 0.9 GB.
- A Short **longer than one minute** with any active copyright claim is blocked worldwide (YouTube Help, checked
  2026-11-13): a narrated montage stays under 60 s (`narrated_cut.py` refuses more than 59.5 s, whatever the music).

## Open decisions (owner)

- Whether the pilot (private on the channel since 2026-11-16) is good enough to publish, and with which music:
  a track of the YouTube Audio Library chosen from the list, or a catalogue sound added in the mobile app from the
  local voice-only file (YouTube's help: the audio of an uploaded video can no longer be changed in the mobile app).
- Whether another rider seen very far ahead, from behind (under 2 % of the frame height), is acceptable.
- Which voice carries the French narration (samples to listen to; the pilot uses VoxCPM2). On 2026-11-16 the
  owner found the pilot's voice still robotic: he listens to the corrected narration
  (`C:\workdir\_s2s_cb\pilot01\ecoute\`) and says whether it is good enough to rebuild the pilot with it.
- Relax "no other person in frame" (a helmeted rider far away) or film new footage, if more variety is wanted.
- What to do with the Shorts already on the channel that show a face.

See the [TODO](todo.md) for the ordered list.
