"""Versione leggera (LOD) di tutta Napoli per la vista da lontano: napoli_lod.blend.

Per ogni tile crea la collezione <nome_tile>_LOD con:
  - edifici come blocchi estrusi (stessa pianta, stessa altezza e stesso colore della facciata del dettaglio,
    senza finestre, balconi né cornicioni);
  - terreno su griglia da 40 m (stessi vertici di bordo delle tile vicine);
  - verde e piazze appoggiati sul terreno leggero.

Uso:
    blender -b --factory-startup --python costruisci_lod.py -- tile napoli_lod.blend
"""
import importlib.util
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

HERE = Path(__file__).resolve().parent
LOD_STEP = 5  # 5 celle da 8 m = 40 m
T0 = time.time()


def log(msg):
    print(f"[{time.time() - T0:6.1f}s] {msg}", flush=True)


def load_generator():
    spec = importlib.util.spec_from_file_location("napoli_palazzi", HERE / "napoli_palazzi.py")
    mod = importlib.util.module_from_spec(spec)
    saved = sys.argv
    sys.argv = [saved[0]]
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.argv = saved
    return mod


def simple_material(gen, name, color, rough=0.85):
    m, _, _ = gen.new_material(name, color, rough)
    return m


def lod_terrain_grid(t):
    nx, ny, h = t["nx"], t["ny"], t["h"]
    ix = list(range(0, nx, LOD_STEP))
    iy = list(range(0, ny, LOD_STEP))
    assert ix[-1] == nx - 1 and iy[-1] == ny - 1, "la tile deve essere un multiplo di 40 m"
    return {"x0": t["x0"], "y0": t["y0"], "step": t["step"] * LOD_STEP, "nx": len(ix), "ny": len(iy),
            "h": [h[j * nx + i] for j in iy for i in ix]}


def build_terrain(gen, name, g, coll):
    nx, ny, step, x0, y0, h = g["nx"], g["ny"], g["step"], g["x0"], g["y0"], g["h"]
    verts = [(x0 + i * step, y0 + j * step, h[j * nx + i]) for j in range(ny) for i in range(nx)]
    faces = [[j * nx + i, j * nx + i + 1, (j + 1) * nx + i + 1, (j + 1) * nx + i]
             for j in range(ny - 1) for i in range(nx - 1)]
    me = bpy.data.meshes.new(f"{name}_LOD_Terreno")
    me.from_pydata(verts, [], faces)
    me.materials.append(gen.M["lod_terreno"])
    ob = bpy.data.objects.new(me.name, me)
    coll.objects.link(ob)
    return len(faces)


def build_areas(gen, name, data, terrain, coll):
    faces = 0
    for kind, lift in (("verde", 0.6), ("piazza", 0.8)):
        bm = bmesh.new()
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
        for _ in range(4):
            long_edges = [e for e in bm.edges if e.calc_length() > 40.0]
            if not long_edges:
                break
            bmesh.ops.subdivide_edges(bm, edges=long_edges, cuts=1, use_grid_fill=False)
            bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
        for v in bm.verts:
            v.co.z = max(terrain(v.co.x, v.co.y), 0.2) + lift
        if not bm.faces:
            bm.free()
            continue
        me = bpy.data.meshes.new(f"{name}_LOD_{kind.capitalize()}")
        bm.to_mesh(me)
        bm.free()
        me.materials.append(gen.M[f"lod_{kind}"])
        faces += len(me.polygons)
        ob = bpy.data.objects.new(me.name, me)
        coll.objects.link(ob)
    return faces


def build_buildings(gen, name, data, coll):
    mb = gen.MeshBuilder()
    for b in data["buildings"]:
        rnd = random.Random(b["id"])
        floors, top = gen.plan_floors(b, rnd)
        facade = rnd.randrange(len(gen.FACADE_COLORS))
        mat = {"chiesa": "lod_travertino", "castello": "lod_tufo"}.get(b["kind"], f"lod_facciata{facade}")
        z0 = b["gmin"] - 3.0
        for ring in b["rings"]:
            for k in range(len(ring)):
                e = gen.Edge(ring[k], ring[(k + 1) % len(ring)])
                if e.L >= 0.05:
                    gen.wall(mb, e, 0, e.L, z0, top, 0, mat)
        gen.roof(mb, b["rings"], top, "lod_lastrico")
    obj = mb.build(f"{name}_LOD_Edifici", coll)
    return len(obj.data.polygons) if obj else 0


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    tile_dir, out = Path(argv[0]), Path(argv[1])
    if bpy.app.background:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    gen = load_generator()
    for i, c in enumerate(gen.FACADE_COLORS):
        gen.M[f"lod_facciata{i}"] = simple_material(gen, f"LOD_Facciata_{i:02d}", c)
    gen.M["lod_travertino"] = simple_material(gen, "LOD_Travertino", "#ddd3bd")
    gen.M["lod_tufo"] = simple_material(gen, "LOD_Tufo", "#8a7c66")
    gen.M["lod_lastrico"] = simple_material(gen, "LOD_Lastrico", "#b9b2a6")
    gen.M["lod_terreno"] = simple_material(gen, "LOD_Terreno", "#88837a")
    gen.M["lod_verde"] = simple_material(gen, "LOD_Verde", "#5d7b3e")
    gen.M["lod_piazza"] = simple_material(gen, "LOD_Piazza", "#8e877b")

    index = json.loads((tile_dir / "indice_tile.json").read_text(encoding="utf-8"))
    totals = {}
    for t in index["tiles"]:
        name = t["name"]
        data = json.loads((tile_dir / f"{name}.json").read_text(encoding="utf-8"))
        coll = bpy.data.collections.new(f"{name}_LOD")
        bpy.context.scene.collection.children.link(coll)
        g = lod_terrain_grid(data["terrain"])
        terrain = gen.Terrain(g)
        f_t = build_terrain(gen, name, g, coll)
        f_a = build_areas(gen, name, data, terrain, coll)
        f_b = build_buildings(gen, name, data, coll)
        totals[name] = {"facce_lod": f_t + f_a + f_b, "edifici": len(data["buildings"])}
        log(f"{name}: {f_t + f_a + f_b:,} facce LOD ({len(data['buildings'])} edifici)")
    total = sum(v["facce_lod"] for v in totals.values())
    print("STATISTICHE_LOD " + json.dumps({"tile": len(totals), "facce": total}), flush=True)
    (tile_dir / "statistiche_lod.json").write_text(json.dumps(totals, indent=1), encoding="utf-8")
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
    log(f"salvato {out}: {total:,} facce in {len(totals)} tile")


if __name__ == "__main__":
    main()
