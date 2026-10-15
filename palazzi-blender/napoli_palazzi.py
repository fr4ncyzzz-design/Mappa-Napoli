"""Genera una zona di Napoli in Blender (5.x) con palazzi procedurali in stile napoletano.

Uso da riga di comando:
    blender -b --python napoli_palazzi.py -- zona_plebiscito.json napoli_plebiscito.blend [cartella_anteprime]
Modalità tile (JSON creato da strumenti/tile_export.py, riconosciuta dalla chiave "tile"):
    blender -b --factory-startup --python napoli_palazzi.py -- tile/napoli_r08_c10.json tile/napoli_r08_c10.blend
    Crea solo la collezione della tile (edifici, terreno, strade): niente cielo, sole, mare e camere,
    che stanno una volta sola in napoli_tutta.blend.
Uso da Blender: apri lo script nel Text Editor, metti zona_plebiscito.json accanto al .blend e premi Run Script.
"""
import json
import math
import random
import sys
import time
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
JSON_PATH = Path(argv[0]) if argv else Path(bpy.path.abspath("//zona_plebiscito.json"))
BLEND_OUT = Path(argv[1]) if len(argv) > 1 else None
PREVIEW_DIR = Path(argv[2]) if len(argv) > 2 else None

GROUND_H = 4.8
FLOOR_H = 3.8
BAY = 3.5
BAY_COURT = 2.9
REVEAL = 0.28
FRAME = 0.16
T0 = time.time()


def log(msg):
    print(f"[{time.time() - T0:6.1f}s] {msg}", flush=True)


def srgb(hex_color):
    h = hex_color.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


# ---------------------------------------------------------------- materiali

def new_material(name, color, rough=0.85, metal=0.0):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except AttributeError:
        pass
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    lin = srgb(color)
    bsdf.inputs["Base Color"].default_value = (*lin, 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    m.diffuse_color = (*lin, 1)
    return m, nt, bsdf


def add_variation(nt, bsdf, color, scale=0.35, low=0.8, bump_scale=0.0, bump_strength=0.15):
    coord = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = 8
    nt.links.new(coord.outputs["Object"], noise.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (low, low, low, 1)
    ramp.color_ramp.elements[1].color = (1.05, 1.05, 1.05, 1)
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    mul = nt.nodes.new("ShaderNodeVectorMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = srgb(color)
    nt.links.new(ramp.outputs["Color"], mul.inputs[0])
    nt.links.new(mul.outputs["Vector"], bsdf.inputs["Base Color"])
    if bump_scale:
        fine = nt.nodes.new("ShaderNodeTexNoise")
        fine.inputs["Scale"].default_value = bump_scale
        fine.inputs["Detail"].default_value = 10
        nt.links.new(coord.outputs["Object"], fine.inputs["Vector"])
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = bump_strength
        nt.links.new(fine.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def mat_plaster(name, color):
    m, nt, bsdf = new_material(name, color, 0.9)
    add_variation(nt, bsdf, color, scale=0.25, low=0.78, bump_scale=9, bump_strength=0.08)
    return m


def mat_stone(name, color, brick=False):
    m, nt, bsdf = new_material(name, color, 0.8)
    if brick:
        uv = nt.nodes.new("ShaderNodeTexCoord")
        br = nt.nodes.new("ShaderNodeTexBrick")
        br.inputs["Scale"].default_value = 1.0
        br.inputs["Mortar Size"].default_value = 0.025
        br.inputs["Brick Width"].default_value = 1.2
        br.inputs["Row Height"].default_value = 0.55
        br.inputs["Color1"].default_value = (*srgb(color), 1)
        br.inputs["Color2"].default_value = (*[c * 0.85 for c in srgb(color)], 1)
        br.inputs["Mortar"].default_value = (*[c * 0.55 for c in srgb(color)], 1)
        nt.links.new(uv.outputs["UV"], br.inputs["Vector"])
        nt.links.new(br.outputs["Color"], bsdf.inputs["Base Color"])
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.6
        bump.invert = True
        nt.links.new(br.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    else:
        add_variation(nt, bsdf, color, scale=0.8, low=0.75, bump_scale=14, bump_strength=0.2)
    return m


def mat_paving(name, color, size):
    m, nt, bsdf = new_material(name, color, 0.75)
    uv = nt.nodes.new("ShaderNodeTexCoord")
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.inputs["Scale"].default_value = 1.0 / size
    br.inputs["Mortar Size"].default_value = 0.02
    br.inputs["Color1"].default_value = (*srgb(color), 1)
    br.inputs["Color2"].default_value = (*[c * 0.8 for c in srgb(color)], 1)
    br.inputs["Mortar"].default_value = (*[c * 0.6 for c in srgb(color)], 1)
    nt.links.new(uv.outputs["UV"], br.inputs["Vector"])
    nt.links.new(br.outputs["Color"], bsdf.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.4
    bump.invert = True
    nt.links.new(br.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def mat_slats(name, color, spacing=0.06, rough=0.6, metal=0.0):
    m, nt, bsdf = new_material(name, color, rough, metal)
    uv = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(uv.outputs["UV"], sep.inputs["Vector"])
    div = nt.nodes.new("ShaderNodeMath")
    div.operation = "DIVIDE"
    div.inputs[1].default_value = spacing
    nt.links.new(sep.outputs["Y"], div.inputs[0])
    fr = nt.nodes.new("ShaderNodeMath")
    fr.operation = "FRACT"
    nt.links.new(div.outputs[0], fr.inputs[0])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.5
    nt.links.new(fr.outputs[0], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def mat_railing(name, color):
    m, nt, bsdf = new_material(name, color, 0.5, 0.6)
    uv = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(uv.outputs["UV"], sep.inputs["Vector"])

    def math_node(op, a, b=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        if isinstance(a, float):
            n.inputs[0].default_value = a
        else:
            nt.links.new(a, n.inputs[0])
        if b is not None:
            if isinstance(b, float):
                n.inputs[1].default_value = b
            else:
                nt.links.new(b, n.inputs[1])
        return n.outputs[0]

    bars = math_node("LESS_THAN", math_node("FRACT", math_node("DIVIDE", sep.outputs["X"], 0.12)), 0.22)
    bottom = math_node("LESS_THAN", sep.outputs["Y"], 0.06)
    top = math_node("GREATER_THAN", sep.outputs["Y"], 0.93)
    mid = math_node("LESS_THAN", math_node("ABSOLUTE", math_node("SUBTRACT", sep.outputs["Y"], 0.82)), 0.02)
    alpha = math_node("MAXIMUM", math_node("MAXIMUM", bars, bottom), math_node("MAXIMUM", top, mid))
    nt.links.new(alpha, bsdf.inputs["Alpha"])
    if hasattr(m, "surface_render_method"):
        m.surface_render_method = "DITHERED"
    m.use_backface_culling = False
    return m


def mat_glass(name, color, rough=0.05):
    m, nt, bsdf = new_material(name, color, rough)
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.8
    return m


def mat_water(name):
    m, nt, bsdf = new_material(name, "#2f6283", 0.08)
    coord = nt.nodes.new("ShaderNodeTexCoord")
    wave = nt.nodes.new("ShaderNodeTexNoise")
    wave.inputs["Scale"].default_value = 0.6
    wave.inputs["Detail"].default_value = 6
    nt.links.new(coord.outputs["Object"], wave.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    nt.links.new(wave.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


FACADE_COLORS = ["#a8432f", "#c98d3b", "#d6ad5c", "#d48b7a", "#d99a6c", "#e2d2ab", "#cfc6b6",
                 "#b9623f", "#e2c58a", "#c97e5e", "#e6d9bf", "#9c5a3c"]

M = {}


def build_materials():
    for i, c in enumerate(FACADE_COLORS):
        M[f"facciata{i}"] = mat_plaster(f"Facciata_{i:02d}", c)
    M["stucco"] = mat_plaster("Stucco_Bianco", "#ebe5d8")
    M["piperno"] = mat_stone("Piperno_Bugnato", "#6f6c66", brick=True)
    M["pietra_grigia"] = mat_stone("Piperno", "#77736c")
    M["travertino"] = mat_stone("Travertino", "#ddd3bd")
    M["tufo"] = mat_stone("Tufo_Castello", "#8a7c66", brick=True)
    M["vetro"] = mat_glass("Vetro_Finestra", "#1d252b")
    M["vetrina"] = mat_glass("Vetrina", "#2b343a", 0.08)
    M["persiana_verde"] = mat_slats("Persiana_Verde", "#3d5b40")
    M["persiana_marrone"] = mat_slats("Persiana_Marrone", "#6a4a32")
    M["saracinesca"] = mat_slats("Saracinesca", "#8d9093", spacing=0.1, rough=0.45, metal=0.7)
    M["portone"] = mat_slats("Portone_Legno", "#4a3324", spacing=0.4, rough=0.7)
    M["ringhiera"] = mat_railing("Ringhiera_Ferro", "#1d1d1f")
    M["lastrico"] = mat_stone("Lastrico_Solare", "#b9b2a6")
    M["basoli"] = mat_paving("Basoli_Lavici", "#4b4a48", 0.55)
    M["asfalto"] = mat_stone("Asfalto", "#3c3d3f")
    M["pietra"] = mat_paving("Marciapiede", "#88837a", 0.45)
    M["piazza"] = mat_paving("Piazza_Pietra", "#8e877b", 0.9)
    M["verde"] = mat_stone("Prato", "#5d7b3e")
    M["mare"] = mat_water("Mare")
    M["cupola"] = mat_stone("Cupola_Piombo", "#7f8a8c")


# ---------------------------------------------------------------- geometria

class MeshBuilder:
    def __init__(self):
        self.verts, self.faces, self.uvs, self.mats = [], [], [], []
        self.index = {}
        self.mat_slots = {}

    def slot(self, key):
        if key not in self.mat_slots:
            self.mat_slots[key] = len(self.mat_slots)
        return self.mat_slots[key]

    def vid(self, p):
        k = (round(p[0], 3), round(p[1], 3), round(p[2], 3))
        i = self.index.get(k)
        if i is None:
            i = self.index[k] = len(self.verts)
            self.verts.append(k)
        return i

    def face(self, pts, uvs, mat):
        idx, kept = [], []
        for p, uv in zip(pts, uvs):
            i = self.vid(p)
            if i not in idx:
                idx.append(i)
                kept.append(uv)
        if len(idx) < 3:
            return
        self.faces.append(idx)
        self.uvs.extend(kept)
        self.mats.append(self.slot(mat))

    def build(self, name, collection, origin=(0, 0, 0)):
        if not self.faces:
            return None
        ox, oy, oz = origin
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([(x - ox, y - oy, z - oz) for x, y, z in self.verts], [], self.faces)
        for key in self.mat_slots:
            mesh.materials.append(M[key])
        mesh.polygons.foreach_set("material_index", self.mats)
        uv = mesh.uv_layers.new(name="UVMap")
        uv.data.foreach_set("uv", [c for p in self.uvs for c in p])
        mesh.validate()
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        obj.location = origin
        collection.objects.link(obj)
        return obj


class Edge:
    def __init__(self, a, b):
        self.a = Vector((a[0], a[1]))
        d = Vector((b[0] - a[0], b[1] - a[1]))
        self.L = d.length
        self.t = d / self.L if self.L > 1e-6 else Vector((1, 0))
        self.n = Vector((self.t.y, -self.t.x))

    def P(self, u, z, d=0.0):
        q = self.a + self.t * u + self.n * d
        return (q.x, q.y, z)


def wall(mb, e, u0, u1, z0, z1, d, mat, local=None):
    if u1 - u0 < 1e-3 or z1 - z0 < 1e-3:
        return
    ou, oz = local if local else (0.0, 0.0)
    mb.face([e.P(u0, z0, d), e.P(u1, z0, d), e.P(u1, z1, d), e.P(u0, z1, d)],
            [(u0 - ou, z0 - oz), (u1 - ou, z0 - oz), (u1 - ou, z1 - oz), (u0 - ou, z1 - oz)], mat)


def wall_back(mb, e, u0, u1, z0, z1, d, mat):
    if u1 - u0 < 1e-3 or z1 - z0 < 1e-3:
        return
    mb.face([e.P(u0, z0, d), e.P(u0, z1, d), e.P(u1, z1, d), e.P(u1, z0, d)],
            [(u0, z0), (u0, z1), (u1, z1), (u1, z0)], mat)


def box(mb, e, u0, u1, z0, z1, d0, d1, mat, bottom=True, ends=True, top=True):
    wall(mb, e, u0, u1, z0, z1, d1, mat)
    if top:
        mb.face([e.P(u0, z1, d1), e.P(u1, z1, d1), e.P(u1, z1, d0), e.P(u0, z1, d0)],
                [(u0, d1), (u1, d1), (u1, d0), (u0, d0)], mat)
    if bottom:
        mb.face([e.P(u0, z0, d1), e.P(u0, z0, d0), e.P(u1, z0, d0), e.P(u1, z0, d1)],
                [(u0, d1), (u0, d0), (u1, d0), (u1, d1)], mat)
    if ends:
        mb.face([e.P(u0, z0, d0), e.P(u0, z0, d1), e.P(u0, z1, d1), e.P(u0, z1, d0)],
                [(d0, z0), (d1, z0), (d1, z1), (d0, z1)], mat)
        mb.face([e.P(u1, z0, d1), e.P(u1, z0, d0), e.P(u1, z1, d0), e.P(u1, z1, d1)],
                [(d1, z0), (d0, z0), (d0, z1), (d1, z1)], mat)


def opening(mb, e, u0, u1, z0, z1, depth, wall_mat, back_mat):
    mb.face([e.P(u0, z0, 0), e.P(u1, z0, 0), e.P(u1, z0, -depth), e.P(u0, z0, -depth)],
            [(u0, 0), (u1, 0), (u1, depth), (u0, depth)], wall_mat)
    mb.face([e.P(u0, z1, 0), e.P(u0, z1, -depth), e.P(u1, z1, -depth), e.P(u1, z1, 0)],
            [(u0, 0), (u0, depth), (u1, depth), (u1, 0)], wall_mat)
    mb.face([e.P(u0, z0, 0), e.P(u0, z0, -depth), e.P(u0, z1, -depth), e.P(u0, z1, 0)],
            [(0, z0), (depth, z0), (depth, z1), (0, z1)], wall_mat)
    mb.face([e.P(u1, z0, 0), e.P(u1, z1, 0), e.P(u1, z1, -depth), e.P(u1, z0, -depth)],
            [(0, z0), (0, z1), (depth, z1), (depth, z0)], wall_mat)
    wall(mb, e, u0, u1, z0, z1, -depth, back_mat)


class Terrain:
    def __init__(self, t):
        self.x0, self.y0, self.step = t["x0"], t["y0"], t["step"]
        self.nx, self.ny, self.h = t["nx"], t["ny"], t["h"]

    def __call__(self, x, y):
        gx = min(max((x - self.x0) / self.step, 0), self.nx - 1.001)
        gy = min(max((y - self.y0) / self.step, 0), self.ny - 1.001)
        ix, iy = int(gx), int(gy)
        fx, fy = gx - ix, gy - iy
        i = iy * self.nx + ix
        h = self.h
        return (h[i] * (1 - fx) * (1 - fy) + h[i + 1] * fx * (1 - fy)
                + h[i + self.nx] * (1 - fx) * fy + h[i + self.nx + 1] * fx * fy)


# ---------------------------------------------------------------- palazzi

def facade_edge(mb, e, flag, b, floors, top, rnd, style):
    zb = b["zb"]
    gh = floors[0][1] - floors[0][0]
    wall_mat = style["wall"]
    base_mat = style["base"]
    street = flag == 1

    wall(mb, e, 0, e.L, zb - 3.0, zb, 0, base_mat)
    if flag == 0 or e.L < 2.0 or style["plain"]:
        wall(mb, e, 0, e.L, zb, floors[0][1], 0, base_mat if flag else wall_mat)
        wall(mb, e, 0, e.L, floors[0][1], top, 0, wall_mat)
        if style["plain"] and flag and e.L >= 4 and style["kind"] == "chiesa":
            church_windows(mb, e, zb, top, style)
            pilasters(mb, e, zb, top, style)
        if flag and e.L >= 2.0:
            box(mb, e, -0.45, e.L + 0.45, top - 0.6, top, 0, 0.45, style["cornice"])
        return

    nb = max(1, int((e.L - 1.0) / (BAY if street else BAY_COURT)))
    margin = 0.5
    bay = (e.L - 2 * margin) / nb
    edge_ground = b["terrain"](*e.P(e.L / 2, 0)[:2])

    for fi, (zf, zt) in enumerate(floors):
        fh = zt - zf
        holes = []
        if fi == 0:
            if street and edge_ground < zt - 3.2:
                z0 = max(zb, edge_ground)
                ow = min(2.6, bay * 0.66)
                oh = min(3.6, zt - z0 - 0.9)
                if oh > 1.8:
                    for i in range(nb):
                        uc = margin + bay * (i + 0.5)
                        r = rnd.random()
                        back = "portone" if r < 0.14 else ("vetrina" if r < 0.55 else "saracinesca")
                        holes.append((uc - ow / 2, uc + ow / 2, z0, z0 + oh, 0.35, back, None))
            else:
                ww = min(1.0, bay * 0.4)
                for i in range(nb):
                    uc = margin + bay * (i + 0.5)
                    holes.append((uc - ww / 2, uc + ww / 2, zf + max(1.6, fh - 2.4), zt - 0.7, REVEAL, "vetro", "court"))
            mat_floor = base_mat
        else:
            ww = min(1.25, bay * 0.42)
            win_top = zf + min(fh * 0.74, 2.9)
            noble = street and (fi in (1, 2) or rnd.random() < 0.22)
            for i in range(nb):
                uc = margin + bay * (i + 0.5)
                balcony = noble and fh > 2.8
                z0 = zf + 0.05 if balcony else zf + 0.95
                kind = "balcone" if balcony else ("finestra" if street else "court")
                holes.append((uc - ww / 2, uc + ww / 2, z0, win_top, REVEAL, "vetro", kind))
            mat_floor = wall_mat

        prev = 0.0
        for u0, u1, z0, z1, depth, back, kind in holes:
            wall(mb, e, prev, u0, zf, zt, 0, mat_floor)
            wall(mb, e, u0, u1, zf, z0, 0, mat_floor)
            wall(mb, e, u0, u1, z1, zt, 0, mat_floor)
            prev = u1
            closed = kind in ("finestra", "balcone") and rnd.random() < 0.28
            if closed:
                opening(mb, e, u0, u1, z0, z1, 0.08, style["frame"], style["shutter"])
            else:
                opening(mb, e, u0, u1, z0, z1, depth, style["frame"] if fi else mat_floor, back)
            if kind in ("finestra", "balcone"):
                f = FRAME
                wall(mb, e, u0 - f, u1 + f, z1, z1 + f, 0.03, style["frame"])
                wall(mb, e, u0 - f, u0, z0, z1, 0.03, style["frame"])
                wall(mb, e, u1, u1 + f, z0, z1, 0.03, style["frame"])
                if kind == "finestra":
                    box(mb, e, u0 - f - 0.05, u1 + f + 0.05, z0 - 0.12, z0, 0, 0.1, style["frame"])
                if fi == 1:
                    box(mb, e, u0 - f - 0.12, u1 + f + 0.12, z1 + f, z1 + f + 0.16, 0, 0.14, style["frame"], ends=True)
                sw = (u1 - u0) / 2
                if not closed and bay - (u1 - u0) >= 2 * (f + sw) + 0.05:
                    wall(mb, e, u0 - f - sw, u0 - f, z0, z1, 0.05, style["shutter"])
                    wall(mb, e, u1 + f, u1 + f + sw, z0, z1, 0.05, style["shutter"])
                if kind == "balcone":
                    bu0, bu1 = u0 - f - 0.35, u1 + f + 0.35
                    zs = zf + 0.05
                    box(mb, e, bu0, bu1, zs - 0.15, zs, 0, 0.78, style["slab"])
                    wall(mb, e, bu0, bu1, zs, zs + 1.0, 0.74, "ringhiera", local=(bu0, zs))
                    mb.face([e.P(bu0, zs, 0), e.P(bu0, zs, 0.74), e.P(bu0, zs + 1.0, 0.74), e.P(bu0, zs + 1.0, 0)],
                            [(0, 0), (0.74, 0), (0.74, 1.0), (0, 1.0)], "ringhiera")
                    mb.face([e.P(bu1, zs, 0.74), e.P(bu1, zs, 0), e.P(bu1, zs + 1.0, 0), e.P(bu1, zs + 1.0, 0.74)],
                            [(0, 0), (0.74, 0), (0.74, 1.0), (0, 1.0)], "ringhiera")
        wall(mb, e, prev, e.L, zf, zt, 0, mat_floor)

        if street and fi < len(floors) - 1:
            if fi == 0:
                box(mb, e, -0.15, e.L + 0.15, zt - 0.15, zt + 0.2, 0, 0.15, style["base"])
            else:
                box(mb, e, -0.1, e.L + 0.1, zt - 0.08, zt + 0.1, 0, 0.09, style["frame"])

    if street:
        box(mb, e, -0.5, e.L + 0.5, top - 0.65, top, 0, 0.5, style["cornice"])
        box(mb, e, -0.55, e.L + 0.55, top - 0.25, top - 0.05, 0.5, 0.58, style["cornice"], bottom=True)


def church_windows(mb, e, zb, top, style):
    nb = max(1, int(e.L / 7.0))
    bay = e.L / nb
    h = top - zb
    for i in range(nb):
        uc = bay * (i + 0.5)
        w = min(1.8, bay * 0.3)
        z0, z1 = zb + h * 0.45, zb + h * 0.78
        wall(mb, e, uc - w / 2 - 0.25, uc + w / 2 + 0.25, z0 - 0.25, z1 + 0.35, 0.06, style["frame"])
        wall(mb, e, uc - w / 2, uc + w / 2, z0, z1, 0.07, "vetro")


def pilasters(mb, e, zb, top, style):
    n = max(1, int(e.L / 3.6))
    step = e.L / n
    for i in range(n + 1):
        u = min(max(step * i, 0.35), e.L - 0.35)
        box(mb, e, u - 0.35, u + 0.35, zb, top - 0.6, 0, 0.32, style["frame"], bottom=False)
        box(mb, e, u - 0.48, u + 0.48, zb, zb + 0.9, 0, 0.42, style["frame"], bottom=False)
        box(mb, e, u - 0.45, u + 0.45, top - 1.0, top - 0.6, 0, 0.4, style["frame"])
    box(mb, e, -0.1, e.L + 0.1, zb, zb + 0.5, 0, 0.5, style["frame"], bottom=False)


def parapet(mb, e, top, mat, crenel=False):
    if crenel:
        u = 0.0
        while u < e.L:
            u1 = min(u + 1.2, e.L)
            box(mb, e, u, u1, top, top + 1.6, -0.6, 0, mat, bottom=False)
            u += 2.2
        return
    box(mb, e, 0, e.L, top, top + 1.0, -0.28, 0, mat, bottom=False, ends=False)
    wall_back(mb, e, 0, e.L, top, top + 1.0, -0.28, mat)


def roof(mb, rings, z, mat):
    loops = [[Vector((x, y, z)) for x, y in r] for r in rings]
    flat = [p for r in loops for p in r]
    for tri in tessellate_polygon(loops):
        a, b, c = (flat[i] for i in tri)
        if (b - a).cross(c - a).z < 0:
            a, c = c, a
        mb.face([a, b, c], [(a.x, a.y), (b.x, b.y), (c.x, c.y)], mat)


def world_box(mb, cx, cy, sx, sy, z0, z1, mat):
    x0, x1, y0, y1 = cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2
    for (ax, ay), (bx, by) in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        e = Edge((ax, ay), (bx, by))
        wall(mb, e, 0, e.L, z0, z1, 0, mat)
    mb.face([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], mat)


def dome(mb, cx, cy, r, z0, drum, mat, drum_mat):
    seg, rows = 32, 10
    for i in range(seg):
        a0, a1 = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
        p0 = (cx + r * math.cos(a0), cy + r * math.sin(a0))
        p1 = (cx + r * math.cos(a1), cy + r * math.sin(a1))
        e = Edge(p0, p1)
        wall(mb, e, 0, e.L, z0, z0 + drum, 0, drum_mat)
    zb = z0 + drum
    for j in range(rows):
        t0, t1 = (math.pi / 2) * j / rows, (math.pi / 2) * (j + 1) / rows
        for i in range(seg):
            a0, a1 = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
            pts = []
            for t, a in ((t0, a0), (t0, a1), (t1, a1), (t1, a0)):
                pts.append((cx + r * math.cos(t) * math.cos(a), cy + r * math.cos(t) * math.sin(a), zb + r * 1.15 * math.sin(t)))
            mb.face(pts, [(a0 * r, t0 * r), (a1 * r, t0 * r), (a1 * r, t1 * r), (a0 * r, t1 * r)], mat)
    world_box(mb, cx, cy, r * 0.35, r * 0.35, zb + r * 1.1, zb + r * 1.1 + r * 0.45, drum_mat)


def plan_floors(b, rnd):
    """Piani del palazzo (quota inizio/fine). Usata anche dal LOD: stesso rnd, stesse altezze."""
    kind, zb, levels = b["kind"], b["gmin"], b["levels"]
    if kind == "chiesa":
        total = b["height"] or 20.0
        floors = [(zb, zb + total)]
    elif kind == "tettoia":
        floors = [(zb, zb + 4.0)]
    else:
        if b["height"] and levels > 1:
            fh = min(max((b["height"] - GROUND_H) / (levels - 1), 3.0), 5.0)
        else:
            fh = FLOOR_H + rnd.uniform(-0.25, 0.3)
        floors = [(zb, zb + GROUND_H)]
        for i in range(1, levels):
            floors.append((floors[-1][1], floors[-1][1] + fh))
    return floors, floors[-1][1]


def build_building(b, terrain, coll):
    rnd = random.Random(b["id"])
    rings = b["rings"]
    kind = b["kind"]
    zb = b["gmin"]
    b["zb"] = zb
    b["terrain"] = terrain

    levels = b["levels"]
    floors, top = plan_floors(b, rnd)

    facade = f"facciata{rnd.randrange(len(FACADE_COLORS))}"
    style = {
        "kind": kind, "wall": facade, "base": "piperno", "frame": "stucco", "cornice": "stucco",
        "slab": "pietra_grigia", "shutter": "persiana_verde" if rnd.random() < 0.7 else "persiana_marrone",
        "plain": False,
    }
    if kind == "chiesa":
        style.update(wall="travertino", base="travertino", cornice="stucco", frame="stucco", plain=True)
    elif kind == "castello":
        style.update(wall="tufo", base="tufo", cornice="tufo", plain=True)
    elif kind == "tettoia":
        style.update(plain=True)

    mb = MeshBuilder()
    for ri, ring in enumerate(rings):
        flags = b["flags"][ri]
        for k in range(len(ring)):
            e = Edge(ring[k], ring[(k + 1) % len(ring)])
            if e.L < 0.05:
                continue
            facade_edge(mb, e, flags[k], b, floors, top, rnd, style)
            if ri == 0:
                parapet(mb, e, top, "tufo" if kind == "castello" else style["wall"], crenel=(kind == "castello"))
    roof(mb, rings, top, "lastrico")

    if kind == "palazzo" and levels >= 3:
        xs = [p[0] for p in rings[0]]
        ys = [p[1] for p in rings[0]]
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        if (max(xs) - min(xs)) > 12 and (max(ys) - min(ys)) > 12 and point_in(cx, cy, rings):
            world_box(mb, cx, cy, 3.2, 3.6, top, top + 2.8, style["wall"])

    if b["name"] == "Basilica di San Francesco di Paola":
        xs = [p[0] for p in rings[0]]
        ys = [p[1] for p in rings[0]]
        dome(mb, (min(xs) + max(xs)) / 2 - 8, (min(ys) + max(ys)) / 2, 16.5, top, 9.0, "cupola", "travertino")

    xs = [p[0] for p in rings[0]]
    ys = [p[1] for p in rings[0]]
    origin = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, zb)
    name = b["name"] or f"Palazzo_{b['id']}"
    return mb.build(name[:60], coll, origin)


def point_in(x, y, rings):
    inside = False
    for ring in rings:
        n = len(ring)
        for i in range(n):
            (x0, y0), (x1, y1) = ring[i], ring[(i + 1) % n]
            if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
                inside = not inside
    return inside


# ---------------------------------------------------------------- terreno, strade, aree

def urban_mask(data, t):
    nx, ny, step, x0, y0 = t["nx"], t["ny"], t["step"], t["x0"], t["y0"]
    hit = set()

    def mark(x, y):
        i, j = round((x - x0) / step), round((y - y0) / step)
        for dj in range(-2, 3):
            for di in range(-2, 3):
                hit.add((i + di, j + dj))

    for b in data["buildings"]:
        for ring in b["rings"]:
            for x, y in ring:
                mark(x, y)
    for r in data["roads"]:
        pts = [Vector(p) for p in r["pts"]]
        for a, b in zip(pts, pts[1:]):
            n = max(1, math.ceil((b - a).length / step))
            for s in range(n + 1):
                p = a.lerp(b, s / n)
                mark(p.x, p.y)
    return hit


def build_terrain(data, terrain, coll):
    t = data["terrain"]
    nx, ny, step, x0, y0, h = t["nx"], t["ny"], t["step"], t["x0"], t["y0"], t["h"]
    # In modalità tile le quote arrivano già corrette (terra/mare calcolati su tutta la città)
    urban = set() if t.get("final") else urban_mask(data, t)
    verts = []
    for j in range(ny):
        for i in range(nx):
            z = h[j * nx + i]
            if t.get("final"):
                pass
            elif (i, j) in urban:
                z = max(z, 1.0)
            elif z <= 0.6:
                z = -3.0
            h[j * nx + i] = z
            verts.append((x0 + i * step, y0 + j * step, z))
    faces, uvs = [], []
    for j in range(ny - 1):
        for i in range(nx - 1):
            a = j * nx + i
            q = [a, a + 1, a + 1 + nx, a + nx]
            faces.append(q)
            uvs.extend((verts[k][0], verts[k][1]) for k in q)
    mesh = bpy.data.meshes.new(f"{PREFIX}_Terreno")
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(M["pietra"])
    uv = mesh.uv_layers.new(name="UVMap")
    uv.data.foreach_set("uv", [c for p in uvs for c in p])
    mesh.update()
    obj = bpy.data.objects.new(f"{PREFIX}_Terreno", mesh)
    coll.objects.link(obj)

    if TILE:
        return
    sea = bpy.data.meshes.new("Napoli_Mare")
    s = 40000
    sea.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [[0, 1, 2, 3]])
    sea.materials.append(M["mare"])
    so = bpy.data.objects.new("Napoli_Mare", sea)
    coll.objects.link(so)


def build_roads(data, terrain, coll):
    order = {"pietra": 0.12, "basoli": 0.15, "asfalto": 0.18}
    t = data["terrain"]
    pad = -0.05 if TILE else 2  # in modalità tile le strade sono già tagliate esattamente sul bordo
    gx0, gy0 = t["x0"] + pad, t["y0"] + pad
    gx1, gy1 = t["x0"] + (t["nx"] - 1) * t["step"] - pad, t["y0"] + (t["ny"] - 1) * t["step"] - pad
    inside = lambda p: gx0 <= p.x <= gx1 and gy0 <= p.y <= gy1
    runs = []
    for r in data["roads"]:
        run = []
        for p in r["pts"]:
            v = Vector(p)
            if inside(v):
                run.append(v)
            else:
                if len(run) >= 2:
                    runs.append((r, run))
                run = []
        if len(run) >= 2:
            runs.append((r, run))
    mb = MeshBuilder()
    for r, pts in runs:
        dense = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            n = max(1, math.ceil((b - a).length / 4.0))
            dense += [a.lerp(b, s / n) for s in range(1, n + 1)]
        if len(dense) < 2:
            continue
        lift = order[r["kind"]]
        g0, g1 = terrain(*dense[0]), terrain(*dense[-1])
        total = sum((b - a).length for a, b in zip(dense, dense[1:])) or 1.0
        acc, rows = 0.0, []
        half = r["w"] / 2
        for i, p in enumerate(dense):
            if i:
                acc += (p - dense[i - 1]).length
            a, b = dense[max(i - 1, 0)], dense[min(i + 1, len(dense) - 1)]
            tdir = (b - a)
            if tdir.length < 1e-6:
                continue
            tdir.normalize()
            nrm = Vector((-tdir.y, tdir.x))
            if r.get("span"):  # ponte tagliato tra più tile: rampa calcolata sull'intero ponte
                s0, s1, a_start, a_total = r["span"]
                z = s0 + (s1 - s0) * min((a_start + acc) / (a_total or 1.0), 1.0) + lift
            else:
                z = (g0 + (g1 - g0) * acc / total if r["bridge"] else terrain(p.x, p.y)) + lift
            rows.append(((p + nrm * half).to_3d(), (p - nrm * half).to_3d(), z, acc))
        for (l0, r0, z0, a0), (l1, r1, z1, a1) in zip(rows, rows[1:]):
            mb.face([(r0.x, r0.y, z0), (r1.x, r1.y, z1), (l1.x, l1.y, z1), (l0.x, l0.y, z0)],
                    [(0, a0), (0, a1), (r["w"], a1), (r["w"], a0)], r["kind"])
    mb.build(f"{PREFIX}_Strade", coll)


def build_areas(data, terrain, coll):
    for kind, lift in (("verde", 0.04), ("piazza", 0.07)):
        bm = bmesh.new()
        uv_layer = bm.loops.layers.uv.new("UVMap")
        for a in data["areas"]:
            if a["kind"] != kind:
                continue
            loops = [[Vector((x, y, 0)) for x, y in r] for r in a["rings"] if len(r) >= 3]
            flat = [p for r in loops for p in r]
            vs = [bm.verts.new(p) for p in flat]
            for tri in tessellate_polygon(loops):
                try:
                    f = bm.faces.new([vs[i] for i in tri])
                except ValueError:
                    continue
                if f.normal.z < 0:
                    f.normal_flip()
        bm.verts.ensure_lookup_table()
        for _ in range(6):
            long_edges = [e for e in bm.edges if e.calc_length() > 6.0]
            if not long_edges:
                break
            bmesh.ops.subdivide_edges(bm, edges=long_edges, cuts=1, use_grid_fill=False)
            bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
        for v in bm.verts:
            v.co.z = max(terrain(v.co.x, v.co.y), 0.2) + lift
        for f in bm.faces:
            for loop in f.loops:
                loop[uv_layer].uv = (loop.vert.co.x, loop.vert.co.y)
        mesh = bpy.data.meshes.new(f"{PREFIX}_{kind.capitalize()}")
        bm.to_mesh(mesh)
        bm.free()
        mesh.materials.append(M[kind])
        obj = bpy.data.objects.new(mesh.name, mesh)
        coll.objects.link(obj)


def build_domes(data, terrain, coll):
    mb = MeshBuilder()
    for d in data["domes"]:
        z0 = d["ground"] + d["base"]
        dome(mb, d["c"][0], d["c"][1], d["r"], z0, 0.5, "cupola", "travertino")
    mb.build(f"{PREFIX}_Cupole", coll)


# ---------------------------------------------------------------- scena

def setup_world_and_render():
    scene = bpy.context.scene
    engines = bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items.keys()
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = 1600, 900
    eevee = scene.eevee
    for attr, val in (("taa_render_samples", 48), ("use_raytracing", True), ("use_shadows", True)):
        if hasattr(eevee, attr):
            setattr(eevee, attr, val)
    try:
        scene.view_settings.view_transform = "AgX"
    except TypeError:
        pass
    for look in ("AgX - Medium High Contrast", "Medium High Contrast"):
        try:
            scene.view_settings.look = look
            break
        except TypeError:
            continue
    scene.view_settings.exposure = -0.35

    world = bpy.data.worlds.new("Cielo_Napoli")
    scene.world = world
    try:
        world.use_nodes = True
    except AttributeError:
        pass
    nt = world.node_tree
    bg = next(n for n in nt.nodes if n.type == "BACKGROUND")
    sky = nt.nodes.new("ShaderNodeTexSky")
    chosen = None
    for st in ("MULTIPLE_SCATTERING", "SINGLE_SCATTERING", "NISHITA"):
        try:
            sky.sky_type = st
            chosen = st
            break
        except TypeError:
            continue
    if chosen:
        for attr, val in (("sun_disc", False), ("sun_elevation", math.radians(38)), ("sun_rotation", math.radians(225)),
                          ("altitude", 50.0)):
            if hasattr(sky, attr):
                setattr(sky, attr, val)
        nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = 0.28
    else:
        bg.inputs["Color"].default_value = (*srgb("#bcd3e3"), 1)
        bg.inputs["Strength"].default_value = 1.0

    sun_data = bpy.data.lights.new("Sole", "SUN")
    sun_data.energy = 4.0
    sun_data.angle = math.radians(1.2)
    sun_data.color = srgb("#fff1dd")
    sun = bpy.data.objects.new("Sole", sun_data)
    sun.rotation_euler = (math.radians(52), 0, math.radians(-45))
    scene.collection.objects.link(sun)


def add_camera(name, eye, target, lens=24):
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = lens
    cam_data.clip_start = 0.5
    cam_data.clip_end = 45000
    cam = bpy.data.objects.new(name, cam_data)
    cam.location = eye
    direction = Vector(target) - Vector(eye)
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(cam)
    return cam


def find_road(data, name):
    best = None
    for r in data["roads"]:
        if r["name"] == name and (best is None or len(r["pts"]) > len(best["pts"])):
            best = r
    return best


def setup_cameras(data, terrain):
    cams = []
    cams.append(add_camera("Cam_Plebiscito", (150, -95, terrain(150, -95) + 42), (-45, 25, terrain(-45, 25) + 12), 28))
    toledo = find_road(data, "Via Toledo")
    if toledo:
        pts = sorted(toledo["pts"], key=lambda p: p[1])
        a = Vector(pts[0])
        b = Vector(pts[-1])
        d = (b - a).normalized()
        eye = a + d * 40
        tgt = a + d * 200
        cams.append(add_camera("Cam_Toledo", (eye.x, eye.y, terrain(eye.x, eye.y) + 1.8),
                               (tgt.x, tgt.y, terrain(tgt.x, tgt.y) + 9), 22))
    partenope = find_road(data, "Via Partenope")
    if partenope:
        pts = [Vector(p) for p in partenope["pts"]]
        mid = pts[len(pts) // 2]
        far = min(pts, key=lambda p: p.x)
        eye = Vector((mid.x + 60, mid.y - 230))
        cams.append(add_camera("Cam_Lungomare", (eye.x, eye.y, 22), (far.x, far.y + 30, 16), 24))
    cams.append(add_camera("Cam_Panoramica", (700, -1500, 520), (-60, 0, 30), 30))
    bpy.context.scene.camera = cams[0]
    return cams


TILE = None
PREFIX = "Napoli"


def main():
    global TILE, PREFIX
    if bpy.app.background:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    TILE = data.get("tile")
    if TILE:
        PREFIX = TILE["name"]
    # Le quote si leggono dalla griglia con margine (se c'è), così i palazzi sul bordo della tile sono esatti
    terrain = Terrain(data.get("terrain_sample", data["terrain"]))
    build_materials()

    root = bpy.context.scene.collection
    if TILE:
        root = bpy.data.collections.new(PREFIX)
        bpy.context.scene.collection.children.link(root)
    colls = {}
    for name in ("Edifici", "Terreno", "Strade"):
        colls[name] = bpy.data.collections.new(f"{PREFIX}_{name}")
        root.children.link(colls[name])

    build_terrain(data, terrain, colls["Terreno"])
    log("terreno ok")
    build_areas(data, terrain, colls["Terreno"])
    log("piazze e verde ok")
    build_roads(data, terrain, colls["Strade"])
    log("strade ok")
    total_faces = 0
    for i, b in enumerate(data["buildings"]):
        obj = build_building(b, terrain, colls["Edifici"])
        if obj:
            total_faces += len(obj.data.polygons)
        if i % 250 == 0:
            log(f"edifici {i}/{len(data['buildings'])}")
    build_domes(data, terrain, colls["Edifici"])
    log(f"edifici ok, facce totali {total_faces}")

    if TILE:
        all_faces = sum(len(o.data.polygons) for o in bpy.data.objects if o.type == "MESH")
        print("STATISTICHE " + json.dumps({"tile": PREFIX, "edifici": len(data["buildings"]),
                                            "facce_edifici": total_faces, "facce_totali": all_faces,
                                            "secondi": round(time.time() - T0, 1)}), flush=True)
        if BLEND_OUT:
            bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUT), compress=True)
            log(f"salvato {BLEND_OUT}")
        return

    setup_world_and_render()
    cams = setup_cameras(data, terrain)

    if BLEND_OUT:
        bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUT), compress=True)
        log(f"salvato {BLEND_OUT}")
    if PREVIEW_DIR:
        PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
        scene = bpy.context.scene
        for cam in cams:
            scene.camera = cam
            scene.render.filepath = str(PREVIEW_DIR / f"{cam.name}.png")
            bpy.ops.render.render(write_still=True)
            log(f"render {cam.name}")
        scene.camera = cams[0]


if __name__ == "__main__":
    main()
