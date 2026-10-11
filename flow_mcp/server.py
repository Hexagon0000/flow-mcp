"""MCP server exposing Google Flow to local agents.

Attaches to a Chrome you launched yourself with --remote-debugging-port,
so your normal Google session (and your AI Pro quota) is used as-is.
"""
import asyncio
import base64
import json
import mimetypes
import os
import pathlib
import urllib.request

from mcp.server.mcpserver import MCPServer

from . import flow, guides
from .cdp import open_page

PORT = int(os.environ.get("FLOW_CDP_PORT", "9222"))
DOWNLOAD_DIR = pathlib.Path(
    os.environ.get("FLOW_DOWNLOAD_DIR", pathlib.Path.home() / "Downloads" / "flow")
)

INSTRUCTIONS = """\
Google Flow'da video ve gorsel uretir. Kullanicinin kendi tarayicisina
bagli calisir; uretim onun Google AI Pro kotasindan harcanir.

Cogu istek icin tek arac yeter: flow_create(prompt, kind="image"|"video").
Modu ayarlar, uretir, bitmesini bekler ve dosyayi diske indirir.

Daha fazla denetim gerekiyorsa adimlar ayri ayri da cagirilabilir:
flow_settings -> flow_model -> (flow_frame | flow_ingredient) ->
flow_generate -> flow_status -> flow_download.

Bilinmesi gerekenler:

- Uretim bir Flow projesine yapilir. Sekme ana sayfadaysa sunucu kendisi
  yeni proje acar; flow_project ile dogrulayabilirsin. Chrome kapaliysa
  veya Google oturumu yoksa kullanicidan debug Chrome'u acip giris
  yapmasini iste.
- Gorsel uretimi (Nano Banana) kredi harcamaz, video harcar. Kullanici
  aksini soylemedikce en ucuz ayari sec: kisa sure, x1, dusuk cozunurluk.
  4K upscale kredi harcar ve ayrica onay ister.
- Video uretimi dakikalar surer. flow_generate beklemez; sonucu
  flow_status ile yokla.
- Daha iyi bir prompt icin flow_prompt_guide ile Google'in kendi
  rehberine bakabilirsin. Rehber otomatik uygulanmaz: okursun, prompt'u
  kendin yazarsin. Yanittaki tarih eskiyse tavsiyeye guvenme.
- Frames iki uc kareyi belirler, Ingredients ise prompt'a tasinan
  referans gorsellerdir. Ikisi de video moduna ozgudur.
"""

mcp = MCPServer("flow", instructions=INSTRUCTIONS)


async def _media_in_page(cdp):
    """Media ids currently rendered in the gallery."""
    js = (r"JSON.stringify([...new Set((document.body.innerHTML.match("
          r"/flow-content\.google\/(?:video|image)\/[0-9a-f-]{36}/g)||[]))]"
          r".map(s=>s.split('/').pop()))")
    return json.loads(await cdp.evaluate(js))


class _Page:
    """Opens a short-lived CDP session per call.

    Cheaper than holding a socket open for hours against a browser the
    user may close and reopen at will.
    """

    async def __aenter__(self):
        await self._connect()
        return self

    async def _connect(self):
        session, self.target = await open_page(PORT)
        self.session = session
        self.cdp = await session.__aenter__()
        await self.cdp.send("Runtime.enable")
        self.url = self.target["url"]

    async def __aexit__(self, *exc):
        await self.session.__aexit__(*exc)

    @property
    def project_id(self):
        return flow.project_id_from_url(self.url)

    async def require_project(self):
        """Open a new Flow project when the attached tab is the home page."""
        info = await flow.ensure_project(self.cdp)
        if info.get("project_id"):
            self.url = info["url"]
            return info
        # New-project sometimes opens a second tab; reconnect to it.
        await self.session.__aexit__(None, None, None)
        deadline = asyncio.get_running_loop().time() + 20
        last_err = "Yeni proje sekmesi gorunmedi"
        while asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.5)
            try:
                await self._connect()
            except RuntimeError as e:
                last_err = str(e)
                continue
            if self.project_id:
                info["project_id"] = self.project_id
                info["url"] = self.url
                info["switched"] = True
                return info
        raise RuntimeError(
            last_err + ". Yeni proje tiklandi ama /project/ URL'sine "
            "gecilemedi; Google hesabina giris yapilmis mi?"
        )


@mcp.tool()
async def flow_project() -> dict:
    """Which Flow project the attached browser tab currently has open.

    If the tab is still on the Flow home page, a new project is created.
    """
    async with _Page() as p:
        try:
            opened = await p.require_project()
        except RuntimeError as e:
            return {"error": str(e), "url": getattr(p, "url", "")}
        info = await flow.project_info(p.cdp, p.project_id)
        info["created"] = bool(opened.get("created"))
        return info


@mcp.tool()
async def flow_generate(prompt: str) -> dict:
    """Start a generation in the open Flow project.

    Produces a video or an image depending on the mode set with
    flow_settings, and honours the model, frames and ingredients
    currently selected. Returns immediately with media ids; poll
    flow_status for the result rather than blocking, since a video
    takes minutes.
    """
    async with _Page() as p:
        try:
            await p.require_project()
            ids = await flow.start_generation(p.cdp, prompt)
        except RuntimeError as e:
            return {"error": str(e)}
        return {"project_id": p.project_id, "media_ids": ids,
                "state": "pending",
                "hint": "flow_status ile durumu sorgula"}


@mcp.tool()
async def flow_create(prompt: str, kind: str = "image", model: str = "",
                      aspect: str = "", duration: str = "", resolution: str = "",
                      count: str = "", ingredients: list[str] | None = None,
                      start_frame: str = "", end_frame: str = "",
                      wait: int = 420, download: bool = True) -> dict:
    """Generate in Flow in one call: configure, generate, wait, download.

    This is the tool to reach for by default. `kind` is "image" or
    "video"; the rest are optional and take the labels Flow's own panel
    shows ("16:9", "720p", "8s", "x2"). Images cost no credits, video
    does, so leave the video options alone unless the user asked for
    something specific.

    Returns the local file path when the render finished, and the media
    ids to poll with flow_status if it was still going when `wait` ran
    out.
    """
    kind = kind.strip().lower()
    if kind not in ("image", "video"):
        return {"error": "kind 'image' ya da 'video' olmali"}

    mode = ["Image"] if kind == "image" else ["Video"]
    if start_frame or end_frame:
        mode.append("Frames")
    elif ingredients:
        mode.append("Ingredients")
    wanted = mode + [v for v in (aspect, resolution, duration, count) if v]

    steps = {}
    async with _Page() as p:
        try:
            await p.require_project()
            steps["settings"] = await flow.apply_settings(p.cdp, wanted)
            if model:
                steps["model"] = await flow.set_model(p.cdp, model)
            if start_frame:
                steps["start"] = await flow.set_frame(p.cdp, "Start", start_frame)
            if end_frame:
                steps["end"] = await flow.set_frame(p.cdp, "End", end_frame)
            if ingredients:
                steps["ingredients"] = await flow.add_ingredients(p.cdp, ingredients)
            media_ids = await flow.start_generation(p.cdp, prompt)
        except RuntimeError as e:
            return {"error": str(e), "steps": steps}

    result = {"project_id": p.project_id, "media_ids": media_ids, "steps": steps}

    deadline = asyncio.get_running_loop().time() + max(wait, 0)
    done = []
    for mid in media_ids:
        while asyncio.get_running_loop().time() < deadline:
            st = await flow_status(mid)
            if st["state"] != "pending":
                done.append(st)
                break
            await asyncio.sleep(8)
        else:
            result["state"] = "pending"
            result["hint"] = "Sure doldu, flow_status ile yoklamaya devam et"
            return result

    result["state"] = "done"
    if download:
        result["files"] = [await flow_download(st["media_id"]) for st in done]
    else:
        result["urls"] = [{"media_id": st["media_id"], "url": st["url"]} for st in done]
    return result


@mcp.tool()
async def flow_settings(options: list[str] | None = None) -> dict:
    """Read or change the generation settings panel.

    Call with no arguments to see what is selected and what is on offer.
    Pass labels exactly as they appear, e.g. ["Video", "9:16", "720p",
    "8s", "x2"]. Put "Video" or "Image" first: switching mode replaces
    the rest of the panel.
    """
    async with _Page() as p:
        try:
            await p.require_project()
        except RuntimeError as e:
            return {"error": str(e)}
        if not options:
            return await flow.read_settings(p.cdp)
        return await flow.apply_settings(p.cdp, options)


@mcp.tool()
async def flow_model(name: str = "") -> dict:
    """List the models on offer, or switch to one by name.

    The list depends on the current Image/Video mode, so set that with
    flow_settings first.
    """
    async with _Page() as p:
        try:
            await p.require_project()
        except RuntimeError as e:
            return {"error": str(e)}
        if not name:
            return await flow.list_models(p.cdp)
        return await flow.set_model(p.cdp, name)


@mcp.tool()
async def flow_frame(slot: str = "Start", asset: str = "") -> dict:
    """Set the Start or End frame of a video from an existing asset.

    Needs Frames mode: flow_settings(["Video", "Frames"]). Call without
    an asset to list what the picker offers; `asset` matches on the
    caption shown there.
    """
    if slot not in ("Start", "End"):
        return {"error": "slot 'Start' ya da 'End' olmali"}
    async with _Page() as p:
        try:
            await p.require_project()
        except RuntimeError as e:
            return {"error": str(e)}
        if not asset:
            return {"slot": slot, "assets": await flow.list_frame_assets(p.cdp, slot)}
        return await flow.set_frame(p.cdp, slot, asset)


@mcp.tool()
async def flow_upload(file_path: str) -> dict:
    """Upload a local image into the open Flow project.

    Once uploaded it can be used as a frame or an ingredient.
    """
    src = pathlib.Path(file_path).expanduser()
    if not src.is_file():
        return {"error": f"Dosya yok: {src}"}
    data = base64.b64encode(src.read_bytes()).decode()
    mime = mimetypes.guess_type(src.name)[0] or "image/jpeg"

    async with _Page() as p:
        try:
            await p.require_project()
        except RuntimeError as e:
            return {"error": str(e)}
        before = set(await _media_in_page(p.cdp))
        r = await p.cdp.evaluate(
            flow.JS_DROP % (json.dumps(data), json.dumps(src.name),
                            json.dumps(mime)), timeout=120)
        if not r.get("ok"):
            return {"error": "Yukleme tetiklenemedi"}
        for _ in range(20):
            await asyncio.sleep(2)
            new = set(await _media_in_page(p.cdp)) - before
            if new:
                return {"uploaded": src.name, "bytes": r["bytes"],
                        "media_ids": sorted(new)}
    return {"error": "Yukleme gorunmedi", "uploaded": src.name}


@mcp.tool()
async def flow_download_quality(media_id: str, quality: str = "1080p",
                                confirm_paid: bool = False) -> dict:
    """Download a clip at a chosen quality, including upscaled renders.

    Flow's own menu offers "270p" (animated GIF), "720p" (the original),
    "1080p" and "4K" (both upscaled). 270p/720p/1080p cost nothing; 4K
    spends credits, so it needs confirm_paid=True. Upscales render on
    demand and can take minutes.
    """
    if "4k" in quality.lower() and not confirm_paid:
        return {"error": "4K upscale kredi harciyor. Gercekten istiyorsan "
                         "confirm_paid=True ver.",
                "ucretsiz": ["270p", "720p", "1080p"]}
    async with _Page() as p:
        try:
            await p.require_project()
            return await flow.download_quality(
                p.cdp, media_id, quality, DOWNLOAD_DIR)
        except RuntimeError as e:
            return {"error": str(e)}


@mcp.tool()
async def flow_ingredient(assets: list[str] | None = None,
                          clear: bool = False) -> dict:
    """Attach reference images to the prompt as ingredients.

    Needs Ingredients mode: flow_settings(["Video", "Ingredients"]).
    With no arguments it reports what is attached and what the picker
    still offers; `assets` match on the captions shown there and several
    can be attached at once; `clear=True` detaches everything first.
    """
    async with _Page() as p:
        try:
            await p.require_project()
            if clear:
                cleared = await flow.clear_ingredients(p.cdp)
                if not assets:
                    return cleared
            if not assets:
                return {"attached": len(await flow.attached_ingredients(p.cdp)),
                        "available": await flow.list_ingredients(p.cdp)}
            res = await flow.add_ingredients(p.cdp, assets)
            res["attached"] = len(await flow.attached_ingredients(p.cdp))
            return res
        except RuntimeError as e:
            attached = await flow.attached_ingredients(p.cdp)
            return {"error": str(e), "attached": len(attached),
                    "ipucu": "Zaten ekli olanlar seciciden dusuyor; "
                             "clear=True ile hepsini kaldirabilirsin."}


@mcp.tool()
async def flow_prompt_guide(model: str = "", section: str = "") -> dict:
    """Google's own prompting guide for a Flow model.

    Reference material to write a better prompt with — nothing here is
    applied automatically, so read what is useful and put it in your own
    prompt to flow_generate. Call with no arguments to see which guides
    exist and their sections; with a model to get its formula and section
    list; with a section to read that section.

    Each answer carries the source url and the date it was retrieved:
    check that against the model list from flow_model, and ignore advice
    that no longer matches what Flow offers.
    """
    if not model:
        return guides.index()
    return guides.get(model, section)


@mcp.tool()
async def flow_status(media_id: str) -> dict:
    """Check whether a clip has finished rendering; returns its URLs when done."""
    async with _Page() as p:
        return await flow.get_media(p.cdp, media_id)


@mcp.tool()
async def flow_download(media_id: str, filename: str = "") -> dict:
    """Download a finished video or image to the local download directory."""
    async with _Page() as p:
        media = await flow.get_media(p.cdp, media_id)
    if media["state"] != "done":
        return {"error": "Medya hazir degil", "state": media["state"]}

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    # The CDN url is pre-signed, so a plain fetch works without cookies.
    with urllib.request.urlopen(media["url"], timeout=120) as resp:
        # Flow serves images as JPEG despite the /image/ path, so take the
        # extension from what the server actually sends.
        ext = mimetypes.guess_extension(
            resp.headers.get_content_type()) or (
                ".mp4" if media["kind"] == "video" else ".jpg")
        dest = DOWNLOAD_DIR / (filename or f"{media_id}{ext}")
        dest.write_bytes(resp.read())
    return {"path": str(dest), "kind": media["kind"],
            "bytes": dest.stat().st_size, "prompt": media["prompt"]}


def main():
    mcp.run()


if __name__ == "__main__":
    main()
