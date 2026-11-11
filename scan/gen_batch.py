# -*- coding: utf-8 -*-
"""Genere N montages 'texte motivant' varies par theme, clips uniques (zero recoupement).
Ecrit: scan/mont/g_<id>.json (segments) + scan/batch_manifest.json (hook/outro/musique/titre/publishAt)."""
import sys
from pathlib import Path as _P
sys.path.insert(0,str(_P(__file__).resolve().parents[1]))
import json, os
from pathlib import Path as Path_
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import mm_paths, mm_config, mm_privacy
mm_paths.use_root()
CFG=mm_config.load()   # scan/gen_config.json (dates exclues, calendrier, textes) : voir mm_config.py

R=[json.loads(l) for l in open("scan/moments.jsonl",encoding="utf-8")]
R=[r for r in R if r.get("ok")]
TAGS=json.load(open("scan/clip_tags.json",encoding="utf-8"))
def cat(path): return TAGS.get(path,{}).get("top",[["other",0]])[0][0]
def moto(path): return TAGS.get(path,{}).get("moto",0)

# clips deja utilises (9 montages existants) -> ne jamais reutiliser
used=set()
for k in CFG["used_montages"]:
    p=f"scan/mont/{k}.json"
    if os.path.exists(p):
        for s in json.load(open(p,encoding="utf-8")): used.add(os.path.basename(s["clip"]))

EXCL_DATE=set(CFG["exclude_dates"])  # footage perso : scan/gen_config.json
MOTO_CATS={"moto_pov","rider","group_ride","bike_meet"}

# ---- porte ANONYMAT : on ne pioche QUE dans les intervalles verifies de scan/privacy_pool.json
POOL_FILE = "scan/privacy_pool.json"
if not os.path.exists(POOL_FILE):
    sys.exit("scan/privacy_pool.json absent : lancez d'abord scan/privacy_scan.py (porte anonymat)")
POOL = json.load(open(POOL_FILE, encoding="utf-8"))
BLOCK = json.load(open("scan/privacy_blocklist.json", encoding="utf-8")) if os.path.exists("scan/privacy_blocklist.json") else {}
# rushes deplaces dans PRIVATE/row/ (scan/raw_audit.py) : jamais planifies
MOVED = set(json.load(open("PRIVATE/row/_moved.json", encoding="utf-8"))) if os.path.exists("PRIVATE/row/_moved.json") else set()
# COPIES identiques d'un meme rushe (inbox + camera_roll : meme nom, meme taille) : une seule est planifiee, sinon le meme
# plan passe deux fois dans le montage ; les plages bloquees (et le deplacement dans PRIVATE/row/) de TOUTES les copies comptent
COPIES = defaultdict(list)
for _r in R: COPIES[(_r["name"], _r.get("size"))].append(_r["path"])
GROUP_OF = {_p: _ps for _ps in COPIES.values() for _p in _ps}
def copies_of(path): return GROUP_OF.get(path, [path])
def representative(path):
    ps = copies_of(path)
    if any(q in MOVED for q in ps): return None           # une copie isolee dans PRIVATE/row/ : tout le groupe l'est
    return next((q for q in ps if q in POOL), ps[0])
def blocks_for(path):
    return [b for q in copies_of(path) for b in BLOCK.get(q, [])]
# rushes SUPPRIMES definitivement (journal PRIVATE/_suppressions_*.json) : jamais planifies
DELETED = set()
for _f in sorted(Path_("PRIVATE").glob("_suppressions_*.json")) if Path_("PRIVATE").exists() else []:
    for _e in json.load(open(_f, encoding="utf-8")).get("supprimes", []):
        DELETED.update((_e.get("origine"), _e.get("fichier")))
# sources en lettre-boite (bandes noires dans l'image : scan/letterbox_scan.py) : jamais planifiees
QUALITY = json.load(open("scan/clip_quality.json", encoding="utf-8")) if os.path.exists("scan/clip_quality.json") else {}
EDGE = 0.15                                   # marge de securite aux deux bouts (la grille d'energie de viral_cut est a 0,1 s)
MIN_LEN = float(CFG.get("min_interval", 2.6))  # un intervalle plus court ne permet pas de decouper proprement
PREFIX = CFG.get("id_prefix", "safe")         # nouveaux identifiants : le journal d'envoi ne confond pas avec les anciens montages
SEGS = int(CFG.get("segments_per_montage", 12))
MIN_CLIPS = int(CFG.get("min_clips", 5))
MIN_SCORE = float(CFG.get("min_score", 0.42))   # score mini de la fenetre (le pool a ete analyse des 0,35)
LANE_CLIPS = int(CFG.get("clips_per_montage", 5))     # clips distincts mini par voie (borne le nombre de voies)
LANE_SEC = float(CFG.get("lane_seconds", 45))        # secondes verifiees (hors liste de blocage) reservees a chaque voie
MIN_SEC = float(CFG.get("min_seconds", 28))          # secondes verifiees mini d'un montage une fois la liste de blocage retiree
SKIP_IDS = set(CFG.get("skip_ids", []))   # clips reserves a chaque montage (voie)

# segments candidats par categorie-theme
def collect(cats_wanted, block=True):
    segs = []
    for r in R:
        name = r["name"]
        if name in used: continue
        if any(name.startswith(e) for e in EXCL_DATE): continue
        if moto(r["path"]) < 0.6: continue
        c = cat(r["path"])
        if c not in cats_wanted: continue
        if r.get("mean_bright", 0) < 32: continue
        if r["path"] in MOVED: continue       # rushe isole dans PRIVATE/row/
        if r["path"] in DELETED: continue     # rushe supprime definitivement (PRIVATE/_suppressions_*.json)
        if representative(r["path"]) != r["path"]: continue   # copie identique d'un autre rushe : une seule est utilisee
        if QUALITY.get(r["path"], {}).get("letterbox"): continue   # bandes noires dans la source
        entry = POOL.get(r["path"])
        if not entry: continue                # clip non analyse par la porte anonymat : INTERDIT
        for w in entry["windows"]:
            for a0, b0 in w["clean"]:
                for a1, b1 in mm_privacy.subtract_blocks(a0 + EDGE, b0 - EDGE, blocks_for(r["path"]) if block else []):
                    if b1 - a1 < MIN_LEN: continue
                    sc = max((m["score"] for m in r.get("top4", []) if m["t"] < b1 and m["t"] + m["len"] > a1), default=0)
                    if sc >= MIN_SCORE:
                        segs.append({"clip": r["path"], "start": round(a1, 2), "len": round(b1 - a1, 2), "score": sc, "name": name, "cat": c})
    segs.sort(key=lambda s: -s["score"])
    return segs

THEMES={
 "pov":  (["moto_pov"], 12),
 "rider":(["rider"], 10),
}
MUSIC=["ph_drift.mp3","ph_aggr.mp3","ph_monda.mp3","ph_vaitsez.mp3","ph_zephira.mp3","ph_aura.mp3","ph_arp1.mp3","ph_hard.mp3","ph_arp2.mp3"]
# accroches inspirees du top 100 des Shorts moto de 2026 (docs/viral-dna.md) : texte d'abord (question, POV, tension),
# appel au commentaire a la fin ; 3 a 6 mots (la voix les dit) ; pas d'emoji (la police de drawtext n'en a pas)
HOOKS={
 "pov":["POV: NO TRAFFIC NO PLAN","WAIT FOR THE TURN","THIS ROAD HITS DIFFERENT","WHICH ROAD WOULD YOU TAKE","POV: YOU LEFT THE CITY","TURN THE VOLUME UP","ONE MORE ROAD","THIS IS WHY WE RIDE","SUNDAY RIDES HIT DIFFERENT","NO SPEED LIMIT ON THIS FEELING","ROAD FIRST EVERYTHING ELSE LATER","THE ROAD IS CALLING"],
 "rider":["ONLY RIDERS GET THIS","WHICH BIKE WOULD YOU PICK","THE BEST SEAT IN THE WORLD","SAVE THIS FOR YOUR NEXT RIDE","BORN TO RIDE","TWO WHEELS ONE SOUL","THIS IS FREEDOM","WAIT FOR IT","RIDE LIKE NOBODY IS WATCHING","MADE FOR THE OPEN ROAD"],
}
OUTROS={
 "pov":["COMMENT BIKE IF YOU RIDE","FOLLOW FOR MORE ROADS","SEND THIS TO YOUR RIDING BUDDY","WHICH ONE IS YOURS","SAVE THIS FOR YOUR NEXT RIDE","KEEP RIDING"],
 "rider":["COMMENT BIKE IF YOU RIDE","SEND THIS TO A RIDER","FOLLOW FOR MORE","WHICH ONE IS YOURS","SAVE THIS FOR LATER","RIDE ON"],
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

# surcharges optionnelles des textes/listes depuis scan/gen_config.json
for _n,_d in (("hooks",HOOKS),("outros",OUTROS),("titles",TITLES),("tagset",TAGSET)): _d.update(CFG.get(_n,{}))
MUSIC=CFG.get("music",MUSIC)
if "themes" in CFG: THEMES={k:(v[0],v[1]) for k,v in CFG["themes"].items()}

manifest=[]
gi=0
# publishAt : 2 creneaux/jour (premier creneau puis le lendemain le second), depuis schedule_start
H0,H1=CFG["slot_hours"]
if CFG["schedule_start"]: start=datetime.fromisoformat(CFG["schedule_start"].replace("Z","+00:00"))
else: start=(datetime.now(timezone.utc)+timedelta(days=1)).replace(hour=H0,minute=0,second=0,microsecond=0)
slots=[]
d=start
for _ in range(60):
    slots.append(d)
    if d.hour==H0: d=(d+timedelta(days=1)).replace(hour=H1)
    else: d=d.replace(hour=H0)

def write_if_changed(path, obj):
    """N'ecrit que si le contenu change : la date du fichier n'avance pas, le rendu existant reste valide."""
    text = json.dumps(obj, ensure_ascii=False, indent=1)
    if os.path.exists(path) and open(path, encoding="utf-8").read() == text:
        return
    open(path, "w", encoding="utf-8").write(text)

for theme,(cats_w,n) in THEMES.items():
    # VOIES : chaque clip appartient a UN montage (rang du clip, calcule SANS la liste de blocage, modulo le nombre de
    # montages). Retirer un segment refuse a l'audit ne change que SON montage : pas de cascade sur les autres.
    order=[]; secs=defaultdict(float); kept=defaultdict(int)
    for sg in collect(cats_w, block=False):
        if sg["name"] not in order: order.append(sg["name"])
        if kept[sg["name"]]<2: kept[sg["name"]]+=1; secs[sg["name"]]+=sg["len"]   # au plus 2 segments par clip et par montage
    # nombre de voies : borne par la demande, par le nombre de clips et par les SECONDES verifiees disponibles ; chaque clip
    # va a la voie la moins chargee (glouton, ordre des scores) : les voies sont equilibrees en secondes, pas en nombre de clips
    N=min(n, len(order)//LANE_CLIPS, int(sum(secs.values())//LANE_SEC))
    load=[0.0]*N; lane={}
    for name in order:
        k=min(range(N), key=lambda j:(load[j], j)); lane[name]=k; load[k]+=secs[name]
    pool=collect(cats_w)
    for k in range(N):
        mid=f"{PREFIX}_{theme}_{gi:02d}"
        slot=gi; gi+=1          # l'identifiant, le calendrier et la musique ne bougent jamais, meme si une voie manque de matiere
        if mid in SKIP_IDS:     # montage abandonne apres des echecs d'audit repetes (scan/gen_config.json : "skip_ids")
            print(f"  {mid}: abandonne (skip_ids)")
            continue
        picked=[]; cnt=defaultdict(int)
        for sg in pool:
            if lane.get(sg["name"])!=k or cnt[sg["name"]]>=2: continue
            cnt[sg["name"]]+=1; picked.append(sg)
            if len(picked)>=SEGS: break
        uniq={sg["name"] for sg in picked}
        total=sum(sg["len"] for sg in picked)
        if len(uniq)<MIN_CLIPS or total<MIN_SEC:
            print(f"  {mid}: pas assez de matiere VERIFIEE ({len(picked)} segments, {len(uniq)} clips, {total:.0f} s) : montage ignore")
            continue
        write_if_changed(f"scan/mont/{mid}.json", picked)
        manifest.append({
            "id":mid,"theme":theme,
            "music":MUSIC[slot%len(MUSIC)],
            "hook":HOOKS[theme][k%len(HOOKS[theme])],
            "outro":OUTROS[theme][k%len(OUTROS[theme])],
            "title":TITLES[theme][k%len(TITLES[theme])]+" #Shorts",
            "tags":TAGSET[theme],
            "target":18,
            "publishAt":slots[slot].strftime("%Y-%m-%dT%H:%M:%SZ"),
            "nseg":len(picked),"nclips":len(uniq),
        })

json.dump(manifest,open("scan/batch_manifest.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("montages generes:",len(manifest))
for m in manifest: print(f"  {m['id']:14s} {m['nclips']}clips mus={m['music']:14s} '{m['hook']}' -> '{m['outro']}' | {m['publishAt']}")
