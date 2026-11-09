"""Scanne chaque clip: mouvement (scene score), nettete (laplacien), pics audio, luminosite -> meilleures fenetres.
Resumable: une ligne JSON par clip dans scan/moments.jsonl."""
import sys
from pathlib import Path as _P
sys.path.insert(0,str(_P(__file__).resolve().parents[1]))
import json, subprocess, re, os, tempfile, time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
import mm_paths
mm_paths.use_root()
FF=mm_paths.FFMPEG
HW=["-hwaccel","cuda"] if os.environ.get("SCAN_HW")=="1" else []
OUT=Path("scan/moments.jsonl")

def scan(rec):
    p=rec["path"]; t0=time.time(); d=Path(tempfile.mkdtemp(prefix="mo_"))
    try:
        # frames gris 2fps 160px + scene score 10fps via une seule passe? deux passes legeres
        r=subprocess.run([FF,*HW,"-i",p,"-vf","scale=160:-2,fps=10,select='gte(scene,0)',metadata=print:file=-","-an","-f","null",os.devnull],capture_output=True,text=True,errors="replace",timeout=600)
        if r.returncode!=0: raise RuntimeError("ffmpeg scene: "+(r.stderr or "")[-100:].replace(chr(10)," "))
        ts,sc=[],[]
        for m in re.finditer(r"pts_time:([\d.]+)[\s\S]*?lavfi\.scene_score=([\d.]+)",r.stdout): ts.append(float(m.group(1))); sc.append(float(m.group(2)))
        ts=np.array(ts); sc=np.array(sc)
        r2=subprocess.run([FF,*HW,"-i",p,"-vf","scale=160:-2,fps=2,format=gray","-an",str(d/"%05d.png")],capture_output=True,text=True,errors="replace",timeout=600)
        if r2.returncode!=0: raise RuntimeError("ffmpeg frames: "+(r2.stderr or "")[-100:].replace(chr(10)," "))
        from PIL import Image
        sh,br=[],[]
        for f in sorted(d.glob("*.png")):
            a=np.asarray(Image.open(f),dtype=np.float32); lap=a[1:-1,1:-1]*4-a[:-2,1:-1]-a[2:,1:-1]-a[1:-1,:-2]-a[1:-1,2:]
            sh.append(float(lap.var())); br.append(float(a.mean()))
        subprocess.run([FF,"-i",p,"-vn","-ac","1","-ar","8000","-f","s16le",str(d/"a.raw")],capture_output=True,timeout=600)
        au=np.fromfile(d/"a.raw",dtype=np.int16).astype(np.float32)/32768 if (d/"a.raw").exists() else np.zeros(1)
        win=4000; n=len(au)//win; rms=np.sqrt((au[:n*win].reshape(n,win)**2).mean(1)) if n else np.zeros(1)
        dur=float(ts[-1]) if len(ts) else 0
        # score par fenetre de 0.5s
        grid=np.arange(0,max(dur-0.5,0.5),0.5); 
        def at(x,tt,v): return np.interp(x,tt,v) if len(v)>1 else np.zeros_like(x)
        mo=at(grid,ts,sc) if len(sc) else np.zeros_like(grid)
        shp=at(grid,np.arange(len(sh))/2.0,np.array(sh)) if sh else np.zeros_like(grid)
        brg=at(grid,np.arange(len(br))/2.0,np.array(br)) if br else np.zeros_like(grid)
        ar=at(grid,np.arange(len(rms))*0.5,rms) if len(rms)>1 else np.zeros_like(grid)
        def nz(v): q=np.percentile(v,90) if len(v) else 1; return np.minimum(v/(q+1e-9),1.0)
        score=0.45*nz(mo)+0.35*nz(shp)+0.2*nz(ar)
        score[brg<25]*=0.3  # trop sombre
        # top fenetres de 2s et 4s (non chevauchantes)
        def tops(L,k=3):
            w=int(L/0.5); out=[]; s=score.copy()
            for _ in range(k):
                if len(s)<w: break
                cs=np.convolve(s,np.ones(w),"valid")/w; i=int(cs.argmax())
                if cs[i]<=0: break
                out.append({"t":round(float(grid[i]),1),"len":L,"score":round(float(cs[i]),3)}); s[max(0,i-w):i+w]=0
            return out
        return {**rec,"ok":True,"dur_scanned":round(dur,1),"mean_score":round(float(score.mean()),3),"max_score":round(float(score.max()) if len(score) else 0,3),
                "mean_sharp":round(float(np.mean(sh)) if sh else 0,1),"mean_bright":round(float(np.mean(br)) if br else 0,1),"audio_peak":round(float(rms.max()) if len(rms) else 0,3),
                "top2":tops(2.0),"top4":tops(4.0),"secs":round(time.time()-t0,1)}
    except Exception as e:
        return {**rec,"ok":False,"err":f"{type(e).__name__}: {e}"[:120]}
    finally:
        for f in d.glob("*"): 
            try: f.unlink()
            except OSError: pass
        try: d.rmdir()
        except OSError: pass

if __name__=="__main__":
    inv=json.load(open("scan/inventory.json",encoding="utf-8"))
    todo=[x for x in inv if x["ext"] in(".mp4",".mov") and (x.get("dur") or 0)>=3 and x["src"]!="insta360" or (x["src"]=="insta360" and x["ext"]==".mp4" and (x.get("w") or 0)!=2880 and (x.get("dur") or 0)>=3)]
    done=set()
    if OUT.exists():
        for l in open(OUT,encoding="utf-8"):
            try: done.add(json.loads(l)["path"])
            except (ValueError, KeyError): pass
    todo=[x for x in todo if x["path"] not in done]
    limit=int(sys.argv[1]) if len(sys.argv)>1 else len(todo)
    todo=todo[:limit]
    print(f"a scanner: {len(todo)} (deja faits {len(done)})",flush=True)
    with ProcessPoolExecutor(max_workers=int(os.environ.get("SCAN_WORKERS","3"))) as ex, open(OUT,"a",encoding="utf-8") as fo:
        futs=[ex.submit(scan,x) for x in todo]; k=0
        for f in as_completed(futs):
            r=f.result(); fo.write(json.dumps(r,ensure_ascii=False)+"\n"); fo.flush(); k+=1
            if k%25==0: print(f"{k}/{len(todo)} {time.strftime('%H:%M:%S')}",flush=True)
    print("DONE",flush=True)
