fx_version 'cerulean'
game 'gta5'
lua54 'yes'

name 'napoli3d'
description 'Napoli in 3D (dati OpenStreetMap) costruita con Blender + Sollumz'
version '1.0.0'

-- Mappa personalizzata: tutto quello che sta in stream/ viene caricato dal gioco
this_is_a_map 'yes'
data_file 'DLC_ITYP_REQUEST' 'stream/nap_tipi.ytyp'

shared_scripts {
    'config.lua',
    'luoghi.lua',
}

client_script 'client.lua'

-- Mappa 3D interattiva di Napoli dentro il gioco (comando /mappanapoli)
ui_page 'html/index.html'

files {
    'html/index.html',
    'html/css/*.css',
    'html/js/*.js',
    'html/lib/*.js',
    'html/lib/*.css',
}
