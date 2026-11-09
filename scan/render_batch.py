# -*- coding: utf-8 -*-
import json, subprocess, os
PY="C:/workdir/_s2s_cb/venv/Scripts/python.exe"
man=json.load(open("scan/batch_manifest.json",encoding="utf-8"))
ok=[]; ko=[]
for m in man:
    out=f"out/{m['id']}.mp4"
    if os.path.exists(out) and os.path.getsize(out)>200000:
        ok.append(m['id']); print("deja:",m['id'],flush=True); continue
    try:
        r=subprocess.run([PY,"-X","utf8","viral_cut.py","--segments",f"scan/mont/{m['id']}.json",
                      "--music",f"public/{m['music']}","--hook",m["hook"],"--outro",m["outro"],
                      "--target",str(m["target"]),"--out",out],
                     capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=240)
    except subprocess.TimeoutExpired:
        import os as _os; _os.system('taskkill /IM ffmpeg.exe /F >NUL 2>&1')
        ko.append(m['id']); print(f"TIMEOUT {m['id']}",flush=True); continue
    if os.path.exists(out) and os.path.getsize(out)>200000:
        ok.append(m['id']); print(f"OK {m['id']} ({os.path.getsize(out)//1024}Ko)",flush=True)
    else:
        ko.append(m['id']); print(f"ECHEC {m['id']}: {(r.stderr or '')[-200:]}",flush=True)
print(f"\nBILAN RENDU: {len(ok)} OK, {len(ko)} KO {ko}",flush=True)
