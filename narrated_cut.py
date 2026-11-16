# -*- coding: utf-8 -*-
"""Montage NARRE : la duree vient de la narration, les plans changent sur les phrases et sur le rythme, les mots
s'affichent un a un, la voix passe devant la musique.

Entree : un plan JSON (ecrit par un planificateur ; toutes les durees de plan sont en IMAGES, la somme fait la video) :
  {"fps": 30, "size": [1080, 1920],
   "voice": "narration.wav", "voice_start": 0.5, "words": "narration_words.json",
   "music": "morceau.mp3" ou null, "music_offset": 27.7, "drop": 35.4 ou null,
   "handle": "@ma_chaine", "keywords": ["LIBRE", ...], "intro_hit": true (coup grave sur la premiere image),
   "caption": {"max_words": 2, "max_chars": 13} (taille des blocs de sous-titres ; defaut 3 mots, 16 caracteres),
   "shots": [{"clip": "...", "src": 12.3, "frames": 45, "rate": 1.0, "push": 0.06, "punch": false}, ...]}

Sorties, a cote de --out :
  <out>.mp4         voix + musique (son original, reutilisable)
  <out>_voix.mp4    voix seule + effets : pour ajouter un son du catalogue Shorts dans l'appli YouTube
  <out>_proxy.mp4   plans masques, sans texte ni etalonnage : pour l'audit d'anonymat et la relecture des planches
  <out>_report.json durees, plaques masquees par plan, niveaux sonores
  <out>_plates_masked.jpg / _plates_visible.jpg  recadrages des pistes floutees / laissees visibles (a relire)

Etapes : decoupe de chaque plan (recadrage 9:16, vitesse, zoom lent) -> masquage des plaques (mm_plates, environnement
a part) -> assemblage -> etalonnage, eclair sur le temps fort, sous-titres -> son -> multiplexage. L'encodage de la video
et celui du son restent separes (ffmpeg 9 se fige sur un graphe unique : voir viral_cut.py).

  python narrated_cut.py --plan plan.json --out out/nom [--keep] [--no-plates] [--cache dossier]
--cache : garde chaque plan decoupe et ses detections de plaques (cle = clip, instant, duree, vitesse, zoom) : un second
rendu apres un changement de quelques plans ne refait que ceux-la.
"""
import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import mm_paths

FF, FP = mm_paths.FFMPEG, mm_paths.FFPROBE
GRADE = "eq=contrast=1.10:saturation=1.20:brightness=0.005,vignette=PI/6"
FONT_WORDS, FONT_HANDLE = "Montserrat Black", "Montserrat ExtraBold"
WHITE, ACTIVE, KEY = "&H00FFFFFF", "&H0019D9FF", "&H001A6CFF"     # ASS : &HAABBGGRR (jaune, orange)
CAPTION_Y, CAPTION_MAXW, CAPTION_MAX_PT, CAPTION_MIN_PT = 0.63, 800, 112, 62
CHAR_W = 0.70          # largeur moyenne d'une capitale Montserrat Black, en fraction du corps
SR = 48000
FINAL_LUFS, FINAL_TP = -14, -1
VOICE_OVER_MUSIC = 6.0  # dB : voix au-dessus de la musique dans le passage courant (le temps fort monte au-dessus)
VOICE_LEVEL = -17.0     # dB : niveau des passages parles avant mixage (le premix arrive pres de -14 LUFS : la
                        # normalisation finale reste lineaire, sans pompage)


def run(cmd, timeout=900):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"{Path(str(cmd[0])).name} a echoue : {r.stderr[-600:]}")
    return r


def duration(path):
    r = subprocess.run([FP, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


# ---------------------------------------------------------------- sous-titres mot a mot

def clean_word(w):
    """Mot affiche : capitales, sans la ponctuation faible ; « ? » et « ! » sont gardes."""
    w = w.strip().upper().replace("’", "'")
    w = re.sub(r"\s+([?!])", r"\1", w)
    return w.rstrip(".,;:…").strip()


def chunks(words, max_words=3, max_chars=16):
    """Regroupe les mots d'une ligne en blocs courts : jamais a cheval sur une ponctuation forte, 2 a 3 mots au plus."""
    out, cur = [], []
    for w in words:
        text = clean_word(w["w"])
        if not text:
            continue
        item = {"text": text, "a": w["a"], "b": w["b"]}
        size = sum(len(x["text"]) for x in cur) + len(cur) + len(text)
        if cur and (len(cur) >= max_words or size > max_chars):
            out.append(cur)
            cur = []
        cur.append(item)
        if re.search(r"[.?!;:…]$", w["w"].strip()) or w["w"].strip().endswith(","):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def ass_time(t):
    t = max(0.0, t)
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def caption_events(lines, start, keywords=(), hold=0.45, max_words=3, max_chars=16):
    """lines : [{"words": [{"w", "a", "b"}]}] (instants dans la narration). -> [(debut, fin, texte ASS)] en temps video.
    Un bloc reste a l'ecran tant qu'il est dit ; chaque mot apparait a son instant, le mot en cours est colore."""
    blocks = [c for ln in lines for c in chunks(ln["words"], max_words, max_chars)]
    keys = {k.upper() for k in keywords}
    events = []
    for bi, blk in enumerate(blocks):
        nxt = blocks[bi + 1][0]["a"] if bi + 1 < len(blocks) else None
        end = blk[-1]["b"] + hold
        if nxt is not None:
            end = min(end, nxt) if nxt - blk[-1]["b"] > 0.6 else nxt
        text_len = sum(len(w["text"]) for w in blk) + len(blk) - 1
        pt = int(max(CAPTION_MIN_PT, min(CAPTION_MAX_PT, CAPTION_MAXW / (CHAR_W * max(1, text_len)))))
        for k, w in enumerate(blk):
            t0 = w["a"]
            t1 = blk[k + 1]["a"] if k + 1 < len(blk) else end
            parts = []
            for j, x in enumerate(blk):
                bare = re.sub(r"[^\w']", "", x["text"])
                if j < k:
                    parts.append(f"{{\\alpha&H00&\\c{WHITE}}}{x['text']}")
                elif j == k:
                    parts.append(f"{{\\alpha&H00&\\c{KEY if bare in keys else ACTIVE}}}{x['text']}")
                else:
                    parts.append(f"{{\\alpha&HFF&}}{x['text']}")
            pop = "\\fscx86\\fscy86\\t(0,90,\\fscx100\\fscy100)" if k == 0 else ""
            events.append((start + t0, start + t1, f"{{\\fs{pt}{pop}}}" + " ".join(parts)))
    return events


def write_ass(path, events, size, total, handle=None):
    w, h = size
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: W,{FONT_WORDS},96,{WHITE},{WHITE},&H00000000,&H78000000,0,0,0,0,100,100,1,0,1,8,4,5,40,40,0,1
Style: H,{FONT_HANDLE},66,{WHITE},{WHITE},&H00000000,&H78000000,0,0,0,0,100,100,2,0,1,6,3,5,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    rows = [f"Dialogue: 0,{ass_time(a)},{ass_time(b)},W,,0,0,0,,{{\\an5\\pos({w // 2},{int(h * CAPTION_Y)})}}{t}"
            for a, b, t in events if b > a]
    if handle:
        rows.append(f"Dialogue: 1,{ass_time(total - 2.4)},{ass_time(total)},H,,0,0,0,,"
                    f"{{\\an5\\pos({w // 2},{int(h * 0.76)})\\fad(350,0)}}{handle}")
    Path(path).write_text(head + "\n".join(rows) + "\n", encoding="utf-8-sig")


# ---------------------------------------------------------------- image

def ease(x):
    return 0.5 - 0.5 * math.cos(math.pi * min(1.0, max(0.0, x)))


def zoom_at(k, n, push=0.0, punch=False):
    """Facteur de zoom de l'image k d'un plan de n images : zoom lent (push > 0 avance, < 0 recule) et « coup » d'entree."""
    z = 1.0 + (abs(push) * (ease(k / max(1, n - 1)) if push >= 0 else 1.0 - ease(k / max(1, n - 1))))
    if punch:
        z *= 1.0 + 0.07 * math.exp(-k / 2.5)
    return z


def cut_shot(shot, dst, size, fps):
    """Decoupe un plan : recadrage 9:16, vitesse, nombre d'images exact, zoom. Sans son."""
    w, h = size
    n, rate = int(shot["frames"]), float(shot.get("rate", 1.0))
    need = n / fps * rate + 0.4
    vf = [f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos", f"crop={w}:{h}"]
    if rate != 1.0:
        vf.append(f"setpts=PTS/{rate:.4f}")
    vf.append(f"minterpolate=fps={fps}:mi_mode=blend" if rate < 0.8 else f"fps={fps}")
    src = [FF, "-v", "error", "-ss", f"{max(0.0, shot['src']):.3f}", "-t", f"{need:.3f}", "-i", shot["clip"], "-an",
           "-vf", ",".join(vf), "-frames:v", str(n)]
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "12", "-pix_fmt", "yuv420p", str(dst)]
    push, punch = float(shot.get("push", 0.0)), bool(shot.get("punch"))
    if not push and not punch:
        run([*src[:1], "-y", *src[1:], *enc])
    else:
        import cv2
        import numpy as np
        dec = subprocess.Popen([*src, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
        out = subprocess.Popen([FF, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(fps),
                                "-i", "-", "-an", *enc], stdin=subprocess.PIPE)
        k = 0
        while True:
            buf = dec.stdout.read(w * h * 3)
            if len(buf) < w * h * 3:
                break
            fr = np.frombuffer(buf, np.uint8).reshape(h, w, 3)
            z = zoom_at(k, n, push, punch)
            m = np.float32([[z, 0, (1 - z) * w / 2], [0, z, (1 - z) * h / 2]])
            out.stdin.write(cv2.warpAffine(fr, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT).tobytes())
            k += 1
        dec.stdout.close()
        dec.wait()
        out.stdin.close()
        if out.wait() != 0:
            raise RuntimeError(f"encodage du plan en echec : {dst}")
    got = frame_count(dst)
    if got != n:
        raise RuntimeError(f"plan trop court dans la source : {got} images au lieu de {n} ({shot['clip']} a {shot['src']} s)")


def shot_key(shot, size, fps):
    """Cle de cache d'un plan : tout ce qui change ses images (source, instant, duree, vitesse, zoom, cadre)."""
    st = Path(shot["clip"]).stat()
    spec = [shot["clip"], st.st_size, int(st.st_mtime), round(float(shot["src"]), 3), int(shot["frames"]),
            float(shot.get("rate", 1.0)), float(shot.get("push", 0.0)), bool(shot.get("punch")), list(size), fps]
    return hashlib.sha1(json.dumps(spec).encode("utf-8")).hexdigest()[:16]


def load_detections(path, frames):
    """Detections en cache d'un plan, ou None s'il faut redetecter (pas de cache, fichier absent ou illisible, nombre
    d'images different de celui du plan)."""
    if not path or not Path(path).exists():
        return None
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except ValueError:
        return None
    return d if len(d.get("per_frame", ())) == int(frames) else None


def output_base(out, plates):
    """Prefixe des fichiers ecrits. Un rendu SANS masquage des plaques (essai de mise en page) porte un autre nom : il ne
    doit jamais passer pour le rendu masque."""
    out = Path(out)
    return out if plates else out.with_name(out.name + "_sans_flou")


def frame_count(path):
    r = subprocess.run([FP, "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries", "stream=nb_read_packets",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return int(r.stdout.strip().strip(","))
    except ValueError:
        return 0


def _plates_python(args, timeout=3600):
    run([mm_paths.PLATES_PYTHON, "-X", "utf8", str(Path(__file__).resolve().parent / "mm_plates.py"), *args], timeout=timeout)


def mask_plates(raw, segs, tmp, sheet_prefix, det_cache=None, frames=None):
    """Masque les plaques de chaque plan : detection (environnement du detecteur), tri des pistes (CLIP : plaque d'un
    vehicule, ou compteur, autocollant, ciel ? voir mm_scene.must_blur), puis masquage. -> rapport par plan ; ecrit deux
    planches de recadrages (pistes masquees / pistes laissees visibles) pour la relecture.
    det_cache : pour chaque plan, fichier JSON ou relire / ecrire ses detections (None : pas de cache) ; frames : nombre
    d'images attendu de chaque plan (un cache d'une autre longueur n'est pas relu)."""
    import cv2
    import numpy as np

    import mm_plates
    import mm_scene
    det_cache = det_cache or [None] * len(raw)
    frames = frames or [None] * len(raw)
    dets = [(load_detections(c, n) if n is not None else (json.loads(c.read_text(encoding="utf-8")) if c and c.exists() else None))
            for c, n in zip(det_cache, frames)]
    todo = [i for i, d in enumerate(dets) if d is None]
    if todo:
        det_file = tmp / "plates_det.json"
        spec = tmp / "plates_detect.jobs.json"
        spec.write_text(json.dumps({"jobs": [str(raw[i]) for i in todo], "report": str(det_file), "ffmpeg": FF, "ffprobe": FP}),
                        encoding="utf-8")
        _plates_python(["detectmany", str(spec)])
        for i, d in zip(todo, json.loads(det_file.read_text(encoding="utf-8"))):
            dets[i] = d
            if det_cache[i]:
                det_cache[i].write_text(json.dumps(d), encoding="utf-8")
    judge = None
    jobs, report, crops = [], [], {"masked": [], "visible": []}
    for i, (src, dst, d) in enumerate(zip(raw, segs, dets)):
        w, h, n = d["w"], d["h"], len(d["per_frame"])
        tracks = mm_plates.link_tracks(d["per_frame"])
        wanted = {}                                   # image -> [(piste, boite)] : au plus 5 echantillons par piste
        for ti, tr in enumerate(tracks):
            pick = sorted({round(k * (len(tr) - 1) / 4) for k in range(5)}) if len(tr) > 1 else [0]
            for k in pick:
                wanted.setdefault(tr[k][0], []).append((ti, tr[k][1]))
        samples, thumbs = {}, {}
        if wanted:
            judge = judge or mm_scene.PlateJudge()
            for fi, fr in enumerate(mm_plates.read_frames(src, w, h, FF)):
                for ti, box in wanted.get(fi, []):
                    x0, y0, x1, y1 = mm_scene.context_box(box, w, h)
                    crop = fr[y0:y1, x0:x1]
                    samples.setdefault(ti, []).append((judge.prob(crop), (box[1] + box[3]) / 2 / h, (box[2] - box[0]) / w))
                    if ti not in thumbs:
                        t = cv2.resize(crop, (200, 200))
                        sx, sy = 200 / max(1, x1 - x0), 200 / max(1, y1 - y0)
                        cv2.rectangle(t, (int((box[0] - x0) * sx), int((box[1] - y0) * sy)),
                                      (int((box[2] - x0) * sx), int((box[3] - y0) * sy)), (0, 0, 255), 1)
                        thumbs[ti] = t
        keep = [ti for ti in range(len(tracks)) if mm_scene.must_blur(samples.get(ti, []))]
        doubts = [ti for ti in range(len(tracks)) if ti not in keep and mm_scene.doubt(samples.get(ti, []))]
        for ti in range(len(tracks)):
            t = thumbs.get(ti)
            if t is not None:
                cv2.rectangle(t, (0, 0), (200, 20), (0, 0, 180) if ti in doubts else (0, 0, 0), -1)
                cv2.putText(t, f"plan {i} img {tracks[ti][0][0]} P{max(x[0] for x in samples[ti]):.2f}" + (" DOUTE" if ti in doubts else ""),
                            (3, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)
                crops["masked" if ti in keep else "visible"].append(t)
        masks = mm_plates.masks_from_tracks([tracks[ti] for ti in keep], n, w, h)
        jobs.append([str(src), str(dst), masks])
        def entry(ti):
            return {"p": round(max(x[0] for x in samples[ti]), 2) if samples.get(ti) else None,
                    "cy": round(sum((b[1] + b[3]) / 2 for _, b in tracks[ti]) / len(tracks[ti]) / h, 2),
                    "w": max(b[2] - b[0] for _, b in tracks[ti]), "n": len(tracks[ti])}
        report.append({"shot": i, "frames": n, "tracks": len(tracks), "masked_tracks": len(keep),
                       "visible_tracks": len(tracks) - len(keep), "doubts": len(doubts), "frames_masked": sum(1 for m in masks if m),
                       "max_w": max((b[2] - b[0] for ti in keep for _, b in tracks[ti]), default=0),
                       "masked": [entry(ti) for ti in keep],
                       "visible": [{**entry(ti), "doubt": ti in doubts} for ti in range(len(tracks)) if ti not in keep]})
    spec = tmp / "plates_apply.jobs.json"
    spec.write_text(json.dumps({"jobs": jobs, "ffmpeg": FF, "ffprobe": FP}), encoding="utf-8")
    _plates_python(["applymany", str(spec)])
    for name, tiles in crops.items():
        if not tiles:
            continue
        cols = 8
        tiles = tiles + [np.zeros((200, 200, 3), np.uint8)] * (-len(tiles) % cols)
        cv2.imwrite(f"{sheet_prefix}_plates_{name}.jpg", np.vstack([np.hstack(tiles[k:k + cols]) for k in range(0, len(tiles), cols)]),
                    [cv2.IMWRITE_JPEG_QUALITY, 88])
    return report


# ---------------------------------------------------------------- son

def synth_impact(path, riser=1.9, tail=1.6):
    """Montee de souffle puis coup grave, synthetises (aucun droit) : le coup tombe a `riser` secondes du debut
    (riser=0 : le coup seul)."""
    import numpy as np
    import soundfile as sf
    rng = np.random.default_rng(7)
    n1, n2 = int(riser * SR), int(tail * SR)
    rise = np.zeros(0)
    if n1:
        t1 = np.arange(n1) / SR
        k = np.exp(-np.arange(64) / 32.0)                       # souffle adouci (moyenne glissante courte)
        rise = np.convolve(rng.standard_normal(n1), k / k.sum(), mode="same") * (t1 / riser) ** 2.6 * 0.22
    t2 = np.arange(n2) / SR
    f = 44 + 70 * np.exp(-t2 * 9)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t2 * 3.2) * 0.9
    crack = rng.standard_normal(n2) * np.exp(-t2 * 26) * 0.35
    y = np.concatenate([rise, boom + crack]).astype(np.float32)
    sf.write(str(path), y / max(1e-9, np.abs(y).max()) * 0.85, SR)
    return riser


def speech_level(path):
    """Niveau moyen (dB) des passages parles d'un fichier."""
    import numpy as np
    import soundfile as sf
    y, _ = sf.read(str(path), dtype="float32")
    if y.ndim > 1:
        y = y.mean(axis=1)
    n = 2048
    fr = np.sqrt(np.mean(y[: len(y) // n * n].reshape(-1, n) ** 2, axis=1))
    keep = fr > np.percentile(fr, 95) * 10 ** (-25 / 20)
    return float(20 * np.log10(np.sqrt(np.mean(fr[keep] ** 2)) + 1e-9))


def band_level(path, a, b):
    """Niveau moyen (dB) d'un fichier entre a et b secondes (via ffmpeg : le morceau peut etre un mp3)."""
    r = subprocess.run([FF, "-hide_banner", "-nostats", "-ss", f"{a:.2f}", "-t", f"{b - a:.2f}", "-i", str(path), "-af",
                        "volumedetect", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", r.stderr)
    if r.returncode != 0 or not m:                 # ne pas inventer un niveau : la musique sortirait trop forte ou muette
        raise RuntimeError(f"niveau introuvable entre {a:.1f} et {b:.1f} s de {path} : {r.stderr.strip()[-200:]}")
    return float(m.group(1))


def loudnorm_to(src, dst):
    p1 = subprocess.run([FF, "-hide_banner", "-nostats", "-i", str(src), "-af",
                         f"loudnorm=I={FINAL_LUFS}:TP={FINAL_TP}:LRA=11:print_format=json", "-f", "null", "-"],
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    mj = re.search(r"\{[^{}]*input_i[^{}]*\}", p1.stderr, re.S)
    ln = f"loudnorm=I={FINAL_LUFS}:TP={FINAL_TP}:LRA=11"
    info = {}
    if mj:
        j = json.loads(mj.group(0))
        info = {"input_i": j["input_i"], "input_tp": j["input_tp"], "loudnorm": "deux passes"}
        ln += (f":measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}"
               f":measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
    else:                                          # mesure absente : une seule passe, dynamique ; le rapport le dit
        info = {"loudnorm": "une passe (mesure absente)"}
        print(f"ATTENTION : mesure de niveau absente pour {Path(src).name}, normalisation en une passe", file=sys.stderr)
    run([FF, "-y", "-v", "error", "-i", str(src), "-af", f"{ln},aresample={SR}", "-ar", str(SR), "-ac", "2",
         "-c:a", "aac", "-b:a", "192k", str(dst)])
    return info


def build_audio(plan, total, tmp, with_music):
    """Voix (deja masterisee) + musique baissee sous la voix + effet sur le temps fort. -> (fichier m4a, infos)"""
    voice, start = plan["voice"], float(plan.get("voice_start", 0.5))
    drop = plan.get("drop")
    inputs, graph, mix = ["-i", str(voice)], [], []
    measured = speech_level(voice)
    gv = VOICE_LEVEL - measured
    graph.append(f"[0:a]aresample={SR},volume={gv:.2f}dB,alimiter=limit=0.84:attack=3:release=60:level=0,"
                 f"adelay={int(start * 1000)}:all=1,apad=whole_dur={total:.3f},aformat=channel_layouts=stereo,asplit=2[v][sc]")
    mix.append("[v]")
    info = {"voice_level_db": VOICE_LEVEL, "voice_gain_db": round(gv, 1)}
    idx = 1
    if with_music and plan.get("music"):
        off = float(plan.get("music_offset", 0.0))
        have = duration(plan["music"])
        if have < off + total:                     # sinon la musique s'arrete en cours de video, sans un mot dans le rapport
            raise RuntimeError(f"la musique dure {have:.1f} s : il en faut {off + total:.1f} (music_offset {off:.1f} s + "
                               f"video {total:.1f} s)")
        ref_a, ref_b = off + min(4.0, total / 4), off + (drop - 1.0 if drop else total)
        g = (info["voice_level_db"] - VOICE_OVER_MUSIC) - band_level(plan["music"], ref_a, max(ref_a + 2, ref_b))
        inputs += ["-i", str(plan["music"])]
        graph.append(f"[{idx}:a]aresample={SR},atrim=start={off:.3f},asetpts=PTS-STARTPTS,atrim=0:{total:.3f},"
                     f"aformat=channel_layouts=stereo,volume={g:.2f}dB,afade=t=in:d=0.4,"
                     f"afade=t=out:st={total - 1.2:.3f}:d=1.2[m]")
        graph.append("[m][sc]sidechaincompress=threshold=0.03:ratio=3:attack=12:release=320:makeup=1[md]")
        mix.append("[md]")
        info["music_gain_db"] = round(g, 1)
        idx += 1
    else:
        graph.append("[sc]anullsink")
    if drop:
        fx = tmp / "impact.wav"
        lead = synth_impact(fx, riser=min(1.9, max(0.0, float(drop))))     # temps fort avant 1,9 s : montee raccourcie
        inputs += ["-i", str(fx)]
        graph.append(f"[{idx}:a]aresample={SR},adelay={int(max(0.0, drop - lead) * 1000)}:all=1,volume=-7dB,"
                     f"aformat=channel_layouts=stereo[fx]")
        mix.append("[fx]")
    if plan.get("intro_hit"):
        fx0 = tmp / "hit.wav"
        synth_impact(fx0, riser=0.0, tail=1.2)
        inputs += ["-i", str(fx0)]
        n_in = len(inputs) // 2 - 1
        graph.append(f"[{n_in}:a]aresample={SR},adelay=30:all=1,volume=-10dB,aformat=channel_layouts=stereo[hit]")
        mix.append("[hit]")
    graph.append(f"{''.join(mix)}amix=inputs={len(mix)}:duration=first:normalize=0,"
                 f"alimiter=limit=0.93:attack=3:release=50:level=0,atrim=0:{total:.3f}[mix]")
    name = "mix" if with_music else "voix"
    pre = tmp / f"pre_{name}.wav"
    run([FF, "-y", "-v", "error", *inputs, "-filter_complex", ";".join(graph), "-map", "[mix]", "-ar", str(SR), "-ac", "2", str(pre)])
    out = tmp / f"{name}.m4a"
    info.update(loudnorm_to(pre, out))
    return out, info


# ---------------------------------------------------------------- montage

def render(plan, out, keep=False, plates=True, cache=None):
    out = output_base(out, plates)
    out.parent.mkdir(parents=True, exist_ok=True)
    for suffix in (".mp4", "_voix.mp4", "_proxy.mp4", "_captions.ass", "_report.json", "_plates_masked.jpg", "_plates_visible.jpg"):
        (out.parent / (out.name + suffix)).unlink(missing_ok=True)     # aucun fichier d'un rendu precedent ne passe pour celui-ci
    fps, size = int(plan.get("fps", 30)), tuple(plan.get("size", [1080, 1920]))
    shots = plan["shots"]
    total = sum(int(s["frames"]) for s in shots) / fps
    words = json.loads(Path(plan["words"]).read_text(encoding="utf-8"))
    vend = float(plan.get("voice_start", 0.5)) + float(words["dur"])
    if vend > total - 0.3:
        raise RuntimeError(f"la narration finit a {vend:.2f} s, la video a {total:.2f} s : il manque des plans")
    if total > 59.5:
        raise RuntimeError(f"video de {total:.1f} s : un Short de plus d'une minute est bloque a la moindre reclamation")
    import mm_plates
    tmp = Path(tempfile.mkdtemp(prefix="narr_", dir=str(out.parent)))
    try:
        raw, det_cache = [], []
        if cache:
            Path(cache).mkdir(parents=True, exist_ok=True)
        for i, s in enumerate(shots):
            key = shot_key(s, size, fps) if cache else None
            p = Path(cache) / f"raw_{key}.mp4" if cache else tmp / f"raw_{i:03d}.mp4"
            if not (cache and p.exists() and frame_count(p) == int(s["frames"])):
                cut_shot(s, p, size, fps)
            raw.append(p)
            det_cache.append(Path(cache) / f"det_{key}_{mm_plates.signature()}.json" if cache else None)
        report = {"total": round(total, 3), "shots": len(shots), "plates_masked": bool(plates), "doubts": 0, "plates": None}
        segs = raw
        if plates:
            segs = [tmp / f"seg_{i:03d}.mp4" for i in range(len(raw))]
            report["plates"] = mask_plates(raw, segs, tmp, str(out.parent / out.name), det_cache, [int(s["frames"]) for s in shots])
            report["doubts"] = sum(r["doubts"] for r in report["plates"])
        lst = tmp / "list.txt"
        lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in segs), encoding="utf-8")
        proxy = out.parent / (out.name + "_proxy.mp4")
        run([FF, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(proxy)])
        ass = tmp / "captions.ass"
        cap = plan.get("caption", {})
        write_ass(ass, caption_events(words["lines"], float(plan.get("voice_start", 0.5)), plan.get("keywords", ()),
                                      max_words=int(cap.get("max_words", 3)), max_chars=int(cap.get("max_chars", 16))),
                  size, total, plan.get("handle"))
        vf = [GRADE]
        if plan.get("drop"):
            d = float(plan["drop"])
            vf.append(f"eq=brightness='0.55*gte(t,{d:.3f})*max(0,1-(t-{d:.3f})/0.22)':eval=frame")
        esc = ass.as_posix().replace(":", "\\:")
        vf.append(f"ass='{esc}'")
        vid = tmp / "video.mp4"
        run([FF, "-y", "-v", "error", "-i", str(proxy), "-vf", ",".join(vf) + ",format=yuv420p", "-an", "-c:v", "libx264",
             "-preset", "medium", "-crf", "20", "-r", str(fps), str(vid)])
        results = {}
        for name, with_music in (("", True), ("_voix", False)):
            if with_music and not plan.get("music"):
                continue
            a, info = build_audio(plan, total, tmp, with_music)
            dst = out.parent / (out.name + name + ".mp4")
            run([FF, "-y", "-v", "error", "-i", str(vid), "-i", str(a), "-map", "0:v", "-map", "1:a", "-c", "copy",
                 "-movflags", "+faststart", "-t", f"{total:.3f}", str(dst)])
            results[dst.name] = {**info, "duration": round(duration(dst), 3), "bytes": dst.stat().st_size}
        report["outputs"] = results
        shutil.copyfile(ass, out.parent / (out.name + "_captions.ass"))
        (out.parent / (out.name + "_report.json")).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        return report
    finally:
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description="Montage narre (voir l'en-tete du fichier)")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--keep", action="store_true", help="garde le dossier de travail")
    ap.add_argument("--no-plates", action="store_true", help="saute le masquage des plaques (essai de mise en page seulement)")
    ap.add_argument("--cache", help="dossier de cache des plans decoupes et de leurs detections")
    a = ap.parse_args()
    rep = render(json.loads(Path(a.plan).read_text(encoding="utf-8")), a.out, keep=a.keep, plates=not a.no_plates, cache=a.cache)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    if not rep["plates_masked"]:
        print("ATTENTION : rendu SANS masquage des plaques (fichiers « _sans_flou ») : jamais a publier", file=sys.stderr)
    if rep["doubts"]:
        print(f"DOUTE : {rep['doubts']} detection(s) large(s) laissee(s) visible(s) alors que le tri penche pour une plaque : "
              "regarder la planche « _plates_visible.jpg » (vignettes a bandeau rouge) ou remplacer le plan", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
