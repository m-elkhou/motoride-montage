"""Orchestrateur : enchaine les etapes du pipeline, dans l'ordre, et s'arrete a la premiere erreur.

  python run_pipeline.py --list
  python run_pipeline.py                      # inventory -> meta (jamais l'envoi)
  python run_pipeline.py --from plan --to mix # une plage
  python run_pipeline.py --only render
  python run_pipeline.py --to upload          # + envoi, en SIMULATION (--dry-run)
  python run_pipeline.py --to upload --yes-upload   # envoi reel sur YouTube

L'envoi est la seule etape qui agit hors de la machine : elle n'a lieu que si on la demande
explicitement (--to upload / --only upload) et reste en simulation sans --yes-upload.
Chaque etape est reexecutable seule ; voir docs/pipeline/.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import mm_paths

# (nom, script, description)
STAGES = [
    ("inventory", "scan/inventory.py", "liste des clips (ffprobe)"),
    ("moments", "scan/moments.py", "meilleures fenetres par clip (reprise automatique)"),
    ("classify", "scan/classify.py", "etiquettes CLIP + score moto (reprise automatique)"),
    ("plan", "scan/gen_batch.py", "montages uniques + manifest + calendrier"),
    ("render", "scan/render_batch.py", "rendu viral_cut.py (saute les rendus valides)"),
    ("voice", "scan/gen_vo_edge.py", "voix courte edge-tts (saute les voix existantes)"),
    ("mix", "scan/overlay_vo.py", "voix sous la musique (idempotent)"),
    ("meta", "scan/make_meta.py", "meta/<id>.json avec signature + hashtags"),
    ("upload", "upload_short.py", "envoi YouTube (simulation sauf --yes-upload)"),
]
NAMES = [s[0] for s in STAGES]
DEFAULT_LAST = "meta"


def stage_command(name, script, yes_upload):
    root = mm_paths.ROOT
    if name != "upload":
        return [mm_paths.RENDER_PYTHON, "-X", "utf8", str(root / script)]
    try:
        ids = [m["id"] for m in json.load(open(root / "scan/batch_manifest.json", encoding="utf-8"))]
    except FileNotFoundError:
        ids = []  # pas encore de plan : l'uploader signalera "aucun fichier meta trouve"
    metas = [str(root / "meta" / f"{i}.json") for i in ids if (root / "meta" / f"{i}.json").exists()]
    cmd = ["uv", "run", "--project", str(mm_paths.S2S_ROOT), "python", "-X", "utf8", str(root / script), *metas,
           "--retry-min", "45", "--max-hours", "30"]
    return cmd if yes_upload else cmd + ["--dry-run"]


def select(frm, to, only):
    if only:
        return [only]
    i, j = NAMES.index(frm or NAMES[0]), NAMES.index(to or DEFAULT_LAST)
    if i > j:
        raise SystemExit(f"--from {frm} est apres --to {to}")
    return NAMES[i:j + 1]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--from", dest="frm", choices=NAMES)
    ap.add_argument("--to", choices=NAMES)
    ap.add_argument("--only", choices=NAMES)
    ap.add_argument("--yes-upload", action="store_true", help="envoi reel (sinon simulation)")
    a = ap.parse_args(argv)
    if a.list:
        for n, s, d in STAGES:
            print(f"  {n:10s} {s:24s} {d}")
        return 0
    todo = select(a.frm, a.to, a.only)
    print("etapes :", " -> ".join(todo), flush=True)
    for name in todo:
        script = dict((n, s) for n, s, _ in STAGES)[name]
        cmd = stage_command(name, script, a.yes_upload)
        print(f"\n=== {name} ===  {' '.join(Path(c).name if c == cmd[0] else c for c in cmd)[:150]}", flush=True)
        rc = subprocess.run(cmd, cwd=mm_paths.ROOT).returncode
        if rc != 0:
            print(f"\nARRET : l'etape '{name}' a echoue (code {rc}). Corrigez puis relancez avec --from {name}.", flush=True)
            return rc
    print("\npipeline termine.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
