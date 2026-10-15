-- Napoli 3D: teletrasporto, spawn, icone dei luoghi simbolo e mappa 3D in gioco

local function trovaLuogo(testo)
    if not testo or testo == '' then testo = Config.LuogoPredefinito end
    testo = string.lower(testo)
    for _, l in ipairs(Luoghi) do
        if l.id == testo then return l end
    end
    for _, l in ipairs(Luoghi) do
        if string.find(string.lower(l.nome), testo, 1, true) or string.find(l.id, testo, 1, true) then
            return l
        end
    end
    return nil
end

local function messaggio(testo)
    TriggerEvent('chat:addMessage', { args = { '^3Napoli 3D', testo } })
end

-- Teletrasporta il giocatore (e il veicolo) aspettando che la collisione sia caricata
local function vaiA(coord)
    local ped = PlayerPedId()
    local entita = ped
    local veicolo = GetVehiclePedIsIn(ped, false)
    if veicolo ~= 0 and GetPedInVehicleSeat(veicolo, -1) == ped then entita = veicolo end

    DoScreenFadeOut(400)
    while not IsScreenFadedOut() do Wait(0) end

    FreezeEntityPosition(entita, true)
    SetEntityCoordsNoOffset(entita, coord.x, coord.y, coord.z + 1.0, false, false, false)
    local inizio = GetGameTimer()
    while not HasCollisionLoadedAroundEntity(entita) and GetGameTimer() - inizio < 8000 do
        RequestCollisionAtCoord(coord.x, coord.y, coord.z)
        Wait(0)
    end
    -- Cerca il suolo vero (il punto salvato è indicativo)
    local trovato, suolo = GetGroundZFor_3dCoord(coord.x, coord.y, coord.z + 50.0, false)
    if trovato then
        SetEntityCoordsNoOffset(entita, coord.x, coord.y, suolo + 0.5, false, false, false)
    end
    FreezeEntityPosition(entita, false)
    DoScreenFadeIn(600)
end

RegisterCommand(Config.Comando, function(_, args)
    local testo = table.concat(args, ' ')
    if testo == 'lista' then
        local nomi = {}
        for _, l in ipairs(Luoghi) do nomi[#nomi + 1] = l.id end
        messaggio('Luoghi: ' .. table.concat(nomi, ', '))
        return
    end
    local luogo = trovaLuogo(testo)
    if not luogo then
        messaggio('Luogo non trovato. Scrivi /' .. Config.Comando .. ' lista')
        return
    end
    vaiA(luogo.coord)
    messaggio('Benvenuto a ' .. luogo.nome .. '!')
end, false)

TriggerEvent('chat:addSuggestion', '/' .. Config.Comando, 'Vai a Napoli', {
    { name = 'luogo', help = 'es. plebiscito, duomo, lungomare, vesuvio, lista' }
})

-- Spawn a Napoli
if Config.SpawnANapoli then
    AddEventHandler('playerSpawned', function()
        local luogo = trovaLuogo(Config.LuogoPredefinito)
        if luogo then vaiA(luogo.coord) end
    end)
end

-- Icone dei luoghi simbolo
local SPRITE = { castelli = 176, chiese = 305, musei = 176, piazze = 162, mare = 410, moderno = 546, dintorni = 436 }
local COLORE = { castelli = 1, chiese = 27, musei = 3, piazze = 5, mare = 38, moderno = 26, dintorni = 47 }

CreateThread(function()
    if not Config.Blip then return end
    for _, l in ipairs(Luoghi) do
        local b = AddBlipForCoord(l.coord.x, l.coord.y, l.coord.z)
        SetBlipSprite(b, SPRITE[l.cat] or 1)
        SetBlipColour(b, COLORE[l.cat] or 0)
        SetBlipScale(b, 0.8)
        SetBlipAsShortRange(b, true)
        BeginTextCommandSetBlipName('STRING')
        AddTextComponentSubstringPlayerName(l.nome)
        EndTextCommandSetBlipName(b)
    end
end)

-- Mappa 3D di Napoli (pagina web dentro il gioco)
local mappaAperta = false

local function apriMappa(stato)
    mappaAperta = stato
    SetNuiFocus(stato, stato)
    SendNUIMessage({ azione = stato and 'apri' or 'chiudi', notte = GetClockHours() >= 20 or GetClockHours() < 6 })
end

RegisterCommand(Config.ComandoMappa, function() apriMappa(not mappaAperta) end, false)
RegisterKeyMapping(Config.ComandoMappa, 'Mappa 3D di Napoli', 'keyboard', Config.TastoMappa)

RegisterNUICallback('chiudi', function(_, cb)
    apriMappa(false)
    cb('ok')
end)

-- Dalla mappa 3D: "Vai qui" su un luogo simbolo
RegisterNUICallback('vai', function(dati, cb)
    cb('ok')
    local luogo = trovaLuogo(dati and dati.id)
    if luogo then
        apriMappa(false)
        vaiA(luogo.coord)
    end
end)

AddEventHandler('onResourceStop', function(nome)
    if nome == GetCurrentResourceName() and mappaAperta then SetNuiFocus(false, false) end
end)
