"""Classe chaque clip scanne (2 images) avec CLIP zero-shot -> scan/clip_tags.json."""
import json, subprocess, torch, open_clip, time
from pathlib import Path
from PIL import Image
FF="C:/ffmpeg/bin/ffmpeg"
LABELS={"moto_pov":"first-person view from a motorcycle handlebar while riding on a road",
 "rider":"a motorcycle rider on a motorbike seen from outside","group_ride":"several motorcycles riding together on a road",
 "bike_meet":"many parked motorcycles and bikers gathered","scenery":"a scenic landscape with mountains, lake or sea",
 "city_night":"a city street at night with lights and traffic","people":"a group of people or a family indoors or at an event",
 "indoor":"an indoor room, shop, aquarium or screen","car":"inside a car or a car interior","other":"a random object close-up"}
dev="cuda" if torch.cuda.is_available() else "cpu"
model,_,pre=open_clip.create_model_and_transforms("ViT-B-32",pretrained="laion2b_s34b_b79k",device=dev)
tok=open_clip.get_tokenizer("ViT-B-32")
with torch.no_grad():
    T=model.encode_text(tok(list(LABELS.values())).to(dev)); T=T/T.norm(dim=-1,keepdim=True)
R=[json.loads(l) for l in open("scan/moments.jsonl",encoding="utf-8")]; R=[r for r in R if r.get("ok")]
out={}; tmp=Path("scan/_cls"); tmp.mkdir(exist_ok=True); t0=time.time()
for k,r in enumerate(R):
    d=r.get("dur") or 10; probs=torch.zeros(len(LABELS))
    n=0
    for frac in (0.3,0.7):
        f=tmp/"f.jpg"; subprocess.run([FF,"-y","-hwaccel","cuda","-ss",str(d*frac),"-i",r["path"],"-frames:v","1","-vf","scale=320:-2",str(f)],capture_output=True)
        if not f.exists(): continue
        with torch.no_grad():
            I=model.encode_image(pre(Image.open(f).convert("RGB")).unsqueeze(0).to(dev)); I=I/I.norm(dim=-1,keepdim=True)
            probs+=(100*I@T.T).softmax(-1)[0].cpu(); n+=1
        f.unlink()
    if n: probs/=n
    keys=list(LABELS); top=sorted(zip(keys,probs.tolist()),key=lambda x:-x[1])[:3]
    out[r["path"]]={"top":[(a,round(b,3)) for a,b in top],"moto":round(sum(p for a,p in zip(keys,probs.tolist()) if a in("moto_pov","rider","group_ride","bike_meet")),3)}
    if k%200==0: print(k,len(R),f"{time.time()-t0:.0f}s",flush=True); json.dump(out,open("scan/clip_tags.json","w"),indent=0)
json.dump(out,open("scan/clip_tags.json","w"),indent=0); print("DONE",len(out))
