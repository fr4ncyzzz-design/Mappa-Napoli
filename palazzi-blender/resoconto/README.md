# Napoli intera in Blender: resoconto

Esecuzione di prova completa nel cloud (4 vCPU, 15 GB di RAM, nessuna GPU, Blender 5.1.2 come modulo Python),
15 ottobre 2026. I file `.blend` (4 GB) non sono nel repository: si rigenerano sul PC con i comandi in fondo.

## Risultato

| | |
|---|---|
| Griglia | 15 righe × 20 colonne da 1 km × 1 km, bordi a 504 + k·1000 m dal Plebiscito |
| Tile con edifici | **157** (143 vuote saltate: mare o fuori comune) |
| Edifici | **53.263** (tutti quelli del `.pbf`, nessun doppione tra tile) |
| Facce totali | **106,2 milioni** (96,0 M edifici + terreno, strade, verde, piazze) |
| Facce per tile | min 20.471, mediana 599.975, media 676.385, max 2.155.998 (`napoli_r07_c11`, 1.795 edifici) |
| Edifici per tile | min 1, mediana 277, max 1.795 |
| `.blend` delle tile | 3,99 GB in tutto, max 78,6 MB (`napoli_r07_c11`) |
| LOD (`napoli_lod.blend`) | 1,06 M facce, 31 MB |
| `napoli_tutta.blend` | 118 KB: LOD + cielo, sole, mare unici + pannello per caricare il dettaglio |

Dettaglio per tile (edifici, facce, facce LOD, MB, tempi): [`statistiche_tile.csv`](statistiche_tile.csv).

## Tempi (cloud, 3 processi Blender in parallelo)

| Passo | Tempo |
|---|---|
| `tile_export.py` (un passaggio sul `.pbf`, 157 JSON) | 47 s |
| 157 tile `.blend` | 524 s (8 min 44 s); somma dei processi 1.570 s, max 30,8 s per tile, RAM max 635 MB per processo |
| `costruisci_lod.py` | 13 s |
| `costruisci_tutta.py` (versione leggera) | 1 s |
| 157 anteprime Eevee 640×360 (Eevee in software, senza GPU) | 1.720 s (29 min) |
| panoramica 1600×900 dal LOD | 70 s |
| **Totale** | **~40 min** (~11 min senza le anteprime) |

Sul PC con RTX 4060 la generazione per processo è un po' più lenta (la zona pilota: 85 s contro 61 s qui),
le anteprime molto più veloci perché Eevee usa la GPU.

## Controlli fatti

- **Aspetto invariato**: la zona pilota rigenerata con gli script nuovi dà la stessa geometria (hash identico su
  vertici, posizioni e materiali di tutti i 2.837 oggetti) e `zona_export.py` riorganizzato dà un JSON identico
  byte per byte a `dati/zona_plebiscito.json`.
- **Bordo tra tile** (`napoli_r08_c10` centro / `napoli_r08_c09` Vomero, bordo x = −496 m con forte salita):
  126 vertici del terreno in comune, differenza di quota **0,0000 m**; il terreno di una tile finisce
  esattamente dove comincia l'altra (nessuna sovrapposizione); le 27 strade tagliate sul bordo hanno tutte la
  continuazione nell'altra tile; 0 edifici doppi. Render del bordo: [`bordo_r08_c09_r08_c10.jpg`](bordo_r08_c09_r08_c10.jpg).
- **Anteprime**: 157 su 157, guardate a campione: centro (Toledo), collina (Vomero), porto, periferia nord
  (Scampia), Posillipo, Fuorigrotta: [`campione_5_zone.jpg`](campione_5_zone.jpg); tutte insieme:
  [`mosaico_157_tile.jpg`](mosaico_157_tile.jpg).
- **Stile dei palazzi fuori dalla zona pilota**: [`strada_vomero.jpg`](strada_vomero.jpg).
- **Panoramica** dalla versione leggera: [`panoramica_lod.jpg`](panoramica_lod.jpg).
- **File unico**: si apre in 0,5 s con 378 MB di RAM e 1,06 M facce visibili; con "Carica tile vicino al
  cursore" sul Plebiscito (raggio 0,8 km) collega 7 tile di dettaglio: 9,4 M facce visibili, 1,7 GB di RAM;
  "Scarica tutte" torna al solo LOD.

## Problemi trovati

1. **Collegare tutte le tile costa ~13 GB di RAM.** Blender carica i dati collegati anche se la collezione è
   esclusa dal view layer: il file con tutte le 157 tile collegate è stato chiuso per memoria esaurita a ~14 GB.
   Quindi `napoli_tutta.blend` collega subito solo il LOD e il dettaglio si collega a richiesta dal pannello
   **Napoli** (vista 3D, barra laterale N), sempre come Link. La versione con tutto collegato si crea con
   `--completa` (`napoli_tutta_completa.blend`), solo per PC con 32 GB di RAM o più.
2. **Dati ritagliati sul confine comunale**: nelle tile di bordo il terreno fuori dal comune (Pozzuoli, Portici,
   San Giorgio, ecc.) c'è ma è senza edifici, e finisce dritto sul bordo della tile. Si vede nella panoramica.
3. **Tile con molto verde e pochi edifici pesano più del previsto** (es. `napoli_r07_c00`: 1 edificio, 152.813
   facce): il generatore suddivide prati e boschi a lati di 6 m per farli seguire il terreno. È lo stesso
   comportamento della zona pilota, non l'ho cambiato.
4. **Porto commerciale quasi vuoto** (`napoli_r09_c12`: 4 edifici): in OSM i capannoni del porto sono pochi.
5. **Mare**: nella panoramica dall'alto il bordo del piano del mare da 40 km si vedeva all'orizzonte; in
   `napoli_tutta.blend` il mare è largo 200 km (le tile non hanno mare).
6. **Palazzi su forti pendenze** (Vomero, Posillipo): la base parte dalla quota più bassa della pianta, quindi
   sul lato a monte una parte del piano terra resta nel terreno. È come nella zona pilota.
7. **Anteprime del cloud più chiare** di quelle della zona pilota: qui Eevee gira in software (Mesa), senza GPU.

## Rigenerare tutto sul PC (PowerShell, cartella napoli-blender)

```powershell
powershell -ExecutionPolicy Bypass -File setup_windows.ps1
.\.venv\Scripts\python.exe genera_tile.py --processi 2 --anteprime
& "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" -b --factory-startup --python costruisci_lod.py -- tile napoli_lod.blend
& "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" -b --factory-startup --python costruisci_tutta.py -- tile napoli_lod.blend napoli_tutta.blend --anteprima anteprime_tile\panoramica.png
```
`genera_tile.py` crea da solo i JSON delle tile se mancano e, se si interrompe, riparte saltando le tile già fatte.
All'apertura di `napoli_tutta.blend` Blender chiede di consentire gli script ("Allow Execution"): serve per il
pannello Napoli.
