"""Lays out the renders from render_character_sheet.py as a presentation sheet.

    python3 tools/art/compose_character_sheet.py <render_dir> <fighter_id> <NAME> <Title> <out.png>
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

src, fid, name, title, out = sys.argv[1:6]
W, H = 3600, 2300
BG, INK, RED = (236, 236, 241), (22, 20, 24), (200, 30, 28)
sheet = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(sheet)
B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
Rg = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
F = lambda size, bold=True: ImageFont.truetype(B if bold else Rg, size)  # noqa: E731


def tag(x, y, text, size=34, w=None):
    tw = d.textlength(text, font=F(size)) + 60
    w = w or tw
    d.polygon([(x, y), (x + w, y), (x + w - 22, y + size + 26), (x - 22, y + size + 26)], fill=INK)
    d.text((x + 22, y + 11), text, font=F(size), fill=(255, 255, 255))


def place(view, box, pad=0.0, shadow=True):
    """Fits a transparent render into box = (x, y, w, h), bottom-aligned."""
    im = Image.open(f"{src}/{fid}_{view}.png").convert("RGBA")
    bb = im.getbbox()
    im = im.crop(bb)
    x, y, w, h = box
    k = min(w * (1 - pad) / im.width, h * (1 - pad) / im.height)
    im = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
    px, py = x + (w - im.width) // 2, y + h - im.height
    if shadow:
        sh = Image.new("RGBA", (im.width + 120, 70), (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse((10, 10, im.width + 110, 60), fill=(40, 40, 60, 90))
        sh = sh.filter(ImageFilter.GaussianBlur(14))
        sheet.paste(sh, (px - 60, py + im.height - 38), sh)
    sheet.paste(im, (px, py), im)


def panel(box, label):
    x, y, w, h = box
    d.rectangle((x, y, x + w, y + h), fill=(246, 246, 250), outline=(196, 196, 206), width=3)
    d.text((x + 16, y + 12), label, font=F(26), fill=(90, 90, 104))


# header
d.polygon([(0, 0), (1500, 0), (1420, 150), (0, 150)], fill=INK)
d.polygon([(0, 150), (1420, 150), (1412, 166), (0, 166)], fill=RED)
d.text((60, 26), name, font=F(96), fill=(255, 255, 255))
d.text((70 + d.textlength(name, font=F(96)) + 30, 70), title.upper(), font=F(40), fill=(255, 90, 80))
tag(1560, 40, os.environ.get("SUBTITLE", "3D CHARACTER SHEET  ·  MODELLED IN BLENDER FROM THE APPROVED ART"), 30)
d.text((1570, 122), "These are renders of the actual game model, posed with the game's own animations.", font=F(26, False), fill=(90, 90, 104))

# turnaround
for i, (v, lab) in enumerate((("front", "FRONT"), ("back", "BACK"))):
    x = 60 + i * 720
    d.line((x + 40, 1500, x + 660, 1500), fill=(196, 196, 206), width=3)
    place(v, (x, 230, 700, 1270))
    d.text((x + 350 - d.textlength(lab, font=F(30)) / 2, 1520), lab, font=F(30), fill=(90, 90, 104))
# action poses
tag(1560, 215, "ACTION POSES")
place("stance", (1500, 300, 760, 1200))
place("kick", (2240, 300, 1300, 1200))
d.text((1700, 1520), "FIGHTING STANCE", font=F(30), fill=(90, 90, 104))
d.text((2760, 1520), "KICK", font=F(30), fill=(90, 90, 104))
# close-ups
tag(60, 1600, "CLOSE-UPS")
for i, (v, lab) in enumerate((("face", "FACE"), ("torso", "TORSO  ·  ORIGIN LINE"), ("gauntlet", "FOREARM GUARD + GLOVE"), ("legs", "SASH  ·  KNEE GUARDS  ·  BOOTS"))):
    box = (60 + i * 640, 1690, 610, 560)
    panel(box, lab)
    place(v, (box[0] + 10, box[1] + 50, box[2] - 20, box[3] - 60), shadow=False)
# palette + notes
tag(2660, 1600, "PALETTE  +  NOTES")
for i, c in enumerate(((24, 25, 31), (58, 60, 72), (104, 108, 124), (176, 24, 20), (255, 60, 44), (196, 142, 108))):
    d.rounded_rectangle((2660 + i * 150, 1690, 2660 + i * 150 + 130, 1790), 14, fill=c, outline=(120, 120, 130), width=2)
import os  # noqa: E402
NOTES = {"v4": ["Sculpted from scratch: muscles, skull, face",
                "Stylized-realistic (SF6 / Tekken direction)",
                "Fitted top: the muscles read through",
                "Sculpted fists, knuckle plates, Origin line",
                "Torn red sash knotted on the right hip",
                "Layered spiky hair with one red streak",
                "44.3k triangles, 6 materials, game rig"]}
notes = NOTES.get(os.environ.get("NOTES", ""), [
         "Heroic build: wide shoulders, narrow waist", "Fitted sleeveless top, muscle definition sculpted in",
         "Glowing red Origin line on chest, guards and boots", "Forearm guards and gloves with knuckle plates",
         "Torn red sash over the right thigh", "Short spiked hair with one red streak",
         "Cel shading and ink outlines, as in the 2D art"])
for i, n in enumerate(notes):
    d.ellipse((2664, 1836 + i * 54, 2680, 1852 + i * 54), fill=RED)
    d.text((2700, 1824 + i * 54), n, font=F(30, False), fill=INK)
sheet.save(out)
print("saved", out, sheet.size)
