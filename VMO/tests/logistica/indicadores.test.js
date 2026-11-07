// Indicadores (2026-10-28): metros bombeados por equipo y cumplimiento de
// tiempos de despacho (reportes del sistema) y metros transportados por camion
// (cargue con Macao), siempre separados por zona.
const test = require('node:test');
const assert = require('node:assert');
const L = require('../../static/logistica.logic.js');

// ---- lectores de los reportes ----
test('bombeo: una celda por equipo y dia, sin la fila de totales; el rango es el de las columnas', () => {
  const hojas = [{nombre: 'Metros bombeados por equipo', rows: [
    ['idEquipo', 'Equipo', 'Total', '10/01/2026', '10/02/2026', '10/03/2026'],
    ['B-44', 'Bom.44', 458, 207, 251, null],
    ['700', 'Alquilada', 30.5, 30.5, null, null],
    [null, null, 488.5, 237.5, 251, 0],
  ]}];
  const r = L.parseBombeoSheets(hojas);
  assert.deepEqual([r.desde, r.hasta], ['2026-10-01', '2026-10-03']);
  assert.deepEqual(r.filas, [
    {fecha: '2026-10-01', equipo: 'B-44', nombre: 'Bom.44', m3: 207},
    {fecha: '2026-10-02', equipo: 'B-44', nombre: 'Bom.44', m3: 251},
    {fecha: '2026-10-01', equipo: '700', nombre: 'Alquilada', m3: 30.5},
  ]);
});

test('tiempos: un renglon por pedido; una hora en 00:00 es que el sistema no la tiene', () => {
  // Fecha y horas como seriales de Excel, como las lee SheetJS sin cellDates.
  const s = (dia, h = 0, m = 0) => 46295 + dia + (h * 60 + m) / 1440;   // 46296 = 2026-10-01
  const hojas = [{nombre: 'x', rows: [
    ['OrdComp', 'Planta', 'Cliente', 'Fecha', 'Hora', 'HoraFin', 'DespachosIn', 'DespachosOut', 'Cantidad',
     'Total In', '% Cumplimiento', 'Logro', 'TotalDespachado', 'ViajesProgramados', 'ViajesEfectuados', 'DiferenciaViajes', 'Bomba'],
    ['00112596', 'SanIsidro', 'CIVILTEC', s(1), s(1, 8), s(1, 15), 5, 2, 60.5, 46, 76.03, 'NO', 60.5, 9, 7, -2, 40],
    ['00112750', 'Movil IV', 'ABREU', s(5), s(5, 9), s(5), 0, 2, 21, 0, 0, 'NO', 21, 3, 2, -1, 37],
  ]}];
  const r = L.parseTiemposSheets(hojas);
  assert.deepEqual([r.desde, r.hasta], ['2026-10-01', '2026-10-05']);
  assert.deepEqual(r.filas[0], {fecha: '2026-10-01', ordComp: '00112596', planta: 'SanIsidro', cliente: 'CIVILTEC',
    horaIni: 480, horaFin: 900, cantidad: 60.5, totalIn: 46, logro: 'NO', totalDespachado: 60.5,
    viajesProgramados: 9, viajesEfectuados: 7, bomba: '40'});
  assert.equal(r.filas[1].horaFin, null, 'HoraFin sin hora');
});

test('un Excel que no es el reporte devuelve null', () => {
  assert.equal(L.parseBombeoSheets([{nombre: 'x', rows: [['Ficha', 'Hora']]}]), null);
  assert.equal(L.parseTiemposSheets([{nombre: 'x', rows: [['Ficha', 'Hora']]}]), null);
});

// ---- calculos ----
const pedido = (o) => ({fecha: '2026-10-01', ordComp: null, planta: 'SanIsidro', cliente: 'ACME', horaIni: 480, horaFin: 900,
  cantidad: 10, totalIn: 10, logro: 'SI', totalDespachado: 10, viajesProgramados: 1, viajesEfectuados: 1, bomba: '44', ...o});

test('tiempos: m3 antes de la Hora Fin / m3 programados; sin Hora Fin y sin viajes van aparte', () => {
  const t = L.indicadoresDelPeriodo([], {tiempos: [
    pedido({cantidad: 60, totalIn: 45, logro: 'NO'}),
    pedido({cantidad: 40, totalIn: 40}),
    pedido({horaFin: null, totalIn: 0}),                    // sin Hora Fin
    pedido({viajesEfectuados: 0, totalDespachado: 0}),      // sin viajes
  ]}).tiempos;
  assert.equal(t.pct, 85);
  assert.deepEqual([t.n, t.logro, t.sin, t.sinViajes], [2, 1, 1, 1]);
});

test('tiempos: Macao II no entra; los otros clientes de Macao si', () => {
  const t = L.indicadoresDelPeriodo([], {tiempos: [
    pedido({cliente: 'MACAO ALTO RESORT S.R.L, (MACAO II, ESTRUCTURA)', totalIn: 0}),
    pedido({cliente: 'MACAO ALTO RESORT SRL (CEDIS)'}),
  ]}).tiempos;
  assert.deepEqual([t.n, t.pct], [1, 100]);
});

test('tiempos: "Sin dato" si menos de la mitad de los pedidos con viaje tiene Hora Fin', () => {
  const filas = [pedido({planta: 'Movil IV'}), pedido({planta: 'Movil IV', horaFin: null}), pedido({planta: 'Movil IV', horaFin: null}),
                 pedido({planta: 'SanIsidro'})];
  const t = L.indicadoresDelPeriodo([], {tiempos: filas}).tiempos;
  const pc = t.zonas.find(z => z.zona === 'Punta Cana'), sd = t.zonas.find(z => z.zona === 'Santo Domingo');
  assert.deepEqual([pc.hayDato, pc.n, pc.sin], [false, 1, 2]);
  assert.equal(pc.plantas[0].hayDato, false);
  assert.deepEqual([sd.hayDato, sd.pct], [true, 100]);
});

test('bombeo: tal cual el reporte, con la zona de cada equipo sacada del reporte de tiempos', () => {
  const b = L.indicadoresDelPeriodo([], {
    bombeo: [{fecha: '2026-10-01', equipo: 'B-44', nombre: 'Bom.44', m3: 207}, {fecha: '2026-10-02', equipo: 'B-44', nombre: 'Bom.44', m3: 251},
             {fecha: '2026-10-01', equipo: 'Tecno-420', nombre: 'Tecno-420', m3: 30}, {fecha: '2026-10-01', equipo: 'B-99', nombre: null, m3: 5}],
    tiempos: [pedido({bomba: '44', planta: 'SanIsidro'}), pedido({bomba: '420', planta: 'Movil VIII'})],
  }).bombeo;
  assert.deepEqual(b.equipos.map(e => [e.equipo, e.m3, e.dias, e.m3PorDia, e.zona]),
    [['B-44', 458, 2, 229, 'Santo Domingo'], ['Tecno-420', 30, 1, 30, 'Punta Cana'], ['B-99', 5, 1, 5, 'Sin zona']]);
  assert.deepEqual(b.zonas.map(z => [z.zona, z.m3, z.n]), [['Santo Domingo', 458, 1], ['Punta Cana', 30, 1], ['Sin zona', 5, 1]]);
  assert.equal(b.mediana, 118.5, 'mediana de 207, 251, 30 y 5');
});

// ---- camiones ----
const SUP = () => ({cargue: 15, calidad: 10, tolerancia: 30, trayecto: {}, zonaPlanta: {'SanIsidro': 'Santo Domingo', 'Movil VIII': 'Punta Cana'}});
const viaje = (ficha, planta, cantidad, cliente = 'ACME') => ({ficha, horaMin: 480, cliente, obra: 'OBRA', elemento: 'LOSA', planta, cantidad, conduce: null});
const dia = (fecha, cargue, cargueMacao = []) => ({fecha, assumptions: SUP(), state: {fecha, cargue, cargueMacao}});

test('camiones: por ficha m3/dias y viajes/dias; la zona es la suma de la columna / camiones', () => {
  const c = L.indicadoresDelPeriodo([
    dia('2026-10-01', [viaje('F-1', 'SanIsidro', 10), viaje('F-1', 'SanIsidro', 12), viaje('F-2', 'SanIsidro', 8)]),
    dia('2026-10-02', [viaje('F-1', 'SanIsidro', 14)], [viaje('E-9', 'Movil VIII', 7, 'MACAO ALTO RESORT SRL (CEDIS)')]),
  ], {}).camiones;
  const f1 = c.camiones.find(k => k.ficha === 'F-1');
  assert.deepEqual([f1.m3, f1.dias, f1.m3PorDia, f1.viajes, f1.viajesPorDia, f1.m3PorViaje], [36, 2, 18, 3, 1.5, 12]);
  const sd = c.zonas.find(z => z.zona === 'Santo Domingo');
  assert.deepEqual([sd.n, sd.sumaM3PorDia, sd.m3PorCamionDia, sd.sumaViajesPorDia, sd.viajesPorCamionDia], [2, 26, 13, 2.5, 1.25]);
  assert.deepEqual([c.n, c.m3, c.viajes, c.viajesMacao], [3, 51, 5, 1], 'Macao entra en camiones');
  assert.equal(c.zonas.find(z => z.zona === 'Punta Cana').camiones[0].ficha, 'E-9');
});

test('un camion que cargo en las dos zonas va en la que hizo mas viajes', () => {
  const c = L.indicadoresDelPeriodo([dia('2026-10-01', [viaje('F-1', 'SanIsidro', 10), viaje('F-1', 'SanIsidro', 10), viaje('F-1', 'Movil VIII', 10)])], {}).camiones;
  assert.deepEqual([c.camiones[0].zona, c.camiones[0].otraZona], ['Santo Domingo', 1]);
});

// ---- Macao en el cargue: se guarda, pero no entra al cumplimiento ----
test('el cargue guarda los viajes de Macao aparte y el cumplimiento no los ve', () => {
  const hojas = [{nombre: 'x', rows: [
    ['Ficha', 'Hora', 'Tiempo', 'Cliente', 'Conduce', 'Elemento', 'Planta', 'Direccion', 'Cantidad'],
    ['F-1', 46296 + 8 / 24, null, 'ACME', 'C1', 'LOSA', 'SanIsidro', 'OBRA: TORRE', 8],
    ['E-9', 46296 + 9 / 24, null, 'MACAO ALTO RESORT SRL (CEDIS)', 'C2', 'LOSA', 'Movil VIII', 'OBRA: PARMOL', 7],
    ['Carga Vacia', 46296 + 9 / 24, null, 'ACME', 'C3', 'LOSA', 'SanIsidro', 'OBRA: TORRE', 1],
  ]}];
  const p = L.parseCargueSheets(hojas);
  assert.deepEqual([p.rows.map(r => r.ficha), p.macao.map(r => r.ficha)], [['F-1'], ['E-9']]);
  const state = {fecha: '2026-10-01', programacion: [], cargue: p.rows, cargueMacao: p.macao, trayectoOverrides: new Map(),
                 observaciones: new Map(), responsables: new Map(), motivos: new Map(), cumplidosManuales: new Set()};
  const pay = L.payloadDelDia(state, {...SUP(), toleranciaAdelanto: 60, espaciamiento: 30}, '2026-10-01');
  assert.equal(pay.cargue_rows.length, 2, 'se guardan los dos');
  const vuelta = L.restaurarDia({fecha: '2026-10-01', supuestos: {cargue: 15, calidad: 10, tolerancia: 30, plantas: pay.plantas},
                                 programacion: [], cargue: pay.cargue_rows});
  assert.deepEqual(vuelta.state.cargue.map(r => r.ficha), ['F-1'], 'el cumplimiento sigue sin Macao');
  assert.deepEqual(vuelta.state.cargueMacao.map(r => r.ficha), ['E-9']);
});

test('sin datos no rompe', () => {
  const r = L.indicadoresDelPeriodo([], {});
  assert.deepEqual([r.bombeo.m3, r.camiones.n, r.camiones.m3PorCamionDia, r.tiempos.pct], [0, 0, null, null]);
});
