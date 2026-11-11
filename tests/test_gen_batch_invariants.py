"""gen_batch.py dans un bac a sable : donnees synthetiques, aucune donnee reelle touchee.

On copie les scripts dans un dossier temporaire (qui devient la « racine » via mm_paths.ROOT) puis on verifie
les invariants du planificateur : aucun clip reutilise, calendrier regulier, exclusions respectees.
"""
import json
import shutil
import subprocess
import sys
from datetime import datetime

import pytest


@pytest.fixture
def sandbox(tmp_path, root):
    (tmp_path / "scan" / "mont").mkdir(parents=True)
    for f in ("mm_paths.py", "mm_config.py", "mm_privacy.py"):
        shutil.copy(root / f, tmp_path / f)
    shutil.copy(root / "scan" / "gen_batch.py", tmp_path / "scan" / "gen_batch.py")

    rows, tags = [], {}
    def add(prefix, n, cat, date):
        for i in range(n):
            name = f"{date}_{prefix}{i:03d}.mp4"
            path = f"/clips/{name}"
            rows.append({"ok": True, "name": name, "path": path, "mean_bright": 60,
                         "top4": [{"t": 1.0, "len": 4.0, "score": 0.9 - i * 0.001},
                                  {"t": 8.0, "len": 4.0, "score": 0.8 - i * 0.001}]})
            tags[path] = {"top": [[cat, 0.9]], "moto": 0.95}
    add("p", 60, "moto_pov", "20260101")
    add("r", 50, "rider", "20260102")
    add("c", 40, "group_ride", "20260103")
    add("x", 12, "moto_pov", "20230822")      # date a exclure
    (tmp_path / "scan" / "moments.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    (tmp_path / "scan" / "clip_tags.json").write_text(json.dumps(tags), encoding="utf-8")
    # pool ANONYMAT : seuls les clips pov / rider ont ete analyses (les "crew" ne le sont pas : interdits)
    pool = {r["path"]: {"sig": "x", "windows": [{"start": 0.5, "end": 12.5, "frames": 36, "hits": [],
                                                  "clean": [[0.6, 5.4], [7.6, 12.4]]}]}
            for r in rows if ("p" in r["name"].split("_")[1][:1] or "r" in r["name"].split("_")[1][:1])
            and not r["name"].startswith("20230822")}
    (tmp_path / "scan" / "privacy_pool.json").write_text(json.dumps(pool), encoding="utf-8")
    (tmp_path / "scan" / "gen_config.json").write_text(json.dumps({
        "exclude_dates": ["20230822"], "schedule_start": "2026-11-12T17:00:00Z", "slot_hours": [17, 10],
        "themes": {"pov": [["moto_pov"], 4], "rider": [["rider"], 3], "crew": [["group_ride"], 2]}}), encoding="utf-8")
    return tmp_path


def run(sandbox):
    r = subprocess.run([sys.executable, "-X", "utf8", "scan/gen_batch.py"], cwd=sandbox, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 0, r.stderr[-500:]
    manifest = json.loads((sandbox / "scan" / "batch_manifest.json").read_text(encoding="utf-8"))
    mont = {m["id"]: json.loads((sandbox / "scan" / "mont" / f"{m['id']}.json").read_text(encoding="utf-8"))
            for m in manifest}
    return manifest, mont


def test_counts_follow_the_config(sandbox):
    manifest, _ = run(sandbox)
    assert [m["theme"] for m in manifest].count("pov") == 4
    assert len(manifest) == 4 + 3            # le theme "crew" n'a aucun clip verifie : aucun montage


def test_no_clip_is_used_twice_across_montages(sandbox):
    _, mont = run(sandbox)
    seen = {}
    for mid, segs in mont.items():
        for name in {s["name"] for s in segs}:
            assert name not in seen, f"{name} reutilise dans {seen[name]} et {mid}"
            seen[name] = mid


def test_each_montage_has_enough_distinct_clips(sandbox):
    _, mont = run(sandbox)
    for mid, segs in mont.items():
        assert len({s["name"] for s in segs}) >= 5, mid
        assert len(segs) >= 10, mid
        assert max(list(s["name"] for s in segs).count(n) for n in {s["name"] for s in segs}) <= 2, mid


def test_excluded_dates_never_appear(sandbox):
    _, mont = run(sandbox)
    assert all(not s["name"].startswith("20230822") for segs in mont.values() for s in segs)


def test_schedule_is_two_slots_per_day_and_increasing(sandbox):
    manifest, _ = run(sandbox)
    times = [datetime.fromisoformat(m["publishAt"].replace("Z", "+00:00")) for m in manifest]
    assert times == sorted(times) and len(set(times)) == len(times)
    assert times[0].isoformat().startswith("2026-11-12T17:00")
    assert [t.hour for t in times[:4]] == [17, 10, 17, 10]


def test_deterministic(sandbox):
    first, _ = run(sandbox)
    second, _ = run(sandbox)
    assert first == second


def test_only_verified_intervals_are_used(sandbox):
    """Chaque segment est entierement dans un intervalle propre du pool (marge de securite comprise)."""
    _, mont = run(sandbox)
    for segs in mont.values():
        for s in segs:
            end = s["start"] + s["len"]
            assert (0.75 <= s["start"] and end <= 5.25) or (7.75 <= s["start"] and end <= 12.25)
            assert s["len"] >= 2.6


def test_unanalysed_clips_are_never_planned(sandbox):
    _, mont = run(sandbox)
    assert all("_c" not in s["name"] for segs in mont.values() for s in segs)


def test_blocked_ranges_are_removed(sandbox):
    (sandbox / "scan" / "privacy_blocklist.json").write_text(json.dumps(
        {"/clips/20260101_p000.mp4": [[0.0, 20.0, "visage"]]}), encoding="utf-8")
    _, mont = run(sandbox)
    assert all(s["name"] != "20260101_p000.mp4" for segs in mont.values() for s in segs)


def test_planner_refuses_to_run_without_the_privacy_pool(sandbox):
    (sandbox / "scan" / "privacy_pool.json").unlink()
    r = subprocess.run([sys.executable, "-X", "utf8", "scan/gen_batch.py"], cwd=sandbox, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=60)
    assert r.returncode != 0 and "privacy" in (r.stderr + r.stdout)


def test_lane_count_is_bounded_by_verified_seconds(sandbox):
    """60 clips x 2 segments de 4,5 s = 540 s verifiees : avec 400 s reservees par voie, une seule voie pour ce theme."""
    cfg = json.loads((sandbox / "scan" / "gen_config.json").read_text(encoding="utf-8"))
    cfg["lane_seconds"] = 400
    (sandbox / "scan" / "gen_config.json").write_text(json.dumps(cfg), encoding="utf-8")
    manifest, _ = run(sandbox)
    assert [m["theme"] for m in manifest].count("pov") == 1


def test_a_lane_without_enough_verified_seconds_is_dropped_not_padded(sandbox):
    cfg = json.loads((sandbox / "scan" / "gen_config.json").read_text(encoding="utf-8"))
    cfg["min_seconds"] = 500                    # aucun montage ne peut atteindre 500 s verifiees : tous ignores
    (sandbox / "scan" / "gen_config.json").write_text(json.dumps(cfg), encoding="utf-8")
    manifest, _ = run(sandbox)
    assert manifest == []


def test_letterboxed_sources_are_never_planned(sandbox):
    """scan/clip_quality.json (letterbox_scan.py) : une source avec des bandes noires n'est jamais utilisee."""
    bad = {f"/clips/20260101_p{i:03d}.mp4": {"sig": "x", "bars": 0.6, "letterbox": True} for i in range(0, 30)}
    (sandbox / "scan" / "clip_quality.json").write_text(json.dumps(bad), encoding="utf-8")
    _, mont = run(sandbox)
    banned = {n.split("/")[-1] for n in bad}
    assert all(s["name"] not in banned for segs in mont.values() for s in segs)


def test_identical_copies_of_a_rush_are_planned_once_and_share_their_blocks(sandbox):
    """inbox + camera_roll : meme nom, meme taille. Le meme plan ne passe jamais deux fois ; une plage bloquee sur une
    copie vaut pour l'autre."""
    rows = [json.loads(line) for line in (sandbox / "scan" / "moments.jsonl").read_text(encoding="utf-8").splitlines()]
    pool = json.loads((sandbox / "scan" / "privacy_pool.json").read_text(encoding="utf-8"))
    tags = json.loads((sandbox / "scan" / "clip_tags.json").read_text(encoding="utf-8"))
    extra = []
    for r in [r for r in rows if "_p" in r["name"]][:40]:
        d = dict(r, path=r["path"].replace("/clips/", "/inbox/"))
        extra.append(d)
        pool[d["path"]] = pool[r["path"]]
        tags[d["path"]] = tags[r["path"]]
    (sandbox / "scan" / "moments.jsonl").write_text("\n".join(json.dumps(r) for r in rows + extra), encoding="utf-8")
    (sandbox / "scan" / "privacy_pool.json").write_text(json.dumps(pool), encoding="utf-8")
    (sandbox / "scan" / "clip_tags.json").write_text(json.dumps(tags), encoding="utf-8")
    (sandbox / "scan" / "privacy_blocklist.json").write_text(json.dumps(          # bloque sur la copie /inbox/ seulement
        {"/inbox/20260101_p001.mp4": [[0.0, 20.0, "visage"]]}), encoding="utf-8")
    _, mont = run(sandbox)
    for segs in mont.values():
        paths = {}
        for s in segs:
            paths.setdefault(s["name"], set()).add(s["clip"])
        assert all(len(v) == 1 for v in paths.values())                      # jamais deux copies du meme rushe
    assert all(s["name"] != "20260101_p001.mp4" for segs in mont.values() for s in segs)
