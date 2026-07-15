# Green 發 Favicon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a traditional green 發 Mahjong-tile favicon to the 牌运 frontend.

**Architecture:** Generate one transparent raster master with an ivory tile face, charcoal outline, and deep-green 發 mark. Package downscaled 16px, 32px, and 48px frames into `favicon.ico`, then reference the asset from the Vite HTML entrypoint.

**Tech Stack:** Pillow image processing, ICO container format, Vite HTML entrypoint.

## Global Constraints

- User-facing product name remains 牌运 · Haiun.
- The favicon must be a traditional ivory Mahjong tile with a centered green 發 and no shadows, glints, or extra decoration.
- The ICO must provide 16px, 32px, and 48px square images and use transparent canvas corners.
- Preserve unrelated user work.

---

### Task 1: Package and reference the favicon

**Files:**
- Create: `frontend/public/favicon.ico`
- Modify: `frontend/index.html:3-7`
- Test: inline Python ICO metadata check

**Interfaces:**
- Consumes: an ICO file at `frontend/public/favicon.ico`.
- Produces: `<link rel="icon" href="/favicon.ico" sizes="any" />` in the document head and browser-readable favicon frames.

- [ ] **Step 1: Verify the missing-asset condition**

Run:

```bash
test ! -f frontend/public/favicon.ico
```

Expected: exit code 0, confirming the favicon must be created.

- [ ] **Step 2: Generate the ICO and add the HTML reference**

Use Pillow to draw a transparent 192px master: a warm ivory rounded Mahjong tile with a thin charcoal stroke and a centered deep-green 發 glyph. Downsample it with a high-quality resampler to 48px, 32px, and 16px frames, save all frames to `frontend/public/favicon.ico`, then add this element beneath the existing viewport meta tag:

```html
<link rel="icon" href="/favicon.ico" sizes="any" />
```

- [ ] **Step 3: Verify the favicon metadata and HTML reference**

Run:

```bash
nix develop -c .venv/bin/python -c "from PIL import Image; im = Image.open('frontend/public/favicon.ico'); assert im.format == 'ICO'; assert set(im.ico.sizes()) == {(16, 16), (32, 32), (48, 48)}; assert im.convert('RGBA').getpixel((0, 0))[3] == 0"
rg -n '<link rel="icon" href="/favicon.ico" sizes="any" />' frontend/index.html
```

Expected: both commands exit 0; the ICO has exactly the three required sizes, transparent corners, and the document head references it.

- [ ] **Step 4: Run the frontend build**

Run:

```bash
nix develop -c npm --prefix frontend run build
```

Expected: exit code 0 and Vite copies `favicon.ico` to `frontend/dist/favicon.ico`.

- [ ] **Step 5: Commit the feature**

```bash
git add frontend/public/favicon.ico frontend/index.html
git commit -m "feat: add green fa favicon"
```
