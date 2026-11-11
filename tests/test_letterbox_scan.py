"""Detection des bandes noires d'une source (pure : des images synthetiques, aucun fichier video)."""
import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")


@pytest.fixture
def lb(load_script):
    return load_script("scan/letterbox_scan.py")


def frame(h=960, w=540, top=0, bottom=0, left=0, right=0):
    img = np.full((h, w, 3), 120, np.uint8)
    img[:top] = 0
    if bottom:
        img[h - bottom:] = 0
    img[:, :left] = 0
    if right:
        img[:, w - right:] = 0
    return img


def test_a_clean_frame_has_no_bars(lb):
    assert lb.bar_fraction(frame()) == 0.0


def test_letterbox_bars_top_and_bottom_are_measured(lb):
    assert lb.bar_fraction(frame(top=300, bottom=300)) == pytest.approx(600 / 960)


def test_pillarbox_bars_left_and_right_are_measured(lb):
    assert lb.bar_fraction(frame(left=100, right=100)) == pytest.approx(200 / 540)


def test_a_fully_black_frame_counts_as_all_bars(lb):
    assert lb.bar_fraction(np.zeros((960, 540, 3), np.uint8)) == 1.0


def test_dark_noisy_night_rows_are_not_bars(lb):
    rng = np.random.default_rng(1)
    night = rng.integers(0, 40, (960, 540, 3), dtype=np.uint8)           # du bruit : aucune ligne entierement noire
    assert lb.bar_fraction(night) == 0.0


def test_the_montage_framing_is_a_centred_cover_crop(lb):
    wide = frame(h=540, w=1920, left=0)                                  # paysage : le recadrage centre garde le milieu
    out = lb.framed(wide)
    assert out.shape == (960, 540, 3)
    assert lb.bar_fraction(out) == 0.0
