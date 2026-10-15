<!-- Nota di progetto da mettere in: cervello\FiveM\Napoli intera in Blender.md -->

# Napoli intera in Blender

**Stato**: tutto il comune generato a tile e verificato (ottobre 2026). Export per FiveM/Sollumz: passo separato,
non ancora fatto.
**Repository**: `fr4ncyzzz-design/Mappa-Napoli`, cartella `palazzi-blender/`, branch `claude/determined-lamport-5bh3z6`.
**Cartella sul PC**: `C:\Users\fr4ncyz\Documents\napoli-blender`.
**Vedi anche**: [[Città reale in Blender da OpenStreetMap]].

## Obiettivo
Tutto il comune di Napoli in Blender con lo stile dei palazzi della zona pilota Plebiscito–Toledo–lungomare
(approvata), navigabile su RTX 4060 8 GB.

## Come è fatto
- Griglia 15 × 20 tile da 1 km, 157 con edifici: `tile/napoli_rRR_cCC.json` + `.blend` (righe da nord).
- `genera_tile.py`: un processo Blender per tile, log, ripresa automatica, anteprime.
- `napoli_lod.blend`: blocchi estrusi con stessi colori/altezze, 1,06 M facce.
- `napoli_tutta.blend`: LOD + cielo/sole/mare unici; pannello **Napoli** (barra N) per collegare il dettaglio
  vicino al cursore 3D. `napoli_tutta_completa.blend` (con `--completa`) collega tutto: serve ≥ 32 GB di RAM.

## Numeri
53.263 edifici, 106,2 M facce (96 M edifici), tile più pesante `napoli_r07_c11` (1.795 edifici, 2,16 M facce,
78,6 MB). Generazione nel cloud 8 min 44 s con 3 processi; anteprime 29 min senza GPU.

## Da fare / idee
- Export FiveM con Sollumz a partire dalle tile (una tile = un gruppo di `.ydr`/`.ybn`; il LOD può diventare
  il LOD di GTA).
- Terreno oltre il confine comunale: estratto `.pbf` più largo o terreno tagliato sul confine.
- Porto commerciale povero di edifici in OSM.

## Comandi (PowerShell)
```powershell
powershell -ExecutionPolicy Bypass -File setup_windows.ps1
.\.venv\Scripts\python.exe genera_tile.py --processi 2 --anteprime
& "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" -b --factory-startup --python costruisci_lod.py -- tile napoli_lod.blend
& "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" -b --factory-startup --python costruisci_tutta.py -- tile napoli_lod.blend napoli_tutta.blend
```
