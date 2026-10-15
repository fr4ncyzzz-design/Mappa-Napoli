"""Generazione della geometria dei blocchi e delle texture procedurali.

Solo numpy: funziona sia dentro Blender sia in un Python normale (per i test).
"""

import struct
import zlib

import numpy as np

# ---------------------------------------------------------------------------
# Materiali visivi (indice -> nome texture) e materiali di collisione GTA
# ---------------------------------------------------------------------------
MATERIALI = [
    "asfalto", "basoli", "urbano", "verde", "sabbia", "fondale", "roccia", "tetto",
    "fac_gialla", "fac_rossa", "fac_rosa", "fac_bianca", "fac_ocra", "fac_grigia", "fac_moderna", "fac_chiesa",
    "mare",
]
M_ASFALTO, M_BASOLI, M_URBANO, M_VERDE, M_SABBIA, M_FONDALE, M_ROCCIA, M_TETTO = range(8)
M_FACCIATA = 8
M_MARE = 16
# Materiale celle del terreno (2_prepara_dati.py) -> materiale visivo
TERRENO_A_MAT = np.array([M_URBANO, M_VERDE, M_SABBIA, M_FONDALE, M_ROCCIA], dtype=np.int32)

COLLISIONE = {
    "asfalto": "TARMAC", "basoli": "COBBLESTONE", "urbano": "CONCRETE", "verde": "GRASS",
    "sabbia": "SAND_LOOSE", "fondale": "SAND_UNDERWATER", "roccia": "ROCK", "tetto": "CONCRETE",
    "fac_moderna": "CONCRETE", "fac_chiesa": "STONE",
}


def materiale_collisione(nome):
    if nome in COLLISIONE:
        return COLLISIONE[nome]
    return "PLASTER_SOLID" if nome.startswith("fac_") else "CONCRETE"


LARGHEZZA_CAMPATA = 3.6   # distanza tra le finestre (m)
ALTEZZA_PIANO = 3.4
SCALA_SUOLO = 8.0         # le texture del terreno si ripetono ogni 8 m


class Parti:
    """Accumula triangoli con materiale, UV e colore per vertice."""

    def __init__(self):
        self.V, self.T, self.M, self.UV, self.C, self.S = [], [], [], [], [], []
        self.n = 0

    def aggiungi(self, V, T, M, UV, C=None, liscio=False):
        if len(T) == 0:
            return
        V = np.asarray(V, dtype=np.float64)
        T = np.asarray(T, dtype=np.int64)
        self.V.append(V)
        self.T.append(T + self.n)
        self.M.append(np.broadcast_to(np.asarray(M, dtype=np.int32), (len(T),)).copy())
        self.UV.append(np.asarray(UV, dtype=np.float32)[T].reshape(-1, 2))
        if C is None:
            C = np.ones(len(V), dtype=np.float32)
        C = np.asarray(C, dtype=np.float32)[T].reshape(-1)
        self.C.append(np.repeat(C[:, None], 3, axis=1))
        self.S.append(np.full(len(T), liscio, dtype=bool))
        self.n += len(V)

    def risultato(self):
        if not self.T:
            return None
        return {
            "V": np.concatenate(self.V), "T": np.concatenate(self.T), "M": np.concatenate(self.M),
            "UV": np.concatenate(self.UV), "C": np.concatenate(self.C), "S": np.concatenate(self.S),
        }


# ---------------------------------------------------------------------------
# Terreno
# ---------------------------------------------------------------------------
def terreno(parti, z, mat, origine, passo, centro, salta_mare=False):
    ny, nx = z.shape
    ix, iy = np.meshgrid(np.arange(nx), np.arange(ny))
    x = origine[0] + ix * passo - centro[0]
    y = origine[1] + iy * passo - centro[1]
    V = np.column_stack([x.ravel(), y.ravel(), z.ravel()])
    UV = np.column_stack([(ix.ravel() * passo) / SCALA_SUOLO, (iy.ravel() * passo) / SCALA_SUOLO])
    i, j = np.meshgrid(np.arange(nx - 1), np.arange(ny - 1))
    v00 = (j * nx + i).ravel()
    v10 = v00 + 1
    v01 = v00 + nx
    v11 = v01 + 1
    # Stessa diagonale usata in 2_prepara_dati.Terreno.quota
    T = np.concatenate([np.column_stack([v00, v10, v11]), np.column_stack([v00, v11, v01])])
    M = TERRENO_A_MAT[np.concatenate([mat.ravel(), mat.ravel()])]
    if salta_mare:
        tenere = M != M_FONDALE
        T, M = T[tenere], M[tenere]
    parti.aggiungi(V, T, M, UV, liscio=True)


def piano_mare(parti, z, origine, passo, centro, quota=-0.25):
    """Superficie del mare visibile (solo estetica) sulle celle sotto il livello del mare."""
    ny, nx = z.shape
    celle = (z[:-1, :-1] + z[1:, 1:] + z[:-1, 1:] + z[1:, :-1]) / 4 < 0
    if not celle.any():
        return
    j, i = np.nonzero(celle)
    x0 = origine[0] + i * passo - centro[0]
    y0 = origine[1] + j * passo - centro[1]
    n = len(i)
    V = np.empty((n * 4, 3))
    V[0::4] = np.column_stack([x0, y0, np.full(n, quota)])
    V[1::4] = np.column_stack([x0 + passo, y0, np.full(n, quota)])
    V[2::4] = np.column_stack([x0 + passo, y0 + passo, np.full(n, quota)])
    V[3::4] = np.column_stack([x0, y0 + passo, np.full(n, quota)])
    b = np.arange(n) * 4
    T = np.concatenate([np.column_stack([b, b + 1, b + 2]), np.column_stack([b, b + 2, b + 3])])
    UV = V[:, :2] / 16.0
    parti.aggiungi(V, T, M_MARE, UV, liscio=True)


# ---------------------------------------------------------------------------
# Edifici: muri estrusi + tetto piano (lastrico solare, tipico di Napoli)
# ---------------------------------------------------------------------------
def edifici(parti, d, prefisso, centro):
    if f"{prefisso}_xy" not in d:
        return 0
    xy = d[f"{prefisso}_xy"]
    anelli = d[f"{prefisso}_anelli"]
    n_anelli = d[f"{prefisso}_n_anelli"]
    tri = d[f"{prefisso}_tri"]
    n_tri = d[f"{prefisso}_n_tri"]
    base = d[f"{prefisso}_base"]
    cima = d[f"{prefisso}_cima"]
    stile = d[f"{prefisso}_stile"]

    pv = pa = pt = 0
    for b in range(len(base)):
        conti = anelli[pa:pa + n_anelli[b]]
        nv = int(conti.sum())
        vert = xy[pv:pv + nv] - centro
        triangoli = tri[pt:pt + n_tri[b]]
        pv += nv
        pa += n_anelli[b]
        pt += n_tri[b]
        z0, z1 = float(base[b]), float(cima[b])
        mat = M_FACCIATA + int(stile[b])

        # Muri: un quad per lato, vertici non condivisi (normali nette)
        k = 0
        for c in conti:
            r = vert[k:k + c]
            k += c
            a = r
            bb = np.roll(r, -1, axis=0)
            lung = np.hypot(*(bb - a).T)
            buoni = lung > 0.05
            a, bb, lung = a[buoni], bb[buoni], lung[buoni]
            if len(a) == 0:
                continue
            u0 = np.concatenate([[0], np.cumsum(lung)[:-1]]) / LARGHEZZA_CAMPATA
            u1 = u0 + lung / LARGHEZZA_CAMPATA
            m = len(a)
            V = np.empty((m * 4, 3))
            V[0::4] = np.column_stack([a, np.full(m, z0)])
            V[1::4] = np.column_stack([bb, np.full(m, z0)])
            V[2::4] = np.column_stack([bb, np.full(m, z1)])
            V[3::4] = np.column_stack([a, np.full(m, z1)])
            vt = (z1 - z0) / ALTEZZA_PIANO
            UV = np.empty((m * 4, 2))
            UV[0::4] = np.column_stack([u0, np.zeros(m)])
            UV[1::4] = np.column_stack([u1, np.zeros(m)])
            UV[2::4] = np.column_stack([u1, np.full(m, vt)])
            UV[3::4] = np.column_stack([u0, np.full(m, vt)])
            # Occlusione ambientale finta: base dei muri più scura (vicoli stretti)
            C = np.tile([0.55, 0.55, 1.0, 1.0], m)
            o = np.arange(m) * 4
            T = np.concatenate([np.column_stack([o, o + 1, o + 2]), np.column_stack([o, o + 2, o + 3])])
            parti.aggiungi(V, T, mat, UV, C)

        # Tetto
        V = np.column_stack([vert, np.full(len(vert), z1)])
        parti.aggiungi(V, triangoli, M_TETTO, vert / 6.0)
    return len(base)


# ---------------------------------------------------------------------------
# Strade: nastri adagiati sul terreno
# ---------------------------------------------------------------------------
def strade(parti, d, centro):
    if "st_xyz" not in d:
        return 0
    xyz = d["st_xyz"]
    n = d["st_n"]
    larg = d["st_larg"]
    tipo = d["st_tipo"]
    k = 0
    for s in range(len(n)):
        p = xyz[k:k + n[s]].copy()
        k += n[s]
        p[:, :2] -= centro
        if len(p) < 2:
            continue
        dirz = np.zeros((len(p), 2))
        seg = np.diff(p[:, :2], axis=0)
        lung = np.hypot(*seg.T)
        seg = seg / np.maximum(lung, 1e-6)[:, None]
        dirz[:-1] += seg
        dirz[1:] += seg
        dirz /= np.maximum(np.hypot(*dirz.T), 1e-6)[:, None]
        nrm = np.column_stack([-dirz[:, 1], dirz[:, 0]]) * (larg[s] / 2)
        sx = p[:, :2] + nrm
        dx = p[:, :2] - nrm
        m = len(p)
        V = np.empty((m * 2, 3))
        V[0::2] = np.column_stack([sx, p[:, 2]])
        V[1::2] = np.column_stack([dx, p[:, 2]])
        dist = np.concatenate([[0], np.cumsum(lung)])
        UV = np.empty((m * 2, 2))
        scala = max(float(larg[s]), 2.0)
        UV[0::2] = np.column_stack([np.zeros(m), dist / scala])
        UV[1::2] = np.column_stack([np.ones(m), dist / scala])
        o = np.arange(m - 1) * 2
        # (sx_i, dx_i, dx_i+1) e (sx_i, dx_i+1, sx_i+1): normali verso l'alto
        T = np.concatenate([np.column_stack([o, o + 1, o + 3]), np.column_stack([o, o + 3, o + 2])])
        T = np.column_stack([T[:, 0], T[:, 2], T[:, 1]]) if _normale_giu(V, T[0]) else T
        parti.aggiungi(V, T, M_BASOLI if tipo[s] == 1 else M_ASFALTO, UV, liscio=True)
    return len(n)


def _normale_giu(V, t):
    a, b, c = V[t[0]], V[t[1]], V[t[2]]
    return np.cross(b - a, c - a)[2] < 0


# ---------------------------------------------------------------------------
def blocco(d, centro, lato, mare_visibile=False):
    """Restituisce (visivo HD, collisione, LOD, n. edifici, n. strade) per un blocco."""
    origine = d["origine"]
    z = d["terreno_z"]
    mat = d["terreno_mat"]
    passo = lato / (z.shape[1] - 1)

    hd = Parti()
    terreno(hd, z, mat, origine, passo, centro)
    n_ed = edifici(hd, d, "ed", centro)
    n_st = strade(hd, d, centro)
    vis = hd.risultato()

    collisione = vis  # stessa geometria (senza il mare finto)
    if mare_visibile:
        piano_mare(hd, z, origine, passo, centro)
        vis = hd.risultato()

    # LOD: griglia del terreno più rada (fattore che divide esattamente il blocco, ~30-40 m)
    celle = z.shape[1] - 1
    f = next((k for k in (5, 4, 6, 3, 2) if celle % k == 0), 1)
    lod = Parti()
    terreno(lod, z[::f, ::f], mat[::f, ::f], origine, passo * f, centro)
    edifici(lod, d, "lod", centro)
    if mare_visibile:
        piano_mare(lod, z[::f, ::f], origine, passo * f, centro)
    return vis, collisione, lod.risultato(), n_ed, n_st


def salda(V, T, tolleranza=0.01):
    """Unisce i vertici coincidenti (per la collisione) e scarta i triangoli degeneri."""
    chiavi = np.round(V / tolleranza).astype(np.int64)
    _, primo, inverso = np.unique(chiavi, axis=0, return_index=True, return_inverse=True)
    inverso = inverso.reshape(-1)
    V2 = V[primo]
    T2 = inverso[T]
    buoni = (T2[:, 0] != T2[:, 1]) & (T2[:, 1] != T2[:, 2]) & (T2[:, 0] != T2[:, 2])
    return V2, T2, buoni


def dividi(V, T, M, max_vertici=60000):
    """Divide una mesh in pezzi con al massimo max_vertici (limite 16 bit dei bound GTA)."""
    pezzi = []
    inizio = 0
    passo = max(1, max_vertici // 3)
    while inizio < len(T):
        fine = min(len(T), inizio + passo)
        while True:
            usati = np.unique(T[inizio:fine])
            if len(usati) <= max_vertici or fine - inizio <= 1:
                break
            fine = inizio + (fine - inizio) // 2
        mappa = np.full(len(V), -1, dtype=np.int64)
        mappa[usati] = np.arange(len(usati))
        pezzi.append((V[usati], mappa[T[inizio:fine]], M[inizio:fine]))
        inizio = fine
    return pezzi


# ---------------------------------------------------------------------------
# Texture procedurali (RGBA uint8, ripetibili senza cuciture)
# ---------------------------------------------------------------------------
def _sfoca(a, r):
    for _ in range(2):
        a = sum(np.roll(a, s, axis=0) for s in range(-r, r + 1)) / (2 * r + 1)
        a = sum(np.roll(a, s, axis=1) for s in range(-r, r + 1)) / (2 * r + 1)
    return a


def _rumore(n, seme, r=2):
    g = np.random.default_rng(seme)
    a = _sfoca(g.random((n, n)), r)
    a = (a - a.min()) / max(a.max() - a.min(), 1e-6)
    return a * 2 - 1


def _colore(base, var, rumore):
    return np.clip(np.asarray(base, dtype=np.float32)[None, None, :] + var * rumore[..., None], 0, 255)


def _facciata(n, base, seme):
    rum = _rumore(n, seme, 1) * 0.6 + _rumore(n, seme + 1, 6) * 0.4
    img = _colore(base, 14, rum)
    y, x = np.mgrid[0:n, 0:n] / n
    # Fascia marcapiano
    img[(y > 0.0) & (y < 0.05)] *= 0.86
    # Finestra con cornice
    fin = (x > 0.33) & (x < 0.67) & (y > 0.22) & (y < 0.82)
    cornice = (x > 0.30) & (x < 0.70) & (y > 0.18) & (y < 0.86) & ~fin
    img[cornice] = img[cornice] * 0.4 + np.array([240, 235, 225]) * 0.6
    vetro = np.array([45, 55, 70], dtype=np.float32) + 25 * (y[fin] - 0.2)[:, None]
    img[fin] = vetro
    # Persiane verdi aperte ai lati (classiche napoletane)
    persiane = ((x > 0.19) & (x < 0.30) | (x > 0.70) & (x < 0.81)) & (y > 0.22) & (y < 0.82)
    righe = (np.floor(y * n / 3) % 2 == 0)
    img[persiane] = np.where(righe[persiane][:, None], [55, 95, 65], [45, 80, 55])
    # Balconcino
    balcone = (x > 0.28) & (x < 0.72) & (y > 0.18) & (y < 0.22)
    img[balcone] = [70, 70, 72]
    return img


def _blocchetti(n, base, giunto, colonne, righe, seme, sfalsato=True, var=18):
    g = np.random.default_rng(seme)
    y, x = np.mgrid[0:n, 0:n]
    h = n // righe
    w = n // colonne
    riga = (y // h) % righe
    xs = (x + (riga % 2) * (w // 2 if sfalsato else 0)) % n
    col = (xs // w) % colonne
    tono = g.normal(0, var, (righe, colonne))[riga, col]
    img = _colore(base, 10, _rumore(n, seme, 1)) + tono[..., None]
    bordo = ((y % h) < 2) | ((xs % w) < 2)
    img[bordo] = giunto
    return np.clip(img, 0, 255)


def genera_texture(nome, n=256):
    s = zlib.crc32(nome.encode()) % 1000
    if nome == "asfalto":
        img = _colore([72, 72, 74], 16, _rumore(n, 1, 1))
    elif nome == "basoli":  # basoli di pietra lavica vesuviana
        img = _blocchetti(n, [78, 76, 74], [50, 48, 46], 4, 8, 2)
    elif nome == "urbano":  # marciapiedi e cortili
        img = _blocchetti(n, [160, 152, 140], [120, 114, 104], 4, 4, 3, sfalsato=False, var=6)
    elif nome == "verde":
        img = _colore([78, 112, 50], 28, _rumore(n, 4, 1) * 0.5 + _rumore(n, 5, 8) * 0.5)
    elif nome == "sabbia":
        img = _colore([196, 178, 140], 14, _rumore(n, 6, 1))
    elif nome == "fondale":
        img = _colore([95, 98, 88], 14, _rumore(n, 7, 4))
    elif nome == "roccia":  # tufo giallo napoletano
        r = _rumore(n, 8, 1) * 0.5 + _rumore(n, 9, 10) * 0.5
        img = _colore([186, 158, 98], 26, r)
        img *= (0.92 + 0.08 * np.sin(np.mgrid[0:n, 0:n][0] / n * 2 * np.pi * 6))[..., None]
    elif nome == "tetto":  # lastrico solare
        img = _blocchetti(n, [176, 170, 160], [140, 134, 126], 8, 8, 10, sfalsato=False, var=5)
    elif nome == "mare":
        img = _colore([38, 88, 118], 10, _rumore(n, 11, 6))
    elif nome == "fac_moderna":
        y, x = np.mgrid[0:n, 0:n] / n
        img = _colore([88, 108, 126], 10, _rumore(n, 12, 8))
        img[(x < 0.06) | (y < 0.08)] = [190, 192, 196]
    elif nome == "fac_chiesa":  # piperno e marmo
        img = _blocchetti(n, [150, 146, 138], [120, 116, 110], 2, 4, 13, var=10)
    else:
        colori = {"fac_gialla": [226, 186, 110], "fac_rossa": [168, 72, 56], "fac_rosa": [222, 160, 148],
                  "fac_bianca": [232, 226, 214], "fac_ocra": [204, 148, 82], "fac_grigia": [168, 164, 156]}
        # Riga 0 dell'immagine = alto del piano (convenzione DirectX): balcone in basso
        img = _facciata(n, colori.get(nome, [200, 180, 150]), s)[::-1]
    rgba = np.concatenate([img, np.full((n, n, 1), 255.0)], axis=2)
    return np.clip(rgba, 0, 255).astype(np.uint8)


def dds_rgba(img):
    """Crea un file DDS non compresso A8R8G8B8 con mipmap (fino a 4x4)."""
    h, w = img.shape[:2]
    livelli = []
    cur = img.astype(np.float32)
    while True:
        livelli.append(cur)
        if cur.shape[0] <= 4 or cur.shape[1] <= 4:
            break
        cur = (cur[0::2, 0::2] + cur[1::2, 0::2] + cur[0::2, 1::2] + cur[1::2, 1::2]) / 4
    intest = struct.pack(
        "<4sIIIIIII44sIIIIIIIIIIIII",
        b"DDS ", 124, 0x1 | 0x2 | 0x4 | 0x8 | 0x1000 | 0x20000, h, w, w * 4, 0, len(livelli), b"\0" * 44,
        32, 0x40 | 0x1, 0, 32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000,
        0x1000 | 0x400000 | 0x8, 0, 0, 0, 0,
    )
    corpo = b"".join(np.round(l[..., [2, 1, 0, 3]]).astype(np.uint8).tobytes() for l in livelli)
    return intest + corpo
