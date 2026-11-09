# -*- coding: utf-8 -*-
"""Genere la voix COURTE de chaque montage (la ligne du hook) avec edge-tts -> vo/<id>.mp3.

Voix `en-US-GuyNeural`, vitesse +8 %. Necessite le reseau (service en ligne).
- reprise : une voix deja generee est conservee (`--force` pour tout regenerer) ;
- nouvel essai : 3 tentatives par montage (attente 2, 4 s) avant d'abandonner CE montage et de continuer.
Usage : python scan/gen_vo_edge.py [--force]
"""
import sys
from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parents[1]))
import asyncio
import json

import mm_paths

mm_paths.use_root()
VOICE = "en-US-GuyNeural"
RATE = "+8%"
RETRIES = 3
MIN_SIZE = 2000


def hook_line(m):
    return m["hook"].capitalize().rstrip(".") + "."


async def one(edge_tts, line, out):
    last = None
    for k in range(1, RETRIES + 1):
        try:
            await edge_tts.Communicate(line, voice=VOICE, rate=RATE).save(str(out))
            if out.exists() and out.stat().st_size > MIN_SIZE:
                return True
            last = RuntimeError("fichier vide")
        except Exception as e:  # service reseau : toute erreur = nouvel essai, jamais d'arret du lot
            last = e
        if k < RETRIES:
            await asyncio.sleep(2 * k)
    print(f"  echec apres {RETRIES} essais: {type(last).__name__}: {str(last)[:100]}", flush=True)
    return False


async def main(force):
    import edge_tts
    man = json.load(open("scan/batch_manifest.json", encoding="utf-8"))
    mm_paths.VO.mkdir(exist_ok=True)
    ko = []
    for i, m in enumerate(man, 1):
        out = mm_paths.VO / f"{m['id']}.mp3"
        if out.exists() and out.stat().st_size > MIN_SIZE and not force:
            print(f"[{i}/{len(man)}] {m['id']} deja", flush=True)
            continue
        line = hook_line(m)
        if await one(edge_tts, line, out):
            print(f"[{i}/{len(man)}] {m['id']} '{line}'", flush=True)
        else:
            ko.append(m["id"])
    print(f"DONE vo_edge ({len(ko)} KO {ko})", flush=True)
    return 1 if ko else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main("--force" in sys.argv)))
