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
