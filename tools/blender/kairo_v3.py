"""Kairo, third sculpt — anime-proportioned, built from anatomical sections.

What changed from kairo_v2_shells (which read as a toy):
  * limbs are `Shell.limb` tubes whose sections bulge on one side only
    (quadriceps in front, calf behind, brachioradialis outside) and taper to
    real wrists, knees and ankles instead of even cylinders;
  * 8-head heroic proportions: small head, wide shoulders, narrow waist;
  * the top has short sleeve caps, so no bare shoulder "ball joints";
  * hands are fists with separate curled fingers and a thumb;
  * feet are shaped boots (heel, arch, toe cap), not blocks;
  * the face is drawn the way the approved 2D sheet draws it: a clean anime
    head with a sharp jaw, a small nose, and eyes, lashes, brows and mouth
    as crisp shapes — no realistic folds that turn doll-like under cel shading;
  * hair is short swept locks with one red streak, not a crown of spikes.
"""

from mathutils import Vector


def V(*a):
    return Vector(a)


def shells(B, bones, Shell):
    P = {n: (Vector(h), Vector(t)) for n, (h, t, _p, _c) in B.items()}
    SKIN, SKIN_D, LIP = (0.6, 0.38, 0.27), (0.44, 0.25, 0.17), (0.4, 0.2, 0.15)
    TOP, TOP_L = (0.05, 0.052, 0.066), (0.13, 0.135, 0.165)
    PANTS, GUARD, BOOT = (0.045, 0.047, 0.06), (0.2, 0.21, 0.25), (0.07, 0.072, 0.09)
    SASH, SASH_D = (0.55, 0.03, 0.025), (0.33, 0.015, 0.015)
    HAIR, HAIR_L, STREAK = (0.03, 0.028, 0.034), (0.075, 0.07, 0.085), (0.62, 0.05, 0.035)
    WHITE, IRIS, INK = (0.92, 0.9, 0.86), (0.4, 0.1, 0.05), (0.02, 0.015, 0.02)
    out = []

    def S(name, slot, **kw):
        s = Shell(name, slot, bones, **kw)
        out.append(s)
        return s

    def along(a, b, rows, sx=1, scale=1.0, grow=0.0):
        """rows: (t, r_outer, r_inner, r_front, r_back) → limb rings a→b."""
        rings = []
        for t, ro, ri, rf, rb in rows:
            ro, ri, rf, rb = (r * scale + grow for r in (ro, ri, rf, rb))
            rings.append((a.lerp(b, t), ro if sx > 0 else ri, ri if sx > 0 else ro, rf, rb))
        return rings

    UPPER_ARM = [(0.0, .060, .056, .058, .060), (0.22, .061, .052, .060, .064), (0.45, .057, .049, .064, .063),
                 (0.7, .049, .045, .054, .053), (0.9, .043, .041, .045, .047), (1.0, .041, .040, .043, .046)]
    FOREARM = [(0.0, .041, .040, .043, .046), (0.14, .050, .045, .046, .046), (0.32, .053, .045, .046, .043),
               (0.6, .042, .038, .038, .035), (0.85, .034, .031, .029, .028), (1.0, .031, .029, .026, .026)]
    THIGH = [(-0.06, .066, .090, .096, .104), (0.1, .076, .090, .104, .104), (0.3, .078, .082, .104, .096),
             (0.55, .070, .071, .093, .084), (0.8, .059, .059, .074, .066), (1.0, .053, .053, .062, .058)]
    SHIN = [(0.0, .053, .053, .062, .058), (0.12, .057, .054, .056, .066), (0.3, .059, .053, .051, .073),
            (0.5, .051, .046, .046, .062), (0.75, .041, .039, .042, .046), (1.0, .037, .036, .042, .042)]

    # ============================================================ body ====
    b = S("body", "Skin", voxel=0.0036, smooth=7, tris=8000, weight_blur=7, cavity=0.9)
    # Head: 0.225 tall (8 heads in 1.80 m). Skull, then a face that narrows to
    # a sharp chin — sections run top to bottom.
    b.ell((0, 0.012, 1.702), (0.0745, 0.09, 0.086), "Head", SKIN)
    b.limb([(V(0, -0.004, 1.722), .070, .070, .078, .060), (V(0, -0.004, 1.69), .0725, .0725, .0825, .066),
            (V(0, -0.004, 1.655), .0705, .0705, .0835, .064), (V(0, -0.004, 1.63), .0595, .0595, .081, .056),
            (V(0, -0.006, 1.607), .044, .044, .077, .046), (V(0, -0.012, 1.591), .029, .029, .069, .034),
            (V(0, -0.02, 1.58), .018, .018, .056, .02)], "Head", SKIN, segs=28)
    b.ell((0, -0.074, 1.693), (0.056, 0.014, 0.011), "Head", SKIN)                       # brow ridge
    b.limb([(V(0, -0.082, 1.682), .006, .006, .006, .01), (V(0, -0.091, 1.66), .0065, .0065, .008, .012),
            (V(0, -0.098, 1.641), .0085, .0085, .011, .014), (V(0, -0.091, 1.632), .0075, .0075, .006, .012)],
           "Head", SKIN, segs=12)                                                        # nose: a clean wedge
    for sx in (1, -1):
        b.ell((sx * 0.049, -0.05, 1.648), (0.02, 0.026, 0.018), "Head", SKIN)            # cheekbone
        b.ell((sx * 0.076, 0.012, 1.657), (0.0075, 0.016, 0.026), "Head", SKIN_D, rot=(0, sx * 10, sx * 16))   # ear
    # Neck and the top of the shoulders (the rest of the torso is under the top).
    b.limb([(V(0, 0.02, 1.43), .078, .078, .066, .07), (V(0, 0.012, 1.5), .066, .066, .06, .064),
            (V(0, 0.004, 1.56), .06, .06, .057, .06), (V(0, 0.0, 1.61), .057, .057, .055, .057)], "Neck", SKIN)
    for sx in (1, -1):
        b.limb([(V(sx * 0.012, -0.012, 1.47), .013, .013, .016, .014), (V(sx * 0.04, -0.008, 1.6), .011, .011, .014, .012)],
               "Neck", SKIN, segs=10)                                                    # sternomastoid
    for side, sx in (("Left", 1), ("Right", -1)):
        sh, el = P[f"{side}UpperArm"]
        wr = P[f"{side}Hand"][0]
        ua, la = f"{side}UpperArm", f"{side}LowerArm"
        b.limb(along(sh, el, UPPER_ARM, sx), ua, SKIN)
        b.ell(sh.lerp(el, 0.47) + V(-sx * 0.004, -0.03, 0), (0.04, 0.04, 0.085), ua, SKIN)        # biceps
        b.ell(sh.lerp(el, 0.4) + V(sx * 0.012, 0.03, 0), (0.042, 0.04, 0.1), ua, SKIN)            # triceps
        b.ell(sh.lerp(el, 0.2) + V(sx * 0.02, 0, 0), (0.046, 0.058, 0.075), ua, SKIN)             # deltoid insertion
        b.limb(along(el, wr, FOREARM, sx), la, SKIN)
        b.ell(el + V(0, 0.03, 0.004), (0.022, 0.02, 0.024), la, SKIN)                             # elbow point
        b.crease(sh.lerp(el, 0.3) + V(sx * 0.055, -0.03, 0), sh.lerp(el, 0.62) + V(sx * 0.03, -0.05, 0), 0.01, 0.003)
        b.crease(sh.lerp(el, 0.42) + V(sx * 0.058, 0.0, 0), el + V(sx * 0.04, 0.004, 0.03), 0.008, 0.003)
        b.crease(sh.lerp(el, 0.42) + V(-sx * 0.048, 0.0, 0), el + V(-sx * 0.036, 0.0, 0.03), 0.008, 0.0025)
        b.dent(el + V(0, -0.04, 0.0), 0.018, 0.0035)

    # ============================================================= top ====
    t = S("top", "Cloth2", voxel=0.0042, smooth=7, tris=6400, weight_blur=7, cavity=1.3)
    rows = [(1.0, .150, .100, .104, 0.0), (1.07, .139, .098, .098, 0.0), (1.13, .141, .100, .099, 0.0),
            (1.21, .158, .108, .106, 0.0), (1.29, .188, .120, .118, 0.002), (1.37, .212, .130, .128, 0.004),
            (1.43, .214, .118, .124, 0.008), (1.485, .168, .092, .104, 0.012), (1.525, .08, .07, .078, 0.012)]
    names = ["Hips", "Hips", "Spine", "Spine", "Chest", "Chest", "Chest", "Chest"]
    t.limb([(V(0, y, z), rx, rx, rf, rb) for z, rx, rf, rb, y in rows], names, TOP, segs=36, sq=2.35)
    for sx in (1, -1):
        t.ell((sx * 0.092, -0.076, 1.385), (0.096, 0.044, 0.062), "Chest", TOP, rot=(8, sx * 8, 0))      # pectoral
        t.ell((sx * 0.168, 0.034, 1.31), (0.036, 0.075, 0.115), "Chest", TOP)                                 # latissimus
        t.ell((sx * 0.085, 0.092, 1.385), (0.075, 0.04, 0.085), "Chest", TOP)                             # shoulder blade
        t.ell((sx * 0.105, 0.024, 1.47), (0.12, 0.066, 0.036), "Chest", TOP, rot=(0, sx * 22, 0))        # trapezius
        t.ell((sx * 0.045, 0.094, 1.17), (0.036, 0.026, 0.11), "Spine", TOP)                              # spinal erector
        for k, zz in enumerate((1.25, 1.195, 1.14, 1.085)):
            t.ell((sx * 0.036, -0.088 + k * 0.002, zz), (0.032, 0.014, 0.024), "Spine", TOP)              # abdominals
        t.ell((sx * 0.118, -0.03, 1.1), (0.03, 0.06, 0.07), "Spine", TOP)                                 # oblique
    for side, sx in (("Left", 1), ("Right", -1)):                                                         # sleeve caps
        sh, el = P[f"{side}UpperArm"]
        ua = f"{side}UpperArm"
        t.ell(sh + V(-sx * 0.008, 0.002, -0.024), (0.066, 0.072, 0.088), ua, TOP, rot=(0, sx * 10, 0))
        t.limb(along(sh, el, [r for r in UPPER_ARM if r[0] <= 0.25] + [(0.33, .060, .051, .062, .064)], sx, grow=0.007), ua, TOP)
    t.crease((0, -0.134, 1.44), (0, -0.124, 1.31), 0.011, 0.005)                                # sternum
    t.crease((0, -0.118, 1.3), (0, -0.104, 1.05), 0.007, 0.004)                                 # linea alba
    t.crease((0, 0.128, 1.46), (0, 0.104, 1.06), 0.015, 0.007)                                  # spine
    for sx in (1, -1):
        t.crease((sx * 0.014, -0.126, 1.322), (sx * 0.1, -0.12, 1.312), 0.011, 0.005)          # under the pectoral
        t.crease((sx * 0.1, -0.12, 1.312), (sx * 0.178, -0.076, 1.348), 0.011, 0.0045)
        t.crease((sx * 0.178, -0.076, 1.348), (sx * 0.196, -0.04, 1.4), 0.01, 0.004)
        for zz in (1.222, 1.167, 1.112):
            t.crease((sx * 0.006, -0.112, zz), (sx * 0.072, -0.102, zz + 0.003), 0.007, 0.0036)   # abdominal rows
        t.crease((sx * 0.076, -0.102, 1.285), (sx * 0.084, -0.092, 1.06), 0.007, 0.0036)       # rectus edge
        t.crease((sx * 0.06, 0.118, 1.42), (sx * 0.15, 0.088, 1.3), 0.012, 0.004)              # shoulder blade
        t.crease((sx * 0.158, 0.07, 1.28), (sx * 0.098, 0.096, 1.12), 0.011, 0.0035)           # lat edge
    hem = S("sleeve_hems", "Cloth2", voxel=0.004, smooth=2, tris=1000, weight_blur=3, cavity=1.2)
    col = S("collar", "Cloth2", voxel=0.004, smooth=2, tris=800, weight_blur=2, cavity=1.2)
    col.limb([(V(0, 0.012, 1.492), .08, .08, .075, .079), (V(0, 0.008, 1.548), .069, .069, .066, .069)], "Neck", TOP_L, segs=28)
    sg = S("shoulder_guards", "Cloth2", voxel=0.004, smooth=2, tris=1600, weight_blur=3, cavity=1.5)
    for side, sx in (("Left", 1), ("Right", -1)):
        sh, el = P[f"{side}UpperArm"]
        ua = f"{side}UpperArm"
        hem.limb(along(sh, el, [(0.3, .060, .051, .062, .064), (0.36, .059, .050, .063, .064)], sx, grow=0.0105), ua, TOP_L)
        sg.ell(sh + V(sx * 0.014, 0.0, 0.024), (0.052, 0.06, 0.016), ua, GUARD, rot=(0, sx * 38, 0))        # upper plate
    line = S("origin_line", "Accent", voxel=0, tris=0, weight_blur=0)
    line.box((0.024, -0.136, 1.385), (0.011, 0.016, 0.17), "Chest", (1, 1, 1), rot=(5, 0, 0))
    line.box((0.03, -0.117, 1.2), (0.01, 0.018, 0.2), "Spine", (1, 1, 1), rot=(-5, 0, 0))
    line.box((0.064, -0.128, 1.44), (0.066, 0.016, 0.01), "Chest", (1, 1, 1), rot=(0, -28, 0))

    # ========================================= forearm guards and fists ===
    g = S("gauntlets", "Cloth2", voxel=0.0034, smooth=3, tris=4200, weight_blur=4, cavity=1.6)
    gl = S("glove_lines", "Accent", voxel=0, tris=0, weight_blur=0)
    for side, sx in (("Left", 1), ("Right", -1)):
        el = P[f"{side}LowerArm"][0]
        wr, ht = P[f"{side}Hand"]
        la, hd = f"{side}LowerArm", f"{side}Hand"
        g.limb(along(el, wr, [r for r in FOREARM if 0.3 < r[0]] , sx, grow=0.007), la, GUARD)
        g.limb(along(el, wr, [(0.3, .053, .045, .046, .043), (0.37, .051, .044, .045, .042)], sx, grow=0.011), la, TOP_L)   # cuff
        g.ell(el.lerp(wr, 0.62) + V(sx * 0.038, 0.002, 0), (0.014, 0.027, 0.075), la, TOP_L)                # outer plate
        d = (ht - wr).normalized()
        inn = V(-sx, 0, 0)                      # toward the thigh: the palm side
        pc = wr + d * 0.062
        g.limb([(wr - d * 0.012, .031, .031, .028, .028), (wr + d * 0.02, .03, .03, .04, .038),
                (pc, .029, .029, .048, .046), (pc + d * 0.036, .026, .026, .046, .043)], hd, TOP, segs=20)     # wrist → back of hand
        for k, yy in enumerate((-0.034, -0.0115, 0.011, 0.033)):
            r = (0.0125, 0.013, 0.0125, 0.011)[k]
            kn = pc + d * (0.04 + (0.004, 0.008, 0.006, 0.0)[k]) + V(sx * 0.012, yy, 0)
            mid = kn + inn * 0.04 + d * 0.004
            tip = mid - d * 0.036 + inn * 0.002
            g.ell(kn, (r * 1.15, r * 1.02, r * 1.1), hd, GUARD)                                           # knuckle
            g.limb([(kn, r, r, r * .95, r * .95), (mid, r * .95, r * .95, r * .9, r * .9)], hd, TOP, segs=10)
            g.ell(mid, (r, r * .95, r), hd, TOP)
            g.limb([(mid, r * .9, r * .9, r * .9, r * .9), (tip, r * .8, r * .8, r * .8, r * .8)], hd, TOP, segs=10)
        th0 = wr + d * 0.03 + V(-sx * 0.012, -0.036, 0)
        th1 = pc + d * 0.01 + V(-sx * 0.03, -0.05, 0)
        th2 = pc + d * 0.04 + V(-sx * 0.046, -0.03, 0)
        g.limb([(th0, .017, .017, .016, .016), (th1, .0145, .0145, .014, .014), (th2, .012, .012, .012, .012)], hd, TOP, segs=10)
        g.ell(th2, (0.012, 0.012, 0.013), hd, TOP)
        g.crease(wr + V(sx * 0.04, 0, 0.004), wr + V(-sx * 0.04, 0, 0.004), 0.005, 0.0025)
        g.crease(wr + V(0, -0.04, 0.004), wr + V(0, 0.04, 0.004), 0.005, 0.0025)
        gl.box(el.lerp(wr, 0.62) + V(sx * 0.054, 0.002, 0), (0.005, 0.011, 0.12), la, (1, 1, 1))

    # ======================================================== trousers ====
    p = S("trousers", "Cloth", voxel=0.0046, smooth=6, tris=6200, weight_blur=7, cavity=1.4)
    p.limb([(V(0, 0.004, 0.8), .1, .1, .082, .095), (V(0, 0.006, 0.88), .166, .166, .1, .116), (V(0, 0.006, 0.96), .168, .168, .104, .118),
            (V(0, 0, 1.05), .152, .152, .102, .106)], "Hips", PANTS, segs=32, sq=2.3)
    for side, sx in (("Left", 1), ("Right", -1)):
        hip, knee = P[f"{side}UpperLeg"]
        ankle = P[f"{side}Foot"][0]
        ul, ll = f"{side}UpperLeg", f"{side}LowerLeg"
        p.limb(along(hip, knee, THIGH, sx, grow=0.006), ul, PANTS)
        p.ell(hip.lerp(knee, 0.42) + V(sx * 0.014, -0.05, 0), (0.05, 0.05, 0.15), ul, PANTS)        # quadriceps
        p.ell(hip.lerp(knee, 0.72) + V(-sx * 0.03, -0.035, 0), (0.03, 0.035, 0.06), ul, PANTS)      # inner quad teardrop
        p.ell(hip.lerp(knee, 0.42) + V(0, 0.05, 0), (0.055, 0.045, 0.14), ul, PANTS)                # hamstring
        p.ell((sx * 0.085, 0.085, 0.94), (0.075, 0.06, 0.08), "Hips", PANTS)                        # glute
        p.limb(along(knee, ankle, [r for r in SHIN if r[0] <= 0.5] + [(0.56, .05, .046, .047, .058)], sx, grow=0.006), ll, PANTS)
        p.crease(hip + V(sx * 0.078, 0, 0.02), knee + V(sx * 0.064, 0, 0), 0.004, 0.002)              # outer seam
        for dz, w in ((0.03, 0.07), (-0.01, 0.085), (-0.05, 0.06)):                                 # folds from the crotch
            p.crease((sx * 0.02, -0.1, 0.85 + dz), (sx * w, -0.11, 0.89 + dz * 0.5), 0.008, 0.0036)
        p.crease(knee + V(-0.045, 0.058, 0.02), knee + V(0.045, 0.058, 0.02), 0.008, 0.0045)         # behind the knee
        p.crease(knee + V(-sx * 0.05, -0.03, 0.05), knee + V(sx * 0.05, -0.04, 0.075), 0.007, 0.003)  # above the knee
        for tt in (0.44, 0.5):                                                                      # bunching over the boot
            c = knee.lerp(ankle, tt)
            p.crease(c + V(-0.06, -0.03, 0), c + V(0.06, -0.03, 0.006), 0.006, 0.003)
    p.crease((0, -0.108, 1.02), (0, -0.096, 0.86), 0.005, 0.0025)                                   # fly
    kn = S("knee_guards", "Cloth2", voxel=0.004, smooth=2, tris=1500, weight_blur=2, cavity=1.5)
    for side, sx in (("Left", 1), ("Right", -1)):
        hip, knee = P[f"{side}UpperLeg"]
        kn.ell(knee + V(0, -0.052, 0.0), (0.046, 0.026, 0.062), f"{side}LowerLeg", GUARD)
        kn.ell(knee + V(0, -0.066, 0.004), (0.03, 0.018, 0.042), f"{side}LowerLeg", TOP_L)
        kn.limb(along(hip, knee, [(0.4, .074, .077, .099, .09), (0.46, .072, .074, .096, .087)], sx, grow=0.011),
                f"{side}UpperLeg", TOP_L)                                                           # thigh strap
    belt = S("belt", "Cloth2", voxel=0.004, smooth=1, tris=1700, weight_blur=0, cavity=1.5)
    belt.limb([(V(0, 0, 1.012), .157, .157, .109, .111), (V(0, 0, 1.068), .15, .15, .107, .109)], "Hips", TOP_L, segs=36, sq=2.3)
    for x, y in ((0.158, 0.0), (0.095, 0.098), (-0.095, 0.098)):
        belt.box((x, y, 0.998), (0.05, 0.036, 0.07), "Hips", GUARD, rot=(0, 0, 0 if y else 90))
    buckle = S("buckle", "Accent", voxel=0, tris=0, weight_blur=0)
    buckle.box((0, -0.112, 1.04), (0.046, 0.012, 0.036), "Hips", (1, 1, 1))

    # ============================================== torn red sash =========
    sa = S("sash", "Cloth", voxel=0.004, smooth=4, tris=3000, weight_blur=6, cavity=2.0)
    pts = [(V(-0.1, -0.114, 1.04), .07, "Hips"), (V(-0.13, -0.128, 0.94), .09, "Hips"), (V(-0.158, -0.13, 0.82), .105, "RightUpperLeg"),
           (V(-0.178, -0.126, 0.69), .108, "RightUpperLeg"), (V(-0.2, -0.118, 0.56), .095, "RightUpperLeg"),
           (V(-0.212, -0.11, 0.47), .07, "RightUpperLeg")]
    sa.limb([(c, w, w, .012, .012) for c, w, _b in pts], [bn for _c, _w, bn in pts[:-1]], SASH, segs=18)
    for dx, ln, w0 in ((-0.065, 0.15, 0.03), (-0.01, 0.24, 0.036), (0.05, 0.12, 0.03)):               # torn tails
        a = V(-0.208 + dx, -0.112, 0.5)
        sa.limb([(a, w0, w0, .01, .01), (a + V(-0.012, 0.004, -ln * 0.55), w0 * .6, w0 * .6, .008, .008),
                 (a + V(-0.02 + dx * 0.2, 0.006, -ln), .004, .004, .003, .003)], "RightUpperLeg", SASH_D, segs=10)
    for dx in (-0.05, 0.0, 0.05):                                                                 # hanging folds
        sa.limb([(V(-0.11 + dx, -0.126, 1.0), .016, .016, .007, .007), (V(-0.16 + dx, -0.132, 0.8), .024, .024, .009, .009),
                 (V(-0.2 + dx, -0.122, 0.54), .014, .014, .006, .006)], "RightUpperLeg", SASH, segs=8)
    sa.limb([(V(-0.125, 0.1, 1.04), .065, .065, .011, .011), (V(-0.16, 0.128, 0.86), .08, .08, .011, .011),
             (V(-0.19, 0.13, 0.66), .03, .03, .006, .006)], "Hips", SASH_D, segs=12)                 # back tail
    sa.ell((-0.105, -0.118, 1.04), (0.04, 0.024, 0.034), "Hips", SASH)                             # knot

    # =========================================================== boots ====
    bt = S("boots", "Cloth2", voxel=0.0036, smooth=3, tris=3800, weight_blur=5, cavity=1.5)
    bl = S("boot_lines", "Accent", voxel=0, tris=0, weight_blur=0)
    for side, sx in (("Left", 1), ("Right", -1)):
        knee = P[f"{side}LowerLeg"][0]
        ankle = P[f"{side}Foot"][0]
        ll, ft = f"{side}LowerLeg", f"{side}Foot"
        x = ankle.x
        bt.limb(along(knee, ankle, [(0.5, .051, .046, .046, .062), (0.75, .042, .04, .043, .048), (0.93, .039, .038, .044, .045),
                                    (1.06, .04, .04, .048, .048)], sx, grow=0.009), ll, BOOT)        # shaft follows the calf
        bt.limb(along(knee, ankle, [(0.48, .051, .046, .046, .062), (0.55, .05, .045, .046, .06)], sx, grow=0.015), ll, TOP_L)   # cuff
        bt.ell(knee.lerp(ankle, 0.72) + V(0, -0.05, 0), (0.036, 0.018, 0.09), ll, GUARD)            # shin plate
        # Foot: heel, arch and toe as sections running forward (−Y).
        bt.limb([(V(x, 0.07, 0.05), .03, .03, .034, .03), (V(x, 0.035, 0.056), .043, .043, .052, .05),
                 (V(x, -0.02, 0.054), .044, .042, .05, .055), (V(x + sx * 0.004, -0.085, 0.046), .05, .044, .042, .044),
                 (V(x + sx * 0.006, -0.15, 0.04), .052, .046, .036, .034), (V(x + sx * 0.004, -0.2, 0.034), .042, .038, .03, .022),
                 (V(x + sx * 0.002, -0.222, 0.03), .024, .022, .024, .012)], ft, BOOT, segs=22)
        bt.ell((x + sx * 0.005, -0.172, 0.043), (0.05, 0.05, 0.036), ft, GUARD)                     # toe cap
        bt.box((x + sx * 0.003, -0.065, 0.011), (0.094, 0.292, 0.022), ft, (0.012, 0.012, 0.014))   # sole
        bt.box((x, 0.045, 0.014), (0.082, 0.07, 0.028), ft, (0.012, 0.012, 0.014))                  # heel block
        for tt in (0.68, 0.84):
            bt.limb(along(knee, ankle, [(tt, .044, .041, .044, .05), (tt + 0.035, .043, .04, .044, .049)], sx, grow=0.014), ll, TOP_L)   # straps
        bt.crease(V(x - 0.06, -0.13, 0.07), V(x + 0.06, -0.13, 0.07), 0.005, 0.003)                 # toe-cap seam
        bt.crease(V(x - 0.06, -0.035, 0.105), V(x + 0.06, -0.035, 0.105), 0.006, 0.003)             # ankle flex
        bl.box((x + sx * 0.056, 0.004, 0.2), (0.005, 0.011, 0.085), ll, (1, 1, 1))

    # ============================================================ hair ====
    h = S("hair", "Hair", voxel=0.0034, smooth=2, tris=4000, weight_blur=0, cavity=2.0)
    h.ell((0, 0.018, 1.716), (0.0815, 0.097, 0.086), "Head", HAIR)
    h.ell((0, 0.066, 1.672), (0.07, 0.052, 0.06), "Head", HAIR)

    def lock(pts, w, th, c=HAIR):
        """A flat tapering lock of hair through 3 points."""
        a, m, e = (Vector(q) for q in pts)
        h.limb([(a, w, w, th, th), (a.lerp(m, 0.6), w * .95, w * .95, th * .95, th * .95), (m, w * .7, w * .7, th * .8, th * .8),
                (m.lerp(e, 0.6), w * .36, w * .36, th * .5, th * .5), (e, .002, .002, .002, .002)], "Head", c, segs=10)

    # fringe: falls forward over the forehead, parted to his left; one red lock
    lock(((0.004, -0.058, 1.78), (0.022, -0.094, 1.745), (0.034, -0.097, 1.694)), .019, .011, STREAK)
    lock(((-0.022, -0.058, 1.78), (-0.012, -0.096, 1.748), (-0.004, -0.099, 1.702)), .019, .011)
    lock(((-0.046, -0.05, 1.776), (-0.044, -0.09, 1.744), (-0.04, -0.092, 1.705)), .018, .011)
    lock(((0.036, -0.052, 1.778), (0.054, -0.084, 1.748), (0.062, -0.082, 1.7)), .018, .011)
    lock(((-0.064, -0.034, 1.768), (-0.073, -0.068, 1.735), (-0.074, -0.066, 1.685)), .017, .011)
    lock(((0.064, -0.034, 1.768), (0.078, -0.06, 1.738), (0.08, -0.054, 1.69)), .017, .011)
    for sx in (1, -1):                                                         # in front of the ears
        lock(((sx * 0.076, -0.012, 1.735), (sx * 0.082, -0.03, 1.69), (sx * 0.078, -0.036, 1.64)), .015, .009)
    # crown: short tufts swept up and back
    for a, m, e, w in (((0.0, -0.03, 1.795), (0.008, -0.045, 1.83), (0.03, -0.085, 1.845), .024),
                       ((-0.035, -0.02, 1.79), (-0.05, -0.03, 1.826), (-0.075, -0.07, 1.842), .022),
                       ((0.038, -0.02, 1.79), (0.06, -0.02, 1.824), (0.095, -0.04, 1.84), .022),
                       ((0.0, 0.02, 1.8), (0.0, 0.03, 1.838), (0.012, 0.02, 1.868), .026),
                       ((-0.045, 0.03, 1.79), (-0.07, 0.045, 1.82), (-0.102, 0.05, 1.838), .022),
                       ((0.045, 0.03, 1.79), (0.07, 0.05, 1.818), (0.1, 0.07, 1.834), .022),
                       ((0.0, 0.07, 1.782), (0.0, 0.1, 1.806), (0.0, 0.14, 1.812), .024),
                       ((-0.072, 0.0, 1.768), (-0.094, 0.01, 1.786), (-0.118, 0.02, 1.79), .018),
                       ((0.072, 0.0, 1.768), (0.094, 0.01, 1.786), (0.118, 0.025, 1.788), .018),
                       ((-0.05, 0.085, 1.755), (-0.07, 0.115, 1.76), (-0.088, 0.145, 1.75), .02),
                       ((0.05, 0.085, 1.755), (0.07, 0.115, 1.76), (0.09, 0.142, 1.748), .02),
                       ((0.0, 0.105, 1.72), (0.0, 0.126, 1.69), (0.0, 0.132, 1.645), .022),
                       ((-0.04, 0.098, 1.7), (-0.05, 0.115, 1.67), (-0.052, 0.116, 1.632), .018),
                       ((0.04, 0.098, 1.7), (0.05, 0.115, 1.67), (0.052, 0.116, 1.632), .018)):
        lock((a, m, e), w, w * 0.62)

    # ============================================ face, drawn anime-style ==
    f = S("face_ink", "Hair", voxel=0, tris=0, weight_blur=0)
    e = S("eyes", "Skin", voxel=0, tris=0, weight_blur=0)
    for sx in (1, -1):
        yaw = sx * 20
        e.ell((sx * 0.031, -0.0745, 1.6605), (0.0165, 0.006, 0.0078), "Head", WHITE, rot=(0, sx * -6, yaw), segs=18, rings=10)
        e.ell((sx * 0.0295, -0.0792, 1.6612), (0.0074, 0.0028, 0.0078), "Head", IRIS, rot=(0, 0, yaw), segs=16, rings=8)
        e.ell((sx * 0.0293, -0.0812, 1.6612), (0.0036, 0.0016, 0.004), "Head", INK, rot=(0, 0, yaw), segs=12, rings=6)
        e.ell((sx * 0.0312, -0.0822, 1.6638), (0.0015, 0.0008, 0.0015), "Head", (1, 1, 1), rot=(0, 0, yaw), segs=8, rings=4)
        f.ell((sx * 0.031, -0.0762, 1.669), (0.0195, 0.0062, 0.0034), "Head", INK, rot=(0, sx * -9, yaw), segs=16, rings=6)    # upper lash
        f.ell((sx * 0.0485, -0.0668, 1.6665), (0.006, 0.004, 0.005), "Head", INK, rot=(0, sx * 30, sx * 38), segs=10, rings=6)  # outer corner
        f.ell((sx * 0.033, -0.0755, 1.6525), (0.012, 0.004, 0.0012), "Head", SKIN_D, rot=(0, sx * 4, yaw), segs=12, rings=4)   # lower lid
        f.ell((sx * 0.033, -0.0795, 1.6865), (0.024, 0.006, 0.0052), "Head", INK, rot=(0, sx * -16, yaw * 0.8), segs=16, rings=6)   # brow, angled down to the nose
    f.ell((0, -0.0812, 1.6105), (0.019, 0.004, 0.0016), "Head", (0.2, 0.08, 0.07), segs=14, rings=4)       # mouth line
    f.ell((0, -0.079, 1.6005), (0.009, 0.004, 0.0012), "Head", SKIN_D, segs=10, rings=4)                    # lower-lip shadow
    return out
