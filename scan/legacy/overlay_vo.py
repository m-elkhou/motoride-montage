# -*- coding: utf-8 -*-
"""OBSOLETE : depuis le 10/11/2026 viral_cut.py mixe la voix dans la MEME passe que la musique (mm_audio.py :
voix traitee, musique baissee sous la voix, 48 kHz, flux controle). Ce script re-encodait l'audio d'un montage deja
fini (voix a peine au-dessus de la musique, flux AAC parfois corrompu). Conserve pour memoire, plus appele.

Mixe la voix courte (vo/<id>.mp3) LEGER par-dessus le phonk, debut a 0.4 s.
Remplace out/<id>.mp4 (video copiee, audio re-mux).

IDEMPOTENT : apres le mixage on ecrit un marqueur out/<id>.voiced contenant la signature (taille:date) du
fichier. Relancer ne mixe pas deux fois ; si le montage est re-rendu, la signature change et la voix est
remixee. Options :
  --force        remixe meme si le marqueur est valide (ATTENTION : double voix si deja mixe)
  --assume-done  n'ecrit que les marqueurs pour les videos DEJA voisees (migration), sans rien mixer
"""
import sys
from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parents[2]))
import json
import os
import shutil
import subprocess
import tempfile

import mm_paths

mm_paths.use_root()
FF = mm_paths.FFMPEG
MIN_SIZE = 200000
FC = "[1:a]adelay=400|400,volume=1.35[v];[0:a][v]amix=inputs=2:duration=first:normalize=0[a]"


def signature(path):
    s = os.stat(path)
    return f"{s.st_size}:{s.st_mtime_ns}"


def marker_for(video):
    return _P(video).with_suffix(".voiced")


def already_voiced(video):
    mk = marker_for(video)
    return mk.exists() and mk.read_text(encoding="utf-8").strip() == signature(video)


def mark(video):
    marker_for(video).write_text(signature(video), encoding="utf-8")


def main(argv):
    force, assume = "--force" in argv, "--assume-done" in argv
    man = json.load(open("scan/batch_manifest.json", encoding="utf-8"))
    ok, ko, skipped, absent = [], [], [], []
    for m in man:
        vid, vo = f"out/{m['id']}.mp4", f"vo/{m['id']}.mp3"
        if not os.path.exists(vid) or os.path.getsize(vid) < MIN_SIZE:
            absent.append(m["id"])  # rendu absent/invalide : rien a mixer (avertissement, pas un echec)
            continue
        if assume:
            mark(vid)
            skipped.append(m["id"])
            continue
        if already_voiced(vid) and not force:
            skipped.append(m["id"])
            continue
        if not os.path.exists(vo):
            ko.append(m["id"] + "(voix manquante)")
            continue
        with tempfile.NamedTemporaryFile(suffix=".mp4", dir="out", delete=False) as tf:
            tmp = tf.name
        try:
            subprocess.run([FF, "-y", "-i", vid, "-i", vo, "-filter_complex", FC,
                            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                            "-movflags", "+faststart", tmp],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
            if os.path.getsize(tmp) > MIN_SIZE:
                shutil.move(tmp, vid)
                mark(vid)
                ok.append(m["id"])
            else:
                ko.append(m["id"])
        except subprocess.TimeoutExpired:
            ko.append(m["id"] + "(timeout)")
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    print(f"VOIX MIXEE: {len(ok)} OK, {len(skipped)} deja faits/marques, {len(ko)} KO {ko}", flush=True)
    if absent:
        print(f"  avertissement : {len(absent)} video(s) absente(s)/invalide(s), non traitee(s) : {absent}", flush=True)
    return 1 if ko else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
