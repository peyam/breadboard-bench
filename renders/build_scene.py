"""Blender scene builder for the PC-2 renders (run with plain python3; uses the bpy module).

    python3 build_scene.py board <slug> out.png [width height samples]
    python3 build_scene.py machine out.png [...]
    python3 build_scene.py empty out.png | cutaway out.png | closeup out.png

Units: 1 Blender unit = 1 cm. Everything is placed from scene.json, which comes from the
same layout the book's wire lists come from, so the renders show the real build.
"""
import json
import math
import os
import sys

import bpy
if "--" in sys.argv:
    sys.argv = [sys.argv[0]] + sys.argv[sys.argv.index("--") + 1:]
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "..", "fonts", "lexend-latin-600-normal.ttf")
TEX = os.path.join(HERE, "_tex")
os.makedirs(TEX, exist_ok=True)
P = 0.254                     # hole pitch, cm
COL = {c: i for i, c in enumerate("abcde")}
COL.update({c: i + 7 for i, c in enumerate("fghij")})
RAILY = {"B-": -2.2, "B+": -3.2, "T-": 13.2, "T+": 14.2}
BOARD_W, BOARD_H, BOARD_T = 16.51, 5.46, 0.85
LEDC = {"red": (0.95, 0.12, 0.08), "green": (0.12, 0.85, 0.2), "yellow": (1.0, 0.75, 0.05), "sky": (0.1, 0.35, 1.0)}


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def srgb_to_lin(c):
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)


# ------------------------------------------------------------------ materials
_mats = {}


def mat(name, rgb, rough=0.5, metal=0.0, emit=None, strength=0.0, image=None, transmission=0.0, coat=0.0):
    key = (name, rgb, rough, metal, emit, strength, image, transmission)
    if key in _mats:
        return _mats[key]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*srgb_to_lin(rgb), 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if transmission:
        b.inputs["Transmission Weight"].default_value = transmission
    if coat:
        b.inputs["Coat Weight"].default_value = coat
    if emit is not None:
        b.inputs["Emission Color"].default_value = (*srgb_to_lin(emit), 1)
        b.inputs["Emission Strength"].default_value = strength
    if image:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(image)
        nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    _mats[key] = m
    return m


def box(name, x, y, z, sx, sy, sz, m, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z))
    o = bpy.context.active_object
    o.name = name
    o.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    if bevel:
        mod = o.modifiers.new("bev", "BEVEL")
        mod.width = bevel
        mod.segments = 2
    o.data.materials.append(m)
    return o


def cyl(name, x, y, z, r, h, m, rot=(0, 0, 0), verts=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=h, location=(x, y, z), rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(m)
    bpy.ops.object.shade_smooth()
    return o


def sphere(name, x, y, z, r, m):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=(x, y, z), segments=20, ring_count=10)
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(m)
    bpy.ops.object.shade_smooth()
    return o


def textured_plane(name, x, y, z, sx, sy, image, rough=0.6):
    bpy.ops.mesh.primitive_plane_add(size=1, location=(x, y, z))
    o = bpy.context.active_object
    o.name = name
    o.scale = (sx, sy, 1)
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(mat(name + "_m", (1, 1, 1), rough=rough, image=image))
    return o


def curve(name, pts, radius, m):
    cd = bpy.data.curves.new(name, "CURVE")
    cd.dimensions = "3D"
    cd.bevel_depth = radius
    cd.bevel_resolution = 3
    sp = cd.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts):
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    o = bpy.data.objects.new(name, cd)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(m)
    return o


# ------------------------------------------------------------------ textures
def board_texture():
    path = os.path.join(TEX, "board.png")
    if os.path.exists(path):
        return path
    s = 20                                  # pixels per mm
    W, H = int(BOARD_W * 10 * s), int(BOARD_H * 10 * s)
    im = Image.new("RGB", (W, H), (241, 240, 234))
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FONT, int(1.5 * s))

    def xy(row, colidx):
        x = (BOARD_W * 10 / 2) + ((row - 32) * 2.54)
        y = (BOARD_H * 10 / 2) - ((colidx - 5.5) * 2.54)
        return x * s, y * s

    # centre channel
    _, y1 = xy(1, 5.0)
    _, y2 = xy(1, 6.0)
    d.rectangle([0, min(y1, y2), W, max(y1, y2)], fill=(222, 220, 212))
    for row in range(1, 64):
        for c, ci in COL.items():
            x, y = xy(row, ci)
            d.rectangle([x - 0.55 * s, y - 0.55 * s, x + 0.55 * s, y + 0.55 * s], fill=(58, 56, 52))
        if row % 5 == 0 or row == 1:
            x, y = xy(row, -1.2)
            d.text((x, y), str(row), fill=(120, 118, 110), font=f, anchor="mm")
            x, y = xy(row, 12.2)
            d.text((x, y), str(row), fill=(120, 118, 110), font=f, anchor="mm")
    for c, ci in COL.items():
        x, y = xy(0, ci)
        d.text((x, y), c, fill=(120, 118, 110), font=f, anchor="mm")
    for rail, ry in RAILY.items():
        col = (205, 50, 40) if rail[1] == "+" else (40, 90, 180)
        for row in range(1, 64):
            if (row - 1) % 6 == 5:
                continue
            x, y = xy(row, ry)
            d.rectangle([x - 0.55 * s, y - 0.55 * s, x + 0.55 * s, y + 0.55 * s], fill=(58, 56, 52))
        _, y = xy(1, ry + (0.62 if rail in ("T+",) else -0.62 if rail == "B+" else (0.62 if rail == "T-" else -0.62)))
        if rail in ("B+", "T+"):
            yy = xy(1, ry - 0.62 if rail == "B+" else ry + 0.62)[1]
            d.line([(2 * s, yy), (W - 2 * s, yy)], fill=col, width=int(0.4 * s))
        else:
            yy = xy(1, ry + 0.62 if rail == "B-" else ry - 0.62)[1]
            d.line([(2 * s, yy), (W - 2 * s, yy)], fill=col, width=int(0.4 * s))
    im.save(path)
    return path


def chip_texture(label, ref, n, wide):
    path = os.path.join(TEX, f"chip_{label.split()[0]}_{ref}.png")
    s = 40
    L = n // 2 * 2.54
    Wd = 13.2 if wide else 6.35
    im = Image.new("RGB", (int(L * s), int(Wd * s)), (24, 24, 26))
    d = ImageDraw.Draw(im)
    f1 = ImageFont.truetype(FONT, int((2.0 if not wide else 2.6) * s))
    f2 = ImageFont.truetype(FONT, int((1.3 if not wide else 1.9) * s))
    d.text((L * s / 2, Wd * s * 0.36), label, fill=(205, 205, 200), font=f1, anchor="mm")
    d.text((L * s / 2, Wd * s * 0.70), ref, fill=(150, 150, 145), font=f2, anchor="mm")
    r = (1.0 if not wide else 1.5) * s
    d.ellipse([-r, Wd * s / 2 - r, r, Wd * s / 2 + r], fill=(12, 12, 12))
    d.ellipse([0.9 * s, Wd * s - 2.0 * s, 1.6 * s, Wd * s - 1.3 * s], fill=(45, 45, 48))
    im.save(path)
    return path


# ------------------------------------------------------------------ board
class BoardBuilder:
    def __init__(self, name, data, ox=0.0, oy=0.0):
        self.name, self.d, self.ox, self.oy = name, data, ox, oy

    def hole(self, row, col):
        x = self.ox + (row - 32) * P
        y = self.oy + (COL[col] - 5.5) * P
        return x, y

    def rail(self, rail, row):
        x = self.ox + (row - 32) * P
        y = self.oy + (RAILY[rail] - 5.5) * P
        return x, y

    def build(self):
        tex = board_texture()
        box(f"{self.name}_body", self.ox, self.oy, -BOARD_T / 2, BOARD_W, BOARD_H, BOARD_T,
            mat("bb_plastic", (0.93, 0.92, 0.89), rough=0.55), bevel=0.05)
        textured_plane(f"{self.name}_top", self.ox, self.oy, 0.001, BOARD_W, BOARD_H, tex)
        for it in self.d["items"]:
            getattr(self, "p_" + it["kind"].replace("-", "_"), self.p_other)(it)
        for i, w in enumerate(self.d["wires"]):
            self.wire(w, i)

    # parts ----------------------------------------------------------
    def p_chip(self, it):
        r1, r2 = it["rows"]
        n, wide = it["pins"], it["wide"]
        L = n // 2 * P
        Wd = 1.32 if wide else 0.635
        x = self.ox + ((r1 + r2) / 2 - 32) * P
        ymid = self.hole(r1, "e")[1] + (P * 1.5 if not wide else 0)
        if wide:
            ymid = (self.hole(r1, "c")[1] + self.hole(r1, "g")[1]) / 2      # 0.6 in: pins in c and g
        else:
            ymid = (self.hole(r1, "e")[1] + self.hole(r1, "f")[1]) / 2
        h = 0.33
        body = box(f"{it['ref']}", x, ymid, 0.15 + h / 2, L - 0.05, Wd, h, mat("chip_black", (0.06, 0.06, 0.065), rough=0.42), bevel=0.02)
        img = chip_texture(it["label"], it["ref"], n, wide)
        textured_plane(f"{it['ref']}_lab", x, ymid, 0.15 + h + 0.002, L - 0.07, Wd - 0.03, img, rough=0.45)
        pin_m = mat("pin", (0.75, 0.76, 0.78), rough=0.3, metal=1.0)
        span = (1.524 if wide else 0.762)
        for k in range(n // 2):
            px = self.ox + (r1 + k - 32) * P
            for side in (-1, 1):
                py = ymid + side * span / 2
                box(f"{it['ref']}_pin", px, py, 0.12, 0.05, 0.025, 0.26, pin_m)
                box(f"{it['ref']}_pinb", px, ymid + side * (Wd / 2 + (span / 2 - Wd / 2) / 2), 0.25,
                    0.05, (span / 2 - Wd / 2), 0.025, pin_m)

    def p_dipswitch(self, it):
        r1, r2 = it["rows"]
        L = (r2 - r1 + 1) * P
        x = self.ox + ((r1 + r2) / 2 - 32) * P
        y = (self.hole(r1, "e")[1] + self.hole(r1, "f")[1]) / 2
        box(f"{it['ref']}", x, y, 0.2, L - 0.04, 0.95, 0.4, mat("dip_red", (0.78, 0.16, 0.14), rough=0.5), bevel=0.02)
        for k in range(it["n"]):
            px = self.ox + (r1 + k - 32) * P
            on = it.get("on", [False] * it["n"])[k]
            box(f"{it['ref']}_sl", px, y + (0.18 if on else -0.18), 0.43, 0.12, 0.2, 0.08, mat("dip_white", (0.96, 0.96, 0.94), rough=0.4))

    def p_rn(self, it):
        r1, r2 = it["rows"]
        x = self.ox + ((r1 + r2) / 2 - 32) * P
        y = self.hole(r1, "j")[1]
        box(f"{it['ref']}", x, y, 0.32, (r2 - r1 + 1) * P - 0.04, 0.22, 0.5, mat("rn", (0.85, 0.72, 0.35), rough=0.55), bevel=0.02)
        sphere(f"{it['ref']}_dot", self.ox + (r1 - 32) * P, y - 0.115, 0.45, 0.025, mat("ink", (0.1, 0.1, 0.1)))

    def p_button(self, it):
        r1, r2 = it["rows"]
        x = self.ox + ((r1 + r2) / 2 - 32) * P
        y = (self.hole(r1, "e")[1] + self.hole(r1, "f")[1]) / 2
        box(f"{it['ref']}", x, y, 0.18, 0.6, 0.6, 0.35, mat("btn", (0.12, 0.12, 0.13), rough=0.5), bevel=0.02)
        cyl(f"{it['ref']}_cap", x, y, 0.45, 0.18, 0.2, mat("btn_cap", (0.55, 0.55, 0.57), rough=0.4))

    def p_spdt(self, it):
        r1, r2 = it["rows"]
        x = self.ox + ((r1 + r2) / 2 - 32) * P
        y = self.hole(r1, "h")[1]
        box(f"{it['ref']}", x, y, 0.25, 0.86, 0.38, 0.4, mat("spdt", (0.15, 0.25, 0.55), rough=0.4), bevel=0.02)
        box(f"{it['ref']}_k", x + 0.12, y, 0.52, 0.12, 0.12, 0.18, mat("spdt_k", (0.1, 0.1, 0.1)))

    p_jp = p_spdt

    def p_q(self, it):
        r1, r2 = it["rows"]
        x = self.ox + ((r1 + r2) / 2 - 32) * P
        y = self.hole(r1, "h")[1]
        cyl(f"{it['ref']}", x, y, 0.45, 0.24, 0.45, mat("to92", (0.08, 0.08, 0.08), rough=0.45), rot=(0, 0, 0))

    def p_pot(self, it):
        r1, r2 = it["rows"]
        x = self.ox + ((r1 + r2) / 2 - 32) * P
        y = self.hole(r1, "i")[1]
        box(f"{it['ref']}", x, y, 0.35, 1.0, 0.95, 0.6, mat("pot", (0.12, 0.3, 0.65), rough=0.4), bevel=0.03)
        cyl(f"{it['ref']}_k", x, y, 0.75, 0.2, 0.3, mat("pot_k", (0.85, 0.85, 0.85), rough=0.3, metal=0.6))

    def p_digit(self, it):
        r1, r2 = it["rows"]
        x = self.ox + ((r1 + r2) / 2 - 32) * P
        y = (self.hole(r1, "c")[1] + self.hole(r1, "g")[1]) / 2          # pins in c and g
        box(f"{it['ref']}", x, y, 0.4, 1.26, 1.9, 0.8, mat("digit", (0.05, 0.05, 0.05), rough=0.35), bevel=0.02)
        segs = it.get("segments", 0)
        on = mat("seg_on", (1, 0.15, 0.08), emit=(1, 0.12, 0.05), strength=8)
        off = mat("seg_off", (0.22, 0.09, 0.08), rough=0.5)
        z = 0.81
        w, h, t = 0.62, 1.1, 0.1
        S = {0: (0, h / 2, w, t), 6: (0, 0, w, t), 3: (0, -h / 2, w, t),
             5: (-w / 2, h / 4, t, h / 2), 1: (w / 2, h / 4, t, h / 2), 4: (-w / 2, -h / 4, t, h / 2), 2: (w / 2, -h / 4, t, h / 2)}
        for k, (dx, dy, sx, sy) in S.items():
            box(f"{it['ref']}_s{k}", x + dx, y + dy, z, sx * 0.92, sy * 0.92, 0.01, on if (segs >> k) & 1 else off)

    def _led(self, ref, x, y, it):
        col = LEDC.get(it.get("colour") or it.get("value"), (0.8, 0.8, 0.8))
        lit = it.get("lit")
        m = mat(f"led_{col}_{lit}", tuple(c * (1 if lit else 0.55) for c in col), rough=0.15, transmission=0.3,
                emit=col if lit else None, strength=7 if lit else 0)
        cyl(ref, x, y, 0.55, 0.15, 0.42, m)
        sphere(ref + "_dome", x, y, 0.76, 0.15, m)
        cyl(ref + "_rim", x, y, 0.36, 0.17, 0.06, m)

    def p_led_bridge(self, it):
        r = it["rows"][0]
        x, y1 = self.hole(r, "d")
        _, y2 = self.hole(r, "f")
        self._led(it["ref"], x, (y1 + y2) / 2, it)

    def p_led_rail(self, it):
        r = it["rows"][0]
        x, y1 = self.hole(r, it["hole"][1])
        _, y2 = self.rail(it["rail"], r)
        self._led(it["ref"], x, (y1 + y2) / 2, it)

    def _res(self, ref, x, y1, y2, value):
        y = (y1 + y2) / 2
        L = abs(y2 - y1)
        cyl(ref, x, y, 0.32, 0.085, min(0.62, L * 0.75), mat("res", (0.85, 0.74, 0.52), rough=0.5), rot=(math.pi / 2, 0, 0))
        lead = mat("lead", (0.7, 0.7, 0.72), rough=0.3, metal=1)
        curve(ref + "_lead", [(x, y1, 0.0), (x, y1, 0.32), (x, y2, 0.32), (x, y2, 0.0)], 0.022, lead)

    def p_r_bridge(self, it):
        r = it["rows"][0]
        x, y1 = self.hole(r, "d")
        _, y2 = self.hole(r, "f")
        self._res(it["ref"], x, y1, y2, it.get("value"))

    def p_r_rail(self, it):
        r = it["rows"][0]
        x, y1 = self.hole(r, it["hole"][1])
        _, y2 = self.rail(it["rail"], r)
        self._res(it["ref"], x, y1, y2, it.get("value"))

    def _cap(self, ref, x, y, value):
        if value and "uF" in value:
            cyl(ref, x, y, 0.35, 0.25, 0.6, mat("ecap", (0.12, 0.2, 0.55), rough=0.35))
        else:
            sphere(ref, x, y, 0.32, 0.17, mat("ccap", (0.9, 0.62, 0.15), rough=0.45))

    def p_c_rail(self, it):
        r = it["rows"][0]
        x, y1 = self.hole(r, it["hole"][1])
        _, y2 = self.rail(it["rail"], r)
        self._cap(it["ref"], x, (y1 + y2) / 2, it.get("value"))

    def p_c_bridge(self, it):
        r = it["rows"][0]
        x, y1 = self.hole(r, "d")
        _, y2 = self.hole(r, "f")
        self._cap(it["ref"], x, (y1 + y2) / 2, it.get("value"))

    def p_decoupling(self, it):
        # from a hole in the chip's VCC row to the top GND rail
        r = it["rows"][0]
        x, y1 = self.hole(r, it["hole"][1])
        _, y2 = self.rail(it["rail"], r)
        lead = mat("lead", (0.7, 0.7, 0.72), rough=0.3, metal=1)
        curve(it["ref"] + "_lead", [(x, y1, 0.0), (x, y1, 0.3), (x, y2, 0.3), (x, y2, 0.0)], 0.02, lead)
        sphere(it["ref"], x, (y1 + y2) / 2, 0.36, 0.17, mat("ccap", (0.9, 0.62, 0.15), rough=0.45))

    def p_bulk(self, it):
        # electrolytic standing across the top rails
        r = it["rows"][0]
        x, y1 = self.rail("T+", r)
        _, y2 = self.rail("T-", r)
        big = "100" in str(it.get("value"))
        rad, h = (0.32, 1.1) if big else (0.25, 0.75)
        cyl(it["ref"], x, (y1 + y2) / 2, 0.08 + h / 2, rad, h, mat("ecap", (0.12, 0.2, 0.55), rough=0.35))
        cyl(it["ref"] + "_top", x, (y1 + y2) / 2, 0.09 + h, rad * 0.9, 0.02, mat("ecap_top", (0.75, 0.75, 0.78), rough=0.3, metal=1))
        box(it["ref"] + "_stripe", x, (y1 + y2) / 2 - rad * 0.97, 0.08 + h / 2, rad * 0.6, 0.02, h * 0.9,
            mat("ecap_stripe", (0.85, 0.85, 0.9), rough=0.4))

    def p_usbc(self, it):
        # USB-C breakout: header in hole a, board lying out over the bottom rails, socket off the edge
        r1, r2 = it["rows"]
        x = self.ox + ((r1 + r2) / 2 - 32) * P
        ya = self.hole(r1, "a")[1]
        depth = 1.42
        yc = ya + 0.25 - depth / 2
        box(f"{it['ref']}_hdr", x, ya, 0.125, (r2 - r1 + 1) * P - 0.03, 0.25, 0.25, mat("hdr", (0.05, 0.05, 0.05)))
        box(f"{it['ref']}_pcb", x, yc, 0.3, 2.04, depth, 0.16, mat("ada_blue", (0.08, 0.16, 0.42), rough=0.4), bevel=0.01)
        box(f"{it['ref']}_usb", x, ya + 0.25 - depth + 0.25, 0.5, 0.9, 0.75, 0.33, mat("usb", (0.8, 0.8, 0.82), rough=0.25, metal=1), bevel=0.03)
        pin_m = mat("pin", (0.75, 0.76, 0.78), rough=0.3, metal=1.0)
        for k in range(r2 - r1 + 1):
            px = self.ox + (r1 + k - 32) * P
            cyl(f"{it['ref']}_pad", px, ya, 0.39, 0.06, 0.02, mat("gold", (0.85, 0.68, 0.3), rough=0.3, metal=1))
            box(f"{it['ref']}_pin", px, ya, 0.35, 0.05, 0.05, 0.25, pin_m)

    def p_fuse(self, it):
        # radial resettable fuse bridging the gap (yellow dipped disc)
        r = it["rows"][0]
        x, y1 = self.hole(r, "d")
        _, y2 = self.hole(r, "f")
        lead = mat("lead", (0.7, 0.7, 0.72), rough=0.3, metal=1)
        curve(it["ref"] + "_lead", [(x, y1, 0.0), (x, y1, 0.35), (x, y2, 0.35), (x, y2, 0.0)], 0.022, lead)
        box(it["ref"], x, (y1 + y2) / 2, 0.75, 0.22, 0.75, 0.75, mat("pptc", (0.88, 0.72, 0.1), rough=0.45), bevel=0.08)

    def p_other(self, it):
        pass

    # wires --------------------------------------------------------------
    def wire(self, w, i):
        if isinstance(w["a"][0], str):                 # rail-to-rail jumper: a = [rail, row], b = [rail, row]
            a = self.rail(*w["a"])
        else:
            a = self.hole(*w["a"])
        if isinstance(w["b"], list) and isinstance(w["b"][0], str):
            b = self.rail(*w["b"])
        elif isinstance(w["b"], str):
            b = self.rail(w["b"], w["a"][0])
        else:
            b = self.hole(*w["b"])
        dist = math.dist(a, b)
        lift = 0.16 + min(0.45, dist * 0.035) + (i % 4) * 0.035
        side = ((i % 2) * 2 - 1) * min(0.2, dist * 0.03)
        m = mat("wire_" + w["colour"], hexrgb(w["colour"]), rough=0.45, coat=0.2)
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        pts = [(a[0], a[1], 0.0), (a[0], a[1], lift * 0.8), (a[0] + (b[0] - a[0]) * 0.25, a[1] + (b[1] - a[1]) * 0.25 + side, lift),
               (a[0] + (b[0] - a[0]) * 0.75, a[1] + (b[1] - a[1]) * 0.75 + side, lift), (b[0], b[1], lift * 0.8), (b[0], b[1], 0.0)]
        curve(f"w_{self.name}_{i}", pts, 0.07, m)


# ------------------------------------------------------------------ world, camera, render
def setup(width, height, samples):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    if os.environ.get("BB_GPU"):
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = kind
                prefs.get_devices()
                for d in prefs.devices:
                    d.use = d.type == kind
                if any(d.use for d in prefs.devices):
                    sc.cycles.device = "GPU"
                    print("GPU render:", kind, [d.name for d in prefs.devices if d.use])
                    break
            except Exception as e:
                print("no", kind, e)
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = width, height
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    world = bpy.data.worlds.new("w")
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.82, 0.86, 0.92, 1)
    bg.inputs["Strength"].default_value = 0.35
    return sc


def desk(size=200):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, -BOARD_T - 0.001))
    o = bpy.context.active_object
    m = bpy.data.materials.new("desk")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.inputs["Scale"].default_value = 0.06
    wave.inputs["Distortion"].default_value = 6
    wave.inputs["Detail"].default_value = 6
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.42, 0.27, 0.14, 1)
    ramp.color_ramp.elements[1].color = (0.68, 0.50, 0.32, 1)
    nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.55
    o.data.materials.append(m)


def lights(cx=0, cy=0, scale=1.0):
    bpy.ops.object.light_add(type="AREA", location=(cx - 20 * scale, cy - 25 * scale, 40 * scale))
    l = bpy.context.active_object
    l.data.energy = 9000 * scale * scale
    l.data.size = 30 * scale
    l.rotation_euler = (math.radians(35), 0, math.radians(-35))
    bpy.ops.object.light_add(type="AREA", location=(cx + 30 * scale, cy + 20 * scale, 30 * scale))
    l = bpy.context.active_object
    l.data.energy = 3500 * scale * scale
    l.data.size = 40 * scale
    l.rotation_euler = (math.radians(-40), math.radians(30), 0)


def camera(loc, target, lens=50, dof=None):
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.active_object
    bpy.ops.object.empty_add(location=target)
    tgt = bpy.context.active_object
    c = cam.constraints.new("TRACK_TO")
    c.target = tgt
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"
    cam.data.lens = lens
    cam.data.clip_end = 2000
    if dof:
        cam.data.dof.use_dof = True
        cam.data.dof.focus_object = tgt
        cam.data.dof.aperture_fstop = dof
    bpy.context.scene.camera = cam


def render(out):
    bpy.context.scene.render.filepath = out
    bpy.ops.render.render(write_still=True)


def main():
    data = json.load(open(os.path.join(HERE, "scene.json")))
    what = sys.argv[1]
    args = sys.argv[2:]
    if what == "board":
        slug, out = args[0], args[1]
        W, H, S = (int(args[2]), int(args[3]), int(args[4])) if len(args) > 4 else (1950, 1100, 48)
        name = next(n for n in data["boards"] if n.lower().replace(" ", "-") == slug)
        setup(W, H, S)
        desk()
        BoardBuilder(name, data["boards"][name]).build()
        lights()
        camera((-2.5, -15.0, 15.5), (0.0, 0.25, 0.0), lens=40, dof=8)
        render(out)
    elif what == "machine":
        out = args[0]
        W, H, S = (int(args[1]), int(args[2]), int(args[3])) if len(args) > 3 else (1950, 1300, 40)
        setup(W, H, S)
        desk(600)
        rack = data["rack"]
        pos = {}
        for name, (c, s) in rack.items():
            ox = (c - 1) * 18.5
            oy = (3.5 - s) * 6.4
            pos[name] = (ox, oy)
            BoardBuilder(name, data["boards"][name], ox, oy).build()
        # board-to-board wires as long arcs
        for i, l in enumerate(data["links"]):
            (b1, h1), (b2, h2) = l["a"], l["b"]
            bb1 = BoardBuilder(b1, None, *pos[b1])
            bb2 = BoardBuilder(b2, None, *pos[b2])
            a = bb1.hole(*h1)
            b = bb2.hole(*h2)
            d = math.dist(a, b)
            lift = 1.0 + d * 0.08 + (i % 7) * 0.12
            m = mat("wire_" + l["colour"], hexrgb(l["colour"]), rough=0.45, coat=0.2)
            curve(f"link{i}", [(a[0], a[1], 0), (a[0], a[1], 0.4), ((a[0] + b[0]) / 2 + (i % 5 - 2) * 0.3,
                               (a[1] + b[1]) / 2, lift), (b[0], b[1], 0.4), (b[0], b[1], 0)], 0.075, m)
        lights(0, 0, 3.2)
        view = args[4] if len(args) > 4 else "persp"
        if view == "top":
            camera((0, -1, 150), (0, 0, 0), lens=50)
        else:
            camera((-30, -95, 72), (1.5, -2, 0), lens=61, dof=11)
        render(out)


# ------------------------------------------------------------------ extra scenes
def strip_metal():
    return mat("strip", (0.78, 0.76, 0.7), rough=0.3, metal=1.0)


def cutaway_board():
    """Left half of the board's plastic removed to show the spring-metal strips."""
    tex = board_texture()
    plast = mat("bb_plastic", (0.93, 0.92, 0.89), rough=0.55)
    # right half: full board
    half = BOARD_W / 2
    box("body_r", half / 2, 0, -BOARD_T / 2, half, BOARD_H, BOARD_T, plast, bevel=0.05)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(half / 2, 0, 0.001))
    o = bpy.context.active_object
    o.scale = (half, BOARD_H, 1)
    bpy.ops.object.transform_apply(scale=True)
    m = mat("top_tex", (1, 1, 1), rough=0.6, image=tex)
    o.data.materials.append(m)
    # UV: use only the right half of the texture
    uv = o.data.uv_layers.active.data
    for loop in uv:
        loop.uv[0] = 0.5 + loop.uv[0] * 0.5
    # left half: only the base, strips exposed
    box("body_l", -half / 2, 0, -BOARD_T * 0.8, half, BOARD_H, BOARD_T * 0.4, plast, bevel=0.03)
    bb = BoardBuilder("cut", {"items": [], "wires": []})
    met = strip_metal()
    for row in range(1, 33):
        x = (row - 32) * P
        for hf, cols in (("B", "abcde"), ("T", "fghij")):
            ys = [bb.hole(row, c)[1] for c in cols]
            box("strip", x, sum(ys) / 5, -0.35, 0.16, abs(ys[-1] - ys[0]) + 0.16, 0.35, met)
            for y in ys:
                box("clip", x, y, -0.15, 0.11, 0.06, 0.12, met)
    for rail in RAILY:
        y = bb.rail(rail, 1)[1]
        box("railstrip", -half / 2, y, -0.35, half - 0.5, 0.16, 0.35, met)


def nano(x0, y0, r0):
    """Arduino Nano-compatible board straddling rows r0..r0+14 (USB at row r0)."""
    bb = BoardBuilder("p", {"items": [], "wires": []})
    x = (r0 + 7 - 32) * P
    y = (bb.hole(r0, "c")[1] + bb.hole(r0, "g")[1]) / 2           # 0.6 in: header pins in c and g
    box("nano_pcb", x, y, 0.45, 15 * P + 0.15, 1.8, 0.16, mat("nano_blue", (0.1, 0.3, 0.6), rough=0.4))
    box("nano_mcu", x + 0.6, y, 0.6, 0.7, 0.7, 0.12, mat("chip_black", (0.06, 0.06, 0.065), rough=0.42))
    box("nano_usb", (r0 - 32) * P - 0.15, y, 0.7, 0.9, 0.75, 0.4, mat("usb", (0.8, 0.8, 0.82), rough=0.25, metal=1))
    pin_m = mat("pin", (0.75, 0.76, 0.78), rough=0.3, metal=1.0)
    for k in range(15):
        px = (r0 + k - 32) * P
        for c in ("c", "g"):
            box("hdr", px, bb.hole(r0, c)[1], 0.25, 0.22, 0.22, 0.25, mat("hdr", (0.05, 0.05, 0.05)))
            box("hdrpin", px, bb.hole(r0, c)[1], 0.3, 0.06, 0.06, 0.6, pin_m)


def programmer_scene():
    data = {"items": [], "wires": []}
    it = lambda ref, label, r, n, wide: dict(ref=ref, kind="chip", rows=[r, r + n // 2 - 1], wide=wide, label=label, pins=n)
    data["items"] += [it("U1", "74HC595", 19, 16, False), it("U2", "74HC595", 29, 16, False), it("U3", "AT28C256", 40, 28, True)]
    W = lambda net, a, b, col: data["wires"].append(dict(net=net, a=a, b=b, colour=col))
    Y, B, G, P_, K, R = "#D9A21B", "#3D7FD0", "#4E9F3D", "#7E848D", "#222222", "#D7372B"
    # Nano: bottom side (c) pin k at row 16-(k-1); top side (h) pin 16.. at row 2..
    nb = lambda k: [16 - (k - 1), "b"]          # use hole b on the bottom node
    nt = lambda k: [2 + (k - 16), "i"]          # use hole i on the top node
    # shift-register control
    # colours as in Figure 7.22: yellow serial data, pink clocks, grey address, blue OE/WE, green data
    PK = "#D64570"
    W("SER", nb(5), [21, "h"], Y)               # D2 -> U1 pin 14
    W("SRCLK", nb(6), [24, "h"], PK)            # D3 -> U1 pin 11
    W("SRCLK", [24, "i"], [34, "h"], PK)
    W("RCLK", nb(7), [23, "h"], PK)             # D4 -> U1 pin 12
    W("RCLK", [23, "i"], [33, "h"], PK)
    W("QH'", [26, "h"], [31, "h"], Y)           # U1 QH' -> U2 SER
    # address bits A0..A7 from U1 (QA pin15 top row 20; QB..QH pins1..7 bottom rows 19..25)
    W("A0", [20, "i"], [49, "b"], P_)
    for k in range(1, 8):
        W(f"A{k}", [19 + (k - 1), "c"], [49 - k, "a"], P_)
    # U2: QA (row 30 top), QB..QH rows 29..35 bottom
    W("A8", [30, "i"], [43, "i"], P_)
    for row, dest in ((29, [44, "i"]), (30, [47, "i"]), (31, [45, "j"]), (32, [41, "a"]), (33, [42, "i"]), (34, [40, "a"])):
        W("A", [row, "c"], dest, P_)
    W("OE", [35, "c"], [46, "i"], B)
    # data D5..D12 -> I/O0..7 (EEPROM pins 11,12,13 bottom rows 50-52; 15..19 top rows 53..49)
    for k, (dpin, dest) in enumerate(((8, [50, "b"]), (9, [51, "b"]), (10, [52, "b"]), (11, [53, "i"]),
                                       (12, [52, "i"]), (13, [51, "i"]), (14, [50, "i"]), (15, [49, "i"]))):
        W(f"D{k}", nb(dpin), dest, G)
    W("WE", nt(19), [41, "i"], B)               # A0 (D14) -> WE pin 27 (never D13: the bootloader flashes its LED)
    # power (Table 7.2): Nano 5V -> + rail, GND -> - rail; the top - rail is joined to the bottom - rail
    W("GND", nb(4), "B-", K)
    W("VCC", nt(27), "T+", R)
    W("GND", ["T-", 60], ["B-", 60], K)          # join the two GND rails
    W("VCC", ["T+", 61], ["B+", 61], R)          # and the two +5 V rails
    for r_ in (26, 36, 53):                     # 595 pin 8, 595 pin 8, EEPROM pin 14
        W("GND", [r_, "a"], "B-", K)
    for r_ in (19, 29, 40):                     # 595 pin 16, 595 pin 16, EEPROM pin 28
        W("VCC", [r_, "j"], "T+", R)
    W("CE", [48, "h"], "T-", K)                 # EEPROM CE (pin 20) -> GND: always selected
    for r_ in (25, 35):                         # 595 SRCLR (pin 10) -> +5 V: never clear
        W("SRCLR", [r_, "h"], "T+", R)
    for r_ in (22, 32):                         # 595 OE (pin 13) -> GND: outputs always on
        W("OE595", [r_, "h"], "T-", K)
    # the 10 kOhm pull-up from WE (pin 27, row 41) to +5 V, and one 100 nF per chip, VCC row to GND
    data["items"].append(dict(ref="R1", kind="r-rail", rows=[41, 41], hole=[41, "j"], rail="T+", value="10k"))
    for ref, r_ in (("C1", 19), ("C2", 29), ("C3", 40)):
        data["items"].append(dict(ref=ref, kind="decoupling", rows=[r_, r_], hole=[r_, "i"], rail="T-", value="100nF"))
    bbld = BoardBuilder("prog", data)
    bbld.build()
    nano(0, 0, 2)


def probe_scene():
    data = {"items": [dict(ref="Rp", kind="r-bridge", rows=[20, 20], value="1k"),
                      dict(ref="Dp", kind="led-rail", rows=[20, 20], hole=[20, "a"], rail="B-", lit=True, colour="red")],
            "wires": [dict(net="GND", a=[30, "a"], b="B-", colour="#222222")]}
    bbld = BoardBuilder("probe", data)
    bbld.build()
    x, y = bbld.hole(20, "j")
    m = mat("probe_red", (0.8, 0.12, 0.1), rough=0.4, coat=0.3)
    curve("lead", [(x, y, 0), (x, y, 0.5), (x + 2, y + 3, 1.5), (x + 6, y + 6, 1.0), (x + 9, y + 5, 0.8)], 0.08, m)
    cyl("probe_body", x + 10.2, y + 5, 0.8, 0.35, 2.6, m, rot=(0, math.pi / 2, 0))
    cyl("probe_tip", x + 11.9, y + 5, 0.8, 0.06, 1.0, mat("tip", (0.8, 0.8, 0.8), rough=0.2, metal=1), rot=(0, math.pi / 2, 0))


def analyser_scene(data):
    """Three PC-2 boards (Clock behind, Control sequencer, A register in front) with an 8-channel USB logic
    analyser clipped on at the holes of Figure 10.12 (Ch 10)."""
    clk = BoardBuilder("Clock", data["boards"]["Clock"], 0.0, 5.8)
    seq = BoardBuilder("Control sequencer", data["boards"]["Control sequencer"], 0.0, 0.0)
    areg = BoardBuilder("A register", data["boards"]["A register"], 0.0, -5.8)
    clk.build()
    seq.build()
    areg.build()
    # analyser box on the desk in front of the boards
    bx, by = 4.2, -12.5
    body = mat("la_body", (0.035, 0.035, 0.04), rough=0.5)
    box("la_box", bx, by, 0.4 - BOARD_T, 3.8, 2.5, 0.8, body, bevel=0.12)
    box("la_plate", bx + 0.3, by - 0.1, 0.805 - BOARD_T, 2.4, 1.5, 0.01, mat("la_plate", (0.2, 0.21, 0.23), rough=0.35))
    box("la_led", bx - 1.45, by - 0.85, 0.81 - BOARD_T, 0.18, 0.18, 0.02, mat("la_led", (0.1, 0.9, 0.2), emit=(0.1, 1, 0.2), strength=6))
    hdr = mat("hdr", (0.05, 0.05, 0.05), rough=0.5)
    box("la_hdr", bx, by + 1.4, 0.35 - BOARD_T, 3.0, 0.4, 0.5, hdr)
    # USB cable to the laptop out of frame
    usb = mat("usb_cable", (0.08, 0.08, 0.09), rough=0.6)
    box("la_usbplug", bx + 2.3, by, 0.45 - BOARD_T, 1.0, 0.7, 0.45, usb)
    curve("la_usb", [(bx + 2.8, by, 0.45 - BOARD_T), (bx + 6, by - 0.5, 0.2 - BOARD_T), (bx + 9, by - 3, -BOARD_T + 0.18),
                     (bx + 14, by - 9, -BOARD_T + 0.18)], 0.17, usb)
    # channel leads: colour, board, hole
    # the free holes of Figure 10.12: CLK 18c, CLK_n 19b, HLT_n 28g (Clock); STEP0-2 3g, 4g, 5g
    # (Control sequencer); BUS0 21g, BUS3 24g (A register)
    chans = [("#222222", clk, None),                      # ground lead to the Clock board's GND rail
             ("#8B5A2B", clk, (18, "c")), ("#D7372B", clk, (19, "b")), ("#E8743B", clk, (28, "g")),
             ("#F4C430", seq, (3, "g")), ("#4E9F3D", seq, (4, "g")), ("#3D7FD0", seq, (5, "g")),
             ("#7B5EA7", areg, (21, "g")), ("#9A9A9A", areg, (24, "g"))]
    grab_body = mat("grab_body", (0.85, 0.85, 0.82), rough=0.4)
    pin_m = mat("pin", (0.75, 0.76, 0.78), rough=0.3, metal=1.0)
    for i, (col, bb, h) in enumerate(chans):
        m = mat("lead_" + col, hexrgb(col), rough=0.45, coat=0.2)
        if h is None:
            x, y = bb.rail("B-", 12)
            y_top = 0.15
        else:
            x, y = bb.hole(*h)
            # short jumper standing in the hole, same colour family as the lead
            cyl(f"jmp{i}", x, y, 0.45, 0.07, 0.9, m)
            cyl(f"jmppin{i}", x, y, 1.0, 0.03, 0.25, pin_m)
            y_top = 1.05
        # grabber clip on top of the jumper
        cyl(f"grab{i}", x, y - 0.25, y_top + 0.55, 0.16, 1.1, grab_body, rot=(math.radians(-25), 0, 0))
        cyl(f"grabcap{i}", x, y - 0.5, y_top + 1.05, 0.17, 0.25, m, rot=(math.radians(-25), 0, 0))
        hx = bx - 1.4 + i * 0.35
        hy = by + 1.6
        curve(f"lead{i}", [(x, y - 0.55, y_top + 1.2), (x, y - 1.6, y_top + 1.8), ((x + hx) / 2 + (i % 3 - 1) * 0.6, (y + hy) / 2 - 0.8, 1.6),
                           (hx, hy + 0.8, 0.9), (hx, hy, 0.5 - BOARD_T + 0.5)], 0.05, m)


def extra(what, args):
    out = args[0]
    W, H, S = (int(args[1]), int(args[2]), int(args[3])) if len(args) > 3 else (1950, 1100, 48)
    setup(W, H, S)
    desk()
    data = json.load(open(os.path.join(HERE, "scene.json")))
    if what == "empty":
        BoardBuilder("e", {"items": [], "wires": []}).build()
        lights()
        camera((-2.5, -15.0, 15.5), (0.0, 0.25, 0.0), lens=40, dof=8)
    elif what == "cutaway":
        cutaway_board()
        lights()
        camera((-9.0, -10.5, 8.5), (-3.0, 0.3, -0.3), lens=45, dof=5.6)
    elif what == "closeup":
        BoardBuilder("A register", data["boards"]["A register"]).build()
        lights()
        camera((-7.2, -4.5, 3.6), (-6.4, 0.2, 0.2), lens=60, dof=2.8)
    elif what == "display":
        BoardBuilder("Display", data["boards"]["Display"]).build()
        lights()
        bpy.context.scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.15
        camera((-4.5, -7.5, 9.5), (-4.2, 0.2, 0.3), lens=55, dof=4)
    elif what == "probe":
        probe_scene()
        lights()
        camera((-1.0, -10.0, 10.0), (2.5, 2.0, 0.2), lens=40, dof=6)
    elif what == "analyser":
        analyser_scene(data)
        lights(0, -2, 1.8)
        camera((-3.0, -30.0, 25.0), (1.2, -3.2, 0.0), lens=40, dof=11)
    elif what == "programmer":
        programmer_scene()
        lights()
        camera((-2.5, -15.0, 15.5), (0.0, 0.25, 0.0), lens=40, dof=8)
    render(out)


if __name__ == "__main__":
    if sys.argv[1] in ("empty", "cutaway", "closeup", "display", "probe", "programmer", "analyser"):
        extra(sys.argv[1], sys.argv[2:])
    else:
        main()
