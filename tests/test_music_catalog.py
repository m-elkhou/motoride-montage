"""Choix de la musique : seules les pistes motivantes passent (humeur de la bibliotheque YouTube), sans reseau ni audio."""
import pytest


@pytest.fixture
def mc(load_script):
    return load_script("scan/music_catalog.py")


def test_dark_melancholic_or_angry_moods_are_dropped(mc):
    assert mc.mood_score({"moods": ["Dramatique", "Mélancolique"]}) == -1.0
    assert mc.mood_score({"moods": ["Dramatique", "En colère"]}) == -1.0
    assert mc.mood_score({"moods": ["Dark", "Energetic"]}) == -1.0
    assert mc.mood_score({"moods": ["Sad"]}) == -1.0


def test_upbeat_moods_score_higher_than_neutral_ones(mc):
    upbeat = mc.mood_score({"moods": ["Optimiste", "Entraînante", "Funky", "Joyeuse"]})
    mixed = mc.mood_score({"moods": ["Dramatique", "Optimiste"]})
    plain = mc.mood_score({"moods": ["Dramatique"]})
    assert upbeat == 1.0 and 0 < mixed < upbeat and plain == 0.0
    assert mc.mood_score({"moods": ["Bright", "Happy"]}) == 1.0


def test_unknown_mood_is_neutral_not_dropped(mc):
    assert mc.mood_score({}) == 0.5
    assert mc.mood_score({"moods": []}) == 0.5
