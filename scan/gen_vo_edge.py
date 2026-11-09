# -*- coding: utf-8 -*-
import asyncio, json
from pathlib import Path
import edge_tts
M=Path("C:/workdir/uw/scraper/motoride-montage"); VO=M/"vo"; VO.mkdir(exist_ok=True)
VOICE="en-US-GuyNeural"
async def main():
    man=json.load(open(M/"scan/batch_manifest.json",encoding="utf-8"))
    for i,m in enumerate(man,1):
        line=m["hook"].capitalize().rstrip(".")+"."
        out=VO/f"{m['id']}.mp3"
        c=edge_tts.Communicate(line, voice=VOICE, rate="+8%")
        await c.save(str(out))
        print(f"[{i}/{len(man)}] {m['id']} '{line}'",flush=True)
    print("DONE vo_edge",flush=True)
asyncio.run(main())
