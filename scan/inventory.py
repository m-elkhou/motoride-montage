import sys
from pathlib import Path as _P
sys.path.insert(0,str(_P(__file__).resolve().parents[1]))
import json, subprocess, time
from pathlib import Path
import mm_paths
mm_paths.use_root()
FP=mm_paths.FFPROBE
ROOTS=dict(mm_paths.CLIP_DIRS)
EXT={".mp4",".mov",".insv",".mkv",".webm",".m4v",".3gp",".insp",".lrv"}
inv=[]; t0=time.time()
for src,root in ROOTS.items():
    if not root.exists(): print("ABSENT",src,root); continue
    for f in root.rglob("*"):
        if not f.is_file() or f.suffix.lower() not in EXT: continue
        rec={"src":src,"path":str(f),"name":f.name,"ext":f.suffix.lower(),"size":f.stat().st_size,"mtime":int(f.stat().st_mtime)}
        try:
            r=subprocess.run([FP,"-v","error","-select_streams","v:0","-show_entries","stream=width,height,r_frame_rate,codec_name:format=duration","-of","json",str(f)],capture_output=True,text=True,timeout=30)
            d=json.loads(r.stdout or "{}"); st=(d.get("streams") or [{}])[0]
            rec.update({"w":st.get("width"),"h":st.get("height"),"codec":st.get("codec_name"),"fps":st.get("r_frame_rate"),"dur":round(float(d.get("format",{}).get("duration",0) or 0),1)})
        except Exception as e: rec["err"]=type(e).__name__
        inv.append(rec)
json.dump(inv,open("scan/inventory.json","w",encoding="utf-8"),ensure_ascii=False)
from collections import Counter
print(f"fichiers: {len(inv)}  ({time.time()-t0:.0f}s)")
for src in ROOTS:
    L=[x for x in inv if x["src"]==src]
    if not L: continue
    dur=sum(x.get("dur",0) or 0 for x in L); gb=sum(x["size"] for x in L)/1e9
    print(f"\n[{src}] {len(L)} fichiers, {gb:.1f} Go, {dur/3600:.1f} h")
    print("  ext:",dict(Counter(x["ext"] for x in L)))
    print("  res:",dict(Counter(f"{x.get('w')}x{x.get('h')}" for x in L).most_common(6)))
    print("  codec:",dict(Counter(x.get("codec") for x in L).most_common(4)))
    ds=[x.get("dur",0) or 0 for x in L]; 
    print(f"  durees: <10s {sum(d<10 for d in ds)} | 10-60s {sum(10<=d<60 for d in ds)} | 1-5min {sum(60<=d<300 for d in ds)} | >5min {sum(d>=300 for d in ds)}")
    sub=Counter(str(Path(x["path"]).parent.relative_to(ROOTS[src])) for x in L); print("  dossiers:",dict(sub.most_common(8)))
