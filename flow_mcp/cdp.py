"""Minimal Chrome DevTools Protocol client over websockets.

No Playwright: we attach to a Chrome the user launched with
--remote-debugging-port and drive it with raw CDP messages.
"""
import asyncio
import json
import urllib.request

import websockets

DEFAULT_PORT = 9222


def _http_json(port, path):
    url = f"http://localhost:{port}/json{path}"
    with urllib.request.urlopen(url, timeout=5) as r:
        return json.loads(r.read())


def find_page(port=DEFAULT_PORT, url_contains="flow.google.com"):
    """Return the debug target for the Flow tab to drive.

    A tab sitting on a project is preferred over one on the Flow home
    page: everything here acts on the open project, and the launch agent
    opens the home page, so both can be present at once.
    """
    pages = [t for t in _http_json(port, "/list") if t.get("type") == "page"]
    matches = [t for t in pages if url_contains in t.get("url", "")]
    for t in matches:
        if "/project/" in t.get("url", ""):
            return t
    if matches:
        return matches[0]
    if not pages:
        raise RuntimeError(
            f"Chrome'da acik sekme yok. Debug portu {port} dogru mu?"
        )
    raise RuntimeError(
        f"'{url_contains}' iceren sekme bulunamadi. Acik olanlar: "
        + ", ".join(t.get("url", "")[:60] for t in pages)
    )


class CDPSession:
    """One websocket connection to a single page target."""

    def __init__(self, ws_url):
        self.ws_url = ws_url
        self._ws = None
        self._msg_id = 0
        self._pending = {}
        self._events = asyncio.Queue()
        self._reader = None

    async def __aenter__(self):
        # Flow's payloads are large; raise the frame cap well above default.
        self._ws = await websockets.connect(self.ws_url, max_size=64 * 1024 * 1024)
        self._reader = asyncio.create_task(self._read_loop())
        return self

    async def __aexit__(self, *exc):
        if self._reader:
            self._reader.cancel()
        if self._ws:
            await self._ws.close()

    async def _read_loop(self):
        async for raw in self._ws:
            msg = json.loads(raw)
            if "id" in msg:
                fut = self._pending.pop(msg["id"], None)
                if fut and not fut.done():
                    fut.set_result(msg)
            else:
                await self._events.put(msg)

    async def send(self, method, params=None, timeout=30):
        self._msg_id += 1
        mid = self._msg_id
        fut = asyncio.get_running_loop().create_future()
        self._pending[mid] = fut
        await self._ws.send(json.dumps({"id": mid, "method": method,
                                        "params": params or {}}))
        msg = await asyncio.wait_for(fut, timeout)
        if "error" in msg:
            raise RuntimeError(f"{method} basarisiz: {msg['error']}")
        return msg.get("result", {})

    async def events(self):
        """Async iterator over protocol events."""
        while True:
            yield await self._events.get()

    async def evaluate(self, expression, timeout=30):
        """Run JS in the page and return the JSON-serialised result."""
        res = await self.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        }, timeout=timeout)
        if "exceptionDetails" in res:
            desc = res["exceptionDetails"].get("exception", {}).get(
                "description", res["exceptionDetails"])
            raise RuntimeError(f"JS hatasi: {desc}")
        return res.get("result", {}).get("value")


async def open_page(port=DEFAULT_PORT, url_contains="flow.google.com"):
    target = find_page(port, url_contains)
    return CDPSession(target["webSocketDebuggerUrl"]), target
