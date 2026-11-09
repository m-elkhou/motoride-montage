"""Upload d'un Short avec le token OAuth du projet social2shorts. Reessaie sur uploadLimitExceeded.
Usage: uv run (dans social2shorts) python <ce fichier> meta/x.json [--not-before HH:MM] [--retry-min 10] [--max-hours 6] [--dry-run]"""
import argparse, json, sys, time, socket
socket.setdefaulttimeout(180)
from datetime import datetime, timedelta
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from social2shorts.publish.youtube import get_credentials
P=Path("C:/workdir/uw/scraper/social2shorts")
ap=argparse.ArgumentParser(); ap.add_argument("meta",nargs="+"); ap.add_argument("--not-before"); ap.add_argument("--retry-min",type=int,default=10); ap.add_argument("--max-hours",type=float,default=6); ap.add_argument("--dry-run",action="store_true")
a=ap.parse_args()
if a.not_before:
    h,m=map(int,a.not_before.split(":")); t=datetime.now().replace(hour=h,minute=m,second=0,microsecond=0)
    if t<datetime.now(): t+=timedelta(days=1)
    while datetime.now()<t: print("attente jusqu'a",t.strftime("%H:%M"),flush=True); time.sleep(min(600,max(5,(t-datetime.now()).total_seconds())))
creds=get_credentials(str(P/"secrets/client_secret.json"),str(P/"secrets/token.json"),interactive=False); yt=build("youtube","v3",credentials=creds)
deadline=time.time()+a.max_hours*3600; done={}
for mp in a.meta:
    meta=json.load(open(mp,encoding="utf-8")); v=Path(meta["video"]); assert v.is_file() and len(meta["title"])<=100
    body={"snippet":{"title":meta["title"],"description":meta["description"],"tags":meta["tags"],"categoryId":meta.get("categoryId","2"),"defaultLanguage":meta.get("lang","fr"),"defaultAudioLanguage":meta.get("lang","fr")},
          "status":{"privacyStatus":meta.get("privacy","public"),"selfDeclaredMadeForKids":False,"containsSyntheticMedia":False}}
    if meta.get("publishAt"): body["status"]["privacyStatus"]="private"; body["status"]["publishAt"]=meta["publishAt"]
    if a.dry_run: print("DRY",mp,meta["title"],f"{v.stat().st_size/1e6:.1f} MB"); continue
    net_tries=0
    while True:
        try:
            req=yt.videos().insert(part="snippet,status",body=body,media_body=MediaFileUpload(str(v),mimetype="video/mp4",chunksize=8*1024*1024,resumable=True))
            resp=None
            while resp is None:
                st,resp=req.next_chunk(num_retries=3)
            done[mp]=resp["id"]; print(f"OK {mp} -> https://youtube.com/shorts/{resp['id']}",flush=True); break
        except HttpError as e:
            s=str(e)
            if "uploadLimitExceeded" in s and time.time()<deadline:
                print(f"limite d'envoi atteinte, nouvel essai dans {a.retry_min} min ({time.strftime('%H:%M')})",flush=True); time.sleep(a.retry_min*60); continue
            print("ECHEC",mp,s[:300],flush=True); break
        except (OSError, ConnectionError, TimeoutError, Exception) as e:
            net_tries+=1
            if net_tries<=5 and time.time()<deadline:
                print(f"erreur reseau ({type(e).__name__}: {str(e)[:120]}), reprise {net_tries}/5 dans 20s",flush=True); time.sleep(20); continue
            print("ECHEC",mp,"reseau:",str(e)[:200],flush=True); break
json.dump(done,open("C:/workdir/uw/scraper/motoride-montage/meta/_uploaded_"+time.strftime("%Y%m%d_%H%M")+".json","w"),indent=1)
