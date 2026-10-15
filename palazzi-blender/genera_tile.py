"""Genera tutte le tile di Napoli: un processo Blender per tile, in parallelo, con log e ripresa automatica.

Uso (PowerShell, dalla cartella napoli-blender):
    py -3.11 genera_tile.py                      # JSON mancanti + .blend mancanti
    py -3.11 genera_tile.py --anteprime          # anche un render piccolo per ogni tile
    py -3.11 genera_tile.py --solo napoli_r08_c10,napoli_r08_c09
Opzioni:
    --blender PERCORSO   eseguibile di Blender (predefinito: Blender 5.1 in Program Files su Windows, "blender" altrove)
    --processi N         processi Blender in parallelo (predefinito 2: ogni tile densa usa 2-4 GB di RAM)
    --timeout SECONDI    tempo massimo per tile (predefinito 1800)

Ripresa: una tile è fatta quando esiste tile/<nome>.blend. Il file viene scritto prima come .tmp.blend e
rinominato solo se Blender finisce senza errori, quindi un'interruzione non lascia .blend a metà.
Rilanciando lo stesso comando si riparte da dove ci si era fermati.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
TILE_DIR = HERE / "tile"
LOG_DIR = TILE_DIR / "log"
PREVIEW_DIR = HERE / "anteprime_tile"
DEFAULT_BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" if os.name == "nt" else "blender"


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def run_blender(blender, script, args, logfile, timeout):
    cmd = [blender, "-b", "--factory-startup", "--python", str(script), "--", *map(str, args)]
    t0 = time.time()
    with open(logfile, "w", encoding="utf-8") as f:
        f.write(" ".join(cmd) + "\n")
        f.flush()
        try:
            proc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
            code = proc.returncode
        except subprocess.TimeoutExpired:
            f.write(f"\nTIMEOUT dopo {timeout}s\n")
            code = -1
    return code, time.time() - t0


def make_tile(name, blender, timeout):
    blend = TILE_DIR / f"{name}.blend"
    tmp = TILE_DIR / f"{name}.tmp.blend"
    logfile = LOG_DIR / f"{name}.log"
    if tmp.exists():
        tmp.unlink()
    code, secs = run_blender(blender, HERE / "napoli_palazzi.py", [TILE_DIR / f"{name}.json", tmp], logfile, timeout)
    stats = None
    for line in logfile.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("STATISTICHE "):
            stats = json.loads(line[len("STATISTICHE "):])
    if code == 0 and stats and tmp.exists():
        os.replace(tmp, blend)
        stats["secondi_processo"] = round(secs, 1)
        stats["mb"] = round(blend.stat().st_size / 1e6, 1)
        return name, True, stats
    return name, False, {"codice": code, "secondi_processo": round(secs, 1)}


def make_preview(name, blender, timeout):
    png = PREVIEW_DIR / f"{name}.png"
    logfile = LOG_DIR / f"{name}_anteprima.log"
    code, secs = run_blender(blender, HERE / "render_tile.py", [png, TILE_DIR / f"{name}.blend"], logfile, timeout)
    return name, code == 0 and png.exists(), {"secondi_render": round(secs, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blender", default=DEFAULT_BLENDER)
    ap.add_argument("--processi", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--anteprime", action="store_true")
    ap.add_argument("--solo", default="")
    args = ap.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    index_file = TILE_DIR / "indice_tile.json"
    if not index_file.exists():
        log("creo i JSON delle tile (strumenti/tile_export.py)...")
        subprocess.run([sys.executable, str(HERE / "strumenti" / "tile_export.py"), str(HERE / "dati" / "napoli.osm.pbf"),
                        str(HERE / "strumenti" / "tiles"), str(TILE_DIR)], check=True)
    index = json.loads(index_file.read_text(encoding="utf-8"))
    names = [t["name"] for t in index["tiles"]]
    if args.solo:
        wanted = set(args.solo.split(","))
        names = [n for n in names if n in wanted]

    stats_file = TILE_DIR / "statistiche.json"
    stats = json.loads(stats_file.read_text(encoding="utf-8")) if stats_file.exists() else {}
    # Le tile più dense per prime: la coda finisce prima
    density = {t["name"]: t["buildings"] for t in index["tiles"]}
    todo = sorted((n for n in names if not (TILE_DIR / f"{n}.blend").exists()), key=lambda n: -density[n])
    log(f"{len(names)} tile, già fatte {len(names) - len(todo)}, da fare {len(todo)} con {args.processi} processi")

    t0 = time.time()
    failed = []
    with ThreadPoolExecutor(max_workers=args.processi) as pool:
        futures = [pool.submit(make_tile, n, args.blender, args.timeout) for n in todo]
        for k, fut in enumerate(as_completed(futures), 1):
            name, ok, info = fut.result()
            if ok:
                stats[name] = {**stats.get(name, {}), **info}
                stats_file.write_text(json.dumps(stats, indent=1), encoding="utf-8")
                log(f"[{k}/{len(todo)}] {name}: {info['edifici']} edifici, {info['facce_totali']:,} facce, "
                    f"{info['secondi_processo']} s, {info['mb']} MB")
            else:
                failed.append(name)
                log(f"[{k}/{len(todo)}] {name}: ERRORE (vedi {LOG_DIR / (name + '.log')})")
    log(f"tile finite in {time.time() - t0:.0f} s, errori: {len(failed)} {failed}")

    if args.anteprime:
        PREVIEW_DIR.mkdir(exist_ok=True)
        todo = [n for n in names if (TILE_DIR / f"{n}.blend").exists() and not (PREVIEW_DIR / f"{n}.png").exists()]
        log(f"anteprime da fare: {len(todo)}")
        t1 = time.time()
        with ThreadPoolExecutor(max_workers=args.processi) as pool:
            futures = [pool.submit(make_preview, n, args.blender, args.timeout) for n in todo]
            for k, fut in enumerate(as_completed(futures), 1):
                name, ok, info = fut.result()
                if ok:
                    stats.setdefault(name, {}).update(info)
                    stats_file.write_text(json.dumps(stats, indent=1), encoding="utf-8")
                log(f"[{k}/{len(todo)}] anteprima {name}: {'ok' if ok else 'ERRORE'} ({info['secondi_render']} s)")
        log(f"anteprime finite in {time.time() - t1:.0f} s")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
