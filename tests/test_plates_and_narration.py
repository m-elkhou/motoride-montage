"""Plaques d'immatriculation (tuiles, pistes, masques, tri « poste de pilotage ») et montage narre (sous-titres mot a
mot, zoom). Regles pures : aucun modele, aucun reseau, pas d'ffmpeg, pas de carte graphique.

Les cas viennent du premier montage narre (14/11/2026) : le detecteur prend le compteur et l'ecran du GPS pour des
plaques ; une vraie plaque ne doit JAMAIS rester visible, meme si un seul echantillon de sa piste doute.
"""
import numpy as np
import pytest

import mm_plates
import mm_scene
import narrated_cut as nc


# ───────────────────────── tuiles ─────────────────────────

def test_tiles_cover_the_whole_frame_with_overlap():
    w, h = 1080, 1920
    ts = mm_plates.tiles(w, h)
    cover = np.zeros((h, w), np.uint8)
    for x0, y0, x1, y1 in ts:
        assert 0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h
        assert x1 - x0 <= mm_plates.TILE and y1 - y0 <= mm_plates.TILE
        cover[y0:y1, x0:x1] += 1
    assert cover.min() >= 1                                   # aucun pixel hors de toute tuile
    xs = sorted({t[0] for t in ts})
    assert all(b - a <= mm_plates.TILE * (1 - mm_plates.OVERLAP) + 1 for a, b in zip(xs, xs[1:]))   # recouvrement mini


def test_small_frame_is_one_tile():
    assert mm_plates.tiles(400, 300) == [(0, 0, 400, 300)]


def test_a_plate_straddling_two_tiles_is_whole_in_one_of_them():
    w, h = 1080, 1920
    for x in range(0, w - 120, 37):                           # plaque de 120 x 60 px, partout dans l'image
        for y in range(0, h - 60, 91):
            assert any(x0 <= x and x + 120 <= x1 and y0 <= y and y + 60 <= y1 for x0, y0, x1, y1 in mm_plates.tiles(w, h)), (x, y)


# ───────────────────────── fusion, agrandissement ─────────────────────────

def test_merge_unions_the_same_plate_seen_by_two_tiles():
    out = mm_plates.merge([(100, 100, 200, 140, 0.8), (110, 104, 210, 144, 0.5), (600, 600, 640, 620, 0.3)])
    assert len(out) == 2
    big = max(out, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    assert big[:4] == (100, 100, 210, 144) and big[4] == 0.8


def test_merge_absorbs_a_box_inside_another_of_comparable_size():
    assert len(mm_plates.merge([(100, 100, 300, 200, 0.6), (150, 115, 270, 185, 0.9)])) == 1     # la meme plaque, vue plus courte
    assert len(mm_plates.merge([(100, 100, 300, 200, 0.6), (150, 130, 200, 160, 0.9)])) == 2     # quatre fois plus petite : gardee


def test_grow_stays_inside_the_frame_and_has_a_minimum_margin():
    x0, y0, x1, y1 = mm_plates.grow((500, 900, 600, 940), 1080, 1920)
    assert x0 <= 500 - 35 and x1 >= 600 + 35 and y0 <= 900 - 14 and y1 >= 940 + 14
    assert (x1 - x0, y1 - y0) == (170, 68)                    # loin des bords : 35 % de chaque cote, rien de plus
    x0, y0, x1, y1 = mm_plates.grow((500, 900, 504, 902), 1080, 1920)
    assert x0 <= 500 - mm_plates.MIN_PAD and y1 >= 902 + mm_plates.MIN_PAD      # marge mini en pixels


def test_a_mask_near_an_edge_reaches_the_edge():
    # plaque a moitie sortie par le bas de l'image : la boite detectee s'arrete trop haut, le bas des lettres depassait
    assert mm_plates.grow((300, 1600, 860, 1790), 1080, 1920)[3] == 1920
    assert mm_plates.grow((10, 900, 90, 940), 1080, 1920)[0] == 0
    assert mm_plates.grow((1000, 30, 1070, 60), 1080, 1920)[1:3] == (0, 1080)
    assert mm_plates.grow((500, 900, 600, 940), 1080, 1920)[3] < 1920           # au milieu : pas de prolongement


# ───────────────────────── pistes et masques dans le temps ─────────────────────────

def _covers(masks, box):
    return any(m[0] <= box[0] and m[1] <= box[1] and m[2] >= box[2] and m[3] >= box[3] for m in masks)


def test_a_flickering_plate_is_masked_on_every_frame_between_its_detections():
    seen = {10: 500, 11: 510, 15: 560, 22: 650}               # une voiture qui avance ; le detecteur clignote (trous de 3 et 6)
    per = [[] for _ in range(200)]                            # plan long : le masque suit les detections
    for i, x in seen.items():
        per[i] = [(x, 900, x + 60, 925, 0.5)]
    masks = mm_plates.track_masks(per, 1080, 1920)
    for i in range(10, 23):                                   # aucune image sans masque, position interpolee
        lo, hi = max(k for k in seen if k <= i), min(k for k in seen if k >= i)
        x = seen[lo] if lo == hi else seen[lo] + (seen[hi] - seen[lo]) * (i - lo) / (hi - lo)
        assert _covers(masks[i], (x, 900, x + 60, 925)), i
    assert all(_covers(masks[i], (500, 900, 560, 925)) for i in range(10 - mm_plates.HOLD, 10))          # maintien avant
    assert all(_covers(masks[i], (650, 900, 710, 925)) for i in range(23, 23 + mm_plates.HOLD))          # maintien apres
    assert masks[0] == [] and masks[199] == []


def test_a_moving_plate_is_followed_between_two_detections():
    per = [[] for _ in range(12)]
    per[0] = [(100, 500, 160, 525, 0.6)]
    per[10] = [(200, 520, 260, 545, 0.6)]
    masks = mm_plates.track_masks(per, 1080, 1920)
    mid = (150, 510, 210, 535)                                # position interpolee a mi-chemin
    assert _covers(masks[5], mid)
    assert len(mm_plates.link_tracks(per)) == 1


def test_two_distant_plates_are_two_tracks():
    per = [[(100, 500, 160, 525, 0.6), (800, 700, 860, 725, 0.6)] for _ in range(5)]
    assert len(mm_plates.link_tracks(per)) == 2


def test_a_persistent_track_is_masked_over_the_whole_shot():
    box = (300, 1000, 380, 1040, 0.4)
    per = [[] for _ in range(200)]
    for i in range(60, 160, 3):                               # presente sur la moitie d'un plan long
        per[i] = [box]
    masks = mm_plates.track_masks(per, 1080, 1920)
    assert all(_covers(m, box) for m in masks)                # du premier au dernier : pas de flou qui apparait en cours


def test_in_a_short_shot_every_mask_is_held_from_the_first_frame_to_the_last():
    box = (150, 1270, 280, 1340, 0.5)                         # petit ecran vu sur UNE image d'un plan de 25 images
    per = [[] for _ in range(25)]
    per[6] = [box]
    masks = mm_plates.track_masks(per, 1080, 1920)
    assert all(_covers(m, box) for m in masks)                # sinon il redevient net sur les dernieres images du plan


def test_a_static_object_is_masked_over_the_whole_shot_even_when_seen_briefly():
    box = (150, 1270, 280, 1340, 0.5)                         # etiquette sur la moto garee, vue sur 4 images de 200
    per = [[] for _ in range(200)]
    for i in (2, 3, 5, 6):
        per[i] = [box]
    masks = mm_plates.track_masks(per, 1080, 1920)
    assert all(_covers(m, box) for m in masks)
    moving = [[] for _ in range(200)]                         # une voiture qui passe dans un plan long : pas de flou qui traine
    for k, i in enumerate((2, 3, 5, 6)):
        moving[i] = [(100 + 90 * k, 900, 160 + 90 * k, 925, 0.6)]
    masks = mm_plates.track_masks(moving, 1080, 1920)
    assert masks[199] == [] and not mm_plates.is_static(mm_plates.link_tracks(moving)[0])


def test_only_the_tracks_given_are_masked():
    per = [[(100, 500, 160, 525, 0.6), (500, 1300, 640, 1380, 0.6)] for _ in range(10)]
    tracks = mm_plates.link_tracks(per)
    plate = [t for t in tracks if t[0][1][0] == 100]
    masks = mm_plates.masks_from_tracks(plate, 10, 1080, 1920)
    assert all(_covers(m, (100, 500, 160, 525)) for m in masks)
    assert not any(_covers(m, (500, 1300, 640, 1380)) for m in masks)


def test_blur_removes_the_detail_of_the_plate_and_keeps_the_rest():
    pytest.importorskip("cv2")                                # le flou passe par OpenCV, absent de l'environnement de la CI
    rng = np.random.default_rng(1)
    frame = np.full((400, 400, 3), 90, np.uint8)
    frame[150:200, 120:280] = rng.integers(0, 2, (50, 160, 1), dtype=np.uint8) * 255      # « caracteres » noir et blanc
    before = frame.copy()
    mm_plates.blur_boxes(frame, [mm_plates.grow((120, 150, 280, 200), 400, 400)])
    assert frame[160:190, 140:260].std() < 0.25 * before[160:190, 140:260].std()
    assert np.array_equal(frame[:60], before[:60])            # loin de la boite : image intacte


def test_blur_reaches_the_frame_border_when_the_box_touches_it():
    pytest.importorskip("cv2")
    frame = np.full((400, 400, 3), 90, np.uint8)
    frame[150:210, :160] = (np.arange(160)[None, :, None] // 4 % 2 * 255).astype(np.uint8)    # traits verticaux de 4 px
    before = frame.copy()
    box = mm_plates.grow((0, 160, 100, 200), 400, 400)       # plaque coupee par le bord gauche de l'image
    assert box[0] == 0
    mm_plates.blur_boxes(frame, [box])
    assert frame[165:195, 0:24].std() < 0.25 * before[165:195, 0:24].std()      # la bande collee au bord est floutee aussi
    low = np.full((400, 400, 3), 90, np.uint8)
    low[340:400, 100:300] = (np.arange(200)[None, :, None] // 4 % 2 * 255).astype(np.uint8)
    ref = low.copy()
    box = mm_plates.grow((120, 350, 280, 400), 400, 400)     # plaque coupee par le bas de l'image
    assert box[3] == 400
    mm_plates.blur_boxes(low, [box])
    assert low[384:400, 140:260].std() < 0.25 * ref[384:400, 140:260].std()


def test_a_plate_inside_a_giant_box_keeps_its_own_box():
    plate, giant = (500, 1300, 560, 1335, 0.3), (240, 1250, 840, 1700, 0.2)     # plaque dans un faux positif geant
    out = mm_plates.merge([plate, giant])
    assert len(out) == 2 and plate in out
    half = (500, 1300, 532, 1335, 0.25)                      # la meme plaque coupee par une tuile : toujours fusionnee
    assert len(mm_plates.merge([plate, half])) == 1


def test_a_giant_box_does_not_join_the_track_of_a_plate():
    plate = (500, 600, 560, 635, 0.5)
    per = [[plate] for _ in range(51)] + [[] for _ in range(99)]
    per[20] = [plate, (240, 400, 840, 1000, 0.2)]            # un tableau de bord detecte sur une seule image
    tracks = mm_plates.link_tracks(per)
    small = [t for t in tracks if all(b[2] - b[0] <= 60 for _, b in t)]
    assert len(small) == 1 and len(small[0]) == 51           # la piste de la plaque reste entiere, sans la boite geante
    masks = mm_plates.masks_from_tracks(small, len(per), 1080, 1920)
    assert all(_covers(masks[i], plate) for i in range(51))


def test_the_detection_cache_depends_on_the_detector_settings(monkeypatch, tmp_path):
    a = mm_plates.signature()
    monkeypatch.setattr(mm_plates, "CONF", mm_plates.CONF / 2)
    assert mm_plates.signature() != a                        # seuil change : les detections en cache ne valent plus
    f = tmp_path / "det.json"
    f.write_text('{"w": 1080, "h": 1920, "per_frame": [[], [], []]}', encoding="utf-8")
    assert nc.load_detections(f, 3)["w"] == 1080
    assert nc.load_detections(f, 4) is None                  # pas le meme nombre d'images : on redetecte
    assert nc.load_detections(tmp_path / "absent.json", 3) is None and nc.load_detections(None, 3) is None


def test_a_render_without_plate_masking_never_takes_the_name_of_a_masked_one():
    assert nc.output_base("out/pilote", True).name == "pilote"
    assert nc.output_base("out/pilote", False).name == "pilote_sans_flou"


# ───────────────────────── tri : plaque d'un vehicule, ou autre chose ? ─────────────────────────

def test_a_track_is_blurred_unless_it_is_certainly_not_a_plate():
    low = (0.02, 0.70, 0.06)                                              # compteur : bas de l'image, P faible
    assert not mm_scene.must_blur([low, low, low])
    assert mm_scene.must_blur([low, (0.60, 0.70, 0.06), low])             # un seul echantillon doute : on floute
    assert mm_scene.must_blur([(0.84, 0.52, 0.05)])                       # plaque de travers d'une moto garee
    assert not mm_scene.must_blur([(0.45, 0.52, 0.064)])                  # bord du retroviseur : sous le seuil
    assert not mm_scene.must_blur([(0.23, 0.90, 0.15)])                   # logo du carenage
    assert mm_scene.must_blur([])                                         # aucun echantillon : on floute


def test_small_boxes_and_the_road_zone_are_blurred_whatever_clip_says():
    assert mm_scene.must_blur([(0.03, 0.31, 0.05)])                       # vehicule lointain, voisinage flou : zone haute
    assert mm_scene.must_blur([(0.00, 0.66, 0.05), (0.00, 0.44, 0.05)])   # passe dans la zone haute
    assert mm_scene.must_blur([(0.16, 0.52, 0.014)])                      # 15 px de large, bas de l'image : toujours
    assert mm_scene.must_blur([(0.00, 0.80, 0.034)])
    assert not mm_scene.must_blur([(0.09, 0.48, 0.24)])                   # compteur large a mi-hauteur : CLIP decide
    assert mm_scene.must_blur([(0.97, 0.48, 0.24)])                       # ... et floute la plaque d'une voiture proche


def test_a_giant_box_is_blurred_only_when_clip_is_certain():
    assert not mm_scene.must_blur([(0.11, 0.17, 0.58)])                   # pan de ciel
    assert not mm_scene.must_blur([(0.88, 0.70, 0.54)])                   # tout le tableau de bord
    assert mm_scene.must_blur([(0.97, 0.60, 0.40)])                       # pare-chocs d'une voiture colle a l'objectif


def test_a_giant_sample_in_a_plate_track_does_not_unblur_the_plate():
    plate = (0.10, 0.30, 0.055)                                           # petite plaque, moitie haute : floutee d'office
    assert mm_scene.must_blur([plate] * 4)
    assert mm_scene.must_blur([plate] * 4 + [(0.10, 0.60, 0.555)])        # une boite geante s'est glissee dans la piste
    assert mm_scene.must_blur([(0.84, 0.70, 0.20), (0.84, 0.70, 0.40)])   # plaque qui grossit au-dela du seuil « geant »
    assert not mm_scene.must_blur([(0.88, 0.70, 0.54), (0.88, 0.70, 0.56)])      # piste entierement geante : cas 1
    assert mm_scene.must_blur([(0.30, 0.70, 0.20), (0.96, 0.70, 0.40)])   # echantillon geant certain : on floute


def test_a_wide_track_left_visible_while_clip_leans_to_a_plate_is_a_doubt():
    assert mm_scene.doubt([(0.88, 0.70, 0.54)])                           # tableau de bord ou plaque tres proche : a regarder
    assert not mm_scene.doubt([(0.11, 0.17, 0.58)])                       # pan de ciel
    assert not mm_scene.doubt([(0.97, 0.60, 0.40)])                       # floutee : plus de doute
    assert not mm_scene.doubt([(0.02, 0.70, 0.06)]) and not mm_scene.doubt([])


def test_context_box_is_square_bounded_and_never_tiny():
    assert mm_scene.context_box((500, 900, 520, 908), 1080, 1920) == (430, 824, 590, 984)      # 160 px mini
    x0, y0, x1, y1 = mm_scene.context_box((10, 10, 110, 40), 1080, 1920)
    assert (x0, y0) == (0, 0) and x1 <= 1080 and y1 <= 1920


# ───────────────────────── sous-titres mot a mot ─────────────────────────

def _words(text, start=0.0, step=0.3):
    return [{"w": w, "a": start + k * step, "b": start + k * step + 0.25} for k, w in enumerate(text.split())]


def test_clean_word_keeps_question_marks_and_drops_weak_punctuation():
    assert nc.clean_word("s'arrête.") == "S'ARRÊTE"
    assert nc.clean_word("quoi ?") == "QUOI?"
    assert nc.clean_word("Là,") == "LÀ"
    assert nc.clean_word("Écoute-moi") == "ÉCOUTE-MOI"


def test_chunks_never_cross_a_sentence_end_and_stay_short():
    blocks = nc.chunks(_words("Pas ton patron. Pas tes excuses. Pas demain."))
    assert [" ".join(w["text"] for w in b) for b in blocks] == ["PAS TON PATRON", "PAS TES EXCUSES", "PAS DEMAIN"]
    blocks = nc.chunks(_words("Là, il n'y a plus que toi, la route, et ce que tu as dans le ventre."))
    assert all(len(b) <= 3 for b in blocks)
    assert all(sum(len(w["text"]) for w in b) + len(b) - 1 <= 16 for b in blocks)


def test_each_word_appears_at_its_time_and_future_words_are_hidden():
    lines = [{"words": _words("Alors tu fais quoi ?")}]
    ev = nc.caption_events(lines, start=0.5, keywords=["QUOI"])
    assert [round(a, 2) for a, _, _ in ev][:3] == [0.5, 0.8, 1.1]            # debut + instant de chaque mot
    first = ev[0][2]
    assert "ALORS" in first and "\\alpha&HFF&}TU" in first                   # « TU » pas encore dit : invisible
    assert all(b > a for a, b, _ in ev)
    assert all(e0[1] <= e1[0] + 1e-6 for e0, e1 in zip(ev, ev[1:]))          # jamais deux blocs a la fois


def test_keywords_get_the_accent_colour_only_when_spoken():
    lines = [{"words": _words("Ne t'excuse jamais d'être libre.")}]
    ev = nc.caption_events(lines, start=0.0, keywords=["LIBRE"])
    assert any(f"\\c{nc.KEY}}}LIBRE" in t for _, _, t in ev)
    assert not any(f"\\c{nc.KEY}}}JAMAIS" in t for _, _, t in ev)


def test_long_blocks_use_a_smaller_font_and_stay_inside_the_safe_width():
    lines = [{"words": _words("Démarre. Extraordinairement loin.")}]
    sizes = {}
    for _, _, t in nc.caption_events(lines, 0.0):
        pt = int(t.split("\\fs")[1].split("\\")[0].rstrip("}"))
        text = "".join(c for c in t.split("}")[-1])
        sizes[text] = pt
    assert max(sizes.values()) <= nc.CAPTION_MAX_PT and min(sizes.values()) >= nc.CAPTION_MIN_PT


def test_ass_time_format():
    assert nc.ass_time(0) == "0:00:00.00"
    assert nc.ass_time(75.239) == "0:01:15.24"
    assert nc.ass_time(-1) == "0:00:00.00"


def test_write_ass_has_one_dialogue_per_event_and_the_handle(tmp_path):
    f = tmp_path / "c.ass"
    nc.write_ass(f, [(0.5, 0.9, "A"), (0.9, 0.9, "vide"), (1.0, 1.4, "B")], (1080, 1920), 42.0, "@ma_chaine")
    text = f.read_text(encoding="utf-8-sig")
    assert text.count("Dialogue:") == 3                       # l'evenement de duree nulle est ecarte, la signature ajoutee
    assert "@ma_chaine" in text and "PlayResY: 1920" in text


# ───────────────────────── zoom ─────────────────────────

def test_push_in_grows_smoothly_and_pull_out_shrinks():
    n = 60
    zin = [nc.zoom_at(k, n, 0.08) for k in range(n)]
    assert zin[0] == pytest.approx(1.0) and zin[-1] == pytest.approx(1.08)
    assert all(b >= a for a, b in zip(zin, zin[1:]))
    zout = [nc.zoom_at(k, n, -0.08) for k in range(n)]
    assert zout[0] == pytest.approx(1.08) and zout[-1] == pytest.approx(1.0)


def test_punch_is_a_short_kick_at_the_cut_and_never_zooms_out_of_the_frame():
    z = [nc.zoom_at(k, 30, 0.0, punch=True) for k in range(30)]
    assert z[0] == pytest.approx(1.07) and z[12] < 1.001
    assert min(z) >= 1.0                                      # jamais de bord noir
