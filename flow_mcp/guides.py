"""Prompting guides, served to the agent on request.

These are reference material, never applied automatically: an agent that
silently rewrote the user's prompt would ship something the user never
saw. The agent reads what it needs and writes its own prompt.

Each file is Markdown with a small yaml-ish header naming the source and
the date it was retrieved, so an agent can judge whether the advice still
matches the models Flow is currently offering.
"""
import pathlib
import re

GUIDE_DIR = pathlib.Path(__file__).resolve().parent.parent / "guides"


def _parse(path):
    text = path.read_text()
    meta, body = {}, text
    if text.startswith("---\n"):
        head, _, body = text[4:].partition("\n---\n")
        for line in head.splitlines():
            key, _, val = line.partition(":")
            val = val.strip()
            if val.startswith("[") and val.endswith("]"):
                val = [v.strip().strip('"') for v in val[1:-1].split(",") if v.strip()]
            meta[key.strip()] = val
    return meta, body.strip()


def _sections(body):
    """Split a guide body on its level-2 headings."""
    out, name, buf = {}, None, []
    for line in body.splitlines():
        if line.startswith("## "):
            if name:
                out[name] = "\n".join(buf).strip()
            name, buf = line[3:].strip(), []
        else:
            buf.append(line)
    if name:
        out[name] = "\n".join(buf).strip()
    return out


def load():
    guides = {}
    if not GUIDE_DIR.is_dir():
        return guides
    for path in sorted(GUIDE_DIR.glob("*.md")):
        meta, body = _parse(path)
        guides[path.stem] = {
            "meta": meta,
            "sections": _sections(body),
        }
    return guides


def _match(guides, model):
    """Find the guide covering a model, by file name or by Flow's label."""
    want = model.strip().lower()
    if want in guides:
        return want
    for key, g in guides.items():
        names = [str(n).lower() for n in g["meta"].get("flow_models", [])]
        names.append(str(g["meta"].get("model", "")).lower())
        if any(want == n or want in n or n in want for n in names if n):
            return key
    # Fall back to a loose word match: "veo 3.1 - quality" -> "veo-3.1"
    slug = re.sub(r"[^a-z0-9]+", "-", want).strip("-")
    for key in guides:
        if key in slug or slug.startswith(key):
            return key
    return None


def index():
    """Which guides exist, and what each one covers."""
    guides = load()
    if not guides:
        return {"error": f"Rehber bulunamadi: {GUIDE_DIR}"}
    return {
        "guides": [
            {
                "id": key,
                "model": g["meta"].get("model"),
                "flow_models": g["meta"].get("flow_models", []),
                "source": g["meta"].get("source"),
                "retrieved": g["meta"].get("retrieved"),
                "sections": list(g["sections"]),
            }
            for key, g in guides.items()
        ],
        "kullanim": "flow_prompt_guide(model=..., section=...) ile bolum cek",
    }


def get(model, section=""):
    guides = load()
    if not guides:
        return {"error": f"Rehber bulunamadi: {GUIDE_DIR}"}
    key = _match(guides, model)
    if not key:
        return {"error": f"Bu model icin rehber yok: {model}",
                "mevcut": list(guides)}

    g = guides[key]
    head = {"guide": key, "model": g["meta"].get("model"),
            "source": g["meta"].get("source"),
            "retrieved": g["meta"].get("retrieved")}

    if not section:
        return {**head, "sections": list(g["sections"]),
                "formula": g["sections"].get("Formula")
                        or g["sections"].get("Bes bilesen")
                        or next(iter(g["sections"].values()), "")}

    want = section.strip().lower()
    for name, text in g["sections"].items():
        if want == name.lower() or want in name.lower():
            return {**head, "section": name, "text": text}
    return {**head, "error": f"Bolum yok: {section}",
            "sections": list(g["sections"])}
