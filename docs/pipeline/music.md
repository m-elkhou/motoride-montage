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
The routes, to be chosen by the owner before any render (rules and prices read on the publishers' own pages on
2026-11-13; prices change, check them at checkout):

| Route | Cost | Automatable | Catch |
|---|---|---|---|
| Commercial track in the upload | none | yes | Content ID claim: the rights holder chooses to block, to take the revenue or to track, per country. No strike. **A Short over one minute with any claim is blocked worldwide** |
| Shorts catalogue sound (licensed for Shorts) | none | no: added by hand in the YouTube or YouTube Create mobile app | the hit itself; 30 to 90 s per track; errors possible on channels uploading for commercial purposes |
| Licensed library (Epidemic Sound, Artlist, Uppbeat, Soundstripe), channel declared | about 7 to 15 USD a month | yes; Epidemic Sound publishes an MCP server (search by tempo, mood and genre, cut to a length, download with a paid plan) | "trend-like" tracks, not the hit itself; trap, drill and afrobeats are there, no Arabic or North African genre at Epidemic Sound; videos published while subscribed stay covered after cancelling |
| YouTube Audio Library | none | download in YouTube Studio | the only catalogue YouTube itself calls copyright-safe; less trendy |
| Original music from a generator with a commercial licence (Suno, ElevenLabs Music) | about 6 to 10 USD a month | ElevenLabs: yes (API); Suno: no official API | the style, not the hit; rights only for tracks made while subscribed; ownership not guaranteed by the publishers |

YouTube Creator Music is not a route: it is limited to creators in the United States and stopped selling
licences on 10 August 2026. Lickd licenses chart tracks per video (from 8 USD a track, priced on the channel's
average views); whether its licence covers Shorts was only stated in its marketing pages.

What trended in the first half of November 2026 (Spotify daily charts of 11 November, TikTok France weekly list
of 9 November): in Morocco, Shaw ("CARAPACE", "PILLAVE"), Stormy ("KILOWAT", "ROUTINE", "PER LA VITA"), Najm with
ElGrandeToto ("GHALAT"), Draganov with TIF ("Couci Couca"); in France, Mauvais Djo ("12", "4"), Tiakola ("Jet Lag",
"Mélo Décalé"), Vacra and La Rvfleuze ("Fille à Papa"); worldwide, Tate McRae ("Housewife"), KATSEYE ("Animal"),
HUGEL ("Movin' To The Sun"). Tempo databases know almost none of the Moroccan and French titles: the tempo is
measured on the file itself.

### Shorts sounds ("Use this sound"), checked in the signed-in Studio on 2026-11-13

- **Nothing on the desktop attaches a catalogue sound to a Short.** The Studio editor and the Audio Library page
  only hold the YouTube Audio Library (the editor announced about 13,400 tracks on 2026-11-13, a figure that was not counted; the Audio Library
  page read in full on 2026-11-16 holds 7,160 music tracks; YouTube licence or CC BY 4.0); none of
  the chart titles or their artists is in it. On youtube.com a sound page offers only "Enregistrer" (save the
  sound), and "Remixer" on a Short opens "Remixer sur votre téléphone" with a QR code. The Studio "Créer" menu
  has no Short entry. Using a trending sound is a step done in the mobile app.
- **Where the trends are**: `charts.youtube.com/charts/TopShortsSongs/<fr|us|global>/daily` (and `weekly`), 50
  entries ranked by use in Shorts; each entry links to its sound page `youtube.com/source/<video id>/shorts`,
  whose header shows how many Shorts use it. **Morocco has no YouTube chart**: read the count on the sound page
  of each Moroccan hit instead.
- A Short with original audio has its own sound page too, so a narration published with claim-free audio can be
  reused by other creators.
- A sound saved from the desktop ("Enregistrer") is meant to appear among the saved sounds of the mobile app
  (not verified on a phone). On 2026-11-14, with the owner's go, 15 shortlisted sounds were saved on the channel's
  account this way; on the desktop they sit in a private playlist named "Sons".

### The YouTube Audio Library, listed in full on 2026-11-16

The owner asked for the list of the music he may use "from YouTube", the free tracks and the ones that only need a
mention, then narrowed it to pop, rap and jazz. The whole library of the signed-in Studio (Audio Library, Music tab)
was read: **7,160 tracks, 6,251 under the YouTube Audio Library licence (no attribution) and 909 under Creative
Commons Attribution 4.0 (attribution required)**. Pop: 502 + 89, hip-hop and rap: 671 + 4, jazz and blues: 389 + 65.
There is no Creator Music tab on this channel.

- **Files** (outside the repository): `C:\workdir\_s2s_cb\channel\musiques_youtube\`:
  `musiques_pop_rap_jazz.html` and `.md` (the three genres, free tracks then attribution tracks, moods that suit a
  grave narration first, then the most recent), `mentions_a_copier.md` (the credit text of each Creative Commons
  track), `bibliotheque_youtube_complete.csv` (every track: genre, mood, instruments, licence, date),
  `build_list.py`, and the raw reading in `releve/`.
- **What the two licences say** (pop-ups of the library, read on 2026-11-16). Standard licence: usable in all the
  channel's videos, monetised ones included, no attribution; the music files may not be distributed on their own.
  Creative Commons: same use, but the description must carry the text given by the `Copier` button, of the form
  `<title> de <artist> fait l'objet d'une licence Creative Commons Attribution 4.0.
  https://creativecommons.org/licenses/by/4.0/`, then `Source : <url>` and `Artiste : <url>`; the requirement also
  holds on other platforms.
- **What the track data holds**: title, artist, duration, one genre, one mood, instruments, licence, date. No tempo
  and no "vocals" flag in this list (the editor's own list has both): a title with "feat." is sung, and a
  narration needs an instrumental.
- **How it was read**: the page shows 30 to 100 rows, estimates the total wrongly ("about 2,668", then 512, then
  4,830) and refuses to page past its estimate, so a view stops after 300 to 2,000 rows while the server still
  holds more. The full reading follows the server's page token instead (`releve/releve_complet.js`, 72 requests of
  100 rows). The method is kept in the owner's local notes.
- **Rules checked on YouTube's help pages the same day** (five questions, each answer re-checked by a second
  reader against the official pages):
    - Audio Library music can be monetised and is not claimed by Content ID; a Creative Commons track must be
      credited in the description.
    - Naming or crediting a commercial song gives no right to use it; the pages list the safe sources (permission,
      Creative Commons, Audio Library, Creator Music) and nothing else.
    - Creator Music is for Partner Programme creators in the United States and cannot be used in Shorts.
    - Catalogue songs come from the Shorts sound picker of the mobile app (most songs up to 90 seconds in a
      3-minute Short, some limited to 60 or 30 seconds). A Short longer than one minute with an active claim is
      blocked. The audio track of an uploaded video can no longer be changed in the mobile app: a catalogue sound
      has to be added while the Short is created on the phone, from the local file.
    - Cloning one's own voice for a voice-over is listed among the cases that need no "AI use" disclosure.

**Flow chosen by the owner (2026-11-14).** The engine renders each narrated Short twice
([Narrated montage](narration.md)): one file with the voice over a library track (a claim-free original sound that
other riders can reuse), and one with the voice alone, to which the owner adds a trending catalogue sound in the
YouTube app before publishing. The app step is manual, and the music is then aligned by hand.

The ranking of `scan/music_catalog.py` (level, drop strength, mood) applies to whatever source is chosen. A
narration needs an instrumental (or the stems): sung lyrics fight the spoken voice even when the music is lowered.
See [Next session](../next-session.md).
