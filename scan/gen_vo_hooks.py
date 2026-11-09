# -*- coding: utf-8 -*-
"""Genere une voix COURTE par montage = la ligne du hook (voix clonee, recette smoke).
Sortie vo/<id>.wav . Rapide et leger: 1 phrase, minimal."""
import json, time
from pathlib import Path
import numpy as np, soundfile as sf, librosa, torch
M=Path("C:/workdir/uw/scraper/motoride-montage"); VO=M/"vo"; VO.mkdir(exist_ok=True)
REF=Path("C:/workdir/uw/scraper/social2shorts/work/voiceover/ref_en_clean.wav")
def post(wav,sr):
    wav=np.ascontiguousarray(np.asarray(wav,dtype=np.float32))
    t,_=librosa.effects.trim(wav,top_db=80)
    if t.size>sr//20: wav=t
    n=int(sr*0.008)
    if wav.size>2*n: r=np.linspace(0,1,n,dtype=np.float32); wav[:n]*=r; wav[-n:]*=r[::-1]
    p=float(np.max(np.abs(wav))) or 1.0
    return wav*(0.95/p)
def main():
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    dev="cuda" if torch.cuda.is_available() else "cpu"; print("device",dev,flush=True)
    model=ChatterboxMultilingualTTS.from_pretrained(device=dev); sr=model.sr
    man=json.load(open(M/"scan/batch_manifest.json",encoding="utf-8"))
    for k,m in enumerate(man,1):
        line=m["hook"].capitalize().rstrip(".")+"."
        out=VO/f"{m['id']}.wav"
        if out.exists() and out.stat().st_size>5000: print("deja",m['id'],flush=True); continue
        t0=time.time()
        wav=model.generate(line,language_id="en",audio_prompt_path=str(REF),exaggeration=0.5,cfg_weight=0.3,temperature=0.7)
        wav=post(np.asarray(wav.detach().cpu().float().numpy() if hasattr(wav,"detach") else wav).reshape(-1),sr)
        sf.write(out,wav,sr)
        print(f"[{k}/{len(man)}] {m['id']} '{line}' {len(wav)/sr:.1f}s ({time.time()-t0:.1f}s)",flush=True)
    print("DONE vo_hooks",flush=True)
main()
