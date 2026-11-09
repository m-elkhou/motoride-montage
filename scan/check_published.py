"""pHash des clips candidats vs sources deja publiees (sha) + 3 detectes pHash -> exclut les doublons de chaine.
Usage: uv run (dans social2shorts) python <ce fichier> cand.json  -> cand_checked.json"""
import sys
from pathlib import Path as _P
sys.path.insert(0,str(_P(__file__).resolve().parents[1]))
import json
import mm_paths
from social2shorts.phash import phash_file, min_distance
ROOT=mm_paths.S2S_ROOT
pub=list((ROOT/"_duplicates/on_channel_sha").glob("*.mp4"))+list((ROOT/"_duplicates/on_channel_phash").glob("*.mp4"))
cache=mm_paths.SCAN/"published_hashes.json"
def key(f): s=f.stat(); return f"{f.name}|{s.st_size}|{s.st_mtime_ns}"   # nom+taille+date : un fichier remplace est recalcule
H=json.load(open(cache)) if cache.exists() else {}
H={k:v for k,v in H.items() if "|" in k}   # ancien format (nom seul) : a recalculer
for f in pub:
    if key(f) not in H: H[key(f)]=phash_file(f,8)
json.dump(H,open(cache,"w"),indent=0)
cand=json.load(open(sys.argv[1],encoding="utf-8")); out=[]
for c in cand:
    h=phash_file(c["path"],8); d=min((min_distance(h,v) for v in H.values()),default=999)
    c["dist_channel"]=int(d); c["on_channel"]=d<=10; out.append(c)
json.dump(out,open(sys.argv[1].replace(".json","_checked.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("candidats:",len(out),"| deja sur la chaine (pHash<=10):",sum(c["on_channel"] for c in out))
