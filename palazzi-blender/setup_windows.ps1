# Prepara l'ambiente Python 3.11 per gli strumenti di Napoli in Blender (PowerShell 5.1, niente "&&").
# Uso, dalla cartella napoli-blender:
#   powershell -ExecutionPolicy Bypass -File setup_windows.ps1
# L'antivirus intercetta l'HTTPS: pip usa l'archivio certificati di Windows (truststore), la verifica SSL resta attiva.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    py -3.11 -m venv .venv
}
.\.venv\Scripts\python.exe -m pip install --use-feature=truststore --upgrade pip
.\.venv\Scripts\python.exe -m pip install --use-feature=truststore -r strumenti\requirements.txt

Write-Host ""
Write-Host "Pronto. Per generare tutte le tile:"
Write-Host "  .\.venv\Scripts\python.exe genera_tile.py --processi 2 --anteprime"
Write-Host "Poi la versione leggera e il file unico:"
Write-Host '  & "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" -b --factory-startup --python costruisci_lod.py -- tile napoli_lod.blend'
Write-Host '  & "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" -b --factory-startup --python costruisci_tutta.py -- tile napoli_lod.blend napoli_tutta.blend anteprime_tile\panoramica.png'
