---
model: Veo 3.1
flow_models: ["Veo 3.1 - Lite", "Veo 3.1 - Fast", "Veo 3.1 - Quality"]
source: https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1
retrieved: 2026-09-08
---

## Formula

`[Cinematography] + [Subject] + [Action] + [Context] + [Style & ambiance]`

- **Cinematography** — camera work and shot composition
- **Subject** — the main character or focal point
- **Action** — what the subject is doing
- **Context** — environment and background elements
- **Style & ambiance** — overall aesthetic, mood, lighting

Example:

> Medium shot, a tired corporate worker, rubbing his temples in exhaustion, in
> front of a bulky 1980s computer in a cluttered office late at night. The scene
> is lit by the harsh fluorescent overhead lights and the green glow of the
> monochrome monitor. Retro aesthetic, shot as if on 1980s color film, slightly
> grainy.

## Cinematography vocabulary

Camera movement: dolly shot, tracking shot, crane shot, aerial view, slow pan,
POV shot.

Composition: wide shot, close-up, extreme close-up, low angle, two-shot.

Lens and focus: shallow depth of field, wide-angle lens, soft focus, macro lens,
deep focus.

## Audio and dialogue

- **Dialogue** — put speech in quotation marks: `A woman says, "We have to leave now."`
- **Sound effects** — `SFX: thunder cracks in the distance`
- **Ambient noise** — `Ambient noise: the quiet hum of a starship bridge.`

## Negative prompting

Describe what should be absent in positive, descriptive language rather than
negations: prefer "a desolate landscape with no buildings or roads" over
"no man-made structures".

## Timestamp prompting

Multi-shot sequences can be scripted with explicit time ranges:

```
[00:00-00:02] Medium shot from behind a young female explorer with a leather
satchel and messy brown hair in a ponytail, as she pushes aside a large jungle
vine to reveal a hidden path.

[00:02-00:04] Reverse shot of the explorer's freckled face, her expression filled
with awe as she gazes upon ancient, moss-covered ruins in the background.
SFX: The rustle of dense leaves, distant exotic bird calls.

[00:04-00:06] Tracking shot following the explorer as she steps into the clearing
and runs her hand over the intricate carvings on a crumbling stone wall.
Emotion: Wonder and reverence.

[00:06-00:08] Wide, high-angle crane shot, revealing the lone explorer standing
small in the center of the vast, forgotten temple complex, half-swallowed by the
jungle. SFX: A swelling, gentle orchestral score begins to play.
```

## Ingredients (reference images)

Supply references for a scene, character, object or style to hold a consistent
look across shots. Repeat the same reference phrasing in every shot of a
sequence:

> Using the provided images for the detective, the woman, and the office setting,
> create a medium shot of the detective behind his desk. He looks up at the woman
> and says in a weary voice, "Of all the offices in this town, you had to walk
> into mine."

Maps to this server's `flow_ingredient`.

## First and last frame

Generates a transition between a supplied start image and end image, with audio.
Good for controlled camera moves and transformations. Describe the move itself,
not the two frames:

> The camera performs a smooth 180-degree arc shot, starting with the front-facing
> view of the singer and circling around her to seamlessly end on the POV shot
> from behind her on stage.

Maps to this server's `flow_frame`.

## Limits

720p or 1080p; 16:9 or 9:16; clips of 4, 6 or 8 seconds. All output carries a
SynthID watermark.

Note: "add/remove object" runs on Veo 2 and produces no audio.
