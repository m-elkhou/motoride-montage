"""upload_short.py : fonctions pures (aucun reseau, aucun jeton)."""
import json

import upload_short as u


def make_meta(tmp_path, **over):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x" * 10)
    meta = {"video": str(video), "title": "Titre #Shorts", "description": "d", "tags": ["moto"]}
    meta.update(over)
    return meta


def test_validate_ok(tmp_path):
    assert u.validate_meta(make_meta(tmp_path)) == []


def test_validate_missing_fields():
    errs = u.validate_meta({"title": "x"})
    assert any("video" in e for e in errs) and any("description" in e for e in errs)


def test_validate_title_too_long(tmp_path):
    assert any("100" in e for e in u.validate_meta(make_meta(tmp_path, title="a" * 101)))


def test_validate_video_missing(tmp_path):
    assert any("introuvable" in e for e in u.validate_meta(make_meta(tmp_path, video=str(tmp_path / "nope.mp4"))))


def test_validate_bad_privacy_and_publishat(tmp_path):
    errs = u.validate_meta(make_meta(tmp_path, privacy="secret", publishAt="demain"))
    assert any("privacy" in e for e in errs) and any("publishAt" in e for e in errs)


def test_body_scheduled_is_private(tmp_path):
    body = u.build_body(make_meta(tmp_path, privacy="public", publishAt="2026-11-12T17:00:00Z"))
    assert body["status"]["privacyStatus"] == "private"
    assert body["status"]["publishAt"] == "2026-11-12T17:00:00Z"


def test_body_synthetic_flag_defaults_false_and_is_honoured(tmp_path):
    assert u.build_body(make_meta(tmp_path))["status"]["containsSyntheticMedia"] is False
    assert u.build_body(make_meta(tmp_path, containsSyntheticMedia=True))["status"]["containsSyntheticMedia"] is True


def test_expand_globs_skips_underscore_and_dedups(tmp_path):
    for n in ("a.json", "b.json", "_uploaded.json", "_uploaded_20261109.json"):
        (tmp_path / n).write_text("{}")
    found = u.expand_metas([str(tmp_path / "*.json"), str(tmp_path / "a.json")])
    assert [p.name for p in found] == ["a.json", "b.json"]


def test_ledger_record_and_reload(tmp_path):
    ledger = tmp_path / "_uploaded.json"
    meta = tmp_path / "a.json"
    u.record_upload(ledger, meta, "ID1")
    u.record_upload(ledger, tmp_path / "b.json", "ID2")
    done = u.load_ledger(ledger, tmp_path)
    assert done[u.norm(meta)] == "ID1" and len(done) == 2
    assert not list(tmp_path.glob("*.tmp"))  # ecriture atomique : pas de residu


def test_ledger_reads_legacy_files_and_survives_corruption(tmp_path):
    (tmp_path / "_uploaded_20261109_1200.json").write_text(json.dumps({str(tmp_path / "old.json"): "OLD"}))
    ledger = tmp_path / "_uploaded.json"
    ledger.write_text("{ceci n'est pas du json")
    done = u.load_ledger(ledger, tmp_path)
    assert done[u.norm(tmp_path / "old.json")] == "OLD"
    u.record_upload(ledger, tmp_path / "new.json", "NEW")  # repart d'un journal corrompu sans planter
    assert u.load_ledger(ledger, tmp_path)[u.norm(tmp_path / "new.json")] == "NEW"


def test_norm_ignores_case_and_separators():
    assert u.norm("C:\\Dir\\File.json") == u.norm("c:/dir/file.json")
