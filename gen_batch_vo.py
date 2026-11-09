"""Genere les 30 voix du lot en UNE passe (Chatterbox charge une seule fois, GPU).
Recette smoke (exag0.5/cfg0.3/temp0.7, phrases entieres, traitement minimal).
Ecrit vo/<id>.wav + vo/<id>.timings.json + specs/<id>.json (pour make_one.py)."""
import json, time
import numpy as np, soundfile as sf, librosa, torch

import mm_paths

MONTAGE = mm_paths.ROOT
REF = mm_paths.VOICE_REF
VO = MONTAGE / "vo"; SPECS = MONTAGE / "specs"
VO.mkdir(exist_ok=True); SPECS.mkdir(exist_ok=True)
GAP = 0.45


def postproc(wav, sr, fade_ms=8, top_db=80):
    wav = np.ascontiguousarray(np.asarray(wav, dtype=np.float32))
    t, _ = librosa.effects.trim(wav, top_db=top_db)
    if t.size > sr // 20:
        wav = t
    n = int(sr * fade_ms / 1000)
    if wav.size > 2 * n and n > 0:
        r = np.linspace(0, 1, n, dtype=np.float32)
        wav[:n] *= r; wav[-n:] *= r[::-1]
    peak = float(np.max(np.abs(wav))) or 1.0
    return wav * (0.95 / peak)


def main():
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print("device", dev, flush=True)
    model = ChatterboxMultilingualTTS.from_pretrained(device=dev)
    sr = model.sr
    specs = json.load(open(MONTAGE / "manifest.json", encoding="utf-8"))
    print(len(specs), "voix a generer", flush=True)

    for k, s in enumerate(specs, 1):
        sid = s["id"]
        t0 = time.time()
        pieces, timings, t = [], [], 0.0
        for line in s["lines"]:
            wav = model.generate(line, language_id="en", audio_prompt_path=str(REF),
                                 exaggeration=0.5, cfg_weight=0.3, temperature=0.7)
            wav = postproc(np.asarray(wav.detach().cpu().float().numpy() if hasattr(wav, "detach") else wav).reshape(-1), sr)
            dur = len(wav) / sr
            timings.append({"text": line, "start": round(t, 3), "end": round(t + dur, 3)})
            pieces.append(wav)
            pieces.append(np.zeros(int(GAP * sr), dtype=np.float32))
            t += dur + GAP
        full = np.concatenate(pieces)
        sf.write(VO / f"{sid}.wav", full, sr)
        json.dump({"sr": sr, "total": round(len(full) / sr, 3), "lines": timings},
                  open(VO / f"{sid}.timings.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        spec = {"id": sid, "clip": s["clip"], "music": s["music"], "hook": s["hook"],
                "cta": s["cta"], "style": s["style"], "vo_start_s": s["vo_start_s"],
                "video_len_s": s["video_len_s"], "vo_wav": str(VO / f"{sid}.wav"),
                "timings": str(VO / f"{sid}.timings.json")}
        json.dump(spec, open(SPECS / f"{sid}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"[{k}/{len(specs)}] {sid} {len(full)/sr:.1f}s ({time.time()-t0:.1f}s)", flush=True)

    print("DONE vo", flush=True)


if __name__ == "__main__":
    main()
