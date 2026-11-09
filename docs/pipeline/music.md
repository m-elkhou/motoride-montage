# 3. Music

!!! danger "Commercial tracks get claimed"
    A video using a trending commercial song uploaded through the API is blocked or monetised by the rights
    holder (Content ID). This was confirmed on the channel itself. Trending TikTok/Reels sounds are only usable
    through the in-app Shorts "Sounds" library (manual upload), never through the API.

The engine therefore ships **no audio** and expects **claim-free** tracks in `public/` (git-ignored):

- **Phonk / drift** from a royalty-free source whose licence allows monetised YouTube use and needs no
  attribution (the author used Pixabay's content licence).
- Or the **YouTube Audio Library**, the only safe catalogue through the API.

`gen_batch.py` rotates through the `MUSIC` list (`ph_*.mp3`). Replace the file names with your own.

| Why phonk | |
|---|---|
| Tempo | 120–140 BPM sits in the range measured on viral moto Shorts ([Viral DNA](../viral-dna.md)) |
| Fit | hard drops give `viral_cut.py` a clear moment for the slow-mo hero shot |
| Rights | claim-free libraries exist and are easy to verify |

Check each track's licence yourself before use: licences are per track and can change.
