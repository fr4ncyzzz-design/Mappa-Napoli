// Dati della mappa: luoghi simbolo, quartieri e viste predefinite.
// Coordinate in [longitudine, latitudine].

window.CATEGORIE = {
  castelli: { nome: 'Castelli e palazzi', colore: '#c0392b', icona: '🏰' },
  chiese:   { nome: 'Chiese e arte sacra', colore: '#8e44ad', icona: '⛪' },
  musei:    { nome: 'Musei e sottosuolo', colore: '#2471a3', icona: '🏛️' },
  piazze:   { nome: 'Piazze e strade', colore: '#d68910', icona: '📍' },
  mare:     { nome: 'Mare e panorami', colore: '#148f77', icona: '🌊' },
  moderno:  { nome: 'Sport e Napoli moderna', colore: '#2e86c1', icona: '⚽' },
  dintorni: { nome: 'Dintorni', colore: '#6e2c00', icona: '🌋' }
};

window.LUOGHI = [
  // Castelli e palazzi
  { id: 'maschio-angioino', nome: 'Castel Nuovo (Maschio Angioino)', cat: 'castelli', coord: [14.2527, 40.8384],
    desc: 'La fortezza angioina del 1279, con il celebre arco di trionfo aragonese in marmo tra le due torri.' },
  { id: 'castel-ovo', nome: "Castel dell'Ovo", cat: 'castelli', coord: [14.2475, 40.8282],
    desc: "Il castello più antico della città, sull'isolotto di Megaride, dove secondo la leggenda Virgilio nascose un uovo magico." },
  { id: 'sant-elmo', nome: "Castel Sant'Elmo", cat: 'castelli', coord: [14.2390, 40.8437],
    desc: 'Fortezza a stella sulla collina del Vomero: dai suoi bastioni si vede tutta Napoli, il golfo e il Vesuvio.' },
  { id: 'palazzo-reale', nome: 'Palazzo Reale', cat: 'castelli', coord: [14.2502, 40.8363],
    desc: 'Residenza dei viceré spagnoli e poi dei Borbone, affacciata su Piazza del Plebiscito.' },
  { id: 'reggia-capodimonte', nome: 'Reggia e Bosco di Capodimonte', cat: 'castelli', coord: [14.2505, 40.8670],
    desc: 'La reggia borbonica che ospita il Museo di Capodimonte, circondata da un parco di 134 ettari.' },
  { id: 'castel-capuano', nome: 'Castel Capuano', cat: 'castelli', coord: [14.2640, 40.8530],
    desc: 'Castello normanno, per secoli sede dei tribunali di Napoli, accanto a Porta Capuana.' },

  // Chiese e arte sacra
  { id: 'duomo', nome: 'Duomo di Napoli', cat: 'chiese', coord: [14.2596, 40.8526],
    desc: 'La cattedrale di Santa Maria Assunta, dove si custodisce il sangue di San Gennaro.' },
  { id: 'gesu-nuovo', nome: 'Chiesa del Gesù Nuovo', cat: 'chiese', coord: [14.2502, 40.8483],
    desc: 'Riconoscibile per la facciata a bugne di piperno, in origine Palazzo Sanseverino.' },
  { id: 'santa-chiara', nome: 'Monastero di Santa Chiara', cat: 'chiese', coord: [14.2525, 40.8468],
    desc: 'Complesso gotico angioino con il famoso chiostro maiolicato.' },
  { id: 'sansevero', nome: 'Cappella Sansevero', cat: 'chiese', coord: [14.2547, 40.8494],
    desc: 'Custodisce il Cristo Velato di Giuseppe Sanmartino, capolavoro della scultura del Settecento.' },
  { id: 'san-domenico', nome: 'San Domenico Maggiore', cat: 'chiese', coord: [14.2545, 40.8490],
    desc: 'Basilica gotica dove studiò Tommaso d\'Aquino, con la sua piazza e la guglia.' },
  { id: 'san-gregorio', nome: 'San Gregorio Armeno', cat: 'chiese', coord: [14.2575, 40.8506],
    desc: 'La strada dei presepi: botteghe artigiane aperte tutto l\'anno.' },
  { id: 'pio-monte', nome: 'Pio Monte della Misericordia', cat: 'chiese', coord: [14.2595, 40.8517],
    desc: 'Conserva le Sette opere di Misericordia di Caravaggio.' },
  { id: 'san-francesco-paola', nome: 'San Francesco di Paola', cat: 'chiese', coord: [14.2483, 40.8357],
    desc: 'Basilica neoclassica ispirata al Pantheon, con il colonnato che abbraccia Piazza del Plebiscito.' },
  { id: 'certosa', nome: 'Certosa di San Martino', cat: 'chiese', coord: [14.2412, 40.8433],
    desc: 'Monastero barocco accanto a Sant\'Elmo, oggi museo con la collezione di presepi.' },

  // Musei e sottosuolo
  { id: 'mann', nome: 'Museo Archeologico Nazionale', cat: 'musei', coord: [14.2506, 40.8535],
    desc: 'Una delle più importanti collezioni di arte romana al mondo, con i tesori di Pompei ed Ercolano.' },
  { id: 'napoli-sotterranea', nome: 'Napoli Sotterranea', cat: 'musei', coord: [14.2569, 40.8513],
    desc: 'Da Piazza San Gaetano si scende a 40 metri, tra acquedotti greco-romani e rifugi antiaerei.' },
  { id: 'catacombe', nome: 'Catacombe di San Gennaro', cat: 'musei', coord: [14.2468, 40.8628],
    desc: 'Le catacombe paleocristiane più grandi dell\'Italia meridionale, nel Rione Sanità.' },
  { id: 'sanita', nome: 'Rione Sanità', cat: 'musei', coord: [14.2500, 40.8590],
    desc: 'Il quartiere di Totò, con la Basilica di Santa Maria della Sanità e il Palazzo dello Spagnolo.' },
  { id: 'galleria-umberto', nome: 'Galleria Umberto I', cat: 'musei', coord: [14.2496, 40.8384],
    desc: 'Galleria commerciale di fine Ottocento con la grande cupola in vetro e ferro.' },
  { id: 'san-carlo', nome: 'Teatro di San Carlo', cat: 'musei', coord: [14.2497, 40.8375],
    desc: 'Inaugurato nel 1737, è il teatro d\'opera attivo più antico d\'Europa.' },

  // Piazze e strade
  { id: 'plebiscito', nome: 'Piazza del Plebiscito', cat: 'piazze', coord: [14.2488, 40.8359],
    desc: 'La piazza più grande della città, tra Palazzo Reale e il colonnato di San Francesco di Paola.' },
  { id: 'spaccanapoli', nome: 'Spaccanapoli', cat: 'piazze', coord: [14.2560, 40.8490],
    desc: 'Il decumano inferiore che taglia in due il centro storico, patrimonio UNESCO.' },
  { id: 'via-toledo', nome: 'Via Toledo', cat: 'piazze', coord: [14.2480, 40.8430],
    desc: 'La strada dello shopping, da Piazza Dante a Piazza Trieste e Trento.' },
  { id: 'quartieri-spagnoli', nome: 'Quartieri Spagnoli', cat: 'piazze', coord: [14.2460, 40.8415],
    desc: 'Il reticolo di vicoli costruito nel Cinquecento per le guarnigioni spagnole.' },
  { id: 'murale-maradona', nome: 'Largo Maradona', cat: 'piazze', coord: [14.2453, 40.8411],
    desc: 'Il murale di Diego Armando Maradona nel cuore dei Quartieri Spagnoli.' },
  { id: 'piazza-dante', nome: 'Piazza Dante', cat: 'piazze', coord: [14.2500, 40.8490],
    desc: 'Il Foro Carolino del Vanvitelli, con la statua di Dante e Port\'Alba.' },
  { id: 'piazza-garibaldi', nome: 'Piazza Garibaldi', cat: 'piazze', coord: [14.2720, 40.8530],
    desc: 'La porta d\'ingresso della città, davanti alla Stazione Centrale.' },
  { id: 'porta-capuana', nome: 'Porta Capuana', cat: 'piazze', coord: [14.2666, 40.8536],
    desc: 'Porta rinascimentale delle mura aragonesi.' },
  { id: 'vanvitelli', nome: 'Piazza Vanvitelli (Vomero)', cat: 'piazze', coord: [14.2310, 40.8445],
    desc: 'Il cuore del Vomero, raggiungibile con tre funicolari.' },
  { id: 'stazione-toledo', nome: 'Stazione Toledo', cat: 'piazze', coord: [14.2487, 40.8432],
    desc: 'Una delle stazioni della metropolitana più belle d\'Europa, con il "Crater de Luz" blu.' },

  // Mare e panorami
  { id: 'lungomare', nome: 'Lungomare Caracciolo', cat: 'mare', coord: [14.2420, 40.8310],
    desc: 'La passeggiata sul mare più famosa, con vista su Castel dell\'Ovo e il Vesuvio.' },
  { id: 'villa-comunale', nome: 'Villa Comunale', cat: 'mare', coord: [14.2340, 40.8340],
    desc: 'Il parco storico di Chiaia, con l\'Acquario della Stazione Zoologica Anton Dohrn.' },
  { id: 'mergellina', nome: 'Mergellina', cat: 'mare', coord: [14.2170, 40.8300],
    desc: 'Porticciolo e chalet, punto di partenza degli aliscafi per le isole.' },
  { id: 'donn-anna', nome: "Palazzo Donn'Anna", cat: 'mare', coord: [14.2152, 40.8233],
    desc: 'Palazzo seicentesco incompiuto, costruito direttamente sul mare di Posillipo.' },
  { id: 'marechiaro', nome: 'Marechiaro', cat: 'mare', coord: [14.1940, 40.7950],
    desc: 'Il borgo di pescatori della canzone, con la "fenestella" sul mare.' },
  { id: 'gaiola', nome: 'Parco sommerso della Gaiola', cat: 'mare', coord: [14.1870, 40.7915],
    desc: 'Area marina protetta con resti archeologici romani sott\'acqua.' },
  { id: 'virgiliano', nome: 'Parco Virgiliano', cat: 'mare', coord: [14.1820, 40.7958],
    desc: 'Il belvedere in cima a Posillipo: da qui si vedono Nisida, Capri, Procida e Ischia.' },
  { id: 'floridiana', nome: 'Villa Floridiana', cat: 'mare', coord: [14.2300, 40.8410],
    desc: 'Villa neoclassica del Vomero con il Museo della Ceramica Duca di Martina.' },
  { id: 'beverello', nome: 'Porto - Molo Beverello', cat: 'mare', coord: [14.2557, 40.8363],
    desc: 'Il molo dei traghetti e degli aliscafi per Capri, Ischia, Procida e la Costiera.' },

  // Sport e Napoli moderna
  { id: 'stadio', nome: 'Stadio Diego Armando Maradona', cat: 'moderno', coord: [14.1931, 40.8280],
    desc: 'Lo stadio del Napoli a Fuorigrotta, intitolato a Maradona nel 2020.' },
  { id: 'oltremare', nome: "Mostra d'Oltremare", cat: 'moderno', coord: [14.1890, 40.8240],
    desc: 'Grande quartiere fieristico degli anni Trenta, con la Fontana dell\'Esedra.' },
  { id: 'centro-direzionale', nome: 'Centro Direzionale', cat: 'moderno', coord: [14.2840, 40.8580],
    desc: 'Il quartiere dei grattacieli progettato da Kenzo Tange: lo skyline moderno di Napoli.' },
  { id: 'albergo-poveri', nome: 'Real Albergo dei Poveri', cat: 'moderno', coord: [14.2640, 40.8610],
    desc: 'Uno dei più grandi edifici del Settecento europeo, con una facciata di 354 metri.' },
  { id: 'orto-botanico', nome: 'Orto Botanico', cat: 'moderno', coord: [14.2590, 40.8630],
    desc: 'Fondato nel 1807, uno dei più importanti orti botanici d\'Italia.' },

  // Dintorni
  { id: 'vesuvio', nome: 'Vesuvio', cat: 'dintorni', coord: [14.4261, 40.8213], zoom: 13, pitch: 60,
    desc: 'Il vulcano simbolo di Napoli, alto 1.281 metri. Il cratere si raggiunge a piedi dal versante di Ercolano.' },
  { id: 'solfatara', nome: 'Solfatara (Campi Flegrei)', cat: 'dintorni', coord: [14.1390, 40.8270], zoom: 14,
    desc: 'Il cratere dei Campi Flegrei a Pozzuoli, con fumarole e fanghi caldi.' },
  { id: 'nisida', nome: 'Isola di Nisida', cat: 'dintorni', coord: [14.1620, 40.7960], zoom: 14,
    desc: 'Piccola isola vulcanica collegata alla terraferma da un pontile, di fronte a Bagnoli.' }
];

// I 30 quartieri di Napoli (punto indicativo per l'etichetta)
window.QUARTIERI = [
  ['San Ferdinando', 14.2480, 40.8365], ['Chiaia', 14.2330, 40.8355], ['Posillipo', 14.2000, 40.8100],
  ['Vomero', 14.2300, 40.8455], ['Arenella', 14.2250, 40.8540], ['Montecalvario', 14.2450, 40.8420],
  ['San Giuseppe', 14.2520, 40.8440], ['Avvocata', 14.2460, 40.8510], ['Stella', 14.2500, 40.8580],
  ["San Carlo all'Arena", 14.2620, 40.8650], ['San Lorenzo', 14.2600, 40.8520], ['Vicaria', 14.2680, 40.8560],
  ['Mercato', 14.2700, 40.8480], ['Pendino', 14.2600, 40.8470], ['Porto', 14.2560, 40.8420],
  ['Fuorigrotta', 14.1950, 40.8270], ['Bagnoli', 14.1700, 40.8080], ['Soccavo', 14.1900, 40.8420],
  ['Pianura', 14.1700, 40.8600], ['Chiaiano', 14.2130, 40.8850], ['Scampia', 14.2350, 40.8980],
  ['Secondigliano', 14.2600, 40.8960], ['Piscinola-Marianella', 14.2250, 40.8930], ['Miano', 14.2480, 40.8830],
  ['San Pietro a Patierno', 14.2850, 40.8930], ['Poggioreale', 14.2850, 40.8630], ['Zona Industriale', 14.2950, 40.8540],
  ['Barra', 14.3150, 40.8440], ['San Giovanni a Teduccio', 14.3050, 40.8370], ['Ponticelli', 14.3400, 40.8550]
];

// Inquadrature predefinite
window.VISTE = {
  golfo:     { center: [14.2420, 40.8330], zoom: 13.6, pitch: 70, bearing: 95 },
  centro:    { center: [14.2560, 40.8495], zoom: 16.2, pitch: 62, bearing: -20 },
  dallalto:  { center: [14.2450, 40.8450], zoom: 13.1, pitch: 25, bearing: 0 },
  vesuvio:   { center: [14.3700, 40.8250], zoom: 12.4, pitch: 72, bearing: 100 },
  posillipo: { center: [14.2050, 40.8080], zoom: 14.2, pitch: 68, bearing: 40 }
};
