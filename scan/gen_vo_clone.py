# -*- coding: utf-8 -*-
"""Voix COURTE de chaque montage avec la voix CLONEE du proprietaire (Chatterbox Multilingual) -> vo/<id>.wav.

Remplace la voix neuronale (« Guy »), jugee robotique et trop rapide : le timbre est celui de la reference
(`MM_VOICE_REF`, par defaut social2shorts/work/voiceover/ref_en_clean.wav ; une reference par langue avec
`MM_VOICE_REF_FR`, `MM_VOICE_REF_AR`...). La reference par defaut est un enregistrement en anglais : pour une autre
langue il faut regler la reference de cette langue (ou imposer `MM_VOICE_REF`), sinon on s'arrete.

Langue : `--lang fr|en|ar` (defaut : MM_VOICE_LANG, sinon `voice_lang` de local_paths.json, sinon en). Elle va au
modele de voix, a Whisper et a la comparaison des mots (mm_lang.py). En anglais l'accroche est mise en phrase et
« POV » epele ; dans une autre langue elle est dite comme elle est ecrite (majuscule au debut, point final s'il manque).

Chaque essai est REECOUTE avant d'etre garde (mm_voicecheck.py) : un modele generatif deborde parfois apres la phrase
(il la repete, ajoute un mot, bredouille) et son analyseur coupe alors la generation au milieu d'un mot. Un essai est
refuse si le modele a force sa fin, si le son finit coupe, si Whisper n'entend pas EXACTEMENT les mots voulus, ou si
de la parole reprend apres la phrase. Parmi les essais acceptes, on garde le meilleur compromis debit / ressemblance
au proprietaire / sans trou. Aucun essai accepte = la ligne est refusee, jamais une voix fautive gardee.

Debit : cible par langue (anglais 2,5 mots/s, francais 3,2, arabe 2,5 ; `--words-per-s` l'impose). En anglais un essai
trop rapide est ralenti de 15 % au plus (plus, la voix sonne artificielle). Dans une autre langue un essai n'est
JAMAIS ralenti (le ralenti rendait la voix francaise endormie) ; un essai trop lent est accelere de 20 % au plus dans
toutes les langues. Hors de l'anglais, les mots comptes sont ceux qu'on dit (mm_lang.words : un « ? » isole n'est pas
un mot, « d'un » en fait deux).

- reprise : une voix deja VALIDEE pour le meme texte, dans la meme langue, est conservee dans vo/_cache/ (`--force`
  pour tout refaire) ;
- `--verify-cache` reecoute tout le cache : les voix fautives vont dans vo/_cache/_rejete/ (avec la raison) et seront
  regenerees ; les bonnes sont marquees validees (aucune reference de voix n'est necessaire, ni pour `--fix-cache`) ;
- aucun repli vers une voix synthetique ni vers une voix non verifiee : sans Chatterbox ou sans Whisper, on s'arrete ;
- `--tries N` (defaut 6, jusqu'a 3N si aucun n'est accepte) ; `--words-per-s X` ; graine fixe par essai ;
- `--lines-file f.txt` genere d'avance une accroche par ligne ; `--fix-cache` rattrape le debit ; `--refine` relance
  les voix mediocres de la langue avec 12 essais ;
- `MM_TTS_T3` (ex. « v3 ») choisit le point de controle T3 de Chatterbox, si la version installee le permet.
Usage : python scan/gen_vo_clone.py [--lang fr] [--force] [--tries 6] [--words-per-s 2.5] [--ids safe_pov_00 ...]
        python scan/gen_vo_clone.py --verify-cache | [--lang fr] --lines-file hooks.txt
"""
import sys
from pathlib import Path as _P

sys.path.insert(0, str(_P(__file__).resolve().parents[1]))
import hashlib
import inspect
import json
import os
import re
import shutil
import subprocess
import time

import numpy as np
import soundfile as sf

import mm_lang
import mm_paths
import mm_voicecheck

mm_paths.use_root()
SETTINGS = [(0.2, 0.5), (0.3, 0.5), (0.4, 0.5), (0.2, 0.6), (0.3, 0.6), (0.4, 0.6)]   # (cfg_weight, exaggeration)
MIN_SPEECH = 1.2          # s : une accroche plus courte sonne comme un cri
MAX_GAP = 0.35            # s : silence maximal tolere AU MILIEU de la phrase
CHECKED = "asr-1"         # version de la validation enregistree dans le cache : une voix sans elle est reverifiee
WORDS_PER_S = {"en": 2.5, "fr": 3.2, "ar": 2.5}   # debit cible par langue (`--words-per-s` l'impose)
KEY_SEP = chr(0x1F)       # separateur d'unite (U+001F) entre la langue et le texte : il ne peut pas etre dans une phrase
ENDS = (".", "?", "!", "…", "؟")                  # une phrase qui finit deja : pas de point ajoute


def cache_key(line, lang="en"):
    """Cle du cache : le texte seul en anglais (les voix deja validees restent valables) ; sinon la langue, le
    separateur d'unite puis le texte (aucune phrase anglaise ne peut donner la meme cle)."""
    text = line if lang == "en" else f"{lang}{KEY_SEP}{line}"
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def hook_line(m, lang="en"):
    """Texte DIT. En anglais : l'accroche en phrase, « POV » epele (un modele de voix le lirait comme un mot). Dans
    une autre langue : l'accroche comme elle est ecrite (ses capitales restent), majuscule a la premiere lettre, et
    un point final seulement si elle ne finit pas deja par un point, « ? », « ! » ou des points de suspension."""
    if lang == "en":
        line = m["hook"].capitalize().rstrip(".") + "."
        return re.sub(r"\bPov:?", "P.O.V.,", line)
    line = m["hook"].strip()
    line = line[:1].upper() + line[1:]
    return line if line.endswith(ENDS) else line + "."


def word_count(line, lang="en"):
    """Nombre de mots pour la duree cible. Anglais : le decoupage aux espaces d'origine (les voix validees gardent
    leur cible). Autre langue : les mots qu'on dit (mm_lang.words : un « ? » ou un « : » isole n'est pas un mot, un
    nombre en chiffres compte pour ses mots, « d'un » en fait deux)."""
    return len(line.split()) if lang == "en" else len(mm_lang.words(line, lang))


def target_s(line, wps, lang="en"):
    """Duree de parole visee (s) pour dire `line` a `wps` mots par seconde, jamais sous MIN_SPEECH."""
    return max(MIN_SPEECH, word_count(line, lang) / wps)


def speech_stats(w, sr):
    """(duree de parole hors silences de bord, plus long silence interne), en secondes."""
    peak = float(np.max(np.abs(w))) or 1.0
    on = np.abs(w) > 0.03 * peak
    idx = np.where(on)[0]
    if not len(idx):
        return 0.0, 9.0
    a, b = idx[0], idx[-1]
    gaps, run = [], 0
    for v in on[a:b + 1]:
        if v:
            if run:
                gaps.append(run)
            run = 0
        else:
            run += 1
    return (b - a) / sr, (max(gaps) / sr if gaps else 0.0)


def trim_and_fade(w, sr):
    """Coupe les silences de bord SANS manger la fin du dernier mot : debut a 3 % du pic (+30 ms), fin a 1 % du pic
    (+120 ms de resonance), fondu d'entree de 10 ms et de sortie de 50 ms (pas de clic, pas de coupure seche)."""
    w = np.asarray(w, dtype=np.float32).copy()
    peak = float(np.max(np.abs(w))) or 1.0
    start = np.where(np.abs(w) > 0.03 * peak)[0]
    end = np.where(np.abs(w) > 0.01 * peak)[0]
    if not len(start):
        return w
    w = w[max(0, start[0] - int(0.03 * sr)): min(len(w), end[-1] + int(0.12 * sr))]
    n_in, n_out = int(0.01 * sr), int(0.05 * sr)
    if w.size > n_in + n_out:
        w[:n_in] *= np.linspace(0.0, 1.0, n_in, dtype=np.float32)
        w[-n_out:] *= np.linspace(1.0, 0.0, n_out, dtype=np.float32)
    return w * (0.9 / (float(np.max(np.abs(w))) or 1.0))


PACE_LOW, PACE_HIGH = 0.85, 1.25   # tolerance autour de la cible : au-dela on corrige le debit (atempo)
RATE_MIN, RATE_MAX = 0.85, 1.2     # ralentir de plus de 15 % rend la voix artificielle (« robotique »)
SIM_GOOD = 0.90                    # ressemblance (empreinte de locuteur) a la reference : en dessous, un essai est penalise
SR_EMBED = 16000


def pace_rate(dur, target, lang="en"):
    """Facteur atempo que fix_pace appliquera (1.0 : debit deja dans la tolerance). Hors de l'anglais le facteur ne
    descend jamais sous 1.0 : un essai n'est JAMAIS ralenti (le ralenti rendait la voix francaise endormie)."""
    if target * PACE_LOW <= dur <= target * PACE_HIGH or dur <= 0:
        return 1.0
    return max(RATE_MIN if lang == "en" else 1.0, min(RATE_MAX, dur / target))


def candidate_score(dur, target, gap, sim=None, lang="en"):
    """Plus bas = meilleur. Mesure le RESULTAT FINAL : duree apres correction du debit, etirement subi, trou au milieu
    de la phrase, ressemblance au proprietaire. (Le CONTENU est verifie a part : un essai fautif n'est jamais note.)"""
    rate = pace_rate(dur, target, lang)
    score = abs(dur / rate - target) / target + 0.6 * abs(1.0 - rate) + 3.0 * max(0.0, gap - MAX_GAP)
    if sim is not None:
        score += 4.0 * max(0.0, SIM_GOOD - sim)
    return score


REFINE_ABOVE = 0.12   # une voix stockee dont le score depasse ce seuil est relancee par --refine


def stored_score(info):
    """Score d'une voix deja generee (le debit a pu etre corrige : on compte l'etirement deja subi)."""
    base = candidate_score(info["speech_s"], info["target_s"], info.get("gap_s", 0.0), info.get("sim"),
                           info.get("lang", "en"))
    return base + 0.6 * abs(1.0 - info.get("paced", 1.0))


def embed(model, w, sr):
    """Empreinte de locuteur (encodeur de Chatterbox, normalisee) d'un signal mono."""
    import librosa
    w16 = librosa.resample(np.asarray(w, dtype=np.float32), orig_sr=sr, target_sr=SR_EMBED)
    return model.ve.embeds_from_wavs([w16], sample_rate=SR_EMBED)[0]


def ref_embedding(model, ref):
    import librosa
    w, _ = librosa.load(str(ref), sr=SR_EMBED, mono=True)
    return model.ve.embeds_from_wavs([w], sample_rate=SR_EMBED)[0]


def fix_pace(wav_path, info):
    """Ramene le debit vers la cible quand l'essai retenu en est trop loin. Une seule fois. La langue est celle de
    `info` (anglais si elle n'y est pas) : hors de l'anglais, une voix n'est jamais ralentie."""
    if info.get("paced"):
        return info
    dur, target = info["speech_s"], info["target_s"]
    rate = pace_rate(dur, target, info.get("lang", "en"))   # < 1 : on ralentit ; borne pour garder une voix naturelle
    if rate == 1.0:
        return info
    tmp = _P(wav_path).with_suffix(".paced.wav")
    r = subprocess.run([mm_paths.FFMPEG, "-y", "-v", "error", "-i", str(wav_path), "-af", f"atempo={rate:.3f}", str(tmp)],
                       capture_output=True, text=True)
    if r.returncode == 0 and tmp.exists():
        tmp.replace(wav_path)
        info = {**info, "speech_s": round(dur / rate, 2), "paced": round(rate, 3)}
    return info


def _seed(k):
    try:
        import torch
        torch.manual_seed(k)
    except ImportError:          # tests sans torch : un faux modele n'en a pas besoin
        pass


def generate_take(model, line, ref, cfg, exag, lang="en"):
    """Un essai dans la langue `lang` : (signal brut mono, avertissements de fin forcee emis pendant CET essai)."""
    with mm_voicecheck.EOSWatch() as watch:
        out = model.generate(line, language_id=lang, audio_prompt_path=str(ref), exaggeration=exag,
                             cfg_weight=cfg, temperature=0.7)
    w = out.detach().cpu().float().numpy().reshape(-1) if hasattr(out, "detach") else np.asarray(out, np.float32).reshape(-1)
    return w, list(watch.events)


def generate_takes(model, line, ref, n, seed0, ref_emb, out_dir, lang="en"):
    """Phase 1 (modele de voix seul en memoire) : `n` essais gardes sur disque, avec ce que le modele en dit (fin
    forcee) et ce que le signal BRUT montre (fin coupee) ; la reecoute vient apres, modele decharge."""
    out_dir.mkdir(parents=True, exist_ok=True)
    takes = []
    for k in range(n):
        seed = seed0 + k
        cfg, exag = SETTINGS[seed % len(SETTINGS)]
        _seed(seed)
        w, eos = generate_take(model, line, ref, cfg, exag, lang)
        path = out_dir / f"{cache_key(line, lang)}_{seed}.wav"
        sf.write(str(path), trim_and_fade(w, model.sr), model.sr)
        dur, gap = speech_stats(w, model.sr)
        sim = float(np.dot(ref_emb, embed(model, w, model.sr))) if ref_emb is not None else None
        takes.append({"path": str(path), "seed": seed, "eos": eos, "abrupt": bool(mm_voicecheck.abrupt_end(w, model.sr)),
                      "dur": round(dur, 3), "gap": round(gap, 3), "sim": None if sim is None else round(sim, 4),
                      "cfg": cfg, "exag": exag})
    return takes


def validate_takes(takes, line, asr, log=print, lang="en"):
    """Phase 2 (Whisper seul en memoire) : reecoute de chaque essai pas encore juge -> t['problems'], t['heard']."""
    for t in takes:
        if "problems" in t:
            continue
        t["problems"], t["heard"] = mm_voicecheck.check_take(None, None, t["path"], line, asr, t["eos"], t["abrupt"],
                                                             lang=lang)
        verdict = ("refuse : " + "; ".join(t["problems"])[:140]) if t["problems"] else f"accepte : « {t['heard']} »"
        log(f"   essai {t['seed']} {verdict}")
    return takes


def keep_best(line, takes, target, asr, log=print, lang="en"):
    """Met dans le cache le meilleur essai ACCEPTE (debit, ressemblance, sans trou). Si son debit est corrige (ralenti
    en anglais seulement, accelere dans toutes les langues), l'essai corrige est reecoute aussi, dans la meme langue ;
    une voix deja validee n'est remplacee qu'en cas de succes. -> (wav, info) ou None."""
    cache = mm_paths.VO / "_cache"
    key = cache_key(line, lang)
    wav, meta, tmp = cache / f"{key}.wav", cache / f"{key}.json", cache / f"_{key}.wav"
    accepted = sorted((t for t in takes if not t.get("problems")),
                      key=lambda t: candidate_score(t["dur"], target, t["gap"], t["sim"], lang))
    rejected = sum(1 for t in takes if t.get("problems"))
    for t in accepted:
        shutil.copyfile(t["path"], tmp)
        info = fix_pace(tmp, {"line": line, "lang": lang, "speech_s": round(t["dur"], 2), "target_s": round(target, 2),
                              "cfg": t["cfg"], "exag": t["exag"], "gap_s": round(t["gap"], 2), "sim": t["sim"],
                              "heard": t["heard"], "rejected_takes": rejected, "checked": CHECKED,
                              "asr_model": getattr(asr, "model", None)})
        if info.get("paced"):
            kept, ksr = sf.read(str(tmp), dtype="float32")
            problems, heard = mm_voicecheck.check_take(kept, ksr, tmp, line, asr, lang=lang)
            if problems:
                log(f"   essai {t['seed']} refuse apres {'ralenti' if lang == 'en' else 'acceleration'} : "
                    f"{'; '.join(problems)[:120]}")
                continue
            info["heard"] = heard
        tmp.replace(wav)
        meta.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
        t["kept"] = True
        return wav, info
    tmp.unlink(missing_ok=True)
    return None


def pick(model, line, ref, tries, wps, seed0=1000, ref_emb=None, asr=None, max_tries=None, log=print, lang="en"):
    """Les deux modeles en memoire a la fois (petits lots, tests) : meilleur essai VALIDE ->
    ((score, signal, duree, trou, cfg, exag, ressemblance, entendu), cible, refus). None si aucun ne passe."""
    if asr is None:
        raise ValueError("pas de voix sans reecoute : il faut un ASR (mm_voicecheck.ASR)")
    target = target_s(line, wps, lang)
    max_tries = max_tries or 3 * tries
    tmpdir = mm_paths.VO / "_cache" / "_essais"
    best, rejected, k = None, [], 0
    while k < max_tries and (k < tries or best is None):
        t = generate_takes(model, line, ref, 1, seed0 + k, ref_emb, tmpdir, lang)[0]
        k += 1
        validate_takes([t], line, asr, log=lambda *_: None, lang=lang)
        if t["problems"]:
            rejected.append({"essai": k, "entendu": t["heard"], "problemes": t["problems"]})
            log(f"   essai {k} refuse : {'; '.join(t['problems'])[:140]}")
            continue
        w, _ = sf.read(t["path"], dtype="float32")
        score = candidate_score(t["dur"], target, t["gap"], t["sim"], lang)
        log(f"   essai {k} accepte : « {t['heard']} » score {score:.2f}")
        if best is None or score < best[0]:
            best = (score, w, t["dur"], t["gap"], t["cfg"], t["exag"], t["sim"], t["heard"])
        if best[0] < 0.08:          # valide, debit dans la cible, voix ressemblante : inutile d'en generer d'autres
            break
    shutil.rmtree(tmpdir, ignore_errors=True)
    return best, target, rejected


def unload(model):
    """Libere la memoire du modele de voix avant de charger Whisper (les deux ne tiennent pas ensemble)."""
    import gc
    del model
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def _validated(line, cache, lang="en"):
    meta = cache / f"{cache_key(line, lang)}.json"
    if meta.exists():
        info = json.loads(meta.read_text(encoding="utf-8"))
        if info.get("checked") == CHECKED:
            return cache / f"{cache_key(line, lang)}.wav", info
    return None


def phase_generate(job_path, ref, log=print):
    """Processus 1 : le modele de voix genere les essais du tour, les ecrit (avec leurs mesures) puis le processus se
    TERMINE : toute sa memoire est rendue avant que Whisper ne demarre. La langue est celle du fichier de travail
    (anglais si elle n'y est pas)."""
    job = json.loads(_P(job_path).read_text(encoding="utf-8"))
    lang = job.get("lang", "en")
    model = load_model()
    ref_emb = ref_embedding(model, ref)
    for line in job["lines"]:
        log(f"   generation : '{line}'")
        job["takes"].setdefault(line, []).extend(
            generate_takes(model, line, ref, job["tries"], job["seed0"], ref_emb, _P(job["dir"]), lang))
    _P(job_path).write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    return 0


def phase_validate(job_path, log=print):
    """Processus 2 : Whisper reecoute les essais pas encore juges, dans la langue du fichier de travail, et garde le
    meilleur essai accepte de chaque phrase."""
    job = json.loads(_P(job_path).read_text(encoding="utf-8"))
    lang = job.get("lang", "en")
    asr = open_asr()
    try:
        for line in job["lines"]:
            log(f"'{line}'")
            validate_takes(job["takes"][line], line, asr, log, lang)
            keep_best(line, job["takes"][line], target_s(line, job["wps"], lang), asr, log, lang)
    finally:
        asr.close()
    _P(job_path).write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    return 0


def make_many(lines, ref, tries, wps, force=False, rounds=3, log=print, separate=False, lang="en"):
    """Voix VALIDEES pour des phrases dites dans la langue `lang` (elle voyage dans le fichier de travail jusqu'aux
    deux phases) -> ({phrase: (wav, info, deja_validee)}, [phrases refusees]).
    Phase 1 : le modele de voix genere `tries` essais par phrase ; phase 2 : Whisper reecoute tout et garde le meilleur
    essai accepte. Les deux modeles ne sont jamais en memoire ensemble : `separate=True` (ligne de commande) lance chaque
    phase dans son propre processus ; sinon (tests) le modele est decharge entre les deux. Une phrase sans essai valide
    repart pour un tour (nouvelles graines), au plus `rounds` tours : une voix fautive n'est jamais gardee par defaut."""
    cache = mm_paths.VO / "_cache"
    cache.mkdir(parents=True, exist_ok=True)
    done = {}
    for line in dict.fromkeys(lines):
        hit = None if force else _validated(line, cache, lang)
        if hit:
            done[line] = (*hit, True)
    pending = [line for line in dict.fromkeys(lines) if line not in done]
    takes_dir = cache / "_essais"
    takes_dir.mkdir(parents=True, exist_ok=True)
    job_path = takes_dir / "job.json"
    job = {"lines": pending, "lang": lang, "tries": tries, "wps": wps, "seed0": 1000, "dir": str(takes_dir),
           "takes": {}}
    for rnd in range(rounds):
        if not pending:
            break
        job.update(lines=pending, seed0=1000 + 100 * rnd)
        job_path.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
        log(f"tour {rnd + 1} : {len(pending)} phrase(s), {tries} essais chacune (modele de voix)")
        if separate:
            for phase in ("generate", "validate"):
                r = subprocess.run([sys.executable, "-X", "utf8", str(_P(__file__).resolve()), "--phase", phase, str(job_path)])
                if r.returncode != 0:
                    raise SystemExit(f"phase {phase} en echec (code {r.returncode}) : aucune voix non verifiee n'est gardee")
        else:
            model = load_model()
            ref_emb = ref_embedding(model, ref)
            for line in pending:
                job["takes"].setdefault(line, []).extend(
                    generate_takes(model, line, ref, tries, job["seed0"], ref_emb, takes_dir, lang))
            unload(model)
            model = None
            job_path.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
            log("reecoute de tous les essais (Whisper)")
            asr = open_asr()
            try:
                for line in pending:
                    validate_takes(job["takes"][line], line, asr, log, lang)
                    keep_best(line, job["takes"][line], target_s(line, wps, lang), asr, log, lang)
            finally:
                asr.close()
            job_path.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
        job = json.loads(job_path.read_text(encoding="utf-8"))
        for line in pending:                       # refaite = un essai de CE passage a ete garde (sinon l'ancienne reste)
            hit = _validated(line, cache, lang)
            if hit and any(t.get("kept") for t in job["takes"].get(line, [])):
                done[line] = (*hit, False)
        pending = [line for line in pending if line not in done]
    shutil.rmtree(takes_dir, ignore_errors=True)
    return done, pending


def verify_cache(asr, log=print):
    """Reecoute tout vo/_cache/, chaque voix dans SA langue (anglais si elle n'est pas notee) : fautives ->
    vo/_cache/_rejete/ (avec la raison) ; bonnes -> marquees validees."""
    cache = mm_paths.VO / "_cache"
    bad_dir = cache / "_rejete"
    ok = bad = 0
    for meta in sorted(cache.glob("*.json")):
        info = json.loads(meta.read_text(encoding="utf-8"))
        wav = meta.with_suffix(".wav")
        if not wav.exists():
            continue
        w, sr = sf.read(str(wav), dtype="float32")
        problems, heard = mm_voicecheck.check_take(w, sr, wav, info["line"], asr, lang=info.get("lang", "en"))
        if problems:
            bad_dir.mkdir(exist_ok=True)
            info.update(heard=heard, problems=problems, checked=None)
            (bad_dir / meta.name).write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
            shutil.move(str(wav), str(bad_dir / wav.name))
            meta.unlink()
            bad += 1
            log(f"REFUSEE  '{info['line']}' entendu « {heard} » : {'; '.join(problems)}")
        else:
            info.update(heard=heard, checked=CHECKED, asr_model=getattr(asr, "model", None))
            meta.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
            ok += 1
            log(f"validee  '{info['line']}' entendu « {heard} »")
    log(f"{ok} voix validee(s), {bad} refusee(s) (dans {bad_dir})")
    return bad


def pretrained_kwargs(from_pretrained, device):
    """Arguments de `from_pretrained`. MM_TTS_T3 (ex. « v3 ») choisit le point de controle T3 : il n'est passe que si
    la version installee de Chatterbox a le parametre `t3_model` ; sinon on s'arrete, plutot que de generer avec un
    autre point de controle que celui demande."""
    kwargs = {"device": device}
    t3 = os.environ.get("MM_TTS_T3")
    if t3:
        if "t3_model" not in inspect.signature(from_pretrained).parameters:
            sys.exit(f"MM_TTS_T3={t3} : cette version de Chatterbox ne sait pas choisir son point de controle "
                     "(from_pretrained n'a pas de parametre t3_model). Installer une version qui l'accepte, ou "
                     "retirer MM_TTS_T3.")
        kwargs["t3_model"] = t3
    return kwargs


def load_model():
    try:
        import torch
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    except ImportError as e:
        sys.exit(f"Chatterbox indisponible ({e}) : la voix clonee est obligatoire, aucun repli sur une voix synthetique.")
    loader = ChatterboxMultilingualTTS.from_pretrained
    return loader(**pretrained_kwargs(loader, "cuda" if torch.cuda.is_available() else "cpu"))


def open_asr(log=print):
    """Demarre le serveur Whisper et dit, une fois, quel modele reecoute et sur quel processeur (cpu ou cuda)."""
    try:
        asr = mm_voicecheck.ASR().__enter__()
    except Exception as e:  # sans Whisper, aucune voix ne peut etre validee : on s'arrete
        sys.exit(f"reecoute impossible ({e}) : faster-whisper est requis (MM_ASR_PYTHON), aucune voix non verifiee.")
    log(f"reecoute Whisper {asr.model} sur {asr.device or 'un processeur non annonce'}")
    return asr


def same_file(a, b):
    return _P(b).exists() and _P(a).stat().st_size == _P(b).stat().st_size and _P(a).read_bytes() == _P(b).read_bytes()


def main(argv):
    force = "--force" in argv
    tries = int(argv[argv.index("--tries") + 1]) if "--tries" in argv else 6
    only = argv[argv.index("--ids") + 1:] if "--ids" in argv else None
    try:
        if "--phase" in argv:                      # processus fils : la langue est celle du fichier de travail
            job_file = _P(argv[argv.index("--phase") + 2])
            lang = mm_lang.checked(json.loads(job_file.read_text(encoding="utf-8")).get("lang", "en"))
        elif "--lang" in argv:
            value = argv[argv.index("--lang") + 1:argv.index("--lang") + 2]
            if not value:
                sys.exit(f"--lang attend une langue (valeurs permises : {', '.join(mm_lang.LANGS)})")
            lang = mm_lang.checked(value[0].lower())
        else:
            lang = mm_lang.default_lang()
    except ValueError as e:
        sys.exit(str(e))
    wps = float(argv[argv.index("--words-per-s") + 1]) if "--words-per-s" in argv else WORDS_PER_S[lang]
    mm_paths.VO.mkdir(exist_ok=True)
    if "--fix-cache" in argv:                      # rattrape le debit des voix deja generees (idempotent)
        n = 0
        for meta in sorted((mm_paths.VO / "_cache").glob("*.json")):
            info = json.loads(meta.read_text(encoding="utf-8"))
            new = fix_pace(meta.with_suffix(".wav"), info)
            if new != info:
                new["checked"] = None              # le ralenti change le son : la voix devra etre reecoutee
                meta.write_text(json.dumps(new, ensure_ascii=False), encoding="utf-8")
                n += 1
                print(f"debit corrige : '{info['line']}' {info['speech_s']}s -> {new['speech_s']}s (a reverifier)")
        print(f"{n} voix corrigee(s)")
        return 0
    if "--verify-cache" in argv:                   # comme --fix-cache : aucune reference de voix n'est necessaire
        asr = open_asr()
        try:
            return 1 if verify_cache(asr) else 0
        finally:
            asr.close()
    ref = mm_paths.voice_ref(lang)                 # tout le reste genere des voix : il faut la reference de la langue
    if ref is None:
        sys.exit(f"aucune reference de voix pour la langue « {lang} » : regler MM_VOICE_REF_{lang.upper()} (ou "
                 f"voice_ref_{lang} dans local_paths.json). La reference par defaut est un enregistrement en anglais : "
                 "elle n'est pas reprise pour une autre langue (MM_VOICE_REF l'impose si c'est voulu).")
    if not ref.exists():
        sys.exit(f"reference de voix absente : {ref} (MM_VOICE_REF_{lang.upper()} ou MM_VOICE_REF)")
    if "--phase" in argv:                          # processus fils lances par make_many(separate=True)
        phase, job = argv[argv.index("--phase") + 1], argv[argv.index("--phase") + 2]
        return phase_generate(job, ref) if phase == "generate" else phase_validate(job)
    if "--refine" in argv or "--redo-pace" in argv:   # relance, avec 12 essais, les voix validees mais mediocres
        lines = []
        for meta in sorted((mm_paths.VO / "_cache").glob("*.json")):
            info = json.loads(meta.read_text(encoding="utf-8"))
            if info.get("checked") == CHECKED and info.get("lang", "en") == lang and stored_score(info) > REFINE_ABOVE:
                lines.append(info["line"])            # une langue a la fois : celle de --lang, avec sa reference
        done, ko = make_many(lines, ref, 12, wps, force=True, separate=True, lang=lang)
        print(f"{len(done)} voix relancee(s) ; gardees telles quelles faute de mieux : {ko}")
        return 0
    lines_mode = "--lines-file" in argv
    if lines_mode:
        jobs = [(None, ln.strip()) for ln in open(argv[argv.index("--lines-file") + 1], encoding="utf-8") if ln.strip()]
    else:
        man = [m for m in json.load(open("scan/batch_manifest.json", encoding="utf-8")) if not only or m["id"] in only]
        jobs = [(m["id"], hook_line(m, lang)) for m in man]
    t0 = time.time()
    done, ko = make_many([line for _, line in jobs], ref, tries, wps, force, separate=True, lang=lang)
    for k, (mid, line) in enumerate(jobs, 1):
        if line not in done:
            print(f"[{k}/{len(jobs)}] KO {mid or ''} '{line}' : aucun essai n'a passe la reecoute", flush=True)
            continue
        wav, info, cached = done[line]
        if mid:
            out = mm_paths.VO / f"{mid}.wav"
            if not same_file(wav, out):
                shutil.copyfile(wav, out)
            (mm_paths.VO / f"{mid}.clone.txt").write_text(
                f"{line}\nentendu (Whisper) : {info.get('heard')}\nparole {info['speech_s']}s (cible {info['target_s']}s), "
                f"cfg {info['cfg']}, exagg. {info['exag']}, plus long silence {info['gap_s']}s, ressemblance {info.get('sim')}, "
                f"essais refuses {info.get('rejected_takes', 0)}\nlangue : {lang}\n", encoding="utf-8")
        print(f"[{k}/{len(jobs)}] {mid or ''} '{line}' {'(cache valide)' if cached else ''} entendu « {info.get('heard')} » "
              f"parole {info['speech_s']}s {word_count(line, lang) / max(info['speech_s'], 1e-3):.2f} mots/s", flush=True)
    print(f"DONE vo_clone{' (cache)' if lines_mode else ''} : {len(jobs) - len(ko)} voix validees, {len(ko)} refusees {ko} "
          f"({time.time() - t0:.0f}s)", flush=True)
    return 1 if ko else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
