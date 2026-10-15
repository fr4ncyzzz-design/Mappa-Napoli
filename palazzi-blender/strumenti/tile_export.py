"""Divide tutto il comune in tile da 1 km x 1 km e scrive un JSON per tile (stesso formato di zona_export.py).

Uso:
    python strumenti/tile_export.py dati/napoli.osm.pbf strumenti/tiles tile [--solo napoli_r05_c08,napoli_r05_c07]

Regole per far combaciare le tile senza buchi né sovrapposizioni:
- bordi delle tile a x, y = 504 + k*1000 m dall'origine (Plebiscito): Piazza del Plebiscito cade al centro di una tile;
- un edificio appartiene alla tile in cui cade il suo punto rappresentativo (come zona_export.py);
- il terreno sta su un'unica griglia globale da 8 m; le regole terra/mare (urbano >= 1 m, mare a -3 m) si calcolano
  una volta sola con TUTTI gli edifici e le strade, così i vertici di bordo sono identici nelle tile vicine;
- strade e aree (verde, piazze) vengono tagliate esattamente sul bordo della tile;
- i ponti portano con sé la quota iniziale/finale dell'intero ponte, così la rampa continua da una tile all'altra.
"""
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.polygon import orient

import zona_export as zx

TILE = 1000.0
OFFSET = 504.0         # multiplo di 8 (griglia del terreno) e di 40 (griglia LOD): 504 = 63*8, e 1000 = 25*40
SAMPLE_MARGIN = 64.0   # griglia extra attorno alla tile, solo per leggere le quote (8 celle)
STEP = zx.STEP
T0 = time.time()


def log(msg):
    print(f"[{time.time() - T0:6.1f}s] {msg}", flush=True)


def tile_name(r, c):
    return f"napoli_r{r:02d}_c{c:02d}"


def urban_and_sea(h, x0, y0, nx, ny, buildings, roads):
    """Stesse regole di build_terrain()/urban_mask() di napoli_palazzi.py, ma sulla griglia globale."""
    hit = np.zeros((ny, nx), dtype=bool)

    def mark(x, y):
        i, j = round((x - x0) / STEP), round((y - y0) / STEP)
        hit[max(j - 2, 0):max(j + 3, 0), max(i - 2, 0):max(i + 3, 0)] = True

    for b in buildings:
        for ring in b["rings"]:
            for x, y in ring:
                mark(x, y)
    for r in roads:
        pts = r["pts"]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            n = max(1, math.ceil(math.hypot(bx - ax, by - ay) / STEP))
            for s in range(n + 1):
                t = s / n
                mark(ax + (bx - ax) * t, ay + (by - ay) * t)
    out = np.where(hit, np.maximum(h, 1.0), np.where(h <= 0.6, -3.0, h))
    return out, hit


def sample(h, x0, y0, nx, ny, x, y):
    """Interpolazione bilineare identica a Terrain.__call__ di napoli_palazzi.py."""
    gx = min(max((x - x0) / STEP, 0), nx - 1.001)
    gy = min(max((y - y0) / STEP, 0), ny - 1.001)
    ix, iy = int(gx), int(gy)
    fx, fy = gx - ix, gy - iy
    return float(h[iy, ix] * (1 - fx) * (1 - fy) + h[iy, ix + 1] * fx * (1 - fy)
                 + h[iy + 1, ix] * (1 - fx) * fy + h[iy + 1, ix + 1] * fx * fy)


def parts(geom):
    if geom.is_empty:
        return []
    if hasattr(geom, "geoms"):
        out = []
        for g in geom.geoms:
            out += parts(g)
        return out
    return [geom]


def main():
    src, tiles_dir, out_dir = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    only = None
    if "--solo" in sys.argv:
        only = set(sys.argv[sys.argv.index("--solo") + 1].split(","))
    zx.tiles_dir = tiles_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    everything = (-90.0, -180.0, 90.0, 180.0)
    raw_buildings, roads, areas, domes = zx.read_osm(src, everything, margin=0.0)
    log(f"OSM letto: {len(raw_buildings)} edifici grezzi, {len(roads)} strade, {len(areas)} aree, {len(domes)} cupole")
    polys = zx.make_polys(raw_buildings)
    buildings = zx.make_buildings(polys, lambda x, y: True)
    log(f"{len(buildings)} edifici con muri classificati")

    xs = [p[0] for _, p in buildings]
    ys = [p[1] for _, p in buildings]
    xmin = OFFSET + TILE * math.floor((min(xs) - OFFSET) / TILE)
    xmax = OFFSET + TILE * math.ceil((max(xs) - OFFSET) / TILE)
    ymin = OFFSET + TILE * math.floor((min(ys) - OFFSET) / TILE)
    ymax = OFFSET + TILE * math.ceil((max(ys) - OFFSET) / TILE)
    ncols = int(round((xmax - xmin) / TILE))
    nrows = int(round((ymax - ymin) / TILE))
    log(f"griglia {nrows} righe x {ncols} colonne ({(xmax - xmin) / 1000:.0f} x {(ymax - ymin) / 1000:.0f} km)")

    # Griglia globale del terreno (con margine per le letture ai bordi)
    gx0, gy0 = xmin - SAMPLE_MARGIN, ymin - SAMPLE_MARGIN
    gnx = int(round((xmax - xmin + 2 * SAMPLE_MARGIN) / STEP)) + 1
    gny = int(round((ymax - ymin + 2 * SAMPLE_MARGIN) / STEP)) + 1
    h = np.empty((gny, gnx))
    for j in range(gny):
        y = gy0 + j * STEP
        lat = zx.LAT0 + y / zx.KY
        for i in range(gnx):
            h[j, i] = round(float(zx.elev(zx.LON0 + (gx0 + i * STEP) / zx.KX, lat)), 2)
    log(f"rilievo globale {gnx}x{gny} punti")
    all_b = [b for b, _ in buildings]
    h, urban = urban_and_sea(h, gx0, gy0, gnx, gny, all_b, roads)
    log(f"terra/mare: {int(urban.sum())} celle urbane, {int((h <= -3.0).sum())} celle di mare")

    # Assegnazione per tile (righe contate da nord)
    per_tile = {}
    for b, (x, y) in buildings:
        c = int(math.floor((x - xmin) / TILE))
        r = nrows - 1 - int(math.floor((y - ymin) / TILE))
        per_tile.setdefault((r, c), []).append(b)

    index = []
    for (r, c), bs in sorted(per_tile.items()):
        name = tile_name(r, c)
        if only and name not in only:
            continue
        x0 = xmin + c * TILE
        y0 = ymin + (nrows - 1 - r) * TILE
        x1, y1 = x0 + TILE, y0 + TILE
        rect = box(x0, y0, x1, y1)

        # Strade tagliate sul bordo
        t_roads = []
        for rd in roads:
            pts = rd["pts"]
            if len(pts) < 2:
                continue
            xs_r = [p[0] for p in pts]
            ys_r = [p[1] for p in pts]
            if max(xs_r) < x0 or min(xs_r) > x1 or max(ys_r) < y0 or min(ys_r) > y1:
                continue
            line = LineString(pts)
            if line.length < 0.05:
                continue
            pieces = [p for p in parts(line.intersection(rect)) if p.geom_type == "LineString" and p.length > 0.05]
            for p in pieces:
                rec = dict(rd)
                rec["pts"] = [(round(x, 2), round(y, 2)) for x, y in p.coords]
                if rd["bridge"]:
                    g0 = sample(h, gx0, gy0, gnx, gny, *pts[0])
                    g1 = sample(h, gx0, gy0, gnx, gny, *pts[-1])
                    rec["span"] = [round(g0, 3), round(g1, 3), round(line.project(Point(p.coords[0])), 3),
                                   round(line.length, 3)]
                t_roads.append(rec)

        # Aree tagliate sul bordo
        t_areas = []
        for a in areas:
            rings = a["rings"]
            xs_a = [p[0] for p in rings[0]]
            ys_a = [p[1] for p in rings[0]]
            if max(xs_a) < x0 or min(xs_a) > x1 or max(ys_a) < y0 or min(ys_a) > y1:
                continue
            poly = Polygon(rings[0], rings[1:])
            for p in parts(poly.intersection(rect)):
                if p.geom_type != "Polygon" or p.area < 0.5:
                    continue
                p = orient(p, 1.0)
                t_areas.append({
                    "kind": a["kind"],
                    "rings": [[(round(x, 2), round(y, 2)) for x, y in list(p.exterior.coords)[:-1]]]
                    + [[(round(x, 2), round(y, 2)) for x, y in list(ri.coords)[:-1]] for ri in p.interiors],
                })

        t_domes = [d for d in domes if x0 <= d["c"][0] < x1 and y0 <= d["c"][1] < y1]

        i0 = int(round((x0 - gx0) / STEP))
        j0 = int(round((y0 - gy0) / STEP))
        n = int(round(TILE / STEP)) + 1
        m = int(round(SAMPLE_MARGIN / STEP))
        core = h[j0:j0 + n, i0:i0 + n]
        samp = h[j0 - m:j0 + n + m, i0 - m:i0 + n + m]
        data = {
            "origin": [zx.LON0, zx.LAT0],
            "tile": {"name": name, "r": r, "c": c, "x0": x0, "y0": y0, "x1": x1, "y1": y1},
            "terrain": {"x0": x0, "y0": y0, "step": STEP, "nx": n, "ny": n,
                        "h": [round(float(v), 2) for v in core.ravel()], "final": True},
            "terrain_sample": {"x0": x0 - SAMPLE_MARGIN, "y0": y0 - SAMPLE_MARGIN, "step": STEP,
                               "nx": n + 2 * m, "ny": n + 2 * m, "h": [round(float(v), 2) for v in samp.ravel()]},
            "buildings": bs,
            "roads": t_roads,
            "areas": t_areas,
            "domes": t_domes,
        }
        path = out_dir / f"{name}.json"
        path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        index.append({"name": name, "r": r, "c": c, "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                      "buildings": len(bs), "roads": len(t_roads), "areas": len(t_areas), "domes": len(t_domes),
                      "zmin": float(core.min()), "zmax": float(core.max())})
        log(f"{name}: {len(bs)} edifici, {len(t_roads)} strade, {len(t_areas)} aree")

    if not only:
        (out_dir / "indice_tile.json").write_text(json.dumps({
            "tile_size": TILE, "offset": OFFSET, "rows": nrows, "cols": ncols,
            "xmin": xmin, "xmax": xmax, "ymin": ymin, "ymax": ymax, "tiles": index,
            "skipped_empty": nrows * ncols - len(index),
        }, indent=1), encoding="utf-8")
    log(f"fatto: {len(index)} tile con edifici (vuote saltate: {nrows * ncols - len(per_tile)})")


if __name__ == "__main__":
    main()
