"""
minecraft_portrait.py
=====================
Turns a photo of your kid into a Minecraft block wall!
Supports both a saved image file AND live laptop camera capture.
Optionally removes the background so only the person appears on the wall.

Requirements:
    pip install mcpi pillow numpy opencv-python rembg

Usage:
    python minecraft_portrait.py                        # camera, keep background
    python minecraft_portrait.py --nobg                 # camera, remove background
    python minecraft_portrait.py photo.jpg              # file, keep background
    python minecraft_portrait.py photo.jpg --nobg       # file, remove background

Background colour (what replaces the person's background on the wall):
    Edit BG_BLOCK near the top of this file.
    Default: Light Blue Wool (35, 3) — looks like sky.

The wall is built starting at your player's current position.
Stand somewhere flat with 100+ blocks of open space in front of you.

Note: the first time --nobg runs it downloads a small AI model (~170 MB).
It is saved to your home folder and reused on every run after that.
"""

import sys
import mcpi.minecraft as minecraft
import mcpi.block as block
from PIL import Image
import numpy as np

# rembg is imported lazily inside remove_background() so the script still
# works even if rembg is not installed — as long as --nobg is not used.

# ─────────────────────────────────────────────────────────────────────────────
# BLOCK PALETTE
# Each entry: (block_id, data_value, display_name, (R, G, B))
# RGB values are the measured average colour of each block's texture.
#
# Design decisions vs the old palette:
#   1. Air block REMOVED — a hole in the wall is never the right answer.
#      The darkest block is now Black Wool (20,21,25) and Dark Terracotta.
#   2. Skin tone ramp EXPANDED — 10 carefully graded entries covering
#      very fair → medium → dark skin, plus shadow and highlight versions.
#      This is the single biggest improvement for portrait quality.
#   3. Hair ramp EXPANDED — 5 entries from near-black to blonde gold.
#   4. Neutral grey ramp EXPANDED — 5 entries so shadows on clothing and
#      faces grade smoothly instead of jumping from black to white.
#   5. All blocks are solid, full-block, placeable via mcpi setBlock().
# ─────────────────────────────────────────────────────────────────────────────
PALETTE = [

    # ── BLACKS & VERY DARK (no Air — use wool/terracotta instead) ───────────
    ( 35,  15, "Black Wool",              ( 20,  21,  25)),
    (159,  15, "Black Terracotta",        ( 37,  22,  16)),  # warm near-black
    ( 87,   0, "Netherrack",              ( 97,  29,  27)),  # dark warm brown-red

    # ── DARK-TO-MID GREYS ────────────────────────────────────────────────────
    ( 35,   7, "Grey Wool",               ( 63,  68,  68)),  # darkest usable grey
    (159,   7, "Grey Terracotta",         (135, 107,  98)),  # warm mid-grey
    (  4,   0, "Cobblestone",             (127, 127, 127)),  # neutral mid grey
    ( 44,   0, "Stone Slab",              (160, 160, 160)),  # lighter grey
    ( 98,   0, "Stone Brick",             (122, 122, 122)),  # slightly blue-grey
    ( 35,   8, "Light Grey Wool",         (142, 142, 142)),  # light grey wool
    ( 80,   0, "Snow Block",              (240, 246, 255)),  # near-white / highlights

    # ── SKIN TONES — the most important ramp for portrait quality ────────────
    # Ordered from darkest to lightest, each ~20-30 RGB units apart.
    (159,  12, "Brown Terracotta",        ( 77,  51,  36)),  # very dark skin / deep shadow
    ( 35,  12, "Brown Wool",              ( 94,  56,  27)),  # dark skin shadow
    (159,   1, "Orange Terracotta",       (162,  84,  38)),  # dark-medium skin
    ( 45,   0, "Brick Block",             (150,  97,  83)),  # medium-dark skin / shadow
    (159,   4, "Yellow Terracotta",       (186, 133,  88)),  # medium skin (general face)
    ( 17,   0, "Oak Log (side)",          (162, 130,  78)),  # warm medium skin tone
    ( 24,   0, "Sandstone",               (213, 193, 138)),  # light-medium skin
    ( 12,   0, "Sand",                    (219, 207, 163)),  # light skin
    ( 35,   6, "Pink Wool",               (237, 141, 172)),  # very fair / pink skin
    ( 35,   0, "White Wool",              (233, 236, 236)),  # palest skin / specular highlight
    (159,   6, "Pink Terracotta",         (161, 115, 112)),  # rosy mid-tone (cheeks/nose)

    # ── HAIR TONES — from near-black to blonde ───────────────────────────────
    (159,  15, "Black Terracotta",        ( 37,  22,  16)),  # already in greys, also hair
    ( 35,  12, "Brown Wool",              ( 94,  56,  27)),  # dark brown hair
    (159,   1, "Orange Terracotta",       (162,  84,  38)),  # chestnut / auburn
    ( 35,   1, "Orange Wool",             (234, 126,  53)),  # light brown / ginger
    ( 41,   0, "Gold Block",              (249, 236,  77)),  # blonde hair / highlight

    # ── WARM REDS & ORANGES ──────────────────────────────────────────────────
    (152,   0, "Redstone Block",          (175,  26,  15)),  # bright red
    ( 35,  14, "Red Wool",                (161,  39,  34)),  # dark red
    (159,  14, "Red Terracotta",          (143,  61,  47)),  # muted dark red

    # ── YELLOWS ──────────────────────────────────────────────────────────────
    ( 35,   4, "Yellow Wool",             (248, 198,  39)),  # bright yellow
    (159,   4, "Yellow Terracotta",       (186, 133,  88)),  # already in skin ramp

    # ── GREENS ───────────────────────────────────────────────────────────────
    ( 18,   1, "Spruce Leaves",           ( 39,  83,  34)),  # dark green
    ( 35,  13, "Green Wool",              ( 84, 124,  12)),  # mid green
    ( 35,   5, "Lime Wool",               (112, 185,  25)),  # bright lime

    # ── BLUES & CYANS ────────────────────────────────────────────────────────
    ( 22,   0, "Lapis Block",             ( 29,  51, 130)),  # dark blue
    ( 35,  11, "Blue Wool",               ( 53,  73, 157)),  # mid blue
    ( 35,   3, "Light Blue Wool",         (107, 176, 212)),  # sky blue
    ( 35,   9, "Cyan Wool",               ( 21, 119, 136)),  # teal
    ( 57,   0, "Diamond Block",           (100, 219, 216)),  # bright cyan

    # ── PURPLES & PINKS ──────────────────────────────────────────────────────
    ( 35,  10, "Purple Wool",             (121,  41, 173)),  # purple
    ( 35,   2, "Magenta Wool",            (179,  78, 189)),  # magenta
]

# Deduplicate by (id, data) — keeps first occurrence if same block appears twice
# (some blocks appear in multiple ramps intentionally; dedup avoids double-counting)
_seen = set()
_deduped = []
for _e in PALETTE:
    _key = (_e[0], _e[1])
    if _key not in _seen:
        _seen.add(_key)
        _deduped.append(_e)
PALETTE = _deduped

# ─────────────────────────────────────────────────────────────────────────────
# BACKGROUND BLOCK
# When background removal is used, transparent pixels are replaced with this
# block in the Minecraft wall.
#   (35,  3) = Light Blue Wool  — looks like sky        ← default
#   ( 4,  0) = Cobblestone      — stone grey border
#   (80,  0) = Snow Block       — clean white border
#   (35,  3) = Light Blue Wool  — open sky feel
# NOTE: do NOT use (0, 0) Air here — it leaves holes in the wall.
# ─────────────────────────────────────────────────────────────────────────────
BG_BLOCK = (35, 3)   # Light Blue Wool

# ─────────────────────────────────────────────────────────────────────────────
# COLOUR MATCHING  —  perceptual weighted Euclidean distance in RGB space
#
# Plain RGB distance treats red, green and blue as equally important.
# But human eyes are most sensitive to green, then red, then blue.
# Weighting the channels to match eye sensitivity gives noticeably better
# colour matching, especially for skin tones and subtle face shadows.
#
# Weights come from the ITU-R BT.709 luminance standard (same weights used
# to convert colour to greyscale in HDTV):
#   green  ×  0.7152  (eyes most sensitive here)
#   red    ×  0.2126
#   blue   ×  0.0722  (eyes least sensitive here)
#
# Example: the difference between two very similar skin tones differing only
# in their red channel looks larger to our eyes than the same difference in
# the blue channel.  Weighting corrects for this so we pick the skin block
# that actually looks most similar, not just the one that's closest in raw
# number terms.
# ─────────────────────────────────────────────────────────────────────────────

# Pre-compute palette as a numpy array for fast vectorised distance calculation
# Shape: (N, 3) — one row per palette entry, columns = R, G, B
_PALETTE_COLORS = np.array([e[3] for e in PALETTE], dtype=np.float32)

# Perceptual weights — multiply each channel before computing distance
_W = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)

def closest_block(r, g, b):
    """
    Return (block_id, data_value, name) for the perceptually closest palette entry.
    Uses weighted Euclidean distance so colour differences match what eyes see.
    Vectorised with numpy — about 30× faster than a Python loop over the palette.
    """
    pixel = np.array([r, g, b], dtype=np.float32)
    # Weighted squared difference for every palette entry at once
    diff  = (_PALETTE_COLORS - pixel) ** 2   # shape: (N, 3)
    dist  = diff @ _W                         # dot product with weights → shape: (N,)
    idx   = int(np.argmin(dist))              # index of closest entry
    entry = PALETTE[idx]
    return entry[0], entry[1], entry[2]       # block_id, data_value, name

# ─────────────────────────────────────────────────────────────────────────────
# CAMERA CAPTURE
# Opens the laptop webcam, shows a live preview window, and waits for the user
# to press SPACE to capture or ESC/Q to cancel.
# Returns a PIL Image, or None if cancelled.
# ─────────────────────────────────────────────────────────────────────────────
def capture_from_camera():
    """
    Show a live camera preview with a square crop guide overlay.
    Controls:
        SPACE  — capture the current frame
        F      — flip / mirror the image (selfie mode)
        ESC/Q  — cancel
    Returns a PIL Image (RGB) or None.
    """
    try:
        import cv2
    except ImportError:
        print("❌  opencv-python is not installed.")
        print("    Run:  pip install opencv-python")
        sys.exit(1)

    print("\n📸  Opening camera …")
    print("    SPACE = capture photo")
    print("    F     = flip / mirror (selfie mode)")
    print("    ESC or Q = cancel\n")

    # Try camera index 0 (built-in webcam). If it fails, try 1.
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        cap = cv2.VideoCapture(1)
    if not cap.isOpened():
        print("❌  Could not open any camera.")
        print("    Make sure your laptop camera is not being used by another app.")
        return None

    # Try to set a decent resolution (camera may ignore this — that's OK)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT,  720)

    flipped       = True    # start in selfie/mirror mode — feels more natural
    captured_pil  = None

    while True:
        ok, frame = cap.read()
        if not ok:
            print("❌  Failed to read from camera.")
            break

        # Mirror mode: flip horizontally so it feels like a mirror
        if flipped:
            frame = cv2.flip(frame, 1)

        h, w = frame.shape[:2]

        # ── Draw a square crop guide in the centre ──────────────────────────
        # The portrait will be cropped to this square, so the kid knows to
        # position their face inside it.
        side      = min(h, w)
        sq_left   = (w - side) // 2
        sq_top    = (h - side) // 2
        sq_right  = sq_left + side
        sq_bottom = sq_top  + side

        # Semi-transparent dark overlay OUTSIDE the square
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)          # full dark
        cv2.rectangle(overlay, (sq_left, sq_top), (sq_right, sq_bottom),
                      (0, 0, 0), -1)                                     # cut out centre
        # We only want the outside to be darkened, so:
        #   alpha-blend: show overlay outside, show frame inside
        mask = np.zeros((h, w), dtype=np.uint8)
        mask[sq_top:sq_bottom, sq_left:sq_right] = 255   # white = keep original
        frame_display = frame.copy()
        outside = cv2.bitwise_and(overlay, overlay,
                                  mask=cv2.bitwise_not(mask))
        inside  = cv2.bitwise_and(frame,   frame,   mask=mask)
        frame_display = cv2.addWeighted(outside, 0.55, frame_display, 0.45, 0)
        frame_display[sq_top:sq_bottom, sq_left:sq_right] = \
            frame[sq_top:sq_bottom, sq_left:sq_right]

        # Bright corner brackets (like a camera viewfinder)
        corner_len = side // 8
        thickness  = 3
        colour     = (100, 255, 100)   # green
        # Top-left
        cv2.line(frame_display, (sq_left,  sq_top),
                 (sq_left + corner_len, sq_top),            colour, thickness)
        cv2.line(frame_display, (sq_left,  sq_top),
                 (sq_left, sq_top  + corner_len),           colour, thickness)
        # Top-right
        cv2.line(frame_display, (sq_right, sq_top),
                 (sq_right - corner_len, sq_top),           colour, thickness)
        cv2.line(frame_display, (sq_right, sq_top),
                 (sq_right, sq_top  + corner_len),          colour, thickness)
        # Bottom-left
        cv2.line(frame_display, (sq_left,  sq_bottom),
                 (sq_left + corner_len, sq_bottom),         colour, thickness)
        cv2.line(frame_display, (sq_left,  sq_bottom),
                 (sq_left, sq_bottom - corner_len),         colour, thickness)
        # Bottom-right
        cv2.line(frame_display, (sq_right, sq_bottom),
                 (sq_right - corner_len, sq_bottom),        colour, thickness)
        cv2.line(frame_display, (sq_right, sq_bottom),
                 (sq_right, sq_bottom - corner_len),        colour, thickness)

        # ── Instructions overlay ─────────────────────────────────────────────
        font       = cv2.FONT_HERSHEY_SIMPLEX
        flip_label = "Mirror: ON  (F to toggle)" if flipped else "Mirror: OFF (F to toggle)"
        cv2.putText(frame_display, "Position face inside the box",
                    (sq_left, sq_top - 18), font, 0.65, (100, 255, 100), 2)
        cv2.putText(frame_display, "SPACE = Capture   ESC/Q = Cancel   F = Flip",
                    (10, h - 12), font, 0.55, (200, 200, 200), 1)
        cv2.putText(frame_display, flip_label,
                    (10, 28),     font, 0.55, (200, 200, 200), 1)

        cv2.imshow("📸 Minecraft Portrait — Camera", frame_display)

        key = cv2.waitKey(1) & 0xFF

        if key == ord('f') or key == ord('F'):
            # Toggle mirror mode
            flipped = not flipped
            print(f"    Mirror mode: {'ON' if flipped else 'OFF'}")

        elif key == 32:  # SPACE — capture!
            # Crop the live frame (not the display frame) to the square
            cropped = frame[sq_top:sq_bottom, sq_left:sq_right]

            # Show a brief "flash" feedback — white frame for 3 frames
            for _ in range(3):
                flash = np.ones_like(frame_display) * 255
                cv2.imshow("📸 Minecraft Portrait — Camera", flash)
                cv2.waitKey(30)
            cv2.imshow("📸 Minecraft Portrait — Camera", frame_display)
            cv2.waitKey(1)

            # Convert OpenCV frame (BGR) to PIL Image (RGB)
            # OpenCV stores colours as Blue-Green-Red; PIL uses Red-Green-Blue
            rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
            captured_pil = Image.fromarray(rgb)

            print("✅  Photo captured!")

            # Show a preview of the captured square for 2 seconds
            preview = cv2.resize(cropped, (500, 500))
            cv2.putText(preview, "Captured! Building in Minecraft...",
                        (10, 480), font, 0.55, (100, 255, 100), 1)
            cv2.imshow("📸 Minecraft Portrait — Camera", preview)
            cv2.waitKey(2000)
            break

        elif key == 27 or key == ord('q') or key == ord('Q'):  # ESC or Q — cancel
            print("    Camera cancelled.")
            captured_pil = None
            break

    cap.release()
    cv2.destroyAllWindows()
    return captured_pil

# ─────────────────────────────────────────────────────────────────────────────
# BACKGROUND REMOVAL
# Uses the rembg library which runs a small AI model (U2Net) locally.
# Input:  any PIL Image (RGB or RGBA)
# Output: PIL Image in RGBA mode — background pixels have alpha = 0 (transparent)
#
# How it works in plain English:
#   1. rembg sends the image through a neural network that has been trained
#      to recognise people vs backgrounds.
#   2. It produces an "alpha mask" — a greyscale image where white = person,
#      black = background, and grey = soft edge (hair, fuzzy edges).
#   3. The mask is applied to the original image as the alpha channel.
#   4. We then use that alpha channel when converting pixels to blocks:
#      fully transparent pixels → BG_BLOCK, everything else → colour match.
# ─────────────────────────────────────────────────────────────────────────────
def remove_background(img):
    """
    Remove the background from a PIL Image using rembg (AI-based).
    Returns a PIL Image in RGBA mode.
    Transparent pixels = background.  Opaque pixels = person.
    """
    try:
        from rembg import remove as rembg_remove
    except ImportError:
        print("❌  rembg is not installed.")
        print("    Run:  pip install rembg")
        sys.exit(1)

    print("🤖  Removing background with AI model …")
    print("    (First run downloads ~170 MB model — saved for future runs)")

    # rembg works directly with PIL Images
    # It returns an RGBA image where the background is transparent
    result = rembg_remove(img)

    # Count how many pixels were kept vs removed, for a nice status message
    pixels    = np.array(result)          # shape: (H, W, 4) — R, G, B, Alpha
    alpha     = pixels[:, :, 3]          # just the alpha channel
    kept      = int(np.sum(alpha > 10))  # pixels that are mostly opaque
    removed   = int(np.sum(alpha <= 10)) # pixels that are mostly transparent
    total     = kept + removed
    kept_pct  = int(kept / total * 100)

    print(f"✅  Background removed!")
    print(f"    Person:     {kept:>7,} pixels  ({kept_pct}%)")
    print(f"    Background: {removed:>7,} pixels  ({100 - kept_pct}%)")
    print(f"    Background will be filled with block id={BG_BLOCK[0]}, data={BG_BLOCK[1]}")

    return result   # RGBA PIL Image


# ─────────────────────────────────────────────────────────────────────────────
# IMAGE PREPARATION
# Crop → enhance contrast → sharpen → resize
#
# Why sharpening matters so much for pixel art:
#   A webcam photo or JPEG has soft edges everywhere — the camera's own lens
#   blur, plus JPEG compression, smooths out sharp boundaries between the nose
#   and skin, or between the eye and the eyelid.  When we shrink to 100×100,
#   LANCZOS resampling averages neighbouring pixels together, softening edges
#   further.  The result: a block-art face where the eyes are two smudged
#   brownish blobs instead of recognisable dark circles.
#
#   The fix is to apply sharpening BEFORE resizing, on the full-resolution
#   image.  We use an "unsharp mask" — despite the name, it ADDS sharpness.
#   It works by:
#     1. Making a blurred copy of the image.
#     2. Subtracting the blur from the original → this is the "edge signal".
#     3. Adding the edge signal back to the original (amplified).
#   Result: edges between skin/eye/hair become more distinct, so after
#   shrinking to 100×100 they still map to clearly different blocks.
#
#   We also boost contrast slightly so that dark features (eyebrows, pupils,
#   nostrils, lip edges) are darker relative to skin, making them easier to
#   distinguish in the limited block palette.
# ─────────────────────────────────────────────────────────────────────────────
def prepare_image(img, size=100):
    """
    Crop to square → boost contrast → sharpen edges → resize to size×size.
    Preserves RGBA mode if present (background-removed images).
    """
    from PIL import ImageEnhance, ImageFilter

    # ── Split alpha out if present ───────────────────────────────────────────
    # We apply all image processing only to the RGB channels.
    # The alpha mask is reattached at the end unchanged.
    has_alpha = (img.mode == "RGBA")
    if has_alpha:
        r, g, b, alpha_ch = img.split()   # split into 4 separate channels
        rgb = Image.merge("RGB", (r, g, b))
    else:
        rgb = img.convert("RGB")

    # ── Step 1: Crop to square (centre crop) ────────────────────────────────
    w, h  = rgb.size
    side  = min(w, h)
    left  = (w - side) // 2
    top   = (h - side) // 2
    rgb   = rgb.crop((left, top, left + side, top + side))
    if has_alpha:
        alpha_ch = alpha_ch.crop((left, top, left + side, top + side))

    # ── Step 2: Boost contrast ───────────────────────────────────────────────
    # Factor 1.0 = no change, 2.0 = double contrast.
    # 1.4 gives noticeably more distinct facial features without
    # making the image look artificial.
    rgb = ImageEnhance.Contrast(rgb).enhance(1.4)

    # ── Step 3: Boost colour saturation slightly ─────────────────────────────
    # Webcam images are often a bit washed out.  Boosting saturation by 1.3×
    # makes skin tones warmer and hair darker relative to skin, which gives
    # the block-matching algorithm more to work with.
    rgb = ImageEnhance.Color(rgb).enhance(1.3)

    # ── Step 4: Unsharp mask — sharpens edges before downscaling ────────────
    # Parameters:
    #   radius  = how far the blur reaches (2 px on the full-res image)
    #   percent = how strongly the edge signal is amplified (180%)
    #   threshold = minimum brightness difference to count as an edge (3/255)
    #              — ignores tiny noise but catches real feature edges
    rgb = rgb.filter(ImageFilter.UnsharpMask(radius=2, percent=180, threshold=3))

    # ── Step 5: Resize to target size with LANCZOS ───────────────────────────
    # LANCZOS (also called Lanczos3) is the highest-quality downscaling filter
    # in Pillow.  It preserves edges better than bilinear or bicubic.
    rgb = rgb.resize((size, size), Image.LANCZOS)
    if has_alpha:
        alpha_ch = alpha_ch.resize((size, size), Image.LANCZOS)

    # ── Reattach alpha channel if we had one ─────────────────────────────────
    if has_alpha:
        r2, g2, b2 = rgb.split()
        img = Image.merge("RGBA", (r2, g2, b2, alpha_ch))
    else:
        img = rgb

    mode_label = "RGBA (background removed)" if has_alpha else "RGB"
    print(f"✅  Image ready: {size}×{size} pixels  [{mode_label}]")
    print(f"    Contrast ×1.4 · Saturation ×1.3 · Unsharp mask applied")
    return img

# ─────────────────────────────────────────────────────────────────────────────
# PIXEL → BLOCK CONVERSION
# ─────────────────────────────────────────────────────────────────────────────
def image_to_blocks(img):
    """
    Convert every pixel of a PIL Image to a Minecraft block.
    Returns a 2D list: grid[row][col] = (block_id, data_value)

    Alpha channel handling (background-removed images):
        - Alpha >= 128  →  opaque pixel  →  colour-match to nearest palette block
        - Alpha <  128  →  transparent   →  use BG_BLOCK (the background fill block)

    For plain RGB images (no alpha), every pixel is colour-matched normally.
    """
    has_alpha = (img.mode == "RGBA")
    pixels    = np.array(img)   # shape: (H, W, 3) or (H, W, 4)
    height, width = pixels.shape[:2]

    print(f"🎨  Mapping {width * height:,} pixels to Minecraft blocks …")
    if has_alpha:
        print(f"    Alpha channel detected — transparent pixels → BG_BLOCK {BG_BLOCK}")

    grid          = []
    unique_blocks = {}
    bg_count      = 0

    for row in range(height):
        block_row = []
        for col in range(width):

            # ── Check alpha first ──────────────────────────────────────────
            if has_alpha:
                alpha = int(pixels[row, col, 3])
                if alpha < 128:
                    # Transparent pixel = background
                    block_row.append(BG_BLOCK)
                    unique_blocks["[Background fill]"] = \
                        unique_blocks.get("[Background fill]", 0) + 1
                    bg_count += 1
                    continue   # skip colour matching for this pixel

            # ── Opaque pixel → colour match ────────────────────────────────
            r = int(pixels[row, col, 0])
            g = int(pixels[row, col, 1])
            b = int(pixels[row, col, 2])
            bid, bdata, bname = closest_block(r, g, b)
            block_row.append((bid, bdata))
            unique_blocks[bname] = unique_blocks.get(bname, 0) + 1

        grid.append(block_row)

    print("\n📦  Blocks used in this portrait:")
    for name, count in sorted(unique_blocks.items(), key=lambda x: -x[1]):
        bar = "█" * min(count // 20, 40)
        print(f"    {name:<22} {count:>5}  {bar}")

    return grid

# ─────────────────────────────────────────────────────────────────────────────
# MINECRAFT WALL BUILDER
#
# Wall placement: in FRONT of the player, facing them
# ─────────────────────────────────────────────────────────────────────────────
#
# How we figure out "in front":
#   Minecraft doesn't give us the player's look direction directly through
#   mcpi.  But we can read it cleverly:
#
#     1. Call mc.player.getPos() twice, 0.1 s apart.
#        While the player stands still the position doesn't change, but
#        Minecraft continuously updates a tiny internal "look" vector.
#
#   Actually mcpi DOES expose the tile entity rotation via getTilePos —
#   but that's unreliable.  The most robust approach without a plugin is:
#
#     2. Use getDirection() — NOT available in stock mcpi.
#
#   So we use the simplest reliable method:
#     - Ask for the player's position (pos).
#     - Ask the player to type the compass direction (N/S/E/W) in the
#       terminal.  This takes 2 seconds and is perfectly reliable.
#     - Alternatively, accept a --dir=N/S/E/W command-line flag to skip
#       the prompt entirely.
#
#   Given the direction, we place the wall DISTANCE blocks ahead and
#   centre it on the player's X or Z position.
#
# Wall coordinate maths (example: player faces NORTH = -Z direction):
#
#   Player at (px, py, pz) facing North (-Z):
#     wall_z   = pz - DISTANCE          (in front, going north)
#     wall_x   = px - width/2           (centred left/right)
#     wall_y   = py                     (ground level, wall rises upward)
#     columns  grow along +X axis       (left to right as player sees it)
#
#   The wall always faces the player — i.e. it is perpendicular to the
#   direction of travel, so the player looks straight at it.
# ─────────────────────────────────────────────────────────────────────────────

def _get_direction(cli_dir):
    """
    Return one of 'N', 'S', 'E', 'W'.
    If cli_dir is already valid, use it.  Otherwise ask the user.
    """
    valid = {'N', 'S', 'E', 'W'}
    if cli_dir and cli_dir.upper() in valid:
        return cli_dir.upper()

    print("\n🧭  Which direction are you FACING in Minecraft?")
    print("    (Look at the F3 debug screen — top left shows 'Facing: north' etc.)")
    print("    N = North   S = South   E = East   W = West")
    while True:
        raw = input("    Enter direction [N/S/E/W]: ").strip().upper()
        if raw in valid:
            return raw
        print("    Please type N, S, E or W.")


def build_wall(mc, blocks_grid, distance=150, facing_dir=None):
    """
    Build the portrait wall DISTANCE blocks in front of the player,
    centred on the player's position, facing back towards the player.

    Parameters
    ----------
    mc           : Minecraft connection
    blocks_grid  : 2D list of (block_id, data_value)
    distance     : how many blocks in front of the player to place the wall
                   (100–200 recommended so the player can see the whole picture)
    facing_dir   : 'N','S','E','W' or None (prompts if None)
    """
    import math, time

    pos    = mc.player.getPos()
    px, py, pz = int(pos.x), int(pos.y), int(pos.z)

    height = len(blocks_grid)
    width  = len(blocks_grid[0])
    total  = height * width

    # ── Work out which direction is "in front" ───────────────────────────────
    direction = _get_direction(facing_dir)

    # For each cardinal direction:
    #   forward_axis: which coordinate axis moves "forward"
    #   forward_sign: +1 or -1 along that axis
    #   side_axis:    which axis spreads the wall left/right
    #   side_sign:    +1 means image col 0 is on the player's LEFT
    #                 (so the image looks correct, not mirrored)
    #
    #   Minecraft compass:  North = -Z,  South = +Z,  East = +X,  West = -X
    #   "In front" of the player = the direction they are facing.
    #   "Wall left/right" = perpendicular to facing direction.
    #   We want col 0 on the player's LEFT so the image isn't mirror-flipped.
    #
    #   Player faces North (-Z): wall spreads along X; col 0 at player's LEFT = -X side
    #   Player faces South (+Z): wall spreads along X; col 0 at player's LEFT = +X side
    #   Player faces East  (+X): wall spreads along Z; col 0 at player's LEFT = -Z side
    #   Player faces West  (-X): wall spreads along Z; col 0 at player's LEFT = +Z side

    DIR_CONFIG = {
        # dir : (forward_axis, forward_sign, side_axis, side_sign, label)
        'N': ('z', -1, 'x', -1, "North (-Z)"),
        'S': ('z', +1, 'x', +1, "South (+Z)"),
        'E': ('x', +1, 'z', -1, "East  (+X)"),
        'W': ('x', -1, 'z', +1, "West  (-X)"),
    }
    fwd_ax, fwd_sign, side_ax, side_sign, dir_label = DIR_CONFIG[direction]

    # Wall anchor = player position + DISTANCE along forward axis
    # Then offset sideways by half the wall width so it's centred
    def wall_coord(fwd_offset, side_offset):
        """Convert (forward, side) offsets into absolute (x, z) coordinates."""
        coords = {'x': px, 'z': pz}
        coords[fwd_ax]  += fwd_sign  * fwd_offset
        coords[side_ax] += side_sign * side_offset
        return coords['x'], coords['z']

    # Centre the wall: side_offset 0 = left edge; width/2 = centre
    side_centre_offset = width // 2

    # Bottom of wall at player's feet; it rises upward
    wall_base_y = py

    print(f"\n🏗️   Building portrait wall …")
    print(f"     Facing:    {dir_label}")
    print(f"     Distance:  {distance} blocks ahead")
    print(f"     Size:      {width} wide × {height} tall = {total:,} blocks")
    wx, wz = wall_coord(distance, 0)
    print(f"     Left edge: X={wx}, Y={wall_base_y}, Z={wz}")
    print(f"     (Wall is centred on your position)\n")

    mc.postToChat(f"Building {width}×{height} portrait, {distance} blocks ahead ...")

    for row in range(height):
        # row 0 = top of image → highest Y
        y = wall_base_y + (height - 1 - row)

        for col in range(width):
            bid, bdata = blocks_grid[row][col]
            # col 0 = left edge of image = leftmost block from player's view
            side_offset = col - side_centre_offset
            bx, bz = wall_coord(distance, side_offset)
            mc.setBlock(bx, y, bz, bid, bdata)

        # Progress report every 10 rows
        if (row + 1) % 10 == 0:
            pct = int((row + 1) / height * 100)
            bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
            print(f"     [{bar}] {pct}%  (row {row + 1}/{height})")
            mc.postToChat(f"Building ... {pct}% done")

    # Teleport the player to a good viewing spot:
    #   Stand DISTANCE/2 blocks back from the wall (= DISTANCE/2 in front of player start)
    #   At eye height + a bit so the whole wall is visible
    view_dist  = distance // 2
    view_y     = wall_base_y + height // 2   # vertically centred on the wall
    vx, vz    = wall_coord(view_dist, 0)

    mc.postToChat("🎉 Portrait complete! Teleporting you to the best view ...")
    time.sleep(1)
    mc.player.setPos(vx, view_y, vz)
    mc.postToChat(f"👀 Look ahead — your portrait is {view_dist} blocks in front of you!")

    print(f"\n🎉  Done! {total:,} blocks placed.")
    print(f"     Teleported to viewing position: X={vx}, Y={view_y}, Z={vz}")
    print(f"     The wall is {view_dist} blocks directly ahead of you.")

# ─────────────────────────────────────────────────────────────────────────────
# TERMINAL ASCII PREVIEW
# ─────────────────────────────────────────────────────────────────────────────
def ascii_preview(grid, pixels):
    """Print a small ASCII art preview of the portrait in the terminal."""
    print("\n🖼️   ASCII preview (every 5th pixel):")
    height = len(grid)
    width  = len(grid[0])
    chars  = " .:-=+*#%@"   # dark → bright

    for row in range(0, height, 5):
        line = ""
        for col in range(0, width, 2):   # 2 chars per pixel keeps the aspect ratio
            r = int(pixels[row, col, 0])
            g = int(pixels[row, col, 1])
            b = int(pixels[row, col, 2])
            brightness = int((r * 0.299 + g * 0.587 + b * 0.114) / 255 * (len(chars) - 1))
            line += chars[brightness] * 2
        print("  " + line)
    print()

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    WALL_SIZE   = 100         # change to 20 for a quick test run!
    ORIENTATION = "vertical"  # "vertical" = wall, "horizontal" = floor mosaic

    # ── Parse command-line arguments ─────────────────────────────────────────
    # Accepted forms (order of flags/file does not matter):
    #   python minecraft_portrait.py
    #   python minecraft_portrait.py photo.jpg
    #   python minecraft_portrait.py --nobg
    #   python minecraft_portrait.py --dir=N
    #   python minecraft_portrait.py --dist=150
    #   python minecraft_portrait.py photo.jpg --nobg --dir=S --dist=120
    args      = sys.argv[1:]
    remove_bg = "--nobg" in args

    # --dir=N/S/E/W  (default None -> will ask)
    facing_dir = None
    for a in args:
        if a.startswith("--dir="):
            facing_dir = a.split("=", 1)[1].upper()

    # --dist=N  distance in blocks (default 150, clamped 20-500)
    wall_dist = 150
    for a in args:
        if a.startswith("--dist="):
            try:
                wall_dist = max(20, min(int(a.split("=", 1)[1]), 500))
            except ValueError:
                print(f"Warning: invalid --dist value, using {wall_dist}")

    file_args  = [a for a in args if not a.startswith("--")]
    image_path = file_args[0] if file_args else None

    print("=" * 60)
    print("  Minecraft Portrait Builder")
    print("=" * 60)
    print(f"  Wall size:          {WALL_SIZE}x{WALL_SIZE} blocks")
    print(f"  Distance in front:  {wall_dist} blocks")
    print(f"  Facing direction:   {facing_dir if facing_dir else '(will ask)'}")
    print(f"  Background removal: {'YES  (--nobg)' if remove_bg else 'no'}")
    print(f"  Background block:   id={BG_BLOCK[0]}, data={BG_BLOCK[1]}")
    print("=" * 60 + "\n")

    # ── Get the image ────────────────────────────────────────────────────────
    if image_path:
        print(f"📷  Loading image from file: {image_path}")
        try:
            raw_img = Image.open(image_path)
        except FileNotFoundError:
            print(f"❌  File not found: {image_path}")
            sys.exit(1)
        except Exception as e:
            print(f"❌  Could not open image: {e}")
            sys.exit(1)
    else:
        print("No image file given — opening laptop camera.")
        print("(You can also run:  python minecraft_portrait.py photo.jpg)\n")
        raw_img = capture_from_camera()
        if raw_img is None:
            print("No photo taken. Exiting.")
            sys.exit(0)

    # ── Remove background (optional) ─────────────────────────────────────────
    # This step happens BEFORE prepare_image so that rembg works on the full
    # resolution image (better edge quality), and prepare_image then resizes
    # the already-masked RGBA image down to WALL_SIZE.
    if remove_bg:
        raw_img = remove_background(raw_img)
        # raw_img is now an RGBA PIL Image — transparent = background

    # ── Prepare image (crop + resize) ────────────────────────────────────────
    img    = prepare_image(raw_img, size=WALL_SIZE)
    pixels = np.array(img)
    grid   = image_to_blocks(img)

    # ── ASCII preview ────────────────────────────────────────────────────────
    ascii_preview(grid, pixels)

    # ── Connect to Minecraft ─────────────────────────────────────────────────
    print("🔌  Connecting to Minecraft via RaspberryJuice …")
    try:
        mc = minecraft.Minecraft.create(address="localhost", port=4711)
        mc.postToChat("Python connected! Preparing portrait …")
        print("✅  Connected!\n")
    except Exception as e:
        print(f"❌  Could not connect to Minecraft: {e}")
        print("\n    Make sure:")
        print("    1. Spigot server is running")
        print("    2. RaspberryJuice plugin is installed and enabled")
        print("    3. You are logged into the game on localhost")
        sys.exit(1)

    # ── Build! ───────────────────────────────────────────────────────────────
    build_wall(mc, grid, distance=wall_dist, facing_dir=facing_dir)


if __name__ == "__main__":
    main()
