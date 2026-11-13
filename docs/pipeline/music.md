# 3. Music

!!! danger "Commercial tracks get claimed"
    A video using a trending commercial song uploaded through the API is blocked or monetised by the rights
    holder (Content ID). This was confirmed on the channel itself. Trending TikTok/Reels sounds are only usable
    through the in-app Shorts "Sounds" library (manual upload), never through the API.

The engine therefore ships **no audio** and expects **claim-free** tracks in `public/` (git-ignored). The soundtrack
must be **modern and motivating**: bright, driving, 100-145 BPM, with a clear drop. The safest source is the
**YouTube Audio Library**: its licence covers monetised YouTube videos and it is the only catalogue that cannot be
claimed through the API.

## Getting the tracks

`public/lib/` holds the library tracks (full length, instrumental) with a `catalog.json` (title, artist, BPM,
genres, moods, licence). They are downloaded from YouTube Studio in a signed-in browser (the owner signs in, the
automation never handles a password); see the `youtube-studio-browser` skill of the author's tooling. Check each
track's licence yourself before use: licences are per track and can change.

## Choosing and ranking

```bash
python scan/music_catalog.py --top 40 --write
```

For each track, `scan/music_catalog.py` measures the tempo, the loud level and the **strength of the drop** (loud
passages against the median level: `viral_cut.py` places the slow-motion hero shot on that moment). It then:

- **drops** tracks with a voice or shorter than 60 s;
- **drops** tracks whose declared mood is dark, melancholic or angry (they do not motivate);
- **ranks** the rest by level, drop strength and positive mood, and interleaves slow and fast tracks;
- writes `public/lib/analysis.json` (cached: a track is analysed once) and, with `--write`, the ordered list
  into the local `scan/gen_config.json` under `music`.

`gen_batch.py` gives one track per montage, in rotation, so two neighbouring Shorts never share a soundtrack.

| Why this profile | |
|---|---|
| Tempo | 120-140 BPM sits in the range measured on viral moto Shorts ([Viral DNA](../viral-dna.md)) |
| Fit | hard drops give `viral_cut.py` a clear moment for the slow-mo hero shot |
| Mood | upbeat, driving tracks: the channel is about the joy of riding |
| Rights | library tracks are claim-free and easy to verify |

## Next: trending tracks (owner, 2026-11-13)

The owner wants current, energetic trends (Moroccan pop and rap, English pop) rather than library music only.
Three routes, to be chosen by the owner before any render:

| Route | Automatable | Catch |
|---|---|---|
| Commercial track in the upload | yes | Content ID claim: revenue to the rights holder, possible block by label or country |
| In-app Shorts sounds (licensed for Shorts) | no, added by hand in the YouTube app | the trend itself, but manual |
| Licensed library (subscription such as Epidemic Sound or Artlist, channel declared) | yes | "trend-like" tracks, not the hit itself |

The ranking of `scan/music_catalog.py` (level, drop strength, mood) applies to whatever source is chosen. See
[Next session](../next-session.md).
