"""Assemble des listes de moments par theme -> segments json + planche de controle (1 image par segment)."""
import json, re, subprocess, sys
from pathlib import Path
FF="C:/ffmpeg/bin/ffmpeg"
R=[json.loads(l) for l in open("scan/moments.jsonl",encoding="utf-8")]; R=[r for r in R if r.get("ok")]
for r in R:
    m=re.search(r"(20\d{6})",r["name"]); r["date"]=m.group(1) if m else "?"
EXCL={"20230822","20240124","20260801","20240819","20231210","20250504_23"}  # perso / hors moto
TAGS=json.load(open("scan/clip_tags.json",encoding="utf-8"))
SPECS=json.load(open("scan/montage_specs.json",encoding="utf-8"))
Path("scan/mont").mkdir(exist_ok=True)
for sp in SPECS:
    pool=[r for r in R if any(r["name"].startswith(p) or r["date"].startswith(p) for p in sp["match"]) and not any(r["name"].startswith(e) for e in EXCL) and r["mean_bright"]>=sp.get("min_bright",35) and TAGS.get(r["path"],{}).get("moto",0)>=sp.get("min_moto",0.5) and TAGS.get(r["path"],{}).get("top",[["",0]])[0][0] not in ("people","indoor","car")]
    segs=[]
    for r in pool:
        for m in r["top4"][:2]:
            if m["score"]>=sp.get("min_score",0.35): segs.append({"clip":r["path"],"start":m["t"],"len":4.0,"score":m["score"],"name":r["name"]})
    segs.sort(key=lambda s:-s["score"])
    # max 2 par clip, max N
    cnt={}; keep=[]
    for s in segs:
        if cnt.get(s["clip"],0)>=2: continue
        cnt[s["clip"]]=cnt.get(s["clip"],0)+1; keep.append(s)
        if len(keep)>=sp.get("max",12): break
    json.dump(keep,open(f"scan/mont/{sp['id']}.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
    d=Path(f"scan/mont/{sp['id']}_f"); d.mkdir(exist_ok=True)
    for f in d.glob("*.jpg"): f.unlink()
    for i,s in enumerate(keep):
        subprocess.run([FF,"-y","-hwaccel","cuda","-ss",str(s["start"]+1.5),"-i",s["clip"],"-frames:v","1","-vf",f"scale=150:-2,pad=150:267:(ow-iw)/2:(oh-ih)/2:black,drawtext=fontfile='C\\:/Windows/Fonts/arialbd.ttf':text='{i}':x=3:y=3:fontsize=18:fontcolor=white:box=1:boxcolor=black@0.6",str(d/f"{i:02d}.jpg")],capture_output=True)
    n=len(list(d.glob("*.jpg")))
    if n: subprocess.run([FF,"-y","-i",str(d/"%02d.jpg"),"-vf",f"tile={min(n,12)}x1:nb_frames={n}","-frames:v","1",f"scan/mont/{sp['id']}_sheet.jpg"],capture_output=True)
    print(f"{sp['id']:10s} pool={len(pool):3d} clips | segments={len(keep):2d} | {sp['hook']}")
