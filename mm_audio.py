# -*- coding: utf-8 -*-
"""Piste son d'un montage : musique + voix courte, construites en UNE passe a partir des fichiers d'origine.

Pourquoi : l'ancien montage normalisait la musique, puis mixait la voix a part (re-encodage de l'audio, voix a peine
plus forte que la musique => « voix au fond d'un tunnel », audio a 96 kHz, parfois un flux AAC corrompu).
Ici : voix traitee (chaleur, presence, compression) ; musique baissee automatiquement sous la voix (sidechain) ;
deux passes de loudnorm (gain lineaire, sans pompage) ; sortie AAC 48 kHz ; controle d'integrite du flux.
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import mm_paths

FF = mm_paths.FFMPEG
FFPROBE = mm_paths.FFPROBE
SR = 48000
MUSIC_BED_LUFS = -15.5     # niveau de la musique (extrait utilise) avant ducking
VOICE_LUFS = -13.5         # niveau de la voix traitee : nettement au-dessus de la musique baissee
FINAL_LUFS = -14.0         # reference YouTube : plus fort serait simplement baisse par la plateforme
FINAL_TP = -1.0
VOICE_DELAY = 0.4          # la voix demarre 0,4 s apres le debut (le texte du hook apparait a 0,15 s)
MUSIC_FADE_IN, MUSIC_FADE_OUT = 0.25, 0.9
XOVER = 200                # Hz : sous cette frequence on garde la basse de la musique (808), au-dessus on fait de la place a la voix
DUCK_HI = "sidechaincompress=threshold=0.012:ratio=10:attack=10:release=400:makeup=1"
DUCK_LO = "sidechaincompress=threshold=0.03:ratio=1.5:attack=10:release=400:makeup=1"

# Voix : passe-haut, chaleur (bas), creux a 330 Hz (son « de boite »), presence (3 kHz), air, de-esser,
# compression douce ; puis gain et limiteur (voir fit_voice_gain). AUCUN echo, AUCUNE reverberation.
VOICE_CHAIN = ("aresample=48000,aformat=channel_layouts=mono,highpass=f=80,"
               "lowshelf=f=150:g=3.5,equalizer=f=330:t=q:w=1.1:g=-2.5,"
               "equalizer=f=3000:t=q:w=0.9:g=4,highshelf=f=7500:g=2,"
               "deesser=i=0.4:m=0.5:f=0.5,"
               "acompressor=threshold=-24dB:ratio=3:attack=8:release=100:makeup=2dB:knee=4dB")
VOICE_LIMIT = "alimiter=limit=0.85:attack=5:release=80:level=0"


def run(cmd, timeout=180):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def duration(path):
    r = run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    return float(r.stdout.strip() or 0)


def lufs(args):
    """Loudness integree (LUFS) mesuree par ffmpeg ; `args` = arguments d'entree + filtre (ebur128 en dernier)."""
    r = run([FF, "-hide_banner", "-nostats", *args, "-f", "null", "-"])
    m = re.findall(r"I:\s+(-?\d+\.\d+)\s+LUFS", r.stderr)
    return float(m[-1]) if m else None


def music_filter(offset, total):
    return (f"aresample={SR},atrim=start={offset:.3f},asetpts=PTS-STARTPTS,atrim=0:{total:.3f},"
            f"aformat=channel_layouts=stereo,afade=t=in:d={MUSIC_FADE_IN},"
            f"afade=t=out:st={max(0.0, total - MUSIC_FADE_OUT):.3f}:d={MUSIC_FADE_OUT}")


def voice_filter(voice_len, gain_db=0.0):
    """Chaine voix + fondus courts (pas de claquement) + gain + limiteur ; sortie stereo."""
    tail = max(0.05, min(0.12, voice_len / 4))
    return (f"{VOICE_CHAIN},afade=t=in:d=0.02,afade=t=out:st={max(0.0, voice_len - tail):.3f}:d={tail:.3f},"
            f"volume={gain_db:.2f}dB,{VOICE_LIMIT},aformat=channel_layouts=stereo")


def fit_voice_gain(voice, vlen):
    """Gain (dB) qui amene la voix, APRES limiteur, a VOICE_LUFS. 3 iterations de mesure ; plafonne a +22 dB."""
    base = lufs(["-i", str(voice), "-af", voice_filter(vlen) + ",ebur128=peak=true"])
    if base is None:
        return 0.0, None
    g = min(22.0, VOICE_LUFS - base)
    cur = base
    for _ in range(3):
        cur = lufs(["-i", str(voice), "-af", voice_filter(vlen, g) + ",ebur128=peak=true"])
        if cur is None or abs(cur - VOICE_LUFS) < 0.2:
            break
        g = min(22.0, g + (VOICE_LUFS - cur))
    return g, cur


def build_audio(music, offset, total, voice, out_m4a, tmp):
    """Ecrit `out_m4a` (AAC 48 kHz, duree `total`). voice=None : musique seule. Retourne un dict de mesures."""
    tmp = Path(tmp)
    info = {}
    # 1) niveaux : on mesure la musique (extrait) et la voix (traitee) pour regler la balance
    g_music = 0.0
    m_i = lufs(["-i", str(music), "-af", music_filter(offset, total) + ",ebur128=peak=true"])
    if m_i is not None:
        g_music = MUSIC_BED_LUFS - m_i
    info["music_lufs"] = m_i
    inputs = ["-i", str(music)]
    graph = (f"[0:a]{music_filter(offset, total)},volume={g_music:.2f}dB,asplit=2[mlo][mhi];"
             f"[mlo]lowpass=f={XOVER},lowpass=f={XOVER}[lo];[mhi]highpass=f={XOVER},highpass=f={XOVER}[hi]")
    if voice:
        vlen = duration(voice)
        g_voice, v_i = fit_voice_gain(voice, vlen)
        info.update(voice_lufs=v_i, voice_gain_db=round(g_voice, 1), voice_len=vlen)
        inputs += ["-i", str(voice)]
        d = int(VOICE_DELAY * 1000)
        graph += (f";[1:a]{voice_filter(vlen, g_voice)},adelay={d}:all=1,apad=whole_dur={total:.3f}[vox];"
                  f"[vox]asplit=3[voxm][vs1][vs2];"
                  f"[hi][vs1]{DUCK_HI}[hid];[lo][vs2]{DUCK_LO}[lod];"
                  f"[lod][hid]amix=inputs=2:duration=first:normalize=0[duck];"
                  f"[duck][voxm]amix=inputs=2:duration=first:normalize=0,"
                  f"alimiter=limit=0.9:attack=3:release=50:level=0[mix]")
    else:
        graph += ";[lo][hi]amix=inputs=2:duration=first:normalize=0[mix]"
    pre = tmp / "premix.wav"
    r = run([FF, "-y", *inputs, "-filter_complex", graph, "-map", "[mix]", "-ar", str(SR), "-c:a", "pcm_s16le", str(pre)])
    if not pre.exists():
        raise RuntimeError("mix audio : " + r.stderr[-300:])
    # 2) loudnorm en deux passes (gain lineaire, sans pompage) puis AAC 48 kHz
    p1 = run([FF, "-hide_banner", "-nostats", "-i", str(pre), "-af",
              f"loudnorm=I={FINAL_LUFS}:TP={FINAL_TP}:LRA=11:print_format=json", "-f", "null", "-"])
    mj = re.search(r"\{[^{}]*input_i[^{}]*\}", p1.stderr, re.S)
    ln = f"loudnorm=I={FINAL_LUFS}:TP={FINAL_TP}:LRA=11"
    if mj:
        j = json.loads(mj.group(0))
        ln += (f":measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}"
               f":measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
        info["premix_lufs"] = float(j["input_i"])
    r = run([FF, "-y", "-i", str(pre), "-af", f"{ln},aresample={SR}", "-ar", str(SR), "-ac", "2",
             "-c:a", "aac", "-b:a", "192k", str(out_m4a)])
    if not Path(out_m4a).exists():
        raise RuntimeError("encodage AAC : " + r.stderr[-300:])
    info["final_lufs"] = lufs(["-i", str(out_m4a), "-af", "ebur128=peak=true"])
    return info


def stream_report(path):
    """Controle d'integrite de la piste audio d'un fichier fini : paquets AAC attendus vs reels, durees, cadence."""
    r = run([FFPROBE, "-v", "error", "-count_packets", "-show_entries",
             "stream=codec_type,sample_rate,duration,nb_read_packets", "-of", "json", str(path)])
    streams = json.loads(r.stdout or "{}").get("streams", [])
    if r.returncode != 0 or not streams:
        return {"audio": False, "error": (r.stderr or "fichier illisible")[-200:]}
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    out = {"audio": a is not None}
    if a:
        sr, dur, n = int(a["sample_rate"]), float(a["duration"]), int(a["nb_read_packets"])
        out.update(sample_rate=sr, audio_dur=dur, packets=n, packets_expected=dur * sr / 1024.0)
        out["packets_ratio"] = n / out["packets_expected"] if dur else 0
    if v:
        out["video_dur"] = float(v["duration"])
    return out


def stream_problems(rep):
    """Liste de defauts de la piste audio (liste vide = fichier sain)."""
    bad = []
    if rep.get("error"):
        return ["fichier illisible : " + rep["error"].strip()]
    if not rep.get("audio"):
        return ["pas de piste audio"]
    if rep["sample_rate"] != SR:
        bad.append(f"frequence {rep['sample_rate']} Hz au lieu de {SR}")
    if abs(rep["packets_ratio"] - 1.0) > 0.03:
        bad.append(f"flux AAC incoherent : {rep['packets']} paquets pour {rep['packets_expected']:.0f} attendus")
    if "video_dur" in rep and abs(rep["video_dur"] - rep["audio_dur"]) > 0.1:
        bad.append(f"video {rep['video_dur']:.2f} s != audio {rep['audio_dur']:.2f} s")
    return bad


if __name__ == "__main__":
    # Essai : python mm_audio.py <musique> <offset> <duree> <voix|-> <sortie.m4a>
    music, off, total, voice, out = sys.argv[1:6]
    with tempfile.TemporaryDirectory(prefix="mmaud_") as t:
        print(json.dumps(build_audio(music, float(off), float(total), None if voice == "-" else voice, out, t), indent=1))
    print(stream_report(out))
