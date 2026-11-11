# -*- coding: utf-8 -*-
"""Sources en « lettre-boite » : des bandes noires DANS l'image du rushe (une video paysage collee dans un cadre vertical,
un enregistrement d'ecran). Une fois recadree en 9:16 pour un Short, elle garde ses bandes : le montage a l'air bacle.

  python scan/letterbox_scan.py        # analyse les rushes du pool propre -> scan/clip_quality.json (reprenable)

Le cadrage est celui du montage (recouvrement puis recadrage centre en 540x960) ; trois images (25, 50, 75 % de la duree) ;
une source est ecartee quand TOUTES montrent des bandes noires FIXES (meme taille a 3 % pres) sur au moins 10 % de la
hauteur ou de la largeur (une scene de nuit, dont le noir varie d'une image a l'autre, n'est donc pas confondue). gen_batch.py n'utilise
jamais une source ecartee.
"""
import sys
from pathlib import Path as _P

sys.path.insert(0, str(_P(__file__).resolve().parents[1]))
import json
import os

import mm_paths

mm_paths.use_root()
OUT = _P("scan/clip_quality.json")
W, H = 540, 960
BLACK = 10            # un pixel est « noir » jusqu'a 10/255 (des bandes vraies sont a 0-2)
MIN_BARS = 0.10       # part de la hauteur (ou de la largeur) en bandes noires a partir de laquelle on ecarte
SAMPLES = (0.25, 0.5, 0.75)


def bar_fraction(frame):
    """Part (0-1) de l'image occupee par des bandes noires aux deux bords (haut/bas ou gauche/droite), la plus grande des deux."""
    import numpy as np
    g = np.asarray(frame)
    if g.ndim == 3:
        g = g.max(axis=2)
    out = 0.0
    for lines in (g.max(axis=1) <= BLACK, g.max(axis=0) <= BLACK):          # lignes puis colonnes entierement noires
        n = len(lines)
        top = int(np.argmin(lines)) if not lines.all() else n
        bottom = int(np.argmin(lines[::-1])) if not lines.all() else 0
        out = max(out, (top + bottom) / n)
    return out


def framed(frame):
    """Le cadrage du montage : recouvrement de 540x960 puis recadrage centre."""
    import cv2
    h, w = frame.shape[:2]
    k = max(W / w, H / h)
    big = cv2.resize(frame, (max(W, round(w * k)), max(H, round(h * k))), interpolation=cv2.INTER_AREA)
    y, x = (big.shape[0] - H) // 2, (big.shape[1] - W) // 2
    return big[y:y + H, x:x + W]


def clip_bars(path):
    """Plus petite part de bandes noires parmi les images echantillonnees (bandes FIXES : il faut qu'elles soient dans toutes)."""
    import cv2
    cap = cv2.VideoCapture(path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fr = []
    for s in SAMPLES:
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(total * s)))
        ok, f = cap.read()
        if ok:
            fr.append(bar_fraction(framed(f)))
    cap.release()
    if len(fr) != len(SAMPLES):
        return None
    return min(fr) if max(fr) - min(fr) <= 0.03 else 0.0         # des bandes qui bougent d'une image a l'autre sont une scene sombre


def signature(path):
    s = os.stat(path)
    return f"{s.st_size}:{int(s.st_mtime)}"


def main():
    pool = json.load(open("scan/privacy_pool.json", encoding="utf-8"))
    moved = set(json.load(open("PRIVATE/row/_moved.json", encoding="utf-8"))) if os.path.exists("PRIVATE/row/_moved.json") else set()
    done = json.load(open(OUT, encoding="utf-8")) if OUT.exists() else {}
    todo = [p for p in pool if p not in moved and os.path.exists(p) and done.get(p, {}).get("sig") != signature(p)]
    print(f"{len(todo)} rushe(s) a analyser ({len(done)} deja faits)", flush=True)
    for k, p in enumerate(todo, 1):
        try:
            bars = clip_bars(p)
        except Exception as e:      # un fichier illisible ne doit pas arreter les autres
            done[p] = {"sig": signature(p), "error": f"{type(e).__name__}"}
            continue
        done[p] = {"sig": signature(p), "bars": None if bars is None else round(bars, 3),
                   "letterbox": bool(bars is not None and bars >= MIN_BARS)}
        if k % 25 == 0 or k == len(todo):
            OUT.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
            print(f"{k}/{len(todo)}", flush=True)
    OUT.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
    bad = [p for p, v in done.items() if v.get("letterbox") and p not in moved]
    print(f"{len(bad)} source(s) en lettre-boite ecartee(s) sur {len(done)} :")
    for p in sorted(bad):
        print(f"  {_P(p).name}  bandes {done[p]['bars']:.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
