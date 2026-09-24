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
# RGB values are the approximate average colour of each block's texture.
# ─────────────────────────────────────────────────────────────────────────────
PALETTE = [
    # ID    DAT  NAME                    R    G    B
    (  0,   0, "Air (shadow)",        ( 40,  40,  40)),  # very dark / deep shadow
    ( 22,   0, "Lapis Block",         ( 29,  51, 130)),  # dark blue
    ( 35,  11, "Blue Wool",           ( 53,  73, 157)),  # mid blue
    ( 35,   3, "Light Blue Wool",     (107, 176, 212)),  # sky blue
    ( 35,   9, "Cyan Wool",           ( 21, 119, 136)),  # teal
    ( 18,   1, "Spruce Leaves",       ( 39,  83,  34)),  # dark green
    ( 35,  13, "Green Wool",          ( 84, 124,  12)),  # mid green
    ( 35,   5, "Lime Wool",           (112, 185,  25)),  # bright green
    ( 17,   0, "Oak Log",             (116,  85,  42)),  # dark brown (hair/bark)
    (  4,   0, "Cobblestone",         (128, 128, 128)),  # medium grey
    ( 44,   0, "Stone Slab",          (163, 163, 163)),  # light grey
    ( 80,   0, "Snow Block",          (240, 246, 255)),  # white / bright highlights
    ( 35,  14, "Red Wool",            (161,  39,  34)),  # dark red
    ( 35,   1, "Orange Wool",         (234, 126,  53)),  # orange
    ( 35,   4, "Yellow Wool",         (248, 198,  39)),  # yellow
    ( 35,   0, "White Wool",          (233, 236, 236)),  # near-white
    ( 24,   0, "Sandstone",           (220, 202, 134)),  # sandy / skin mid-tone
    ( 12,   0, "Sand",                (219, 207, 163)),  # light skin tone
    ( 35,  12, "Brown Wool",          ( 94,  56,  27)),  # dark skin / dark hair
    ( 35,   2, "Magenta Wool",        (179,  78, 189)),  # purple / pink
    ( 35,   6, "Pink Wool",           (237, 141, 172)),  # pink / light skin
    ( 35,  10, "Purple Wool",         (121,  41, 173)),  # purple
    ( 41,   0, "Gold Block",          (249, 236,  77)),  # bright gold / blonde hair
    ( 57,   0, "Diamond Block",       (100, 219, 216)),  # bright cyan
    (152,   0, "Redstone Block",      (175,  26,  15)),  # bright red
    ( 35,   7, "Grey Wool",           ( 63,  68,  68)),  # dark grey
    ( 35,  15, "Black Wool",          ( 20,  21,  25)),  # near-black
    ( 87,   0, "Netherrack",          (100,  31,  29)),  # dark red-brown
    ( 45,   0, "Brick",               (150,  97,  83)),  # brick / medium skin
]

# ─────────────────────────────────────────────────────────────────────────────
# BACKGROUND BLOCK
# When background removal is used, transparent pixels are replaced with this
# block in the Minecraft wall.
# Change to any (block_id, data_value) pair from the palette above.
#   (35, 3)  = Light Blue Wool  — looks like sky      ← default
#   ( 0, 0)  = Air              — leaves holes in wall
#   ( 4, 0)  = Cobblestone      — grey stone border
#   (80, 0)  = Snow Block       — clean white border
# ─────────────────────────────────────────────────────────────────────────────
BG_BLOCK = (35, 3)   # Light Blue Wool

# ─────────────────────────────────────────────────────────────────────────────
# COLOUR MATCHING
# Find the closest palette block for a given RGB pixel using Euclidean distance
# in RGB colour space — the same distance formula as in normal 3D geometry!
#   distance = sqrt( (r-pr)^2 + (g-pg)^2 + (b-pb)^2 )
# We skip sqrt because we only need to compare, not measure the real distance.
# ─────────────────────────────────────────────────────────────────────────────
def closest_block(r, g, b):
    """Return (block_id, data_value, name) for the palette colour nearest (r,g,b)."""
    best_dist  = float('inf')
    best_entry = PALETTE[0]
    for entry in PALETTE:
        pr, pg, pb = entry[3]
        dist = (r - pr)**2 + (g - pg)**2 + (b - pb)**2
        if dist < best_dist:
            best_dist  = dist
            best_entry = entry
    return best_entry[0], best_entry[1], best_entry[2]   # id, data, name

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
# Crop to square, resize to target size, optionally enhance contrast
# ─────────────────────────────────────────────────────────────────────────────
def prepare_image(img, size=100):
    """
    Crop to a centre square, resize to size×size.
    Preserves RGBA if the image has an alpha channel (i.e. after background removal).
    img can be a PIL Image from a file, the camera, or rembg output.
    """
    # Keep RGBA if it has one (background-removed image), otherwise use RGB
    if img.mode == "RGBA":
        pass          # keep the alpha channel intact
    else:
        img = img.convert("RGB")

    # Crop to square using the centre
    w, h  = img.size
    side  = min(w, h)
    left  = (w - side) // 2
    top   = (h - side) // 2
    img   = img.crop((left, top, left + side, top + side))

    # Resize with high-quality LANCZOS filter
    img = img.resize((size, size), Image.LANCZOS)
    mode_label = "RGBA (background removed)" if img.mode == "RGBA" else "RGB"
    print(f"✅  Image ready: {size}×{size} pixels  [{mode_label}]")
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
# ─────────────────────────────────────────────────────────────────────────────
def build_wall(mc, blocks_grid, orientation="vertical"):
    """
    Place all blocks in Minecraft, starting 2 blocks in front of the player.

    orientation:
        "vertical"   — upright wall  (width=X, height=Y)
        "horizontal" — floor mosaic  (width=X, depth=Z)
    """
    pos     = mc.player.getPos()
    start_x = int(pos.x) + 2
    start_y = int(pos.y)
    start_z = int(pos.z)

    height = len(blocks_grid)
    width  = len(blocks_grid[0])
    total  = height * width

    print(f"\n🏗️   Building wall at ({start_x}, {start_y}, {start_z}) …")
    print(f"     {width} wide × {height} tall = {total:,} blocks\n")
    mc.postToChat(f"Building portrait — {total} blocks! Stand back!")

    for row in range(height):
        y = start_y + (height - 1 - row)   # row 0 = top → highest Y

        for col in range(width):
            bid, bdata = blocks_grid[row][col]
            if orientation == "vertical":
                mc.setBlock(start_x + col, y, start_z, bid, bdata)
            else:
                mc.setBlock(start_x + col, start_y, start_z + row, bid, bdata)

        # Progress every 10 rows
        if (row + 1) % 10 == 0:
            pct = int((row + 1) / height * 100)
            bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
            print(f"     [{bar}] {pct}%  (row {row + 1}/{height})")
            mc.postToChat(f"Building ... {pct}% done")

    mc.postToChat("🎉 Portrait complete! Come and see!")
    print(f"\n🎉  Done! {total:,} blocks placed.")
    print(f"     Wall starts at X={start_x}, Y={start_y}, Z={start_z}")
    print(f"     Fly about 60 blocks away for the best view!")

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
    # Accepted forms:
    #   python minecraft_portrait.py
    #   python minecraft_portrait.py --nobg
    #   python minecraft_portrait.py photo.jpg
    #   python minecraft_portrait.py photo.jpg --nobg
    #   python minecraft_portrait.py --nobg photo.jpg   (order doesn't matter)
    args       = sys.argv[1:]                          # everything after the script name
    remove_bg  = "--nobg" in args                      # True if --nobg flag present
    file_args  = [a for a in args if not a.startswith("--")]  # non-flag arguments
    image_path = file_args[0] if file_args else None   # first non-flag = filename

    print("=" * 56)
    print("  🧱  Minecraft Portrait Builder")
    print("=" * 56)
    print(f"  Wall size:          {WALL_SIZE}×{WALL_SIZE} blocks")
    print(f"  Orientation:        {ORIENTATION}")
    print(f"  Background removal: {'YES  (--nobg)' if remove_bg else 'no'}")
    print(f"  Background block:   id={BG_BLOCK[0]}, data={BG_BLOCK[1]}")
    print("=" * 56 + "\n")

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
    build_wall(mc, grid, orientation=ORIENTATION)


if __name__ == "__main__":
    main()
