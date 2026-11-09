# -*- coding: utf-8 -*-
"""Genere N montages 'texte motivant' varies par theme, clips uniques (zero recoupement).
Ecrit: scan/mont/g_<id>.json (segments) + scan/batch_manifest.json (hook/outro/musique/titre/publishAt)."""
import json, os, re
from collections import defaultdict
from datetime import datetime, timezone, timedelta

R=[json.loads(l) for l in open("scan/moments.jsonl",encoding="utf-8")]
R=[r for r in R if r.get("ok")]
TAGS=json.load(open("scan/clip_tags.json",encoding="utf-8"))
def cat(path): return TAGS.get(path,{}).get("top",[["other",0]])[0][0]
def moto(path): return TAGS.get(path,{}).get("moto",0)

# clips deja utilises (9 montages existants) -> ne jamais reutiliser
used=set()
for k in ["mountain","paris","night","crew_p","winter_p","meet_p","alpes_p","golden_p","escape_p"]:
    p=f"scan/mont/{k}.json"
    if os.path.exists(p):
        for s in json.load(open(p,encoding="utf-8")): used.add(os.path.basename(s["clip"]))

EXCL_DATE={"20230822","20240124","20260801","20240819","20231210"}  # perso
MOTO_CATS={"moto_pov","rider","group_ride","bike_meet"}

# segments candidats par categorie-theme
def collect(cats_wanted):
    segs=[]
    for r in R:
        b=r["name"]
        if b in used: continue
        if any(b.startswith(e) for e in EXCL_DATE): continue
        if moto(r["path"])<0.6: continue
        c=cat(r["path"])
        if c not in cats_wanted: continue
        if r.get("mean_bright",0)<32: continue
        for m in r.get("top4",[])[:2]:
            if m["score"]>=0.42:
                segs.append({"clip":r["path"],"start":m["t"],"len":4.0,"score":m["score"],"name":b,"cat":c})
    segs.sort(key=lambda s:-s["score"])
    return segs

THEMES={
 "pov":  (["moto_pov"], 12),
 "rider":(["rider"], 10),
 "crew": (["group_ride","bike_meet"], 6),
}
MUSIC=["ph_drift.mp3","ph_aggr.mp3","ph_monda.mp3","ph_vaitsez.mp3","ph_zephira.mp3","ph_aura.mp3","ph_arp1.mp3","ph_hard.mp3","ph_arp2.mp3"]
HOOKS={
 "pov":["THE ROAD IS CALLING","RIDE YOUR OWN PACE","CLEAR MIND OPEN ROAD","NO BAD DAYS ON TWO WHEELS","THE ROAD DOESN'T JUDGE","FREEDOM HAS AN ENGINE","ONE LIFE RIDE IT","BEST THERAPY HAS TWO WHEELS","CHASE THE HORIZON","LEAVE THE STRESS BEHIND","THE ROAD SETS YOU FREE","JUST ME AND THE ROAD"],
 "rider":["BORN TO RIDE","TWO WHEELS ONE SOUL","LIVE TO RIDE","FEAR LESS RIDE MORE","RIDE HARD STAY HUMBLE","NOT ALL WHO WANDER ARE LOST","THE RIDE IS THE REWARD","RIDE LIKE YOU MEAN IT","EYES ON THE HORIZON","MADE FOR THE OPEN ROAD"],
 "crew":["FIND YOUR PEOPLE","WE RIDE AS ONE","BETTER TOGETHER","THE CREW IS FAMILY","RIDE WITH YOUR PACK","STRONGER TOGETHER"],
}
OUTROS={
 "pov":["KEEP RIDING","NEVER STOP","RIDE OR REGRET","THE JOURNEY IS THE POINT","STAY ON TWO WHEELS"],
 "rider":["RIDE ON","STAY HUNGRY","NO LIMITS","FULL THROTTLE","RESPECT THE RIDE"],
 "crew":["RIDE TOGETHER","BROTHERHOOD ON WHEELS","YOUR PACK AWAITS"],
}
TITLES={
 "pov":["La route efface tout 🏍️","Rouler, c'est respirer 🏍️💨","Juste moi et la route 🏍️","La meilleure thérapie a deux roues 🏍️","Zéro stress au guidon 🏍️🔥","La route m'appelle 🏍️","Vivre à fond, une seule vie 🏍️","Au guidon, rien d'autre ne compte 🏍️","Chasser l'horizon 🏍️🌅","Liberté, ça se conduit 🏍️","Rouler pour oublier 🏍️","L'évasion au guidon 🏍️💨"],
 "rider":["Né pour rouler 🏍️","Deux roues, une âme 🏍️🖤","Vivre pour rouler 🏍️🔥","Moins de peur, plus de route 🏍️","Fait pour la route 🏍️","La route est la récompense 🏍️🌅","Rouler avec le cœur 🏍️","Les yeux sur l'horizon 🏍️","Rouler, encore et encore 🏍️","L'esprit motard 🏍️🔥"],
 "crew":["Trouve ton crew 🏍️🤝","On roule en bande 🏍️🔥","Mieux à plusieurs 🏍️🤝","Le crew, c'est la famille 🏍️","Rouler avec sa meute 🏍️","Plus forts ensemble 🏍️🤝"],
}
TAGSET={
 "pov":["moto","motovlog","pov","ride","roadtrip","bikelife","motorcycle","moto pov","balade","liberte"],
 "rider":["moto","motovlog","rider","ride","bikelife","motorcycle","biker","roadtrip","moto life","passion"],
 "crew":["moto","motovlog","crew","groupride","bikelife","motorcycle","ride","balade","motards","brotherhood"],
}

manifest=[]
gi=0
# publishAt: 2/jour a partir du 12/11 17Z (apres la file actuelle qui finit escape 12/11 10Z)
start=datetime(2026,11,12,17,0,0,tzinfo=timezone.utc)
slots=[]
d=start
for _ in range(60):
    slots.append(d)
    # alterner 17Z puis +1j 10Z
    if d.hour==17: d=(d+timedelta(days=1)).replace(hour=10)
    else: d=d.replace(hour=17)

for theme,(cats_w,n) in THEMES.items():
    pool=collect(cats_w)
    hi=oi=ti=0
    for _ in range(n):
        # prendre 8 segments, max 2 par clip, clips pas deja globalement utilises
        picked=[]; cnt=defaultdict(int)
        for s in pool:
            if s["name"] in used: continue
            if cnt[s["name"]]>=2: continue
            cnt[s["name"]]+=1; picked.append(s)
            if len(picked)>=8: break
        uniq={s["name"] for s in picked}
        if len(uniq)<4:  # pas assez de matiere -> stop ce theme
            break
        for s in picked: used.add(s["name"])
        mid=f"g_{theme}_{gi:02d}"
        json.dump(picked,open(f"scan/mont/{mid}.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
        manifest.append({
            "id":mid,"theme":theme,
            "music":MUSIC[gi%len(MUSIC)],
            "hook":HOOKS[theme][hi%len(HOOKS[theme])],
            "outro":OUTROS[theme][oi%len(OUTROS[theme])],
            "title":TITLES[theme][ti%len(TITLES[theme])]+" #Shorts",
            "tags":TAGSET[theme],
            "target":18,
            "publishAt":slots[gi].strftime("%Y-%m-%dT%H:%M:%SZ"),
            "nseg":len(picked),"nclips":len(uniq),
        })
        gi+=1; hi+=1; oi+=1; ti+=1

json.dump(manifest,open("scan/batch_manifest.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("montages generes:",len(manifest))
for m in manifest: print(f"  {m['id']:14s} {m['nclips']}clips mus={m['music']:14s} '{m['hook']}' -> '{m['outro']}' | {m['publishAt']}")
