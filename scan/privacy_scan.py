# -*- coding: utf-8 -*-
"""Pre-filtre ANONYMAT du pool : analyse chaque fenetre candidate avec le cadrage exact du montage
(1080x1920, recadrage central) et ecrit scan/privacy_pool.json = intervalles SANS visage ni 2e personne.

- fenetres : les `top4` de scan/moments.jsonl (score >= 0.35) des clips moto/pilote ; 
- reprenable : un clip deja analyse (meme signature taille:date) est saute ;
- le planificateur (gen_batch.py) ne pioche QUE dans ces intervalles propres.
Usage : python scan/privacy_scan.py [--cats moto_pov,rider] [--limit N] [--fps 3]
        python scan/privacy_scan.py --cars   : 2e passe sur le pool EXISTANT : retire les plans pris depuis une VOITURE
                                              (regle stricte, voir mm_scene.py) ; reprenable
        --reverse --out scan/privacy_pool.rev.json : 2e processus qui part de la FIN de la liste (a fusionner ensuite)
"""
import sys
from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parents[1]))
import json
import os
import subprocess
import time

import numpy as np

import mm_config
import mm_paths
import mm_privacy
import mm_scene

mm_paths.use_root()
FF = mm_paths.FFMPEG
OUT = _P("scan/privacy_pool.json")
W, H = mm_privacy.ANALYSIS_W, mm_privacy.ANALYSIS_H   # demi-resolution du montage (1080x1920) : memes proportions et recadrage
PAD = 0.5                # marge autour de chaque fenetre (s)


def arg(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def signature(path):
    s = os.stat(path)
    return f"{s.st_size}:{int(s.st_mtime)}"


def decode(path, t0, length, fps):
    """Images BGR (W x H) du segment [t0, t0+length], cadrage du montage. [] si le decodage echoue."""
    vf = f"fps={fps},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    for hw in (["-hwaccel", "auto"], []):
        cmd = [FF, "-v", "error", *hw, "-ss", f"{max(0.0, t0):.2f}", "-t", f"{length:.2f}", "-i", path,
               "-vf", vf, "-an", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
        try:
            raw = subprocess.run(cmd, capture_output=True, timeout=180).stdout
        except subprocess.TimeoutExpired:
            raw = b""
        n = len(raw) // (W * H * 3)
        if n:
            return list(np.frombuffer(raw[:n * W * H * 3], np.uint8).reshape(n, H, W, 3))
    return []


def merged_ranges(windows, dur):
    rng = sorted((max(0.0, w["t"] - PAD), min(dur, w["t"] + w["len"] + PAD)) for w in windows)
    out = []
    for a, b in rng:
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def cars_pass(fps):
    """Retire des intervalles propres les images prises depuis une voiture (CLIP), marge 0,5 s, >= 2 s restantes."""
    pool = json.load(open(OUT, encoding="utf-8"))
    todo = [p for p, e in pool.items() if not e.get("car_checked") and any(w["clean"] for w in e["windows"])]
    print(f"{len(todo)} clip(s) a verifier pour les plans de voiture ({len(pool)} dans le pool)", flush=True)
    if not todo:
        return 0
    cf = mm_scene.CarFilter()
    step, t0, removed = 1.0 / fps, time.time(), 0.0
    for k, path in enumerate(todo, 1):
        entry = pool[path]
        if not os.path.exists(path):
            entry["car_checked"] = True
            continue
        for w in entry["windows"]:
            new = []
            for a, b in w["clean"]:
                frames = decode(path, a, b - a, fps)
                samples = [(a + i * step, cf.is_car(fr)) for i, fr in enumerate(frames)]
                for x0, x1 in mm_privacy.clean_intervals(samples, step, margin=0.5, min_len=2.0):
                    new.append([round(max(a, x0), 2), round(min(b, x1), 2)])
                removed += (b - a) - sum(y1 - y0 for y0, y1 in new if a <= y0 and y1 <= b)
            w.setdefault("clean_all", w["clean"])
            w["clean"] = new
        entry["car_checked"] = True
        if k % 10 == 0 or k == len(todo):
            tmp = OUT.with_suffix(".tmp")
            tmp.write_text(json.dumps(pool, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, OUT)
            print(f"[{k}/{len(todo)}] {time.time() - t0:.0f}s | secondes retirees (voiture) : {removed:.0f}", flush=True)
    return 0


def main():
    if "--cars" in sys.argv:
        return cars_pass(float(arg("--fps", "3")))
    cats = set(arg("--cats", "moto_pov,rider").split(","))
    limit = int(arg("--limit", "0"))
    fps = float(arg("--fps", "3"))
    cfg = mm_config.load()
    excl = tuple(cfg["exclude_dates"])
    tags = json.load(open("scan/clip_tags.json", encoding="utf-8"))
    rows = [json.loads(line) for line in open("scan/moments.jsonl", encoding="utf-8")]
    todo = []
    for r in rows:
        if not r.get("ok") or r["name"].startswith(excl):
            continue
        t = tags.get(r["path"], {})
        if t.get("moto", 0) < 0.6 or (t.get("top") or [["other"]])[0][0] not in cats or not os.path.exists(r["path"]):
            continue
        wins = [m for m in r.get("top4", []) if m["score"] >= 0.35]
        if wins:
            todo.append((r, wins))
    out = _P(arg("--out", str(OUT)))
    rev = "--reverse" in sys.argv
    pool = json.load(open(out, encoding="utf-8")) if out.exists() else {}
    other = json.load(open(OUT, encoding="utf-8")) if (out != OUT and OUT.exists()) else {}
    pool_all = {**other, **pool}
    todo = [(r, w) for r, w in todo if pool_all.get(r["path"], {}).get("sig") != signature(r["path"])]
    if rev:
        todo.reverse()
    if limit:
        todo = todo[:limit]
    print(f"{len(todo)} clip(s) a analyser ({len(pool)} deja faits), {fps} img/s", flush=True)
    if not todo:
        return 0
    det = mm_privacy.Detectors(persons=True)
    cars = mm_scene.CarFilter()
    t0, step = time.time(), 1.0 / fps
    for k, (r, wins) in enumerate(todo, 1):
        if out != OUT and OUT.exists():   # le 1er processus a deja analyse ce clip : on s'est rejoints, on s'arrete
            try:
                if r["path"] in json.load(open(OUT, encoding="utf-8")):
                    print("rejoint le 1er processus : arret", flush=True); break
            except (OSError, ValueError):
                pass
        entry = {"sig": signature(r["path"]), "windows": [], "car_checked": True}
        for a, b in merged_ranges(wins, r.get("dur") or 9999):
            frames = decode(r["path"], a, b - a, fps)
            samples, hits = [], []
            for i, fr in enumerate(frames):
                _, _, why = det.analyse(fr)
                if not why and cars.is_car(fr):
                    why = ["plan pris depuis une voiture"]
                t = a + i * step
                samples.append((t, bool(why)))
                if why:
                    hits.append([round(t, 2), why[0]])
            entry["windows"].append({"start": round(a, 2), "end": round(b, 2), "frames": len(frames),
                                     "clean": mm_privacy.clean_intervals(samples, step) if frames else [],
                                     "hits": hits})
        pool[r["path"]] = entry
        if k % 10 == 0 or k == len(todo):
            tmp = out.with_suffix(".tmp")
            tmp.write_text(json.dumps(pool, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, out)
            ok = sum(1 for e in pool.values() if any(w["clean"] for w in e["windows"]))
            print(f"[{k}/{len(todo)}] {time.time() - t0:.0f}s | clips avec du propre : {ok}/{len(pool)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
