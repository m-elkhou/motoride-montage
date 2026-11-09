"""Reglages editoriaux (dates exclues, calendrier, textes) hors du code.

Fichier optionnel ``scan/gen_config.json`` (ignore par git : il contient des choix personnels). Un modele
sans donnees personnelles est fourni : ``scan/gen_config.example.json``. Cles reconnues :

  exclude_dates     liste de prefixes de nom/date de clips a ne jamais utiliser (ex. "20230822")
  used_montages     montages deja publies dont les clips sont interdits (noms de scan/mont/<nom>.json)
  schedule_start    premier creneau de publication, ISO 8601 UTC (ex. "2026-11-12T17:00:00Z")
  slot_hours        heures UTC des deux creneaux quotidiens (defaut [17, 10])
  music, hooks, outros, titles, tagset, themes, descriptions   surcharges des textes/listes de gen_batch
"""
import json
from pathlib import Path

from mm_paths import SCAN

DEFAULTS = {
    "exclude_dates": [],
    "used_montages": [],
    "schedule_start": None,
    "slot_hours": [17, 10],
}


def load(path=None):
    """Retourne la configuration fusionnee (valeurs par defaut + scan/gen_config.json s'il existe)."""
    f = Path(path) if path else SCAN / "gen_config.json"
    cfg = dict(DEFAULTS)
    if f.exists():
        cfg.update(json.loads(f.read_text(encoding="utf-8")))
    return cfg
