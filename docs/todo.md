# TODO

Short, ordered list of what is left. The longer view is in the [roadmap](roadmap.md); the state of the project
for the next person (or session) is in the [handoff](handoff.md).

## Now

- [ ] **More safe footage.** After the strict review no montage is approved: the verified material that is left
  (about 34 s of POV and 16 s of bikes) sits next to windows already refused. New footage filmed with the
  anonymity rules in mind (closed opaque visor, no one else in frame, no plate or sticker) is the real fix.
- [ ] The owner checks what is left in `PRIVATE/row/` (70 clips with several people, 210 in doubt), restores the
  harmless ones (`python scan/raw_audit.py restore name.mp4`) and deletes the rest.
- [ ] Listen to the 22 validated voices (`PRIVATE/ecoute_voix_validees/`): the re-listening is automatic, the
  final judgement is the owner's ear.

## Next

- [ ] Catch automatically what the reviewers catch: a rider far ahead (under 5 % of the frame height), readable
  plates, stickers and printed faces.
- [ ] Score more windows of the clips with no detection at all, and add a scenery theme for POV montages.
- [ ] Re-scan only the windows refused for a weak detection, with a second opinion.

## Done (10-11 November 2026)

- [x] No shot from inside a car, the owner's cloned voice, raw originals isolated then deleted on request,
  strict description rule, modern music ranked by mood (R26-R31).
- [x] Every voice take re-listened by Whisper; 22 of 22 hooks validated (R32).
