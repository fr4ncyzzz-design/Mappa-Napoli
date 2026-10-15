"""Anteprime delle tile: collega (Link) una o più tile in una scena con cielo, sole e mare e fa un render Eevee.

Uso:
    blender -b --factory-startup --python render_tile.py -- uscita.png tile/napoli_r08_c10.blend [altre tile...]
Opzioni (dopo i file):
    --vista tile      vista obliqua che inquadra le tile (predefinita)
    --vista bordo     vista a volo d'uccello lungo il bordo tra due tile vicine
    --vista strada    vista ad altezza d'uomo dal centro della tile
    --res 960x540     risoluzione
    --campioni 16     campioni Eevee
"""
import importlib.util
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent


def load_generator():
    """Importa napoli_palazzi.py senza eseguirlo, per riusare cielo, sole, mare e camere identici."""
    spec = importlib.util.spec_from_file_location("napoli_palazzi", HERE / "napoli_palazzi.py")
    mod = importlib.util.module_from_spec(spec)
    saved = sys.argv
    sys.argv = [saved[0]]
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.argv = saved
    return mod


def link_tile(path, scene):
    """Collega la collezione principale della tile (stesso nome del file) nella scena."""
    name = Path(path).stem
    with bpy.data.libraries.load(str(path), link=True, relative=True) as (src, dst):
        if name not in src.collections:
            raise RuntimeError(f"{path}: collezione '{name}' non trovata")
        dst.collections = [name]
    coll = dst.collections[0]
    scene.collection.children.link(coll)
    return coll


def bounds(colls):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for c in colls:
        for o in c.all_objects:
            if o.type != "MESH" or not o.name.endswith("_Terreno"):
                continue
            for corner in o.bound_box:
                p = o.matrix_world @ Vector(corner)
                lo = Vector(map(min, lo, p))
                hi = Vector(map(max, hi, p))
    return lo, hi


def ground_z(colls, x, y):
    """Quota del terreno sotto (x, y) con un raggio verso il basso sulla scena."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    hit, loc, *_ = bpy.context.scene.ray_cast(depsgraph, Vector((x, y, 2000)), Vector((0, 0, -1)))
    return loc.z if hit else 0.0


def sea_plane(gen, scene):
    gen.M.clear()
    mat = gen.mat_water("Mare")
    me = bpy.data.meshes.new("Napoli_Mare")
    s = 40000
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [[0, 1, 2, 3]])
    me.materials.append(mat)
    ob = bpy.data.objects.new("Napoli_Mare", me)
    scene.collection.objects.link(ob)
    return ob


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    opts = {"--vista": "tile", "--res": "960x540", "--campioni": "16"}
    files = []
    i = 0
    while i < len(argv):
        if argv[i] in opts:
            opts[argv[i]] = argv[i + 1]
            i += 2
        else:
            files.append(argv[i])
            i += 1
    out, tiles = Path(files[0]), files[1:]

    if bpy.app.background:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    gen = load_generator()
    scene = bpy.context.scene
    colls = [link_tile(t, scene) for t in tiles]
    sea_plane(gen, scene)
    gen.setup_world_and_render()
    w, h = (int(v) for v in opts["--res"].split("x"))
    scene.render.resolution_x, scene.render.resolution_y = w, h
    if hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = int(opts["--campioni"])

    lo, hi = bounds(colls)
    c = (lo + hi) / 2
    size = max(hi.x - lo.x, hi.y - lo.y)
    vista = opts["--vista"]
    if vista == "bordo" and len(colls) >= 2:
        # Bordo verticale o orizzontale tra le prime due tile
        a, b = bounds(colls[:1]), bounds(colls[1:2])
        if abs(a[1].x - b[0].x) < 1 or abs(b[1].x - a[0].x) < 1:
            xb = a[1].x if abs(a[1].x - b[0].x) < 1 else a[0].x
            yc = (max(a[0].y, b[0].y) + min(a[1].y, b[1].y)) / 2
            eye = (xb + 60, yc - 520, ground_z(colls, xb, yc - 520) + 160)
            tgt = (xb, yc + 80, ground_z(colls, xb, yc + 80))
        else:
            yb = a[1].y if abs(a[1].y - b[0].y) < 1 else a[0].y
            xc = (max(a[0].x, b[0].x) + min(a[1].x, b[1].x)) / 2
            eye = (xc - 520, yb - 60, ground_z(colls, xc - 520, yb) + 160)
            tgt = (xc + 80, yb, ground_z(colls, xc + 80, yb))
        lens = 26
    elif vista == "strada":
        z = ground_z(colls, c.x, c.y)
        eye = (c.x, c.y - 60, ground_z(colls, c.x, c.y - 60) + 1.8)
        tgt = (c.x, c.y + 200, z + 12)
        lens = 22
    else:
        zc = ground_z(colls, c.x, c.y)
        eye = (c.x - size * 0.55, c.y - size * 1.05, zc + size * 0.75)
        tgt = (c.x, c.y + size * 0.05, zc)
        lens = 32
    cam = gen.add_camera("Cam_Anteprima", eye, tgt, lens)
    scene.camera = cam
    scene.render.filepath = str(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.render.render(write_still=True)
    print(f"render salvato {out}")


if __name__ == "__main__":
    main()
