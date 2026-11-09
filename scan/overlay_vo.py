# -*- coding: utf-8 -*-
"""Mixe la voix courte (vo/<id>.mp3) LEGER par-dessus le phonk, debut a 0.4s.
Remplace out/<id>.mp4. Video copiee (pas de re-encodage), audio re-mux."""
import json, subprocess, os, shutil, tempfile
FF="C:/ffmpeg/bin/ffmpeg"
man=json.load(open("scan/batch_manifest.json",encoding="utf-8"))
ok=[]; ko=[]
for m in man:
    vid=f"out/{m['id']}.mp4"; vo=f"vo/{m['id']}.mp3"
    if not (os.path.exists(vid) and os.path.exists(vo)):
        ko.append(m['id']+"(manquant)"); continue
    if os.path.getsize(vid)<200000:
        ko.append(m['id']+"(video invalide)"); continue
    tmp=tempfile.mktemp(suffix=".mp4",dir="out")
    # voix retardee 0.4s, un peu boostee; musique pleine (normalize=0) -> voix legere au-dessus
    fc="[1:a]adelay=400|400,volume=1.35[v];[0:a][v]amix=inputs=2:duration=first:normalize=0[a]"
    r=subprocess.run([FF,"-y","-i",vid,"-i",vo,"-filter_complex",fc,
                      "-map","0:v","-map","[a]","-c:v","copy","-c:a","aac","-b:a","192k",
                      "-movflags","+faststart",tmp],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=120)
    if os.path.exists(tmp) and os.path.getsize(tmp)>200000:
        shutil.move(tmp,vid); ok.append(m['id'])
    else:
        ko.append(m['id']); 
        try: os.remove(tmp)
        except: pass
print(f"VOIX MIXEE: {len(ok)} OK, {len(ko)} KO {ko}",flush=True)
