import sys
import xml.etree.ElementTree as ET

import osmium

p = sys.argv[1]
counts = {"n": 0, "w": 0, "r": 0}
want = {"Piazza del Plebiscito", "Via Toledo", "Castel dell'Ovo", "Stadio Diego Armando Maradona",
        "Napoli Centrale", "Via Caracciolo", "Vomero", "Scampia"}
found, nodes, missing = set(), set(), 0
for o in osmium.FileProcessor(p):
    counts[o.type_str()] += 1
    if o.is_node():
        nodes.add(o.id)
    elif o.is_way():
        missing += sum(1 for r in o.nodes if r.ref not in nodes)
    name = o.tags.get("name")
    if name in want:
        found.add(name)
print(counts, "nodi mancanti nelle way:", missing)
print("trovati:", sorted(found))
print("non trovati:", sorted(want - found))
ET.parse(p)
print("XML ben formato")
