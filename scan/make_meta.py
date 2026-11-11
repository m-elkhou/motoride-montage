# -*- coding: utf-8 -*-
"""Genere meta/<id>.json (entree de upload_short.py) depuis scan/batch_manifest.json.

C'etait l'etape manquante du pipeline. Chaque meta contient : video, titre, description, tags, categorie,
langue, privacy et publishAt. REGLE STRICTE (mm_description.py) : la description est TOUJOURS detaillee (accroche,
presentation, appel a l'abonnement), puis VOTRE SIGNATURE (votre Instagram), puis les hashtags TOUT A LA FIN.

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
from pathlib import Path

import mm_config
import mm_description
import mm_paths

DEFAULT_ABOUT = ("🏍️ Des sorties moto filmées au guidon : des routes de montagne, des lignes droites, des virages et "
                 "ces moments de liberté qu'on ne trouve que sur deux roues. De nouveaux Shorts chaque semaine.")
DEFAULT_CTA = "🔔 Abonne-toi et active la cloche pour ne rien rater, et dis-moi en commentaire où tu roules ! 💬"
DEFAULT_INTRO = {
    "pov": "La route, le moteur, et plus rien d'autre : monte derrière le guidon le temps d'un Short. 🔥",
    "rider": "L'esprit motard, filmé au plus près : la moto, la route et la passion qui va avec. 🔥",
    "crew": "Rouler à plusieurs, c'est autre chose : la route se partage. 🔥",
}
# textes propres a la chaine (nom, ton) : dans scan/gen_config.json -> "descriptions" (fichier local, hors depot)

hashtags = mm_description.hashtags
build_description = mm_description.build_description
default_signature = mm_description.default_signature


def build_meta(m, video_path, description, privacy="private", lang="fr", category="2"):
    return {"video": Path(video_path).as_posix(), "title": m["title"], "privacy": privacy,
            "publishAt": m["publishAt"], "categoryId": category, "lang": lang, "tags": m["tags"],
            "description": description}


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
    cta = cfg.get("cta", DEFAULT_CTA)
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
        desc = build_description(m, sig, about, intro, cta)
        bad = [] if a.no_signature else mm_description.description_problems(desc, sig)
        if bad:
            sys.exit(f"description non conforme pour {m['id']} : {' ; '.join(bad)}")
        meta = build_meta(m, video, desc, privacy=a.privacy)
        dest.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        made.append(m["id"])
    print(f"meta: {len(made)} ecrits, {len(kept)} deja presents (conserves), {len(absent)} sans video {absent}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
