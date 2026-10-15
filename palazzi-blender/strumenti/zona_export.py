import json
import math
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import osmium
import shapely
from PIL import Image
from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.polygon import orient

src, tiles_dir, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
S, W, N, E = (float(v) for v in sys.argv[4:8]) if len(sys.argv) >= 8 else (40.8275, 14.2380, 40.8470, 14.2545)
LAT0, LON0 = 40.8359, 14.2483
R = 6378137.0
KX = R * math.radians(1) * math.cos(math.radians(LAT0))
KY = R * math.radians(1)
MARGIN = 0.0012


def proj(lon, lat):
    return round((lon - LON0) * KX, 2), round((lat - LAT0) * KY, 2)


Z = 13
NT = 2 ** Z
_tiles = {}


def tile(x, y):
    if (x, y) not in _tiles:
        f = tiles_dir / f"{Z}_{x}_{y}.png"
        if not f.exists():
            url = f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{Z}/{x}/{y}.png"
            curl = "curl.exe" if sys.platform == "win32" else "curl"
            subprocess.run([curl, "-sS", "--fail", "-o", str(f), url], check=True)
        px = np.asarray(Image.open(f).convert("RGB"), dtype=np.float64)
        _tiles[(x, y)] = px[..., 0] * 256 + px[..., 1] + px[..., 2] / 256 - 32768
    return _tiles[(x, y)]


def elev(lon, lat):
    fx = (lon + 180) / 360 * NT * 256 - 0.5
    fy = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * NT * 256 - 0.5
    ix, iy = math.floor(fx), math.floor(fy)
    ax, ay = fx - ix, fy - iy

    def px(gx, gy):
        return tile(gx // 256, gy // 256)[gy % 256, gx % 256]

    return (px(ix, iy) * (1 - ax) * (1 - ay) + px(ix + 1, iy) * ax * (1 - ay)
            + px(ix, iy + 1) * (1 - ax) * ay + px(ix + 1, iy + 1) * ax * ay)


def num(v):
    if not v:
        return None
    m = re.match(r"\s*([\d.]+)", v.replace(",", "."))
    try:
        return float(m.group(1)) if m else None
    except ValueError:
        return None


def ring_ll(nodes):
    pts = [(n.lon, n.lat) for n in nodes]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    return pts


def in_zone(lon, lat, m=0.0):
    return S - m <= lat <= N + m and W - m <= lon <= E + m


ROAD_W = {
    "primary": 12, "primary_link": 9, "secondary": 10, "secondary_link": 8, "tertiary": 8, "tertiary_link": 7,
    "residential": 6, "unclassified": 6, "living_street": 5, "service": 4, "pedestrian": 6,
    "footway": 2.5, "steps": 2.5, "path": 2, "cycleway": 2.5, "track": 3,
}
ROAD_KIND = {"primary": "asfalto", "primary_link": "asfalto", "secondary": "asfalto", "secondary_link": "asfalto",
             "tertiary": "asfalto", "tertiary_link": "asfalto", "service": "asfalto"}

raw_buildings, roads, areas, domes = [], [], [], []
for o in osmium.FileProcessor(src).with_locations().with_areas():
    try:
        if o.is_way():
            hw = o.tags.get("highway")
            if hw in ROAD_W and o.tags.get("tunnel") in (None, "no") and o.tags.get("area") != "yes":
                pts = ring_ll(o.nodes) if o.is_closed() else [(n.lon, n.lat) for n in o.nodes]
                if o.is_closed():
                    pts.append(pts[0])
                if any(in_zone(lo, la, MARGIN) for lo, la in pts):
                    width = num(o.tags.get("width")) or ROAD_W[hw]
                    roads.append({
                        "pts": [proj(lo, la) for lo, la in pts],
                        "w": min(max(width, 1.5), 30),
                        "kind": ROAD_KIND.get(hw, "basoli" if hw in ("residential", "unclassified", "living_street", "pedestrian") else "pietra"),
                        "bridge": o.tags.get("bridge") not in (None, "no"),
                        "name": o.tags.get("name", ""),
                    })
        elif o.is_area():
            t = o.tags
            outers = list(o.outer_rings())
            if not outers:
                continue
            first = ring_ll(outers[0])
            clon = sum(p[0] for p in first) / len(first)
            clat = sum(p[1] for p in first) / len(first)
            if not in_zone(clon, clat, MARGIN):
                continue
            if "building:part" in t and t.get("roof:shape") in ("dome", "onion") and in_zone(clon, clat):
                poly = Polygon([proj(*p) for p in first])
                if poly.is_valid and poly.area > 10:
                    h = num(t.get("height"))
                    r = math.sqrt(poly.area / math.pi)
                    base = num(t.get("min_height"))
                    if base is None:
                        base = (h - (num(t.get("roof:height")) or r)) if h else 15.0
                    c = poly.centroid
                    domes.append({"c": [round(c.x, 2), round(c.y, 2)], "r": round(r, 2), "base": round(base, 2),
                                  "ground": round(elev(clon, clat), 2), "name": t.get("name", "")})
            elif t.get("building") not in (None, "no") and "building:part" not in t:
                for outer in outers:
                    rings = [ring_ll(outer)] + [ring_ll(i) for i in o.inner_rings(outer)]
                    if len(rings[0]) >= 3:
                        raw_buildings.append((rings, dict(t), o.id))
            else:
                kind = None
                if t.get("highway") == "pedestrian" or "area:highway" in t or t.get("place") == "square" \
                        or t.get("amenity") == "parking" or t.get("highway") == "footway":
                    kind = "piazza"
                elif t.get("leisure") in ("park", "garden", "playground") or t.get("landuse") in ("grass", "meadow", "village_green", "forest") \
                        or t.get("natural") in ("wood", "scrub", "grassland"):
                    kind = "verde"
                if kind:
                    for outer in outers:
                        rings = [ring_ll(outer)] + [ring_ll(i) for i in o.inner_rings(outer)]
                        poly = Polygon([proj(*p) for p in rings[0]], [[proj(*p) for p in r] for r in rings[1:] if len(r) >= 3])
                        if poly.is_valid and poly.area > 20:
                            poly = orient(poly, 1.0)
                            areas.append({
                                "kind": kind,
                                "rings": [list(poly.exterior.coords)[:-1]] + [list(r.coords)[:-1] for r in poly.interiors],
                            })
    except osmium.InvalidLocationError:
        continue

polys = []
for rings, tags, oid in raw_buildings:
    try:
        poly = Polygon([proj(*p) for p in rings[0]], [[proj(*p) for p in r] for r in rings[1:] if len(r) >= 3])
    except ValueError:
        continue
    if not poly.is_valid:
        poly = poly.buffer(0)
        if poly.geom_type != "Polygon":
            continue
    if poly.area < 8:
        continue
    polys.append((orient(poly.simplify(0.15), 1.0), tags, oid))

tree = shapely.STRtree([p for p, _, _ in polys])
TYPE = {"church": "chiesa", "basilica": "chiesa", "cathedral": "chiesa", "chapel": "chiesa",
        "castle": "castello", "fortress": "castello", "roof": "tettoia", "train_station": "stazione"}


def levels_for(tags, oid):
    lv = num(tags.get("building:levels"))
    h = num(tags.get("height"))
    if lv:
        lv = int(round(min(max(lv, 1), 30)))
    elif h:
        lv = max(1, int(round(h / 3.9)))
    else:
        lv = [4, 5, 5, 6, 6, 5][oid % 6]
    return lv, h


buildings = []
for idx, (poly, tags, oid) in enumerate(polys):
    c = poly.representative_point()
    lon_c, lat_c = LON0 + c.x / KX, LAT0 + c.y / KY
    if not in_zone(lon_c, lat_c):
        continue
    rings = [list(poly.exterior.coords)[:-1]] + [list(r.coords)[:-1] for r in poly.interiors]
    flags = []
    for ri, ring in enumerate(rings):
        rf = []
        for k in range(len(ring)):
            (x0, y0), (x1, y1) = ring[k], ring[(k + 1) % len(ring)]
            L = math.hypot(x1 - x0, y1 - y0)
            if L < 0.01:
                rf.append(0)
                continue
            nx, ny = (y1 - y0) / L, -(x1 - x0) / L
            probe = Point((x0 + x1) / 2 + nx * 1.2, (y0 + y1) / 2 + ny * 1.2)
            touching = any(j != idx and polys[j][0].contains(probe) for j in tree.query(probe))
            if touching:
                rf.append(0)
            elif ri > 0:
                rf.append(2)
            else:
                rf.append(1)
        flags.append(rf)
    ground = [elev(LON0 + x / KX, LAT0 + y / KY) for x, y in rings[0]]
    lv, h = levels_for(tags, oid)
    btag = tags.get("building")
    kind = TYPE.get(btag) or TYPE.get(tags.get("historic", ""), None) or ("palazzo" if btag != "roof" else "tettoia")
    buildings.append({
        "id": oid,
        "rings": [[(round(x, 2), round(y, 2)) for x, y in r] for r in rings],
        "flags": flags,
        "levels": lv,
        "height": h,
        "roof_levels": num(tags.get("roof:levels")) or 0,
        "roof_shape": tags.get("roof:shape", ""),
        "kind": kind,
        "colour": tags.get("building:colour", ""),
        "name": tags.get("name", ""),
        "gmin": round(min(ground), 2),
        "gavg": round(sum(ground) / len(ground), 2),
    })

x0, y0 = proj(W - MARGIN, S - MARGIN)
x1, y1 = proj(E + MARGIN, N + MARGIN)
STEP = 8.0
gx = int((x1 - x0) // STEP) + 1
gy = int((y1 - y0) // STEP) + 1
grid = []
for j in range(gy):
    y = y0 + j * STEP
    for i in range(gx):
        x = x0 + i * STEP
        grid.append(round(float(elev(LON0 + x / KX, LAT0 + y / KY)), 2))

data = {
    "origin": [LON0, LAT0],
    "terrain": {"x0": x0, "y0": y0, "step": STEP, "nx": gx, "ny": gy, "h": grid},
    "buildings": buildings,
    "roads": roads,
    "areas": areas,
    "domes": domes,
}
out.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
kinds = {}
for b in buildings:
    kinds[b["kind"]] = kinds.get(b["kind"], 0) + 1
ef = [f for b in buildings for r in b["flags"] for f in r]
print(f"edifici {len(buildings)} {kinds}, strade {len(roads)}, aree {len(areas)}, cupole {len(domes)}, griglia {gx}x{gy}")
print("cupole:", [(d["name"], d["r"], d["base"]) for d in domes])
print(f"muri: strada {ef.count(1)}, cortile {ef.count(2)}, attaccati {ef.count(0)}")
print(f"quota min/max {min(grid):.1f}/{max(grid):.1f}, file {out.stat().st_size / 1e6:.1f} MB")
