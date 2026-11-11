# -*- coding: utf-8 -*-
"""Description YouTube : REGLE STRICTE du proprietaire (10/11/2026), dans les deux depots (motoride-montage et
social2shorts) : la description est TOUJOURS detaillee, avec SA SIGNATURE (son Instagram) puis des HASHTAGS tout a la fin.

Forme obligatoire : texte detaille (au moins 150 caracteres, au moins deux paragraphes) -> signature (contient son
Instagram) -> derniere ligne = uniquement des hashtags (au moins 3). `description_problems` renvoie la liste des
manquements ; l'envoi (upload_short.py) REFUSE tout meta dont la liste n'est pas vide, et sans signature configuree.

La signature n'est JAMAIS ecrite dans le code : elle vient de la configuration locale
(`description_signature` de social2shorts/config.toml, table [youtube]) ou de --signature.
"""
import re
import tomllib

import mm_paths

MIN_BODY_CHARS = 150
MIN_HASHTAGS = 3
TAG = re.compile(r"#\w+")


def hashtags(tags):
    """tags -> '#moto #motopov ... #Shorts' (espaces retires, #Shorts toujours en dernier)."""
    out = ["#" + t.replace(" ", "") for t in tags if t.replace(" ", "")]
    if "#Shorts" not in out:
        out.append("#Shorts")
    return " ".join(out)


def default_signature():
    cfg = mm_paths.S2S_ROOT / "config.toml"
    try:
        data = tomllib.loads(cfg.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return data.get("youtube", {}).get("description_signature") or data.get("description_signature", "")


def build_description(entry, signature, about, intro, cta=""):
    """accroche du theme, presentation, appel a l'abonnement, SIGNATURE, puis les hashtags (toujours en dernier)."""
    parts = [intro.get(entry["theme"], ""), about, cta, signature, hashtags(entry["tags"])]
    return "\n\n".join(p for p in parts if p)


def description_problems(description, signature):
    """Manquements a la regle (liste vide = description conforme)."""
    problems = []
    sig = (signature or "").strip()
    if not sig:
        problems.append("signature non configuree (description_signature)")
    elif "@" not in sig and "instagram" not in sig.lower():
        problems.append("la signature doit contenir l'Instagram du proprietaire")
    lines = [ln.strip() for ln in (description or "").strip().splitlines() if ln.strip()]
    last = lines[-1] if lines else ""
    tags = TAG.findall(last)
    if not tags or re.sub(r"#\w+|\s", "", last):
        problems.append("la derniere ligne doit etre uniquement des hashtags")
    elif len(tags) < MIN_HASHTAGS:
        problems.append(f"moins de {MIN_HASHTAGS} hashtags")
    if sig:
        pos = (description or "").rfind(sig)
        if pos < 0:
            problems.append("signature absente de la description")
        elif last and pos > (description or "").rfind(last):
            problems.append("la signature doit se trouver AVANT les hashtags")
    body = [ln for ln in lines[:-1] if ln != sig and not (TAG.fullmatch(ln.split()[0]) if ln.split() else False)]
    if sum(len(ln) for ln in body) < MIN_BODY_CHARS or len(body) < 2:
        problems.append(f"description trop courte : au moins {MIN_BODY_CHARS} caracteres sur 2 paragraphes de texte")
    return problems
