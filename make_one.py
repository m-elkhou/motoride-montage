"""Fabrique UNE Short a partir d'un spec JSON (voix deja generee en amont).
Usage: python make_one.py spec.json
Etapes: pre-encode clip 1080x1920 -> props -> remotion render -> loudnorm -> nettoyage.
Idempotent, continue-on-error (code de sortie != 0 si echec, mais log ecrit)."""
import json, subprocess, sys, shutil, time

import mm_paths

MONTAGE = mm_paths.ROOT
PUBLIC = MONTAGE / "public"
OUT = MONTAGE / "out"
PROPS = MONTAGE / "props"
INBOX = mm_paths.CLIP_DIRS["inbox"]
FF = mm_paths.FFMPEG
for d in (OUT, PROPS):
    d.mkdir(parents=True, exist_ok=True)


def log(sid, msg):
    line = f"{time.strftime('%H:%M:%S')} [{sid}] {msg}"
    print(line, flush=True)
    with open(OUT / "batch_status.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def main(spec_path):
    spec = json.load(open(spec_path, encoding="utf-8"))
    sid = spec["id"]
    final = OUT / f"{sid}.mp4"
    if final.exists():
        log(sid, f"deja fait -> {final}")
        return 0
    try:
        vlen = float(spec["video_len_s"])
        vostart = float(spec.get("vo_start_s", 1.5))
        clip_src = INBOX / spec["clip"]
        staged = PUBLIC / f"{sid}_clip.mp4"
        vo_pub = PUBLIC / f"{sid}_vo.wav"

        # 1) pre-encode clip 1080x1920 (rotation auto, sans audio)
        r = run([FF, "-y", "-i", str(clip_src), "-t", f"{vlen:.2f}", "-an",
                 "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                 "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                 "-pix_fmt", "yuv420p", str(staged)])
        if not staged.exists():
            log(sid, "ECHEC pre-encode clip: " + r.stderr[-300:]); return 2
        shutil.copyfile(spec["vo_wav"], vo_pub)

        # 2) captions (frames) depuis les timings de la voix
        tim = json.load(open(spec["timings"], encoding="utf-8"))["lines"]
        caps = [{"from": round((vostart + l["start"]) * 30),
                 "to": round((vostart + l["end"]) * 30),
                 "text": l["text"]} for l in tim]
        volen = round((tim[-1]["end"] + 0.4) * 30) if tim else 360

        props = {
            "clip": staged.name, "music": spec["music"], "vo": vo_pub.name,
            "hook": spec["hook"], "cta": spec["cta"], "style": spec.get("style", "day"),
            "voStartFrame": round(vostart * 30), "voLenFrames": volen,
            "captions": caps, "durationInFrames": round(vlen * 30),
        }
        pf = PROPS / f"{sid}.json"
        pf.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")

        # 3) rendu Remotion (1080x1920)
        raw = OUT / f"{sid}_raw.mp4"
        r = run(["npx", "remotion", "render", "MotoShort", str(raw),
                 f"--props={pf}", "--codec=h264", "--concurrency=1", "--log=error"],
                cwd=str(MONTAGE), shell=True)
        if not raw.exists():
            log(sid, "ECHEC remotion: " + (r.stderr or r.stdout)[-400:]); return 3

        # 4) loudnorm -> final (garde la video)
        r = run([FF, "-y", "-i", str(raw),
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
                 "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "160k",
                 str(final)])
        if not final.exists():
            log(sid, "ECHEC loudnorm: " + r.stderr[-300:]); return 4

        # 5) nettoyage
        for p in (staged, vo_pub, raw):
            try: p.unlink()
            except Exception: pass
        log(sid, f"OK -> {final} ({final.stat().st_size//1024} Ko, style={spec.get('style')})")
        return 0
    except Exception as e:
        log(sid, f"EXCEPTION {type(e).__name__}: {e}")
        return 9


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
