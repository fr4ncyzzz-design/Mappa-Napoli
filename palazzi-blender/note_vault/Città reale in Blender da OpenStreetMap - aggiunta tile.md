<!-- Da aggiungere in fondo a: cervello\FiveM\Città reale in Blender da OpenStreetMap.md -->

## Lavorare a tile (tutto il comune, ottobre 2026)

Una città intera non sta in un solo `.blend`: Napoli = 53.263 edifici, 106 M facce (96 M solo edifici, ~1.800
facce per edificio contro 1.455 della zona pilota). Si divide in tile da 1 km × 1 km e si genera un `.blend`
per tile, un processo Blender ciascuna.

**Cosa ha funzionato**
- Leggere il `.pbf` **una volta** e scrivere tutti i JSON delle tile (47 s per tutta Napoli), invece di
  rilanciare l'export per ogni zona.
- Bordi delle tile su multipli della griglia del terreno (8 m) e di quella del LOD (40 m): 504 + k·1000 m.
  Con l'offset di 504 m il Plebiscito cade al centro di una tile invece che su un angolo.
- Edificio nella tile del suo **punto rappresentativo**, intervallo semiaperto [x0, x1): niente doppioni.
- **Terreno globale**: le regole terra/mare (celle vicine a edifici/strade ≥ 1 m, il resto ≤ 0,6 m → −3 m)
  vanno calcolate una sola volta con tutti gli edifici e le strade. Rifatte per tile, le celle di bordo
  cambiano tra tile vicine e si aprono gradini. Nel JSON: `"final": true` = non rifarle.
- Le quote dei palazzi si leggono da una griglia con 64 m di margine (`terrain_sample`), il mesh del terreno
  usa solo la griglia della tile: palazzi di bordo esatti, terreno senza sovrapposizioni.
- Strade e aree tagliate con shapely esattamente sul bordo. Il nastro della strada finisce perpendicolare
  alla strada e quello della tile vicina riparte dallo stesso punto con la stessa direzione: combacia.
- **Ponti** tagliati tra più tile: portare quota iniziale/finale e lunghezza dell'intero ponte (`span`),
  sennò la rampa riparte da terra a ogni bordo.
- Prova di regressione prima di toccare l'aspetto: stesso JSON byte per byte e hash della geometria della
  zona pilota identico.
- Scrivere il `.blend` come `.tmp.blend` e rinominarlo solo se Blender finisce bene: la ripresa salta le
  tile fatte senza rischio di file a metà.

**Trappole**
- Blender carica in RAM tutte le librerie collegate, **anche se la collezione è esclusa dal view layer**:
  157 tile collegate = ~13 GB di RAM, OOM su 16 GB. Soluzione: file unico con solo il LOD + pannello che
  collega/scollega le tile vicino al cursore 3D (`bpy.data.libraries.load(link=True)` /
  `bpy.data.libraries.remove(lib)`).
- I percorsi relativi delle librerie (`//tile/...`) si calcolano rispetto al file salvato: salvare il file
  unico vuoto **prima** di collegare.
- Il piano del mare da 40 km della zona pilota si vede all'orizzonte nelle viste di tutta la città: 200 km.
- Il `.pbf` ritagliato sul confine comunale lascia terreno vuoto oltre il confine nelle tile di bordo.
- `bpy` da pip: `import bpy` prima di `bmesh`; Eevee senza GPU va con Mesa (`libegl1 libgl1-mesa-dri`),
  ~45 s per un'anteprima 640×360.
- Testo registrato in un `.blend` (`text.use_module = True`): parte all'apertura solo se l'utente consente
  gli script.

**Numeri**: 157 tile, 8 min 44 s con 3 processi (somma 26 min), RAM max 635 MB per processo, 4 GB di `.blend`;
LOD 1,06 M facce in 31 MB.
