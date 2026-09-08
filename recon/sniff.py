"""Watch Flow's internal network calls while you drive the UI by hand.

Usage:  .venv/bin/python recon/sniff.py [seconds]
Then interact with Flow in the browser; requests are printed live and
saved to recon/capture.json for offline study.
"""
import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from flow_mcp.cdp import open_page  # noqa: E402

OUT = pathlib.Path(__file__).parent / "capture.json"
# Static asset noise we never care about.
SKIP = (".js", ".css", ".png", ".jpg", ".webp", ".woff", ".woff2", ".svg", ".ico")


async def main(seconds):
    session, target = await open_page()
    print(f"Sekme: {target['url']}\n{seconds} saniye dinleniyor. "
          f"Flow'da bir video uretimi baslat.\n" + "-" * 60)

    captured = []
    async with session as cdp:
        await cdp.send("Network.enable")

        async def pump():
            async for msg in cdp.events():
                m = msg.get("method")
                p = msg.get("params", {})
                if m == "Network.requestWillBeSent":
                    req = p["request"]
                    url = req["url"]
                    if url.startswith("data:") or url.endswith(SKIP):
                        continue
                    entry = {
                        "id": p["requestId"],
                        "method": req["method"],
                        "url": url,
                        "body": req.get("postData", "")[:4000],
                    }
                    captured.append(entry)
                    print(f"{req['method']:5} {url[:120]}")
                    if entry["body"]:
                        print(f"      body: {entry['body'][:300]}")
                elif m == "Network.responseReceived":
                    for e in captured:
                        if e["id"] == p["requestId"]:
                            e["status"] = p["response"]["status"]
                            break

        try:
            await asyncio.wait_for(pump(), timeout=seconds)
        except asyncio.TimeoutError:
            pass

        # Pull response bodies for the interesting (non-asset) calls.
        for e in captured:
            try:
                r = await cdp.send("Network.getResponseBody",
                                   {"requestId": e["id"]}, timeout=10)
                e["response"] = r.get("body", "")[:8000]
            except Exception:
                e["response"] = None

    OUT.write_text(json.dumps(captured, indent=2, ensure_ascii=False))
    print("-" * 60)
    print(f"{len(captured)} istek kaydedildi -> {OUT}")


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 90))
