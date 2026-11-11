# -*- coding: utf-8 -*-
"""Choisit les musiques MODERNES et MOTIVANTES de public/lib/ (bibliotheque audio YouTube, sans reclamation).

  python scan/music_catalog.py [--top 40] [--write]

Pour chaque piste : tempo (librosa, replie dans 95-150 BPM : un tempo « demi-temps » est double), niveau, et force du
DROP (rapport entre les passages forts et le niveau median : c'est ce que viral_cut.py cale a 35 % de la duree).
Ecrit public/lib/analysis.json. Avec --write, met la liste classee dans scan/gen_config.json -> "music" (fichier local) :
gen_batch.py la distribue ensuite aux montages (une piste par montage, en rotation).
Les pistes viennent de public/lib/catalog.json si present (titre, artiste, BPM annonce, voix) ; sinon les fichiers audio
du dossier. Une piste avec voix, de moins de 60 s, ou d'humeur sombre / melancolique / en colere, est ecartee.
"""
import sys
from pathlib import Path as _P

sys.path.insert(0, str(_P(__file__).resolve().parents[1]))
import json

import mm_paths

mm_paths.use_root()
LIB = _P("public/lib")
EXT = (".mp3", ".m4a", ".wav", ".ogg", ".flac", ".aac")
# Humeurs de la bibliotheque YouTube (libelles francais ou anglais) : une piste triste, sombre ou en colere ne motive pas.
SAD = ("melanc", "en colere", "angry", "sad", "triste", "calm", "sentiment", "dark")
UPBEAT = ("optimiste", "entrainante", "joyeuse", "funky", "bright", "happy", "inspir", "energ")


def _plain(text):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(text).lower()) if unicodedata.category(c) != "Mn")


def mood_score(info):
    """-1 : humeur a ecarter ; sinon 0..1 (part d'humeurs positives). Sans humeur connue : 0.5."""
    moods = [_plain(m) for m in info.get("moods", [])]
    if not moods:
        return 0.5
    if any(k in m for m in moods for k in SAD):
        return -1.0
    return min(1.0, sum(any(k in m for k in UPBEAT) for m in moods) / 2)


def analyse(path):
    import librosa
    import numpy as np
    y, sr = librosa.load(str(path), sr=22050, mono=True, duration=120)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    tempo = float(np.atleast_1d(tempo)[0])
    while tempo and tempo < 95:
        tempo *= 2
    while tempo > 150:
        tempo /= 2
    rms = librosa.feature.rms(y=y, hop_length=512)[0] + 1e-9
    loud = float(np.mean(np.sort(rms)[-max(1, len(rms) // 5):]))
    med = float(np.median(rms))
    return {"tempo": round(tempo, 1), "loud_db": round(20 * np.log10(loud), 1), "drop": round(loud / med, 2),
            "seconds": round(len(y) / sr, 1)}


def main(argv):
    top = int(argv[argv.index("--top") + 1]) if "--top" in argv else 40
    cat = {}
    cf = LIB / "catalog.json"
    if cf.exists():
        for e in json.load(open(cf, encoding="utf-8")):
            cat[e.get("file", "")] = e
    files = sorted(p for p in LIB.glob("*") if p.suffix.lower() in EXT)
    if not files:
        sys.exit(f"aucune piste dans {LIB} (la bibliotheque n'est pas encore telechargee)")
    rows, rows_skipped = [], []
    done = {}                                              # analyses deja faites : le calcul audio est long, on le garde
    if (LIB / "analysis.json").exists():
        for r in json.load(open(LIB / "analysis.json", encoding="utf-8")):
            done[r["file"]] = {k: r[k] for k in ("tempo", "loud_db", "drop", "seconds") if k in r}
    for p in files:
        info = cat.get(p.name, {})
        if info.get("includesVocals") or info.get("vocals"):
            continue
        try:
            a = dict(done.get(f"lib/{p.name}") or {}) if len(done.get(f"lib/{p.name}", {})) == 4 else analyse(p)
        except Exception as e:  # fichier illisible : on le dit et on continue
            print(f"illisible : {p.name} ({type(e).__name__})", flush=True)
            continue
        if a["seconds"] < 60:
            continue
        a.update(file=f"lib/{p.name}", title=info.get("title", p.stem), artist=info.get("artist", ""),
                 mood=mood_score(info), moods=info.get("moods", []))
        if a["mood"] < 0:                                  # sombre / melancolique / en colere : ecartee, on le dit
            print(f"ecartee (humeur) : {p.name}  {'/'.join(a['moods'])}", flush=True)
            rows_skipped.append(a)
            continue
        rows.append(a)
        print(f"{p.name[:38]:38s} {a['tempo']:6.1f} BPM  {a['loud_db']:6.1f} dB  drop x{a['drop']:.2f}", flush=True)
    # score : niveau fort + drop marque + humeur positive (normalises) ; tempos varies pour ne pas enchainer le meme rythme
    lo, hi = min(r["loud_db"] for r in rows), max(r["loud_db"] for r in rows)
    dmax = max(r["drop"] for r in rows)
    for r in rows:
        r["score"] = round(0.4 * (r["loud_db"] - lo) / max(hi - lo, 1e-6) + 0.3 * r["drop"] / dmax + 0.3 * r["mood"], 3)
    rows.sort(key=lambda r: -r["score"])
    chosen = rows[:top]
    chosen.sort(key=lambda r: r["tempo"])                 # entrelacement lent/rapide : on prend en alternant les deux bouts
    order, i, j = [], 0, len(chosen) - 1
    while i <= j:
        order.append(chosen[i])
        if i != j:
            order.append(chosen[j])
        i, j = i + 1, j - 1
    (LIB / "analysis.json").write_text(json.dumps(rows + rows_skipped, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(rows)} pistes motivantes, {len(rows_skipped)} ecartees (humeur), {len(order)} retenues (tempos {order[0]['tempo']}-{max(r['tempo'] for r in order)} BPM)")
    if "--write" in argv:
        cfgp = _P("scan/gen_config.json")
        cfg = json.loads(cfgp.read_text(encoding="utf-8")) if cfgp.exists() else {}
        cfg["music"] = [r["file"] for r in order]
        cfgp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"scan/gen_config.json : {len(order)} musiques ecrites (cle \"music\")")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
