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
the best compromise between pace, similarity to the owner's voice and no gap inside the sentence. If no take passes
after up to 18 attempts, the line is **refused**: a faulty voice is never kept by default. Without Whisper the stage
stops.

**Pace.** The target depends on the language: **2.5 words per second in English and in Arabic, 3.2 in French**
(`--words-per-s` sets another one).

- In English a take that is too fast is slowed by **15 % at most** (more stretching sounds artificial).
- In any other language a take is **never slowed down**: slowing made the French voice sound sleepy, so a fast take
  is kept as it is.
- A take that is too slow is sped up by 20 % at most, in every language. A take whose pace was corrected is
  re-listened, in the same language, before it is kept.
- Outside English the words counted are the spoken ones: a "?" or a ":" written with a space is not a word, "d'un"
  counts for two words and "150" for two ("cent cinquante"). English keeps its count of space-separated pieces, so
  the validated English voices keep their target.

Whisper runs in its own process, which `mm_voicecheck.ASR` starts once as a small server: in the interpreter that
runs the script when faster-whisper is installed there, otherwise in the social2shorts venv (`MM_ASR_PYTHON` to
choose it, `MM_ASR_MODEL` for the model). `MM_ASR_DEVICE` (`cpu`, `cuda` or `auto`, the default) chooses the
processor. The graphics card is used only when the `torch/lib` folder of that interpreter holds **both**
`cublas64_12.dll` and a cuDNN 9 library (a file named `cudnn*64_9.dll`): CTranslate2 stops the whole process without
them, at load for the first, at the first transcription for the second. Otherwise Whisper runs on the CPU, also when
`cuda` was asked for. If the server still stops in the middle of the work, it is started again **once, on the CPU**,
and the request is sent again; if it stops a second time, the stage ends with a message that names
`MM_ASR_DEVICE=cpu` and `MM_ASR_PYTHON`. The voice stage prints the model and the processor when the re-listening
starts, for example `reecoute Whisper large-v3 sur cuda`.

The voice model and Whisper large-v3 do not fit in memory together on the PC (Windows error 1455, "paging file too
small"), and the smaller `medium` model missed 2 of 18 known faults. So the work runs in **two phases**: the voice model
generates every take of every line **in its own process**, writes the takes and their measurements to disk and
exits (all its memory is returned), then a second process starts Whisper and re-listens to all of them; lines with no
valid take go round again with new seeds, three rounds at most. The audit does the same: the voice first, then the
images.

Each validated line is cached in `vo/_cache/` (key = the text, with the language when it is not English) with what
Whisper heard. `--verify-cache` re-listens to
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
| `--lang fr` (or `en`, `ar`) | language of the voice, of Whisper and of the word comparison (default: `MM_VOICE_LANG`, then `voice_lang` in `local_paths.json`, then `en`) |
| `--force` | regenerate everything |
| `--tries N` / `--words-per-s X` | candidates per line (default 6, up to 18 when none passes) / target pace (default 2.5 in English and Arabic, 3.2 in French) |
| `--lines-file hooks.txt` | generate one hook per line ahead of any plan |
| `--verify-cache` | re-listen to the cache, each voice in its own language, and set the faulty voices aside (needs no reference recording) |

**French and Arabic** (`mm_lang.py`). In French the comparison joins what Whisper splits at an apostrophe ("d 'un"
is "d'un"), expands digits into number words up to 999 999 ("150" is "cent cinquante"; "1 000" and "1.000" are
"mille") and reads a spelled sigle as one word ("P.O.V." is "POV"), so a text written in words matches a transcript
written in digits. Whisper chooses the spelling of a sound on its own, so two words that sound the same count as the
same word ("bat" heard "bas", "et" / "est", "roulé" / "rouler", "ça" / "ca", "paie" / "paye"). The rule is a short
list of spelling rules, not a dictionary.

**Different sounds the French comparison treats as equal, on purpose.** A take that says one for the other is
accepted:

- **é and è endings**: "roulé" / "roulait", "été" / "était", "les" / "lait";
- **silent final letters**: a final s, x, t or d is ignored ("œufs" / "œuf"). It is kept only in the listed words
  where it is pronounced ("but", "six", "dix", "start", "set", "raid", "short"...), and a final "-ent" is read as a
  silent verb ending except in the listed nouns and adjectives ("précédent", "président", "client"...) and in words
  ending in "-ment", "-tient" or "-vient". A word missing from a list can be added to it in `mm_lang.py`.

**Always refused**, in every language: a repetition, a missing word, an extra word and a different word. In French
and in Arabic a tail in another script (Arabic, Cyrillic or Chinese letters added after the sentence) counts as extra
words.

**Refused although the take is right** (another take is generated, or the line has to be written another way):
homophones the rules do not know (a nasal vowel: "sans" / "cent"), "1" heard for "une", and symbols or units
("km/h", "%", "€").

In Arabic the vowel marks are ignored and a ligature is read as its letters. The "P.O.V." spelling applies to English
only: in another language the hook is said as it is written (first letter in upper case, a final period only when
the line does not already end with a period, "?", "!" or an ellipsis).

Each language has its own reference recording (`MM_VOICE_REF_FR` or `voice_ref_fr`, see
[Configuration](../configuration.md)). The default recording is in English, so for another language the stage stops
when neither that setting nor an explicit `MM_VOICE_REF` is set: a French voice is never cloned from the English
recording by accident.

!!! warning "Chatterbox environment"
    Chatterbox pins its own `transformers`; another package upgrading it breaks the import (`LlamaModel`). The
    render venv is built from `requirements-render.txt`, which also keeps `setuptools` below 81: the watermarker
    of Chatterbox imports `pkg_resources`, and without it the model does not load. The publisher retired
    Chatterbox in August 2026; see the [handoff](../handoff.md) for the French test of its two checkpoints and of
    a maintained alternative.

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
of the final mix, under the music; a voice that does not say exactly the hook fails the montage. The audit listens
in the language of the montage: the `lang` field of its manifest entry when there is one, otherwise the default
language (`MM_VOICE_LANG`, then `voice_lang`, then English). `vo/<id>.clone.txt` records the language the voice was
generated in, but the audit does not read that file: for a batch in another language than the default, set
`voice_lang` in `local_paths.json` (or `MM_VOICE_LANG`), or add `lang` to the manifest entries. Otherwise a French
voice is re-listened as English and every montage is refused.

The constants (levels, crossover, ducking, chain) are at the top of `mm_audio.py`. `python mm_audio.py <music>
<offset> <seconds> <voice|-> <out.m4a>` builds one soundtrack on its own, for listening tests.

!!! note "Old script"
    `scan/legacy/overlay_vo.py` (the post-render mixer with `.voiced` markers) is obsolete and no longer called.
