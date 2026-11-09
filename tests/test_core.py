"""viral_cut.best_window, mm_paths / mm_config / run_pipeline : logique pure."""
import json

import numpy as np
import pytest


def test_best_window_picks_the_energetic_span():
    import viral_cut as v
    ts = np.arange(0, 10, 0.1)
    sc = np.zeros_like(ts)
    sc[(ts >= 4) & (ts < 6)] = 1
    score, start = v.best_window(ts, sc, 2.0, [])
    assert score == pytest.approx(1.0) and start == pytest.approx(4.0)


def test_best_window_avoids_used_spans():
    import viral_cut as v
    ts = np.arange(0, 10, 0.1)
    sc = np.zeros_like(ts)
    sc[(ts >= 4) & (ts < 6)] = 1
    sc[(ts >= 1) & (ts < 3)] = 0.5
    _, start = v.best_window(ts, sc, 2.0, [(4.0, 6.0)])
    assert start == pytest.approx(1.0)


def test_importing_viral_cut_does_not_run_the_cutter():
    import viral_cut  # noqa: F401  (avant : main() s'executait a l'import)


def test_ffmpeg_font_is_escaped_for_drawtext():
    import mm_paths
    font = mm_paths.ffmpeg_font()
    assert "\\" not in font.replace("\\:", "")     # seul le « : » du lecteur est echappe
    assert ":" not in font.replace("\\:", "")


def test_mm_config_defaults_and_override(tmp_path):
    import mm_config
    assert mm_config.load(tmp_path / "absent.json")["slot_hours"] == [17, 10]
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"exclude_dates": ["2023"], "schedule_start": "2026-01-01T17:00:00Z"}))
    cfg = mm_config.load(f)
    assert cfg["exclude_dates"] == ["2023"] and cfg["slot_hours"] == [17, 10]


def test_mm_paths_env_override(monkeypatch):
    import importlib
    import mm_paths
    monkeypatch.setenv("MM_FFMPEG", "/opt/ffmpeg")
    monkeypatch.setenv("MM_S2S_ROOT", "/elsewhere/s2s")
    try:
        importlib.reload(mm_paths)
        assert mm_paths.FFMPEG == "/opt/ffmpeg"
        assert mm_paths.S2S_ROOT.as_posix().endswith("elsewhere/s2s")
    finally:
        monkeypatch.undo()
        importlib.reload(mm_paths)


def test_pipeline_stage_selection():
    import run_pipeline as rp
    assert rp.select(None, None, None)[0] == "inventory" and rp.select(None, None, None)[-1] == "meta"
    assert "upload" not in rp.select(None, None, None)           # l'envoi n'est jamais implicite
    assert rp.select("plan", "mix", None) == ["plan", "render", "voice", "mix"]
    assert rp.select(None, None, "render") == ["render"]
    with pytest.raises(SystemExit):
        rp.select("mix", "plan", None)


def test_upload_stage_is_a_dry_run_unless_confirmed():
    import run_pipeline as rp
    assert "--dry-run" in rp.stage_command("upload", "upload_short.py", yes_upload=False)
    assert "--dry-run" not in rp.stage_command("upload", "upload_short.py", yes_upload=True)
