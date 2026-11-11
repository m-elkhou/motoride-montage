# -*- coding: utf-8 -*-
"""Audit des RUSHES (originaux bruts) : visages visibles et autres personnes, puis DEPLACEMENT dans PRIVATE/row/.

Regle du proprietaire : aucun original qui montre son visage (casque ou non) ou une autre personne proche (filles
derriere lui ou avec lui) ne doit rester parmi les rushes. Il verifie A LA MAIN puis supprime lui-meme :
ce script DEPLACE (jamais copie, jamais supprime), garde la liste de ce qui a ete deplace et sait tout remettre.

  python scan/raw_audit.py scan [--shard i/n] [--step 2]   # analyse (reprenable) -> scan/raw_audit.json
  python scan/raw_audit.py report                          # resume chiffre, aucun fichier touche
  python scan/raw_audit.py move                            # deplace les rushes signales vers PRIVATE/row/<source>/
                                                           # (--sure-only : sans les rushes en doute)
  python scan/raw_audit.py restore [fichier ...]           # remet tout (ou ces fichiers) a leur place d'origine

Echantillonnage : une image cle toutes les `--step` secondes (decodage des seules images cles : rapide), image
entiere (rien n'est recadre : un visage n'importe ou dans l'image compte). Un rushe est signale si :
  - un visage confiant (voir mm_privacy.py) apparait sur au moins 2 images, ou un tres net (score >= 0,85) une fois ;
  - ou au moins 2 personnes distinctes apparaissent sur au moins 3 images.
Les rushes « en doute » (une seule detection d'un visage ou de 2 personnes, trop peu pour signaler) sont isoles
aussi, dans PRIVATE/row/doute/ : regle stricte, le proprietaire tranche a la main (beaucoup sont sans danger).
Les images signalees sont gardees en vignettes dans PRIVATE/row/_review/ et listees dans PRIVATE/row/index.html.
"""
import sys
from pathlib import Path as _P

sys.path.insert(0, str(_P(__file__).resolve().parents[1]))
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
import time

import mm_paths
import mm_privacy

mm_paths.use_root()
FF = mm_paths.FFMPEG
SIDE = 960                                    # image carree 960x960 (le contenu est ajuste, bords noirs)
FRAME_BYTES = SIDE * SIDE * 3
AUDIT = _P("scan/raw_audit.json")
ROW = _P("PRIVATE/row")
DOUBT = ROW / "doute"
MOVED = ROW / "_moved.json"
REVIEW = ROW / "_review"
MAX_THUMBS = 6


def arg(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def signature(path):
    s = os.stat(path)
    return f"{s.st_size}:{int(s.st_mtime)}"


def frame_flags(det, frame):
    """-> (visage confiant ?, meilleur score, nombre de personnes distinctes)."""
    faces = det.faces(frame)
    hits = mm_privacy.face_hits(faces, SIDE)
    best = max((h[4] for h in hits), default=0.0)
    persons = 0 if hits else len(mm_privacy.distinct_persons(det.persons(frame), SIDE))
    return bool(hits), best, persons


def sample_frames(path, step):
    """Genere (instant, image BGR 960x960) : images cles espacees d'au moins `step` s, orientation corrigee."""
    import numpy as np
    err = tempfile.TemporaryFile()
    vf = (f"select='isnan(prev_selected_t)+gte(t-prev_selected_t,{step})',showinfo,"
          f"scale={SIDE}:{SIDE}:force_original_aspect_ratio=decrease,pad={SIDE}:{SIDE}:(ow-iw)/2:(oh-ih)/2")
    cmd = [FF, "-hide_banner", "-loglevel", "info", "-skip_frame", "nokey", "-i", path, "-vf", vf,
           "-fps_mode", "vfr", "-an", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err)
    frames = []
    try:
        while True:
            buf = proc.stdout.read(FRAME_BYTES)
            if len(buf) < FRAME_BYTES:
                break
            frames.append(np.frombuffer(buf, np.uint8).reshape(SIDE, SIDE, 3).copy())
            if len(frames) >= 4000:                 # garde-fou (clip tres long)
                break
    finally:
        proc.kill()
        proc.wait()
    err.seek(0)
    times = [float(t) for t in re.findall(r"pts_time:([0-9.]+)", err.read().decode("utf-8", "replace"))]
    err.close()
    for i, fr in enumerate(frames):
        yield (times[i] if i < len(times) else i * step), fr


def audit_clip(det, rec, step):
    import cv2
    path = rec["path"]
    out = {"sig": signature(path), "dur": rec.get("dur"), "src": rec.get("src"), "frames": 0,
           "face_frames": 0, "max_face": 0.0, "multi_frames": 0, "flag_times": [], "thumbs": []}
    key = hashlib.sha1(path.encode("utf-8")).hexdigest()[:10]
    for t, fr in sample_frames(path, step):
        out["frames"] += 1
        face, score, persons = frame_flags(det, fr)
        flagged = face or persons >= 2
        if face:
            out["face_frames"] += 1
            out["max_face"] = max(out["max_face"], round(score, 2))
        if persons >= 2:
            out["multi_frames"] += 1
        if flagged:
            out["flag_times"].append(round(t, 1))
            if len(out["thumbs"]) < MAX_THUMBS:
                REVIEW.mkdir(parents=True, exist_ok=True)
                f = REVIEW / f"{key}_{len(out['thumbs'])}.jpg"
                cv2.imwrite(str(f), cv2.resize(fr, (400, 400), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 80])
                out["thumbs"].append(f.name)
    out["flagged"] = out["face_frames"] >= 2 or out["max_face"] >= 0.85 or out["multi_frames"] >= 3
    return out


def cmd_scan():
    step = float(arg("--step", "2"))
    shard = arg("--shard", "0/1")
    si, sn = (int(x) for x in shard.split("/"))
    inv = json.load(open("scan/inventory.json", encoding="utf-8"))
    mine = [r for i, r in enumerate(inv) if i % sn == si and os.path.exists(r["path"])]
    out_file = _P(arg("--out", str(AUDIT) if sn == 1 else f"scan/raw_audit.{si}of{sn}.json"))
    done = json.load(open(out_file, encoding="utf-8")) if out_file.exists() else {}
    todo = [r for r in mine if done.get(r["path"], {}).get("sig") != signature(r["path"])]
    print(f"[{shard}] {len(todo)} rushe(s) a analyser ({len(done)} deja faits), 1 image cle / {step} s", flush=True)
    if not todo:
        return 0
    det = mm_privacy.Detectors(persons=True)
    t0 = time.time()
    for k, rec in enumerate(todo, 1):
        try:
            done[rec["path"]] = audit_clip(det, rec, step)
        except Exception as e:  # un fichier illisible ne doit pas arreter les autres
            done[rec["path"]] = {"sig": signature(rec["path"]), "error": f"{type(e).__name__}: {e}"[:120], "flagged": False}
        if k % 10 == 0 or k == len(todo):
            tmp = out_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, out_file)
            nf = sum(1 for v in done.values() if v.get("flagged"))
            print(f"[{shard}] {k}/{len(todo)} {time.time() - t0:.0f}s | signales {nf}/{len(done)}", flush=True)
    return 0


def load_audit():
    data = {}
    for f in sorted(_P("scan").glob("raw_audit*.json")):
        try:
            data.update(json.load(open(f, encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return data


def tier(v):
    """'flagged' : rushe signale ; 'doubt' : une seule detection (visage ou 2 personnes) ; None : rien detecte."""
    if v.get("flagged"):
        return "flagged"
    if v.get("face_frames", 0) >= 1 or v.get("multi_frames", 0) >= 1:
        return "doubt"
    return None


def cmd_report():
    data = load_audit()
    inv = json.load(open("scan/inventory.json", encoding="utf-8"))
    n_flag = [p for p, v in data.items() if tier(v) == "flagged"]
    n_doubt = [p for p, v in data.items() if tier(v) == "doubt"]
    miss = [r["path"] for r in inv if r["path"] not in data and os.path.exists(r["path"])]

    def size(ps):
        return sum(os.path.getsize(p) for p in ps if os.path.exists(p)) / 1e9
    print(f"analyses : {len(data)} / {len(inv)} rushes | non analyses : {len(miss)} | signales : {len(n_flag)} "
          f"({size(n_flag):.1f} Go) | en doute : {len(n_doubt)} ({size(n_doubt):.1f} Go)")
    by = {}
    for p in n_flag + n_doubt:
        by.setdefault((tier(data[p]), data[p].get("src")), []).append(p)
    for (t, src), ps in sorted(by.items(), key=lambda x: (x[0][0], -len(x[1]))):
        print(f"  {t} {src}: {len(ps)}")
    return 0


def source_tag(path):
    p = path.replace("\\", "/")
    for tag in ("DCIM_Camera", "DCIM_Creative", "DCIM_VN", "DCIM_mh", "DCIM_Video_Editor", "inbox", "originals", "insta360"):
        if f"/{tag}" in p:
            return tag
    return "autre"


def cmd_move():
    data = load_audit()
    sure_only = "--sure-only" in sys.argv                  # par defaut les rushes « en doute » sont isoles aussi
    todo = sorted(p for p, v in data.items() if os.path.exists(p) and tier(v) in (("flagged",) if sure_only else ("flagged", "doubt")))
    ROW.mkdir(parents=True, exist_ok=True)
    moved = json.load(open(MOVED, encoding="utf-8")) if MOVED.exists() else {}
    failed = []
    try:
        for p in todo:
            v, tag = data[p], source_tag(p)
            dest_dir = ROW / tag if tier(v) == "flagged" else DOUBT / tag
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / _P(p).name
            if dest.exists():   # meme nom dans un autre dossier : on prefixe avec une empreinte du chemin d'origine
                dest = dest_dir / f"{hashlib.sha1(p.encode('utf-8')).hexdigest()[:6]}_{_P(p).name}"
            try:
                shutil.move(p, dest)  # meme volume : simple renommage, aucune copie
            except OSError as e:      # fichier verrouille (autre programme) : on continue, on le dit a la fin
                failed.append(f"{p} ({type(e).__name__})")
                continue
            moved[p] = {"to": str(dest).replace("\\", "/"), "src": tag, "tier": tier(v), "dur": v.get("dur"),
                        "face_frames": v.get("face_frames"), "max_face": v.get("max_face"), "multi_frames": v.get("multi_frames"),
                        "flag_times": v.get("flag_times", [])[:12], "thumbs": v.get("thumbs", [])}
    finally:                       # meme interrompu, la liste de ce qui a bouge est ecrite
        tmp = MOVED.with_suffix(".tmp")
        tmp.write_text(json.dumps(moved, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, MOVED)
        write_index(moved)
    n_doubt = sum(1 for p in todo if tier(data[p]) == "doubt")
    print(f"{len(todo) - len(failed)} rushe(s) DEPLACE(S) (dont {n_doubt} en doute) dans {ROW} ; liste : {MOVED} ; "
          f"a verifier : {ROW / 'index.html'}")
    for f in failed:
        print(f"NON deplace : {f}")
    return 1 if failed else 0


def index_row(orig, m):
    thumbs = "".join(f'<img src="_review/{html.escape(t)}" width="200">' for t in m.get("thumbs", []))
    why = []
    if m.get("face_frames"):
        why.append(f"visage sur {m['face_frames']} image(s) (max {m.get('max_face')})")
    if m.get("multi_frames"):
        why.append(f"2 personnes ou plus sur {m['multi_frames']} image(s)")
    return (f"<tr><td>{html.escape(m['to'].split('PRIVATE/row/')[-1])}<br><small>{m.get('dur') or 0:.0f} s ; "
            f"instants : {', '.join(str(t) for t in m.get('flag_times', [])[:8])}<br>{'; '.join(why)}<br>"
            f"origine : {html.escape(orig)}</small></td><td>{thumbs}</td></tr>")


def write_index(moved):
    def section(t):
        items = sorted(((o, m) for o, m in moved.items() if m.get("tier", "flagged") == t and not m.get("deleted")),
                       key=lambda x: (x[1]["src"], x[1]["to"]))
        return len(items), "".join(index_row(o, m) for o, m in items)
    n_sure, sure = section("flagged")
    n_doubt, doubt = section("doubt")
    n_gone = sum(1 for m in moved.values() if m.get("deleted"))
    page = ("<!doctype html><meta charset='utf-8'><title>Rushes isoles</title>"
            "<style>body{font-family:sans-serif}td{vertical-align:top;border-bottom:1px solid #ccc;padding:4px}</style>"
            f"<h1>{n_sure + n_doubt} rushes deplaces ici (a verifier puis supprimer a la main)</h1>"
            f"<p>{n_gone} autre(s) deja supprime(s) definitivement : voir PRIVATE/_suppressions_*.json</p>"
            "<p>Pour tout remettre : <code>python scan/raw_audit.py restore</code> "
            "(ou un seul : <code>restore nom.mp4</code>)</p>"
            f"<h2>Signales ({n_sure})</h2><table>{sure}</table>"
            f"<h2>En doute : une seule detection ({n_doubt}), beaucoup sont sans danger : dossier <code>doute/</code></h2>"
            f"<table>{doubt}</table>")
    (ROW / "index.html").write_text(page, encoding="utf-8")


def cmd_restore(names):
    moved = json.load(open(MOVED, encoding="utf-8")) if MOVED.exists() else {}
    todo = [o for o, m in moved.items() if not names or any(n in o or n in m["to"] for n in names)]
    for o in todo:
        src, dest = _P(moved[o]["to"]), _P(o)
        if src.exists() and not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(src, dest)
            moved.pop(o)
    tmp = MOVED.with_suffix(".tmp")
    tmp.write_text(json.dumps(moved, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, MOVED)
    write_index(moved)
    print(f"{len(todo)} rushe(s) remis a leur place")
    return 0


def main(argv):
    if not argv or argv[0] not in ("scan", "report", "move", "restore"):
        print(__doc__)
        return 2
    if argv[0] == "scan":
        return cmd_scan()
    if argv[0] == "report":
        return cmd_report()
    if argv[0] == "move":
        return cmd_move()
    return cmd_restore([a for a in argv[1:] if not a.startswith("--")])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
