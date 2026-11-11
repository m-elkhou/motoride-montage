# -*- coding: utf-8 -*-
"""Rend chaque montage de scan/batch_manifest.json avec viral_cut.py.

- timeout par rendu (MM_RENDER_TIMEOUT, defaut 240 s) ; au timeout on tue SEULEMENT l'arbre du rendu
  (avant : `taskkill /IM ffmpeg.exe` detruisait tous les ffmpeg de la machine) et on supprime le fichier partiel ;
- la VOIX (vo/<id>.wav, voix clonee, etape gen_vo_clone.py) est mixee par viral_cut.py dans la meme passe que la musique ;
- chaque rendu est controle (flux AAC sain, 48 kHz, memes durees audio/video) : sinon il est compte KO ;
- un rendu valide est saute SAUF si le plan, la voix, la musique ou le code ont change depuis (rendu obsolete) ;
  `--force` re-rend tout.
Usage : python scan/render_batch.py [--force]
"""
import sys
from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parents[1]))
import json
import os

import mm_audio
import mm_paths
from mm_run import run_tree

mm_paths.use_root()
PY = mm_paths.RENDER_PYTHON
TIMEOUT = int(os.environ.get("MM_RENDER_TIMEOUT", "240"))
MIN_SIZE = 200000
FORCE = "--force" in sys.argv


def valid(path):
    return os.path.exists(path) and os.path.getsize(path) > MIN_SIZE


def stale(out, inputs):
    """Vrai si un des fichiers d'entree est plus recent que le rendu."""
    t = os.path.getmtime(out)
    return any(os.path.exists(p) and os.path.getmtime(p) > t for p in inputs)


def drop(path):
    try:
        os.remove(path)
    except OSError:
        pass


man = json.load(open("scan/batch_manifest.json", encoding="utf-8"))
os.makedirs("out/_cat", exist_ok=True)
CODE = ["viral_cut.py", "mm_audio.py"]
ok, ko = [], []
for m in man:
    out = f"out/{m['id']}.mp4"
    # la voix CLONEE (.wav, scan/gen_vo_clone.py) : AUCUN repli vers une voix synthetique (l'ancienne voix neuronale etait
    # robotique et n'etait pas celle du proprietaire)
    voice = f"vo/{m['id']}.wav"
    seg, music = f"scan/mont/{m['id']}.json", f"public/{m['music']}"
    if not os.path.exists(voice):
        ko.append(m["id"])
        print(f"KO {m['id']}: voix absente ({voice}) : lancez scan/gen_vo_clone.py", flush=True)
        continue
    if valid(out) and not FORCE and not stale(out, [seg, voice, music, *CODE]):
        ok.append(m["id"])
        print("deja:", m["id"], flush=True)
        continue
    r = run_tree([PY, "-X", "utf8", "viral_cut.py", "--segments", seg, "--music", music,
                  "--hook", m["hook"], "--outro", m["outro"], "--target", str(m["target"]), "--voice", voice,
                  "--plan", f"out/{m['id']}.plan.json", "--audit-proxy", f"out/_cat/{m['id']}.mp4", "--out", out],
                 timeout=TIMEOUT)
    if r.timed_out:
        drop(out)  # fichier partiel
        ko.append(m["id"])
        print(f"TIMEOUT {m['id']} (> {TIMEOUT} s, rendu interrompu)", flush=True)
        continue
    if valid(out):
        bad = mm_audio.stream_problems(mm_audio.stream_report(out))
        if bad:
            ko.append(m["id"])
            print(f"KO {m['id']}: {'; '.join(bad)}", flush=True)
        else:
            ok.append(m["id"])
            print(f"OK {m['id']} ({os.path.getsize(out) // 1024}Ko)", flush=True)
    else:
        if os.path.exists(out):
            drop(out)
        ko.append(m["id"])
        print(f"ECHEC {m['id']}: {(r.stderr or '')[-200:]}", flush=True)
print()
print(f"BILAN RENDU: {len(ok)} OK, {len(ko)} KO {ko}", flush=True)
sys.exit(1 if ko else 0)
