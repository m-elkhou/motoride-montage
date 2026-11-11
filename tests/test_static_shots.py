"""Plans fixes d'un montage POV : mesure du mouvement par plan (pure : images grises synthetiques)."""
import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")


@pytest.fixture
def pc(load_script):
    return load_script("scan/privacy_check.py")


def grays(seconds, fps, kind, rng):
    """Une image grise 135x240 par instant ; `kind` : 'still' (image identique) ou 'moving' (grand changement)."""
    out, base = [], rng.integers(0, 255, (240, 135)).astype(np.float32)
    for k in range(int(seconds * fps)):
        img = base.copy() if kind == "still" else rng.integers(0, 255, (240, 135)).astype(np.float32)
        out.append((k / fps, img))
    return out


def test_a_still_shot_is_reported_and_a_moving_shot_is_not(pc):
    rng = np.random.default_rng(3)
    a = grays(2.0, 10, "moving", rng)
    b = [(t + 2.0, g) for t, g in grays(3.0, 10, "still", rng)]
    plan = [{"t_out": 0.0, "t_len": 2.0, "clip": "a.mp4", "start": 0.0, "src_len": 2.0},
            {"t_out": 2.0, "t_len": 3.0, "clip": "b.mp4", "start": 5.0, "src_len": 3.0}]
    found = pc.static_shots(plan, a + b, 0.1)
    assert [s["clip"] for s, _ in found] == ["b.mp4"]
    assert found[0][1] < pc.STATIC_MIN


def test_slow_gentle_motion_above_the_threshold_is_kept(pc):
    rng = np.random.default_rng(4)
    base = rng.integers(0, 120, (240, 135)).astype(np.float32)
    frames = [(k / 10, base + 3.0 * k) for k in range(30)]               # derive reguliere : 6 niveaux de gris par 0,2 s
    plan = [{"t_out": 0.0, "t_len": 3.0, "clip": "c.mp4", "start": 0.0, "src_len": 3.0}]
    assert pc.static_shots(plan, frames, 0.1, min_motion=5.0) == []


def test_a_shot_too_short_to_measure_is_never_reported(pc):
    plan = [{"t_out": 0.0, "t_len": 0.2, "clip": "d.mp4", "start": 0.0, "src_len": 0.2}]
    frames = [(0.0, np.zeros((240, 135), np.float32)), (0.1, np.zeros((240, 135), np.float32))]
    assert pc.static_shots(plan, frames, 0.1) == []
