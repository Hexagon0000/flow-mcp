# flow-mcp

Exposes Google Flow to local agents (Claude Code, Cursor, Codex) over MCP.

It attaches to a Chrome you started yourself, so your own Google session and
**AI Pro quota** are used as-is. No API key, no extra cost.

## How it works

Under the UI, Flow talks to Google's `batchexecute` RPC protocol. The server
splits the work in two:

| Task | Method | Why |
|---|---|---|
| Status polling, media URLs | Direct RPC (`as29s`) | No captcha required; keeps working when the DOM changes |
| Starting a generation | Driving the real UI | The request carries a reCAPTCHA Enterprise token that only Flow's own JS can mint |
| Settings panel | Driving the UI | Settings travel with the request; there is no separate RPC for them |

Flow uses a different RPC for each generation path (plain video, image,
start/end frames …), and where the media id sits in the response also
depends on the path. So no RPC id or index is hard-coded: after the click,
every UUID in every `batchexecute` response is collected and checked
against the media service, and the ones that actually exist are taken as
media ids. If Flow adds a new generation path, this keeps working on its own.

No Playwright — Chrome is driven over raw CDP, and the only dependencies
are `mcp` + `websockets`.

## Installation

```bash
git clone https://github.com/Hexagon0000/flow-mcp.git
cd flow-mcp
python3 -m venv .venv && ./.venv/bin/pip install -e .
```

## Usage

1. Start Chrome in debug mode:

   ```bash
   ./scripts/start-chrome.sh
   ```

   The profile is empty on first launch — sign in to your Google account
   **manually**. The session persists in `~/.flow-mcp-profile`. Chrome
   opens the `flow.google.com` home page; if no project is open, the server
   **creates a new project by itself**.

2. Connect your agent (see below).

### Start automatically at login

To avoid running the command every time:

```bash
./scripts/install-launchd.sh
```

This installs a LaunchAgent; Chrome starts at login with the debug port
open and Flow loaded. Logs live in `~/Library/Logs/flow-mcp/`.

`KeepAlive` is deliberately off: if you quit this Chrome, you meant to, and
launchd should not drag it back. Add `KeepAlive` to the plist if you want it
running no matter what.

To uninstall:

```bash
launchctl bootout gui/$UID/com.flow-mcp.chrome && rm ~/Library/LaunchAgents/com.flow-mcp.chrome.plist
```

## How agents use it

The server introduces itself through the MCP protocol's `instructions`
field: every connecting client (Claude Code, Cursor, Codex) sees the
workflow and the credit warning automatically. If the tab is on the home
page, a new project is opened on its own.

One tool covers most requests:

```
flow_create("a purple mountain silhouette", kind="image")
flow_create("misty forest", kind="video", duration="8s", aspect="9:16")
```

A Claude Code skill file ships in the repo at `skills/flow/SKILL.md`:

```bash
mkdir -p ~/.claude/skills/flow
cp skills/flow/SKILL.md ~/.claude/skills/flow/SKILL.md
```

## Tools

| Tool | Description |
|---|---|
| **`flow_create(prompt, kind)`** | **One call: configure, generate, wait, download** |
| `flow_project` | Id and name of the open project; opens a new one if there is none |
| `flow_settings(options)` | Reads or changes the settings panel |
| `flow_model(name)` | Lists or selects models |
| `flow_frame(slot, asset)` | Sets the Start/End frame from an asset in the project |
| `flow_upload(file_path)` | Uploads a local image to the project |
| `flow_ingredient(assets, clear)` | Adds reference images to the prompt |
| `flow_download_quality(media_id, quality)` | Downloads 270p GIF / 720p / 1080p / 4K |
| `flow_prompt_guide(model, section)` | Google's prompt guide for that model |
| `flow_generate(prompt)` | Starts a generation, **does not wait**, returns the media id |
| `flow_status(media_id)` | `pending` / `done` / `not_found`, type (`video`/`image`) and URL when ready |
| `flow_download(media_id, filename)` | Saves a finished video/image to disk |

Videos and images are generated with the same tools; the mode you pick
with `flow_settings` decides which one you get.

Generation takes minutes, so `flow_generate` is intentionally asynchronous.
The agent starts a generation, carries on with its work, then polls with
`flow_status`.

## Agent configuration

**Claude Code** — `mcpServers` in `~/.claude.json`, or:

```bash
claude mcp add flow -- /ABS/PATH/flow-mcp/.venv/bin/python -m flow_mcp.server
```

**Cursor** — `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "flow": {
      "command": "/ABS/PATH/flow-mcp/.venv/bin/python",
      "args": ["-m", "flow_mcp.server"]
    }
  }
}
```

**Codex** — `~/.codex/config.toml`:

```toml
[mcp_servers.flow]
command = "/ABS/PATH/flow-mcp/.venv/bin/python"
args = ["-m", "flow_mcp.server"]
```

## Prompt guides

`guides/` holds three files distilled from Google's own guides: Veo 3.1,
Nano Banana and Gemini Omni. Each file starts with its source URL and
retrieval date.

```
flow_prompt_guide()                              # which guides exist
flow_prompt_guide("Veo 3.1 - Fast")              # formula + section list
flow_prompt_guide("Veo 3.1 - Fast", "Audio")     # a single section
```

The model name matches the label Flow shows in its panel, with loose
matching on top.

**Design decision:** the guide is not applied to the prompt automatically.
If the agent silently sent a rewritten prompt, the user could not see what
was sent or figure out why the output drifted. Instead the guide is
*shown* to the agent, and the agent writes the prompt. The tool is
optional; an agent that finds it inconsistent can skip it.

Cost: ~110 tokens per section, ~270 for a model summary. The full guides
would be ~2300 tokens — which is why they are served section by section.

Guides can go stale. Compare the `retrieved` date in the response with the
output of `flow_model()`; if a model is missing from the guide, don't
trust it.

## Configuration

| Variable | Default |
|---|---|
| `FLOW_CDP_PORT` | `9222` |
| `FLOW_CHROME_PROFILE` | `~/.flow-mcp-profile` |
| `FLOW_DOWNLOAD_DIR` | `~/Downloads/flow` |

### Generation settings

Called without arguments, `flow_settings()` returns the current selection
and all available options. To change them, pass the labels exactly:

```
flow_settings(["Video", "9:16", "720p", "8s", "x2"])
flow_settings(["Image", "1:1", "x4"])
```

`Video` / `Image` must always come first — switching mode replaces the
rest of the panel entirely.

| Setting | Options |
|---|---|
| Mode | `Image`, `Video` |
| Aspect ratio (video) | `16:9`, `9:16` |
| Aspect ratio (image) | `16:9`, `4:3`, `1:1`, `3:4`, `9:16` |
| Resolution | `360p`, `720p` (video only) |
| Duration | `4s`, `6s`, `8s`, `10s` (video only) |
| Output count | `x1` … `x4` |

### Model

```
flow_model()                      # models available in the current mode
flow_model("Veo 3.1 - Quality")
```

The list depends on the mode: on the video side `Omni 1.1 Flash`,
`Veo 3.1 - Lite / Fast / Quality`; on the image side `Nano Banana Pro`,
`Nano Banana 2`, `Nano Banana 2 Lite`.

### Start / end frames

```
flow_settings(["Video", "Frames"])
flow_frame("Start")                       # lists the assets you can pick
flow_frame("Start", "Green triangle")
flow_frame("End", "Orange fox")
flow_generate("the triangle turns into a fox")
```

In Frames mode Flow hides the resolution and duration options — they
cannot be set in that mode.

### Ingredients (reference images)

```
flow_settings(["Video", "Ingredients"])
flow_ingredient()                                  # attached ones + options
flow_ingredient(["triangle", "Orange fox"])        # add
flow_ingredient(clear=True)                        # remove all
```

The difference from Frames: Frames pin the two end frames, while
Ingredients are reference images carried into the prompt, with no limit on
how many. Ingredients mode keeps the resolution and duration options
(Frames loses them).

The picker holds one asset at a time, so the tool adds each one in a
separate round. An asset that is already attached drops out of the picker
list — to add it again, call `clear=True` first.

### Uploading images

```
flow_upload("~/Desktop/character.png")
```

Flow's own `Upload` menu uses the File System Access API, which no CDP
domain can intercept; it would open a system dialog nobody can answer. So
the file is dropped onto the page (drag-and-drop) to reach the same upload
path. The uploaded image can then be used as a frame with `flow_frame`.

### High-quality / upscaled downloads

```
flow_download_quality(media_id, "1080p")
```

| Option | Note |
|---|---|
| `270p` | Animated GIF |
| `720p` | Original |
| `1080p` | Upscale, **free** |
| `4K` | Upscale, **costs credits** — requires `confirm_paid=True` |

Upscales are rendered on demand and can take minutes. This download does
not go through a signed URL; it captures the browser's own download
instead — upscaled output has no CDN address.

Image generation with Nano Banana Pro costs 0 credits; video costs credits —
check the credit cost shown in the panel before generating.

## If the UI changes

Since the generation path depends on the DOM, it can break when Flow's UI
changes. `recon/sniff.py` captures the network traffic again:

```bash
./.venv/bin/python recon/sniff.py 120
```

Run a generation by hand while the script is running, then copy the new
RPC ids from `recon/capture.json` into the constants at the top of
`flow_mcp/flow.py`.

## Disclaimer

Automation is a grey area under Google's terms of service. This is meant
for personal use; the risk to your account is not zero.

## License

[MIT](LICENSE)
