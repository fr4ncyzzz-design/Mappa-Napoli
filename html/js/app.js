(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // Configurazione
  // ---------------------------------------------------------------------------
  // Dentro FiveM la pagina gira come NUI e il gioco espone GetParentResourceName().
  var IN_FIVEM = typeof window.GetParentResourceName === 'function';
  var RISORSA = IN_FIVEM ? window.GetParentResourceName() : null;

  var STILE = 'https://tiles.openfreemap.org/styles/liberty';
  var DEM = 'https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{z}/{x}/{y}.png';
  var SATELLITE = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
  var ESAGERAZIONE = 1.2;

  // Palette napoletana: dal tufo al giallo napoletano fino al rosso pompeiano.
  var COLORI_GIORNO = ['interpolate', ['linear'], ['coalesce', ['get', 'render_height'], 0],
    0, '#efe3cf', 12, '#eccb92', 25, '#e3a868', 45, '#cf7d52', 80, '#a9483a', 140, '#7d3030'];
  var COLORI_NOTTE = ['interpolate', ['linear'], ['coalesce', ['get', 'render_height'], 0],
    0, '#3b3652', 12, '#5b4b6b', 30, '#9a7448', 60, '#dba95a', 120, '#ffe199'];

  var CIELO_GIORNO = {
    'sky-color': '#8cc4f0', 'horizon-color': '#f3e3c9', 'fog-color': '#f6ead8',
    'sky-horizon-blend': 0.6, 'horizon-fog-blend': 0.7, 'fog-ground-blend': 0.85, 'atmosphere-blend': 0.6
  };
  var CIELO_NOTTE = {
    'sky-color': '#0b1026', 'horizon-color': '#3a2d4f', 'fog-color': '#1a1730',
    'sky-horizon-blend': 0.5, 'horizon-fog-blend': 0.6, 'fog-ground-blend': 0.8, 'atmosphere-blend': 0.3
  };

  var $ = function (id) { return document.getElementById(id); };
  var body = document.body;

  if (IN_FIVEM) {
    body.classList.add('fivem', 'nascosta');
    $('chiudi-fivem').hidden = false;
  }
  if (window.matchMedia('(max-width: 720px)').matches) body.classList.add('pannello-chiuso');

  // ---------------------------------------------------------------------------
  // Mappa
  // ---------------------------------------------------------------------------
  var map = new maplibregl.Map({
    container: 'mappa',
    style: STILE,
    center: [14.25, 40.84],
    zoom: 11,
    pitch: 20,
    bearing: 0,
    maxPitch: 85,
    minZoom: 9,
    maxBounds: [[13.85, 40.6], [14.7, 41.1]],
    attributionControl: { compact: true },
    canvasContextAttributes: { antialias: true }
  });

  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
  map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-right');
  if (!IN_FIVEM) map.addControl(new maplibregl.FullscreenControl({ container: $('app') }), 'top-right');

  var caricata = false;
  var fattoreAltezza = 1;
  var notte = false;

  map.on('error', function (e) {
    console.error('[Napoli 3D]', e && e.error ? e.error : e);
    if (!caricata) {
      $('caricamento').hidden = true;
      var box = $('errore');
      box.hidden = false;
      box.innerHTML = '<strong>Impossibile caricare la mappa.</strong><br>' +
        'Serve una connessione a internet per scaricare edifici e rilievo di Napoli.';
    }
  });

  map.on('load', function () {
    caricata = true;
    costruisciNapoli();
    $('caricamento').hidden = true;
    $('errore').hidden = true;
    aggiornaInfo();
    // Nella versione web parte subito il volo d'ingresso; in FiveM all'apertura.
    if (!IN_FIVEM) introduzione();
  });

  function costruisciNapoli() {
    var stile = map.getStyle();
    var sorgente = Object.keys(stile.sources).filter(function (k) {
      return stile.sources[k].type === 'vector';
    })[0];
    var primoSimbolo = (stile.layers.filter(function (l) { return l.type === 'symbol'; })[0] || {}).id;

    // Sostituisco gli edifici dello stile base con la versione napoletana.
    stile.layers.forEach(function (l) {
      if (l['source-layer'] === 'building') map.removeLayer(l.id);
    });

    // Rilievo: terreno 3D + ombreggiatura
    map.addSource('dem', { type: 'raster-dem', tiles: [DEM], tileSize: 256, maxzoom: 15, encoding: 'terrarium' });
    map.addSource('dem-ombra', { type: 'raster-dem', tiles: [DEM], tileSize: 256, maxzoom: 15, encoding: 'terrarium' });

    map.addSource('satellite', {
      type: 'raster', tiles: [SATELLITE], tileSize: 256, maxzoom: 19,
      attribution: 'Immagini © Esri, Maxar, Earthstar Geographics'
    });
    map.addLayer({ id: 'satellite', type: 'raster', source: 'satellite',
      layout: { visibility: 'none' } }, primoSimbolo);

    map.addLayer({
      id: 'ombreggiatura', type: 'hillshade', source: 'dem-ombra',
      paint: {
        'hillshade-exaggeration': 0.35,
        'hillshade-shadow-color': '#5a4632',
        'hillshade-highlight-color': '#fff6e6',
        'hillshade-accent-color': '#7a6650'
      }
    }, primoSimbolo);

    map.addLayer({
      id: 'edifici-3d',
      type: 'fill-extrusion',
      source: sorgente,
      'source-layer': 'building',
      minzoom: 13,
      filter: ['!=', ['get', 'hide_3d'], true],
      paint: {
        'fill-extrusion-color': COLORI_GIORNO,
        'fill-extrusion-height': altezza('render_height', 8),
        'fill-extrusion-base': altezza('render_min_height', 0),
        'fill-extrusion-opacity': 0.95,
        'fill-extrusion-vertical-gradient': true
      }
    }, primoSimbolo);

    map.setTerrain({ source: 'dem', exaggeration: ESAGERAZIONE });
    map.setSky(CIELO_GIORNO);
    map.setLight({ anchor: 'viewport', color: '#ffffff', intensity: 0.45, position: [1.5, 210, 35] });

    creaMarcatori();
    creaQuartieri();

    map.on('click', 'edifici-3d', function (e) {
      if (!e.features || !e.features.length) return;
      var p = e.features[0].properties;
      var h = Math.round(p.render_height || 0);
      var piani = h ? Math.max(1, Math.round(h / 3.2)) : null;
      new maplibregl.Popup({ offset: 8, className: 'popup-edificio' })
        .setLngLat(e.lngLat)
        .setHTML('<strong>Edificio</strong><br>Altezza: ' + (h ? h + ' m' : 'n.d.') +
          (piani ? '<br>Circa ' + piani + (piani === 1 ? ' piano' : ' piani') : ''))
        .addTo(map);
    });
    map.on('mouseenter', 'edifici-3d', function () { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'edifici-3d', function () { map.getCanvas().style.cursor = ''; });
  }

  function altezza(campo, predefinito) {
    return ['*', fattoreAltezza, ['coalesce', ['get', campo], predefinito]];
  }

  function introduzione() {
    vola(VISTE.golfo, 6000);
  }

  function vola(vista, durata) {
    map.flyTo({
      center: vista.center, zoom: vista.zoom, pitch: vista.pitch, bearing: vista.bearing,
      duration: durata || 4000, essential: true, curve: 1.3
    });
  }

  // ---------------------------------------------------------------------------
  // Luoghi simbolo
  // ---------------------------------------------------------------------------
  var marcatori = {};
  var popupAttivo = null;

  function creaMarcatori() {
    LUOGHI.forEach(function (l) {
      var cat = CATEGORIE[l.cat];
      var el = document.createElement('button');
      el.className = 'marcatore';
      el.style.setProperty('--colore', cat.colore);
      el.setAttribute('aria-label', l.nome);
      el.innerHTML = '<span class="pallino">' + cat.icona + '</span><span class="etichetta">' + l.nome + '</span>';
      el.addEventListener('click', function (ev) { ev.stopPropagation(); vaiAlLuogo(l.id); });
      marcatori[l.id] = new maplibregl.Marker({ element: el, anchor: 'bottom' }).setLngLat(l.coord).addTo(map);
    });
  }

  function creaQuartieri() {
    QUARTIERI.forEach(function (q) {
      var el = document.createElement('div');
      el.className = 'quartiere';
      el.textContent = q[0];
      new maplibregl.Marker({ element: el }).setLngLat([q[1], q[2]]).addTo(map);
    });
  }

  function trovaLuogo(id) {
    return LUOGHI.filter(function (l) { return l.id === id; })[0];
  }

  function vaiAlLuogo(id, durata) {
    var l = trovaLuogo(id);
    if (!l) return;
    fermaOrbita();
    map.flyTo({
      center: l.coord, zoom: l.zoom || 16.8, pitch: l.pitch || 65,
      bearing: map.getBearing() + 30, duration: durata || 4500, essential: true
    });
    mostraPopup(l);
    document.querySelectorAll('.voce-luogo').forEach(function (b) {
      b.classList.toggle('attiva', b.dataset.id === id);
    });
    if (window.matchMedia('(max-width: 720px)').matches) body.classList.add('pannello-chiuso');
  }

  function mostraPopup(l) {
    if (popupAttivo) popupAttivo.remove();
    var cat = CATEGORIE[l.cat];
    popupAttivo = new maplibregl.Popup({ offset: 34, maxWidth: '280px', className: 'popup-luogo' })
      .setLngLat(l.coord)
      .setHTML('<span class="cat" style="color:' + cat.colore + '">' + cat.icona + ' ' + cat.nome + '</span>' +
        '<h3>' + l.nome + '</h3><p>' + l.desc + '</p>' +
        (IN_FIVEM ? '<button class="vai" data-id="' + l.id + '">Vai qui in gioco</button>' : ''))
      .addTo(map);
    var vai = popupAttivo.getElement().querySelector('.vai');
    if (vai) vai.addEventListener('click', function () { postFivem('vai', { id: l.id }); });
  }

  function costruisciLista() {
    var contenitore = $('lista-luoghi');
    Object.keys(CATEGORIE).forEach(function (k) {
      var cat = CATEGORIE[k];
      var gruppo = document.createElement('details');
      gruppo.open = k === 'castelli';
      gruppo.innerHTML = '<summary><span class="punto" style="background:' + cat.colore + '"></span>' +
        cat.icona + ' ' + cat.nome + '</summary>';
      LUOGHI.filter(function (l) { return l.cat === k; }).forEach(function (l) {
        var b = document.createElement('button');
        b.className = 'voce-luogo';
        b.dataset.id = l.id;
        b.textContent = l.nome;
        b.addEventListener('click', function () { fermaTour(); vaiAlLuogo(l.id); });
        gruppo.appendChild(b);
      });
      contenitore.appendChild(gruppo);
    });
  }
  costruisciLista();

  // ---------------------------------------------------------------------------
  // Ricerca: prima tra i luoghi simbolo, poi su OpenStreetMap (Nominatim)
  // ---------------------------------------------------------------------------
  $('cerca').addEventListener('submit', function (e) {
    e.preventDefault();
    var q = $('cerca-testo').value.trim();
    var lista = $('risultati');
    if (!q) { lista.hidden = true; return; }
    var qn = normalizza(q);
    var locali = LUOGHI.filter(function (l) { return normalizza(l.nome).indexOf(qn) !== -1; })
      .map(function (l) { return { nome: l.nome, coord: l.coord, id: l.id }; });
    mostraRisultati(locali, true);

    var url = 'https://nominatim.openstreetmap.org/search?format=jsonv2&limit=6&accept-language=it' +
      '&bounded=1&viewbox=14.10,40.93,14.40,40.77&q=' + encodeURIComponent(q);
    fetch(url).then(function (r) { return r.json(); }).then(function (dati) {
      var remoti = dati.map(function (d) {
        return { nome: d.display_name.split(',').slice(0, 3).join(','), coord: [+d.lon, +d.lat] };
      });
      mostraRisultati(locali.concat(remoti), false);
    }).catch(function () {
      if (!locali.length) mostraRisultati([], false);
    });
  });

  function mostraRisultati(voci, inCorso) {
    var lista = $('risultati');
    lista.innerHTML = '';
    lista.hidden = false;
    if (!voci.length) {
      lista.innerHTML = '<li class="vuoto">' + (inCorso ? 'Cerco…' : 'Nessun risultato a Napoli') + '</li>';
      return;
    }
    voci.forEach(function (v) {
      var li = document.createElement('li');
      var b = document.createElement('button');
      b.textContent = v.nome;
      b.addEventListener('click', function () {
        lista.hidden = true;
        fermaTour();
        if (v.id) return vaiAlLuogo(v.id);
        fermaOrbita();
        map.flyTo({ center: v.coord, zoom: 17, pitch: 60, duration: 4000, essential: true });
        if (popupAttivo) popupAttivo.remove();
        popupAttivo = new maplibregl.Popup({ offset: 10 }).setLngLat(v.coord)
          .setHTML('<strong>' + v.nome.replace(/</g, '&lt;') + '</strong>').addTo(map);
      });
      li.appendChild(b);
      lista.appendChild(li);
    });
  }

  function normalizza(s) {
    return s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  }

  // ---------------------------------------------------------------------------
  // Opzioni
  // ---------------------------------------------------------------------------
  document.querySelectorAll('[data-vista]').forEach(function (b) {
    b.addEventListener('click', function () {
      fermaTour();
      vola(VISTE[b.dataset.vista]);
    });
  });

  $('opt-notte').addEventListener('change', function (e) { impostaNotte(e.target.checked); });

  function impostaNotte(attiva) {
    notte = attiva;
    body.classList.toggle('notte', attiva);
    if (!caricata) return;
    map.setPaintProperty('edifici-3d', 'fill-extrusion-color', attiva ? COLORI_NOTTE : COLORI_GIORNO);
    map.setSky(attiva ? CIELO_NOTTE : CIELO_GIORNO);
    map.setLight(attiva
      ? { anchor: 'viewport', color: '#ffd9a0', intensity: 0.25, position: [1.5, 30, 60] }
      : { anchor: 'viewport', color: '#ffffff', intensity: 0.45, position: [1.5, 210, 35] });
  }

  $('opt-satellite').addEventListener('change', function (e) {
    if (caricata) map.setLayoutProperty('satellite', 'visibility', e.target.checked ? 'visible' : 'none');
  });

  $('opt-rilievo').addEventListener('change', function (e) {
    if (!caricata) return;
    map.setTerrain(e.target.checked ? { source: 'dem', exaggeration: ESAGERAZIONE } : null);
    map.setLayoutProperty('ombreggiatura', 'visibility', e.target.checked ? 'visible' : 'none');
  });

  $('opt-quartieri').addEventListener('change', function (e) {
    body.classList.toggle('mostra-quartieri', e.target.checked);
  });
  $('opt-luoghi').addEventListener('change', function (e) {
    body.classList.toggle('nascondi-luoghi', !e.target.checked);
  });

  $('opt-altezza').addEventListener('input', function (e) {
    fattoreAltezza = parseFloat(e.target.value);
    $('val-altezza').textContent = '×' + fattoreAltezza.toFixed(1);
    if (!caricata) return;
    map.setPaintProperty('edifici-3d', 'fill-extrusion-height', altezza('render_height', 8));
    map.setPaintProperty('edifici-3d', 'fill-extrusion-base', altezza('render_min_height', 0));
  });

  $('chiudi-pannello').addEventListener('click', function () { body.classList.add('pannello-chiuso'); });
  $('apri-pannello').addEventListener('click', function () { body.classList.remove('pannello-chiuso'); });

  // ---------------------------------------------------------------------------
  // Rotazione automatica
  // ---------------------------------------------------------------------------
  var orbitaId = null;

  function avviaOrbita() {
    if (orbitaId) return;
    var ultimo = performance.now();
    function passo(t) {
      var dt = Math.min(64, t - ultimo);
      ultimo = t;
      map.setBearing(map.getBearing() + dt * 0.006);
      orbitaId = requestAnimationFrame(passo);
    }
    orbitaId = requestAnimationFrame(passo);
  }

  function fermaOrbita() {
    if (orbitaId) cancelAnimationFrame(orbitaId);
    orbitaId = null;
    $('opt-orbita').checked = false;
  }

  $('opt-orbita').addEventListener('change', function (e) {
    if (e.target.checked) { fermaTour(); avviaOrbita(); } else fermaOrbita();
  });

  // ---------------------------------------------------------------------------
  // Tour guidato
  // ---------------------------------------------------------------------------
  var TAPPE = ['castel-ovo', 'plebiscito', 'san-carlo', 'galleria-umberto', 'maschio-angioino', 'murale-maradona',
    'gesu-nuovo', 'santa-chiara', 'sansevero', 'san-gregorio', 'napoli-sotterranea', 'duomo', 'mann',
    'catacombe', 'reggia-capodimonte', 'sant-elmo', 'vanvitelli', 'lungomare', 'mergellina', 'marechiaro',
    'virgiliano', 'stadio', 'centro-direzionale', 'vesuvio'];
  var tourAttivo = 0; // contatore: ogni avvio invalida i timer del tour precedente
  var tourTimer = null;

  function avviaTour() {
    fermaOrbita();
    var mio = ++tourAttivo;
    var i = 0;
    function prossima() {
      if (mio !== tourAttivo) return;
      var id = TAPPE[i % TAPPE.length];
      i++;
      vaiAlLuogo(id, 6000);
      map.once('moveend', function () {
        if (mio !== tourAttivo) return;
        tourTimer = setTimeout(prossima, 4500);
      });
    }
    prossima();
  }

  function fermaTour() {
    tourAttivo++;
    clearTimeout(tourTimer);
    $('opt-tour').checked = false;
  }

  $('opt-tour').addEventListener('change', function (e) {
    if (e.target.checked) avviaTour(); else fermaTour();
  });

  // Qualsiasi gesto dell'utente sulla mappa interrompe tour e rotazione.
  ['dragstart', 'wheel', 'touchstart', 'pitchstart', 'rotatestart'].forEach(function (ev) {
    map.on(ev, function (e) {
      if (e.originalEvent) { fermaTour(); fermaOrbita(); }
    });
  });

  // ---------------------------------------------------------------------------
  // Informazioni sulla posizione
  // ---------------------------------------------------------------------------
  function aggiornaInfo() {
    var c = map.getCenter();
    var testo = c.lat.toFixed(4) + '° N, ' + c.lng.toFixed(4) + '° E · zoom ' + map.getZoom().toFixed(1);
    if (caricata && map.getTerrain()) {
      var quota = map.queryTerrainElevation(c);
      if (quota !== null && quota !== undefined) {
        testo += ' · quota ' + Math.max(0, Math.round(quota / ESAGERAZIONE)) + ' m s.l.m.';
      }
    }
    $('info').textContent = testo;
  }
  map.on('moveend', aggiornaInfo);

  // ---------------------------------------------------------------------------
  // Integrazione FiveM (NUI)
  // ---------------------------------------------------------------------------
  var primaApertura = true;

  function postFivem(evento, dati) {
    if (!IN_FIVEM) return;
    fetch('https://' + RISORSA + '/' + evento, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=UTF-8' },
      body: JSON.stringify(dati || {})
    }).catch(function () {});
  }

  function chiudiFivem() { postFivem('chiudi'); }

  window.addEventListener('message', function (e) {
    var d = e.data || {};
    if (d.azione === 'apri') {
      body.classList.remove('nascosta');
      map.resize();
      if (d.notte !== undefined) { $('opt-notte').checked = !!d.notte; impostaNotte(!!d.notte); }
      if (d.luogo) vaiAlLuogo(d.luogo);
      else if (primaApertura && caricata) introduzione();
      primaApertura = false;
    } else if (d.azione === 'chiudi') {
      body.classList.add('nascosta');
      fermaTour();
      fermaOrbita();
    }
  });

  $('chiudi-fivem').addEventListener('click', chiudiFivem);
  document.addEventListener('keyup', function (e) {
    if (e.key === 'Escape' && IN_FIVEM) chiudiFivem();
  });

  // Accesso da console / altri script della pagina
  window.Napoli3D = { mappa: map, vaiAlLuogo: vaiAlLuogo, vola: vola, notte: impostaNotte };
})();
