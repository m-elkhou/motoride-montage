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
    for f in ("mm_paths.py", "mm_config.py"):
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
    assert len(manifest) == 4 + 3 + 2


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
        assert len({s["name"] for s in segs}) >= 4, mid
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
