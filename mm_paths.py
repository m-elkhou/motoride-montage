"""Chemins et outils externes, centralises (plus aucun chemin absolu dans les scripts).

Ordre de priorite pour chaque reglage :
  1. variable d'environnement  (MM_FFMPEG, MM_FFPROBE, MM_RENDER_PYTHON, MM_PLATES_PYTHON, MM_S2S_ROOT,
     MM_VOICE_REF, MM_INSTA360_DIR, MM_FONT)
  2. fichier local ``local_paths.json`` a la racine du depot (ignore par git), memes cles en minuscules
     sans le prefixe : ffmpeg, ffprobe, render_python, plates_python, s2s_root, voice_ref, insta360_dir, font
  3. valeur par defaut deduite de l'emplacement du depot ou du PATH

Voix par langue : ``voice_ref(langue)`` lit MM_VOICE_REF_FR / voice_ref_fr (de meme en, ar) avant la reference
commune ; hors de l'anglais, la reference par defaut (un enregistrement en anglais) n'est pas reprise. La langue par
defaut (MM_VOICE_LANG / voice_lang) est lue par mm_lang.py.

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
# interpreteur du detecteur de plaques (onnxruntime + open-image-models : environnement a part, voir mm_plates.py)
PLATES_PYTHON = _get("plates_python", "MM_PLATES_PYTHON", sys.executable)
# projet voisin qui fournit OAuth, client YouTube et store de doublons
S2S_ROOT = Path(_get("s2s_root", "MM_S2S_ROOT", ROOT.parent / "social2shorts"))
VOICE_REF = Path(_get("voice_ref", "MM_VOICE_REF", S2S_ROOT / "work" / "voiceover" / "ref_en_clean.wav"))


def voice_ref(lang):
    """Enregistrement de reference de la voix clonee pour une langue (fr, en, ar) : variable MM_VOICE_REF_<LANGUE>,
    sinon cle ``voice_ref_<langue>`` de local_paths.json, sinon la reference commune si elle a ete CHOISIE
    (MM_VOICE_REF / ``voice_ref``). Rien de regle : la reference par defaut en anglais, None pour une autre langue
    (l'enregistrement par defaut est en anglais : il ne sert jamais, en silence, a cloner une voix francaise)."""
    chosen = (_get(f"voice_ref_{lang.lower()}", f"MM_VOICE_REF_{lang.upper()}", None)
              or _get("voice_ref", "MM_VOICE_REF", None))
    if chosen:
        return Path(chosen)
    return VOICE_REF if lang.lower() == "en" else None


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
