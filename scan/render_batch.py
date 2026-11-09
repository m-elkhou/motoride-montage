# -*- coding: utf-8 -*-
"""Rend chaque montage de scan/batch_manifest.json avec viral_cut.py.

- timeout par rendu (MM_RENDER_TIMEOUT, defaut 240 s) ; au timeout on tue SEULEMENT l'arbre du rendu
  (avant : `taskkill /IM ffmpeg.exe` detruisait tous les ffmpeg de la machine) et on supprime le fichier partiel ;
- un rendu deja valide (> 200 Ko) est saute ; `--force` re-rend tout.
Usage : python scan/render_batch.py [--force]
"""
import sys
from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parents[1]))
import json
import os

import mm_paths
from mm_run import run_tree

mm_paths.use_root()
PY = mm_paths.RENDER_PYTHON
TIMEOUT = int(os.environ.get("MM_RENDER_TIMEOUT", "240"))
MIN_SIZE = 200000
FORCE = "--force" in sys.argv


def valid(path):
    return os.path.exists(path) and os.path.getsize(path) > MIN_SIZE


def drop(path):
    try:
        os.remove(path)
    except OSError:
        pass


man = json.load(open("scan/batch_manifest.json", encoding="utf-8"))
ok, ko = [], []
for m in man:
    out = f"out/{m['id']}.mp4"
    if valid(out) and not FORCE:
        ok.append(m["id"])
        print("deja:", m["id"], flush=True)
        continue
    r = run_tree([PY, "-X", "utf8", "viral_cut.py", "--segments", f"scan/mont/{m['id']}.json",
                  "--music", f"public/{m['music']}", "--hook", m["hook"], "--outro", m["outro"],
                  "--target", str(m["target"]), "--out", out], timeout=TIMEOUT)
    if r.timed_out:
        drop(out)  # fichier partiel
        ko.append(m["id"])
        print(f"TIMEOUT {m['id']} (> {TIMEOUT} s, rendu interrompu)", flush=True)
        continue
    if valid(out):
        ok.append(m["id"])
        print(f"OK {m['id']} ({os.path.getsize(out) // 1024}Ko)", flush=True)
    else:
        if os.path.exists(out):
            drop(out)
        ko.append(m["id"])
        print(f"ECHEC {m['id']}: {(r.stderr or '')[-200:]}", flush=True)
print(f"\nBILAN RENDU: {len(ok)} OK, {len(ko)} KO {ko}", flush=True)
sys.exit(1 if ko else 0)
