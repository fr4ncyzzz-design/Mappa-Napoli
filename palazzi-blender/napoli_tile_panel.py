"""Pannello "Napoli" (vista 3D > barra laterale N): collega e scollega le tile di dettaglio su richiesta.

È incluso in napoli_tutta.blend come testo registrato: all'apertura Blender chiede di consentire gli script
("Allow Execution"); in alternativa apri il testo napoli_tile_panel.py nel Text Editor e premi Run Script.

- Le tile di dettaglio si collegano (Link) da tile/<nome>.blend dentro la collezione Napoli_Dettaglio.
- Quando una tile di dettaglio è caricata, la stessa tile in Napoli_LOD viene esclusa (niente doppioni).
- Ogni tile densa occupa 0,5-1 GB di RAM: tutte insieme ne servono ~14 GB.
"""
import json

import bpy

INDEX_TEXT = "napoli_indice_tile.json"


def index():
    return json.loads(bpy.data.texts[INDEX_TEXT].as_string())


def find_layer(layer, name):
    if layer.name == name:
        return layer
    for child in layer.children:
        found = find_layer(child, name)
        if found:
            return found
    return None


def set_lod_visible(context, name, visible):
    layer = find_layer(context.view_layer.layer_collection, f"{name}_LOD")
    if layer:
        layer.exclude = not visible


def library_of(name):
    for lib in bpy.data.libraries:
        if bpy.path.basename(lib.filepath) == f"{name}.blend":
            return lib
    return None


def loaded():
    return sorted(bpy.path.basename(lib.filepath)[:-6] for lib in bpy.data.libraries
                  if bpy.path.basename(lib.filepath).startswith("napoli_r"))


def load_tile(context, name):
    if library_of(name):
        return False
    path = f"//tile/{name}.blend"
    with bpy.data.libraries.load(path, link=True, relative=True) as (src, dst):
        dst.collections = [name]
    det = bpy.data.collections.get("Napoli_Dettaglio")
    if det is None:
        det = bpy.data.collections.new("Napoli_Dettaglio")
        context.scene.collection.children.link(det)
    det.children.link(dst.collections[0])
    set_lod_visible(context, name, False)
    return True


def unload_tile(context, name):
    lib = library_of(name)
    if lib:
        bpy.data.libraries.remove(lib)
    set_lod_visible(context, name, True)


def normalize(name):
    name = name.strip().lower()
    return name if name.startswith("napoli_") else f"napoli_{name}"


class NAPOLI_OT_carica_vicino(bpy.types.Operator):
    """Collega le tile di dettaglio vicine al cursore 3D"""
    bl_idname = "napoli.carica_vicino"
    bl_label = "Carica tile vicino al cursore"

    def execute(self, context):
        c = context.scene.cursor.location
        r = context.scene.napoli_raggio * 1000.0
        n = 0
        for t in index()["tiles"]:
            dx = max(t["x0"] - c.x, 0, c.x - t["x1"])
            dy = max(t["y0"] - c.y, 0, c.y - t["y1"])
            if dx * dx + dy * dy <= r * r:
                n += load_tile(context, t["name"])
        self.report({"INFO"}, f"{n} tile caricate, totale {len(loaded())}")
        return {"FINISHED"}


class NAPOLI_OT_carica_nome(bpy.types.Operator):
    """Collega una tile di dettaglio per nome (es. r08_c10)"""
    bl_idname = "napoli.carica_nome"
    bl_label = "Carica tile"

    def execute(self, context):
        name = normalize(context.scene.napoli_tile)
        if name not in {t["name"] for t in index()["tiles"]}:
            self.report({"ERROR"}, f"tile {name} non trovata")
            return {"CANCELLED"}
        load_tile(context, name)
        return {"FINISHED"}


class NAPOLI_OT_scarica_tutte(bpy.types.Operator):
    """Scollega tutte le tile di dettaglio e mostra di nuovo la versione leggera"""
    bl_idname = "napoli.scarica_tutte"
    bl_label = "Scarica tutte"

    def execute(self, context):
        for name in loaded():
            unload_tile(context, name)
        return {"FINISHED"}


class NAPOLI_OT_scarica_nome(bpy.types.Operator):
    """Scollega una tile di dettaglio"""
    bl_idname = "napoli.scarica_nome"
    bl_label = "Scarica tile"

    def execute(self, context):
        unload_tile(context, normalize(context.scene.napoli_tile))
        return {"FINISHED"}


class NAPOLI_PT_tile(bpy.types.Panel):
    bl_label = "Napoli: tile"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Napoli"

    def draw(self, context):
        lay = self.layout
        names = loaded()
        faces = {t["name"]: t.get("facce", 0) for t in index()["tiles"]}
        lay.label(text=f"Dettaglio caricato: {len(names)} tile, {sum(faces.get(n, 0) for n in names) / 1e6:.1f} M facce")
        col = lay.column(align=True)
        col.prop(context.scene, "napoli_raggio")
        col.operator("napoli.carica_vicino", icon="PIVOT_CURSOR")
        col = lay.column(align=True)
        col.prop(context.scene, "napoli_tile", text="Tile")
        row = col.row(align=True)
        row.operator("napoli.carica_nome", icon="LINKED")
        row.operator("napoli.scarica_nome", icon="UNLINKED")
        lay.operator("napoli.scarica_tutte", icon="TRASH")
        if names:
            box = lay.box()
            for n in names[:12]:
                box.label(text=n)
            if len(names) > 12:
                box.label(text=f"... e altre {len(names) - 12}")


CLASSES = (NAPOLI_OT_carica_vicino, NAPOLI_OT_carica_nome, NAPOLI_OT_scarica_tutte, NAPOLI_OT_scarica_nome,
           NAPOLI_PT_tile)


def register():
    bpy.types.Scene.napoli_raggio = bpy.props.FloatProperty(
        name="Raggio (km)", default=0.8, min=0.1, max=20.0, description="Distanza dal cursore 3D")
    bpy.types.Scene.napoli_tile = bpy.props.StringProperty(name="Tile", default="r08_c10")
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


# Eseguito sia con Run Script sia come testo registrato all'apertura del file
try:
    unregister()
except RuntimeError:
    pass
register()
