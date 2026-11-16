"""Audit : la voix d'un montage est reecoutee dans SA langue (champ « lang » du manifest, sinon la langue par defaut).

Aucun modele : faux Whisper, signal synthetique, dossier de travail temporaire (vo/, out/, scan/batch_manifest.json).
"""
import json

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")
sf = pytest.importorskip("soundfile")

TAIT = "Et d'un coup, le monde se tait."
HEARD_FR = "Et d 'un coup, le monde se tait."                    # l'espace avant l'apostrophe, comme le vrai Whisper
TURN = "Wait for the turn."


def timed(text):
    """[(debut, fin, mot, probabilite)] : les mots d'un texte, un dixieme de seconde chacun."""
    return [(round(0.1 * k, 2), round(0.1 * k + 0.1, 2), word, 0.9) for k, word in enumerate(text.split())]


class LangASR:
    """Faux Whisper qui note la langue de chaque ecoute (le mixage par `text`, le fichier seul par `words`)."""

    def __init__(self, heard):
        self.heard, self.calls = heard, []

    def words(self, path, clip_end=None, lang=None):
        self.calls.append(("words", lang))
        return timed(self.heard)

    def text(self, path, clip_end=None, lang=None):
        self.calls.append(("text", lang))
        return self.heard


class OldASR:
    """Faux Whisper d'avant : aucun parametre de langue (l'anglais doit s'en passer)."""

    def __init__(self, heard):
        self.heard = heard

    def words(self, path, clip_end=None):
        return timed(self.heard)

    def text(self, path, clip_end=None):
        return self.heard


@pytest.fixture
def pc(load_script, tmp_path, monkeypatch):
    mod = load_script("scan/privacy_check.py")
    monkeypatch.chdir(tmp_path)                                  # l'audit lit vo/, out/ et scan/ par chemins relatifs
    monkeypatch.setattr(mod.mm_audio, "duration", lambda path: 1.0)
    monkeypatch.delenv("MM_VOICE_LANG", raising=False)
    monkeypatch.setattr(mod.mm_paths, "_L", {})
    return mod


def montage(tmp_path, line, **fields):
    """Un montage « m1 » : sa voix (un son qui finit en fondu), son texte attendu, son mp4 et sa ligne de manifest."""
    for d in ("vo", "out", "scan"):
        (tmp_path / d).mkdir(exist_ok=True)
    sr = 24000
    w = (0.5 * np.sin(2 * np.pi * 180 * np.arange(sr) / sr)).astype(np.float32)
    w[-int(0.05 * sr):] *= np.linspace(1, 0, int(0.05 * sr), dtype=np.float32)
    sf.write(tmp_path / "vo" / "m1.wav", w, sr)
    (tmp_path / "vo" / "m1.clone.txt").write_text(f"{line}\nentendu (Whisper) : ...\n", encoding="utf-8")
    (tmp_path / "out" / "m1.mp4").write_bytes(b"")
    (tmp_path / "scan" / "batch_manifest.json").write_text(
        json.dumps([{"id": "m0", "hook": "AUTRE"}, {"id": "m1", "hook": line, **fields}], ensure_ascii=False),
        encoding="utf-8")


def test_a_french_montage_is_relistened_in_french_and_passes(pc, tmp_path):
    montage(tmp_path, TAIT, lang="fr")
    asr = LangASR(HEARD_FR)
    assert pc.lang_of("m1") == "fr"
    assert pc.voice_check(asr, "m1") == ([], HEARD_FR)
    assert asr.calls == [("text", "fr"), ("words", "fr")]         # le mixage, puis le fichier seul


def test_the_default_language_is_used_when_the_manifest_has_none(pc, tmp_path, monkeypatch):
    montage(tmp_path, TAIT)
    assert pc.lang_of("m1") == "en" and pc.voice_check(LangASR(HEARD_FR), "m1")[0]     # en anglais : refuse
    monkeypatch.setenv("MM_VOICE_LANG", "fr")
    asr = LangASR(HEARD_FR)
    assert pc.lang_of("m1") == "fr" and pc.voice_check(asr, "m1") == ([], HEARD_FR)
    assert asr.calls == [("text", "fr"), ("words", "fr")]


def test_the_manifest_language_wins_over_the_default(pc, tmp_path, monkeypatch):
    montage(tmp_path, TURN, lang=" EN ")
    monkeypatch.setenv("MM_VOICE_LANG", "fr")
    assert pc.lang_of("m1") == "en" and pc.lang_of("m0") == "fr"
    assert pc.voice_check(OldASR(TURN), "m1") == ([], TURN)


def test_an_english_montage_is_audited_with_the_calls_of_before(pc, tmp_path):
    montage(tmp_path, TURN)
    assert pc.voice_check(OldASR(TURN), "m1") == ([], TURN)       # un ASR sans parametre de langue suffit
    problems, heard = pc.voice_check(OldASR("Wait for the turn. The turn."), "m1")
    assert heard == "Wait for the turn. The turn."
    assert problems == ["voix dans le mixage : repetition : « the turn »", "voix (fichier) : repetition : « the turn »"]


def test_a_french_fault_is_reported_for_the_mix_and_for_the_file(pc, tmp_path):
    montage(tmp_path, TAIT, lang="fr")
    problems, _ = pc.voice_check(LangASR(HEARD_FR + " Le monde se tait."), "m1")
    assert problems == ["voix dans le mixage : repetition : « le monde se tait »",
                        "voix (fichier) : repetition : « le monde se tait »"]


def test_an_unknown_manifest_language_fails_that_montage_only(pc, tmp_path):
    montage(tmp_path, TAIT, lang="de")
    problems, heard = pc.voice_check(LangASR(HEARD_FR), "m1")
    assert heard is None and len(problems) == 1 and "en, fr, ar" in problems[0]
