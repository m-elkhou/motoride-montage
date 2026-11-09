# -*- coding: utf-8 -*-
"""Re-rendu des 8 montages avec musique PHONK libre de droits (Pixabay, sans attribution).
Rend dans out/_ph/ ; on bascule vers out/ apres verification."""
NOTE = "ponctuel : re-rendu des 8 premiers montages ; garde pour reference (ranger dans scan/legacy/)"
import sys
from pathlib import Path as _P
sys.path.insert(0,str(_P(__file__).resolve().parents[2]))
import mm_paths
mm_paths.use_root()
import subprocess, os
PY = mm_paths.RENDER_PYTHON
# (nom_final, fichier_segments, musique_phonk, hook_a_l_ecran, duree_s)
JOBS = [
 ("m_mountain",   "scan/mont/mountain.json", "ph_aura.mp3",    "THE ROAD THAT CLEARS YOUR HEAD", 18),
 ("m_paris",      "scan/mont/paris.json",    "ph_monda.mp3",   "PARIS FROM THE SADDLE",          18),
 ("viral_night_v3","scan/mont/night.json",   "ph_hard.mp3",    "PARIS AT 3 A.M.",                18),
 ("m_crew",       "scan/mont/crew_p.json",   "ph_aggr.mp3",    "POV: YOU FOUND YOUR CREW",       18),
 ("m_winter",     "scan/mont/winter_p.json", "ph_drift.mp3",   "WINTER CAN'T STOP THE CREW",     18),
 ("m_meet",       "scan/mont/meet_p.json",   "ph_vaitsez.mp3", "COUNT THE BIKES",                16),
 ("m_rally",      "scan/mont/alpes_p.json",  "ph_arp1.mp3",    "RALLY DAY WITH THE CREW",        20),
 ("m_alps",       "scan/mont/golden_p.json", "ph_arp2.mp3",    "THE ALPS NEVER DISAPPOINT",      18),
]
ok, ko = [], []
for name, seg, music, hook, target in JOBS:
    out = f"out/_ph/{name}.mp4"
    print(f"\n=== {name} | {music} | '{hook}' | {target}s ===", flush=True)
    r = subprocess.run([PY,"-X","utf8","viral_cut.py","--segments",seg,"--music",f"public/{music}",
                        "--hook",hook,"--target",str(target),"--out",out],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    for l in r.stdout.splitlines():
        if l.startswith(("OK","ECHEC","musique","plan")): print("  "+l[:160], flush=True)
    if os.path.exists(out) and os.path.getsize(out) > 200000:
        ok.append(name); print(f"  -> {os.path.getsize(out)//1024} Ko", flush=True)
    else:
        ko.append(name); print("  -> ECHEC\n"+(r.stderr[-500:] if r.stderr else ""), flush=True)
print(f"\n=== BILAN: {len(ok)} OK {ok} | {len(ko)} KO {ko} ===", flush=True)
