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


# ───────────────────────── langue de la voix (fr, en, ar) ─────────────────────────

FR_LINE = "Et d'un coup, roule."        # 5 mots dits (et, d, un, coup, roule) ; en francais un essai n'est jamais ralenti


class LangModel(FakeModel):
    """Faux modele qui note la langue demandee a chaque essai."""

    def __init__(self, bad=0):
        super().__init__(bad)
        self.langs = []

    def generate(self, line, **kw):
        self.langs.append(kw.get("language_id"))
        return super().generate(line, **kw)


class FrenchASR:
    """Faux Whisper francais : l'espace avant l'apostrophe, comme le vrai ; note la langue de chaque reecoute."""
    model = "fake"

    def __init__(self):
        self.langs = []

    def words(self, path, clip_end=None, lang=None):
        self.langs.append(lang)
        return [(0.0, 0.3, "Et", 0.9), (0.3, 0.4, "d", 0.9), (0.4, 0.6, "'un", 0.9), (0.6, 0.9, "coup,", 0.9),
                (0.9, 1.5, "roule.", 0.9)]

    def close(self):
        pass


def _french(vo, monkeypatch, tmp_path, model=None):
    model, asr = model or LangModel(), FrenchASR()
    monkeypatch.setattr(vo.mm_paths, "VO", tmp_path)
    monkeypatch.setattr(vo, "load_model", lambda: model)
    monkeypatch.setattr(vo, "ref_embedding", lambda m, r: None)
    monkeypatch.setattr(vo, "open_asr", lambda: asr)
    return model, asr


def test_cache_key_is_unchanged_for_english_and_carries_the_language_otherwise(vo):
    import hashlib
    line = "Wait for the turn."
    old = hashlib.sha1(line.encode("utf-8")).hexdigest()[:10]
    assert vo.cache_key(line) == old == vo.cache_key(line, "en")                      # les voix deja validees restent
    sep = chr(0x1F)                                                                   # separateur d'unite : jamais dans une phrase
    assert vo.cache_key(line, "fr") == hashlib.sha1(f"fr{sep}{line}".encode("utf-8")).hexdigest()[:10] != old
    assert vo.cache_key(line, "ar") not in (old, vo.cache_key(line, "fr"))
    assert vo.cache_key("Roule.", "fr") != vo.cache_key("fr:Roule.", "en")            # plus de collision avec « fr:... »
    assert vo.cache_key("Roule.", "fr") not in (vo.cache_key("fr:Roule."), vo.cache_key("fr Roule."), vo.cache_key("frRoule."))


def test_pov_is_spelled_in_english_only(vo):
    assert vo.hook_line({"hook": "POV: NO TRAFFIC NO PLAN"}, "en") == "P.O.V., no traffic no plan."
    assert vo.hook_line({"hook": "POV: TU ROULES"}, "fr") == "POV: TU ROULES."


@pytest.mark.parametrize("hook,line", [
    ("TU VIENS ?", "TU VIENS ?"),                                     # pas de point apres « ? »
    ("PARIS-DAKAR EN BMW GS", "PARIS-DAKAR EN BMW GS."),              # les capitales restent comme ecrites
    ("et d'un coup, le monde se tait", "Et d'un coup, le monde se tait."),
    ("Alors roule !", "Alors roule !"),
    ("Et puis...", "Et puis..."),
    ("Et puis…", "Et puis…"),
    ("Roule.", "Roule."),
    ("  élan de Paris à Dakar  ", "Élan de Paris à Dakar."),
    ("هل تأتي؟", "هل تأتي؟"),                                           # point d'interrogation arabe
])
def test_a_hook_in_another_language_is_said_as_written(vo, hook, line):
    assert vo.hook_line({"hook": hook}, "fr") == line == vo.hook_line({"hook": hook}, "ar")


def test_the_english_hook_rule_is_the_one_of_before(vo):
    assert vo.hook_line({"hook": "TU VIENS ?"}) == "Tu viens ?."
    assert vo.hook_line({"hook": "PARIS-DAKAR EN BMW GS"}, "en") == "Paris-dakar en bmw gs."
    assert vo.hook_line({"hook": "Wait..."}) == "Wait."


# ───────────────────────── debit par langue ─────────────────────────

def test_the_default_pace_is_per_language(vo):
    assert vo.WORDS_PER_S == {"en": 2.5, "fr": 3.2, "ar": 2.5}


def test_the_target_duration_counts_the_words_that_are_said(vo):
    assert vo.target_s("Tu viens ? Alors : roule !", 3.2, "fr") == pytest.approx(4 / 3.2)   # « ? » et « : » : pas des mots
    assert vo.target_s("150 chevaux", 3.2, "fr") == pytest.approx(vo.MIN_SPEECH)            # 3 mots dits : plancher
    assert vo.target_s("Cent cinquante chevaux, deux roues, une ligne.", 3.2, "fr") == pytest.approx(7 / 3.2)
    assert vo.target_s("الطريق أمامك ، الآن !", 2.5, "ar") == pytest.approx(vo.MIN_SPEECH)       # 3 mots
    assert vo.target_s("Roule.", 3.2, "fr") == vo.MIN_SPEECH


def test_the_english_target_is_the_one_of_before(vo):
    assert vo.target_s("Wait for the turn.", 2.5) == pytest.approx(1.6) == vo.target_s("Wait for the turn.", 2.5, "en")
    assert vo.target_s("No-traffic day, no plan.", 2.5) == pytest.approx(4 / 2.5)     # decoupage aux espaces, comme avant
    assert vo.target_s("Go.", 2.5) == vo.MIN_SPEECH


def test_a_voice_in_another_language_is_never_slowed_down(vo, monkeypatch):
    assert vo.pace_rate(1.0, 2.0, "fr") == 1.0 == vo.pace_rate(1.0, 2.0, "ar")        # trop rapide : laisse tel quel
    assert vo.pace_rate(3.0, 2.0, "fr") == pytest.approx(1.2)                         # trop lent : accelere, comme en anglais
    assert vo.pace_rate(1.8, 2.0, "fr") == 1.0
    assert vo.pace_rate(1.0, 2.0, "en") == pytest.approx(0.85) == vo.pace_rate(1.0, 2.0)   # anglais : bornes d'avant
    monkeypatch.setattr(vo.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ffmpeg appele")))
    info = {"speech_s": 1.0, "target_s": 2.0, "lang": "fr"}
    assert vo.fix_pace("unused.wav", info) == info                                    # aucun ralenti, aucun ffmpeg
    assert vo.candidate_score(1.0, 2.0, 0.1, lang="fr") == pytest.approx(0.5)         # ecart a la cible, sans etirement
    assert vo.candidate_score(1.0, 2.0, 0.1) == pytest.approx(0.5018, abs=1e-3)       # anglais : ralenti de 15 % compte
    assert vo.stored_score({"speech_s": 1.0, "target_s": 2.0, "gap_s": 0.1, "lang": "fr"}) == pytest.approx(0.5)
    assert vo.stored_score({"speech_s": 1.0, "target_s": 2.0, "gap_s": 0.1}) == pytest.approx(0.5018, abs=1e-3)


def fake_ffmpeg(vo, monkeypatch):
    """Faux ffmpeg (atempo) : recopie l'entree vers la sortie et note l'appel."""
    import shutil
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        shutil.copyfile(cmd[cmd.index("-i") + 1], cmd[-1])
        return type("Done", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(vo.subprocess, "run", run)
    return calls


def test_a_french_take_that_is_too_slow_is_sped_up_and_relistened_in_french(vo, tmp_path, monkeypatch):
    model, asr = _french(vo, monkeypatch, tmp_path)
    calls = fake_ffmpeg(vo, monkeypatch)
    logs = []
    done, ko = vo.make_many([FR_LINE], "ref.wav", 1, 4.0, log=logs.append, lang="fr")      # cible 1,25 s, essai de 1,6 s
    assert ko == [] and len(calls) == 1 and "atempo=1.200" in calls[0]
    assert done[FR_LINE][1]["paced"] == pytest.approx(1.2) and done[FR_LINE][1]["lang"] == "fr"
    assert asr.langs == ["fr", "fr"]                       # l'essai, puis l'essai accelere : les deux en francais


def test_a_french_take_that_is_too_fast_is_kept_as_it_is(vo, tmp_path, monkeypatch):
    _french(vo, monkeypatch, tmp_path)
    calls = fake_ffmpeg(vo, monkeypatch)
    done, ko = vo.make_many([FR_LINE], "ref.wav", 1, 1.0, log=lambda *_: None, lang="fr")   # cible 5 s, essai de 1,6 s
    assert ko == [] and calls == [] and "paced" not in done[FR_LINE][1]
    assert done[FR_LINE][1]["target_s"] == 5.0 and done[FR_LINE][1]["speech_s"] == pytest.approx(1.6, abs=0.03)


def test_an_english_take_that_is_too_fast_is_still_slowed_and_relistened(vo, tmp_path, monkeypatch):
    _two_phase(vo, monkeypatch, tmp_path, FakeModel(bad=0))
    calls = fake_ffmpeg(vo, monkeypatch)
    done, ko = vo.make_many(["Wait for the turn."], "ref.wav", 1, 1.0, log=lambda *_: None)   # cible 4 s, essai de 1,6 s
    info = done["Wait for the turn."][1]
    assert ko == [] and len(calls) == 1 and "atempo=0.850" in calls[0]
    assert info["paced"] == pytest.approx(0.85) and info["target_s"] == 4.0 and info["heard"] == "Wait for the turn."


def test_pick_generates_and_listens_in_the_requested_language(vo, tmp_path, monkeypatch):
    monkeypatch.setattr(vo.mm_paths, "VO", tmp_path)
    model, asr = LangModel(), FrenchASR()
    best, target, rejected = vo.pick(model, FR_LINE, "ref.wav", 1, 2.0, asr=asr, log=lambda *_: None, lang="fr")
    assert best is not None and rejected == [] and best[-1] == "Et d 'un coup, roule."
    assert model.langs == ["fr"] and asr.langs == ["fr"] and target == pytest.approx(5 / 2.0)
    assert best[0] == pytest.approx(abs(best[2] - target) / target)       # essai rapide : note sans ralenti, en francais


def test_the_take_is_generated_in_the_requested_language(vo):
    model = LangModel()
    vo.generate_take(model, "Wait for the turn.", "ref.wav", 0.3, 0.5)
    vo.generate_take(model, FR_LINE, "ref.wav", 0.3, 0.5, lang="fr")
    vo.generate_take(model, "الطريق أمامك.", "ref.wav", 0.3, 0.5, lang="ar")
    assert model.langs == ["en", "fr", "ar"]


def test_make_many_generates_validates_and_caches_in_french(vo, tmp_path, monkeypatch):
    model, asr = _french(vo, monkeypatch, tmp_path)
    done, ko = vo.make_many([FR_LINE], "ref.wav", 2, 2.5, log=lambda *_: None, lang="fr")
    assert ko == [] and model.langs == ["fr", "fr"] and asr.langs and set(asr.langs) == {"fr"}
    wav, info, cached = done[FR_LINE]
    assert wav.name == f"{vo.cache_key(FR_LINE, 'fr')}.wav" and wav.exists() and not cached
    assert info["lang"] == "fr" and info["checked"] == vo.CHECKED and info["heard"] == "Et d 'un coup, roule."
    done, _ = vo.make_many([FR_LINE], "ref.wav", 2, 2.5, log=lambda *_: None, lang="fr")
    assert done[FR_LINE][2] is True and len(model.langs) == 2                         # reprise : rien de regenere


def test_a_voice_cached_in_one_language_is_not_reused_for_another(vo, tmp_path, monkeypatch):
    _french(vo, monkeypatch, tmp_path)
    vo.make_many([FR_LINE], "ref.wav", 1, 2.5, log=lambda *_: None, lang="fr")
    assert vo._validated(FR_LINE, tmp_path / "_cache", "fr") and not vo._validated(FR_LINE, tmp_path / "_cache")
    assert not vo._validated(FR_LINE, tmp_path / "_cache", "ar")


def test_english_stays_the_language_when_none_is_given(vo, tmp_path, monkeypatch):
    model = LangModel()
    _two_phase(vo, monkeypatch, tmp_path, model)
    done, _ = vo.make_many(["Wait for the turn."], "ref.wav", 1, 2.5, log=lambda *_: None)
    wav, info, _ = done["Wait for the turn."]
    assert model.langs == ["en"] and info["lang"] == "en" and wav.name == f"{vo.cache_key('Wait for the turn.')}.wav"


def test_the_job_file_carries_the_language_to_both_phases(vo, tmp_path, monkeypatch):
    model, asr = _french(vo, monkeypatch, tmp_path)
    jobs = []

    def run_phase(cmd, **kw):                 # a la place du processus fils : la phase lit la langue dans le fichier
        phase, job_path = cmd[cmd.index("--phase") + 1], cmd[cmd.index("--phase") + 2]
        jobs.append(json.loads(open(job_path, encoding="utf-8").read())["lang"])
        if phase == "generate":
            code = vo.phase_generate(job_path, "ref.wav", log=lambda *_: None)
        else:
            code = vo.phase_validate(job_path, log=lambda *_: None)
        return type("Done", (), {"returncode": code})()

    monkeypatch.setattr(vo.subprocess, "run", run_phase)
    done, ko = vo.make_many([FR_LINE], "ref.wav", 2, 2.5, log=lambda *_: None, separate=True, lang="fr")
    assert ko == [] and jobs == ["fr", "fr"]
    assert model.langs == ["fr", "fr"] and set(asr.langs) == {"fr"} and done[FR_LINE][1]["lang"] == "fr"


def test_a_job_file_without_a_language_is_english(vo, tmp_path, monkeypatch):
    model = LangModel()
    _two_phase(vo, monkeypatch, tmp_path, model)
    takes = tmp_path / "_cache" / "_essais"
    takes.mkdir(parents=True)
    job = takes / "job.json"
    job.write_text(json.dumps({"lines": ["Wait for the turn."], "tries": 1, "wps": 2.5, "seed0": 1000,
                               "dir": str(takes), "takes": {}}), encoding="utf-8")
    assert vo.phase_generate(job, "ref.wav", log=lambda *_: None) == 0 and model.langs == ["en"]
    assert vo.phase_validate(job, log=lambda *_: None) == 0
    assert vo._validated("Wait for the turn.", tmp_path / "_cache")


def test_verify_cache_relistens_each_voice_in_its_own_language(vo, tmp_path, monkeypatch):
    _, asr = _french(vo, monkeypatch, tmp_path)
    vo.make_many([FR_LINE], "ref.wav", 1, 2.5, log=lambda *_: None, lang="fr")
    asr.langs.clear()
    assert vo.verify_cache(asr, log=lambda *_: None) == 0 and asr.langs == ["fr"]   # relue en francais : valide


def test_the_t3_checkpoint_is_passed_only_to_a_chatterbox_that_accepts_it(vo, monkeypatch):
    def old_loader(device):
        return device

    def new_loader(device, t3_model="v2"):
        return device, t3_model

    monkeypatch.delenv("MM_TTS_T3", raising=False)
    assert vo.pretrained_kwargs(old_loader, "cpu") == {"device": "cpu"} == vo.pretrained_kwargs(new_loader, "cpu")
    monkeypatch.setenv("MM_TTS_T3", "v3")
    assert vo.pretrained_kwargs(new_loader, "cuda") == {"device": "cuda", "t3_model": "v3"}
    with pytest.raises(SystemExit, match="MM_TTS_T3"):
        vo.pretrained_kwargs(old_loader, "cuda")


def _main_with_fake_make_many(vo, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(vo.mm_paths, "VO", tmp_path / "vo")
    monkeypatch.setattr(vo, "make_many",
                        lambda lines, ref, *a, **k: calls.append((lines, ref, k.get("lang"))) or ({}, lines))
    lines = tmp_path / "lines.txt"
    lines.write_text(FR_LINE + "\n", encoding="utf-8")
    for name in ("MM_VOICE_LANG", "MM_VOICE_REF", "MM_VOICE_REF_FR", "MM_VOICE_REF_EN", "MM_VOICE_REF_AR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(vo.mm_paths, "_L", {})
    return calls, lines


def _french_reference(monkeypatch, tmp_path):
    ref = tmp_path / "ref_fr.wav"
    ref.write_bytes(b"RIFF")
    monkeypatch.setenv("MM_VOICE_REF_FR", str(ref))
    return ref


def _manifest(monkeypatch, tmp_path, entries):
    """Manifest de montages dans un dossier de travail a part (main le lit par un chemin relatif)."""
    (tmp_path / "scan").mkdir(exist_ok=True)
    (tmp_path / "scan" / "batch_manifest.json").write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    monkeypatch.chdir(tmp_path)


def test_main_uses_the_language_and_the_reference_of_that_language(vo, tmp_path, monkeypatch, capsys):
    calls, lines = _main_with_fake_make_many(vo, monkeypatch, tmp_path)
    ref = tmp_path / "ref_fr.wav"
    ref.write_bytes(b"RIFF")
    monkeypatch.setenv("MM_VOICE_REF_FR", str(ref))
    assert vo.main(["--lang", "fr", "--lines-file", str(lines)]) == 1                 # faux make_many : rien de valide
    monkeypatch.setenv("MM_VOICE_LANG", "fr")
    vo.main(["--lines-file", str(lines)])                                             # sans --lang : langue par defaut
    assert calls == [([FR_LINE], ref, "fr"), ([FR_LINE], ref, "fr")]
    capsys.readouterr()


def test_main_refuses_an_unknown_language(vo, tmp_path, monkeypatch):
    calls, lines = _main_with_fake_make_many(vo, monkeypatch, tmp_path)
    with pytest.raises(SystemExit, match="en.*fr.*ar"):
        vo.main(["--lang", "de", "--lines-file", str(lines)])
    assert calls == []


def test_lang_without_a_value_names_the_allowed_values(vo, tmp_path, monkeypatch):
    calls, lines = _main_with_fake_make_many(vo, monkeypatch, tmp_path)
    with pytest.raises(SystemExit, match="--lang.*en.*fr.*ar"):
        vo.main(["--lines-file", str(lines), "--lang"])                               # --lang en dernier : pas d'IndexError
    with pytest.raises(SystemExit, match="en.*fr.*ar"):
        vo.main(["--lang", "--force"])                                                # une option a la place de la valeur
    assert calls == []


def test_the_language_option_is_lower_cased_and_the_hooks_are_read_in_that_language(vo, tmp_path, monkeypatch, capsys):
    calls, _ = _main_with_fake_make_many(vo, monkeypatch, tmp_path)
    ref = _french_reference(monkeypatch, tmp_path)
    _manifest(monkeypatch, tmp_path, [{"id": "m1", "hook": "POV: tu roules ?"}, {"id": "m2", "hook": "Autre chose"}])
    vo.main(["--lang", "FR", "--ids", "m1"])
    assert calls == [(["POV: tu roules ?"], ref, "fr")]                               # ni « P.O.V., », ni point apres « ? »
    capsys.readouterr()


def test_the_default_pace_of_the_language_is_used_unless_words_per_s_is_given(vo, tmp_path, monkeypatch, capsys):
    _, lines = _main_with_fake_make_many(vo, monkeypatch, tmp_path)
    _french_reference(monkeypatch, tmp_path)
    en_ref = tmp_path / "ref_en.wav"
    en_ref.write_bytes(b"RIFF")
    monkeypatch.setenv("MM_VOICE_REF_EN", str(en_ref))
    paces = []
    monkeypatch.setattr(vo, "make_many", lambda ls, ref, tries, wps, *a, **k: paces.append((k["lang"], wps)) or ({}, ls))
    vo.main(["--lang", "fr", "--lines-file", str(lines)])
    vo.main(["--lang", "en", "--lines-file", str(lines)])
    vo.main(["--lines-file", str(lines)])                                             # langue par defaut : anglais
    vo.main(["--lang", "fr", "--words-per-s", "2.8", "--lines-file", str(lines)])
    assert paces == [("fr", 3.2), ("en", 2.5), ("en", 2.5), ("fr", 2.8)]
    capsys.readouterr()


def test_another_language_never_borrows_the_default_english_reference(vo, tmp_path, monkeypatch, capsys):
    calls, lines = _main_with_fake_make_many(vo, monkeypatch, tmp_path)
    default = tmp_path / "ref_en_clean.wav"
    default.write_bytes(b"RIFF")
    monkeypatch.setattr(vo.mm_paths, "VOICE_REF", default)                            # la reference par defaut, en anglais
    with pytest.raises(SystemExit, match="MM_VOICE_REF_FR.*voice_ref_fr"):
        vo.main(["--lang", "fr", "--lines-file", str(lines)])
    assert calls == []
    vo.main(["--lang", "en", "--lines-file", str(lines)])                             # en anglais : elle sert, comme avant
    monkeypatch.setenv("MM_VOICE_REF", str(default))                                  # reference commune IMPOSEE : elle sert
    vo.main(["--lang", "fr", "--lines-file", str(lines)])
    assert calls == [([FR_LINE], default, "en"), ([FR_LINE], default, "fr")]
    capsys.readouterr()


def test_a_missing_reference_file_stops_the_generation(vo, tmp_path, monkeypatch):
    calls, lines = _main_with_fake_make_many(vo, monkeypatch, tmp_path)
    monkeypatch.setenv("MM_VOICE_REF_FR", str(tmp_path / "absent.wav"))
    with pytest.raises(SystemExit, match="absente.*absent.wav"):
        vo.main(["--lang", "fr", "--lines-file", str(lines)])
    assert calls == []


def test_verify_cache_and_fix_cache_need_no_reference(vo, tmp_path, monkeypatch, capsys):
    _main_with_fake_make_many(vo, monkeypatch, tmp_path)
    monkeypatch.setattr(vo.mm_paths, "VOICE_REF", tmp_path / "absent.wav")            # aucune reference anglaise
    _french_reference(monkeypatch, tmp_path)                                          # seule la francaise est reglee
    opened = []
    monkeypatch.setattr(vo, "open_asr", lambda: opened.append(1) or FrenchASR())
    assert vo.main(["--verify-cache"]) == 0 and vo.main(["--fix-cache"]) == 0         # langue par defaut : anglais
    monkeypatch.delenv("MM_VOICE_REF_FR")
    assert vo.main(["--lang", "fr", "--verify-cache"]) == 0 and vo.main(["--lang", "fr", "--fix-cache"]) == 0
    assert len(opened) == 2
    capsys.readouterr()


def test_refine_relaunches_only_the_mediocre_voices_of_the_language(vo, tmp_path, monkeypatch, capsys):
    calls, _ = _main_with_fake_make_many(vo, monkeypatch, tmp_path)
    ref = _french_reference(monkeypatch, tmp_path)
    cache = tmp_path / "vo" / "_cache"
    cache.mkdir(parents=True)
    slow = {"speech_s": 4.0, "target_s": 2.0, "checked": vo.CHECKED}                  # deux fois trop lente : mediocre
    voices = {"a": {**slow, "line": "Roule lentement.", "lang": "fr"},
              "b": {**slow, "line": "Ride slowly."},                                   # sans langue : anglais
              "c": {**slow, "line": "اركب ببطء.", "lang": "ar"},
              "d": {"speech_s": 2.0, "target_s": 2.0, "checked": vo.CHECKED, "line": "Roule bien.", "lang": "fr"},
              "e": {**slow, "line": "Pas encore validee.", "lang": "fr", "checked": None}}
    for name, info in voices.items():
        (cache / f"{name}.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    seen = []
    monkeypatch.setattr(vo, "make_many", lambda ls, r, tries, wps, **k: seen.append((ls, r, tries, wps, k)) or ({}, ls))
    assert vo.main(["--lang", "fr", "--refine"]) == 0
    assert seen == [(["Roule lentement."], ref, 12, 3.2, {"force": True, "separate": True, "lang": "fr"})]
    assert calls == []
    capsys.readouterr()


def test_the_phase_child_takes_its_language_and_reference_from_the_job_file(vo, tmp_path, monkeypatch):
    _main_with_fake_make_many(vo, monkeypatch, tmp_path)
    ref_fr = _french_reference(monkeypatch, tmp_path)
    ref_en = tmp_path / "ref_en.wav"
    ref_en.write_bytes(b"RIFF")
    monkeypatch.setenv("MM_VOICE_REF_EN", str(ref_en))
    monkeypatch.setenv("MM_VOICE_LANG", "en")                                         # le fils ne suit PAS l'environnement
    job = tmp_path / "job.json"
    job.write_text(json.dumps({"lines": [], "lang": "fr", "tries": 1, "wps": 3.2, "seed0": 1000, "dir": str(tmp_path),
                               "takes": {}}), encoding="utf-8")
    seen = []
    monkeypatch.setattr(vo, "phase_generate", lambda job_path, ref: seen.append(("generate", job_path, ref)) or 0)
    monkeypatch.setattr(vo, "phase_validate", lambda job_path: seen.append(("validate", job_path)) or 0)
    assert vo.main(["--phase", "generate", str(job)]) == 0
    assert vo.main(["--phase", "validate", str(job), "--lang", "en"]) == 0             # ni --lang
    assert seen == [("generate", str(job), ref_fr), ("validate", str(job))]
    job.write_text(json.dumps({"lines": [], "tries": 1, "wps": 2.5, "seed0": 1000, "dir": str(tmp_path), "takes": {}}),
                   encoding="utf-8")
    monkeypatch.setenv("MM_VOICE_LANG", "fr")
    assert vo.main(["--phase", "generate", str(job)]) == 0                            # fichier sans langue : anglais
    assert seen[-1] == ("generate", str(job), ref_en)


def test_the_clone_file_records_the_language_and_the_pace_counts_spoken_words(vo, tmp_path, monkeypatch, capsys):
    _main_with_fake_make_many(vo, monkeypatch, tmp_path)
    _french_reference(monkeypatch, tmp_path)
    wav = tmp_path / "voice.wav"
    wav.write_bytes(b"RIFF....")
    info = {"heard": "Et d 'un coup, roule.", "speech_s": 2.0, "target_s": 1.56, "cfg": 0.3, "exag": 0.5, "gap_s": 0.0,
            "sim": 0.91, "rejected_takes": 2}
    monkeypatch.setattr(vo, "make_many", lambda ls, *a, **k: ({ln: (wav, info, False) for ln in ls}, []))
    _manifest(monkeypatch, tmp_path, [{"id": "m1", "hook": FR_LINE}])
    assert vo.main(["--lang", "fr"]) == 0
    text = (tmp_path / "vo" / "m1.clone.txt").read_text(encoding="utf-8").splitlines()
    assert text[0] == FR_LINE and text[1] == "entendu (Whisper) : Et d 'un coup, roule." and text[-1] == "langue : fr"
    assert (tmp_path / "vo" / "m1.wav").read_bytes() == wav.read_bytes()
    assert "2.50 mots/s" in capsys.readouterr().out                                   # 5 mots dits en 2 s


def test_the_english_clone_file_keeps_its_first_lines_and_its_pace(vo, tmp_path, monkeypatch, capsys):
    _main_with_fake_make_many(vo, monkeypatch, tmp_path)
    ref = tmp_path / "ref_en.wav"
    ref.write_bytes(b"RIFF")
    monkeypatch.setenv("MM_VOICE_REF_EN", str(ref))
    wav = tmp_path / "voice.wav"
    wav.write_bytes(b"RIFF....")
    info = {"heard": "No traffic day, no plan.", "speech_s": 2.0, "target_s": 1.6, "cfg": 0.3, "exag": 0.5,
            "gap_s": 0.0, "sim": 0.91}
    monkeypatch.setattr(vo, "make_many", lambda ls, *a, **k: ({ln: (wav, info, True) for ln in ls}, []))
    _manifest(monkeypatch, tmp_path, [{"id": "m1", "hook": "NO-TRAFFIC DAY, NO PLAN"}])
    assert vo.main([]) == 0
    text = (tmp_path / "vo" / "m1.clone.txt").read_text(encoding="utf-8")
    assert text.startswith("No-traffic day, no plan.\nentendu (Whisper) : No traffic day, no plan.\n"
                           "parole 2.0s (cible 1.6s), cfg 0.3, exagg. 0.5, plus long silence 0.0s, ressemblance 0.91, "
                           "essais refuses 0\n")
    assert text.splitlines()[-1] == "langue : en"
    assert "2.00 mots/s" in capsys.readouterr().out                                   # 4 morceaux en 2 s, comme avant


def test_the_device_of_the_relistening_is_printed_when_it_starts(vo, monkeypatch):
    class Server:
        model, device = "large-v3", "cuda"

        def __enter__(self):
            return self

    monkeypatch.setattr(vo.mm_voicecheck, "ASR", Server)
    lines = []
    assert isinstance(vo.open_asr(log=lines.append), Server)
    assert lines == ["reecoute Whisper large-v3 sur cuda"]
    Server.device = "cpu"
    vo.open_asr(log=lines.append)
    assert lines[-1] == "reecoute Whisper large-v3 sur cpu"
