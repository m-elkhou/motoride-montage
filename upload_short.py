"""Upload de Shorts YouTube (API Data v3) avec le token OAuth du projet voisin social2shorts.

Usage (depuis le dossier de social2shorts : `uv run python <ce fichier> ...`) :
  upload_short.py meta/a.json meta/b.json | "meta/g_*.json"   [--not-before HH:MM] [--retry-min 10]
                  [--max-hours 6] [--dry-run] [--ledger meta/_uploaded.json]

- TOUS les fichiers meta sont valides AVANT le premier envoi ; un meta invalide est signale et saute
  (il n'arrete plus tout le lot) ;
- chaque envoi reussi est ecrit dans le journal (`--ledger`, defaut meta/_uploaded.json) IMMEDIATEMENT :
  un plantage ne perd rien et une relance saute ce qui est deja parti (les anciens meta/_uploaded_*.json
  sont lus aussi) ;
- `publishAt` => envoi prive, publie a l'heure dite ; `containsSyntheticMedia` se lit dans le meta (defaut false).
Code de sortie : 0 si tout est parti, 1 s'il reste des echecs ou des meta invalides.
"""
import argparse
import glob
import json
import os
import socket
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mm_paths  # noqa: E402

REQUIRED = ("video", "title", "description", "tags")
PRIVACY = {"public", "unlisted", "private"}


# ───────────────────────── fonctions pures (testees, sans reseau) ─────────────────────────
def norm(p):
    """Cle stable d'un chemin (casse et separateurs Windows ignores)."""
    return os.path.normcase(os.path.abspath(str(p))).replace("\\", "/")


def expand_metas(args):
    """Arguments -> liste ordonnee de fichiers meta. Motifs (*, ?, [) developpes ; fichiers `_*.json` ignores."""
    out, seen = [], set()
    for a in args:
        found = sorted(glob.glob(a)) if any(c in a for c in "*?[") else [a]
        for f in found:
            p = Path(f)
            if p.name.startswith("_") or norm(p) in seen:
                continue
            seen.add(norm(p))
            out.append(p)
    return out


def validate_meta(meta):
    """Liste des erreurs d'un meta deja charge (liste vide = valide)."""
    errs = [f"champ manquant: {k}" for k in REQUIRED if k not in meta]
    if errs:
        return errs
    if not isinstance(meta["title"], str) or not 0 < len(meta["title"]) <= 100:
        errs.append("titre vide ou > 100 caracteres")
    if not isinstance(meta["tags"], list):
        errs.append("tags doit etre une liste")
    if not Path(meta["video"]).is_file():
        errs.append(f"video introuvable: {meta['video']}")
    if meta.get("privacy", "public") not in PRIVACY:
        errs.append(f"privacy invalide: {meta.get('privacy')}")
    if meta.get("publishAt"):
        try:
            datetime.fromisoformat(str(meta["publishAt"]).replace("Z", "+00:00"))
        except ValueError:
            errs.append(f"publishAt illisible: {meta['publishAt']}")
    return errs


def build_body(meta):
    """Corps de la requete videos.insert."""
    lang = meta.get("lang", "fr")
    body = {"snippet": {"title": meta["title"], "description": meta["description"], "tags": meta["tags"],
                        "categoryId": meta.get("categoryId", "2"),
                        "defaultLanguage": lang, "defaultAudioLanguage": lang},
            "status": {"privacyStatus": meta.get("privacy", "public"), "selfDeclaredMadeForKids": False,
                       "containsSyntheticMedia": bool(meta.get("containsSyntheticMedia", False))}}
    if meta.get("publishAt"):
        body["status"]["privacyStatus"] = "private"
        body["status"]["publishAt"] = meta["publishAt"]
    return body


def load_ledger(ledger_path, meta_dir):
    """Envois deja faits : journal courant + anciens meta/_uploaded_*.json. Retourne {cle_normalisee: id}."""
    done = {}
    files = sorted(Path(meta_dir).glob("_uploaded_*.json"))
    if Path(ledger_path).exists():
        files.append(Path(ledger_path))
    for f in files:
        try:
            for k, v in json.loads(f.read_text(encoding="utf-8")).items():
                done[norm(k)] = v
        except (ValueError, OSError):
            continue
    return done


def record_upload(ledger_path, meta_path, video_id):
    """Ajoute un envoi au journal, ecriture atomique (jamais de journal tronque)."""
    lp = Path(ledger_path)
    cur = {}
    if lp.exists():
        try:
            cur = json.loads(lp.read_text(encoding="utf-8"))
        except ValueError:
            cur = {}
    cur[norm(meta_path)] = video_id
    tmp = lp.with_suffix(lp.suffix + ".tmp")
    tmp.write_text(json.dumps(cur, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, lp)


# ───────────────────────── envoi ─────────────────────────
def import_credentials():
    """get_credentials de social2shorts (dependance explicite) ; message clair si introuvable."""
    try:
        from social2shorts.publish.youtube import get_credentials
        return get_credentials
    except ImportError:
        sys.path.insert(0, str(mm_paths.S2S_ROOT / "src"))
        try:
            from social2shorts.publish.youtube import get_credentials
            return get_credentials
        except ImportError as e:
            sys.exit(f"social2shorts introuvable ({e}).\n"
                     f"  Lancez ce script avec `uv run` depuis le dossier de social2shorts, ou definissez MM_S2S_ROOT "
                     f"(actuel : {mm_paths.S2S_ROOT}).")


def wait_until(hhmm):
    h, m = map(int, hhmm.split(":"))
    t = datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)
    if t < datetime.now():
        t += timedelta(days=1)
    while datetime.now() < t:
        print("attente jusqu'a", t.strftime("%H:%M"), flush=True)
        time.sleep(min(600, max(5, (t - datetime.now()).total_seconds())))


def upload_one(yt, meta, mp, args, deadline):
    """Envoie un meta. Retourne l'id video, ou None en cas d'echec definitif."""
    import httplib2
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    body, net_tries = build_body(meta), 0
    network_errors = (OSError, TimeoutError, httplib2.HttpLib2Error)  # ConnectionError, ssl.SSLError sont des OSError
    while True:
        try:
            req = yt.videos().insert(part="snippet,status", body=body, media_body=MediaFileUpload(
                str(meta["video"]), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True))
            resp = None
            while resp is None:
                _, resp = req.next_chunk(num_retries=3)
            return resp["id"]
        except HttpError as e:
            s = str(e)
            if "uploadLimitExceeded" in s and time.time() < deadline:
                print(f"limite d'envoi atteinte, nouvel essai dans {args.retry_min} min ({time.strftime('%H:%M')})", flush=True)
                time.sleep(args.retry_min * 60)
                continue
            print("ECHEC", mp, s[:300], flush=True)
            return None
        except network_errors as e:
            net_tries += 1
            if net_tries <= 5 and time.time() < deadline:
                print(f"erreur reseau ({type(e).__name__}: {str(e)[:120]}), reprise {net_tries}/5 dans 20s", flush=True)
                time.sleep(20)
                continue
            print("ECHEC", mp, "reseau:", str(e)[:200], flush=True)
            return None
        except Exception as e:  # inattendu : on le dit (type + message) et on passe au suivant
            print("ECHEC", mp, f"inattendu {type(e).__name__}: {str(e)[:200]}", flush=True)
            return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("meta", nargs="+", help="fichiers meta ou motifs (ex. \"meta/g_*.json\")")
    ap.add_argument("--not-before", help="HH:MM : ne pas commencer avant")
    ap.add_argument("--retry-min", type=int, default=10)
    ap.add_argument("--max-hours", type=float, default=6)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--ledger", default=str(mm_paths.META / "_uploaded.json"))
    a = ap.parse_args(argv)
    socket.setdefaulttimeout(180)

    metas = expand_metas(a.meta)
    if not metas:
        sys.exit("aucun fichier meta trouve")
    done = load_ledger(a.ledger, Path(a.ledger).parent)
    todo, invalid, skipped = [], [], []
    for mp in metas:  # validation de TOUT le lot avant le premier envoi
        try:
            meta = json.loads(mp.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            invalid.append(mp)
            print(f"INVALIDE {mp}: json illisible ({e})", flush=True)
            continue
        errs = validate_meta(meta)
        if errs:
            invalid.append(mp)
            print(f"INVALIDE {mp}: " + " ; ".join(errs), flush=True)
        elif norm(mp) in done:
            skipped.append(mp)
            print(f"DEJA ENVOYE {mp} -> https://youtube.com/shorts/{done[norm(mp)]}", flush=True)
        else:
            todo.append((mp, meta))
    print(f"{len(todo)} a envoyer, {len(skipped)} deja envoyes, {len(invalid)} invalides", flush=True)

    if a.dry_run:
        for mp, meta in todo:
            print("DRY", mp, meta["title"], f"{Path(meta['video']).stat().st_size / 1e6:.1f} MB", flush=True)
        return 1 if invalid else 0
    if not todo:
        return 1 if invalid else 0

    if a.not_before:
        wait_until(a.not_before)
    from googleapiclient.discovery import build
    get_credentials = import_credentials()
    s2s = mm_paths.S2S_ROOT
    creds = get_credentials(str(s2s / "secrets/client_secret.json"), str(s2s / "secrets/token.json"), interactive=False)
    yt = build("youtube", "v3", credentials=creds)
    deadline, failed = time.time() + a.max_hours * 3600, []
    for mp, meta in todo:
        vid = upload_one(yt, meta, mp, a, deadline)
        if vid:
            record_upload(a.ledger, mp, vid)  # immediat : rien n'est perdu si le processus meurt ensuite
            print(f"OK {mp} -> https://youtube.com/shorts/{vid}", flush=True)
        else:
            failed.append(mp)
    print(f"BILAN: {len(todo) - len(failed)} envoyes, {len(failed)} echecs, {len(invalid)} invalides", flush=True)
    return 1 if failed or invalid else 0


if __name__ == "__main__":
    sys.exit(main())
