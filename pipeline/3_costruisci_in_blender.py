"""Passo 3: costruisce Napoli in Blender e la esporta per GTA V / FiveM con Sollumz.

Per ogni blocco crea in Blender:
  - un Drawable Sollumz (terreno + edifici + strade) -> .ydr
  - un Drawable LOD semplificato per la vista da lontano -> .ydr
  - una Bound Composite con la collisione (si cammina e si guida) -> .ybn
Poi scrive texture (.ytd), archetipi (.ytyp), piazzamenti (.ymap) e la risorsa FiveM.

Uso (Blender 4.2+ con l'addon Sollumz installato e attivo):
    blender -b -P pipeline/3_costruisci_in_blender.py -- --zona prova
Opzioni utili:
    --formato binario|xml|auto   binario richiede PyMateria (Sollumz > Preferenze, solo Windows)
    --salva-blend                salva anche il file .blend modificabile (consigliato per zone piccole)
    --blocchi nap_03_04,...      ricostruisce solo alcuni blocchi
    --senza-lod                  niente LOD (entità ORPHANHD)
    --mare-visibile              aggiunge una superficie del mare (se lì GTA non ha acqua)
"""

import argparse
import importlib
import json
import shutil
import sys
import time
import zlib
from pathlib import Path

import bpy  # noqa: I001 - bpy va importato prima di addon_utils
import addon_utils
import numpy as np
from mathutils import Quaternion, Vector

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI))
import config  # noqa: E402
import geometria as geo  # noqa: E402


def argomenti():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="blender -b -P 3_costruisci_in_blender.py --")
    ap.add_argument("--zona", default="prova")
    ap.add_argument("--formato", choices=["auto", "binario", "xml"], default="auto")
    ap.add_argument("--sollumz", help="cartella dell'addon Sollumz, se non è installato in Blender")
    ap.add_argument("--salva-blend", action="store_true")
    ap.add_argument("--senza-lod", action="store_true")
    ap.add_argument("--mare-visibile", action="store_true")
    ap.add_argument("--blocchi", help="elenco di blocchi separati da virgola")
    return ap.parse_args(argv)


# ---------------------------------------------------------------------------
# Sollumz
# ---------------------------------------------------------------------------
PKG = None


def sz(modulo):
    return importlib.import_module(f"{PKG}.{modulo}")


def attiva_sollumz(percorso):
    global PKG
    if percorso:
        p = Path(percorso).absolute()
        sys.path.insert(0, str(p.parent))
        addon_utils.enable(p.name, default_set=True, persistent=True)
        PKG = p.name
        return
    for mod in addon_utils.modules(refresh=True):
        if mod.__name__.split(".")[-1].lower().startswith("sollumz"):
            addon_utils.enable(mod.__name__, default_set=True, persistent=True)
            PKG = mod.__name__
            return
    raise SystemExit(
        "Sollumz non trovato. Installalo da https://github.com/Sollumz/Sollumz/releases "
        "(Blender > Preferenze > Add-on > Installa da disco) oppure usa --sollumz <cartella>."
    )


def controlla_sollumz():
    if not hasattr(bpy.types.Material, "sollum_type"):
        raise SystemExit(
            "Sollumz è installato ma non è pronto: apri Blender > Preferenze > Add-on > Sollumz, premi "
            "'Install dependencies' (szio), riavvia Blender e rilancia questo script."
        )


def obiettivi(formato):
    from szio.gta5 import AssetFormat, AssetTarget, AssetVersion, is_provider_available

    nativo = is_provider_available(AssetFormat.NATIVE)
    if formato == "binario" and not nativo:
        raise SystemExit("Formato binario non disponibile: installa PyMateria da Blender > Preferenze > Sollumz.")
    usa_nativo = formato == "binario" or (formato == "auto" and nativo)
    fmt = AssetFormat.NATIVE if usa_nativo else AssetFormat.CWXML
    return (AssetTarget(fmt, AssetVersion.GEN8),), usa_nativo


# ---------------------------------------------------------------------------
# Materiali e texture
# ---------------------------------------------------------------------------
def crea_materiali(cartella_tex):
    sm = sz("ydr.shader_materials")
    cartella_tex.mkdir(parents=True, exist_ok=True)
    materiali, texture = [], {}
    for nome in geo.MATERIALI:
        nome_tex = f"{config.PREFISSO}_{nome}"
        px = geo.genera_texture(nome)
        percorso = cartella_tex / f"{nome_tex}.dds"
        percorso.write_bytes(geo.dds_rgba(px))
        texture[nome_tex] = percorso

        img = bpy.data.images.get(nome_tex) or bpy.data.images.new(nome_tex, px.shape[1], px.shape[0], alpha=True)
        # In Blender la prima riga è in basso, nei DDS in alto
        img.pixels.foreach_set((np.flipud(px).astype(np.float32) / 255.0).ravel())
        img.pack()
        # Sollumz ricava il nome della texture dal percorso del file
        img.filepath_raw = str(percorso)

        mat = sm.create_shader("default.sps")
        mat.name = nome_tex
        nodo = mat.node_tree.nodes["DiffuseSampler"]
        nodo.image = img
        nodo.texture_properties.embedded = False
        materiali.append(mat)
    return materiali, texture


def crea_materiali_collisione():
    cm = sz("ybn.collision_materials")
    indici = {m.name: i for i, m in enumerate(cm.collisionmats)}
    per_nome = {}
    elenco = []
    for nome in geo.MATERIALI:
        gta = geo.materiale_collisione(nome)
        if gta not in per_nome:
            mat = cm.create_collision_material_from_index(indici.get(gta, 0))
            mat.name = f"col_{gta.lower()}"
            per_nome[gta] = len(elenco)
            elenco.append(mat)
    mappa = np.array([per_nome[geo.materiale_collisione(n)] for n in geo.MATERIALI], dtype=np.int32)
    return elenco, mappa


# ---------------------------------------------------------------------------
# Mesh
# ---------------------------------------------------------------------------
def crea_mesh(nome, V, T, M=None, UV=None, C=None, S=None, materiali=()):
    me = bpy.data.meshes.new(nome)
    me.vertices.add(len(V))
    me.vertices.foreach_set("co", np.asarray(V, dtype=np.float32).ravel())
    me.loops.add(len(T) * 3)
    me.loops.foreach_set("vertex_index", np.asarray(T, dtype=np.int32).ravel())
    me.polygons.add(len(T))
    me.polygons.foreach_set("loop_start", np.arange(0, len(T) * 3, 3, dtype=np.int32))
    for m in materiali:
        me.materials.append(m)
    if M is not None:
        me.polygons.foreach_set("material_index", np.asarray(M, dtype=np.int32))
    if S is not None:
        me.polygons.foreach_set("use_smooth", np.asarray(S, dtype=bool))
    me.update(calc_edges=True)
    if UV is not None:
        uv = me.uv_layers.new(name="UVMap 0")
        uv.data.foreach_set("uv", np.asarray(UV, dtype=np.float32).ravel())
    if C is not None:
        col = me.color_attributes.new("Color 1", "BYTE_COLOR", "CORNER")
        c = np.asarray(C, dtype=np.float32)
        col.data.foreach_set("color_srgb", np.column_stack([c, c, c, np.ones_like(c)]).ravel())
    me.validate(clean_customdata=False)
    return me


def compatta_materiali(dati, materiali):
    """Tiene solo i materiali usati (meno shader = drawable più leggero)."""
    usati = np.unique(dati["M"])
    mappa = np.zeros(len(materiali), dtype=np.int32)
    mappa[usati] = np.arange(len(usati))
    return mappa[dati["M"]], [materiali[i] for i in usati]


def crea_drawable(nome, dati, materiali, posizione, collezione):
    dh = sz("tools.drawablehelper")
    M, mats = compatta_materiali(dati, materiali)
    me = crea_mesh(nome, dati["V"], dati["T"], M, dati["UV"], dati["C"], dati["S"], mats)
    ob = bpy.data.objects.new(nome, me)
    collezione.objects.link(ob)
    drw = dh.convert_obj_to_drawable(ob)
    drw.name = nome
    drw.location = Vector(posizione)
    for o in (drw, ob):
        for c in list(o.users_collection):
            c.objects.unlink(o)
        collezione.objects.link(o)
    return drw


def crea_collisione(nome, V, T, M, mat_col, mappa_col, collezione):
    bh = sz("tools.boundhelper")
    from_types = sz("sollumz_properties")
    V, T, buoni = geo.salda(V, T)
    T = T[buoni]
    Mc = mappa_col[M[buoni]]
    composita = None
    for k, (Vp, Tp, Mp) in enumerate(geo.dividi(V, T, Mc)):
        usati = np.unique(Mp)
        rimappa = np.zeros(len(mat_col), dtype=np.int32)
        rimappa[usati] = np.arange(len(usati))
        me = crea_mesh(f"{nome}_{k}", Vp, Tp, rimappa[Mp], materiali=[mat_col[i] for i in usati])
        ob = bpy.data.objects.new(f"{nome}_{k}", me)
        collezione.objects.link(ob)
        if composita is None:
            composita = bh.convert_obj_to_composite(ob, from_types.SollumType.BOUND_GEOMETRYBVH, "General (Default)")
            composita.name = nome
        else:
            bvh = bh.convert_obj_to_bvh(ob, "General (Default)")
            bvh.parent = composita
    for o in [composita] + list(composita.children_recursive):
        for c in list(o.users_collection):
            c.objects.unlink(o)
        collezione.objects.link(o)
    return composita


def limiti(V):
    vmin = V.min(axis=0)
    vmax = V.max(axis=0)
    centro = (vmin + vmax) / 2
    raggio = float(np.linalg.norm(vmax - vmin) / 2)
    return vmin, vmax, centro, raggio


def elimina(oggetti):
    mesh = {o.data for o in oggetti if o.type == "MESH"}
    for o in oggetti:
        bpy.data.objects.remove(o, do_unlink=True)
    for m in mesh:
        if m.users == 0:
            bpy.data.meshes.remove(m)


# ---------------------------------------------------------------------------
def esporta(funzione, oggetto, nome, cartella, obiettivi_export):
    ie = sz("iecontext")
    impostazioni = ie.ExportSettings(targets=obiettivi_export)
    with ie.export_context_scope(ie.ExportContext(nome, impostazioni)):
        pacchetto = funzione(oggetto)
    if not pacchetto or not pacchetto.is_valid():
        raise RuntimeError(f"Esportazione di '{nome}' non valida (controlla il log di Sollumz)")
    pacchetto.save(cartella, obiettivi_export)


def main():
    args = argomenti()
    zona = config.preset(args.zona)
    # Scena vuota, poi Sollumz
    bpy.ops.wm.read_homefile(use_empty=True)
    attiva_sollumz(args.sollumz)
    controlla_sollumz()
    targets, nativo = obiettivi(args.formato)

    from szio.gta5 import (
        Archetype, ArchetypeAssetType, ArchetypeType, AssetMapData, AssetMapTypes, AssetTextureDictionary,
        EmbeddedTexture, Entity, EntityFlags, EntityLodLevel, EntityPriorityLevel, MapBlockDescription,
        MapContentFlags, MapFlags, save_asset,
    )
    from szio.types import DataSource

    ydrexport = sz("ydr.ydrexport")
    ybnexport = sz("ybn.ybnexport")

    cartella_blocchi = config.CARTELLA_DATI / f"blocchi_{args.zona}"
    indice = json.loads((cartella_blocchi / "indice.json").read_text(encoding="utf-8"))
    uscita = config.CARTELLA_USCITA / args.zona
    risorsa = uscita / config.NOME_RISORSA
    stream = risorsa / "stream"
    cartella_asset = stream if nativo else uscita / "xml_codewalker"
    if cartella_asset.exists() and not args.blocchi:
        shutil.rmtree(cartella_asset)
    cartella_asset.mkdir(parents=True, exist_ok=True)

    print(f"Napoli 3D - zona '{args.zona}', formato {'binario' if nativo else 'XML CodeWalker'}")
    print(f"Uscita: {cartella_asset}")

    scena = bpy.context.scene
    coll = bpy.data.collections.new(f"Napoli_{args.zona}")
    scena.collection.children.link(coll)

    materiali, texture = crea_materiali(uscita / "texture")
    mat_col, mappa_col = crea_materiali_collisione()

    og = np.array(zona["origine_gta"], dtype=np.float64)
    L = indice["lato_blocco"]
    scelti = set(args.blocchi.split(",")) if args.blocchi else None
    archetipi, voci = [], []
    t0 = time.time()
    blocchi = [b for b in indice["blocchi"] if not b["solo_mare"] and (scelti is None or b["nome"] in scelti)]
    for n, b in enumerate(blocchi, 1):
        d = dict(np.load(cartella_blocchi / f"{b['nome']}.npz"))
        centro_loc = d["origine"] + L / 2
        centro_gta = np.array([centro_loc[0] + og[0], centro_loc[1] + og[1], og[2]])
        vis, colli, lod, n_ed, n_st = geo.blocco(d, centro_loc, L, args.mare_visibile)

        creati = []
        nome = b["nome"]
        nome_lod = f"{nome}_lod"
        drw = crea_drawable(nome, vis, materiali, centro_gta, coll)
        creati += [drw] + list(drw.children_recursive)
        esporta(ydrexport.export_ydr, drw, nome, cartella_asset, targets)
        vmin, vmax, bsc, bsr = limiti(vis["V"])
        archetipi.append(Archetype(
            name=nome, type=ArchetypeType.BASE, flags=0, lod_dist=config.LOD_DIST_BLOCCO, special_attribute=0,
            hd_texture_dist=100.0, texture_dictionary=config.NOME_TXD, clip_dictionary="", drawable_dictionary="",
            physics_dictionary="", bb_min=Vector(vmin), bb_max=Vector(vmax), bs_center=Vector(bsc), bs_radius=bsr,
            asset_name=nome, asset_type=ArchetypeAssetType.DRAWABLE, extensions=[],
        ))
        voce = {"nome": nome, "pos": centro_gta, "min": vmin, "max": vmax, "i": b["i"], "j": b["j"]}

        if not args.senza_lod and lod is not None:
            drl = crea_drawable(nome_lod, lod, materiali, centro_gta, coll)
            creati += [drl] + list(drl.children_recursive)
            esporta(ydrexport.export_ydr, drl, nome_lod, cartella_asset, targets)
            lmin, lmax, lc, lr = limiti(lod["V"])
            archetipi.append(Archetype(
                name=nome_lod, type=ArchetypeType.BASE, flags=0, lod_dist=config.LOD_DIST_PANORAMA,
                special_attribute=0, hd_texture_dist=100.0, texture_dictionary=config.NOME_TXD,
                clip_dictionary="", drawable_dictionary="", physics_dictionary="", bb_min=Vector(lmin),
                bb_max=Vector(lmax), bs_center=Vector(lc), bs_radius=lr, asset_name=nome_lod,
                asset_type=ArchetypeAssetType.DRAWABLE, extensions=[],
            ))
            voce["lod"] = {"nome": nome_lod, "min": lmin, "max": lmax}

        # Collisione in coordinate del mondo GTA (i .ybn statici non hanno un'entità)
        Vw = colli["V"] + centro_gta
        comp = crea_collisione(f"{nome}_col", Vw, colli["T"], colli["M"], mat_col, mappa_col, coll)
        creati += [comp] + list(comp.children_recursive)
        esporta(ybnexport.export_ybn, comp, f"{nome}_col", cartella_asset, targets)
        voci.append(voce)

        if not args.salva_blend:
            elimina(creati)
        trascorso = time.time() - t0
        print(f"[{n}/{len(blocchi)}] {nome}: {n_ed} edifici, {n_st} strade, "
              f"{len(vis['T'])} triangoli  ({trascorso:.0f}s, mancano ~{trascorso / n * (len(blocchi) - n):.0f}s)")

    # --- Texture dictionary condiviso
    ytd = AssetTextureDictionary(textures={
        nome: EmbeddedTexture(nome, 256, 256, DataSource.create(p.read_bytes(), f"{nome}.dds"))
        for nome, p in texture.items()
    })
    save_asset(ytd, targets, cartella_asset, config.NOME_TXD)
    if not nativo:
        # CodeWalker importa le texture dalla cartella con lo stesso nome del .ytd.xml
        cartella_dds = cartella_asset / config.NOME_TXD
        cartella_dds.mkdir(exist_ok=True)
        for nome, p in texture.items():
            shutil.copy2(p, cartella_dds / f"{nome}.dds")

    # --- Archetipi
    if not args.blocchi:
        save_asset(AssetMapTypes(name=config.NOME_YTYP, archetypes=archetipi), targets, cartella_asset,
                   config.NOME_YTYP)
        scrivi_ymap(voci, args.senza_lod, targets, cartella_asset, locals())
    else:
        print("(--blocchi: .ytyp e .ymap non rigenerati, riusa quelli della build completa)")

    scrivi_risorsa(risorsa, indice, nativo)

    if args.salva_blend:
        percorso = uscita / f"napoli_{args.zona}.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(percorso), compress=True)
        print(f"File Blender: {percorso}")
    print(f"Fatto in {time.time() - t0:.0f}s.")


def scrivi_ymap(voci, senza_lod, targets, cartella, ns):
    Entity, EntityFlags, EntityLodLevel = ns["Entity"], ns["EntityFlags"], ns["EntityLodLevel"]
    EntityPriorityLevel, AssetMapData = ns["EntityPriorityLevel"], ns["AssetMapData"]
    MapFlags, MapContentFlags, MapBlockDescription = ns["MapFlags"], ns["MapContentFlags"], ns["MapBlockDescription"]
    save_asset = ns["save_asset"]

    ombre = EntityFlags.CAST_STATIC_SHADOWS | EntityFlags.CAST_DYNAMIC_SHADOWS
    identita = Quaternion((1.0, 0.0, 0.0, 0.0))

    def entita(nome, pos, lod_dist, livello, flags, genitore=-1, figli=0, dist_figli=0.0):
        return Entity(
            archetype_name=nome, position=Vector(pos), rotation=identita, scale_xy=1.0, scale_z=1.0,
            flags=flags, guid=zlib.crc32(nome.encode()), parent_index=genitore, lod_dist=lod_dist,
            child_lod_dist=dist_figli, lod_level=livello, priority_level=EntityPriorityLevel.REQUIRED,
            num_children=figli, ambient_occlusion_multiplier=255, artificial_ambient_occlusion=255,
            tint_value=0, extensions=[],
        )

    def estensioni(elementi, margine):
        mins = np.array([e[0] for e in elementi])
        maxs = np.array([e[1] for e in elementi])
        emin, emax = mins.min(axis=0), maxs.max(axis=0)
        return (Vector(emin), Vector(emax)), (Vector(emin - margine), Vector(emax + margine))

    def descrizione(nome):
        return MapBlockDescription(version=0, flags=0, name=nome, exported_by="Napoli3D (Blender + Sollumz)",
                                   owner="", time=time.strftime("%d %B %Y %H:%M"))

    usa_lod = not senza_lod and all("lod" in v for v in voci)
    nome_lod = f"{config.PREFISSO}_lod"
    indice_lod = {}
    if usa_lod:
        ents, est = [], []
        for k, v in enumerate(voci):
            ents.append(entita(v["lod"]["nome"], v["pos"], config.LOD_DIST_PANORAMA, EntityLodLevel.LOD,
                               ombre, figli=1, dist_figli=config.LOD_DIST_BLOCCO))
            est.append((v["pos"] + v["lod"]["min"], v["pos"] + v["lod"]["max"]))
            indice_lod[v["nome"]] = k
        ent_ext, str_ext = estensioni(est, config.LOD_DIST_PANORAMA)
        save_asset(AssetMapData(
            name=nome_lod, parent_name="", flags=MapFlags.IS_PARENT, content_flags=MapContentFlags.HAS_ENTITIES_LOD,
            streaming_extents=str_ext, entities_extents=ent_ext, entities=ents, description=descrizione(nome_lod),
        ), targets, cartella, nome_lod)

    gruppi = {}
    for v in voci:
        g = (v["i"] // config.BLOCCHI_PER_YMAP, v["j"] // config.BLOCCHI_PER_YMAP)
        gruppi.setdefault(g, []).append(v)
    for (gi, gj), elenco in gruppi.items():
        nome = f"{config.PREFISSO}_hd_{gi:02d}_{gj:02d}"
        ents, est = [], []
        for v in elenco:
            if usa_lod:
                ents.append(entita(v["nome"], v["pos"], config.LOD_DIST_BLOCCO, EntityLodLevel.HD,
                                   ombre | EntityFlags.LOD_IN_PARENT_MAP, genitore=indice_lod[v["nome"]]))
            else:
                ents.append(entita(v["nome"], v["pos"], config.LOD_DIST_BLOCCO, EntityLodLevel.ORPHANHD, ombre))
            est.append((v["pos"] + v["min"], v["pos"] + v["max"]))
        ent_ext, str_ext = estensioni(est, config.LOD_DIST_BLOCCO)
        save_asset(AssetMapData(
            name=nome, parent_name=nome_lod if usa_lod else "", flags=MapFlags(0),
            content_flags=MapContentFlags.HAS_ENTITIES_HD, streaming_extents=str_ext, entities_extents=ent_ext,
            entities=ents, description=descrizione(nome),
        ), targets, cartella, nome)
    print(f"{len(gruppi)} ymap HD" + (" + 1 ymap LOD" if usa_lod else ""))


# ---------------------------------------------------------------------------
# Risorsa FiveM
# ---------------------------------------------------------------------------
def lua_stringa(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def scrivi_risorsa(risorsa, indice, nativo):
    modello = config.RADICE / "fivem"
    risorsa.mkdir(parents=True, exist_ok=True)
    for f in ("fxmanifest.lua", "client.lua", "config.lua"):
        destinazione = risorsa / f
        if f == "config.lua" and destinazione.exists():
            continue  # non sovrascrivere le impostazioni dell'utente
        shutil.copy2(modello / f, destinazione)
    # Mappa web 3D da usare in gioco (NUI)
    if (risorsa / "html").exists():
        shutil.rmtree(risorsa / "html")
    shutil.copytree(config.RADICE / "html", risorsa / "html")

    righe = ["-- Generato da pipeline/3_costruisci_in_blender.py: non modificare a mano", "Luoghi = {"]
    for l in indice["luoghi"]:
        x, y, z = l["gta"]
        righe.append(f"    {{ id = {lua_stringa(l['id'])}, nome = {lua_stringa(l['nome'])}, "
                     f"cat = {lua_stringa(l['cat'])}, coord = vector3({x:.2f}, {y:.2f}, {z:.2f}) }},")
    righe.append("}")
    p = indice["proiezione"]
    og = indice["origine_gta"]
    righe.append(f"Proiezione = {{ lon0 = {p['lon0']:.7f}, lat0 = {p['lat0']:.7f}, kx = {p['kx']:.4f}, "
                 f"ky = {p['ky']:.4f}, ox = {og[0]:.2f}, oy = {og[1]:.2f} }}")
    righe.append(f"ZonaNapoli = {lua_stringa(indice['zona'])}")
    (risorsa / "luoghi.lua").write_text("\n".join(righe) + "\n", encoding="utf-8")

    if not nativo:
        (risorsa / "stream").mkdir(exist_ok=True)
        (risorsa / "stream" / "LEGGIMI.txt").write_text(
            "Metti qui i file binari (.ydr .ybn .ytyp .ymap .ytd) convertiti con CodeWalker\n"
            "dalla cartella xml_codewalker. Vedi README del progetto.\n", encoding="utf-8")
    print(f"Risorsa FiveM: {risorsa}")


if __name__ == "__main__":
    main()
