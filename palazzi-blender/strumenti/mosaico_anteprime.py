"""Monta le anteprime delle tile in un mosaico che segue la griglia della città (righe da nord).

Uso:
    python strumenti/mosaico_anteprime.py tile/indice_tile.json anteprime_tile mosaico.jpg [larghezza_cella]
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

index = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
src, out = Path(sys.argv[2]), Path(sys.argv[3])
cw = int(sys.argv[4]) if len(sys.argv) > 4 else 192
ch = cw * 9 // 16
sheet = Image.new("RGB", (index["cols"] * cw, index["rows"] * ch), (24, 40, 60))
draw = ImageDraw.Draw(sheet)
for t in index["tiles"]:
    x, y = t["c"] * cw, t["r"] * ch
    png = src / f"{t['name']}.png"
    if png.exists():
        sheet.paste(Image.open(png).convert("RGB").resize((cw, ch)), (x, y))
    else:
        draw.rectangle([x, y, x + cw - 1, y + ch - 1], outline=(200, 60, 60))
    draw.text((x + 4, y + 2), t["name"].replace("napoli_", ""), fill=(255, 255, 255))
sheet.save(out, quality=88)
print(f"mosaico {sheet.size[0]}x{sheet.size[1]} salvato in {out}")
