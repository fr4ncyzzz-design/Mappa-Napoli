"""Configurazione condivisa della pipeline Napoli -> GTA V / FiveM.

Unità: 1 unità Blender = 1 metro = 1 unità GTA.
Asse X = est, asse Y = nord, asse Z = quota sul livello del mare.
"""

from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
CARTELLA_DATI = RADICE / "dati"
CARTELLA_USCITA = RADICE / "uscita"

# ---------------------------------------------------------------------------
# Zone pronte (lon_min, lat_min, lon_max, lat_max)
# ---------------------------------------------------------------------------
# "origine_gta" è il punto del mondo di GTA in cui finisce il CENTRO della zona.
# La mappa vanilla di Los Santos occupa circa x -4000..+4500, y -4000..+8000:
# per questo Napoli viene costruita in mare aperto, dove non si sovrappone a nulla.
# Il livello del mare di Napoli coincide con quello di GTA (z = 0).
PRESET = {
    # ~1,4 x 1,1 km attorno a Piazza del Plebiscito: per provare la pipeline in pochi minuti
    "prova": {
        "bbox": (14.2400, 40.8310, 14.2560, 40.8420),
        "origine_gta": (-6000.0, 1000.0, 0.0),
    },
    # Posillipo, Chiaia, Vomero, Centro storico, Porto, Stazione: ~6,7 x 4,7 km
    "centro": {
        "bbox": (14.1950, 40.8200, 14.2750, 40.8620),
        "origine_gta": (-8000.0, 1500.0, 0.0),
    },
    # Tutto il comune di Napoli, da Bagnoli a Ponticelli e da Posillipo a Scampia: ~17,7 x 14,4 km
    "napoli": {
        "bbox": (14.1400, 40.7900, 14.3500, 40.9200),
        "origine_gta": (0.0, -13500.0, 0.0),
    },
}

# ---------------------------------------------------------------------------
# Suddivisione in blocchi (tile): ogni blocco diventa un .ydr + un .ybn
# ---------------------------------------------------------------------------
LATO_BLOCCO = 400.0          # metri
PASSO_TERRENO = 8.0          # risoluzione della griglia del terreno (metri)
BLOCCHI_PER_YMAP = 4         # ogni .ymap raggruppa 4x4 blocchi

# Distanze di visibilità (metri)
LOD_DIST_BLOCCO = 1200.0
LOD_DIST_PANORAMA = 15000.0

# ---------------------------------------------------------------------------
# Rilievo (DEM): AWS Terrain Tiles, formato "terrarium" (SRTM / EU-DEM)
# ---------------------------------------------------------------------------
DEM_URL = "https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{z}/{x}/{y}.png"
DEM_ZOOM = 14

# ---------------------------------------------------------------------------
# OpenStreetMap (Overpass API): si prova il primo server, poi gli altri
# ---------------------------------------------------------------------------
OVERPASS_SERVER = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# Altezza di un piano (m) e altezza di ripiego quando OSM non la indica
ALTEZZA_PIANO = 3.4
ALTEZZA_MINIMA = 4.0

# Larghezza delle strade (m) per tipo OSM "highway"
LARGHEZZA_STRADE = {
    "motorway": 14.0, "trunk": 12.0, "primary": 11.0, "secondary": 9.0,
    "tertiary": 8.0, "unclassified": 6.0, "residential": 6.0, "living_street": 5.0,
    "service": 4.5, "pedestrian": 6.0, "footway": 2.5, "path": 2.0, "steps": 2.5,
    "motorway_link": 8.0, "trunk_link": 7.5, "primary_link": 7.0, "secondary_link": 6.5,
    "tertiary_link": 6.0, "track": 3.0, "cycleway": 2.5,
}
# Strade "per auto" (asfalto) vs pedonali (basolato / lastricato)
STRADE_PEDONALI = {"pedestrian", "footway", "path", "steps", "living_street", "cycleway", "track"}

# Nomi degli asset GTA (max ~ 30 caratteri, solo minuscole)
PREFISSO = "nap"
NOME_TXD = "nap_texture"
NOME_YTYP = "nap_tipi"
NOME_RISORSA = "napoli3d"


def preset(nome: str) -> dict:
    if nome not in PRESET:
        raise SystemExit(f"Zona sconosciuta '{nome}'. Scegli tra: {', '.join(PRESET)}")
    return PRESET[nome]
