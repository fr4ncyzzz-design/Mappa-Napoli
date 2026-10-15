"""Passo 2: trasforma i dati OSM + rilievo in blocchi pronti per Blender.

Per ogni blocco (LATO_BLOCCO x LATO_BLOCCO metri) produce un file .npz con:
  - griglia del terreno (quote) e materiale di ogni cella (asfalto, verde, sabbia, fondale)
  - edifici: anelli del perimetro, triangoli del tetto, quota base/cima, stile facciata
  - strade: polilinee 3D adagiate sul terreno (o sopraelevate se ponti/viadotti)
  - versione semplificata degli edifici per il LOD lontano

Uso:
    python pipeline/2_prepara_dati.py --zona prova

Richiede: numpy, shapely>=2, mapbox-earcut
"""

import argparse
import json
import math
import re
import shutil
import zlib

import numpy as np
import shapely
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Point, Polygon, box
from shapely.ops import linemerge, polygonize, unary_union

import config

try:
    import mapbox_earcut as earcut
except ImportError:  # pragma: no cover
    raise SystemExit("Manca mapbox-earcut: pip install -r pipeline/requirements.txt")

# Materiali delle celle del terreno
MAT_URBANO, MAT_VERDE, MAT_SABBIA, MAT_FONDALE, MAT_ROCCIA = 0, 1, 2, 3, 4
# Stili facciata (devono corrispondere alle texture generate in Blender)
STILI = ["gialla", "rossa", "rosa", "bianca", "ocra", "grigia", "moderna", "chiesa"]
COLORI_STILE = {
    "gialla": (232, 190, 110), "rossa": (170, 70, 55), "rosa": (225, 160, 150),
    "bianca": (235, 230, 220), "ocra": (205, 150, 80), "grigia": (160, 160, 160),
}
TIPO_AUTO, TIPO_PEDONALE = 0, 1


# ---------------------------------------------------------------------------
# Proiezione: equirettangolare locale centrata sulla zona (errore < 0,1% su 20 km)
# ---------------------------------------------------------------------------
class Proiezione:
    def __init__(self, bbox):
        self.lon0 = (bbox[0] + bbox[2]) / 2
        self.lat0 = (bbox[1] + bbox[3]) / 2
        self.kx = math.cos(math.radians(self.lat0)) * 111320.0
        self.ky = 110574.0

    def xy(self, lon, lat):
        return (np.asarray(lon) - self.lon0) * self.kx, (np.asarray(lat) - self.lat0) * self.ky

    def lonlat(self, x, y):
        return np.asarray(x) / self.kx + self.lon0, np.asarray(y) / self.ky + self.lat0


class Rilievo:
    """Campionamento bilineare del DEM terrarium (Web Mercator)."""

    def __init__(self, percorso):
        d = np.load(percorso)
        self.q = d["quota"].astype(np.float32)
        self.z = int(d["zoom"])
        self.tx0 = int(d["tx0"])
        self.ty0 = int(d["ty0"])

    def campiona(self, lon, lat):
        n = 2 ** self.z
        lon = np.asarray(lon, dtype=np.float64)
        lat = np.asarray(lat, dtype=np.float64)
        px = ((lon + 180.0) / 360.0 * n - self.tx0) * 256.0 - 0.5
        py = ((1.0 - np.arcsinh(np.tan(np.radians(lat))) / math.pi) / 2.0 * n - self.ty0) * 256.0 - 0.5
        h, w = self.q.shape
        px = np.clip(px, 0, w - 1.001)
        py = np.clip(py, 0, h - 1.001)
        x0 = np.floor(px).astype(int)
        y0 = np.floor(py).astype(int)
        fx = px - x0
        fy = py - y0
        q = self.q
        return ((q[y0, x0] * (1 - fx) + q[y0, x0 + 1] * fx) * (1 - fy) +
                (q[y0 + 1, x0] * (1 - fx) + q[y0 + 1, x0 + 1] * fx) * fy)


# ---------------------------------------------------------------------------
# Lettura OSM
# ---------------------------------------------------------------------------
def coord_way(el, proj):
    g = el.get("geometry") or []
    if len(g) < 2:
        return None
    lon = np.array([p["lon"] for p in g])
    lat = np.array([p["lat"] for p in g])
    x, y = proj.xy(lon, lat)
    return np.column_stack([x, y])


def unisci_anelli(segmenti):
    """Unisce i pezzi di way di una relazione multipolygon in anelli chiusi."""
    segmenti = [list(map(tuple, s)) for s in segmenti if s is not None and len(s) >= 2]
    anelli = []
    while segmenti:
        anello = segmenti.pop(0)
        cambiato = True
        while anello[0] != anello[-1] and cambiato:
            cambiato = False
            for i, s in enumerate(segmenti):
                if s[0] == anello[-1]:
                    anello += s[1:]
                elif s[-1] == anello[-1]:
                    anello += s[::-1][1:]
                elif s[-1] == anello[0]:
                    anello = s[:-1] + anello
                elif s[0] == anello[0]:
                    anello = s[::-1][:-1] + anello
                else:
                    continue
                segmenti.pop(i)
                cambiato = True
                break
        if len(anello) >= 4:
            anelli.append(anello)
    return anelli


def poligono_da_elemento(el, proj):
    if el["type"] == "way":
        c = coord_way(el, proj)
        if c is None or len(c) < 4:
            return None
        poly = Polygon(c)
    else:
        esterni, interni = [], []
        for m in el.get("members", []):
            if m.get("type") != "way" or not m.get("geometry"):
                continue
            c = coord_way(m, proj)
            (interni if m.get("role") == "inner" else esterni).append(c)
        anelli_est = [Polygon(a) for a in unisci_anelli(esterni)]
        anelli_int = [Polygon(a) for a in unisci_anelli(interni)]
        if not anelli_est:
            return None
        poly = unary_union([shapely.make_valid(p) for p in anelli_est])
        if anelli_int:
            poly = poly.difference(unary_union([shapely.make_valid(p) for p in anelli_int]))
    if not poly.is_valid:
        poly = shapely.make_valid(poly)
    return poly


def poligoni_semplici(geom):
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    if hasattr(geom, "geoms"):
        out = []
        for g in geom.geoms:
            out += poligoni_semplici(g)
        return out
    return []


def numero(valore):
    if valore is None:
        return None
    m = re.match(r"\s*(-?\d+(?:[.,]\d+)?)", str(valore))
    return float(m.group(1).replace(",", ".")) if m else None


def hash_id(x):
    return zlib.crc32(str(x).encode()) & 0xFFFFFFFF


def altezze_edificio(tag, ident):
    tipo = tag.get("building") or tag.get("building:part") or "yes"
    h = numero(tag.get("height"))
    livelli = numero(tag.get("building:levels"))
    if h is None and livelli is not None:
        h = livelli * config.ALTEZZA_PIANO + (1.0 if livelli > 0 else 0.0)
    if h is None:
        r = (hash_id(ident) % 1000) / 1000.0
        if tipo in ("church", "cathedral", "basilica", "chapel"):
            h = 22 + 10 * r
        elif tipo in ("garage", "garages", "shed", "hut", "kiosk", "carport", "cabin", "toilets"):
            h = 3 + 1.5 * r
        elif tipo == "roof":
            h = 4.5
        elif tipo in ("house", "detached", "semidetached_house", "bungalow", "villa"):
            h = 7 + 4 * r
        elif tipo in ("industrial", "warehouse", "retail", "supermarket"):
            h = 8 + 5 * r
        else:
            # Il palazzo napoletano tipico: 4-7 piani
            h = 13 + 11 * r
    hmin = numero(tag.get("min_height"))
    if hmin is None:
        lmin = numero(tag.get("building:min_level"))
        hmin = lmin * config.ALTEZZA_PIANO if lmin else 0.0
    if tipo == "roof" and hmin == 0.0:
        hmin = 3.0
    h = max(h, hmin + 2.0, config.ALTEZZA_MINIMA if hmin == 0 else 0)
    return h, hmin, tipo


def stile_edificio(tag, ident, altezza, tipo):
    if tipo in ("church", "cathedral", "basilica", "chapel"):
        return STILI.index("chiesa")
    if altezza > 38:
        return STILI.index("moderna")
    colore = tag.get("building:colour") or tag.get("colour")
    if colore:
        rgb = colore_hex(colore)
        if rgb:
            migliore = min(COLORI_STILE, key=lambda k: sum((a - b) ** 2 for a, b in zip(rgb, COLORI_STILE[k])))
            return STILI.index(migliore)
    # Distribuzione tipica delle facciate napoletane
    scelta = ["gialla", "gialla", "ocra", "rossa", "rosa", "bianca", "gialla", "ocra", "grigia", "rosa"]
    return STILI.index(scelta[hash_id(ident) % len(scelta)])


NOMI_COLORI = {"yellow": (232, 190, 110), "red": (170, 70, 55), "pink": (225, 160, 150),
               "white": (235, 230, 220), "orange": (205, 150, 80), "grey": (160, 160, 160),
               "gray": (160, 160, 160), "beige": (225, 205, 165), "brown": (150, 100, 70)}


def colore_hex(c):
    c = c.strip().lower()
    if c in NOMI_COLORI:
        return NOMI_COLORI[c]
    m = re.fullmatch(r"#?([0-9a-f]{6})", c)
    if m:
        v = int(m.group(1), 16)
        return (v >> 16) & 255, (v >> 8) & 255, v & 255
    return None


# ---------------------------------------------------------------------------
# Costa: separa terra e mare usando le linee di costa OSM (terra a sinistra)
# ---------------------------------------------------------------------------
def calcola_terra(linee_costa, area, rilievo, proj):
    if not linee_costa:
        print("   nessuna linea di costa: uso solo il rilievo")
        return None
    # directed=True conserva il verso delle way (in OSM la terra sta a sinistra)
    unite = linemerge(MultiLineString(linee_costa), directed=True)
    unite = list(getattr(unite, "geoms", [unite]))
    # Le estremità che finiscono dentro l'area vanno prolungate fino al bordo,
    # altrimenti la costa non divide l'area in pezzi di terra e mare.
    estese = []
    for l in unite:
        c = np.asarray(l.coords)
        if len(c) >= 2:
            for estremo, vicino in ((0, 1), (-1, -2)):
                if area.contains(Point(c[estremo])):
                    d = c[estremo] - c[vicino]
                    d = d / max(np.hypot(*d), 1e-9)
                    c = np.insert(c, 0 if estremo == 0 else len(c), c[estremo] + d * 50000.0, axis=0)
        estese.append(LineString(c))
    linee = [l.intersection(area) for l in estese]
    linee = [l for l in linee if not l.is_empty]
    rete = unary_union([area.exterior] + linee)
    pezzi = list(polygonize(rete))
    terra = []
    costa = unary_union(linee)
    for p in pezzi:
        r = p.representative_point()
        lato = lato_costa(r, linee)
        if lato is None:
            lon, lat = proj.lonlat(r.x, r.y)
            lato = 1 if rilievo.campiona(lon, lat) > 0.5 else -1
        if lato > 0:
            terra.append(p)
    print(f"   costa: {len(pezzi)} pezzi, {len(terra)} di terra (distanza costa ~{costa.length / 1000:.1f} km)")
    return unary_union(terra) if terra else Polygon()


def lato_costa(punto, linee):
    migliore, dist = None, float("inf")
    for l in linee:
        for parte in getattr(l, "geoms", [l]):
            if parte.geom_type != "LineString":
                continue
            d = parte.distance(punto)
            if d < dist:
                dist, migliore = d, parte
    if migliore is None:
        return None
    s = migliore.project(punto)
    a = migliore.interpolate(max(0.0, s - 1.0))
    b = migliore.interpolate(min(migliore.length, s + 1.0))
    tx, ty = b.x - a.x, b.y - a.y
    p = migliore.interpolate(s)
    croce = tx * (punto.y - p.y) - ty * (punto.x - p.x)
    if abs(croce) < 1e-9:
        return None
    return 1 if croce > 0 else -1


# ---------------------------------------------------------------------------
# Griglia del terreno condivisa (stessa triangolazione usata in Blender)
# ---------------------------------------------------------------------------
class Terreno:
    def __init__(self, x0, y0, nx, ny, passo, z):
        self.x0, self.y0, self.nx, self.ny, self.passo, self.z = x0, y0, nx, ny, passo, z

    def quota(self, x, y):
        """Quota esatta sulla superficie triangolata (diagonale da (i,j) a (i+1,j+1))."""
        x = np.asarray(x, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        gx = np.clip((x - self.x0) / self.passo, 0, self.nx - 1e-6)
        gy = np.clip((y - self.y0) / self.passo, 0, self.ny - 1e-6)
        i = np.floor(gx).astype(int)
        j = np.floor(gy).astype(int)
        fx = gx - i
        fy = gy - j
        z = self.z
        z00, z10, z01, z11 = z[j, i], z[j, i + 1], z[j + 1, i], z[j + 1, i + 1]
        sotto = fx >= fy  # triangolo (00, 10, 11)
        return np.where(sotto,
                        z00 + fx * (z10 - z00) + fy * (z11 - z10),
                        z00 + fy * (z01 - z00) + fx * (z11 - z01))


def densifica(coords, passo):
    out = [coords[0]]
    for a, b in zip(coords[:-1], coords[1:]):
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(1, int(math.ceil(d / passo)))
        for k in range(1, n + 1):
            t = k / n
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return np.array(out)


def triangola(poly):
    """Restituisce (vertici, conteggi anelli, triangoli) per un poligono con buchi."""
    poly = shapely.geometry.polygon.orient(poly, 1.0)  # esterno antiorario, buchi orari
    anelli = [np.asarray(poly.exterior.coords)[:-1]] + [np.asarray(r.coords)[:-1] for r in poly.interiors]
    anelli = [a for a in anelli if len(a) >= 3]
    if not anelli:
        return None
    vert = np.concatenate(anelli).astype(np.float64)
    fine = np.cumsum([len(a) for a in anelli]).astype(np.uint32)
    tri = earcut.triangulate_float64(vert, fine).reshape(-1, 3)
    if len(tri) == 0:
        return None
    return vert, np.array([len(a) for a in anelli], dtype=np.int32), tri.astype(np.int32)


def leggi_luoghi():
    testo = (config.RADICE / "html" / "js" / "dati.js").read_text(encoding="utf-8")
    patt = re.compile(r"id: '([^']+)', nome: (['\"])(.*?)\2, cat: '(\w+)', coord: \[([\d.]+), ([\d.]+)\]")
    return [{"id": m.group(1), "nome": m.group(3).replace("\\'", "'"), "cat": m.group(4),
             "lon": float(m.group(5)), "lat": float(m.group(6))} for m in patt.finditer(testo)]


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zona", default="prova")
    args = ap.parse_args()
    zona = config.preset(args.zona)
    bbox = zona["bbox"]

    proj = Proiezione(bbox)
    rilievo = Rilievo(config.CARTELLA_DATI / f"dem_{args.zona}.npz")
    osm = json.loads((config.CARTELLA_DATI / f"osm_{args.zona}.json").read_text(encoding="utf-8"))["elements"]
    print(f"Zona '{args.zona}': {len(osm)} elementi OSM")

    # Estensione locale arrotondata ai blocchi
    xa, ya = proj.xy(bbox[0], bbox[1])
    xb, yb = proj.xy(bbox[2], bbox[3])
    L = config.LATO_BLOCCO
    nbx = int(math.ceil((xb - xa) / L))
    nby = int(math.ceil((yb - ya) / L))
    X0 = -nbx * L / 2
    Y0 = -nby * L / 2
    area = box(X0, Y0, X0 + nbx * L, Y0 + nby * L)
    print(f"   {nbx} x {nby} blocchi da {L:.0f} m ({nbx * L / 1000:.1f} x {nby * L / 1000:.1f} km)")

    # --- Classificazione degli elementi OSM
    costa, verdi, sabbie, edifici, parti, strade = [], [], [], [], [], []
    for el in osm:
        t = el.get("tags", {})
        if el["type"] == "way" and t.get("natural") == "coastline":
            c = coord_way(el, proj)
            if c is not None:
                costa.append(LineString(c))
        elif "building:part" in t:
            parti.append(el)
        elif "building" in t:
            edifici.append(el)
        elif "highway" in t and el["type"] == "way":
            strade.append(el)
        elif t.get("natural") in ("beach", "sand"):
            sabbie.append(el)
        elif any(k in t for k in ("leisure", "landuse", "natural")):
            verdi.append(el)

    # --- Terra / mare
    terra = calcola_terra(costa, area, rilievo, proj)

    # --- Terreno globale
    P = config.PASSO_TERRENO
    nx = int(round(nbx * L / P))
    ny = int(round(nby * L / P))
    gx = X0 + np.arange(nx + 1) * P
    gy = Y0 + np.arange(ny + 1) * P
    GX, GY = np.meshgrid(gx, gy)
    lon, lat = proj.lonlat(GX, GY)
    Z = rilievo.campiona(lon, lat).astype(np.float32)
    if terra is not None:
        a_terra = shapely.contains_xy(terra, GX, GY)
        vicino = shapely.contains_xy(terra.buffer(P * 0.75), GX, GY)
    else:
        a_terra = Z > 0.3
        vicino = a_terra
    # Sulla terra almeno 0,6 m; in mare almeno -2 m e poi più profondo allontanandosi
    Z = np.where(a_terra, np.maximum(Z, 0.6), np.minimum(Z, -2.0))
    Z = np.where(~a_terra & vicino, np.minimum(Z, -1.2), Z)
    terreno = Terreno(X0, Y0, nx, ny, P, Z)

    # Materiale per cella
    cx = (GX[:-1, :-1] + P / 2)
    cy = (GY[:-1, :-1] + P / 2)
    MAT = np.full(cx.shape, MAT_URBANO, dtype=np.uint8)
    pendenza = np.hypot(np.diff(Z, axis=1)[:-1, :], np.diff(Z, axis=0)[:, :-1]) / P
    MAT[pendenza > 0.9] = MAT_ROCCIA
    for lista, mat in ((verdi, MAT_VERDE), (sabbie, MAT_SABBIA)):
        geoms = [poligono_da_elemento(e, proj) for e in lista]
        geoms = [g for g in geoms if g is not None and not g.is_empty]
        if geoms:
            MAT[shapely.contains_xy(unary_union(geoms), cx, cy)] = mat
    centro_mare = (Z[:-1, :-1] + Z[1:, 1:] + Z[:-1, 1:] + Z[1:, :-1]) / 4 < 0
    MAT[centro_mare] = MAT_FONDALE
    print(f"   terreno {nx}x{ny} celle, quota {Z.min():.0f}..{Z.max():.0f} m")

    # --- Edifici
    poly_parti = []
    for el in parti:
        g = poligono_da_elemento(el, proj)
        if g is not None and not g.is_empty:
            poly_parti.append((el, g))
    albero_parti = shapely.STRtree([p.representative_point() for _, p in poly_parti]) if poly_parti else None

    voci = []
    for el, g in poly_parti:
        voci.append((el, g))
    for el in edifici:
        g = poligono_da_elemento(el, proj)
        if g is None or g.is_empty:
            continue
        # Se l'edificio è descritto con building:part, il perimetro si ignora (regola OSM Simple 3D)
        if albero_parti is not None and len(albero_parti.query(g, predicate="contains")) > 0:
            continue
        voci.append((el, g))

    blocchi = {}

    def blocco(x, y):
        i = int(min(nbx - 1, max(0, (x - X0) // L)))
        j = int(min(nby - 1, max(0, (y - Y0) // L)))
        k = (i, j)
        if k not in blocchi:
            blocchi[k] = {"ed": [], "lod": [], "st": []}
        return blocchi[k]

    n_ed = 0
    for el, g in voci:
        t = el.get("tags", {})
        ident = f"{el['type']}{el['id']}"
        h, hmin, tipo = altezze_edificio(t, ident)
        stile = stile_edificio(t, ident, h, tipo)
        for p in poligoni_semplici(g.intersection(area)):
            p = p.simplify(0.15)
            if p.is_empty or p.area < 6.0:
                continue
            tri = triangola(p)
            if tri is None:
                continue
            vert, conti, triangoli = tri
            zs = terreno.quota(vert[:, 0], vert[:, 1])
            suolo_min = float(zs.min())
            suolo_med = float(zs.mean())
            base = suolo_min - 0.8 if hmin == 0 else suolo_med + hmin
            cima = suolo_med + h
            c = p.centroid
            b = blocco(c.x, c.y)
            b["ed"].append((vert, conti, triangoli, base, cima, stile))
            n_ed += 1
            # LOD: perimetro semplificato senza cortili, solo edifici non minuscoli
            if p.area >= 40.0 and hmin == 0:
                q = Polygon(p.exterior).simplify(2.5)
                if isinstance(q, Polygon) and not q.is_empty and q.area > 30:
                    tq = triangola(q)
                    if tq is not None:
                        b["lod"].append((tq[0], tq[1], tq[2], base, cima, stile))
    print(f"   {n_ed} edifici")

    # --- Strade
    n_st = 0
    for el in strade:
        t = el["tags"]
        hw = t["highway"]
        if hw not in config.LARGHEZZA_STRADE or t.get("tunnel") in ("yes", "building_passage", "culvert"):
            continue
        if t.get("area") == "yes":
            continue
        c = coord_way(el, proj)
        if c is None:
            continue
        larg = numero(t.get("width")) or config.LARGHEZZA_STRADE[hw]
        larg = min(max(larg, 2.0), 30.0)
        tipo = TIPO_PEDONALE if hw in config.STRADE_PEDONALI else TIPO_AUTO
        pt = densifica(c, 3.0)
        if t.get("bridge") in ("yes", "viaduct"):
            # Ponte/viadotto: interpolazione lineare tra le quote agli estremi
            za = terreno.quota(pt[0, 0], pt[0, 1])
            zb = terreno.quota(pt[-1, 0], pt[-1, 1])
            d = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(pt, axis=0).T))])
            z = za + (zb - za) * (d / max(d[-1], 1e-6)) + 0.3
            z = np.maximum(z, terreno.quota(pt[:, 0], pt[:, 1]) + 0.3)
        else:
            z = terreno.quota(pt[:, 0], pt[:, 1]) + (0.12 if tipo == TIPO_AUTO else 0.16)
            z = np.maximum(z, 0.7)  # moli e banchine sopra il livello del mare
        dentro = (pt[:, 0] >= X0) & (pt[:, 0] <= X0 + nbx * L) & (pt[:, 1] >= Y0) & (pt[:, 1] <= Y0 + nby * L)
        # Spezza la polilinea per blocco (il punto di confine appartiene ad entrambi)
        ib = np.clip(((pt[:, 0] - X0) // L).astype(int), 0, nbx - 1)
        jb = np.clip(((pt[:, 1] - Y0) // L).astype(int), 0, nby - 1)
        inizio = 0
        for k in range(1, len(pt) + 1):
            fine_tratto = k == len(pt) or ib[k] != ib[inizio] or jb[k] != jb[inizio] or not dentro[k]
            if fine_tratto:
                fine = min(k + 1, len(pt))
                if fine - inizio >= 2 and dentro[inizio]:
                    seg = np.column_stack([pt[inizio:fine], z[inizio:fine]])
                    blocco(pt[inizio, 0], pt[inizio, 1])["st"].append((seg, larg, tipo))
                    n_st += 1
                inizio = k
    print(f"   {n_st} tratti di strada")

    # --- Scrittura dei blocchi
    cartella = config.CARTELLA_DATI / f"blocchi_{args.zona}"
    if cartella.exists():
        shutil.rmtree(cartella)
    cartella.mkdir(parents=True)
    passi = int(round(L / P))
    elenco = []
    for i in range(nbx):
        for j in range(nby):
            b = blocchi.get((i, j), {"ed": [], "lod": [], "st": []})
            zt = Z[j * passi:(j + 1) * passi + 1, i * passi:(i + 1) * passi + 1]
            mt = MAT[j * passi:(j + 1) * passi, i * passi:(i + 1) * passi]
            dati = {
                "origine": np.array([X0 + i * L, Y0 + j * L], dtype=np.float64),
                "terreno_z": zt.astype(np.float32),
                "terreno_mat": mt,
            }
            for chiave, lista in (("ed", b["ed"]), ("lod", b["lod"])):
                if lista:
                    dati[f"{chiave}_xy"] = np.concatenate([e[0] for e in lista]).astype(np.float64)
                    dati[f"{chiave}_anelli"] = np.concatenate([e[1] for e in lista]).astype(np.int32)
                    dati[f"{chiave}_n_anelli"] = np.array([len(e[1]) for e in lista], dtype=np.int32)
                    dati[f"{chiave}_tri"] = np.concatenate([e[2] for e in lista]).astype(np.int32)
                    dati[f"{chiave}_n_tri"] = np.array([len(e[2]) for e in lista], dtype=np.int32)
                    dati[f"{chiave}_base"] = np.array([e[3] for e in lista], dtype=np.float32)
                    dati[f"{chiave}_cima"] = np.array([e[4] for e in lista], dtype=np.float32)
                    dati[f"{chiave}_stile"] = np.array([e[5] for e in lista], dtype=np.uint8)
            if b["st"]:
                dati["st_xyz"] = np.concatenate([s[0] for s in b["st"]]).astype(np.float64)
                dati["st_n"] = np.array([len(s[0]) for s in b["st"]], dtype=np.int32)
                dati["st_larg"] = np.array([s[1] for s in b["st"]], dtype=np.float32)
                dati["st_tipo"] = np.array([s[2] for s in b["st"]], dtype=np.uint8)
            nome = f"{config.PREFISSO}_{i:02d}_{j:02d}"
            np.savez_compressed(cartella / f"{nome}.npz", **dati)
            elenco.append({"nome": nome, "i": i, "j": j, "edifici": len(b["ed"]), "strade": len(b["st"]),
                           "solo_mare": bool((zt < 0).all()) and not b["ed"] and not b["st"]})

    # --- Luoghi simbolo (coordinate GTA, quota del suolo)
    og = zona["origine_gta"]
    luoghi = []
    for l in leggi_luoghi():
        x, y = proj.xy(l["lon"], l["lat"])
        if not (X0 <= x <= X0 + nbx * L and Y0 <= y <= Y0 + nby * L):
            continue
        z = float(terreno.quota(x, y))
        luoghi.append({**l, "gta": [round(float(x) + og[0], 2), round(float(y) + og[1], 2), round(max(z, 0.7) + og[2] + 1.0, 2)]})

    indice = {
        "zona": args.zona, "bbox": bbox, "origine_gta": og,
        "lato_blocco": L, "passo_terreno": P, "nbx": nbx, "nby": nby, "X0": X0, "Y0": Y0,
        "proiezione": {"lon0": proj.lon0, "lat0": proj.lat0, "kx": proj.kx, "ky": proj.ky},
        "stili": STILI, "blocchi": elenco, "luoghi": luoghi,
        "quota_min": float(Z.min()), "quota_max": float(Z.max()),
    }
    (cartella / "indice.json").write_text(json.dumps(indice, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Fatto: {len(elenco)} blocchi in {cartella}")
    print("Ora esegui: blender -b -P pipeline/3_costruisci_in_blender.py -- --zona", args.zona)


if __name__ == "__main__":
    main()
