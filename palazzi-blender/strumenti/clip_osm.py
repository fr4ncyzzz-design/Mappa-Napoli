import sys
import time

import numpy as np
import osmium
import shapely
import shapely.wkb

src, dst, city = sys.argv[1], sys.argv[2], sys.argv[3]
t0 = time.time()


def log(msg):
    print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)


wkb = osmium.geom.WKBFactory()
boundary = None
for o in osmium.FileProcessor(src).with_areas(osmium.filter.KeyFilter("boundary")):
    if o.is_area() and not o.from_way() and o.tags.get("boundary") == "administrative" \
            and o.tags.get("admin_level") == "8" and o.tags.get("name") == city:
        boundary = shapely.wkb.loads(wkb.create_multipolygon(o), hex=True)
        log(f"confine relation {o.orig_id()}: area {boundary.area:.5f} deg2")
        break
if boundary is None:
    sys.exit(f"confine di {city} non trovato")

shapely.prepare(boundary)
minx, miny, maxx, maxy = boundary.bounds

ids, xs, ys = [], [], []
for n in osmium.FileProcessor(src, osmium.osm.NODE):
    loc = n.location
    if loc.valid() and minx <= loc.lon <= maxx and miny <= loc.lat <= maxy:
        ids.append(n.id)
        xs.append(loc.lon)
        ys.append(loc.lat)
inside = np.asarray(ids)[shapely.intersects_xy(boundary, np.asarray(xs), np.asarray(ys))]
inside_nodes = set(inside.tolist())
log(f"nodi dentro il confine: {len(inside_nodes)}")

keep_ways, need_nodes = set(), set(inside_nodes)
for w in osmium.FileProcessor(src, osmium.osm.WAY):
    refs = [r.ref for r in w.nodes]
    if any(r in inside_nodes for r in refs):
        keep_ways.add(w.id)
        need_nodes.update(refs)
log(f"way: {len(keep_ways)}, nodi totali: {len(need_nodes)}")

keep_rels = set()
for r in osmium.FileProcessor(src, osmium.osm.RELATION):
    for m in r.members:
        if (m.type == "n" and m.ref in inside_nodes) or (m.type == "w" and m.ref in keep_ways):
            keep_rels.add(r.id)
            break
parents = set()
for r in osmium.FileProcessor(src, osmium.osm.RELATION):
    if r.id not in keep_rels and any(m.type == "r" and m.ref in keep_rels for m in r.members):
        parents.add(r.id)
keep_rels |= parents
log(f"relazioni: {len(keep_rels)}")

header = osmium.io.Header()
header.add_box(osmium.osm.Box(osmium.osm.Location(minx, miny), osmium.osm.Location(maxx, maxy)))
header.set("generator", "pyosmium clip")
writer = osmium.SimpleWriter(osmium.io.File(dst, "osm"), 0, header)
try:
    for o in osmium.FileProcessor(src):
        if (o.is_node() and o.id in need_nodes) or (o.is_way() and o.id in keep_ways) \
                or (o.is_relation() and o.id in keep_rels):
            writer.add(o)
finally:
    writer.close()
log(f"scritto {dst}")
