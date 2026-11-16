# -*- coding: utf-8 -*-
"""Couche de VALIDATION de la voix : on REECOUTE chaque voix generee avant de la garder (et le mixage final a l'audit).

Pourquoi : le modele de voix clonee deborde parfois apres la phrase (il la repete, ajoute un mot) puis son propre
analyseur coupe la generation au milieu d'un mot. Une voix ne passe que si :
  - le modele n'a pas force sa fin (`EOSWatch` capte l'avertissement « forcing EOS » de Chatterbox) ;
  - le signal ne finit pas en plein son (`abrupt_end`) ;
  - Whisper entend EXACTEMENT les mots voulus, ni plus ni moins (`word_problems`) ;
  - rien n'est dit apres le dernier mot reconnu (`trailing_speech` : une repetition que Whisper aurait ignoree).

La langue (en, fr, ar ; anglais si rien n'est dit) est donnee a Whisper et a la comparaison des mots : ce qui compte
pour « les memes mots » dans chaque langue est dans mm_lang.py.

La transcription tourne dans un processus a part : `ASR` lance un petit serveur (`python mm_voicecheck.py --serve`)
qui charge le modele une fois, puis repond fichier par fichier.
  MM_ASR_PYTHON : interpreteur du serveur (defaut : celui qui tourne s'il a faster-whisper, sinon le venv de
                  social2shorts) ;
  MM_ASR_MODEL  : modele (defaut large-v3) ;
  MM_ASR_DEVICE : cpu | cuda | auto (defaut auto). La carte graphique (float16) n'est tentee que si torch/lib, dans
                  l'interpreteur du serveur, contient cublas64_12.dll ET une bibliotheque cuDNN 9 (cudnn*64_9.dll) ;
                  sinon CPU en int8. Si le serveur meurt quand meme en cours de route, le client le relance UNE fois
                  sur le CPU et repete sa demande. Le processeur utilise est dans `ASR.device`.
"""
import json
import logging
import os
import subprocess
import sys
from difflib import SequenceMatcher
from importlib.util import find_spec
from pathlib import Path

import mm_lang

ABRUPT_PEAK = 0.12        # fin coupee : les 5 dernieres ms depassent 12 % du pic
TRAIL_MAX = 0.06          # s de parole REPRISE (apres un silence) toleree apres le dernier mot : au-dela, c'est un mot
HOMOPHONES = mm_lang.HOMOPHONES
EOS_LOGGER = "chatterbox.models.t3.inference.alignment_stream_analyzer"
ASR_DEVICES = ("cpu", "cuda", "auto")
CUDA_DLL = "cublas64_12.dll"      # sans elle (et ses voisines de torch/lib), CTranslate2 fait tomber le processus
CUDNN_DLL = "cudnn*64_9.dll"      # cuDNN 9 : charge seulement a la 1re transcription, apres « READY »


def normalize_words(text):
    """Mots comparables en anglais : minuscules, sans ponctuation, « P.O.V. » = « pov », homophones ramenes a une forme
    (la regle vit dans mm_lang.words ; ce nom est garde pour les anciens appels)."""
    return mm_lang.words(text, "en")


def word_problems(expected, heard, lang="en"):
    """Ecarts entre la phrase voulue et ce que Whisper a entendu (liste vide = identique), dans la langue `lang`.
    L'alignement se fait sur la cle de comparaison de chaque mot (le son, en francais : « bas » s'aligne sur « bat ») ;
    les messages citent les mots eux-memes. Un mot en trop ou en moins est toujours un ecart. Un bloc remplace ne
    contient aucune cle commune aux deux cotes (l'alignement l'aurait trouvee) : il est cite en entier."""
    a, b = mm_lang.words(expected, lang), mm_lang.words(heard, lang)
    ka, kb = [mm_lang.key(w, lang) for w in a], [mm_lang.key(w, lang) for w in b]
    out = []
    for op, i1, i2, j1, j2 in SequenceMatcher(a=ka, b=kb, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        if op == "insert":
            said = f" {' '.join(kb[j1:j2])} " in f" {' '.join(ka)} "       # ces mots ENTIERS sont deja dans la phrase
            out.append(f"{'repetition' if said else 'mot(s) en trop'} : « {' '.join(b[j1:j2])} »")
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


def _installed(module):
    """Vrai si `module` est installe dans l'interpreteur courant (il n'est PAS importe)."""
    try:
        return find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def default_python():
    """Interpreteur du serveur : MM_ASR_PYTHON ; sinon celui qui tourne s'il a faster-whisper ; sinon le venv de
    social2shorts."""
    env = os.environ.get("MM_ASR_PYTHON")
    if env:
        return env
    if _installed("faster_whisper"):
        return sys.executable
    import mm_paths
    venv = Path(mm_paths.S2S_ROOT) / ".venv"
    return str(venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))


def cuda_dll_dir():
    """Dossier `torch/lib` de l'interpreteur courant s'il contient cublas64_12.dll ET une bibliotheque cuDNN 9
    (cudnn*64_9.dll), sinon None. torch n'est PAS importe : on ne cherche que son emplacement."""
    try:
        spec = find_spec("torch")
    except (ImportError, ValueError):
        return None
    if spec is None:
        return None
    roots = list(getattr(spec, "submodule_search_locations", None) or [])
    if not roots and getattr(spec, "origin", None):
        roots = [str(Path(spec.origin).parent)]
    for root in roots:
        lib = Path(root) / "lib"
        if (lib / CUDA_DLL).is_file() and any(lib.glob(CUDNN_DLL)):
            return lib
    return None


def asr_device():
    """(processeur, precision, dossier des DLL) du serveur, d'apres MM_ASR_DEVICE = cpu | cuda | auto (defaut auto).
    La carte graphique n'est retenue QUE si torch/lib contient cublas64_12.dll et cuDNN 9 : sans ces bibliotheques
    CTranslate2 fait tomber le processus (aucune exception a rattraper), au chargement pour cuBLAS, a la premiere
    transcription pour cuDNN. Sinon CPU en int8, meme si « cuda » est demande."""
    want = (os.environ.get("MM_ASR_DEVICE") or "auto").strip().lower()
    if want not in ASR_DEVICES:
        raise ValueError(f"MM_ASR_DEVICE inconnu : {want!r} (valeurs permises : {', '.join(ASR_DEVICES)})")
    lib = None if want == "cpu" else cuda_dll_dir()
    return ("cuda", "float16", lib) if lib else ("cpu", "int8", None)


def load_whisper(model_name):
    """Charge faster-whisper -> (modele, processeur utilise). Sur carte graphique, le dossier des DLL de torch est
    rendu visible AVANT l'import de faster_whisper ; si le chargement echoue quand meme, repli sur le CPU."""
    device, compute, lib = asr_device()
    if lib:
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(lib))
        os.environ["PATH"] = str(lib) + os.pathsep + os.environ.get("PATH", "")
    from faster_whisper import WhisperModel
    if device == "cuda":
        try:
            return WhisperModel(model_name, device=device, compute_type=compute), device
        except Exception:  # pilote, memoire video... : le CPU fait le meme travail, plus lentement
            pass
    return WhisperModel(model_name, device="cpu", compute_type="int8"), "cpu"


class ASR:
    """Transcription mot a mot (faster-whisper) dans un processus a part ; a utiliser avec `with ASR() as asr:`."""

    def __init__(self, python=None, model=None):
        self.python = python or default_python()
        self.model = model or os.environ.get("MM_ASR_MODEL", "large-v3")
        self.device = None        # « cpu » ou « cuda », annonce par le serveur quand il est pret
        self.proc = None
        self.restarted = False    # le serveur, mort en cours de route, a deja ete relance sur le CPU (une seule fois)

    def _start(self, model, device=None):
        """Lance le serveur avec `model` -> None s'il est pret, sinon la raison (sa ligne « ERREUR ... », ou le fait
        qu'il s'est arrete sans rien dire). `device` impose MM_ASR_DEVICE a ce processus (relance sur le CPU)."""
        env = {**os.environ, "MM_ASR_DEVICE": device} if device else None
        self.proc = subprocess.Popen([self.python, "-X", "utf8", str(Path(__file__).resolve()), "--serve", model],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     text=True, encoding="utf-8", bufsize=1, env=env)
        ready = self.proc.stdout.readline().strip()
        if ready.split()[:1] == ["READY"]:            # « READY » seul (ancien serveur) ou « READY cuda »
            self.model, self.device = model, (ready.split() + [None])[1]
            return None
        self.close()
        return ready[:160] or "le processus s'est arrete sans message (essayer MM_ASR_DEVICE=cpu)"

    def __enter__(self):
        """Demarre le serveur ; si le modele demande ne se charge pas (memoire), essaie `medium`, plus leger."""
        errors = []
        for model in dict.fromkeys([self.model, "medium"]):
            why = self._start(model)
            if why is None:
                return self
            errors.append(f"{model}: {why}")
        raise RuntimeError(f"ASR indisponible ({self.python}) : {' | '.join(errors)}")

    def _ask(self, request):
        """Envoie une ligne de requete -> la ligne de reponse ; vide si le serveur est mort (tuyau ferme, fin de
        fichier) ou n'a pas ete relance."""
        if self.proc is None:
            return ""
        try:
            self.proc.stdin.write(request + "\n")
            self.proc.stdin.flush()
            return self.proc.stdout.readline()
        except OSError:
            return ""

    def words(self, path, clip_end=None, lang=None):
        """[(debut, fin, mot, probabilite)] du fichier audio/video `path` (jusqu'a `clip_end` s si donne), transcrit
        dans la langue `lang` (anglais si elle n'est pas donnee). Un serveur mort apres « READY » (bibliotheque de la
        carte graphique absente a la premiere transcription...) est relance UNE fois, sur le CPU, et la demande
        repetee ; s'il meurt encore : RuntimeError."""
        request = json.dumps({"path": str(path), "end": clip_end, "lang": lang})
        line, detail = self._ask(request), "il avait deja ete relance sur le CPU"
        if not line.strip() and not self.restarted:
            self.restarted = True
            print(f"serveur Whisper arrete ({self.device or 'processeur inconnu'}) : relance sur le CPU",
                  file=sys.stderr, flush=True)
            self.close()
            why = self._start(self.model, device="cpu")
            line = "" if why else self._ask(request)
            detail = f"sa relance sur le CPU a echoue : {why}" if why else "relance sur le CPU, il s'est arrete encore"
        if not line.strip():
            self.close()
            raise RuntimeError(f"le serveur Whisper ({self.python}) s'est arrete ({detail}) : regler "
                               "MM_ASR_DEVICE=cpu, ou choisir un autre interpreteur avec MM_ASR_PYTHON")
        reply = json.loads(line)
        if "error" in reply:
            raise RuntimeError(reply["error"])
        return [tuple(x) for x in reply["words"]]

    def text(self, path, clip_end=None, lang=None):
        return " ".join(w for _, _, w, _ in self.words(path, clip_end, lang))

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


def check_take(w, sr, wav_path, expected, asr, eos_events=(), abrupt=None, lang="en"):
    """Tous les controles d'un essai de voix -> (liste des problemes, texte entendu). Liste vide = voix acceptee.
    `w` est le signal BRUT du modele (avant coupe et fondu) : c'est lui qui dit si la fin a ete coupee (ou `abrupt`,
    deja mesure a la generation) ; `wav_path` est la voix telle qu'elle serait gardee : c'est elle que Whisper reecoute,
    dans la langue `lang`."""
    reps = [e for e in eos_events if is_repetition(e)]
    problems = [f"le modele s'est arrete sur une repetition ({len(reps)}x)"] if reps else []
    if abrupt is None:
        abrupt = abrupt_end(w, sr)
    if abrupt:
        problems.append("fin coupee en plein son")
    # anglais : l'appel d'avant, sans langue (le serveur transcrit alors en anglais ; un ASR ancien n'a pas `lang`)
    words = asr.words(wav_path) if lang == "en" else asr.words(wav_path, lang=lang)
    heard = " ".join(x[2] for x in words)
    problems += word_problems(expected, heard, lang)
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
    """Serveur : une ligne JSON {"path", "end", "lang"} en entree -> une ligne JSON {"words": [...]} en sortie.
    Sans "lang" (ancien client), la transcription se fait en anglais."""
    try:
        model, device = load_whisper(model_name)
    except Exception as e:  # le modele ne se charge pas : on le dit au client et on s'arrete
        print(f"ERREUR {type(e).__name__}: {e}"[:300], flush=True)
        return 1
    print(f"READY {device}", flush=True)
    for line in sys.stdin:
        try:
            req = json.loads(line)
            clip = f"0,{req['end']}" if req.get("end") else "0"
            segs, _ = model.transcribe(req["path"], language=req.get("lang") or "en", word_timestamps=True,
                                       vad_filter=False, beam_size=5, condition_on_previous_text=False,
                                       clip_timestamps=clip)
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
