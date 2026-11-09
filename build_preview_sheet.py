import subprocess, math, json

import mm_paths

MON = mm_paths.ROOT
OUT = MON / "out"; TMP = MON / "_sheet"; TMP.mkdir(exist_ok=True)
FF = mm_paths.FFMPEG
FONT = mm_paths.ffmpeg_font()

manifest = {m["id"]: m for m in json.load(open(MON / "manifest.json", encoding="utf-8"))}
ids = [f"{s}{i:02d}" for s in "abc" for i in range(1, 11)]

frames = []
missing = []
for vid in ids:
    f = OUT / f"{vid}.mp4"
    if not f.exists():
        missing.append(vid); continue
    out = TMP / f"lbl_{vid}.jpg"
    vf = (f"scale=216:-2,drawtext=fontfile='{FONT}':text='{vid}':x=6:y=6:"
          f"fontsize=22:fontcolor=white:box=1:boxcolor=black@0.65:boxborderw=5")
    subprocess.run([FF, "-y", "-ss", "1.6", "-i", str(f), "-frames:v", "1", "-vf", vf, str(out)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if out.exists():
        frames.append(out)

for j, fr in enumerate(frames):
    (TMP / f"s{j:02d}.jpg").write_bytes(fr.read_bytes())
n = len(frames); cols = 5; rows = math.ceil(n / cols)
subprocess.run([FF, "-y", "-i", str(TMP / "s%02d.jpg"), "-vf", f"tile={cols}x{rows}",
                "-frames:v", "1", str(MON / "PREVIEW_30.jpg")],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("preview:", n, "vignettes | manquants:", missing)

# INDEX.md
STYLE = {"day": "A — Daylight Freedom", "night": "B — Night Rider", "raw": "C — Escape / Adventure"}
lines = ["# Les 30 Shorts — index\n",
         f"Dossier des vidéos : `{OUT}`  — aperçu : `PREVIEW_30.jpg`\n"]
for st in ("day", "night", "raw"):
    lines.append(f"\n## {STYLE[st]}\n")
    for vid in ids:
        m = manifest[vid]
        if m["style"] != st:
            continue
        ok = "" if (OUT / f"{vid}.mp4").exists() else "  ⚠️ MANQUANT"
        lines.append(f"- **{vid}** — « {m['hook']} » — clip `{m['clip']}` — `out/{vid}.mp4`{ok}\n")
(MON / "INDEX.md").write_text("".join(lines), encoding="utf-8")
print("INDEX.md written")
