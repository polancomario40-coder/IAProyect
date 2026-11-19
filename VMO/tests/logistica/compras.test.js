// Compras: entregas en el plazo (2026-11-19). La lista de CBS "Tiempos de sol.
// compra" ya trae el objetivo de cada linea y si cumple: se copia tal cual.
const test = require('node:test');
const assert = require('node:assert');
const L = require('../../static/logistica.logic.js');

const ENC = ['Solicitud', 'Descripcion', 'FechaSolicitud', 'Aprobacion Sol', 'Dias Aprobacion', 'Fecha Sol. Cot.', 'Dias Sol. Cot.', 'FechaCotizacion',
  'Dias Cot.', 'FechaAnalisis', 'Dias Analisis Cot.', 'Fecha O/C', 'Dias O/C', 'Fecha Apr O/C', 'Dias Apr. O/C', 'UltimaRecepcion', 'Dias Recepcion',
  'TiempoTotal', 'Aplica', 'Objetivo', 'Cumple'];
const fila = (sol, oc, total, objetivo, cumple, aplica = 'SI') => [sol, 'TORNILLO', 46300, 46300, 0, 46300, 0, 46300, 0, 46300, 0, oc, 3, oc + 0.4, 0,
  oc + 4, 4, total, aplica, objetivo, cumple];
const linea = (fecha, solicitud, dias, objetivo, cumple, aplica = true) => ({fecha, solicitud, descripcion: 'X', fechaSolicitud: null, fechaRecepcion: null, dias, objetivo, aplica, cumple});

test('lee la lista: la fecha es la de la O/C, sin la fila de totales', () => {
  const rows = [ENC, fila('65833-1', 46342, 3, 15, 'SI'), fila('59781-33', 46325, 477, 30, 'NO'),
                ['', '', '', '', 4174, '', 1537, '', 1763, '', 6516, '', 15042, '', 957, '', 5645, 21644, '', 32749, '']];
  const r = L.parseComprasSheets([{nombre: 'x', rows}]);
  assert.deepStrictEqual([r.desde, r.hasta, r.filas.length], ['2026-10-30', '2026-11-16', 2]);
  assert.deepStrictEqual(r.filas[0], {fecha: '2026-11-16', solicitud: '65833-1', descripcion: 'TORNILLO', fechaSolicitud: '2026-10-05',
                                      fechaRecepcion: '2026-11-20', dias: 3, objetivo: 15, aplica: true, cumple: true});
  assert.strictEqual(r.filas[1].cumple, false);
  assert.strictEqual(L.parseComprasSheets([{nombre: 'x', rows: [['Fecha', 'Cliente']]}]), null);
});

test('cumple lo que CBS marca SI; las que no aplican no entran; por objetivo', () => {
  const k = L.comprasDelPeriodo([linea('2026-10-01', '1-1', 7, 30, true), linea('2026-10-01', '1-2', 40, 30, false),
                                 linea('2026-10-02', '2-1', 5, 15, true), linea('2026-10-02', '3-1', 9, 3, false),
                                 linea('2026-10-03', '4-1', 99, 30, false, false)]);
  assert.deepStrictEqual([k.n, k.cumplen, k.pct, k.noAplica, k.solicitudes, k.mediana], [4, 2, 50, 1, 3, 8]);
  assert.deepStrictEqual(k.objetivos.map(o => [o.objetivo, o.n, o.cumplen]), [[30, 2, 1], [15, 1, 1], [3, 1, 0]]);
  assert.deepStrictEqual(k.fallas.map(f => f.solicitud), ['1-2', '3-1']);
});

test('contra la meta: 80% o mas', () => {
  const base = {tiempos: {n: 0, zonas: []}, camiones: {zonas: []}};
  const m = L.metasDelPeriodo([], {...base, compras: {n: 1224, cumplen: 1076, pct: 87.9}});
  assert.deepStrictEqual([m.compras.valor, m.compras.cumple, m.compras.meta, m.compras.lineas], [88, true, 80, 1224]);
  assert.strictEqual(L.metasDelPeriodo([], base).compras.valor, null);
});

test('las filas del servidor (snake_case, 0/1) dan lo mismo', () => {
  const ind = L.indicadoresDelPeriodo([], {compras: [
    {fecha: '2026-10-01', orden: 0, solicitud: '1-1', descripcion: 'X', fecha_solicitud: '2026-09-28', fecha_recepcion: '2026-10-03', dias: 5, objetivo: 30, aplica: 1, cumple: 1},
    {fecha: '2026-10-01', orden: 1, solicitud: '1-2', descripcion: 'X', fecha_solicitud: '2026-09-01', fecha_recepcion: '2026-10-03', dias: 32, objetivo: 30, aplica: 1, cumple: 0}]});
  assert.deepStrictEqual([ind.compras.n, ind.compras.cumplen], [2, 1]);
});
