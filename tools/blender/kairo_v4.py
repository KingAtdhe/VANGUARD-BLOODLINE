"""Kairo v4 — sculpted with the SDF engine (sdf_sculpt.py), FROM SCRATCH.

Target: stylized-realistic fighting-game hero in the spirit of SF6 / Tekken 8
(heroic anatomy, strong readable face, real clothing volume), following
Saba's VANGUARD: BLOODLINE character art sheet for the design: black fitted
top with the glowing red Origin line, bare upper arms, black gloves with
forearm guards, dark tactical trousers with knee guards, boots, belt with a
torn red sash on the right hip, short swept spiky black hair with one red
streak.

Frame: metres, Z up, faces -Y, +X = Kairo's LEFT. Joint positions come from
character_builder.skeleton() so the existing rig and animations still fit.
"""

import numpy as np

from sdf_sculpt import Layer

SKIN = (0.60, 0.40, 0.29)
SKIN_SH = (0.52, 0.32, 0.23)
LIP = (0.50, 0.29, 0.24)
BLACK = (0.035, 0.037, 0.045)
CHAR = (0.075, 0.078, 0.09)
GREY = (0.20, 0.21, 0.24)
STEEL = (0.32, 0.33, 0.36)
RED = (0.62, 0.035, 0.03)
GLOW = (1.0, 0.09, 0.05)
HAIR = (0.02, 0.018, 0.02)
WHITE = (0.72, 0.70, 0.67)
IRIS = (0.16, 0.09, 0.05)


def P(B, bone, end=0):
    return np.array(B[bone][end], float)


def mir(v):
    v = np.array(v, float)
    v[0] = -v[0]
    return v


def body_layer(B):
    L = Layer("Body", "Skin", voxel=0.003, tris=9000)
    S = SKIN
    # ---------------------------------------------------------- torso --
    L.ell((0, 0.01, 1.315), (0.152, 0.1, 0.165), "Chest", S, k=0.03)            # ribcage
    L.ell((0, 0.04, 1.36), (0.145, 0.065, 0.13), "Chest", S, k=0.05)              # upper back
    L.ell((0, -0.022, 1.13), (0.108, 0.076, 0.12), "Spine", S, k=0.045)           # abdomen
    L.ell((0, 0.012, 1.02), (0.1, 0.082, 0.085), "Hips", S, k=0.04)               # pelvis
    L.ell((0, -0.058, 1.135), (0.068, 0.03, 0.105), "Spine", S, k=0.02)          # rectus abdominis
    for sx in (1, -1):
        side = "Left" if sx > 0 else "Right"
        sh, el, wr = P(B, f"{side}UpperArm"), P(B, f"{side}LowerArm"), P(B, f"{side}Hand")
        L.cone((0.04 * sx, 0.0, 1.465), sh + (-0.025 * sx, 0.0, 0.025), 0.045, 0.045, "Chest", S, k=0.03)  # clavicle girdle
        L.cone((0.03 * sx, 0.035, 1.57), (0.17 * sx, 0.02, 1.462), 0.056, 0.036, "Chest", S, k=0.04)      # trapezius
        L.ell((0.082 * sx, -0.068, 1.35), (0.098, 0.045, 0.07), "Chest", S, k=0.025, rot=(0, 10 * sx, 0))  # pec
        L.cone((0.12 * sx, -0.05, 1.36), sh + (-0.035 * sx, -0.015, -0.05), 0.036, 0.03, "Chest", S, k=0.03)  # pec insertion
        L.ell((0.115 * sx, 0.035, 1.31), (0.05, 0.062, 0.1), "Chest", S, k=0.045, rot=(0, -10 * sx, 0))   # lat
        L.cone((0.14 * sx, 0.035, 1.33), sh + (-0.04 * sx, 0.02, -0.06), 0.04, 0.032, "Chest", S, k=0.035)  # lat insertion
        L.ell((0.088 * sx, -0.012, 1.1), (0.04, 0.06, 0.075), "Spine", S, k=0.035)                       # oblique
        L.ell((0.058 * sx, 0.062, 0.95), (0.062, 0.058, 0.08), "Hips", S, k=0.03)                       # glute
        L.ell((0.032 * sx, 0.062, 1.2), (0.03, 0.03, 0.17), "Spine", S, k=0.04)                         # spinal erector
        L.ell((0.085 * sx, 0.07, 1.38), (0.07, 0.035, 0.075), "Chest", S, k=0.045)                      # rhomboid / infraspinatus
        # ------------------------------------------------------------ arm --
        L.muscle(sh, el, 0.1, (0.012 * sx, 0.0, 0), (0.058, 0.064, 0.095), f"{side}UpperArm", S, k=0.03)  # deltoid
        L.cone(sh + (0, 0, -0.03), el, 0.055, 0.042, f"{side}UpperArm", S, k=0.02)
        L.muscle(sh, el, 0.56, (0.0, -0.027, 0), (0.044, 0.042, 0.085), f"{side}UpperArm", S, k=0.02)      # biceps
        L.muscle(sh, el, 0.62, (0.03 * sx, -0.005, 0), (0.026, 0.03, 0.06), f"{side}UpperArm", S, k=0.018)  # brachialis
        L.muscle(sh, el, 0.42, (0.006 * sx, 0.031, 0), (0.046, 0.042, 0.11), f"{side}UpperArm", S, k=0.02)  # triceps
        L.cone(el, wr, 0.047, 0.031, f"{side}LowerArm", S, k=0.02, squash=(1.0, 0.82))
        L.muscle(el, wr, 0.22, (0.01 * sx, -0.006, 0), (0.033, 0.03, 0.07), f"{side}LowerArm", S, k=0.02)    # brachiorad.
        L.cone(wr, wr + (0, -0.01, -0.05), 0.026, 0.024, f"{side}Hand", S, k=0.015)                          # hand core (gloved)
        # ------------------------------------------------------------ leg --
        hp, kn, an = P(B, f"{side}UpperLeg"), P(B, f"{side}LowerLeg"), P(B, f"{side}Foot")
        L.cone(hp + (-0.012 * sx, 0.0, 0.02), kn, 0.076, 0.054, f"{side}UpperLeg", S, k=0.03)
        L.muscle(hp, kn, 0.42, (0.02 * sx, -0.008, 0), (0.05, 0.056, 0.17), f"{side}UpperLeg", S, k=0.03)  # vastus lat.
        L.muscle(hp, kn, 0.8, (-0.024 * sx, -0.022, 0), (0.042, 0.042, 0.075), f"{side}UpperLeg", S, k=0.025)  # vastus med.
        L.muscle(hp, kn, 0.4, (0.0, -0.038, 0), (0.048, 0.042, 0.16), f"{side}UpperLeg", S, k=0.03)          # rectus fem.
        L.muscle(hp, kn, 0.45, (0.0, 0.035, 0), (0.052, 0.048, 0.16), f"{side}UpperLeg", S, k=0.03)          # hamstrings
        L.muscle(hp, kn, 0.22, (-0.04 * sx, 0.0, 0), (0.045, 0.052, 0.11), f"{side}UpperLeg", S, k=0.03)     # adductor
        L.ell(kn + (0, -0.042, 0.0), (0.024, 0.016, 0.026), f"{side}LowerLeg", S, k=0.015)                  # patella
        L.cone(kn, an + (0, 0, -0.03), 0.05, 0.033, f"{side}LowerLeg", S, k=0.02)
        L.muscle(kn, an, 0.22, (0.018 * sx, 0.032, 0), (0.035, 0.037, 0.1), f"{side}LowerLeg", S, k=0.025)  # gastroc lat.
        L.muscle(kn, an, 0.25, (-0.018 * sx, 0.032, 0), (0.037, 0.039, 0.11), f"{side}LowerLeg", S, k=0.025)  # gastroc med.
        ft = P(B, f"{side}Foot", 1)
        L.cone(an + (0, 0.02, -0.055), ft + (0, 0, -0.005), 0.04, 0.03, f"{side}Foot", S, k=0.02, squash=(1.0, 0.7))
    # ----------------------------------------------------------- neck --
    L.cone((0, 0.018, 1.44), (0, 0.02, 1.615), 0.068, 0.055, "Neck", S, k=0.024)
    for sx in (1, -1):
        L.cone((0.052 * sx, 0.012, 1.63), (0.014 * sx, -0.045, 1.465), 0.016, 0.013, "Neck", S, k=0.015)  # SCM
    # ---- anatomy detail pass (what a character artist sculpts next) ----
    for sx in (1, -1):
        side = "Left" if sx > 0 else "Right"
        sh, el = P(B, f"{side}UpperArm"), P(B, f"{side}LowerArm")
        ax = (el - sh) / np.linalg.norm(el - sh)
        L.cone((0.025 * sx, -0.068, 1.474), (0.16 * sx, -0.032, 1.468), 0.006, 0.005, "Chest", S, k=0.014)      # clavicle
        L.muscle(sh, el, 0.16, (0.0, -0.036, 0), (0.034, 0.028, 0.068), f"{side}UpperArm", S, k=0.016)         # front delt
        L.muscle(sh, el, 0.16, (0.0, 0.036, 0), (0.034, 0.028, 0.068), f"{side}UpperArm", S, k=0.016)          # rear delt
        L.groove([(0.128 * sx, -0.092, 1.445), (0.17 * sx, -0.075, 1.38), (0.19 * sx, -0.05, 1.33)], 0.006, 0.0028)  # pec/delt
        L.groove([sh + ax * 0.12 + (0.05 * sx, -0.02, 0), sh + ax * 0.2 + (0.052 * sx, 0.0, 0),
                  sh + ax * 0.12 + (0.05 * sx, 0.022, 0)], 0.006, 0.002)                                    # delt insertion
        L.groove([sh + ax * 0.32 + (0.05 * sx, 0.004, 0), sh + ax * 0.6 + (0.048 * sx, 0.006, 0),
                  sh + ax * 0.85 + (0.04 * sx, 0.004, 0)], 0.005, 0.0022)                                   # biceps/triceps
        L.groove([sh + ax * 0.5 + (0.0, 0.07, 0), sh + ax * 0.8 + (0.0 * sx, 0.06, 0)], 0.006, 0.0018)        # triceps horseshoe
        L.groove([(0.232 * sx, -0.05, 1.235), (0.243 * sx, -0.047, 1.19), (0.252 * sx, -0.04, 1.15)], 0.0028, -0.0013)  # vein
        L.groove([(0.215 * sx, -0.046, 1.3), (0.228 * sx, -0.05, 1.25)], 0.0024, -0.001)                        # vein
        for i, z in enumerate((1.31, 1.27, 1.23)):                                                           # serratus
            L.ell((0.124 * sx, -0.056 + 0.004 * i, z), (0.008, 0.014, 0.011), "Chest", S, k=0.012, rot=(0, 0, 25 * sx))
        for z in (1.19, 1.137, 1.083):                                                                        # six-pack
            L.ell((0.03 * sx, -0.08, z), (0.025, 0.009, 0.022), "Spine", S, k=0.018)
        L.groove([(0.07 * sx, -0.085, 1.21), (0.075 * sx, -0.075, 1.12), (0.06 * sx, -0.082, 1.03)], 0.006, 0.0025)  # oblique line
    # muscle separations (sculpt grooves)
    L.groove([(0, -0.11, 1.40), (0, -0.115, 1.31)], 0.012, 0.004)                     # sternum
    L.groove([(0, -0.09, 1.21), (0, -0.09, 1.04)], 0.008, 0.0025)                      # linea alba
    for z in (1.18, 1.12, 1.06):
        L.groove([(-0.055, -0.085, z), (0.055, -0.085, z)], 0.006, 0.0018)             # abs
    for sx in (1, -1):
        L.groove([(0.02 * sx, -0.108, 1.29), (0.1 * sx, -0.09, 1.295), (0.155 * sx, -0.06, 1.33)], 0.012, 0.004)  # pec lower edge
    head_forms(L)
    return L


def head_forms(L):
    """Skull and face. Head bone 1.56 -> 1.80. Proportions: SF6 / Tekken male
    hero — heavy brow, narrow determined eyes, defined cheekbones, square jaw."""
    S, H = SKIN, "Head"
    L.ell((0, 0.006, 1.712), (0.072, 0.086, 0.084), H, S, k=0.02)            # cranium
    L.ell((0, -0.03, 1.705), (0.066, 0.055, 0.07), H, S, k=0.03)             # forehead / face block
    L.ell((0, -0.052, 1.65), (0.045, 0.04, 0.045), H, S, k=0.03)             # maxilla
    L.ell((0, -0.068, 1.598), (0.03, 0.03, 0.022), H, S, k=0.022)            # chin mass
    L.box((0, -0.088, 1.588), (0.019, 0.01, 0.013), H, S, rad=0.009, k=0.012)  # square chin
    L.ell((0, -0.074, 1.624), (0.025, 0.022, 0.024), H, S, k=0.02)           # muzzle
    for sx in (1, -1):
        L.ell((0.052 * sx, -0.054, 1.672), (0.017, 0.019, 0.011), H, S, k=0.028, rot=(0, 0, -15 * sx))   # zygoma
        L.ell((0.042 * sx, -0.068, 1.64), (0.016, 0.017, 0.018), H, S, k=0.02)                          # cheek fullness
        L.cone((0.052 * sx, -0.016, 1.61), (0.017 * sx, -0.075, 1.588), 0.012, 0.011, H, S, k=0.022)   # jaw line
        L.ell((0.054 * sx, -0.004, 1.65), (0.009, 0.017, 0.027), H, S, k=0.018)                         # ramus
        L.ell((0.074 * sx, 0.006, 1.674), (0.009, 0.018, 0.027), H, S, k=0.008, rot=(0, 0, 15 * sx))  # ear
        L.ell((0.081 * sx, 0.004, 1.67), (0.005, 0.009, 0.013), H, op="sub", k=0.003)                 # concha
        L.groove([(0.064 * sx, -0.035, 1.72), (0.062 * sx, -0.05, 1.695)], 0.014, 0.002)                 # temple
        # brow ridge: one continuous bar, slightly lowered toward the centre (scowl)
        L.ell((0.027 * sx, -0.084, 1.711), (0.027, 0.016, 0.0105), H, S, k=0.02, rot=(0, 6 * sx, -18 * sx))
        e = np.array((0.031 * sx, -0.082, 1.693))                                       # eyeball centre
        L.ell(e + (0, -0.016, 0.002), (0.018, 0.007, 0.0105), H, op="sub", k=0.007)       # socket
        L.ell(e, (0.0142, 0.0132, 0.0142), H, S, k=0.004)                               # lid shell
        L.ell(e + (0.001 * sx, -0.012, -0.0003), (0.0146, 0.012, 0.0051), H, op="sub", k=0.0015,
              rot=(0, 8 * sx, 0))                                                        # eye opening (outer corner up)
        L.groove([e + (-0.011 * sx, -0.011, 0.007), e + (0.0, -0.013, 0.0085), e + (0.012 * sx, -0.009, 0.0075)],
                 0.0022, 0.0009)                                                         # upper lid crease
        L.ell((0.011 * sx, -0.095, 1.643), (0.0075, 0.0075, 0.0065), H, S, k=0.006)    # nose wing
        L.ell((0.006 * sx, -0.1, 1.64), (0.0028, 0.0035, 0.0022), H, op="sub", k=0.002)  # nostril
        L.groove([(0.014 * sx, -0.099, 1.641), (0.022 * sx, -0.094, 1.627), (0.025 * sx, -0.09, 1.614)],
                 0.0045, 0.0006)                                                          # nasolabial
    L.cone((0, -0.094, 1.698), (0, -0.103, 1.659), 0.006, 0.0075, H, S, k=0.008)    # nose bridge
    L.ell((0, -0.102, 1.652), (0.0085, 0.009, 0.0085), H, S, k=0.007)               # nose tip
    L.ell((0, -0.096, 1.622), (0.019, 0.007, 0.0045), H, LIP, k=0.006)               # upper lip
    L.ell((0, -0.0935, 1.6115), (0.017, 0.0075, 0.0055), H, LIP, k=0.006)           # lower lip
    L.groove([(-0.02, -0.098, 1.6182), (0, -0.101, 1.6175), (0.02, -0.098, 1.6182)], 0.003, 0.0014)  # mouth line
    L.groove([(0, -0.101, 1.635), (0, -0.101, 1.627)], 0.003, 0.0008)              # philtrum
    L.groove([(-0.015, -0.096, 1.6), (0.015, -0.096, 1.6)], 0.0045, 0.001)          # mentolabial sulcus
    L.groove([(-0.007, -0.1, 1.697), (0.007, -0.1, 1.697)], 0.004, 0.001)           # glabella furrow
    for sx in (1, -1):                                                            # brow paint
        L.paint("cone", (0.008 * sx, -0.1, 1.705), (0.03 * sx, -0.099, 1.713), 0.006, 0.005, color=HAIR, soft=0.002)
        L.paint("cone", (0.03 * sx, -0.099, 1.713), (0.054 * sx, -0.083, 1.711), 0.005, 0.002, color=HAIR, soft=0.002)
    L.paint("ell", (0, -0.075, 1.6), (0.05, 0.04, 0.035), color=SKIN_SH, soft=0.012)   # beard shadow


def eye_layer():
    L = Layer("Eyes", "Skin", voxel=0.001, tris=700)
    for sx in (1, -1):
        c = np.array((0.031 * sx, -0.082, 1.693))
        L.ell(c, (0.0124, 0.0124, 0.0124), "Head", WHITE, k=0.0)
        L.paint("ell", c + (0.002 * sx, -0.0105, 0.0005), (0.0072, 0.004, 0.0072), color=IRIS, soft=0.0008)
        L.paint("ell", c + (0.002 * sx, -0.0115, 0.0005), (0.0028, 0.002, 0.0028), color=(0.01, 0.01, 0.01),
                soft=0.0005)
    return L


# ================================================================ outfit ==
def ring(a, b, t, rad, ang0, ang1, n=7, tilt=0.0, up=None):
    """Points on a ring around segment a->b (for wrap-around folds/seams).
    Angles in degrees, 0 = +X side (lateral), 90 = depth axis."""
    from sdf_sculpt import _frame
    a, b = np.asarray(a, float), np.asarray(b, float)
    ax = (b - a) / np.linalg.norm(b - a)
    u, w = _frame(ax, up)
    out = []
    for i in range(n):
        g = np.radians(ang0 + (ang1 - ang0) * i / (n - 1))
        c = a + (b - a) * (t + tilt * math.sin(g) * 0.5)
        out.append(c + u * math.cos(g) * rad + w * math.sin(g) * rad)
    return out


import math  # noqa: E402


def top_layer(B, body):
    """Fitted compression top: the body surface itself, dilated, so every
    muscle reads through the cloth (SF6 / Tekken fitted-top look)."""
    L = Layer("Top", "Cloth", voxel=0.003, tris=6000, base=body, base_offset=0.0045, color=BLACK)
    L.clip((0, 0, 1.005), (0, 0, -1), k=0.003)                         # hem (under belt)
    L.clip((0, 0, 1.524), (0, 0, 1), k=0.003)                          # collar top
    for sx in (1, -1):
        side = "Left" if sx > 0 else "Right"
        sh, el = P(B, f"{side}UpperArm"), P(B, f"{side}LowerArm")
        cut = sh + (el - sh) * 0.36
        axu = (el - sh) / np.linalg.norm(el - sh)
        L.cone(cut + axu * 0.085, el + (el - sh) * 3, 0.085, 0.085, f"{side}UpperArm", op="sub", k=0.002)  # sleeve
        L.cone(sh + (el - sh) * 0.31, sh + (el - sh) * 0.36, 0.066, 0.062, f"{side}UpperArm", BLACK, k=0.004)  # cuff
        # panel seams following the anatomy
        L.groove([(0.14 * sx, -0.055, 1.42), (0.11 * sx, -0.095, 1.33), (0.07 * sx, -0.1, 1.24),
                  (0.06 * sx, -0.09, 1.1)], 0.003, 0.0012)
        L.groove([(0.17 * sx, 0.0, 1.38), (0.145 * sx, 0.01, 1.22), (0.11 * sx, 0.0, 1.03)], 0.003, 0.0012)  # side seam
        L.groove([(0.05 * sx, 0.11, 1.45), (0.12 * sx, 0.085, 1.32), (0.1 * sx, 0.08, 1.12)], 0.003, 0.001)  # back panel
    for sx in (1, -1):
        for o in (0.0, 0.03):                                                       # armpit tension folds
            L.groove([(0.165 * sx, -0.055, 1.34 - o), (0.11 * sx, -0.09, 1.28 - o), (0.06 * sx, -0.1, 1.22 - o)],
                     0.005, 0.0022)
        for z in (1.04, 1.065, 1.09):                                               # waist compression
            L.groove([(0.06 * sx, -0.095, z), (0.1 * sx, -0.06, z + 0.006), (0.115 * sx, 0.0, z + 0.004)], 0.004, 0.0016)
        L.groove([(0.06 * sx, 0.0, 1.5), (0.15 * sx, 0.0, 1.46), (0.22 * sx, 0.0, 1.43)], 0.0028, 0.0014)  # shoulder seam
    L.cone((0, 0.017, 1.45), (0, 0.021, 1.522), 0.071, 0.066, "Neck", BLACK, k=0.01)    # high collar
    L.groove(ring((0, 0.017, 1.45), (0, 0.021, 1.533), 0.9, 0.067, 0, 360, n=25), 0.0025, 0.0012)
    return L


def accent_layer(B):
    """Glowing red Origin lines (emissive)."""
    L = Layer("Origin", "Accent", voxel=0.0016, tris=900)
    # chest: vertical line from the collar down the left pec, plus a short slash
    L.cone((0.022, -0.082, 1.475), (0.03, -0.118, 1.35), 0.0032, 0.0032, "Chest", GLOW, k=0.002)
    L.cone((0.03, -0.118, 1.35), (0.032, -0.107, 1.18), 0.0032, 0.003, "Spine", GLOW, k=0.002)
    L.cone((0.04, -0.118, 1.37), (0.085, -0.116, 1.395), 0.0028, 0.0028, "Chest", GLOW, k=0.002)
    for sx in (1, -1):
        side = "Left" if sx > 0 else "Right"
        el, wr = P(B, f"{side}LowerArm"), P(B, f"{side}Hand")
        # forearm guard inlay (outer side)
        L.plate(el, wr, 0.5, (0.048 * sx, 0.0, 0.0), (0.0025, 0.004, 0.06), f"{side}LowerArm", GLOW, rad=0.0022, k=0.0)
        an = P(B, f"{side}Foot")
        L.box(an + (0.051 * sx, -0.01, 0.12), (0.0022, 0.004, 0.06), f"{side}LowerLeg", GLOW, rad=0.002, k=0.0)
    return L


def no_arms(L, B, r=0.062):
    """Carve the arms out of a field derived from the whole body."""
    for side in ("Left", "Right"):
        el, wr, tip = P(B, f"{side}LowerArm"), P(B, f"{side}Hand"), P(B, f"{side}Hand", 1)
        sh = P(B, f"{side}UpperArm")
        L.cone(sh + (el - sh) * 0.5, el, r, r, f"{side}LowerArm", op="sub", k=0.002)
        L.cone(el, tip + (tip - wr), r, r, f"{side}LowerArm", op="sub", k=0.002)


def trouser_layer(B, body):
    L = Layer("Trousers", "Cloth2", voxel=0.003, tris=5500, base=body, base_offset=0.009, color=CHAR)
    C = CHAR
    no_arms(L, B)
    L.clip((0, 0, 1.035), (0, 0, 1), k=0.003)
    L.clip((0, 0, 0.2), (0, 0, -1), k=0.003)
    for sx in (1, -1):
        side = "Left" if sx > 0 else "Right"
        hp, kn, an = P(B, f"{side}UpperLeg"), P(B, f"{side}LowerLeg"), P(B, f"{side}Foot")
        L.cone(hp + (-0.01 * sx, 0.0, -0.02), kn, 0.088, 0.066, f"{side}UpperLeg", C, k=0.03)
        L.cone(kn, an + (0, 0, 0.12), 0.066, 0.06, f"{side}LowerLeg", C, k=0.025)
        # cloth folds: knee bunching, diagonal thigh pulls, stacking above the boot
        for t, tl in ((0.86, 0.12), (0.92, -0.1), (0.97, 0.08)):
            L.groove(ring(hp, kn, t, 0.074, -40, 220, n=9, tilt=tl), 0.006, 0.0035)
        for t in (0.15, 0.27):
            L.groove(ring(kn, an, t, 0.07, 100, 260, n=6), 0.007, 0.003)       # back of knee
        L.groove([hp + (-0.06 * sx, -0.07, -0.05), hp + (0.0, -0.095, -0.2), hp + (0.03 * sx, -0.09, -0.3)], 0.006, 0.003)
        L.groove([hp + (-0.03 * sx, -0.08, 0.0), hp + (0.04 * sx, -0.1, -0.12)], 0.006, 0.0025)
        for t in (0.6, 0.66):
            L.groove(ring(kn, an, t, 0.061, 20, 200, n=8, tilt=0.12), 0.006, 0.0022)
        L.groove([hp + (0.085 * sx, 0.0, 0.0), kn + (0.07 * sx, 0.0, 0.0), an + (0.06 * sx, 0, 0.15)], 0.0025, 0.0012)  # side seam
        # cargo pocket on the outer thigh
        L.plate(hp, kn, 0.45, (0.095 * sx, 0.0, 0), (0.008, 0.045, 0.055), f"{side}UpperLeg", C, rad=0.006, k=0.006)
    L.groove([(0, -0.13, 1.03), (0, -0.115, 0.92)], 0.004, 0.0025)                    # fly
    for sx in (1, -1):                                                                   # crotch gravity folds
        for a_, b_ in (((0.02, -0.1, 0.9), (0.09, -0.11, 0.74)), ((0.03, -0.095, 0.87), (0.12, -0.1, 0.66)),
                       ((0.015, -0.09, 0.85), (0.06, -0.1, 0.7))):
            L.groove([(a_[0] * sx, a_[1], a_[2]), (b_[0] * sx, b_[1], b_[2])], 0.008, 0.0035)
        for z in (0.33, 0.36, 0.39):                                                     # stacking over the boot
            hp, kn, an = P(B, "LeftUpperLeg" if sx > 0 else "RightUpperLeg"), P(B, "LeftLowerLeg" if sx > 0 else "RightLowerLeg"), P(B, "LeftFoot" if sx > 0 else "RightFoot")
            t = (kn[2] - z) / (kn[2] - an[2])
            L.groove(ring(kn, an, t, 0.062, -30, 200, n=9, tilt=0.15), 0.007, 0.003)
    return L


def knee_layer(B):
    L = Layer("KneeGuards", "Gear", voxel=0.0022, tris=1200)
    for sx in (1, -1):
        side = "Left" if sx > 0 else "Right"
        kn, an = P(B, f"{side}LowerLeg"), P(B, f"{side}Foot")
        hp = P(B, f"{side}UpperLeg")
        L.ell(kn + (0.0, -0.066, -0.005), (0.05, 0.03, 0.06), f"{side}LowerLeg", GREY, k=0.01)
        L.ell(kn + (0.0, -0.035, -0.005), (0.06, 0.05, 0.08), f"{side}LowerLeg", op="sub", k=0.01)  # hollow back
        L.groove([kn + (-0.05, -0.09, 0.0), kn + (0.05, -0.09, 0.0)], 0.004, 0.003)
        L.cone(kn + (-0.065, -0.02, 0.035), kn + (0.065, -0.02, 0.035), 0.008, 0.008, f"{side}UpperLeg", BLACK, k=0.004)   # strap
        L.cone(kn + (-0.06, -0.015, -0.05), kn + (0.06, -0.015, -0.05), 0.008, 0.008, f"{side}LowerLeg", BLACK, k=0.004)
    return L


def boot_layer(B):
    L = Layer("Boots", "Cloth", voxel=0.0025, tris=4000)
    for sx in (1, -1):
        side = "Left" if sx > 0 else "Right"
        kn, an, ft = P(B, f"{side}LowerLeg"), P(B, f"{side}Foot"), P(B, f"{side}Foot", 1)
        L.cone(an + (0, 0.004, 0.24), an + (0, 0.008, 0.02), 0.06, 0.05, f"{side}LowerLeg", BLACK, k=0.02)  # shaft
        L.ell(an + (0, 0.035, -0.035), (0.045, 0.05, 0.045), f"{side}Foot", BLACK, k=0.02)                   # heel
        L.cone(an + (0, -0.01, -0.03), (ft[0], ft[1] - 0.01, 0.035), 0.05, 0.038, f"{side}Foot", BLACK, k=0.025,
               squash=(1.0, 0.75))                                                                         # vamp
        L.ell((ft[0], ft[1] - 0.02, 0.035), (0.042, 0.05, 0.032), f"{side}Foot", BLACK, k=0.02)            # toe box
        L.box((ft[0], an[1] - 0.075, 0.012), (0.046, 0.158, 0.013), f"{side}Foot", GREY, rad=0.012, k=0.008)  # sole
        L.clip((0, 0, -0.0005), (0, 0, -1), k=0.002)
        L.ell((ft[0], ft[1] - 0.03, 0.04), (0.044, 0.04, 0.03), f"{side}Foot", CHAR, k=0.008)              # toe cap
        L.box(an + (0, 0.07, 0.0), (0.045, 0.025, 0.04), f"{side}Foot", CHAR, rad=0.015, k=0.012)          # heel counter
        for z in (0.12, 0.17, 0.22):
            L.groove(ring(an + (0, 0, 0.3), an, 1.0 - z / 0.3, 0.059, 200, 340, n=6), 0.0035, 0.002)    # lace rows
            L.groove(ring(an + (0, 0, 0.3), an, 1.0 - z / 0.3, 0.06, 0, 30, n=3), 0.003, 0.0015)
        L.cone(an + (0, -0.06, 0.2), an + (0, -0.04, 0.03), 0.006, 0.006, f"{side}LowerLeg", GREY, k=0.003)   # tongue ridge
        for i, z in enumerate(np.arange(0.05, 0.22, 0.024)):                               # laces (criss-cross)
            y0 = -0.058 + (0.22 - z) * 0.05
            L.cone(an + (-0.02, y0, z), an + (0.02, y0 - 0.002, z + 0.014), 0.0028, 0.0028, f"{side}LowerLeg", CHAR, k=0.0015)
            L.cone(an + (0.02, y0, z), an + (-0.02, y0 - 0.002, z + 0.014), 0.0028, 0.0028, f"{side}LowerLeg", CHAR, k=0.0015)
        for i in range(9):                                                                  # sole tread
            yy = an[1] + 0.07 - i * 0.03
            L.groove([(ft[0] - 0.05, yy, 0.008), (ft[0] + 0.05, yy - 0.006, 0.008)], 0.0035, 0.002)
        L.groove([(ft[0] - 0.05, an[1] - 0.15, 0.026), (ft[0] + 0.05, an[1] - 0.15, 0.026)], 0.003, 0.0015)
        L.groove(ring(an + (0, 0, 0.3), an, 0.98, 0.061, 0, 360, n=15), 0.003, 0.0018)                    # top rim
        L.groove([(ft[0] - 0.06, an[1] + 0.06, 0.028), (ft[0] - 0.06, ft[1] - 0.06, 0.028)], 0.003, 0.0018)  # welt
        L.groove([(ft[0] + 0.06, an[1] + 0.06, 0.028), (ft[0] + 0.06, ft[1] - 0.06, 0.028)], 0.003, 0.0018)
    return L


def glove_layer(B):
    """Fists (sculpted knuckles, curled fingers, wrapped thumb) + forearm guards."""
    L = Layer("Gloves", "Cloth", voxel=0.0018, tris=5000)
    for sx in (1, -1):
        side = "Left" if sx > 0 else "Right"
        el, wr = P(B, f"{side}LowerArm"), P(B, f"{side}Hand")
        hb = f"{side}Hand"
        # forearm guard (cuff + plate)
        L.cone(el + (wr - el) * 0.13, wr + (wr - el) * 0.03, 0.056, 0.037, f"{side}LowerArm", BLACK, k=0.01,
               squash=(1.0, 0.85))
        L.plate(el, wr, 0.5, (0.03 * sx, 0.0, 0), (0.014, 0.034, 0.1), f"{side}LowerArm", GREY, rad=0.009, k=0.006)
        L.groove(ring(el, wr, 0.16, 0.055, 0, 360, n=15), 0.003, 0.0015)
        L.groove(ring(el, wr, 0.94, 0.037, 0, 360, n=15), 0.003, 0.0015)
        # fist
        c = wr + np.array((0.002 * sx, -0.012, -0.05))
        L.box(c, (0.025, 0.04, 0.042), hb, BLACK, rad=0.016, k=0.01)                        # palm / back of hand
        for i, y in enumerate((-0.03, -0.01, 0.01, 0.029)):
            r = 0.0115 if i < 3 else 0.0098
            kz = c[2] - 0.04
            L.ell((c[0] + 0.006 * sx, c[1] + y, kz), (r * 1.05, r, r), hb, BLACK, k=0.006)  # knuckle (MCP)
            L.cone((c[0] + 0.006 * sx, c[1] + y, kz - 0.002), (c[0] - 0.024 * sx, c[1] + y, kz - 0.004),
                   r, r * 0.95, hb, BLACK, k=0.005)                                       # proximal phalanx
            L.cone((c[0] - 0.026 * sx, c[1] + y, kz - 0.002), (c[0] - 0.029 * sx, c[1] + y, kz + 0.03),
                   r * 0.95, r * 0.85, hb, BLACK, k=0.005)                                # middle phalanx (curled)
            L.groove([(c[0] - 0.034 * sx, c[1] + y + 0.0105, kz - 0.01), (c[0] - 0.034 * sx, c[1] + y + 0.0105,
                                                                           kz + 0.03)], 0.0018, 0.0012)
        # thumb wraps across the front of the index / middle fingers
        L.cone((c[0] - 0.006 * sx, c[1] - 0.04, c[2] + 0.018), (c[0] - 0.02 * sx, c[1] - 0.048, c[2] - 0.012),
               0.012, 0.011, hb, BLACK, k=0.008)
        L.cone((c[0] - 0.02 * sx, c[1] - 0.048, c[2] - 0.012), (c[0] - 0.03 * sx, c[1] - 0.028, c[2] - 0.02),
               0.011, 0.0095, hb, BLACK, k=0.006)
        # knuckle guard plate
        L.box((c[0] + 0.012 * sx, c[1], c[2] - 0.032), (0.009, 0.036, 0.016), hb, GREY, rad=0.007, k=0.004,
              rot=(0, -35 * sx, 0))
        L.groove([(c[0] + 0.024 * sx, c[1] - 0.033, c[2] - 0.03), (c[0] + 0.024 * sx, c[1] + 0.033, c[2] - 0.03)],
                 0.0025, 0.0012)
    return L


def belt_layer(B, body):
    L = Layer("Belt", "Gear", voxel=0.0022, tris=2000, base=body, base_offset=0.019, color=BLACK)
    no_arms(L, B)
    L.clip((0, 0, 0.996), (0, 0, -1), k=0.002)
    L.clip((0, 0, 1.039), (0, 0, 1), k=0.002)
    L.box((0, -0.112, 1.0175), (0.032, 0.008, 0.024), "Hips", STEEL, rad=0.006, k=0.003)        # buckle
    L.box((0, -0.121, 1.0175), (0.018, 0.004, 0.012), "Hips", op="sub", rad=0.003, k=0.002)
    L.paint("box", (0, -0.119, 1.0175), (0.016, 0.006, 0.01), color=GLOW, soft=0.002)
    L.groove(ring((0, 0.015, 0.995), (0, 0.015, 1.04), 0.2, 0.13, 0, 360, n=41), 0.0025, 0.0012)
    L.groove(ring((0, 0.015, 0.995), (0, 0.015, 1.04), 0.8, 0.128, 0, 360, n=41), 0.0025, 0.0012)
    return L


def sash_layer(B):
    """Torn red sash knotted on the right hip, hanging over the right thigh."""
    L = Layer("Sash", "Cloth", voxel=0.0022, tris=3000)
    hp, kn = P(B, "RightUpperLeg"), P(B, "RightLowerLeg")
    knot = np.array((-0.13, -0.07, 1.0))
    L.ell(knot, (0.03, 0.022, 0.026), "Hips", RED, k=0.008)                       # knot
    L.cone((-0.03, -0.12, 1.02), knot, 0.012, 0.016, "Hips", RED, k=0.008)          # band to knot
    L.cone(knot, (-0.15, 0.06, 1.01), 0.016, 0.012, "Hips", RED, k=0.008)
    # two cloth panels: draped over the front-outer thigh, wrapping round it,
    # with folds that deepen toward the torn hem
    L.sheet((-0.145, -0.118, 0.985), (-0.12, 0.02, -1.0), (-0.75, 0.66, 0), 0.115, 0.44, "RightUpperLeg", RED,
            k=0.006, thick=0.0028, folds=((0.05, 0.011, 0.0), (0.023, 0.003, 1.0)), wrap=2.2, tear=0.045, seed=1)
    L.sheet((-0.19, -0.06, 0.98), (-0.08, 0.06, -1.0), (-0.25, 0.97, 0), 0.1, 0.36, "RightUpperLeg", RED,
            k=0.006, thick=0.0028, folds=((0.055, 0.013, 1.5), (0.025, 0.003, 0.3)), wrap=2.0, tear=0.04, seed=2)
    return L


def hair_layer(B):
    """Hair as in Saba's portrait: full on top, layered locks falling from the
    crown over the forehead to the brows (red streak at the front-left),
    swept over the sides with the ears showing, tapered at the nape."""
    L = Layer("Hair", "Hair", voxel=0.0016, tris=7000)
    H = "Head"
    cc, cr = np.array((0, 0.004, 1.712)), np.array((0.078, 0.092, 0.089))
    L.ell(cc + (0, 0.004, 0.008), cr + (0.004, 0.006, 0.004), H, HAIR, k=0.012)     # volume under the locks
    L.clip((0, -0.07, 1.735), (0, -0.7, -1), k=0.012)                               # forehead line (bangs cover it)
    L.clip((0, 0.0, 1.645), (0, 0.3, -1), k=0.01)
    for sx in (1, -1):
        L.ell((0.084 * sx, 0.006, 1.672), (0.016, 0.028, 0.026), H, op="sub", k=0.012)   # ears show
    rng = np.random.default_rng(3)
    crown = np.array((0.0, 0.03, 1.806))

    def surf(az, el, lift):
        a, e = math.radians(az), math.radians(el)
        d = np.array((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
        return cc + d * (cr + lift)

    locks = []
    # (azimuth range, end elevation, count, width, tip length, end direction)
    groups = [((-56, 56), 9, 7, 0.042, 0.022, "down"), ((-40, 40), 34, 6, 0.044, 0.02, "fwd"),
              ((-35, 35), 62, 4, 0.04, 0.03, "up"),
              ((62, 118), 4, 4, 0.034, 0.025, "down"), ((-118, -62), 4, 4, 0.034, 0.025, "down"),
              ((125, 235), -38, 7, 0.036, 0.022, "down"), ((140, 220), 15, 5, 0.04, 0.02, "back")]
    for (a0, a1), el_end, n, wd, tip, kind in groups:
        for j in range(n):
            az = a0 + (a1 - a0) * (j + rng.uniform(0.2, 0.8)) / n
            el_e = el_end + rng.uniform(-4, 4)
            pts = [crown + rng.uniform(-0.01, 0.01, 3) * (1, 1, 0)]
            for t in (0.25, 0.5, 0.75, 1.0):
                el = 82 * (1 - t) + el_e * t
                lift = 0.026 * (1 - t) ** 1.5 + 0.006 + 0.005 * math.sin(t * 3)  # volume on top
                pts.append(surf(az, el, lift))
            end = pts[-1]
            if kind == "down":
                tipd = np.array((0.15 * math.sin(math.radians(az)), -0.25 * math.cos(math.radians(az)), -1.0))
            elif kind == "fwd":
                tipd = np.array((0.2 * math.sin(math.radians(az)), -0.8, -0.4))
            elif kind == "up":
                tipd = np.array((0.3 * math.sin(math.radians(az)), 0.5, 0.8))
            else:
                tipd = np.array((0.3 * math.sin(math.radians(az)), 0.6, -0.6))
            tipd /= np.linalg.norm(tipd)
            pts.append(end + tipd * tip * rng.uniform(0.8, 1.3))
            locks.append((pts, wd * rng.uniform(0.85, 1.15), az))
    for pts, wd, az in locks:
        m = len(pts) - 1
        for i in range(m):
            r0 = wd * 0.5 * (1 - 0.55 * i / m)
            r1 = wd * 0.5 * (1 - 0.55 * (i + 1) / m) if i < m - 1 else 0.0018
            nrm = (pts[i] + pts[i + 1]) / 2 - cc
            L.cone(pts[i], pts[i + 1], r0, r1, H, HAIR, k=0.006 if i < m - 1 else 0.003, squash=(0.38, 1.0), up=nrm)
        L.groove(pts[1:-1], 0.0022, 0.0012)                                           # lock separation
        if 12 <= az <= 26:
            for a_, b_ in zip(pts[:-1], pts[1:]):
                L.paint("cone", a_, b_, 0.014, 0.009, color=RED, soft=0.003)
    # brows: low-relief, tapered (the colour is painted onto the skin in head_forms)
    for sx in (1, -1):
        L.cone((0.008 * sx, -0.1005, 1.705), (0.029 * sx, -0.0995, 1.7125), 0.0042, 0.0038, H, HAIR, k=0.003,
               squash=(1.0, 0.28), up=(sx, 0, 0))
        L.cone((0.029 * sx, -0.0995, 1.7125), (0.053 * sx, -0.0835, 1.7105), 0.0038, 0.0012, H, HAIR, k=0.003,
               squash=(1.0, 0.28), up=(sx, 0, 0))
    return L


def all_layers(B):
    body = body_layer(B)
    return [body, eye_layer(), top_layer(B, body), accent_layer(B), trouser_layer(B, body), knee_layer(B),
            boot_layer(B), glove_layer(B), belt_layer(B, body), sash_layer(B), hair_layer(B)]
