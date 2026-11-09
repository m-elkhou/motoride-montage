"""Chemins et outils externes, centralises (plus aucun chemin absolu dans les scripts).

Ordre de priorite pour chaque reglage :
  1. variable d'environnement  (MM_FFMPEG, MM_FFPROBE, MM_RENDER_PYTHON, MM_S2S_ROOT, MM_VOICE_REF,
     MM_INSTA360_DIR, MM_FONT)
  2. fichier local ``local_paths.json`` a la racine du depot (ignore par git), memes cles en minuscules
     sans le prefixe : ffmpeg, ffprobe, render_python, s2s_root, voice_ref, insta360_dir, font
  3. valeur par defaut deduite de l'emplacement du depot ou du PATH

Tous les scripts de ``scan/`` utilisent des chemins relatifs a la racine : appelez ``use_root()`` au debut.
"""
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCAN = ROOT / "scan"
OUT = ROOT / "out"
VO = ROOT / "vo"
META = ROOT / "meta"
PUBLIC = ROOT / "public"


def _local():
    f = ROOT / "local_paths.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except ValueError:
        return {}


_L = _local()


def _get(key, env, default):
    return os.environ.get(env) or _L.get(key) or default


def _default_font():
    if sys.platform.startswith("win"):
        return "C:/Windows/Fonts/arialbd.ttf"
    if sys.platform == "darwin":
        return "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    return "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


FFMPEG = _get("ffmpeg", "MM_FFMPEG", shutil.which("ffmpeg") or "ffmpeg")
FFPROBE = _get("ffprobe", "MM_FFPROBE", shutil.which("ffprobe") or "ffprobe")
# interpreteur qui a librosa / torch / open_clip (par defaut : celui qui lance le script)
RENDER_PYTHON = _get("render_python", "MM_RENDER_PYTHON", sys.executable)
# projet voisin qui fournit OAuth, client YouTube et store de doublons
S2S_ROOT = Path(_get("s2s_root", "MM_S2S_ROOT", ROOT.parent / "social2shorts"))
VOICE_REF = Path(_get("voice_ref", "MM_VOICE_REF", S2S_ROOT / "work" / "voiceover" / "ref_en_clean.wav"))
INSTA360_DIR = Path(_get("insta360_dir", "MM_INSTA360_DIR", Path.home() / "Desktop" / "insta360"))
FONT_FILE = _get("font", "MM_FONT", _default_font())

CLIP_DIRS = {
    "inbox": S2S_ROOT / "inbox",
    "camera_roll": S2S_ROOT / "camera_roll",
    "insta360": INSTA360_DIR,
}


def ffmpeg_font():
    """Chemin de police echappe pour le filtre drawtext d'ffmpeg (le ':' d'un lecteur Windows)."""
    return str(FONT_FILE).replace("\\", "/").replace(":", "\\:")


def use_root():
    """Se place a la racine du depot : les scripts utilisent des chemins relatifs (scan/..., out/...)."""
    os.chdir(ROOT)
