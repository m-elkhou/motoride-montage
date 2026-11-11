"""Porte anonymat et piste son : regles pures, sans modele, sans reseau, sans ffmpeg."""
import json

import mm_audio as A
import mm_privacy as P
import upload_short as u


# ---------- visages : un visage visible fait refuser l'image ----------
def test_strong_face_is_refused_even_if_small_but_not_tiny():
    assert P.face_hits([(0, 0, 40, 40, 0.9)], 1080)
    assert not P.face_hits([(0, 0, 25, 25, 0.9)], 1080)          # < 3 % de la largeur : trop petit pour identifier


def test_low_score_detections_are_noise_not_faces():
    """Verifie sur des recadrages : sous 0,55 ce sont des mains, tableaux de bord, arbres, retroviseurs."""
    assert not P.face_hits([(0, 0, 80, 80, 0.35)], 1080)
    assert not P.face_hits([(0, 0, 300, 300, 0.50)], 1080)
    assert P.face_hits([(0, 0, 40, 40, 0.60)], 1080)


def test_thresholds_scale_with_the_analysis_resolution():
    assert P.face_hits([(0, 0, 20, 20, 0.9)], 540) == [(0, 0, 20, 20, 0.9)]   # meme visage, image deux fois moins large


# ---------- personnes : deux personnes ou plus font refuser l'image ----------
def test_overlapping_boxes_are_one_person():
    one = [(100, 100, 400, 900, 0.9), (110, 110, 410, 910, 0.8)]
    assert len(P.distinct_persons(one, 1920)) == 1


def test_far_away_people_do_not_count():
    far = [(100, 100, 400, 900, 0.9), (600, 700, 630, 760, 0.9)]   # 60 px de haut sur 1920 = 3 %
    assert len(P.distinct_persons(far, 1920)) == 1
    assert P.frame_reasons(1080, 1920, [], far) == []


def test_two_real_people_are_refused():
    two = [(100, 100, 400, 900, 0.9), (600, 300, 900, 1100, 0.9)]
    assert any("2 personnes" in r for r in P.frame_reasons(1080, 1920, [], two))


def test_clean_frame_has_no_reason():
    assert P.frame_reasons(1080, 1920, [], [(100, 100, 400, 900, 0.9)]) == []


# ---------- intervalles propres ----------
def test_clean_intervals_exclude_a_margin_around_refusals():
    samples = [(i * 0.5, i in (10, 11)) for i in range(40)]          # refus a 5,0 s et 5,5 s
    out = P.clean_intervals(samples, 0.5, margin=0.4, min_len=2.0)
    assert out[0][0] == 0.0 and out[0][1] <= 4.5
    assert out[1][0] >= 6.2
    assert all(not (a < 5.5 < b) and not (a < 5.0 < b) for a, b in out)


def test_short_clean_runs_are_dropped():
    samples = [(i * 0.5, i % 4 == 0) for i in range(20)]
    assert P.clean_intervals(samples, 0.5, margin=0.4, min_len=2.0) == []


def test_subtract_blocks_splits_and_trims():
    assert P.subtract_blocks(0, 10, [[4, 5, "x"]], margin=0.3) == [[0, 3.7], [5.3, 10]]
    assert P.subtract_blocks(0, 10, [[20, 30, "x"]]) == [[0, 10]]
    assert P.subtract_blocks(2, 4, [[0, 10, "x"]]) == []


# ---------- piste son ----------
def good():
    return {"audio": True, "sample_rate": 48000, "audio_dur": 18.0, "packets": 844, "packets_expected": 843.75,
            "packets_ratio": 1.0003, "video_dur": 18.0}


def test_healthy_stream_has_no_problem():
    assert A.stream_problems(good()) == []


def test_corrupt_aac_stream_is_detected():
    bad = dict(good(), packets=2767, packets_ratio=2767 / 843.75, sample_rate=96000)
    msgs = " ".join(A.stream_problems(bad))
    assert "incoherent" in msgs and "96000" in msgs


def test_video_shorter_than_audio_is_detected():
    assert any("video" in m for m in A.stream_problems(dict(good(), video_dur=16.8)))


def test_unreadable_file_is_reported():
    assert "illisible" in A.stream_problems({"audio": False, "error": "No such file"})[0]


def test_voice_chain_has_no_echo_or_reverb():
    chain = A.voice_filter(1.9, 12.0)
    assert "aecho" not in chain and "reverb" not in chain and "afade=t=in" in chain and "alimiter" in chain


def test_music_filter_fades_in_and_out_and_trims():
    f = A.music_filter(70.63, 15.0)
    assert "atrim=start=70.630" in f and "afade=t=in" in f and "afade=t=out:st=14.100" in f


# ---------- porte a l'envoi ----------
def test_unapproved_montage_is_refused(tmp_path):
    v = tmp_path / "safe_pov_00.mp4"
    v.write_bytes(b"x" * 100)
    assert "non approuve" in u.privacy_problem({"video": str(v)}, {})


def test_approved_montage_passes_until_it_changes(tmp_path):
    v = tmp_path / "safe_pov_00.mp4"
    v.write_bytes(b"x" * 100)
    ok = {"safe_pov_00": {"sig": u.video_signature(v), "by": "test"}}
    assert u.privacy_problem({"video": str(v)}, ok) is None
    v.write_bytes(b"y" * 120)                                         # montage modifie apres l'approbation
    assert "modifie" in u.privacy_problem({"video": str(v)}, ok)


def test_approvals_file_is_read_leniently(tmp_path):
    assert u.load_approvals(tmp_path / "absent.json") == {}
    (tmp_path / "bad.json").write_text("{pas du json", encoding="utf-8")
    assert u.load_approvals(tmp_path / "bad.json") == {}
    (tmp_path / "ok.json").write_text(json.dumps({"a": {"sig": "1:2"}}), encoding="utf-8")
    assert u.load_approvals(tmp_path / "ok.json")["a"]["sig"] == "1:2"
