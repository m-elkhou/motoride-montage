# -*- coding: utf-8 -*-
"""Genere meta/<id>.json (entree de upload_short.py) depuis scan/batch_manifest.json.

C'etait l'etape manquante du pipeline. Chaque meta contient : video, titre, description, tags, categorie,
langue, privacy et publishAt. La description est toujours : accroche du theme, ligne de presentation,
VOTRE SIGNATURE, puis les hashtags (tags + #Shorts).

Usage : python scan/make_meta.py [--out meta] [--signature "..."] [--privacy private] [--force]
- un meta existant n'est PAS ecrase sans --force ; une video absente est sautee (avertissement) ;
- signature : --signature, sinon `description_signature` de social2shorts (config.toml, table [youtube]).
  Sans signature le script S'ARRETE (elle doit figurer sur chaque video) sauf `--no-signature` ;
- textes : valeurs par defaut ci-dessous, surchargeables dans scan/gen_config.json -> "descriptions"
  ({"about": "...", "intro": {"pov": "...", "rider": "...", "crew": "..."}}).
"""
import sys
from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parents[1]))
import argparse
import json
import tomllib
from pathlib import Path

import mm_config
import mm_paths

DEFAULT_ABOUT = "🏍️ Moto Ride Vlog : des sorties moto filmées au guidon. Abonne-toi pour la suite."
DEFAULT_INTRO = {
    "pov": "La route, le moteur, et plus rien d'autre. 🔥",
    "rider": "L'esprit motard, filmé au plus près. 🔥",
    "crew": "Rouler à plusieurs, c'est autre chose. 🔥",
}


def hashtags(tags):
    """tags -> '#moto #motopov ... #Shorts' (espaces retires, #Shorts toujours en dernier)."""
    out = ["#" + t.replace(" ", "") for t in tags if t.replace(" ", "")]
    if "#Shorts" not in out:
        out.append("#Shorts")
    return " ".join(out)


def build_description(manifest_entry, signature, about, intro):
    parts = [intro.get(manifest_entry["theme"], ""), about, signature, hashtags(manifest_entry["tags"])]
    return "\n\n".join(p for p in parts if p)


def build_meta(m, video_path, description, privacy="private", lang="fr", category="2"):
    return {"video": Path(video_path).as_posix(), "title": m["title"], "privacy": privacy,
            "publishAt": m["publishAt"], "categoryId": category, "lang": lang, "tags": m["tags"],
            "description": description}


def default_signature():
    cfg = mm_paths.S2S_ROOT / "config.toml"
    try:
        data = tomllib.loads(cfg.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return data.get("youtube", {}).get("description_signature") or data.get("description_signature", "")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(mm_paths.META))
    ap.add_argument("--signature", default=None)
    ap.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-signature", action="store_true", help="autorise des descriptions sans signature")
    a = ap.parse_args(argv)
    mm_paths.use_root()
    cfg = mm_config.load().get("descriptions", {})
    about = cfg.get("about", DEFAULT_ABOUT)
    intro = {**DEFAULT_INTRO, **cfg.get("intro", {})}
    sig = a.signature if a.signature is not None else default_signature()
    if not sig and not a.no_signature:
        sys.exit("aucune signature (Instagram...) : passez --signature, definissez description_signature dans "
                 "social2shorts/config.toml ([youtube]), ou --no-signature pour l'omettre volontairement.")
    man = json.load(open("scan/batch_manifest.json", encoding="utf-8"))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    made, kept, absent = [], [], []
    for m in man:
        dest = out / f"{m['id']}.json"
        video = mm_paths.OUT / f"{m['id']}.mp4"
        if not video.is_file():
            absent.append(m["id"])
            continue
        if dest.exists() and not a.force:
            kept.append(m["id"])
            continue
        meta = build_meta(m, video, build_description(m, sig, about, intro), privacy=a.privacy)
        dest.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        made.append(m["id"])
    print(f"meta: {len(made)} ecrits, {len(kept)} deja presents (conserves), {len(absent)} sans video {absent}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
