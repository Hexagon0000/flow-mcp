---
model: Nano Banana
flow_models: ["Nano Banana Pro", "Nano Banana 2", "Nano Banana 2 Lite"]
source: https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-nano-banana
retrieved: 2026-09-08
---

## Formula

Text to image:

`[Subject] + [Action] + [Location/context] + [Composition] + [Style]`

> [Subject] A striking fashion model wearing a tailored brown dress, sleek boots,
> and holding a structured handbag. [Action] Posing with a confident, statuesque
> stance, slightly turned. [Location/context] A seamless, deep cherry red studio
> backdrop. [Composition] Medium-full shot, center-framed. [Style] Fashion
> magazine style editorial, shot on medium-format analog film, pronounced grain,
> high saturation, cinematic lighting effect.

With reference images:

`[Reference images] + [Relationship instruction] + [New scenario]`

> Using the attached napkin sketch as the structure and the attached fabric sample
> as the texture, transform this into a high-fidelity 3D armchair render. Place it
> in a sun-drenched, minimalist living room.

## Best practices

1. **Be specific** about subject, lighting and composition.
2. **Frame positively** — say "empty street", not "no cars".
3. **Control the camera** with photographic terms: "low angle", "aerial view".
4. **Iterate** conversationally rather than rewriting the whole prompt.
5. **Start with a strong verb** naming the primary operation.

## Creative direction

**Lighting** — "three-point softbox setup" for even product light;
"chiaroscuro lighting with harsh, high contrast"; "golden hour backlighting
creating long shadows".

**Camera and lens** — naming hardware changes the visual DNA: GoPro for an
immersive distorted action feel, Fujifilm for its colour science, a disposable
camera for a raw nostalgic flash look. Control depth with "shallow depth of
field (f/1.8)", "wide-angle lens" for scale, "macro lens" for detail.

**Colour grade** — "rendered as if on 1980s color film, slightly grainy";
"cinematic color grading with muted teal tones".

**Material and texture** — name the physical makeup rather than the object:
"navy blue tweed" over "suit jacket"; "ornate elven plate armor, etched with
silver leaf patterns" over "armor".

## Text rendering

1. Put the wanted words **in quotes**: `"URBAN EXPLORER"`.
2. Name the typography: `"bold, white, sans-serif font"`, `"Century Gothic 12px"`.
3. To localise, write the prompt in one language and name the target language for
   the rendered text.
4. Text-first trick: settle the wording in conversation, then ask for the image.

> A high-end, glossy commercial beauty shot of a sleek, minimalist nude-colored
> face moisturizer jar resting on a warm studio background. The lighting is soft
> and radiant. Next to the product, render three lines of text with the following
> exact styling: For the top line, the word 'GLOW' in a flowing, elegant Brush
> Script font. For the middle line, the text '10% OFF' in a heavy, blocky Impact
> font. For the bottom line, the text 'Your First Order' in a thin, minimalist
> Century Gothic font.

Text as a window into a photograph:

> A typographic poster with a solid black background, bold letters spell
> "New York", filling the center of the frame. The text acts as a cut-out window.
> A photograph of New York skyline is visible ONLY inside the letterforms.

## Editing

For conversational edits, be explicit about what must stay unchanged. Simple
instructions work: "Remove the man from the photo". Style transfer works by
asking for the same content recreated in another style.

## Limits

Resolutions 1K, 2K, 4K (Nano Banana 2 also 512px). Aspect ratios 1:1, 3:2, 2:3,
3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9 — Nano Banana 2 adds 1:4, 4:1, 1:8, 8:1.
Up to 14 reference images per prompt. Output carries C2PA credentials and a
SynthID watermark.

**Flow'da dikkat:** Flow'un görsel paneli bu oranların yalnızca bir alt kümesini
sunuyor (16:9, 4:3, 1:1, 3:4, 9:16). Rehberdeki diğer oranları Flow üzerinden
seçemezsin.
