"""Idempotence du mixage de voix (marqueurs) et generation des metadonnees."""


def test_overlay_marker_roundtrip(tmp_path, load_script):
    ov = load_script("scan/overlay_vo.py")
    video = tmp_path / "a.mp4"
    video.write_bytes(b"x" * 100)
    assert not ov.already_voiced(str(video))      # jamais mixe
    ov.mark(str(video))
    assert ov.already_voiced(str(video))          # relancer ne mixe pas deux fois
    video.write_bytes(b"y" * 150)                 # le montage est re-rendu : la signature change
    assert not ov.already_voiced(str(video))      # la voix sera remixee


def test_overlay_marker_lives_next_to_the_video(tmp_path, load_script):
    ov = load_script("scan/overlay_vo.py")
    assert str(ov.marker_for(str(tmp_path / "g_pov_00.mp4"))).endswith("g_pov_00.voiced")


def test_hashtags_strip_spaces_and_end_with_shorts(load_script):
    mm = load_script("scan/make_meta.py")
    assert mm.hashtags(["moto", "moto pov", "ride"]) == "#moto #motopov #ride #Shorts"
    assert mm.hashtags(["moto", "Shorts"]).count("#Shorts") == 1


def test_description_layout_and_signature(load_script):
    mm = load_script("scan/make_meta.py")
    entry = {"theme": "pov", "tags": ["moto", "moto pov"]}
    desc = mm.build_description(entry, "SIGNATURE", "A PROPOS", {"pov": "ACCROCHE"})
    assert desc.split("\n\n") == ["ACCROCHE", "A PROPOS", "SIGNATURE", "#moto #motopov #Shorts"]


def test_description_without_signature_has_no_blank_gap(load_script):
    mm = load_script("scan/make_meta.py")
    desc = mm.build_description({"theme": "pov", "tags": ["moto"]}, "", "A PROPOS", {"pov": "ACCROCHE"})
    assert "\n\n\n" not in desc and desc.count("\n\n") == 2


def test_meta_fields_are_what_the_uploader_expects(tmp_path, load_script):
    import upload_short as u
    mm = load_script("scan/make_meta.py")
    video = tmp_path / "g.mp4"
    video.write_bytes(b"x")
    entry = {"id": "g", "theme": "pov", "title": "T #Shorts", "tags": ["moto"], "publishAt": "2026-11-12T17:00:00Z"}
    meta = mm.build_meta(entry, video, "desc")
    assert u.validate_meta(meta) == []            # le meta produit est accepte tel quel par l'uploader
    assert meta["privacy"] == "private" and meta["publishAt"] == entry["publishAt"]
