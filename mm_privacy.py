# -*- coding: utf-8 -*-
"""Porte « anonymat » : detecteurs et regles communs (pool de clips, montages finis).

Regle : AUCUN visage visible (meme dans un casque ouvert ou a visiere relevee), AUCUNE autre personne proche
du pilote. Les detections de visage a score bas sont du bruit (mains, tableaux de bord, feuillage) : seul un score
confiant refuse l'image, et la RELECTURE HUMAINE des planches (scan/privacy_check.py) couvre le reste. Les regles sont des fonctions pures (testees sans modele) ;
les detecteurs ne se chargent qu'a la demande.

  visages   : OpenCV YuNet (models/face_detection_yunet_2023mar.onnx, `python mm_privacy.py --fetch-model`)
  personnes : RT-DETR (transformers, PekingU/rtdetr_r50vd) ; deux personnes ou plus = refus
"""
import sys
import urllib.request

import mm_paths

FACE_URL = ("https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/"
            "face_detection_yunet_2023mar.onnx")
FACE_MODEL = mm_paths.ROOT / "models" / "face_detection_yunet_2023mar.onnx"
PERSON_MODEL = "PekingU/rtdetr_r50vd"

# Resolution d'analyse FIXE (celle du pool et celle de l'audit) : memes images, memes decisions. Les seuils sont
# des fractions de l'image.
ANALYSIS_W, ANALYSIS_H = 540, 960
FACE_SURE = 0.55       # score YuNet : au-dela, un visage de taille notable est un visage (verifie sur des recadrages :
                       # en dessous, ce sont des mains, des tableaux de bord, des arbres, des retroviseurs)
FACE_MIN_W = 0.03      # largeur mini d'un visage (~16 px a 540 de large, ~32 px sur 1080) : plus petit, personne n'est identifiable
PERSON_MIN_H = 0.05    # une personne de moins de 5 % de la hauteur est « au loin »
PERSON_SCORE = 0.45
PERSON_IOU = 0.5       # deux boites aussi recouvertes = la meme personne


def face_hits(faces, width):
    """faces : [(x, y, w, h, score)] -> sous-liste des visages qui font REFUSER l'image."""
    return [(x, y, w, h, s) for x, y, w, h, s in faces if s >= FACE_SURE and w >= FACE_MIN_W * width]


def iou(a, b):
    ix0, iy0, ix1, iy1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def distinct_persons(persons, height):
    """persons : [(x0, y0, x1, y1, score)] -> personnes distinctes (fusion des boites recouvertes) assez grandes."""
    kept = []
    for p in sorted(persons, key=lambda q: -q[4]):
        if p[4] < PERSON_SCORE or (p[3] - p[1]) < PERSON_MIN_H * height:
            continue
        if all(iou(p, k) < PERSON_IOU for k in kept):
            kept.append(p)
    return kept


def frame_reasons(width, height, faces, persons):
    """Raisons de refuser une image (liste vide = image acceptable)."""
    reasons = []
    fh = face_hits(faces, width)
    if fh:
        reasons.append("visage(s) visible(s): " + ", ".join(f"w{int(w)}@{s:.2f}" for _, _, w, _, s in fh))
    n = len(distinct_persons(persons, height))
    if n >= 2:
        reasons.append(f"{n} personnes")
    return reasons


def clean_intervals(samples, step, margin=0.4, min_len=2.0):
    """samples : [(t, refuse_bool)] triees par t, une image tous les `step` s.
    Retourne les intervalles [debut, fin] sans aucun refus, marge `margin` s de chaque cote d'un refus."""
    bad = [t for t, refuse in samples if refuse]
    out, run0, last = [], None, None
    for t, _ in samples:
        t0, t1 = max(0.0, t - step / 2), t + step / 2
        blocked = any(b - margin - step / 2 < t1 and b + margin + step / 2 > t0 for b in bad)
        if blocked:
            if run0 is not None and last - run0 >= min_len:
                out.append([round(run0, 2), round(last, 2)])
            run0 = None
        else:
            if run0 is None:
                run0 = t0
            last = t1
    if run0 is not None and last - run0 >= min_len:
        out.append([round(run0, 2), round(last, 2)])
    return out


def subtract_blocks(a, b, blocks, margin=0.3):
    """[a, b] prive des plages refusees `blocks` = [[debut, fin, raison], ...] (marge `margin` s). -> liste d'intervalles."""
    parts = [[a, b]]
    for x0, x1, *_ in blocks:
        nxt = []
        for p0, p1 in parts:
            if x1 + margin <= p0 or x0 - margin >= p1:
                nxt.append([p0, p1])
                continue
            if x0 - margin - p0 > 0:
                nxt.append([p0, x0 - margin])
            if p1 - (x1 + margin) > 0:
                nxt.append([x1 + margin, p1])
        parts = nxt
    return parts


def fetch_model():
    FACE_MODEL.parent.mkdir(exist_ok=True)
    if not FACE_MODEL.exists():
        urllib.request.urlretrieve(FACE_URL, FACE_MODEL)
    return FACE_MODEL


class Detectors:
    """Charge YuNet (visages) et RT-DETR (personnes) a la demande ; analyse une image BGR (numpy)."""

    def __init__(self, persons=True):
        import cv2
        self.cv2 = cv2
        if not FACE_MODEL.exists():
            sys.exit(f"modele de visages absent : {FACE_MODEL}\n  lancez : python mm_privacy.py --fetch-model")
        self.face = cv2.FaceDetectorYN.create(str(FACE_MODEL), "", (320, 320), 0.3, 0.3, 5000)
        self.det = None
        if persons:
            import torch
            from transformers import RTDetrForObjectDetection, RTDetrImageProcessor
            self.torch = torch
            self.dev = "cuda" if torch.cuda.is_available() else "cpu"
            self.proc = RTDetrImageProcessor.from_pretrained(PERSON_MODEL)
            self.det = RTDetrForObjectDetection.from_pretrained(PERSON_MODEL).to(self.dev).eval()
            self.labels = self.det.config.id2label

    def faces(self, bgr):
        h, w = bgr.shape[:2]
        self.face.setInputSize((w, h))
        _, f = self.face.detect(bgr)
        return [] if f is None else [(float(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[14])) for r in f]

    def persons(self, bgr):
        if self.det is None:
            return []
        from PIL import Image
        h, w = bgr.shape[:2]
        img = Image.fromarray(self.cv2.cvtColor(bgr, self.cv2.COLOR_BGR2RGB))
        inp = self.proc(images=img, return_tensors="pt").to(self.dev)
        with self.torch.no_grad():
            out = self.det(**inp)
        res = self.proc.post_process_object_detection(out, target_sizes=[(h, w)], threshold=0.25)[0]
        return [tuple(float(v) for v in b.tolist()) + (float(s),)
                for s, lab, b in zip(res["scores"], res["labels"], res["boxes"])
                if self.labels[int(lab)] == "person"]

    def analyse(self, bgr):
        """-> (faces, persons, raisons de refus). L'image est ramenee a la resolution d'analyse fixe."""
        h, w = bgr.shape[:2]
        if (w, h) != (ANALYSIS_W, ANALYSIS_H):
            bgr = self.cv2.resize(bgr, (ANALYSIS_W, ANALYSIS_H), interpolation=self.cv2.INTER_AREA)
            h, w = ANALYSIS_H, ANALYSIS_W
        faces = self.faces(bgr)
        # inutile de lancer le detecteur de personnes si un visage suffit deja a refuser l'image
        persons = [] if face_hits(faces, w) else self.persons(bgr)
        return faces, persons, frame_reasons(w, h, faces, persons)


if __name__ == "__main__":
    if "--fetch-model" in sys.argv:
        print("modele de visages :", fetch_model())
    else:
        print(__doc__)
