# -*- coding: utf-8 -*-
"""Couche de VALIDATION de la voix : on REECOUTE chaque voix generee avant de la garder (et le mixage final a l'audit).

Pourquoi : le modele de voix clonee deborde parfois apres la phrase (il la repete, ajoute un mot) puis son propre
analyseur coupe la generation au milieu d'un mot. Une voix ne passe que si :
  - le modele n'a pas force sa fin (`EOSWatch` capte l'avertissement « forcing EOS » de Chatterbox) ;
  - le signal ne finit pas en plein son (`abrupt_end`) ;
  - Whisper entend EXACTEMENT les mots voulus, ni plus ni moins (`word_problems`) ;
  - rien n'est dit apres le dernier mot reconnu (`trailing_speech` : une repetition que Whisper aurait ignoree).

La transcription tourne dans le Python de social2shorts (faster-whisper y est installe) : `ASR` lance un petit serveur
(`python mm_voicecheck.py --serve`) qui charge le modele une fois, puis repond fichier par fichier.
  MM_ASR_PYTHON : interpreteur a utiliser ; MM_ASR_MODEL : modele (defaut large-v3, sur CPU en int8).
"""
import json
import logging
import os
import re
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path

ABRUPT_PEAK = 0.12        # fin coupee : les 5 dernieres ms depassent 12 % du pic
TRAIL_MAX = 0.06          # s de parole REPRISE (apres un silence) toleree apres le dernier mot : au-dela, c'est un mot
HOMOPHONES = {"rode": "road", "rowed": "road", "ok": "okay"}
EOS_LOGGER = "chatterbox.models.t3.inference.alignment_stream_analyzer"


def normalize_words(text):
    """Mots comparables : minuscules, sans ponctuation, « P.O.V. » = « pov », homophones ramenes a une forme."""
    t = str(text).lower().replace("p.o.v.", " pov ").replace("p.o.v", " pov ").replace("’", "'")
    words = re.findall(r"[a-z0-9']+", t)
    merged = []                                   # sigle epele lettre par lettre (« P O V ») = un seul mot (« pov »)
    for w in words:
        if len(w) == 1 and w.isalpha() and merged and merged[-1][1]:
            merged[-1] = (merged[-1][0] + w, True)
        else:
            merged.append((w, len(w) == 1 and w.isalpha()))
    return [HOMOPHONES.get(w, w) for w, _ in merged]


def word_problems(expected, heard):
    """Ecarts entre la phrase voulue et ce que Whisper a entendu (liste vide = identique)."""
    a, b = normalize_words(expected), normalize_words(heard)
    out = []
    for op, i1, i2, j1, j2 in SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        if op == "insert":
            extra = " ".join(b[j1:j2])
            kind = "repetition" if extra in " ".join(a) else "mot(s) en trop"
            out.append(f"{kind} : « {extra} »")
        elif op == "delete":
            out.append(f"mot(s) manquant(s) : « {' '.join(a[i1:i2])} »")
        else:
            out.append(f"« {' '.join(a[i1:i2])} » entendu « {' '.join(b[j1:j2])} »")
    return out


def _mono(w):
    import numpy as np
    w = np.asarray(w, dtype=np.float32)
    return w.mean(axis=1) if w.ndim > 1 else w


def abrupt_end(w, sr, window=0.005):
    """Vrai si le signal finit en plein son : les 5 dernieres ms (environ une periode de voix) depassent ABRUPT_PEAK du
    pic. Une fin naturelle, ou un fondu de 50 ms, finit pres de zero ; une generation coupee finit au milieu d'une onde."""
    import numpy as np
    w = _mono(w)
    peak = float(np.max(np.abs(w))) or 1.0
    return float(np.max(np.abs(w[-max(1, int(window * sr)):]))) / peak > ABRUPT_PEAK


def trailing_speech(w, sr, last_word_end, frame=0.02, quiet=0.05, burst=0.20, gap=0.12, min_burst=0.06):
    """Secondes de PAROLE REPRISE apres la phrase : apres le dernier mot reconnu, un silence (>= `gap` s sous `quiet`
    de l'energie maximale) puis une nouvelle bouffee (>= `min_burst` s au-dessus de `burst`). La resonance du dernier
    mot, qui decroit sans silence, n'est pas comptee (Whisper date souvent la fin du dernier mot trop tot)."""
    import numpy as np
    w = _mono(w)
    n = max(1, int(frame * sr))
    k = len(w) // n
    if k == 0:
        return 0.0
    rms = np.sqrt((w[:k * n].reshape(k, n) ** 2).mean(axis=1))
    top = float(rms.max()) or 1.0
    i = min(k, int(float(last_word_end) / frame))
    run = 0
    while i < k and run < round(gap / frame):          # 1) attendre un vrai silence apres le dernier mot
        run = run + 1 if rms[i] < quiet * top else 0
        i += 1
    if run < round(gap / frame):
        return 0.0                                     # pas de silence : le mot decroit jusqu'a la fin, rien d'autre
    loud = rms[i:] > burst * top                        # 2) une nouvelle bouffee de parole apres ce silence ?
    run = best = 0
    for v in loud:
        run = run + 1 if v else 0
        best = max(best, run)
    return best * frame if best * frame >= min_burst else 0.0


def is_repetition(msg):
    """Fin forcee POUR REPETITION (a refuser). Une fin forcee pour « queue » (long_tail : le modele s'attarde sur la
    derniere syllabe) est la facon normale de finir pour ce modele (163 essais sur 184 le 10/11) : elle ne dit rien seule,
    la fin coupee, Whisper et la parole reprise jugent ces essais-la."""
    return "alignment_repetition=tensor(True)" in msg or "token_repetition=True" in msg


class EOSWatch(logging.Handler):
    """Capte les avertissements de l'analyseur de Chatterbox : une fin forcee = le modele a deborde ou repete."""

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.events = []

    def emit(self, record):
        msg = record.getMessage()
        if "forcing EOS" in msg:
            self.events.append(msg[:160])

    def __enter__(self):
        self.events = []
        logging.getLogger(EOS_LOGGER).addHandler(self)
        return self

    def __exit__(self, *exc):
        logging.getLogger(EOS_LOGGER).removeHandler(self)
        return False


def default_python():
    env = os.environ.get("MM_ASR_PYTHON")
    if env:
        return env
    import mm_paths
    venv = Path(mm_paths.S2S_ROOT) / ".venv"
    return str(venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))


class ASR:
    """Transcription mot a mot (faster-whisper) dans un processus a part ; a utiliser avec `with ASR() as asr:`."""

    def __init__(self, python=None, model=None):
        self.python = python or default_python()
        self.model = model or os.environ.get("MM_ASR_MODEL", "large-v3")
        self.proc = None

    def __enter__(self):
        """Demarre le serveur ; si le modele demande ne se charge pas (memoire), essaie `medium`, plus leger."""
        errors = []
        for model in dict.fromkeys([self.model, "medium"]):
            self.proc = subprocess.Popen([self.python, "-X", "utf8", str(Path(__file__).resolve()), "--serve", model],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                         text=True, encoding="utf-8", bufsize=1)
            ready = self.proc.stdout.readline().strip()
            if ready == "READY":
                self.model = model
                return self
            errors.append(f"{model}: {ready[:160]}")
            self.close()
        raise RuntimeError(f"ASR indisponible ({self.python}) : {' | '.join(errors)}")

    def words(self, path, clip_end=None):
        """[(debut, fin, mot, probabilite)] du fichier audio/video `path` (jusqu'a `clip_end` s si donne)."""
        self.proc.stdin.write(json.dumps({"path": str(path), "end": clip_end}) + "\n")
        self.proc.stdin.flush()
        reply = json.loads(self.proc.stdout.readline())
        if "error" in reply:
            raise RuntimeError(reply["error"])
        return [tuple(x) for x in reply["words"]]

    def text(self, path, clip_end=None):
        return " ".join(w for _, _, w, _ in self.words(path, clip_end))

    def close(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=20)
            except Exception:
                self.proc.kill()
        self.proc = None

    def __exit__(self, *exc):
        self.close()
        return False


def check_take(w, sr, wav_path, expected, asr, eos_events=(), abrupt=None):
    """Tous les controles d'un essai de voix -> (liste des problemes, texte entendu). Liste vide = voix acceptee.
    `w` est le signal BRUT du modele (avant coupe et fondu) : c'est lui qui dit si la fin a ete coupee (ou `abrupt`,
    deja mesure a la generation) ; `wav_path` est la voix telle qu'elle serait gardee : c'est elle que Whisper reecoute."""
    reps = [e for e in eos_events if is_repetition(e)]
    problems = [f"le modele s'est arrete sur une repetition ({len(reps)}x)"] if reps else []
    if abrupt is None:
        abrupt = abrupt_end(w, sr)
    if abrupt:
        problems.append("fin coupee en plein son")
    words = asr.words(wav_path)
    heard = " ".join(x[2] for x in words)
    problems += word_problems(expected, heard)
    if words:
        import soundfile as sf
        kept, ksr = sf.read(str(wav_path), dtype="float32")
        trail = trailing_speech(kept, ksr, words[-1][1])
        if trail >= TRAIL_MAX:
            problems.append(f"parole reprise apres un silence en fin de phrase ({trail:.2f} s : repetition ou bredouillement)")
    else:
        problems.append("rien d'entendu")
    return problems, heard


def _serve(model_name):
    """Serveur : une ligne JSON {"path", "end"} en entree -> une ligne JSON {"words": [...]} en sortie."""
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
    except Exception as e:  # le modele ne se charge pas : on le dit au client et on s'arrete
        print(f"ERREUR {type(e).__name__}: {e}"[:300], flush=True)
        return 1
    print("READY", flush=True)
    for line in sys.stdin:
        try:
            req = json.loads(line)
            clip = f"0,{req['end']}" if req.get("end") else "0"
            segs, _ = model.transcribe(req["path"], language="en", word_timestamps=True, vad_filter=False,
                                       beam_size=5, condition_on_previous_text=False, clip_timestamps=clip)
            words = [[round(w.start, 3), round(w.end, 3), w.word.strip(), round(w.probability, 3)]
                     for s in segs for w in (s.words or [])]
            print(json.dumps({"words": words}), flush=True)
        except Exception as e:  # un fichier illisible : erreur pour CE fichier, le serveur continue
            print(json.dumps({"error": f"{type(e).__name__}: {e}"[:300]}), flush=True)
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--serve":
        sys.exit(_serve(sys.argv[2] if len(sys.argv) > 2 else "large-v3"))
    print(__doc__)
