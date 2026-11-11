"""raw_audit.py : DEPLACE (jamais copie) les rushes signales dans PRIVATE/row/, garde la liste et sait tout remettre.

Bac a sable : de faux fichiers dans un dossier temporaire, aucune donnee reelle touchee, aucun modele necessaire.
"""
import json
import shutil
import subprocess
import sys

import pytest


@pytest.fixture
def sandbox(tmp_path, root):
    (tmp_path / "scan").mkdir()
    for f in ("mm_paths.py", "mm_privacy.py"):
        shutil.copy(root / f, tmp_path / f)
    shutil.copy(root / "scan" / "raw_audit.py", tmp_path / "scan" / "raw_audit.py")
    footage = tmp_path / "social2shorts" / "camera_roll" / "DCIM_Camera"
    footage.mkdir(parents=True)
    names = ["ok.mp4", "face.mp4", "girls.mp4", "maybe.mp4"]
    for n in names:
        (footage / n).write_bytes(b"x" * 100)
    inv = [{"path": str(footage / n), "src": "camera_roll", "dur": 10} for n in names]
    (tmp_path / "scan" / "inventory.json").write_text(json.dumps(inv), encoding="utf-8")
    audit = {str(footage / "ok.mp4"): {"flagged": False, "src": "camera_roll"},
             str(footage / "face.mp4"): {"flagged": True, "src": "camera_roll", "face_frames": 3, "max_face": 0.9,
                                         "flag_times": [1.0, 3.0], "thumbs": []},
             str(footage / "girls.mp4"): {"flagged": True, "src": "camera_roll", "multi_frames": 4, "flag_times": [2.0],
                                          "thumbs": []},
             str(footage / "maybe.mp4"): {"flagged": False, "src": "camera_roll", "face_frames": 1, "max_face": 0.7,
                                          "flag_times": [4.0], "thumbs": []}}
    (tmp_path / "scan" / "raw_audit.json").write_text(json.dumps(audit), encoding="utf-8")
    return tmp_path, footage


def run(sandbox, *args):
    r = subprocess.run([sys.executable, "-X", "utf8", "scan/raw_audit.py", *args], cwd=sandbox, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=60)
    assert r.returncode == 0, r.stderr[-400:]
    return r.stdout


def test_flagged_rushes_are_moved_not_copied_and_listed(sandbox):
    tmp, footage = sandbox
    run(tmp, "move")
    assert (footage / "ok.mp4").exists()                                     # le rushe propre ne bouge pas
    assert not (footage / "face.mp4").exists() and not (footage / "girls.mp4").exists()   # DEPLACES : plus a l'origine
    row = tmp / "PRIVATE" / "row" / "DCIM_Camera"
    assert (row / "face.mp4").exists() and (row / "girls.mp4").exists()
    moved = json.loads((tmp / "PRIVATE" / "row" / "_moved.json").read_text(encoding="utf-8"))
    assert len(moved) == 3 and all(m["src"] == "DCIM_Camera" for m in moved.values())
    maybe = next(m for o, m in moved.items() if o.endswith("maybe.mp4"))
    assert maybe["tier"] == "doubt" and "/row/doute/DCIM_Camera/" in maybe["to"]
    assert (row.parent / "doute" / "DCIM_Camera" / "maybe.mp4").exists()     # une seule detection : isole a part
    assert not (footage / "maybe.mp4").exists()
    index = (tmp / "PRIVATE" / "row" / "index.html").read_text(encoding="utf-8")
    assert "face.mp4" in index and "girls.mp4" in index


def test_restore_puts_everything_back(sandbox):
    tmp, footage = sandbox
    run(tmp, "move")
    run(tmp, "restore")
    assert (footage / "face.mp4").exists() and (footage / "girls.mp4").exists() and (footage / "maybe.mp4").exists()
    assert not (tmp / "PRIVATE" / "row" / "DCIM_Camera" / "face.mp4").exists()


def test_restore_can_target_one_file(sandbox):
    tmp, footage = sandbox
    run(tmp, "move")
    run(tmp, "restore", "face.mp4")
    assert (footage / "face.mp4").exists() and not (footage / "girls.mp4").exists()


def test_second_move_is_harmless(sandbox):
    tmp, footage = sandbox
    run(tmp, "move")
    out = run(tmp, "move")
    assert "0 rushe" in out
    assert (tmp / "PRIVATE" / "row" / "DCIM_Camera" / "face.mp4").exists()


def test_report_counts_without_touching_files(sandbox):
    tmp, footage = sandbox
    out = run(tmp, "report")
    assert "signales : 2" in out and "en doute : 1" in out and (footage / "face.mp4").exists()


def test_sure_only_leaves_the_doubtful_rushes_in_place(sandbox):
    tmp, footage = sandbox
    run(tmp, "move", "--sure-only")
    assert (footage / "maybe.mp4").exists() and (footage / "ok.mp4").exists()
    assert not (footage / "face.mp4").exists() and not (footage / "girls.mp4").exists()


def test_index_lists_both_tiers(sandbox):
    tmp, _ = sandbox
    run(tmp, "move")
    index = (tmp / "PRIVATE" / "row" / "index.html").read_text(encoding="utf-8")
    assert "Signales (2)" in index and "En doute" in index and "maybe.mp4" in index
