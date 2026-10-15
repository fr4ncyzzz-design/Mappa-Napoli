"""napoli_tutta.blend: collega (Link) tutte le tile, con un solo cielo, un solo sole e un solo mare.

Struttura del file:
  Napoli_LOD        versione leggera di tutte le tile (da napoli_lod.blend), visibile all'apertura
  Napoli_Dettaglio  tutte le tile complete (da tile/*.blend), ESCLUSE dal view layer all'apertura:
                    nell'Outliner spunta la casella di una tile per vederla in dettaglio
                    (e togli la spunta alla stessa tile in Napoli_LOD).
  Napoli_Mare, Sole, cielo nel World, camere panoramiche.

Uso:
    blender -b --factory-startup --python costruisci_tutta.py -- tile napoli_lod.blend napoli_tutta.blend [anteprima.png]
"""
import importlib.util
import json
import sys
import time
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
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


def link_collections(path, names):
    with bpy.data.libraries.load(str(path), link=True, relative=True) as (src, dst):
        missing = [n for n in names if n not in src.collections]
        if missing:
            raise RuntimeError(f"{path}: collezioni mancanti {missing}")
        dst.collections = list(names)
    return list(dst.collections)


def find_layer(layer, name):
    if layer.name == name:
        return layer
    for child in layer.children:
        found = find_layer(child, name)
        if found:
            return found
    return None


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    tile_dir, lod_file, out = Path(argv[0]).resolve(), Path(argv[1]).resolve(), Path(argv[2]).resolve()
    preview = Path(argv[3]) if len(argv) > 3 else None
    if bpy.app.background:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    # I percorsi relativi delle librerie si calcolano rispetto al file salvato: lo salvo subito vuoto
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out))

    gen = load_generator()
    scene = bpy.context.scene
    index = json.loads((tile_dir / "indice_tile.json").read_text(encoding="utf-8"))
    names = [t["name"] for t in index["tiles"] if (tile_dir / f"{t['name']}.blend").exists()]
    log(f"{len(names)} tile da collegare")

    lod = bpy.data.collections.new("Napoli_LOD")
    det = bpy.data.collections.new("Napoli_Dettaglio")
    scene.collection.children.link(lod)
    scene.collection.children.link(det)

    for coll in link_collections(lod_file, [f"{n}_LOD" for n in names]):
        lod.children.link(coll)
    log("LOD collegato")
    for n in names:
        for coll in link_collections(tile_dir / f"{n}.blend", [n]):
            det.children.link(coll)
    log("tile di dettaglio collegate")

    view = bpy.context.view_layer
    for n in names:
        layer = find_layer(view.layer_collection, n)
        if layer:
            layer.exclude = True

    # Un solo mare, cielo e sole
    gen.M.clear()
    sea = bpy.data.meshes.new("Napoli_Mare")
    s = 40000
    sea.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [[0, 1, 2, 3]])
    sea.materials.append(gen.mat_water("Mare"))
    scene.collection.objects.link(bpy.data.objects.new("Napoli_Mare", sea))
    gen.setup_world_and_render()

    cx = (index["xmin"] + index["xmax"]) / 2
    cy = (index["ymin"] + index["ymax"]) / 2
    cams = [
        gen.add_camera("Cam_Napoli_Golfo", (cx + 1500, index["ymin"] - 7500, 3600), (cx - 800, cy + 600, 0), 30),
        gen.add_camera("Cam_Napoli_Alto", (cx, cy - 9000, 16000), (cx, cy + 500, 0), 30),
        gen.add_camera("Cam_Plebiscito", (150, -95, 50), (-45, 25, 15), 28),
    ]
    scene.camera = cams[0]
    for c in cams:
        c.data.clip_end = 80000

    bpy.ops.wm.save_as_mainfile(filepath=str(out), relative_remap=True, compress=True)
    log(f"salvato {out}")

    if preview:
        scene.render.filepath = str(preview)
        bpy.ops.render.render(write_still=True)
        log(f"render {preview}")


if __name__ == "__main__":
    main()
