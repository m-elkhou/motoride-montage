"""Voix clonee : texte dit, mesure du debit et du silence interne (pures, sans modele ni GPU)."""
import json

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("soundfile")


@pytest.fixture
def vo(load_script):
    return load_script("scan/gen_vo_clone.py")


def tone(seconds, sr=24000, amp=0.5):
    return (amp * np.sin(2 * np.pi * 180 * np.arange(int(seconds * sr)) / sr)).astype(np.float32)


def test_hook_is_a_sentence_and_pov_is_spelled(vo):
    assert vo.hook_line({"hook": "WAIT FOR THE TURN"}) == "Wait for the turn."
    assert vo.hook_line({"hook": "POV: NO TRAFFIC NO PLAN"}) == "P.O.V., no traffic no plan."


def test_speech_duration_ignores_silence_at_the_edges(vo):
    sr = 24000
    w = np.concatenate([np.zeros(sr // 2, np.float32), tone(2.0), np.zeros(sr, np.float32)])
    dur, gap = vo.speech_stats(w, sr)
    assert 1.95 <= dur <= 2.05 and gap < 0.01


def test_a_gap_inside_the_sentence_is_measured(vo):
    sr = 24000
    w = np.concatenate([tone(1.0), np.zeros(int(0.6 * sr), np.float32), tone(1.0)])
    dur, gap = vo.speech_stats(w, sr)
    assert 2.55 <= dur <= 2.65 and 0.55 <= gap <= 0.65


def test_trim_and_fade_keeps_the_voice_and_avoids_clicks(vo):
    sr = 24000
    w = np.concatenate([np.zeros(sr, np.float32), tone(1.0), np.zeros(sr, np.float32)])
    out = vo.trim_and_fade(w.copy(), sr)
    assert 1.0 <= len(out) / sr <= 1.2                                   # la resonance du dernier mot est gardee
    assert abs(float(out[0])) < 0.01 and abs(float(out[-1])) < 0.01
    assert float(np.max(np.abs(out))) == pytest.approx(0.9, abs=0.02)


def test_pace_is_left_alone_when_close_to_the_target(vo):
    info = {"speech_s": 2.0, "target_s": 2.2}
    assert vo.fix_pace("unused.wav", info) == info
    paced = {"speech_s": 1.0, "target_s": 2.0, "paced": 0.7}
    assert vo.fix_pace("unused.wav", paced) == paced                   # une seule correction


def test_pace_rate_only_corrects_outside_the_tolerance(vo):
    assert vo.pace_rate(2.0, 2.0) == 1.0
    assert vo.pace_rate(1.8, 2.0) == 1.0                                # dans la tolerance : on ne touche pas
    assert vo.pace_rate(1.0, 2.0) == pytest.approx(0.85)                # tres rapide : ralenti, mais jamais plus de 15 %
    assert vo.pace_rate(3.0, 2.0) == pytest.approx(1.2)                 # trop lent : accelere au plus de 20 %
    assert vo.pace_rate(0.0, 2.0) == 1.0


def test_candidate_score_prefers_the_voice_that_sounds_like_the_owner(vo):
    close_but_fast = vo.candidate_score(1.7, 2.0, 0.1, sim=0.93)
    perfect_pace_other_voice = vo.candidate_score(2.0, 2.0, 0.1, sim=0.80)
    assert close_but_fast < perfect_pace_other_voice                      # la ressemblance pese plus qu'un debit parfait
    assert vo.candidate_score(2.0, 2.0, 0.1, sim=0.95) == pytest.approx(0.0)


def test_candidate_score_penalises_stretching_and_gaps(vo):
    unstretched = vo.candidate_score(2.0, 2.0, 0.1, sim=0.92)
    stretched = vo.candidate_score(1.2, 2.0, 0.1, sim=0.92)             # rate 0.7 : corrige mais artificiel
    assert unstretched < stretched
    assert vo.candidate_score(2.0, 2.0, 0.9, sim=0.92) > unstretched    # un trou au milieu de la phrase
    assert vo.candidate_score(2.0, 2.0, 0.1) == pytest.approx(0.0)       # sans mesure de ressemblance : pas de penalite


def test_stored_score_counts_the_stretch_already_applied(vo):
    base = {"speech_s": 2.0, "target_s": 2.0, "gap_s": 0.1, "sim": 0.92}
    assert vo.stored_score(base) == pytest.approx(0.0)
    assert vo.stored_score({**base, "paced": 0.7}) == pytest.approx(0.18)


class FakeModel:
    """Faux modele de voix : un son propre ; les `bad` premiers essais declenchent la fin forcee de Chatterbox."""
    sr = 24000

    def __init__(self, bad):
        self.bad, self.calls = bad, 0

    def generate(self, line, **kw):
        import logging
        self.calls += 1
        if self.calls <= self.bad:
            logging.getLogger("chatterbox.models.t3.inference.alignment_stream_analyzer").warning(
                "forcing EOS token, long_tail=tensor(False), alignment_repetition=tensor(False), token_repetition=True")
        w = tone(1.6)
        w[-1200:] *= np.linspace(1, 0, 1200, dtype=np.float32)
        return w


class FakeASR:
    def words(self, path, clip_end=None):
        return [(0.0, 0.3, "Wait", 0.9), (0.3, 0.5, "for", 0.9), (0.5, 0.7, "the", 0.9), (0.7, 1.5, "turn.", 0.9)]


def test_pick_never_keeps_a_take_the_model_had_to_cut(vo, tmp_path, monkeypatch):
    monkeypatch.setattr(vo.mm_paths, "VO", tmp_path)
    model = FakeModel(bad=2)
    best, target, rejected = vo.pick(model, "Wait for the turn.", "ref.wav", 3, 2.5, asr=FakeASR(), log=lambda *_: None)
    assert [r["essai"] for r in rejected] == [1, 2]                        # les 2 essais coupes sont refuses
    assert best is not None and best[-1] == "Wait for the turn."


def test_pick_returns_nothing_when_no_take_passes(vo, tmp_path, monkeypatch):
    monkeypatch.setattr(vo.mm_paths, "VO", tmp_path)
    best, _, rejected = vo.pick(FakeModel(bad=99), "Wait for the turn.", "ref.wav", 2, 2.5, asr=FakeASR(),
                                max_tries=4, log=lambda *_: None)
    assert best is None and len(rejected) == 4                             # jamais une voix fautive par defaut


def test_pick_refuses_to_run_without_listening(vo):
    with pytest.raises(ValueError):
        vo.pick(FakeModel(bad=0), "Wait for the turn.", "ref.wav", 1, 2.5, asr=None)


class ClosableASR(FakeASR):
    model = "fake"

    def close(self):
        pass


def _two_phase(vo, monkeypatch, tmp_path, model):
    monkeypatch.setattr(vo.mm_paths, "VO", tmp_path)
    monkeypatch.setattr(vo, "load_model", lambda: model)
    monkeypatch.setattr(vo, "ref_embedding", lambda m, r: None)
    monkeypatch.setattr(vo, "open_asr", lambda: ClosableASR())


def test_make_many_retries_a_line_until_a_take_passes(vo, tmp_path, monkeypatch):
    model = FakeModel(bad=6)                                               # tout le 1er tour deborde
    _two_phase(vo, monkeypatch, tmp_path, model)
    done, ko = vo.make_many(["Wait for the turn."], "ref.wav", 6, 2.5, log=lambda *_: None)
    assert ko == [] and "Wait for the turn." in done
    wav, info, cached = done["Wait for the turn."]
    assert wav.exists() and info["checked"] == vo.CHECKED and info["rejected_takes"] == 6 and not cached
    assert not (tmp_path / "_cache" / "_essais").exists()                  # les essais temporaires sont effaces


def test_make_many_never_caches_a_line_that_always_fails(vo, tmp_path, monkeypatch):
    _two_phase(vo, monkeypatch, tmp_path, FakeModel(bad=999))
    done, ko = vo.make_many(["Wait for the turn."], "ref.wav", 2, 2.5, rounds=2, log=lambda *_: None)
    assert done == {} and ko == ["Wait for the turn."]
    assert not list((tmp_path / "_cache").glob("*.wav"))                   # aucune voix fautive gardee


def test_make_many_reuses_a_validated_voice_without_loading_any_model(vo, tmp_path, monkeypatch):
    _two_phase(vo, monkeypatch, tmp_path, FakeModel(bad=0))
    vo.make_many(["Wait for the turn."], "ref.wav", 1, 2.5, log=lambda *_: None)
    monkeypatch.setattr(vo, "load_model", lambda: (_ for _ in ()).throw(AssertionError("modele charge pour rien")))
    done, _ = vo.make_many(["Wait for the turn."], "ref.wav", 1, 2.5, log=lambda *_: None)
    assert done["Wait for the turn."][2] is True


def test_forcing_keeps_the_old_validated_voice_when_no_new_take_passes(vo, tmp_path, monkeypatch):
    _two_phase(vo, monkeypatch, tmp_path, FakeModel(bad=0))
    vo.make_many(["Wait for the turn."], "ref.wav", 1, 2.5, log=lambda *_: None)
    _two_phase(vo, monkeypatch, tmp_path, FakeModel(bad=999))
    done, ko = vo.make_many(["Wait for the turn."], "ref.wav", 1, 2.5, force=True, rounds=1, log=lambda *_: None)
    assert ko == ["Wait for the turn."] and done == {}
    meta = json.loads(next((tmp_path / "_cache").glob("*.json")).read_text(encoding="utf-8"))
    assert meta["checked"] == vo.CHECKED                                   # l'ancienne voix validee reste valide
