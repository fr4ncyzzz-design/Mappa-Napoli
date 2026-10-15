"""Passo 1: scarica i dati reali di Napoli.

- Edifici, strade, costa e aree verdi da OpenStreetMap (Overpass API)
- Rilievo del terreno (DEM) da AWS Terrain Tiles

Uso:
    python pipeline/1_scarica_dati.py --zona prova
    python pipeline/1_scarica_dati.py --zona napoli

Richiede: numpy, pillow  (pip install -r pipeline/requirements.txt)
"""

import argparse
import io
import json
import math
import sys
import time
import urllib.parse
import urllib.request

import numpy as np
from PIL import Image

import config

USER_AGENT = "Napoli3D-FiveM/1.0 (https://github.com/fr4ncyzzz-design/mappa-napoli)"

QUERY = """[out:json][timeout:900][maxsize:2000000000];
(
  way["building"]({b});
  relation["building"]["type"="multipolygon"]({b});
  way["building:part"]({b});
  relation["building:part"]["type"="multipolygon"]({b});
  way["highway"]({b});
  way["natural"="coastline"]({b});
  way["leisure"~"^(park|garden|pitch|playground)$"]({b});
  way["landuse"~"^(grass|forest|meadow|park|cemetery|recreation_ground|vineyard|orchard|village_green)$"]({b});
  way["natural"~"^(wood|scrub|grassland|beach|sand|heath)$"]({b});
  relation["leisure"~"^(park|garden)$"]["type"="multipolygon"]({b});
  relation["landuse"~"^(forest|grass|cemetery)$"]["type"="multipolygon"]({b});
  relation["natural"~"^(wood|scrub)$"]["type"="multipolygon"]({b});
);
out geom;
"""


def scarica(url, dati=None, tentativi=4):
    for i in range(tentativi):
        try:
            req = urllib.request.Request(url, data=dati, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=960) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001 - rete instabile: riprova
            attesa = 2 ** (i + 1)
            print(f"   ! errore ({e}), riprovo tra {attesa}s")
            time.sleep(attesa)
    return None


def scarica_osm(bbox, uscita):
    lon0, lat0, lon1, lat1 = bbox
    # Le zone grandi si scaricano a pezzi per non superare i limiti di Overpass.
    n = max(1, math.ceil(max(lon1 - lon0, lat1 - lat0) / 0.05))
    elementi = {}
    for i in range(n):
        for j in range(n):
            a = lon0 + (lon1 - lon0) * i / n
            b = lon0 + (lon1 - lon0) * (i + 1) / n
            c = lat0 + (lat1 - lat0) * j / n
            d = lat0 + (lat1 - lat0) * (j + 1) / n
            q = QUERY.replace("{b}", f"{c},{a},{d},{b}")
            print(f" - OSM pezzo {i * n + j + 1}/{n * n}")
            contenuto = None
            for server in config.OVERPASS_SERVER:
                contenuto = scarica(server, urllib.parse.urlencode({"data": q}).encode())
                if contenuto:
                    break
            if not contenuto:
                sys.exit("Impossibile scaricare i dati OSM: controlla la connessione e riprova.")
            for el in json.loads(contenuto)["elements"]:
                elementi[(el["type"], el["id"])] = el
    uscita.write_text(json.dumps({"elements": list(elementi.values())}), encoding="utf-8")
    print(f"   {len(elementi)} elementi OSM salvati in {uscita}")


def lonlat_a_tile(lon, lat, z):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
    return x, y


def scarica_dem(bbox, uscita):
    z = config.DEM_ZOOM
    margine = 0.01
    x0, y1 = lonlat_a_tile(bbox[0] - margine, bbox[1] - margine, z)
    x1, y0 = lonlat_a_tile(bbox[2] + margine, bbox[3] + margine, z)
    tx0, tx1, ty0, ty1 = int(x0), int(x1), int(y0), int(y1)
    w, h = (tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256
    quota = np.zeros((h, w), dtype=np.float32)
    totale = (tx1 - tx0 + 1) * (ty1 - ty0 + 1)
    k = 0
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            k += 1
            print(f"\r - DEM tile {k}/{totale}", end="", flush=True)
            dati = scarica(config.DEM_URL.format(z=z, x=tx, y=ty))
            if not dati:
                sys.exit("\nImpossibile scaricare il rilievo (DEM).")
            img = np.asarray(Image.open(io.BytesIO(dati)).convert("RGB"), dtype=np.float32)
            # Codifica terrarium: quota = R*256 + G + B/256 - 32768
            q = img[..., 0] * 256.0 + img[..., 1] + img[..., 2] / 256.0 - 32768.0
            quota[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = q
    print()
    np.savez_compressed(uscita, quota=quota, zoom=z, tx0=tx0, ty0=ty0)
    print(f"   rilievo {w}x{h} px salvato in {uscita}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zona", default="prova", help="prova | centro | napoli")
    ap.add_argument("--solo-dem", action="store_true", help="scarica solo il rilievo")
    args = ap.parse_args()

    p = config.preset(args.zona)
    config.CARTELLA_DATI.mkdir(parents=True, exist_ok=True)
    print(f"Zona '{args.zona}': {p['bbox']}")
    scarica_dem(p["bbox"], config.CARTELLA_DATI / f"dem_{args.zona}.npz")
    if not args.solo_dem:
        scarica_osm(p["bbox"], config.CARTELLA_DATI / f"osm_{args.zona}.json")
    print("Fatto. Ora esegui: python pipeline/2_prepara_dati.py --zona", args.zona)


if __name__ == "__main__":
    main()
