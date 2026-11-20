"""Sets Godot import options for arena textures (run after Godot's first import).

    python tools/art/arena_texture_imports.py && godot --headless --path . --import

Arena textures must be VRAM-compressed (ETC2/ASTC on phones) with mipmaps;
normal maps are flagged as normal maps. Godot only switches textures to VRAM
compression by itself when they are opened in the editor, so this makes it
explicit for builds made from the command line.
"""
import glob
import re

paths = glob.glob("assets/arenas/textures/*.png.import") + glob.glob("assets/arenas/*/*_ao.png.import") + glob.glob("assets/arenas/*/*_light.png.import") + glob.glob("assets/arenas/*/*_sky.png.import") \
    + glob.glob("assets/arenas/*/*banner*.png.import")
for p in paths:
    s = open(p).read()
    s = re.sub(r"compress/mode=\d", "compress/mode=2", s)
    s = re.sub(r"mipmaps/generate=\w+", "mipmaps/generate=true", s)
    s = re.sub(r"detect_3d/compress_to=\d", "detect_3d/compress_to=0", s)
    s = re.sub(r"compress/normal_map=\d", "compress/normal_map=%d" % (1 if "_normal" in p else 2), s)
    open(p, "w").write(s)
print(f"{len(paths)} texture imports set to VRAM compressed + mipmaps")
