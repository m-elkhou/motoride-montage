"""Montage 'style viral' : coupes sur le beat, passages a forte energie visuelle, slow-mo sur le drop,
grade, hook texte, musique forte, SANS voix. Sortie 1080x1920 30fps.
Usage: python viral_cut.py --clips a.mp4 b.mp4 --music public/future.mp3 --hook "PARIS AT 3 A.M." --target 18 --out out/x.mp4"""
import argparse, json, subprocess, re, tempfile, os
from pathlib import Path
import numpy as np, librosa
FF="C:/ffmpeg/bin/ffmpeg"; FONT="C\:/Windows/Fonts/arialbd.ttf"; FPS=30
def run(cmd): return subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8",errors="replace")

def music_grid(path, target):
    y,sr=librosa.load(path,sr=22050,mono=True,duration=90)
    tempo,beats=librosa.beat.beat_track(y=y,sr=sr,units="time")
    tempo=float(np.atleast_1d(tempo)[0]); beats=list(beats)
    rms=librosa.feature.rms(y=y,hop_length=512)[0]; t_rms=librosa.frames_to_time(np.arange(len(rms)),sr=sr,hop_length=512)
    def energy(t0,t1): m=(t_rms>=t0)&(t_rms<t1); return float(rms[m].mean()) if m.any() else 0
    best=(0,beats[4] if len(beats)>12 else 0)
    for k in range(4,len(beats)-8):
        e=energy(beats[k],beats[k+8])
        if e>best[0]: best=(e,beats[k])
    drop=best[1]; offset=max(0.0,drop-0.35*target)
    grid=[b-offset for b in beats if 0<=b-offset<=target+0.5]
    return tempo,offset,drop-offset,grid

def clip_energy(path):
    r=run([FF,"-i",path,"-vf","scale=160:-2,fps=10,select='gte(scene,0)',metadata=print:file=-","-an","-f","null","NUL"])
    ts,sc=[],[]
    for m in re.finditer(r"pts_time:([\d.]+)[\s\S]*?lavfi\.scene_score=([\d.]+)",r.stdout):
        ts.append(float(m.group(1))); sc.append(float(m.group(2)))
    ts=np.array(ts); sc=np.array(sc)
    if len(sc): sc=np.minimum(sc,np.percentile(sc,85))/(np.percentile(sc,85)+1e-9)
    # nettete (variance du laplacien) a 2 fps, pour eviter flou/secousses/blouson
    d=Path(tempfile.mkdtemp(prefix="sh_")); run([FF,"-i",path,"-vf","scale=240:-2,fps=2,format=gray","-an",str(d/"%04d.png")])
    from PIL import Image
    sh_t,sh=[],[]
    for k,f in enumerate(sorted(d.glob("*.png"))):
        a=np.asarray(Image.open(f),dtype=np.float32); lap=a[1:-1,1:-1]*4-a[:-2,1:-1]-a[2:,1:-1]-a[1:-1,:-2]-a[1:-1,2:]
        sh_t.append(k/2.0); sh.append(float(lap.var()))
    sh=np.array(sh); sh=sh/(np.percentile(sh,90)+1e-9) if len(sh) else sh
    shi=np.interp(ts,sh_t,sh) if len(sh) else np.ones_like(ts)
    return ts, 0.6*sc+0.4*np.minimum(shi,1.0)

def best_window(ts,sc,L,used,margin=0.5):
    best=(-1,None)
    for i in range(len(ts)):
        s=ts[i]; e=s+L
        if e>ts[-1]: break
        if any(not(e+margin<=u0 or s-margin>=u1) for u0,u1 in used): continue
        m=(ts>=s)&(ts<e); en=sc[m].mean() if m.any() else 0
        if en>best[0]: best=(en,s)
    return best

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--clips",nargs="*",default=[]); ap.add_argument("--music",required=True)
    ap.add_argument("--hook",default=""); ap.add_argument("--outro",default=""); ap.add_argument("--target",type=float,default=18); ap.add_argument("--out",required=True)
    ap.add_argument("--segments",default="",help="json: [{clip,start,len,score}] moments pre-selectionnes (ordre libre)")
    ap.add_argument("--grade",default="eq=contrast=1.08:saturation=1.25:brightness=0.01,vignette=PI/5")
    a=ap.parse_args()
    tempo,offset,drop,grid=music_grid(a.music,a.target)
    spb=60/tempo; mult=2 if tempo>140 else 1
    print(f"musique: {tempo:.0f} BPM, offset {offset:.2f}s, drop a {drop:.2f}s, {len(grid)} beats dans {a.target}s")
    if a.segments:
        M=json.load(open(a.segments,encoding="utf-8")); a.clips=list(dict.fromkeys(m["clip"] for m in M))
        # energie synthetique: 1 sur les fenetres de moments, 0 ailleurs (+ score)
        E={}
        for c in a.clips:
            ts=np.arange(0,max(m["start"]+m["len"] for m in M if m["clip"]==c)+2,0.1); sc=np.zeros_like(ts)
            for m in M:
                if m["clip"]==c: sc[(ts>=m["start"])&(ts<m["start"]+m["len"])]=max(float(m.get("score",1)),0.05)
            E[c]=(ts,sc)
    else:
        E={c:clip_energy(c) for c in a.clips}
    used={c:[] for c in a.clips}
    # plan: phrases avant le drop en 2 beats, hero 4 beats (source 2 beats x0.5), puis 4 beats
    segs=[]; t=0.0; k=0; ci=0
    drop_beat=min(range(len(grid)),key=lambda i:abs(grid[i]-drop)) if grid else 0
    i=0; hero_done=False
    while t<a.target-0.3 and i<len(grid)-1:
        if (not hero_done) and i>=drop_beat: nb=4*mult; rate=2.0; hero_done=True
        elif i<drop_beat: nb=2*mult; rate=1.0
        else: nb=4*mult; rate=1.0
        j=min(i+nb,len(grid)-1); dur=grid[j]-grid[i]
        if dur<=0.2: i+=1; continue
        src_len=dur/rate
        if rate>1:  # hero = fenetre la plus energique globale
            cand=[(best_window(*E[c],src_len,used[c]),c) for c in a.clips]
            (en,s),c=max(cand,key=lambda x:x[0][0])
        else:
            c=a.clips[ci%len(a.clips)]; ci+=1
            en,s=best_window(*E[c],src_len,used[c])
            if s is None:
                c=max(a.clips,key=lambda cc:best_window(*E[cc],src_len,used[cc])[0]); en,s=best_window(*E[c],src_len,used[c])
        if s is None: break
        used[c].append((s,s+src_len)); segs.append({"clip":c,"start":round(s,2),"src_len":round(src_len,2),"rate":rate,"dur":round(dur,2)})
        t+=dur; i=j
    print("plan:",json.dumps(segs,ensure_ascii=False))
    tmp=Path(tempfile.mkdtemp(prefix="vc_")); lst=[]
    for k,s in enumerate(segs):
        o=tmp/f"s{k:02d}.mp4"
        vf=f"setpts={s['rate']}*PTS,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps={FPS}"
        run([FF,"-y","-ss",str(s["start"]),"-i",s["clip"],"-t",str(s["src_len"]),"-vf",vf,"-an","-c:v","libx264","-preset","veryfast","-crf","18","-pix_fmt","yuv420p",str(o)])
        if o.exists(): lst.append(o)
    (tmp/"list.txt").write_text("".join(f"file '{p.as_posix()}'\n" for p in lst),encoding="utf-8")
    cat=tmp/"cat.mp4"; run([FF,"-y","-f","concat","-safe","0","-i",str(tmp/"list.txt"),"-c","copy",str(cat)])
    hook=a.hook.strip(); txt=""
    if hook:
        w=hook.split(); lines=[hook]
        if len(hook)>13 and len(w)>1:
            best=min(range(1,len(w)),key=lambda k:abs(len(" ".join(w[:k]))-len(" ".join(w[k:]))))
            lines=[" ".join(w[:best])," ".join(w[best:])]
        fs=int(min(92, 1500/max(len(l) for l in lines)))
        tf=Path(tempfile.mkdtemp(prefix="hk_"))/"hook.txt"; tf.write_text(chr(10).join(lines),encoding="utf-8")
        tfp=tf.as_posix().replace(":","\:")
        txt=f",drawtext=fontfile='{FONT}':textfile='{tfp}':x=(w-text_w)/2:y=150:fontsize={fs}:line_spacing=10:fontcolor=white:borderw=6:bordercolor=black:box=1:boxcolor=black@0.35:boxborderw=22:enable='between(t,0.15,3.2)'" 
    outro=a.outro.strip()
    if outro:
        w2=outro.split(); ol=[outro]
        if len(outro)>15 and len(w2)>1:
            b=min(range(1,len(w2)),key=lambda k:abs(len(" ".join(w2[:k]))-len(" ".join(w2[k:]))))
            ol=[" ".join(w2[:b])," ".join(w2[b:])]
        ofs=int(min(80,1400/max(len(l) for l in ol)))
        otf=Path(tempfile.mkdtemp(prefix="ou_"))/"outro.txt"; otf.write_text(chr(10).join(ol),encoding="utf-8")
        otfp=otf.as_posix().replace(":","\:")
        t0=max(0.0,a.target-3.0); t1=a.target-0.25
        txt=txt+f",drawtext=fontfile='{FONT}':textfile='{otfp}':x=(w-text_w)/2:y=h*0.60:fontsize={ofs}:line_spacing=10:fontcolor=white:borderw=6:bordercolor=black:box=1:boxcolor=black@0.35:boxborderw=22:enable='between(t,{t0:.2f},{t1:.2f})'"
    fc=(f"[0:v]{a.grade}{txt},format=yuv420p[v];"
        f"[1:a]atrim=start={offset:.3f},asetpts=PTS-STARTPTS,atrim=0:{a.target},afade=t=in:d=0.3,afade=t=out:st={a.target-0.8:.2f}:d=0.8,loudnorm=I=-14:TP=-1:LRA=9[a]")
    r=run([FF,"-y","-i",str(cat),"-i",a.music,"-filter_complex",fc,"-map","[v]","-map","[a]","-t",str(a.target),"-c:v","libx264","-preset","fast","-crf","20","-c:a","aac","-b:a","192k","-movflags","+faststart",a.out])
    print("OK ->",a.out if Path(a.out).exists() else "ECHEC "+r.stderr[-400:])
main()
