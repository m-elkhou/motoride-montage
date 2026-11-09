"""pHash des clips candidats vs sources deja publiees (sha) + 3 detectes pHash -> exclut les doublons de chaine.
Usage: uv run (dans social2shorts) python <ce fichier> cand.json  -> cand_checked.json"""
import json, sys
from pathlib import Path
from social2shorts.phash import phash_file, min_distance
ROOT=Path("C:/workdir/uw/scraper/social2shorts")
pub=list((ROOT/"_duplicates/on_channel_sha").glob("*.mp4"))+list((ROOT/"_duplicates/on_channel_phash").glob("*.mp4"))
cache=Path("C:/workdir/uw/scraper/motoride-montage/scan/published_hashes.json")
H=json.load(open(cache)) if cache.exists() else {}
for f in pub:
    if f.name not in H: H[f.name]=phash_file(f,8)
json.dump(H,open(cache,"w"),indent=0)
cand=json.load(open(sys.argv[1],encoding="utf-8")); out=[]
for c in cand:
    h=phash_file(c["path"],8); d=min((min_distance(h,v) for v in H.values()),default=999)
    c["dist_channel"]=int(d); c["on_channel"]=d<=10; out.append(c)
json.dump(out,open(sys.argv[1].replace(".json","_checked.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("candidats:",len(out),"| deja sur la chaine (pHash<=10):",sum(c["on_channel"] for c in out))
