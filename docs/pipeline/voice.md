# 4. Voice and on-screen text

Viral moto Shorts mostly have **no voice-over** ([Viral DNA](../viral-dna.md)). This engine keeps the voice
**short and light**: the hook line, spoken once, under the music.

## Generating the voice: the owner's own voice, cloned

`scan/gen_vo_clone.py` reads each manifest `hook` and writes `vo/<id>.wav` with **Chatterbox Multilingual**, cloning
the timbre of the reference recording (`MM_VOICE_REF`, default `social2shorts/work/voiceover/ref_en_clean.wav`).
The neural voice used on 9 November (`en-US-GuyNeural`) was judged **robotic and too fast** and is no longer used.

A generative voice is unstable: the same sentence comes out at 1 to 4 words per second between runs, and sometimes
the model **runs past the end of the sentence** (it repeats it, adds a word, mumbles) until its own alignment analyser
forces the end, **in the middle of a word**. So every candidate is **listened to again** before it can be kept.

### Validation: every take is re-listened (`mm_voicecheck.py`)

A take is refused when any of these is true:

| Check | Catches |
|---|---|
| the model stopped itself on a **repetition** (`token_repetition` / `alignment_repetition` in Chatterbox's `forcing EOS` warning, captured per take) | repeated words or phrases |
| the raw signal ends in full sound (last 5 ms above 12 % of the peak) | a voice cut in the middle of a word |
| **Whisper** (large-v3) does not hear **exactly** the intended words | repeated phrases, extra words, missing words, mispronunciations ("Pov" read "Pav") |
| speech starts again after a silence at the end of the sentence | a repetition or a mumble that Whisper left out |

A forced end for a "long tail" alone is not a fault: it is how this model normally finishes (163 of 184 takes on
10 November), so those takes are judged by the other three checks. The comparison ignores case and punctuation, reads "P.O.V." as "POV" and treats homophones ("road" / "rode") as
equal; the natural decay of the last word is not counted as extra speech. Among the accepted takes, the script keeps
the best compromise between pace (target **2.5 words per second**, slowed by **15 % at most**: more stretching sounds
artificial), similarity to the owner's voice and no gap inside the sentence. If no take passes after up to 18
attempts, the line is **refused**: a faulty voice is never kept by default. Without Whisper the stage stops.

Whisper runs in the social2shorts interpreter, where faster-whisper is installed (`MM_ASR_PYTHON` to change it,
`MM_ASR_MODEL` for the model); `mm_voicecheck.ASR` starts it once as a small server.

The voice model and Whisper large-v3 do not fit in memory together on the PC (Windows error 1455, "paging file too
small"), and the smaller `medium` model missed 2 of 18 known faults. So the work runs in **two phases**: the voice model
generates every take of every line **in its own process**, writes the takes and their measurements to disk and
exits (all its memory is returned), then a second process starts Whisper and re-listens to all of them; lines with no
valid take go round again with new seeds, three rounds at most. The audit does the same: the voice first, then the
images.

Each validated line is cached in `vo/_cache/` (key = the text) with what Whisper heard. `--verify-cache` re-listens to
the whole cache: faulty voices go to `vo/_cache/_rejete/` with the reason, and are regenerated on the next run. There
is **no fallback to a synthetic voice**, and the renderer refuses to fall back to the old one.

On 10 November this check found **12 faulty voices out of 23** in the cache that the pace-only selection had kept:
"Wait for the turn. Wait for the turn.", "Born to ride, to ride.", "One more road. One.", "There's no speed limit",
"...different and" cut short, "This is freedom... freedom". The pace-only rule had even favoured them: a sentence said
twice lasts about as long as the slow target.

After the fix, the 22 hooks of the planner all have a validated voice (the two shortest, "Born to ride." and "This is
freedom.", needed ten takes per round: short sentences make the model stammer most). An independent re-check of the
cache and 22 voice-plus-music previews, re-listened in the mix, came back clean.

| Option | Use |
|---|---|
| `--force` | regenerate everything |
| `--tries N` / `--words-per-s X` | candidates per line (default 6, up to 18 when none passes) / target pace (default 2.5) |
| `--lines-file hooks.txt` | generate one hook per line ahead of any plan |
| `--verify-cache` | re-listen to the cache, set the faulty voices aside |

!!! warning "Chatterbox environment"
    Chatterbox pins its own `transformers`; another package upgrading it breaks the import (`LlamaModel`). It works
    in the render venv today; if it breaks again, give it its own venv.

`scan/gen_vo_edge.py` (edge-tts) is kept only as an archive of the old neural voice.

## Mixing: `mm_audio.py`, inside the render

Since 10 November 2026 the voice is mixed **by `viral_cut.py`, in the same pass as the music**, from the original
files. The old two-step version (normalise the music, then re-encode the whole file to add the voice) made the voice
sound far away and left some files with a corrupt audio stream (see [R22](../review.md)).

**Voice treatment** (no echo, no reverb): high-pass 80 Hz, +3.5 dB warmth around 150 Hz, -2.5 dB at 330 Hz (boxy
sound), +4 dB presence around 3 kHz, light air, de-esser, soft compression, then a gain **fitted by measurement** to
-13.5 LUFS through a limiter, with 20 ms / 100 ms fades so the voice never starts or ends with a click.

**Making room for the voice**: the music is split at 200 Hz (Linkwitz-Riley). Above 200 Hz it is lowered
**about 7-9 dB while the voice speaks** (sidechain compression keyed by the voice), below 200 Hz only slightly, so the
808 bass keeps its punch. The voice ends up roughly 9 dB above the music in the speech band.

**Loudness and encoding**: music brought to -15.5 LUFS before ducking, then **two-pass `loudnorm`** (linear gain, no
pumping) to **-14 LUFS / -1 dBTP** (YouTube's reference), AAC **48 kHz**, muxed with the video **without
re-encoding**. Every render is then checked (`mm_audio.stream_problems`): sample rate, AAC packet count against the
declared duration, equal audio and video durations.

**Checked again at the audit**: `privacy_check.py audit` re-listens to the voice file alone and to the first seconds
of the final mix, under the music; a voice that does not say exactly the hook fails the montage.

The constants (levels, crossover, ducking, chain) are at the top of `mm_audio.py`. `python mm_audio.py <music>
<offset> <seconds> <voice|-> <out.m4a>` builds one soundtrack on its own, for listening tests.

!!! note "Old script"
    `scan/legacy/overlay_vo.py` (the post-render mixer with `.voiced` markers) is obsolete and no longer called.
