# -*- coding: utf-8 -*-
"""Porte ANONYMAT d'un montage fini : analyse image par image + controle du flux audio, puis approbation.

  python scan/privacy_check.py audit [ids...]          # tous les montages du manifest par defaut
  python scan/privacy_check.py sheets <id>...          # planches de relecture : a REGARDER avant d'approuver
  python scan/privacy_check.py approve <id>... --by NOM   # enregistre l'approbation (seulement si l'audit est PASS)
  python scan/privacy_check.py flag <id> <debut> <fin> --why "texte"   # un doute releve a la RELECTURE : bloque la source
  python scan/privacy_check.py quarantine <id>...      # deplace tout ce qui concerne ces montages dans PRIVATE/
  python scan/privacy_check.py status

Regle : aucun visage visible (meme casque ouvert), aucune autre personne proche, piste audio saine, memes durees
audio et video. Au moindre doute : refus. L'envoi YouTube (upload_short.py) REFUSE un montage non approuve, ou
modifie apres son approbation. Les images refusees sont ajoutees a scan/privacy_blocklist.json (le planificateur
ne les reutilise plus).
"""
import sys
from pathlib import Path as _P

sys.path.insert(0, str(_P(__file__).resolve().parents[1]))
import json
import os
import shutil
from datetime import datetime

import cv2
import numpy as np

import mm_audio
import mm_paths
import mm_privacy
import mm_scene
import mm_voicecheck

mm_paths.use_root()
STEP = 3                    # une image sur 3 a 30 img/s = 10 img/s
STATIC_MIN = 9.0            # mouvement moyen (ecart de gris entre images distantes de 0,2 s, sur 255) sous lequel un plan POV est « fixe »
AUDIT_DIR = _P("meta/_privacy")
OK_FILE = _P("meta/_privacy_ok.json")
BLOCKLIST = _P("scan/privacy_blocklist.json")
PRIVATE = _P("PRIVATE")


def signature(path):
    s = os.stat(path)
    return f"{s.st_size}:{s.st_mtime_ns}"


def load_json(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return default


def save_json(path, data):
    _P(path).parent.mkdir(parents=True, exist_ok=True)
    tmp = _P(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def manifest_ids():
    return [m["id"] for m in load_json("scan/batch_manifest.json", [])]


def video_of(mid):
    return _P("out") / f"{mid}.mp4"


def proxy_of(mid):
    p = _P("out/_cat") / f"{mid}.mp4"
    return p if p.exists() else video_of(mid)   # le proxy n'a ni texte ni etalonnage : pas de faux positif sur les lettres


def source_range(plan, t):
    """Instant t du montage -> (clip, instant source) d'apres out/<id>.plan.json."""
    for s in plan:
        if s["t_out"] <= t < s["t_out"] + s["t_len"] + 0.05:
            return s["clip"], s["start"] + (t - s["t_out"]) / max(s.get("rate", 1.0), 1e-6)
    return None


def theme_of(mid):
    return next((m.get("theme") for m in load_json("scan/batch_manifest.json", []) if m["id"] == mid), None)


def static_shots(plan, grays, step_s, min_motion=STATIC_MIN):
    """Plans du montage dont le mouvement moyen est trop faible : [(plan, mouvement)].
    `grays` : [(instant, image grise reduite)] a pas regulier de `step_s` s ; mouvement = ecart moyen de gris entre images
    distantes de 0,2 s, a l'interieur d'un meme plan (un POV sans mouvement ne retient personne)."""
    gap = max(1, round(0.2 / step_s))
    out = []
    for s in plan:
        seg = [g for t, g in grays if s["t_out"] <= t < s["t_out"] + s["t_len"]]
        d = [float(np.abs(seg[i + gap] - seg[i]).mean()) for i in range(len(seg) - gap)]
        if d and sum(d) / len(d) < min_motion:
            out.append((s, sum(d) / len(d)))
    return out


def voice_in_mix(asr, video, expected, voice_wav=None):
    """Reecoute la voix DANS le mixage final (sous la musique) : Whisper doit entendre exactement la phrase prevue,
    sans repetition ni coupure. -> (problemes, texte entendu)."""
    vdur = mm_audio.duration(voice_wav) if voice_wav and _P(voice_wav).exists() else 3.0
    heard = asr.text(video, clip_end=round(mm_audio.VOICE_DELAY + vdur + 0.8, 2))
    return [f"voix dans le mixage : {p}" for p in mm_voicecheck.word_problems(expected, heard)], heard


def voice_check(asr, mid):
    """Reecoute de la voix d'un montage : le fichier seul (precis) et le debut du mixage final (sous la musique).
    -> (problemes, texte entendu dans le mixage)."""
    txt, wavp, vid = _P(f"vo/{mid}.clone.txt"), _P(f"vo/{mid}.wav"), video_of(mid)
    if not txt.exists():
        return ["voix : texte attendu introuvable (vo/<id>.clone.txt)"], None
    if asr is None:
        return ["voix non reecoutee (Whisper indisponible) : refus par prudence"], None
    if not vid.exists() or not wavp.exists():
        return ["voix ou montage absent"], None
    expected = txt.read_text(encoding="utf-8").splitlines()[0].strip()
    problems, heard = voice_in_mix(asr, vid, expected, str(wavp))
    import soundfile as sf
    w, sr = sf.read(str(wavp), dtype="float32")
    alone, _ = mm_voicecheck.check_take(w, sr, wavp, expected, asr)
    return problems + [f"voix (fichier) : {p}" for p in alone], heard


def audit_one(det, mid, cars=None, voice=None):
    vid = video_of(mid)
    if not vid.exists():
        return {"id": mid, "verdict": "FAIL", "qc": ["montage absent"], "refused": []}
    rep = mm_audio.stream_report(vid)
    qc = mm_audio.stream_problems(rep)
    cap = cv2.VideoCapture(str(proxy_of(mid)))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    refused, grays, n, i = [], [], 0, 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        if i % STEP == 0:
            n += 1
            grays.append((i / fps, cv2.cvtColor(cv2.resize(fr, (135, 240), interpolation=cv2.INTER_AREA),
                                                cv2.COLOR_BGR2GRAY).astype(np.float32)))
            _, _, why = det.analyse(fr)
            if not why and cars is not None and cars.is_car(fr):
                why = ["plan pris depuis une voiture"]
            if why:
                refused.append([round(i / fps, 2), why[0]])
        i += 1
    cap.release()
    if rep.get("video_dur", 0) < 10:
        qc.append(f"montage trop court ({rep.get('video_dur', 0):.1f} s)")
    vproblems, heard = voice if voice is not None else (["voix non reecoutee"], None)
    qc += vproblems
    static = []
    if theme_of(mid) == "pov":                     # un montage POV doit bouger ; les montages « rider » montrent des motos a l'arret
        for sh, motion in static_shots(load_json(f"out/{mid}.plan.json", []), grays, STEP / fps):
            static.append([sh["clip"], sh["start"], sh["src_len"], round(motion, 1)])
            qc.append(f"plan fixe {sh['t_out']:.1f}-{sh['t_out'] + sh['t_len']:.1f} s (mouvement {motion:.1f})")
    out = {"id": mid, "sig": signature(vid), "frames": n, "refused": refused, "qc": qc, "static": static, "voice_heard": heard,
           "verdict": "PASS" if not refused and not qc else "FAIL", "date": datetime.now().isoformat(timespec="seconds")}
    save_json(AUDIT_DIR / f"{mid}.json", out)
    return out


def add_to_blocklist(mid, refused):
    plan = load_json(f"out/{mid}.plan.json", [])
    if not plan or not refused:
        return 0
    bl = load_json(BLOCKLIST, {})
    added = 0
    for t, why in refused:
        sr = source_range(plan, t)
        if not sr:
            continue
        clip, ts = sr
        rng = [round(ts - 0.7, 2), round(ts + 0.7, 2), why[:60]]
        if rng not in bl.setdefault(clip, []):
            bl[clip].append(rng)
            added += 1
    save_json(BLOCKLIST, bl)
    return added


def block_static(mid, static):
    """Bloque le SEGMENT entier du planificateur dont vient un plan fixe (un clip fixe l'est en entier : sinon on le
    retrouverait, tranche par tranche, a chaque nouveau plan)."""
    segs = load_json(f"scan/mont/{mid}.json", [])
    bl = load_json(BLOCKLIST, {})
    added = 0
    for clip, start, src_len, motion in static:
        spans = [(g["start"], g["start"] + g["len"]) for g in segs
                 if g["clip"] == clip and g["start"] < start + src_len and g["start"] + g["len"] > start] or [(start, start + src_len)]
        for lo, hi in spans:
            rng = [round(lo, 2), round(hi, 2), f"plan fixe (mouvement {motion})"]
            if rng not in bl.setdefault(clip, []):
                bl[clip].append(rng)
                added += 1
    save_json(BLOCKLIST, bl)
    return added


def cmd_audit(ids):
    ids = ids or manifest_ids()
    voices = {}
    try:                                   # 1) la voix d'abord, Whisper seul en memoire (avec les detecteurs, ca ne tient pas)
        with mm_voicecheck.ASR() as asr:
            for mid in ids:
                voices[mid] = voice_check(asr, mid)
    except Exception as e:  # sans reecoute, chaque montage echouera (qc) : on le dit une fois
        print(f"reecoute de la voix impossible ({e}) : les montages seront refuses", flush=True)
        voices = {mid: voice_check(None, mid) for mid in ids}
    det = mm_privacy.Detectors(persons=True)   # 2) puis les images
    cars = mm_scene.CarFilter()
    nfail = 0
    for mid in ids:
        r = audit_one(det, mid, cars, voices.get(mid))
        if r["verdict"] == "FAIL":
            nfail += 1
            added = add_to_blocklist(mid, r["refused"]) + block_static(mid, r.get("static", []))
            print(f"FAIL {mid}: {len(r['refused'])} image(s) refusee(s) {[x[0] for x in r['refused']][:8]} | "
                  f"qc {r['qc']} | +{added} plage(s) bloquee(s)", flush=True)
        else:
            print(f"PASS {mid}: {r['frames']} images analysees, flux sain -> relire les planches puis `approve`", flush=True)
    print(f"\n{len(ids) - nfail} PASS, {nfail} FAIL", flush=True)
    return 1 if nfail else 0


def cmd_sheets(ids, per_sheet=10, every=0.8):
    import numpy as np
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    for mid in ids:
        cap = cv2.VideoCapture(str(video_of(mid)))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cells = []
        for k in range(0, int(total / fps / every) + 1):
            cap.set(cv2.CAP_PROP_POS_FRAMES, min(total - 1, int(k * every * fps)))
            ok, fr = cap.read()
            if not ok:
                continue
            c = cv2.resize(fr, (300, 533), interpolation=cv2.INTER_AREA)
            cv2.putText(c, f"{k * every:.1f}s", (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cells.append(c)
        cap.release()
        files = []
        for n in range(0, len(cells), per_sheet):
            chunk = cells[n:n + per_sheet]
            while len(chunk) % 5:
                chunk.append(np.zeros((533, 300, 3), np.uint8))
            grid = np.vstack([np.hstack(chunk[i:i + 5]) for i in range(0, len(chunk), 5)])
            f = AUDIT_DIR / f"{mid}_sheet{n // per_sheet + 1}.jpg"
            cv2.imwrite(str(f), grid, [cv2.IMWRITE_JPEG_QUALITY, 88])
            files.append(str(f))
        print(mid, "->", ", ".join(files))
    return 0


def cmd_approve(ids, by):
    ok = load_json(OK_FILE, {})
    bad = 0
    for mid in ids:
        a = load_json(AUDIT_DIR / f"{mid}.json", None)
        if not a or a.get("verdict") != "PASS" or not video_of(mid).exists() or a.get("sig") != signature(video_of(mid)):
            print(f"REFUSE {mid}: pas d'audit PASS a jour (relancez `audit`)")
            bad += 1
            continue
        ok[mid] = {"sig": a["sig"], "by": by, "date": datetime.now().isoformat(timespec="seconds")}
        print(f"APPROUVE {mid} par {by}")
    save_json(OK_FILE, ok)
    return 1 if bad else 0


def cmd_flag(mid, t0, t1, why):
    """Doute releve par un humain entre t0 et t1 (secondes du montage) : la SOURCE correspondante est bloquee pour les
    prochains plans, et l'audit + l'approbation de ce montage sont retires."""
    plan = load_json(f"out/{mid}.plan.json", [])
    if not plan:
        print(f"pas de plan pour {mid} (out/{mid}.plan.json) : impossible de remonter a la source")
        return 1
    spans, t = {}, t0
    while t <= t1 + 1e-6:
        sr = source_range(plan, t)
        if sr:
            clip, ts = sr
            lo, hi = spans.get(clip, (ts, ts))
            spans[clip] = (min(lo, ts), max(hi, ts))
        t += 0.1
    bl = load_json(BLOCKLIST, {})
    for clip, (lo, hi) in spans.items():
        rng = [round(lo - 0.7, 2), round(hi + 0.7, 2), ("revue humaine: " + why)[:60]]
        if rng not in bl.setdefault(clip, []):
            bl[clip].append(rng)
        print(f"bloque {_P(clip).name} {rng[0]}-{rng[1]} s ({why})")
    save_json(BLOCKLIST, bl)
    ok = load_json(OK_FILE, {})
    ok.pop(mid, None)
    save_json(OK_FILE, ok)
    (AUDIT_DIR / f"{mid}.json").unlink(missing_ok=True)
    print(f"{mid} : audit et approbation retires ; relancez gen_batch.py, render_batch.py puis audit")
    return 0


def cmd_quarantine(ids):
    dest = PRIVATE / datetime.now().strftime("%Y%m%d_%H%M")
    ok = load_json(OK_FILE, {})
    for mid in ids:
        moved = []
        proxy = proxy_of(mid)
        for p in (video_of(mid), proxy if proxy != video_of(mid) else None, _P(f"out/{mid}.plan.json"),
                  _P(f"out/{mid}.voiced"), _P(f"vo/{mid}.mp3"), _P(f"meta/{mid}.json"), _P(f"scan/mont/{mid}.json")):
            if p and p.exists():
                (dest / p.parent).mkdir(parents=True, exist_ok=True)
                shutil.move(str(p), str(dest / p))   # on DEPLACE : rien n'est supprime
                moved.append(p.name)
        ok.pop(mid, None)
        print(f"PRIVATE/{dest.name}: {mid} ({', '.join(moved) or 'rien a deplacer'})")
    save_json(OK_FILE, ok)
    return 0


def cmd_status():
    ok = load_json(OK_FILE, {})
    for mid in manifest_ids():
        a = load_json(AUDIT_DIR / f"{mid}.json", {})
        cur = signature(video_of(mid)) if video_of(mid).exists() else None
        if cur is None:
            state = "absent"
        elif mid in ok and ok[mid].get("sig") == cur:
            state = "APPROUVE"
        elif a and a.get("sig") != cur:
            state = "modifie depuis l'audit : relancer audit"
        elif a.get("verdict") == "PASS":
            state = "PASS (non approuve)"
        else:
            state = a.get("verdict", "non audite")
        print(f"{mid:14s} {state}")
    return 0


def main(argv):
    if not argv or argv[0] not in ("audit", "sheets", "approve", "quarantine", "status", "flag"):
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    by = rest[rest.index("--by") + 1] if "--by" in rest else None
    ids = [x for k, x in enumerate(rest) if not x.startswith("--") and (k == 0 or rest[k - 1] not in ("--by", "--why"))]
    if cmd == "audit":
        return cmd_audit(ids)
    if cmd == "sheets":
        return cmd_sheets(ids)
    if cmd == "approve":
        if not by:
            print("--by NOM est obligatoire (qui a regarde les planches ?)")
            return 2
        return cmd_approve(ids, by)
    if cmd == "flag":
        why = rest[rest.index("--why") + 1] if "--why" in rest else "doute"
        if len(ids) != 3:
            print('usage : flag <id> <debut> <fin> --why "texte"')
            return 2
        return cmd_flag(ids[0], float(ids[1]), float(ids[2]), why)
    if cmd == "quarantine":
        return cmd_quarantine(ids)
    return cmd_status()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
