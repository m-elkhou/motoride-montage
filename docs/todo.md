# TODO

Short, ordered list of what is left. The longer view is in the [roadmap](roadmap.md); the state of the project
for the next person (or session) is in the [handoff](handoff.md), and the brief for the next session in
[Next session](next-session.md).

## Now: narrated Shorts (owner, 2026-11-13 and 2026-11-14)

- [x] **Rebuild the render venv** (2026-11-13): `requirements-render.txt`, models downloaded again, GPU checked,
  French voice test done ([Handoff](handoff.md)).
- [x] **Trending music** (2026-11-13/14): what trends and the licensing routes are in [Music](pipeline/music.md).
  From a computer no catalogue sound can be attached to a Short. **Owner's go, 2026-11-14**: each narrated Short
  is rendered twice (voice over a library track, and voice alone for a catalogue sound added in the YouTube app);
  15 shortlisted sounds were saved on the channel's account.
- [x] **Licence plates** (owner, 2026-11-14: "hide the plates"): `mm_plates.py` and the plate judge of
  `mm_scene.py`, used by the narrated montage ([Narrated montage](pipeline/narration.md)).
- [ ] **First narrated Short (pilot 01)**: built end to end on 2026-11-14 (text, cloned voice, shots matched to
  the sentences, plates blurred, word-by-word captions, two sound versions). State and files: [Handoff](handoff.md).
  The voice-only file is on the channel as a **private** video since 2026-11-16; publishing waits
  for the owner's go.
- [ ] **Music of the pilot** (owner, 2026-11-16): he chooses a pop, rap or jazz track in the list of the YouTube
  Audio Library (`C:\workdir\_s2s_cb\channel\musiques_youtube\`, [Music](pipeline/music.md)). Then either add it in
  the Studio editor (definitive save, no ducking, no fade) or, better, download it, mix it under the voice with the
  engine (ducking, drop on the beat) and upload that file in place of the private one. A narration needs an
  instrumental.
- [ ] **Bring the pilot scripts into the repository** (they live in `C:\workdir\_s2s_cb\pilot01\scripts\`), with tests: the
  whole-clip privacy scan (`full_scan.py`: every eligible clip from end to end, 3 images per second), the
  narration stage (`gen_vox.py`, `asr_fr_check.py`, `master_narration.py`: best exact take per sentence, takes
  cut on speech and words timed by forced alignment), the planner (`plan_shots.py`: cuts on sentences and beats,
  shots chosen by CLIP text queries, a 10 images per second privacy check of each chosen extract, diversity),
  the audit of the finished video with its contact sheets (`audit_narr.py`) and the loop that replaces a refused
  extract (`blocks_from_render.py`, `make_pilot.sh`). Code in a worktree must be able to read the data of the
  main checkout (a `MM_ROOT` setting or an equivalent).
- [ ] **Pre-edited rushes**: some clips already carry a burned-in sticker ("JUST GO"), a picture-in-picture inset
  or an Insta360 watermark. They are found by eye on the storyboard and excluded by name; detect them
  automatically.
- [ ] **Plate judge**: a few cockpit parts (a mirror edge, a switch) are still blurred by caution; a second plate
  detector as a cross-check would allow leaving them visible without risk.
- [ ] **Waiting for the owner** (asked 2026-11-13, do not ask again before he comes back to it):
    - the voice: which of the three listening versions is closest to the reference Short (`demo3_A_cine`,
      `demo3_B_cine_grave`, `demo4_C_propre_grave` in `C:\workdir\_s2s_cb\demo\`), and what is still missing; the pilot uses the
      settings of the third one;
    - a cleaner recording of his voice (10 to 30 minutes, quiet room, the deep and steady tone he wants), which
      would allow training the voice model on him instead of prompting it with 10 seconds;
    - whether to try a hosted voice service (his voice would be stored there).
- [ ] **Voice quality** (owner, 2026-11-13): the first French samples were rejected (flat, no energy); the
  reference Short is still better. **2026-11-16: the pilot's voice is "still robotic".** Two causes measured in
  the chain (the `rubberband` pitch and tempo filter, and the choice of the deepest take), and a corrected
  narration built from the same takes: [Handoff](handoff.md). Waiting for the owner's ear on
  `C:\workdir\_s2s_cb\pilot01\ecoute\`.
- [ ] **Rebuild the pilot with the corrected voice** once the owner approves it: plan, render, audit, three
  reviewers (the narration is 4.7 s longer, every shot moves), then replace the private upload on his go.
- [ ] **Refuse a doubt automatically**: `narrated_cut.py` counts the wide detections left visible while the
  judge leans to a plate (`doubts` in the report); the loop that replaces such a shot belongs with the pilot
  scripts, once the judge's scores on dashboards are measured on more footage.
- [ ] **Voice rules to bring into the engine with the pilot scripts**: take chosen on measured quality near the
  natural pitch, never `rubberband` on the voice, light mastering, a faint floor instead of digital silence
  between sentences; `voice_diag.py` as the check that compares a narration with a real recording.

## Then

- [ ] The owner checks what is left in `PRIVATE/row/` (70 clips with several people, 210 in doubt), restores the
  harmless ones (`python scan/raw_audit.py restore name.mp4`) and deletes the rest.
- [ ] Catch automatically what the reviewers catch: a rider far ahead (under 5 % of the frame height), readable
  plates, stickers and printed faces.
- [ ] Score more windows of the clips with no detection at all, and add a scenery theme for POV montages.

## Done (10-11 November 2026)

- [x] No shot from inside a car, the owner's cloned voice, raw originals isolated then deleted on request,
  strict description rule, modern music ranked by mood (R26-R31).
- [x] Every voice take re-listened by Whisper; 22 of 22 hooks validated (R32).
