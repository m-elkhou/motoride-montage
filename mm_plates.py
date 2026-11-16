# -*- coding: utf-8 -*-
"""Plaques d'immatriculation : detection et masquage (regle du proprietaire : aucune plaque lisible a l'image).

Le detecteur (YOLOv9 « license plate » du paquet open-image-models, ONNX) tourne sur des TUILES a la resolution du
montage : une plaque de moto fait 40 a 120 px de large dans une image 1080x1920, et disparait si l'image entiere est
reduite a 608 px. Le seuil est volontairement bas : on prefere flouter un panneau que laisser une plaque.

Dans le temps : les detections sont reliees en pistes ; une piste est masquee sans trou (boite interpolee entre deux
detections, le detecteur clignotant sur les petites plaques), HOLD images avant et apres, la boite grossissant avec
l'ecart pour suivre le mouvement. Le masque est un flou tres fort borde d'un fondu : aucun caractere n'est recuperable.
Le detecteur prend aussi pour des plaques le compteur, l'ecran du GPS et les etiquettes du reservoir. Le montage narre
trie donc les pistes entre deux passes (`detectmany`, puis `applymany`) : mm_scene.PlateJudge et mm_scene.must_blur
laissent visibles celles qui ne sont, sans aucun doute, pas la plaque d'un vehicule ; tout le reste est floute.

Les regles (tuiles, fusion, maintien, agrandissement) sont des fonctions pures, testees sans modele. Le detecteur a
son propre environnement (onnxruntime) : ce module n'importe ni torch ni le reste du moteur.

  python mm_plates.py mask  <entree.mp4> <sortie.mp4> [--report r.json] [--conf 0.12] [--hold 8]
  python mm_plates.py detectmany <travaux.json>   {"jobs": [video, ...], "report": "r.json"} : detections seulement
  python mm_plates.py applymany <travaux.json>    {"jobs": [[entree, sortie, masques par image], ...]} : masquage seulement
  python mm_plates.py probe <image ou video> [...] [--out dossier]     images annotees, pour regler les seuils
La relecture des planches reste obligatoire : un detecteur ne voit pas tout.
"""
import json
import subprocess
import sys
from pathlib import Path

MODEL = "yolo-v9-s-608-license-plate-end2end"
CONF = 0.12          # seuil bas : un faux positif coute un petit flou, un oubli coute une plaque lisible
TILE = 640           # cote d'une tuile (px) ; le modele attend 608
OVERLAP = 0.3        # recouvrement mini entre tuiles voisines : une plaque a cheval reste entiere dans l'une d'elles
HOLD = 8             # images de maintien avant et apres chaque detection (0,27 s a 30 img/s)
GROW = 0.35          # agrandissement de la boite (fraction de sa taille) de chaque cote
GROW_PER_FRAME = 0.06  # agrandissement supplementaire par image d'ecart pendant le maintien
MIN_PAD = 6          # marge mini en pixels
EDGE = 0.06          # un cote du masque a moins de 6 % d'un bord de l'image est prolonge jusqu'au bord
MERGE_IOU = 0.2
SIZE_RATIO = 2.0     # deux boites dont la plus grande dimension differe de plus de 2 fois ne sont pas le meme objet :
                     # un faux positif geant (tableau de bord, pan de ciel) n'absorbe pas la plaque qu'il recouvre
MAX_GAP = 24         # ecart maxi (images) entre deux detections d'un meme objet
PERSIST = 0.4        # une piste presente sur 40 % du plan est masquee sur tout le plan
WHOLE_SHOT = 90      # dans un plan de 3 s ou moins (en images), tout masque est tenu du debut a la fin : un flou qui
                     # s'arrete avant la fin du plan laisse l'objet lisible sur les dernieres images (relecture du 14/11)


def axis_starts(size, tile, overlap=OVERLAP):
    """Origines des tuiles le long d'un axe : couvrent [0, size] avec au moins `overlap` de recouvrement."""
    if size <= tile:
        return [0]
    n = 2
    while (n * tile - size) / (n - 1) < overlap * tile:
        n += 1
    return [round(i * (size - tile) / (n - 1)) for i in range(n)]


def tiles(w, h, tile=TILE, overlap=OVERLAP):
    """Tuiles (x0, y0, x1, y1) couvrant une image w x h."""
    return [(x, y, min(w, x + tile), min(h, y + tile)) for y in axis_starts(h, tile, overlap) for x in axis_starts(w, tile, overlap)]


def iou(a, b):
    ix0, iy0, ix1, iy1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def merge(boxes, thr=MERGE_IOU):
    """Fusionne les boites (x0, y0, x1, y1, score) qui se recouvrent (meme plaque vue par deux tuiles) : union."""
    out = []
    for b in sorted(boxes, key=lambda q: -q[4]):
        for i, k in enumerate(out):
            if _comparable(b, k) and (iou(b, k) >= thr or _inside(b, k) or _inside(k, b)):
                out[i] = (min(b[0], k[0]), min(b[1], k[1]), max(b[2], k[2]), max(b[3], k[3]), max(b[4], k[4]))
                break
        else:
            out.append(tuple(b))
    return out


def _inside(a, b):
    """a presque entierement dans b."""
    ix0, iy0, ix1, iy1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    area = (a[2] - a[0]) * (a[3] - a[1])
    return area > 0 and max(0, ix1 - ix0) * max(0, iy1 - iy0) / area >= 0.7


def _comparable(a, b, ratio=SIZE_RATIO):
    """Deux boites de tailles voisines (leur plus grande dimension differe de moins de `ratio` fois)."""
    sa, sb = max(a[2] - a[0], a[3] - a[1]), max(b[2] - b[0], b[3] - b[1])
    return max(sa, sb) <= ratio * max(1, min(sa, sb))


def signature():
    """Empreinte des reglages qui changent les detections : un cache fait avec d'autres reglages n'est pas relu."""
    import hashlib
    spec = [MODEL, CONF, TILE, OVERLAP, MERGE_IOU, SIZE_RATIO, 2]        # dernier terme : version de la detection
    return hashlib.sha1(json.dumps(spec).encode("utf-8")).hexdigest()[:8]


def grow(box, w, h, ratio=GROW, min_pad=MIN_PAD, edge=EDGE):
    """Boite agrandie de `ratio` de chaque cote (au moins `min_pad` px), bornee a l'image. Un cote arrive a moins de
    `edge` (fraction de l'image) d'un bord est prolonge jusqu'au bord : une plaque a moitie hors champ est detectee
    trop courte, et la partie qui depasse du flou reste lisible. -> (x0, y0, x1, y1) entiers."""
    x0, y0, x1, y1 = box[:4]
    px, py = max(min_pad, (x1 - x0) * ratio), max(min_pad, (y1 - y0) * ratio)
    x0, y0, x1, y1 = max(0, int(x0 - px)), max(0, int(y0 - py)), min(w, int(x1 + px + 0.999)), min(h, int(y1 + py + 0.999))
    return (0 if x0 < edge * w else x0, 0 if y0 < edge * h else y0, w if x1 > (1 - edge) * w else x1, h if y1 > (1 - edge) * h else y1)


def _same_object(a, b, gap):
    """Deux boites a `gap` images d'ecart peuvent-elles etre le meme objet ? (tailles voisines, centres proches a
    l'echelle de la boite). Sans la condition de taille, une boite geante vue sur une image rejoignait la piste de la
    plaque voisine, et toute la piste etait jugee comme une boite geante (relecture du 16/11)."""
    if not _comparable(a, b):
        return False
    size = max(a[2] - a[0], a[3] - a[1], b[2] - b[0], b[3] - b[1])
    dx = (a[0] + a[2]) / 2 - (b[0] + b[2]) / 2
    dy = (a[1] + a[3]) / 2 - (b[1] + b[3]) / 2
    return (dx * dx + dy * dy) ** 0.5 <= 1.5 * size + min(150, 6 * gap)


def link_tracks(per_frame, max_gap=MAX_GAP):
    """Relie les detections d'images successives en pistes (un objet suivi dans le temps).
    per_frame : pour chaque image, la liste des boites (x0, y0, x1, y1[, score]). -> [[(image, boite), ...], ...]"""
    tracks = []
    for i, boxes in enumerate(per_frame):
        open_ = [t for t in tracks if 0 < i - t[-1][0] <= max_gap]
        for b in sorted(boxes, key=lambda q: -(q[2] - q[0]) * (q[3] - q[1])):
            cands = [t for t in open_ if _same_object(b, t[-1][1], i - t[-1][0])]
            if cands:
                best = min(cands, key=lambda t: abs((b[0] + b[2]) - (t[-1][1][0] + t[-1][1][2])) + abs((b[1] + b[3]) - (t[-1][1][1] + t[-1][1][3])))
                best.append((i, tuple(b[:4])))
                open_.remove(best)
            else:
                tracks.append([(i, tuple(b[:4]))])
    return tracks


def masks_from_tracks(tracks, n, w, h, hold=HOLD, ratio=GROW, per_frame_grow=GROW_PER_FRAME, persist=PERSIST):
    """tracks : pistes de `link_tracks` (celles a masquer) ; n : nombre d'images. -> pour chaque image, les boites A MASQUER.

    Chaque piste est masquee sans trou : entre deux detections la boite est interpolee ; avant la premiere et apres la
    derniere elle est maintenue `hold` images, en grossissant avec l'ecart. Une piste presente sur plus de `persist` de
    la duree (une plaque suivie) est masquee d'un bout a l'autre du plan : un flou qui apparait et disparait attire
    l'oeil et laisse passer des images."""
    out = [[] for _ in range(n)]
    for tr in tracks:
        first, last = tr[0][0], tr[-1][0]
        whole = n <= WHOLE_SHOT or ((last - first + 1) >= persist * n and len(tr) >= 3) or is_static(tr)
        lo = 0 if whole else max(0, first - hold)
        hi = n - 1 if whole else min(n - 1, last + hold)
        for j in range(lo, first):
            out[j].append(grow(tr[0][1], w, h, ratio + min(0.5, per_frame_grow * (first - j))))
        for j in range(last + 1, hi + 1):
            out[j].append(grow(tr[-1][1], w, h, ratio + min(0.5, per_frame_grow * (j - last))))
        for (i0, b0), (i1, b1) in zip(tr, tr[1:] + [tr[-1]]):
            for j in (range(i0, i1) if i1 > i0 else [i0]):
                f = (j - i0) / (i1 - i0) if i1 > i0 else 0.0
                box = tuple(b0[k] + (b1[k] - b0[k]) * f for k in range(4))
                out[j].append(grow(box, w, h, ratio + min(0.3, 0.03 * min(j - i0, i1 - j))))
    return out


def is_static(track, min_len=3):
    """Piste d'un objet qui ne bouge pas dans l'image (etiquette, ecran, moto garee dans un plan fixe) : ses boites
    restent a moins d'une demi-boite de la premiere. Un tel objet est masque sur TOUT le plan : un flou qui disparait
    en cours de plan le laisse lisible sur les images suivantes (relecture du 14/11)."""
    if len(track) < min_len:
        return False
    x0, y0, x1, y1 = track[0][1][:4]
    size = max(x1 - x0, y1 - y0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return all(abs((b[0] + b[2]) / 2 - cx) <= 0.5 * size and abs((b[1] + b[3]) / 2 - cy) <= 0.5 * size for _, b in track)


def track_masks(per_frame, w, h, hold=HOLD):
    """Toutes les detections sont masquees (aucun tri) : voir `masks_from_tracks`."""
    return masks_from_tracks(link_tracks(per_frame), len(per_frame), w, h, hold)


def blur_boxes(frame, boxes):
    """Masque les boites (x0, y0, x1, y1) d'une image BGR, sur place : flou tres fort, bord fondu. Un cote de la boite
    colle au bord de l'image n'est PAS fondu : le fondu laissait une bande presque nette le long du bord, la ou passe
    justement une plaque a moitie hors champ (relecture du 16/11)."""
    import cv2
    import numpy as np
    fh, fw = frame.shape[:2]
    for x0, y0, x1, y1 in boxes:
        roi = frame[y0:y1, x0:x1]
        if roi.size == 0:
            continue
        bh, bw = roi.shape[:2]
        small = cv2.resize(roi, (max(2, bw // 16), max(2, bh // 16)), interpolation=cv2.INTER_AREA)   # pixelise d'abord :
        soft = cv2.resize(small, (bw, bh), interpolation=cv2.INTER_LINEAR)                             # plus aucun trait fin
        k = max(3, (min(bw, bh) // 2) | 1)
        soft = cv2.GaussianBlur(soft, (k, k), 0)
        f = max(2, min(bw, bh) // 6)
        left, top = (0 if x0 <= 0 else f), (0 if y0 <= 0 else f)
        right, bottom = (0 if x1 >= fw else f), (0 if y1 >= fh else f)
        core = np.zeros((bh, bw), np.float32)                    # le coeur (la plaque elle-meme) est toujours opaque
        core[top:bh - bottom, left:bw - right] = 1.0
        mask = cv2.GaussianBlur(core, (2 * f + 1, 2 * f + 1), 0, borderType=cv2.BORDER_REPLICATE)
        mask = np.maximum(mask, core)[..., None]
        roi[:] = (soft * mask + roi * (1.0 - mask)).astype(np.uint8)
    return frame


class PlateDetector:
    """Detecteur de plaques sur tuiles. `detect(bgr)` -> [(x0, y0, x1, y1, score)] en pixels de l'image."""

    def __init__(self, conf=CONF, model=MODEL, providers=None):
        import onnxruntime as ort
        from open_image_models import create_detector
        if providers is None:
            avail = ort.get_available_providers()
            providers = [p for p in ("DmlExecutionProvider", "CUDAExecutionProvider") if p in avail] + ["CPUExecutionProvider"]
        self.conf = conf
        self.det = create_detector(model, conf_thresh=conf, providers=providers)
        self.providers = providers

    def detect(self, bgr):
        h, w = bgr.shape[:2]
        found = []
        for x0, y0, x1, y1 in tiles(w, h):
            crop = bgr[y0:y1, x0:x1]
            for d in self.det.predict(crop):
                b = d.bounding_box
                found.append((b.x1 + x0, b.y1 + y0, b.x2 + x0, b.y2 + y0, float(d.confidence)))
        for d in self.det.predict(bgr):                         # image entiere : les plaques proches, plus grandes qu'une tuile
            b = d.bounding_box
            found.append((b.x1, b.y1, b.x2, b.y2, float(d.confidence)))
        return merge(found)


def probe_video(path, ffprobe="ffprobe"):
    r = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate",
                        "-of", "json", str(path)], capture_output=True, text=True)
    s = json.loads(r.stdout)["streams"][0]
    a, b = s["r_frame_rate"].split("/")
    return int(s["width"]), int(s["height"]), float(a) / float(b)


def read_frames(path, w, h, ffmpeg="ffmpeg"):
    """Generateur d'images BGR (numpy) d'une video, dans l'ordre."""
    import numpy as np
    p = subprocess.Popen([ffmpeg, "-v", "error", "-i", str(path), "-an", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         stdout=subprocess.PIPE)
    size = w * h * 3
    try:
        while True:
            buf = p.stdout.read(size)
            if len(buf) < size:
                break
            yield np.frombuffer(buf, np.uint8).reshape(h, w, 3).copy()
    finally:
        p.stdout.close()
        p.wait()


def detect_video(src, det, ffmpeg="ffmpeg", ffprobe="ffprobe"):
    """Detections de chaque image d'une video. -> {"w", "h", "fps", "per_frame": [[[x0, y0, x1, y1, score], ...], ...]}"""
    w, h, fps = probe_video(src, ffprobe)
    per_frame = [[[int(b[0]), int(b[1]), int(b[2]), int(b[3]), round(float(b[4]), 3)] for b in det.detect(fr)]
                 for fr in read_frames(src, w, h, ffmpeg)]
    return {"w": w, "h": h, "fps": fps, "per_frame": per_frame}


def apply_masks(src, dst, masks, ffmpeg="ffmpeg", ffprobe="ffprobe", crf=14):
    """Ecrit `dst` = `src` (video sans son) avec, pour chaque image, les boites de `masks` floutees. -> nombre d'images."""
    w, h, fps = probe_video(src, ffprobe)
    enc = subprocess.Popen([ffmpeg, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", f"{fps:.6f}",
                            "-i", "-", "-an", "-c:v", "libx264", "-preset", "fast", "-crf", str(crf), "-pix_fmt", "yuv420p",
                            str(dst)], stdin=subprocess.PIPE)
    n = 0
    for i, fr in enumerate(read_frames(src, w, h, ffmpeg)):
        if i < len(masks) and masks[i]:
            blur_boxes(fr, [tuple(int(v) for v in b[:4]) for b in masks[i]])
        enc.stdin.write(fr.tobytes())
        n += 1
    enc.stdin.close()
    if enc.wait() != 0 or n != len(masks):
        raise RuntimeError(f"masquage incomplet : {n} images ecrites pour {len(masks)} attendues ({dst})")
    return n


def mask_video(src, dst, det, hold=HOLD, ffmpeg="ffmpeg", ffprobe="ffprobe", crf=14):
    """Masque TOUTES les detections de `src` et ecrit `dst` (deux passes : detection, puis masquage).
    -> rapport {frames, frames_with_plate, frames_masked, boxes, max_w}."""
    d = detect_video(src, det, ffmpeg, ffprobe)
    masks = track_masks(d["per_frame"], d["w"], d["h"], hold)
    apply_masks(src, dst, masks, ffmpeg, ffprobe, crf)
    boxes = [b for fr in d["per_frame"] for b in fr]
    return {"frames": len(masks), "frames_with_plate": sum(1 for b in d["per_frame"] if b), "frames_masked": sum(1 for m in masks if m),
            "boxes": len(boxes), "max_w": max((b[2] - b[0] for b in boxes), default=0)}


def _arg(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("mask", "detectmany", "applymany", "probe"):
        print(__doc__)
        return 2
    if sys.argv[1] == "applymany":               # aucun modele a charger : les masques sont deja decides
        spec = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        n = sum(apply_masks(a, b, m, spec.get("ffmpeg", "ffmpeg"), spec.get("ffprobe", "ffprobe")) for a, b, m in spec["jobs"])
        print(f"{len(spec['jobs'])} plan(s) ecrits, {n} images")
        return 0
    det = PlateDetector(conf=float(_arg("--conf", CONF)))
    if sys.argv[1] == "detectmany":
        spec = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        reps = [detect_video(a, det, spec.get("ffmpeg", "ffmpeg"), spec.get("ffprobe", "ffprobe")) for a in spec["jobs"]]
        Path(spec["report"]).write_text(json.dumps(reps), encoding="utf-8")
        print(f"{len(reps)} plan(s), {sum(1 for r in reps for f in r['per_frame'] if f)} image(s) avec detection, "
              f"fournisseur {det.providers[0]}")
        return 0
    if sys.argv[1] == "mask":
        rep = mask_video(sys.argv[2], sys.argv[3], det, hold=int(_arg("--hold", HOLD)))
        if "--report" in sys.argv:
            Path(_arg("--report", "")).write_text(json.dumps(rep), encoding="utf-8")
        print(f"{rep['frames']} images, plaque detectee sur {rep['frames_with_plate']}, masquees {rep['frames_masked']}, "
              f"largeur maxi {rep['max_w']} px")
        return 0
    import cv2
    out = Path(_arg("--out", "plates_probe"))
    out.mkdir(parents=True, exist_ok=True)
    paths = [a for a in sys.argv[2:] if not a.startswith("--") and a != str(out) and a != _arg("--conf", "")]
    for p in paths:
        img = cv2.imread(p)
        if img is None:
            continue
        boxes = det.detect(img)
        for x0, y0, x1, y1, s in boxes:
            cv2.rectangle(img, (int(x0), int(y0)), (int(x1), int(y1)), (0, 0, 255), 3)
            cv2.putText(img, f"{s:.2f}", (int(x0), max(20, int(y0) - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        cv2.imwrite(str(out / (Path(p).stem + "_plates.jpg")), img)
        print(Path(p).name, [(int(b[0]), int(b[1]), int(b[2]), int(b[3]), round(b[4], 2)) for b in boxes])
    return 0


if __name__ == "__main__":
    sys.exit(main())
