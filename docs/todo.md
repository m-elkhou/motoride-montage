# TODO

Short, ordered list of what is left. The longer view is in the [roadmap](roadmap.md); the state of the project
for the next person (or session) is in the [handoff](handoff.md), and the brief for the next session in
[Next session](next-session.md).

## Now: new direction (owner, 2026-11-13)

- [ ] **Rebuild the render venv** (`C:\workdir\_s2s_cb\venv`, Python 3.12: torch with CUDA, Chatterbox
  Multilingual, open_clip, transformers, librosa, opencv, soundfile) and let the models download again.
- [ ] **Trending music**: current energetic tracks (Moroccan pop and rap, English pop, other trends) instead of the
  claim-free library only. Research what trends now, then have the owner choose the licensing route before any
  render (claims through the API, in-app Shorts sounds, or a licensed library).
- [ ] **Narrated monologue in the owner's cloned voice**, in the style of the reference Short (a spoken, rhythmic,
  second-person text over the whole ride, about 50 s): original texts, French first, voice cloned from the
  French references, every take re-listened by Whisper in French.
- [ ] **Footage**: the strict review left too little verified material; new footage, or an owner decision on far
  away helmeted riders, comes first.

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
