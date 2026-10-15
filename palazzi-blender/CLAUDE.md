# Mappa-Napoli

Napoli in Blender con palazzi procedurali in stile napoletano, dai dati OpenStreetMap. Rispondi in **italiano**; codice, nomi e file in **inglese** o come sono già.

## File
- `dati/napoli.osm.pbf`: tutto il comune di Napoli (ritagliato sul confine ufficiale, relation 40767), ~53.000 edifici, 641.937 nodi. pyosmium lo legge come l'`.osm`.
- `strumenti/zona_export.py`: dal `.pbf` crea il JSON di una zona.
  `python strumenti/zona_export.py dati/napoli.osm.pbf strumenti/tiles uscita.json S W N E`
  L'origine delle coordinate è **fissa** su Piazza del Plebiscito (40.8359, 14.2483): tutte le zone si allineano. Un edificio appartiene alla zona se il suo punto rappresentativo cade dentro, quindi niente doppioni tra zone vicine. Le tile del rilievo che mancano le scarica da `s3.amazonaws.com/elevation-tiles-prod/terrarium/13/x/y.png`.
- `strumenti/tiles/`: tile Terrarium z13 (quota = R*256 + G + B/256 - 32768).
- `strumenti/clip_osm.py`, `verify_osm.py`: ritaglio di un comune da un `.pbf` regionale e controllo del risultato.
- `napoli_palazzi.py`: generatore per **Blender 5.1**. Legge il JSON e crea palazzi (piani, finestre incassate, persiane, balconi con ringhiera alpha, cornicioni, terrazzi), terreno, strade, piazze, verde, mare, camere e anteprime.
  `blender -b --factory-startup --python napoli_palazzi.py -- zona.json uscita.blend cartella_anteprime`
- `dati/zona_plebiscito.json` + `anteprime/`: zona pilota Plebiscito–Toledo–lungomare **approvata dall'utente**. È il riferimento visivo: l'aspetto dei palazzi non va cambiato.

## Tutta Napoli a tile (1 km × 1 km)
- `strumenti/tile_export.py dati/napoli.osm.pbf strumenti/tiles tile`: legge il `.pbf` **una volta** e scrive `tile/napoli_rRR_cCC.json` + `tile/indice_tile.json`. Righe contate da nord. Bordi a x, y = 504 + k·1000 m dall'origine: il Plebiscito cade al centro di `napoli_r09_c10`. 15 × 20 tile, 157 con edifici (143 vuote saltate).
- `genera_tile.py [--processi 2] [--anteprime]`: un processo Blender per tile, log in `tile/log/`, ripresa automatica (scrive `.tmp.blend` e rinomina solo a fine riuscita), statistiche in `tile/statistiche.json`.
- `napoli_palazzi.py` riconosce il JSON di tile (chiave `"tile"`): crea solo la collezione `napoli_rRR_cCC` (figlie `_Edifici`, `_Terreno`, `_Strade`), niente cielo/sole/mare/camere. Con il JSON della zona pilota fa esattamente come prima (stesso hash della geometria).
- `costruisci_lod.py -- tile napoli_lod.blend`: blocchi estrusi con stessa pianta/altezza/colore (`plan_floors()` condivisa con il generatore), terreno 40 m, verde e piazze. 1,06 M facce in tutto.
- `costruisci_tutta.py -- tile napoli_lod.blend napoli_tutta.blend`: LOD collegato + cielo, sole, mare unici + pannello **Napoli** (vista 3D, barra N) che collega/scollega le tile di dettaglio vicino al cursore 3D. `--completa` collega subito tutte le tile (serve ~14 GB di RAM).
- `render_tile.py -- out.png tile/x.blend [altre] [--vista tile|bordo|strada]`: anteprima Eevee con le tile collegate.

## Numeri della zona pilota
2.826 edifici → 4,1 milioni di facce, 85 s di generazione, `.blend` compresso 156 MB, render Eevee 1600×900 in ~1 min ciascuno su RTX 4060.

## Trappole già trovate
- Muri: un lato è "in comune" se il punto a 1,2 m fuori dal suo centro cade in un altro edificio (niente finestre); lato di un anello interno = cortile; altrimenti strada.
- Mare: quota ≤ 0,6 m = mare, ma le celle vicine a edifici o strade restano a terra (sennò il porto si allaga).
- Strade fuori dalla griglia del terreno vanno tagliate, sennò restano sospese in aria.
- `read_factory_settings` solo con `bpy.app.background`.
- Blender 5.x: motore `BLENDER_EEVEE`, `sky_type` cambiato (lo script prova i valori in un `try`).
- Overpass è spesso giù e vuole uno User-Agent: meglio gli estratti `.pbf`.
- GitHub non accetta file > 100 MB (25 MB dal caricamento web): i `.blend` e i `.json` grandi non vanno nel repo.
- Tile senza buchi: il terreno sta su **una griglia globale da 8 m** e le regole terra/mare (urbano ≥ 1 m, mare a −3 m) si calcolano una volta con tutti gli edifici e le strade; nel JSON `"final": true` dice al generatore di non rifarle (con la maschera locale le celle di bordo cambierebbero tra tile vicine). Le quote dei palazzi si leggono da `terrain_sample` (griglia + 64 m), il mesh usa solo `terrain`.
- Strade e aree vanno tagliate con shapely esattamente sul bordo; nel generatore il taglio "a 2 m dal bordo" va tolto in modalità tile. I ponti tagliati portano `span` = [quota inizio, quota fine, progressiva del pezzo, lunghezza totale] dell'intero ponte, sennò la rampa ricomincia a ogni tile.
- Blender carica in RAM i dati collegati anche se la collezione è esclusa dal view layer: 157 tile collegate = ~13 GB di RAM (OOM su 16 GB). Per questo `napoli_tutta.blend` collega il dettaglio su richiesta; `bpy.data.libraries.remove(lib)` scollega una tile.
- Generatore come modulo `bpy` (pip): `import bpy` prima di `bmesh`; Eevee senza GPU funziona con Mesa (`libegl1 libgl1-mesa-dri`) ma è lento (~45 s per un'anteprima 640×360).

## Ambiente dell'utente
PC Windows 11, Blender 5.1 in `C:\Program Files\Blender Foundation\Blender 5.1\blender.exe`, RTX 4060 8 GB, PowerShell 5.1 (niente `&&`), Python 3.11 con `py -3.11`. Il generatore finale gira sul suo PC.
