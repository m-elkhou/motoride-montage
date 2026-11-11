"""Couche de validation de la voix : comparaison des mots, fin coupee, parole reprise, fin forcee du modele.

Les cas viennent des voix fautives trouvees le 10/11 (repetitions, mots en trop, « Pov » lu « Pav », fins coupees).
Aucun modele : signaux synthetiques et textes.
"""
import logging

import pytest

np = pytest.importorskip("numpy")
import mm_voicecheck as vc  # noqa: E402

SR = 24000


def tone(seconds, amp=0.5, f=180):
    t = np.arange(int(seconds * SR)) / SR
    return (amp * np.sin(2 * np.pi * f * t)).astype(np.float32)


def silence(seconds):
    return np.zeros(int(seconds * SR), np.float32)


@pytest.mark.parametrize("expected,heard", [
    ("Wait for the turn.", "Wait for the turn."),
    ("Which bike would you pick.", "Which bike would you pick?"),
    ("P.O.V., no traffic no plan.", "POV, no traffic, no plan."),
    ("Road first everything else later.", "Rode first, everything else later."),
    ("The best seat in the world.", "the best seat in the world."),
    ("P.O.V., you left the city.", "P O V, you left the city."),
    ("P.O.V., you left the city.", "P. O. V. You left the city."),
])
def test_the_same_words_pass(expected, heard):
    assert vc.word_problems(expected, heard) == []


@pytest.mark.parametrize("expected,heard,needle", [
    ("Wait for the turn.", "Wait for the turn. Wait for the turn.", "repetition"),
    ("Born to ride.", "Born to ride, to ride.", "repetition"),
    ("One more road.", "One more road. One.", "repetition"),
    ("No speed limit on this feeling.", "There's no speed limit on this feeling.", "en trop"),
    ("This road hits different.", "this road hits different and", "en trop"),
    ("Pov: you left the city.", "Pav, you left the city.", "entendu"),
    ("Which bike would you pick.", "Which bike would you", "manquant"),
])
def test_repetitions_extra_missing_or_wrong_words_are_reported(expected, heard, needle):
    problems = vc.word_problems(expected, heard)
    assert problems and any(needle in p for p in problems)


def test_a_voice_cut_in_full_sound_is_detected():
    assert vc.abrupt_end(tone(1.0), SR)


def test_a_voice_that_fades_out_is_not_cut():
    w = tone(1.0)
    w[-int(0.05 * SR):] *= np.linspace(1, 0, int(0.05 * SR), dtype=np.float32)
    assert not vc.abrupt_end(w, SR)


def test_speech_resumed_after_a_silence_is_measured():
    w = np.concatenate([tone(0.8), silence(0.3), tone(0.2), silence(0.1)])
    assert vc.trailing_speech(w, SR, last_word_end=0.8) == pytest.approx(0.2, abs=0.03)


def test_the_natural_decay_of_the_last_word_is_not_a_repetition():
    decay = tone(0.4) * np.exp(-np.linspace(0, 6, int(0.4 * SR))).astype(np.float32)
    w = np.concatenate([tone(0.8), decay])
    assert vc.trailing_speech(w, SR, last_word_end=0.6) == 0.0      # Whisper date la fin du mot trop tot


def test_a_short_click_after_the_sentence_is_ignored():
    w = np.concatenate([tone(0.8), silence(0.3), tone(0.02), silence(0.2)])
    assert vc.trailing_speech(w, SR, last_word_end=0.8) == 0.0


def test_forced_end_warnings_of_the_voice_model_are_captured():
    log = logging.getLogger(vc.EOS_LOGGER)
    with vc.EOSWatch() as watch:
        log.warning("forcing EOS token, long_tail=tensor(True)")
        log.warning("something unrelated")
    log.warning("forcing EOS token outside the watch")
    assert len(watch.events) == 1 and "forcing EOS" in watch.events[0]


class FakeASR:
    def __init__(self, words):
        self._words = words

    def words(self, path, clip_end=None):
        return self._words


def test_check_take_accepts_a_long_tail_end_and_rejects_a_repetition(tmp_path):
    sf = pytest.importorskip("soundfile")
    w = tone(1.0)
    w[-int(0.05 * SR):] *= np.linspace(1, 0, int(0.05 * SR), dtype=np.float32)
    path = tmp_path / "v.wav"
    sf.write(path, w, SR)
    asr = FakeASR([(0.0, 0.3, "Wait", 0.9), (0.3, 0.5, "for", 0.9), (0.5, 0.7, "the", 0.9), (0.7, 0.95, "turn.", 0.9)])
    problems, heard = vc.check_take(w, SR, path, "Wait for the turn.", asr)
    assert problems == [] and heard == "Wait for the turn."
    tail = "forcing EOS token, long_tail=tensor(True), alignment_repetition=tensor(False), token_repetition=False"
    problems, _ = vc.check_take(w, SR, path, "Wait for the turn.", asr, eos_events=[tail])
    assert problems == []                                                  # la « queue » est la fin normale du modele
    rep = "forcing EOS token, long_tail=tensor(False), alignment_repetition=tensor(False), token_repetition=True"
    problems, _ = vc.check_take(w, SR, path, "Wait for the turn.", asr, eos_events=[tail, rep])
    assert any("repetition" in p for p in problems)


def test_only_repetition_warnings_count_as_a_fault():
    assert vc.is_repetition("forcing EOS token, long_tail=tensor(False), alignment_repetition=tensor(False), token_repetition=True")
    assert vc.is_repetition("forcing EOS token, long_tail=tensor(False), alignment_repetition=tensor(True), token_repetition=False")
    assert not vc.is_repetition("forcing EOS token, long_tail=tensor(True), alignment_repetition=tensor(False), token_repetition=False")


def test_a_single_letter_word_is_not_merged_with_the_next_word():
    assert vc.normalize_words("Take a road.") == ["take", "a", "road"]
    assert vc.word_problems("Take a road.", "Take the road.")                # « a » remplace : signale
