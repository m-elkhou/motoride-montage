import json, subprocess, sys
KEEP={"alpes":[0,2,3,4,6,7,9,11],"crew":[0,1,2,3,4,5,6,7,8,10,11],"golden":[0,1,2,5,7,8,10,11],"winter":list(range(12)),"ferry":[0,1,2,6,7,10],"meet":[0,1,2,4,5,3,10,11]}
RENDER={"alpes":("adrift.mp3","SWISS ALPS ON A KTM",20),"crew":("snow_drift.mp3","POV: YOU FOUND YOUR CREW",18),"golden":("shady.mp3","CHASING THE LAST LIGHT",18),
        "winter":("kick_it.mp3","WINTER CAN'T STOP THE CREW",18),"ferry":("piano_trap_beethoven.mp3","ESCAPE THE CITY",18),"meet":("sacrifices.mp3","COUNT THE BIKES",16)}
PY="C:/workdir/_s2s_cb/venv/Scripts/python.exe"; FF="C:/ffmpeg/bin/ffmpeg"
allclips=set()
for k,idx in KEEP.items():
    segs=json.load(open(f"scan/mont/{k}.json",encoding="utf-8")); keep=[segs[i] for i in idx if i<len(segs)]
    json.dump(keep,open(f"scan/mont/{k}_p.json","w",encoding="utf-8"),ensure_ascii=False,indent=1); allclips|={s["clip"] for s in keep}
    music,hook,target=RENDER[k]
    r=subprocess.run([PY,"-X","utf8","viral_cut.py","--segments",f"scan/mont/{k}_p.json","--music",f"public/{music}","--hook",hook,"--target",str(target),"--out",f"out/m_{k}.mp4"],capture_output=True,text=True,encoding="utf-8",errors="replace")
    print(k,"->",[l for l in r.stdout.splitlines() if l.startswith(("OK","ECHEC","musique"))],flush=True)
    subprocess.run([FF,"-y","-i",f"out/m_{k}.mp4","-vf","fps=1/2,scale=200:-2,tile=5x2","-frames:v","1",f"scan/mont/m_{k}_sheet.jpg"],capture_output=True)
json.dump([{"path":p} for p in sorted(allclips)],open("scan/cand_all.json","w"),indent=0); print("clips utilises:",len(allclips))
