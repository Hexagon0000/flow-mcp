"""Flow-specific layer: batchexecute RPC + UI driving.

Two paths, deliberately split:
  * Read operations (status, media details) go straight to Flow's own
    batchexecute RPC from inside the page. No captcha, no DOM.
  * Generation drives the real UI, because the request Flow sends carries
    a reCAPTCHA Enterprise token that only its own JS can mint.
"""
import json
import re

RPC_MEDIA = "as29s"       # media detail, incl. signed CDN urls
RPC_STATUS = "jwpduf"     # lightweight status poll
RPC_PROJECT = "ngNC2"     # project metadata
# Starting a generation carries a captcha token, and Flow uses a different
# rpc per media kind. Which one fires depends on the Video/Image toggle.
RPC_GEN_VIDEO = "YhhmEf"
RPC_GEN_IMAGE = "ogiZ0b"
RPC_GENERATE = (RPC_GEN_VIDEO, RPC_GEN_IMAGE)

_CDN = re.compile(r"https://flow-content\.google/(video|image)/[^\"\\\s]+")


def _js_rpc(rpcid, payload):
    """JS that POSTs one batchexecute call from within the page."""
    return """
(async () => {
  const at = window.WIZ_global_data && window.WIZ_global_data.SNlM0e;
  if (!at) return {ok:false, err:"XSRF token yok - Flow sekmesi acik mi?"};
  const body = new URLSearchParams({
    "f.req": JSON.stringify([[[%s, %s, null, "generic"]]]),
    at: at,
  });
  const r = await fetch("/_/AiSandboxAngularFrontend/data/batchexecute?rpcids=%s",
    {method:"POST", body,
     headers:{"content-type":"application/x-www-form-urlencoded;charset=UTF-8"}});
  return {ok: r.ok, status: r.status, text: await r.text()};
})()
""" % (json.dumps(rpcid), json.dumps(json.dumps(payload)), rpcid)


def _parse(raw, rpcid):
    """Pull the payload for `rpcid` out of a batchexecute envelope."""
    # Envelope: )]}'\n\n<len>\n[["wrb.fr","<rpc>","<json string>",...]]
    for line in raw.split("\n"):
        line = line.strip()
        if not line.startswith("[["):
            continue
        try:
            rows = json.loads(line)
        except json.JSONDecodeError:
            continue
        for row in rows:
            if len(row) > 2 and row[0] == "wrb.fr" and row[1] == rpcid:
                return json.loads(row[2]) if row[2] else None
    return None


async def rpc(cdp, rpcid, payload):
    res = await cdp.evaluate(_js_rpc(rpcid, payload), timeout=60)
    if not res or not res.get("ok"):
        raise RuntimeError(f"{rpcid} RPC hatasi: {res}")
    return _parse(res["text"], rpcid), res["text"]


async def get_media(cdp, media_id):
    """Status, kind and URLs for one generated item (video or image)."""
    data, _ = await rpc(cdp, RPC_MEDIA, [media_id])
    if data is None:
        # Flow answers an unknown id with an empty payload, not an HTTP
        # error. Without this it would look indistinguishable from an
        # item that is still rendering.
        return {"media_id": media_id, "state": "not_found", "kind": None,
                "url": None, "prompt": None,
                "error": "Bu id ile medya bulunamadi"}

    # The payload carries the finished asset in a slot that depends on its
    # kind: index 7 for video, index 6 for image. Whichever is populated
    # tells us both what was generated and whether it is ready.
    node_img = data[6] if len(data) > 6 else None
    node_vid = data[7] if len(data) > 7 else None
    kind = "video" if node_vid else ("image" if node_img else None)
    node = node_vid or node_img

    url = _first_url(node) if node else None
    return {
        "media_id": media_id,
        "kind": kind,
        "state": "done" if url else "pending",
        "url": url,
        "prompt": _first_prompt(data),
        "created": _created(data),
    }


def _created(data):
    """Creation time of a media record, epoch seconds."""
    try:
        return data[5][0][0]
    except (TypeError, IndexError):
        return None


def _unescape(text):
    """Signed urls arrive JSON-escaped at a depth that varies with nesting."""
    text = re.sub(r"\\+u003d", "=", text)
    return re.sub(r"\\+u0026", "&", text)


def _first_url(node):
    m = _CDN.search(_unescape(json.dumps(node, ensure_ascii=False)))
    return m.group(0) if m else None


def _first_prompt(data):
    """The prompt text, wherever Flow parked it for this media kind."""
    try:
        meta = data[5]
    except (TypeError, IndexError):
        return None
    if isinstance(meta, list) and len(meta) > 1 and isinstance(meta[1], str):
        return meta[1]
    for s in re.findall(r'"([^"]{12,500})"',
                        json.dumps(meta, ensure_ascii=False)):
        if not s.startswith(("http", "type.googleapis")):
            return s
    return None


async def project_info(cdp, project_id):
    data, _ = await rpc(cdp, RPC_PROJECT,
                        [f"tools/PINHOLE/projects/{project_id}"])
    name = None
    if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
        name = data[1][0] if data[1] else None
    return {"project_id": project_id, "name": name}


def project_id_from_url(url):
    m = re.search(r"/project/([0-9a-f-]{36})", url or "")
    return m.group(1) if m else None


JS_NEW_PROJECT = r"""
(() => {
  const label = el => (
    (el.getAttribute('aria-label') || '') + ' ' +
    (el.innerText || el.textContent || '')
  ).replace(/\s+/g, ' ').trim();
  const visible = el => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const els = [...document.querySelectorAll(
    'button, a, [role=button], [role=link]')].filter(visible);
  const hit = els.find(el =>
    /new\s*project|yeni\s*proje|create\s*(a\s*)?project|create\s*new/i
      .test(label(el)));
  if (!hit) {
    const nearby = els.map(label).filter(t => t && t.length < 80).slice(0, 24);
    return {ok:false, err:"Yeni proje butonu bulunamadi", nearby};
  }
  hit.click();
  return {ok:true, label: label(hit)};
})()
"""


async def page_url(cdp):
    return await cdp.evaluate("location.href")


async def ensure_project(cdp, timeout=45):
    """If the tab is Flow home, open a new project and wait for /project/.

    Returns {project_id, created, url}. `created` is False when a project
    was already open. Raises if the home page has no New-project control
    (usually because the user is not signed in).
    """
    import asyncio
    url = await page_url(cdp)
    pid = project_id_from_url(url)
    if pid:
        return {"project_id": pid, "created": False, "url": url}

    clicked = await cdp.evaluate(JS_NEW_PROJECT)
    if not clicked.get("ok"):
        nearby = clicked.get("nearby") or []
        hint = (" Yakin etiketler: " + ", ".join(nearby)) if nearby else ""
        raise RuntimeError(
            (clicked.get("err") or "Yeni proje acilamadi") +
            ". flow.google.com acik ve Google hesabina giris yapilmis olmali."
            + hint
        )

    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(0.4)
        url = await page_url(cdp)
        pid = project_id_from_url(url)
        if pid:
            return {"project_id": pid, "created": True, "url": url,
                    "clicked": clicked.get("label")}
    return {"project_id": None, "created": True, "url": url,
            "clicked": clicked.get("label"),
            "pending_other_tab": True}


# --- generation: drive the real UI so Flow mints its own captcha token ---

JS_SET_PROMPT = """
(() => {
  const ed = document.querySelector('.ProseMirror');
  if (!ed) return {ok:false, err:"Prompt alani bulunamadi"};
  ed.focus();
  // ProseMirror ignores direct .textContent writes; go through the
  // clipboard/input pipeline it actually listens to.
  document.execCommand('selectAll', false, null);
  document.execCommand('insertText', false, %s);
  return {ok:true, text: ed.innerText.trim()};
})()
"""

JS_CLICK_GENERATE = """
(() => {
  // Flow's Angular build renames its css classes between releases, so the
  // submit control is identified by its material icon glyph instead, with
  // the class name kept only as a hint.
  const cands = [...document.querySelectorAll('button')].filter(b =>
    b.offsetParent !== null &&
    (/generate/i.test(b.className) ||
     (b.innerText || '').trim() === 'arrow_forward'));
  if (!cands.length) return {ok:false, err:"Generate butonu bulunamadi"};
  const b = cands.find(x => !x.disabled);
  if (!b) return {ok:false, err:"Generate butonu pasif (prompt bos ya da uretim suruyor)"};
  b.click();
  return {ok:true};
})()
"""


async def start_generation(cdp, prompt, timeout=60):
    """Type the prompt, press generate, return the new media ids.

    Flow uses a different rpc per generation path (plain video, image,
    start/end frames, ...), so rather than watch for a known rpc id, every
    batchexecute reply that follows the click is scanned for uuids and the
    media service is asked which of them are real. That keeps this working
    when Flow adds a path we have never seen.
    """
    import asyncio

    await cdp.send("Network.enable")
    # Reference images travel in the generate request too, and they are
    # real media, so ids are also filtered by creation time to keep the
    # ingredients out of the result.
    since = await cdp.evaluate("Math.floor(Date.now()/1000)") - 5
    bodies = []
    pending = {}

    async def watch():
        async for msg in cdp.events():
            m, p = msg.get("method"), msg.get("params", {})
            if m == "Network.requestWillBeSent":
                if "batchexecute" in p.get("request", {}).get("url", ""):
                    pending[p["requestId"]] = True
            elif m == "Network.loadingFinished" and p.get("requestId") in pending:
                try:
                    body = await cdp.send("Network.getResponseBody",
                                          {"requestId": p["requestId"]},
                                          timeout=20)
                    bodies.append(body.get("body", ""))
                except Exception:
                    pass

    watcher = asyncio.create_task(watch())
    try:
        r = await cdp.evaluate(JS_SET_PROMPT % json.dumps(prompt))
        if not r or not r.get("ok"):
            raise RuntimeError(r.get("err") if r else "prompt yazilamadi")
        if prompt.strip()[:40] not in (r.get("text") or ""):
            raise RuntimeError(f"Prompt tam yazilamadi, editorde: {r.get('text')!r}")

        r = await cdp.evaluate(JS_CLICK_GENERATE)
        if not r or not r.get("ok"):
            raise RuntimeError(r.get("err") if r else "generate tiklanamadi")

        deadline = asyncio.get_running_loop().time() + timeout
        tried = set()
        while asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(3)
            found = await _resolve_media_ids(cdp, "\n".join(bodies),
                                             skip=tried, since=since)
            if found:
                return found
            tried |= set(_uuids("\n".join(bodies)))
    finally:
        watcher.cancel()

    raise RuntimeError(
        "Generate'e basildi ama medya kaydi olusmadi - tarayicida captcha, "
        "kota uyarisi ya da eksik bir alan olabilir")


def _uuids(text):
    seen, out = set(), []
    for u in re.findall(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", text):
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


async def _resolve_media_ids(cdp, raw, skip=(), since=None):
    """Which uuids in the captured traffic the media service recognises.

    A generate reply also carries operation, project and scene ids, and
    their positions differ per path, so identity is established by asking
    rather than by reading a fixed index.
    """
    found = []
    for u in _uuids(raw):
        if u in skip:
            continue
        info = await get_media(cdp, u)
        if info["state"] == "not_found":
            continue
        created = info.get("created")
        if since is not None and created is not None and created < since:
            continue    # pre-existing asset, e.g. an ingredient
        found.append(u)
    return found


# --- settings panel -----------------------------------------------------
#
# Model, aspect ratio, resolution, duration and output count all live in a
# popover that Flow renders into Angular's overlay container. Its controls
# are plain toggle buttons carrying their own labels, so they are matched
# by text rather than by class.

JS_PANEL_OPEN = """
(() => {
  const ov = document.querySelector('.cdk-overlay-container');
  if (ov && ov.children.length) return {ok:true, already:true};
  const b = [...document.querySelectorAll('button')]
    .find(x => /settings-trigger/i.test(x.className));
  if (!b) return {ok:false, err:"Ayar butonu bulunamadi"};
  b.click();
  return {ok:true};
})()
"""

JS_PANEL_READ = """
(() => {
  const q = '.cdk-overlay-container button';
  const btns = [...document.querySelectorAll(q)];
  const label = e => (e.innerText||'').replace(/\\n/g,' ').trim();
  const on = e => e.className.includes('selected')
                || e.getAttribute('aria-checked') === 'true'
                || e.getAttribute('aria-pressed') === 'true';
  return {
    ok: btns.length > 0,
    options: btns.map(e => ({label: label(e), selected: on(e)})),
  };
})()
"""

JS_PANEL_CLICK = """
(() => {
  const want = %s;
  const btns = [...document.querySelectorAll('.cdk-overlay-container button')];
  const norm = e => (e.innerText||'').replace(/\\n/g,' ').trim();
  // Labels read like "crop_16_9 16:9" — the icon glyph is a separate word,
  // so match on the words rather than the whole string.
  const b = btns.find(e => norm(e).split(/\\s+/).includes(want))
         || btns.find(e => norm(e).includes(want));
  if (!b) return {ok:false, err:"Secenek yok: " + want,
                  mevcut: btns.map(norm)};
  b.click();
  return {ok:true};
})()
"""


async def close_overlay(cdp):
    """Dismiss any open popover without touching the page underneath.

    Clicking a blind coordinate would land on the gallery and open a
    media item, so only the overlay's own backdrop is clicked, and a real
    Escape key event is used when there is none.
    """
    import asyncio
    had = await cdp.evaluate("""
      (() => {
        const bd = document.querySelector('.cdk-overlay-backdrop');
        if (bd) { bd.click(); return 'backdrop'; }
        const ov = document.querySelector('.cdk-overlay-container');
        return (ov && ov.children.length) ? 'overlay' : 'none';
      })()
    """)
    if had == "none":
        return
    for _ in range(3):
        await cdp.send("Input.dispatchKeyEvent",
                       {"type": "keyDown", "key": "Escape",
                        "code": "Escape", "windowsVirtualKeyCode": 27})
        await cdp.send("Input.dispatchKeyEvent",
                       {"type": "keyUp", "key": "Escape",
                        "code": "Escape", "windowsVirtualKeyCode": 27})
        await asyncio.sleep(0.4)
        left = await cdp.evaluate(
            "document.querySelectorAll('.cdk-overlay-container > *').length")
        if not left:
            return


async def open_panel(cdp, attempts=3):
    """Open the settings popover and confirm it actually rendered.

    A click issued while a previous overlay is still animating out gets
    swallowed, so the result is verified and the click retried.
    """
    import asyncio
    for _ in range(attempts):
        await close_overlay(cdp)
        await asyncio.sleep(0.8)
        r = await cdp.evaluate(JS_PANEL_OPEN)
        if not r.get("ok"):
            raise RuntimeError(r.get("err"))
        for _ in range(6):
            await asyncio.sleep(0.4)
            n = await cdp.evaluate(
                "document.querySelectorAll('.cdk-overlay-container button').length")
            if n:
                return True
    raise RuntimeError("Ayar paneli acilmadi")


def _selected(options):
    return [o["label"].split()[-1] for o in options if o["selected"]]


async def read_settings(cdp):
    import asyncio
    await open_panel(cdp)
    panel = await cdp.evaluate(JS_PANEL_READ)
    await close_overlay(cdp)
    opts = panel.get("options", [])
    return {"selected": _selected(opts),
            "available": [o["label"] for o in opts]}


async def apply_settings(cdp, values):
    """Click each requested option in the settings popover, in order."""
    import asyncio
    # A picker left open from an earlier step would otherwise swallow
    # these clicks, so start from a clean slate.
    await open_panel(cdp)

    applied, failed = [], []
    for v in values:
        res = await cdp.evaluate(JS_PANEL_CLICK % json.dumps(str(v)))
        if res.get("ok"):
            applied.append(v)
            # Switching Image/Video swaps the rest of the panel out.
            await asyncio.sleep(0.8)
        else:
            failed.append({"value": v, "mevcut": res.get("mevcut", [])})

    panel = await cdp.evaluate(JS_PANEL_READ)
    await close_overlay(cdp)
    return {"applied": applied, "failed": failed,
            "selected": _selected(panel.get("options", []))}


# --- model menu ---------------------------------------------------------

JS_MODEL_OPEN = """
(() => {
  const b = [...document.querySelectorAll('.cdk-overlay-container button')]
    .find(x => /mat-mdc-menu-trigger/.test(x.className)
            && /arrow_drop_down/.test(x.innerText || ''));
  if (!b) return {ok:false, err:"Model menusu bulunamadi"};
  b.click();
  return {ok:true, current: b.innerText.replace('arrow_drop_down','').trim()};
})()
"""

JS_MODEL_LIST = """
JSON.stringify([...document.querySelectorAll(
  '[role=menu] button, [role=menuitem], .mat-mdc-menu-panel button')]
  .map(e => (e.innerText||'').replace(/\\n/g,' ').replace(/^volume_up\\s*/,'').trim())
  .filter(Boolean))
"""

JS_MODEL_PICK = """
(() => {
  const want = %s;
  const items = [...document.querySelectorAll(
    '[role=menu] button, [role=menuitem], .mat-mdc-menu-panel button')];
  const name = e => (e.innerText||'').replace(/\\n/g,' ')
                     .replace(/^volume_up\\s*/,'').trim();
  const b = items.find(e => name(e).toLowerCase() === want.toLowerCase())
         || items.find(e => name(e).toLowerCase().includes(want.toLowerCase()));
  if (!b) return {ok:false, mevcut: items.map(name)};
  b.click();
  return {ok:true, secilen: name(b)};
})()
"""


async def list_models(cdp):
    """Model names offered for the currently selected media kind."""
    import asyncio
    await open_panel(cdp)
    opened = await cdp.evaluate(JS_MODEL_OPEN)
    if not opened.get("ok"):
        await close_overlay(cdp)
        raise RuntimeError(opened.get("err"))
    await asyncio.sleep(1.0)
    models = json.loads(await cdp.evaluate(JS_MODEL_LIST))
    await close_overlay(cdp)
    return {"current": opened.get("current"), "models": models}


async def set_model(cdp, name):
    import asyncio
    await open_panel(cdp)
    opened = await cdp.evaluate(JS_MODEL_OPEN)
    if not opened.get("ok"):
        await close_overlay(cdp)
        raise RuntimeError(opened.get("err"))
    await asyncio.sleep(1.0)
    res = await cdp.evaluate(JS_MODEL_PICK % json.dumps(name))
    await asyncio.sleep(0.8)
    await close_overlay(cdp)
    if not res.get("ok"):
        raise RuntimeError(
            f"Model bulunamadi: {name}. Mevcut: {', '.join(res.get('mevcut', []))}")
    return {"model": res["secilen"]}


# --- frames (start / end reference images) ------------------------------

JS_FRAME_SLOT = """
(() => {
  const want = %s;   // "Start" or "End"
  const b = [...document.querySelectorAll('button')]
    .filter(e => e.offsetParent !== null)
    .find(e => (e.innerText||'').trim() === want);
  if (!b) return {ok:false, err:want + " kutusu yok - Frames modu acik mi?"};
  b.click();
  return {ok:true};
})()
"""

JS_FRAME_ASSETS = """
JSON.stringify([...document.querySelectorAll('.cdk-overlay-container button')]
  .map(e => (e.innerText||'').replace(/\\n/g,' ').trim())
  .filter(t => t && t !== 'close' && t !== 'Add to prompt'))
"""

JS_FRAME_PICK = """
(async () => {
  const want = %s;
  const btns = () => [...document.querySelectorAll('.cdk-overlay-container button')];
  const label = e => (e.innerText||'').replace(/\\n/g,' ').trim();
  const hit = btns().find(e => label(e).toLowerCase().includes(want.toLowerCase()));
  if (!hit) return {ok:false, mevcut: btns().map(label).filter(Boolean)};
  hit.click();
  await new Promise(r => setTimeout(r, 900));
  const add = btns().find(e => label(e) === 'Add to prompt');
  if (!add) return {ok:false, err:"'Add to prompt' bulunamadi"};
  add.click();
  return {ok:true, secilen: label(hit)};
})()
"""


async def set_frame(cdp, slot, asset):
    """Put an existing project asset into the Start or End frame slot."""
    import asyncio
    r = await cdp.evaluate(JS_FRAME_SLOT % json.dumps(slot))
    if not r.get("ok"):
        raise RuntimeError(r.get("err"))
    await asyncio.sleep(1.8)
    res = await cdp.evaluate(JS_FRAME_PICK % json.dumps(asset), timeout=30)
    if not res.get("ok"):
        raise RuntimeError(
            res.get("err") or
            f"Varlik bulunamadi: {asset}. Mevcut: {', '.join(res.get('mevcut', [])[:8])}")
    await asyncio.sleep(1.2)
    return {"slot": slot, "asset": res["secilen"]}


async def list_frame_assets(cdp, slot="Start"):
    import asyncio
    r = await cdp.evaluate(JS_FRAME_SLOT % json.dumps(slot))
    if not r.get("ok"):
        raise RuntimeError(r.get("err"))
    await asyncio.sleep(1.8)
    assets = json.loads(await cdp.evaluate(JS_FRAME_ASSETS))
    await close_overlay(cdp)
    return assets


# --- upload -------------------------------------------------------------
#
# Flow's own Upload menu item goes through the File System Access API,
# which no CDP domain can intercept, so it would open a native dialog
# nothing here can answer. Dropping the file onto the page reaches the
# same upload path without a dialog.

JS_DROP = """
(() => {
  const b64 = %s, name = %s, type = %s;
  const bin = atob(b64);
  const buf = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
  const file = new File([buf], name, {type});
  const dt = new DataTransfer();
  dt.items.add(file);
  // One target only: several elements carry a drop handler and hitting
  // more than one uploads the file more than once.
  const target = document.querySelector('.ProseMirror') || document.body;
  for (const ev of ['dragenter', 'dragover', 'drop']) {
    target.dispatchEvent(new DragEvent(ev,
      {bubbles: true, cancelable: true, dataTransfer: dt}));
  }
  return {ok: true, bytes: file.size};
})()
"""


# --- quality downloads (upscale) ----------------------------------------
#
# Upscaled renders exist only behind the detail view's download menu:
# there is no signed cdn url for them, so the browser has to perform the
# download and we collect the file it writes.

JS_OPEN_MEDIA = """
(() => {
  const id = %s;
  const el = [...document.querySelectorAll('img, video, source')]
    .find(e => (e.src || '').includes(id));
  if (!el) return {ok:false, err:"Bu id galeride gorunmuyor: " + id};
  let card = el;
  for (let i = 0; i < 5 && card.parentElement; i++) card = card.parentElement;
  const r = card.getBoundingClientRect();
  for (const t of ['pointerdown','mousedown','pointerup','mouseup','click']) {
    card.dispatchEvent(new MouseEvent(t, {bubbles:true,
      clientX: r.x + r.width/2, clientY: r.y + r.height/2}));
  }
  return {ok:true};
})()
"""

JS_DOWNLOAD_OPEN = """
(() => {
  const b = [...document.querySelectorAll('button')]
    .filter(e => e.offsetParent !== null)
    .find(e => (e.innerText||'').trim() === 'download');
  if (!b) return {ok:false, err:"Indirme butonu yok - medya acik mi?"};
  b.click();
  return {ok:true};
})()
"""

JS_DOWNLOAD_OPTIONS = """
JSON.stringify([...document.querySelectorAll(
  '.cdk-overlay-container button, [role=menuitem]')]
  .map(e => (e.innerText||'').replace(/\\n/g,' ').trim()).filter(Boolean))
"""

JS_DOWNLOAD_PICK = """
(() => {
  const want = %s;
  const items = [...document.querySelectorAll(
    '.cdk-overlay-container button, [role=menuitem]')];
  const label = e => (e.innerText||'').replace(/\\n/g,' ').trim();
  const b = items.find(e => label(e).toLowerCase().includes(want.toLowerCase()));
  if (!b) return {ok:false, mevcut: items.map(label).filter(Boolean)};
  b.click();
  return {ok:true, secilen: label(b)};
})()
"""

JS_BACK = """
(() => {
  const b = [...document.querySelectorAll('button')]
    .filter(e => e.offsetParent !== null)
    .find(e => (e.innerText||'').trim() === 'arrow_back');
  if (b) b.click();
  return true;
})()
"""


async def open_media(cdp, media_id):
    import asyncio
    r = await cdp.evaluate(JS_OPEN_MEDIA % json.dumps(media_id))
    if not r.get("ok"):
        raise RuntimeError(r.get("err"))
    await asyncio.sleep(2.5)
    return True


async def download_quality(cdp, media_id, quality, out_dir, timeout=300):
    """Drive the detail view's download menu and capture the written file."""
    import asyncio
    import pathlib

    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    before = {p.name for p in out.iterdir()}

    await open_media(cdp, media_id)
    r = await cdp.evaluate(JS_DOWNLOAD_OPEN)
    if not r.get("ok"):
        raise RuntimeError(r.get("err"))
    await asyncio.sleep(1.8)

    options = json.loads(await cdp.evaluate(JS_DOWNLOAD_OPTIONS))
    await cdp.send("Page.enable")
    await cdp.send("Browser.setDownloadBehavior", {
        "behavior": "allowAndName", "downloadPath": str(out),
        "eventsEnabled": True})

    done = asyncio.get_running_loop().create_future()

    async def watch():
        async for m in cdp.events():
            if m.get("method") in ("Browser.downloadProgress",
                                   "Page.downloadProgress"):
                p = m["params"]
                if p.get("state") == "completed" and not done.done():
                    done.set_result(p)
                    return
                if p.get("state") == "canceled" and not done.done():
                    done.set_exception(RuntimeError("Indirme iptal edildi"))
                    return

    watcher = asyncio.create_task(watch())
    try:
        picked = await cdp.evaluate(JS_DOWNLOAD_PICK % json.dumps(quality))
        if not picked.get("ok"):
            raise RuntimeError(
                f"Kalite bulunamadi: {quality}. Mevcut: "
                f"{', '.join(picked.get('mevcut', []))}")
        try:
            # Upscales are rendered on demand, so this can take minutes.
            await asyncio.wait_for(done, timeout)
        except asyncio.TimeoutError:
            raise RuntimeError(
                f"Indirme {timeout}s icinde bitmedi ({picked['secilen']})")
    finally:
        watcher.cancel()
        await cdp.evaluate(JS_BACK)

    new = [p for p in out.iterdir() if p.name not in before]
    if not new:
        raise RuntimeError("Indirme tamamlandi ama dosya bulunamadi")

    # Chrome names the file by its download guid; give it back an identity.
    src = new[0]
    ext = ".gif" if "gif" in picked["secilen"].lower() else ".mp4"
    tag = picked["secilen"].split()[0]
    dest = src.with_name(f"{media_id}-{tag}{ext}")
    src.replace(dest)
    return {"quality": picked["secilen"], "options": options,
            "path": str(dest), "bytes": dest.stat().st_size}


# --- ingredients (reference images carried into the prompt) --------------

JS_ING_OPEN = """
(() => {
  // The picker hangs off the "+" inside the prompt bar. The header has one
  // too, so take the lowest visible one on the page.
  const adds = [...document.querySelectorAll('button')]
    .filter(e => e.offsetParent !== null && (e.innerText||'').trim() === 'add');
  if (!adds.length) return {ok:false, err:"'+' bulunamadi - Ingredients modu acik mi?"};
  adds.sort((a, b) => a.getBoundingClientRect().y - b.getBoundingClientRect().y);
  adds[adds.length - 1].click();
  return {ok:true};
})()
"""

JS_ING_LIST = """
JSON.stringify([...document.querySelectorAll('.cdk-overlay-container button')]
  .map(e => (e.innerText||'').replace(/\\n/g,' ').trim())
  .filter(t => t && !['close','Add to prompt'].includes(t)))
"""

JS_ING_PICK = """
(() => {
  const wanted = %s;
  const btns = [...document.querySelectorAll('.cdk-overlay-container button')];
  const label = e => (e.innerText||'').replace(/\\n/g,' ').trim();
  const chosen = [], missing = [];
  for (const w of wanted) {
    const b = btns.find(e => label(e).toLowerCase().includes(w.toLowerCase()));
    if (b) { b.click(); chosen.push(label(b)); }
    else missing.push(w);
  }
  return {ok: chosen.length > 0, chosen, missing,
          mevcut: missing.length ? btns.map(label).filter(Boolean) : []};
})()
"""

JS_ING_CONFIRM = """
(() => {
  const b = [...document.querySelectorAll('.cdk-overlay-container button')]
    .find(e => (e.innerText||'').trim() === 'Add to prompt');
  if (!b) return {ok:false, err:"'Add to prompt' bulunamadi"};
  b.click();
  return {ok:true};
})()
"""


async def list_ingredients(cdp):
    import asyncio
    r = await cdp.evaluate(JS_ING_OPEN)
    if not r.get("ok"):
        raise RuntimeError(r.get("err"))
    await asyncio.sleep(1.8)
    assets = json.loads(await cdp.evaluate(JS_ING_LIST))
    await close_overlay(cdp)
    return assets


async def add_ingredients(cdp, assets):
    """Attach one or more existing assets to the prompt as ingredients.

    The picker holds a single selection at a time — choosing a second
    asset drops the first — so each one is attached in its own pass.
    """
    import asyncio

    added, missing = [], []
    for want in assets:
        r = await cdp.evaluate(JS_ING_OPEN)
        if not r.get("ok"):
            raise RuntimeError(r.get("err"))
        await asyncio.sleep(1.8)

        picked = await cdp.evaluate(JS_ING_PICK % json.dumps([want]))
        if not picked.get("ok"):
            missing.append(want)
            await close_overlay(cdp)
            await asyncio.sleep(0.6)
            continue
        await asyncio.sleep(0.6)

        ok = await cdp.evaluate(JS_ING_CONFIRM)
        if not ok.get("ok"):
            await close_overlay(cdp)
            raise RuntimeError(ok.get("err"))
        added.extend(picked["chosen"])
        await asyncio.sleep(1.5)

    if not added:
        raise RuntimeError(f"Hicbiri eklenemedi: {', '.join(missing)}")
    return {"added": added, "missing": missing}


JS_ING_ATTACHED = """
JSON.stringify([...document.querySelectorAll('img')]
  .filter(i => /ingredient/i.test(i.alt || ''))
  .map(i => ({alt: i.alt, src: i.src})))
"""

JS_ING_CLEAR = """
(() => {
  // The remove control sits on an ancestor of the chip, not inside it,
  // so walk outwards from each ingredient thumbnail until one turns up.
  const imgs = [...document.querySelectorAll('img')]
    .filter(i => /ingredient/i.test(i.alt || ''));
  let n = 0;
  for (const img of imgs) {
    let node = img;
    for (let i = 0; i < 5 && node.parentElement; i++) {
      node = node.parentElement;
      const x = [...node.querySelectorAll('button')]
        .find(b => (b.innerText||'').trim() === 'cancel');
      if (x) { x.click(); n++; break; }
    }
  }
  return {removed: n};
})()
"""


async def attached_ingredients(cdp):
    return json.loads(await cdp.evaluate(JS_ING_ATTACHED))


async def clear_ingredients(cdp):
    import asyncio
    r = await cdp.evaluate(JS_ING_CLEAR)
    await asyncio.sleep(1.0)
    return {"removed": r.get("removed", 0),
            "remaining": len(await attached_ingredients(cdp))}
