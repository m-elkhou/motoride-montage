# -*- coding: utf-8 -*-
"""Regle de scene : JAMAIS de plan pris depuis une voiture (regle stricte du proprietaire, 10/11/2026).

Une chaine de moto qui montre l'interieur d'une voiture (volant, tableau de bord, pare-brise) avec un titre
« deux roues » est un contresens. CLIP (zero-shot, deja utilise pour classer les clips) compare chaque image a des
descriptions d'habitacle de voiture et de scenes de moto ; au-dela de `CAR_THRESHOLD` l'image est refusee.

Verifie sur des images relues a la main : 10 plans de voiture sur 10 trouves, 2 faux positifs sur 37 images de moto
(on prefere perdre un plan de moto que garder un plan de voiture). La relecture des planches reste obligatoire.
"""
CAR_THRESHOLD = 0.30

CAR_PROMPTS = [
    "a photo taken from inside a car, with the steering wheel and the dashboard visible",
    "the interior of a car: dashboard, air vents and windscreen",
    "a view of the road through a car windscreen with the car dashboard in the foreground",
    "a driver's view from a car seat with a steering wheel",
]
OTHER_PROMPTS = [
    "a first-person view from a motorcycle with the handlebars, fuel tank and mirrors in front",
    "a motorcycle dashboard with a small digital display, seen from the rider's seat",
    "a motorcycle windscreen and handlebars on a road",
    "a motorcycle seen from outside, parked or riding on a road",
    "a landscape with trees, mountains and sky",
    "a road with white lines and no vehicle part visible in the foreground",
    "a closeup of a motorcycle front wheel and fairing",
]


class CarFilter:
    """Probabilite qu'une image BGR (numpy) soit prise depuis une voiture. Charge CLIP a la demande."""

    def __init__(self):
        import cv2
        import open_clip
        import torch
        self.cv2, self.torch = cv2, torch
        self.dev = "cuda" if torch.cuda.is_available() else "cpu"
        self.model, _, self.pre = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="laion2b_s34b_b79k", device=self.dev)
        tok = open_clip.get_tokenizer("ViT-B-32")
        with torch.no_grad():
            t = self.model.encode_text(tok(CAR_PROMPTS + OTHER_PROMPTS).to(self.dev))
            self.text = t / t.norm(dim=-1, keepdim=True)

    def prob(self, bgr):
        from PIL import Image
        img = Image.fromarray(self.cv2.cvtColor(bgr, self.cv2.COLOR_BGR2RGB))
        with self.torch.no_grad():
            v = self.model.encode_image(self.pre(img).unsqueeze(0).to(self.dev))
            v = v / v.norm(dim=-1, keepdim=True)
            p = (100 * v @ self.text.T).softmax(-1)[0].cpu().numpy()
        return float(p[:len(CAR_PROMPTS)].sum())

    def is_car(self, bgr):
        return self.prob(bgr) >= CAR_THRESHOLD


# ---- Plaques : une detection du detecteur de plaques est-elle vraiment la plaque d'un vehicule ?
# Le detecteur (mm_plates) prend aussi pour des plaques le compteur, l'ecran du GPS, les autocollants du reservoir, un
# logo, un bout de ciel. Tout flouter abime chaque plan « vue du guidon ». CLIP compare donc le voisinage de chaque
# detection a trois familles de descriptions : plaque sur un vehicule, poste de pilotage, autre chose.
#
# Une piste est FLOUTEE sauf certitude du contraire. Dans l'ordre :
#   1. boite geante (HUGE de la largeur ou plus : un pan de ciel, tout un tableau de bord) : floutee seulement si CLIP y
#      voit un vehicule sans hesiter (HUGE_BLUR) : une plaque de cette taille remplirait l'image ;
#   2. boite minuscule (moins de SMALL de la largeur, soit 38 px : illisible de toute facon) : toujours floutee, le
#      flou ne se voit pas et couvre les vehicules lointains ou files que CLIP ne reconnait pas ;
#   3. petite boite (moins de MEDIUM, soit 130 px) qui passe dans la moitie haute de l'image (la route, l'horizon) :
#      toujours floutee ;
#   4. sinon : floutee des que P(plaque d'un vehicule) atteint PLATE_BLUR sur UN SEUL de ses echantillons.
# Modele : ViT-L/14 (le ViT-B/32 du filtre « voiture » confond un compteur vu a travers la bulle avec une plaque : 13
# grandes confusions sur 54 elements du poste de pilotage, contre 3). Mesure sur 158 pistes d'un montage et 100
# detections d'images isolees relues a la main (14/11/2026), boites de 38 px ou plus : les vraies plaques ont
# P >= 0,95 (une seule a 0,84, de travers) ; les elements de la moto (retroviseur, commodo, logo, compteur) P <= 0,45.
JUDGE_MODEL, JUDGE_WEIGHTS = "ViT-L-14", "laion2b_s32b_b82k"
PLATE_BLUR = 0.50
ROAD_ZONE = 0.50        # centre de la boite au-dessus de la mi-hauteur : la route, l'horizon
SMALL = 0.035           # largeur (fraction de l'image) sous laquelle on floute sans demander l'avis de CLIP
MEDIUM = 0.12           # largeur sous laquelle une boite de la zone de la route est floutee d'office
HUGE = 0.30             # largeur (fraction de l'image) au-dela de laquelle il faut une certitude pour flouter
HUGE_BLUR = 0.95

PLATE_PROMPTS = [
    "the rear of a car with its licence plate",
    "a licence plate on a vehicle",
    "the back of a van or a truck on the road",
    "a motorcycle seen from behind with its number plate",
    "the front of a car with its licence plate",
    "cars in traffic on a road",
    "a vehicle on the road at night with its lights on",
]
COCKPIT_PROMPTS = [
    "a motorcycle dashboard display showing the speed",
    "a phone screen showing a GPS map, mounted on handlebars",
    "a warning sticker on a motorcycle fuel tank",
    "motorcycle handlebars, switches and mirrors seen by the rider",
    "a motorcycle windscreen and instrument panel",
    "a motorcycle fuel tank and filler cap seen from the seat",
]
OTHER_THINGS = [
    "the sky with clouds",
    "an empty road surface with painted lines",
    "a motorcycle helmet",
    "a logo or brand name on motorcycle bodywork",
    "a guard rail, a wall or a fence beside a road",
    "trees and vegetation",
    "a blurry dark image",
    "a rider's glove, arm or leg",
    "a road sign with text",
]


def context_box(box, w, h, factor=3.0, min_side=160):
    """Carre de voisinage autour d'une boite (x0, y0, x1, y1), borne a l'image w x h. -> (x0, y0, x1, y1) entiers."""
    side = max(min_side, factor * max(box[2] - box[0], box[3] - box[1]))
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return (int(max(0, cx - side / 2)), int(max(0, cy - side / 2)), int(min(w, cx + side / 2)), int(min(h, cy + side / 2)))


def must_blur(samples):
    """samples : [(P(plaque d'un vehicule), centre vertical relatif, largeur relative)] d'une piste.
    Vrai sauf certitude que ce n'est pas une plaque (voir les quatre cas ci-dessus). Aucun echantillon : on floute."""
    if not samples:
        return True
    giant = [x for x in samples if x[2] >= HUGE]
    rest = [x for x in samples if x[2] < HUGE]
    if any(x[0] >= HUGE_BLUR for x in giant):
        return True
    if not rest:                                   # cas 1 : piste ENTIEREMENT geante, sans certitude
        return False
    # Piste melee (une boite geante s'y est glissee, ou la plaque grossit au-dela du seuil) : les echantillons geants ne
    # decident pas pour les autres, sinon une seule boite geante rendait visible une plaque detectee (relecture du 16/11).
    p = max(x[0] for x in rest)
    width = max(x[2] for x in rest)
    if width < SMALL:
        return True
    if width < MEDIUM and any(cy < ROAD_ZONE for _, cy, _ in rest):
        return True
    return p >= PLATE_BLUR


def doubt(samples):
    """Piste LAISSEE VISIBLE alors que CLIP penche pour une plaque (boite geante sous le seuil de certitude : un tableau
    de bord, ou une plaque tres proche). A regarder sur la planche des pistes visibles avant toute approbation, ou plan a
    remplacer : le rapport du montage les compte."""
    return bool(samples) and not must_blur(samples) and max(x[0] for x in samples) >= PLATE_BLUR


class PlateJudge:
    """P(plaque d'un vehicule) pour un recadrage BGR autour d'une detection (CLIP, trois familles de descriptions)."""

    def __init__(self):
        import cv2
        import open_clip
        import torch
        self.cv2, self.torch = cv2, torch
        self.dev = "cuda" if torch.cuda.is_available() else "cpu"
        self.model, _, self.pre = open_clip.create_model_and_transforms(JUDGE_MODEL, pretrained=JUDGE_WEIGHTS, device=self.dev)
        tok = open_clip.get_tokenizer(JUDGE_MODEL)
        with torch.no_grad():
            t = self.model.encode_text(tok(PLATE_PROMPTS + COCKPIT_PROMPTS + OTHER_THINGS).to(self.dev))
            self.text = t / t.norm(dim=-1, keepdim=True)

    def prob(self, bgr):
        from PIL import Image
        img = Image.fromarray(self.cv2.cvtColor(bgr, self.cv2.COLOR_BGR2RGB))
        with self.torch.no_grad():
            v = self.model.encode_image(self.pre(img).unsqueeze(0).to(self.dev))
            v = v / v.norm(dim=-1, keepdim=True)
            p = (100 * v @ self.text.T).softmax(-1)[0].cpu().numpy()
        return float(p[:len(PLATE_PROMPTS)].sum())
