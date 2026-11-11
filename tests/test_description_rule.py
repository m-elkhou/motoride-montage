"""Regle stricte des descriptions : detaillee, signature (Instagram), hashtags TOUT A LA FIN."""
import mm_description as d
import upload_short as u

SIG = "📸 Suis-moi sur Instagram : @exemple"
BODY = ("La route, le moteur, et plus rien d'autre : monte derrière le guidon le temps d'un Short. 🔥\n\n"
        "Des sorties moto filmées au guidon : des routes de montagne, des lignes droites, des virages et ces "
        "moments de liberté qu'on ne trouve que sur deux roues.\n\n"
        "🔔 Abonne-toi et active la cloche pour ne rien rater !")
GOOD = f"{BODY}\n\n{SIG}\n\n#moto #motovlog #pov #ride #Shorts"


def test_a_complete_description_is_accepted():
    assert d.description_problems(GOOD, SIG) == []


def test_no_signature_configured_is_refused():
    assert any("signature non configuree" in p for p in d.description_problems(GOOD, ""))


def test_signature_must_hold_the_instagram():
    assert any("Instagram" in p for p in d.description_problems(GOOD.replace(SIG, "Merci !"), "Merci !"))


def test_hashtags_must_be_last_and_alone_on_their_line():
    bad = GOOD + "\n\nMerci d'avoir regardé"
    assert any("derniere ligne" in p for p in d.description_problems(bad, SIG))
    mixed = GOOD.replace("#moto #motovlog #pov #ride #Shorts", "Suivez-moi #moto #motovlog #pov")
    assert any("derniere ligne" in p for p in d.description_problems(mixed, SIG))


def test_signature_after_the_hashtags_is_refused():
    bad = f"{BODY}\n\n#moto #motovlog #pov #ride #Shorts\n\n{SIG}"
    assert d.description_problems(bad, SIG)


def test_too_few_hashtags_is_refused():
    assert any("hashtags" in p for p in d.description_problems(f"{BODY}\n\n{SIG}\n\n#moto #Shorts", SIG))


def test_a_short_description_is_refused():
    assert any("trop courte" in p for p in d.description_problems(f"Joli Short\n\n{SIG}\n\n#a #b #c #d", SIG))


def test_missing_signature_is_refused():
    assert any("signature absente" in p for p in d.description_problems(GOOD.replace(SIG, "Texte sans signature"), SIG))


def test_built_description_is_conforme():
    entry = {"theme": "pov", "tags": ["moto", "motovlog", "pov", "ride"]}
    desc = d.build_description(entry, SIG, "Des sorties moto filmées au guidon, tout au long de l'année, sur toutes les routes, par tous les temps, avec la passion intacte.",
                               {"pov": "La route, le moteur, et plus rien d'autre. 🔥"}, "🔔 Abonne-toi !")
    assert d.description_problems(desc, SIG) == []
    assert desc.rstrip().endswith("#Shorts")


def test_the_uploader_refuses_a_meta_with_a_bad_description(tmp_path):
    v = tmp_path / "v.mp4"
    v.write_bytes(b"x" * 10)
    meta = {"video": str(v), "title": "T #Shorts", "description": "trop court", "tags": ["moto"]}
    assert u.validate_meta(meta) == []                                # sans signature : ancien comportement (tests)
    assert any(e.startswith("description:") for e in u.validate_meta(meta, SIG))
    meta["description"] = GOOD
    assert u.validate_meta(meta, SIG) == []
