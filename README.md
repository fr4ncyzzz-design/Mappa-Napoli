# Napoli 3D per FiveM

Napoli ricostruita in 3D dai dati reali (OpenStreetMap + rilievo) con **Blender + Sollumz**
ed esportata come mappa per GTA V / FiveM.

> Lavoro in corso: la pipeline funziona dall'inizio alla fine, il livello di dettaglio grafico è in sviluppo.

## Struttura
- `pipeline/` – script di generazione
  1. `1_scarica_dati.py` – scarica edifici/strade/costa (OSM) e rilievo (AWS Terrain Tiles)
  2. `2_prepara_dati.py` – divide la zona in blocchi da 400 m (terreno, edifici, strade)
  3. `3_costruisci_in_blender.py` – costruisce i blocchi in Blender e li esporta con Sollumz
     (`.ydr`, `.ybn`, `.ytyp`, `.ymap`, `.ytd`) + genera la risorsa FiveM
- `fivem/` – modelli della risorsa FiveM (`/napoli`, spawn, icone, mappa 3D in gioco)
- `html/` – mappa web 3D di Napoli (anteprima nel browser e mappa in gioco via NUI)

## Uso rapido
```bash
pip install -r pipeline/requirements.txt
python pipeline/1_scarica_dati.py --zona prova        # prova | centro | napoli
python pipeline/2_prepara_dati.py --zona prova
blender -b -P pipeline/3_costruisci_in_blender.py -- --zona prova --salva-blend
```
Serve Blender 4.2+ con l'addon [Sollumz](https://github.com/Sollumz/Sollumz) (e le sue dipendenze).
Con PyMateria (Sollumz > Preferenze, Windows) l'export è direttamente binario in
`uscita/<zona>/napoli3d/stream`; altrimenti escono XML in `uscita/<zona>/xml_codewalker`
da convertire con CodeWalker.

Copia poi `uscita/<zona>/napoli3d` nella cartella `resources` del server e aggiungi `ensure napoli3d`.

## Limiti attuali
- Napoli viene posizionata in mare accanto a Los Santos (coordinate in `pipeline/config.py`).
- Niente pedoni/traffico (servono navmesh e percorsi).

Dati © OpenStreetMap contributors (ODbL). MapLibre GL JS (BSD-3) in `html/lib`.
