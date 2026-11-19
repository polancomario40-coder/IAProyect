// Resistencia a compresion (2026-11-19): la lista de CBS "Batchada vs Roturas
// de Calidad". Solo cuentan las cargas con muestra; cumple si la rotura a 28
// dias es igual o mayor que el f'c.
const test = require('node:test');
const assert = require('node:assert');
const L = require('../../static/logistica.logic.js');

const ENC = ['Planta', 'Fecha', 'FichaCamion', 'Resistencia', 'Metros', 'Conduce', 'idCliente', 'Cliente', 'idProducto', 'Producto', 'Roturas7', 'Roturas28'];
const muestra = (fecha, planta, conduce, fc, r7, r28, cliente = 'ACME') => ({fecha, planta, conduce, cliente, producto: 'H', fc, r7, r28});

test('lee la lista: solo las cargas con muestra, sin la fila de totales, con el rango de todas las cargas', () => {
  const rows = [ENC,
    ['MOVIL VII', 46296.3, '', 350, 11, 'M200122790', 4592, 'TERRAMARE', '44859', 'HORMIGON 350', 391.08, 510.48],
    ['SanIsidro', 46297, '', 210, 9, 'SI00161537', 1164, 'A E', '44818', 'HORMIGON 210', 0, 0],
    ['SDN', 46298.4, '89', 210, 5, '00158816', 4758, 'FIDEICOMISO', '44808', 'HORMIGON 210', 180, 0],
    ['', '', '', 1475900, 40607, '', 24191862, '', '', '', 368435, 232206]];
  const r = L.parseRoturasSheets([{nombre: 'x', rows}]);
  assert.deepStrictEqual([r.desde, r.hasta, r.cargas], ['2026-10-01', '2026-10-03', 3]);
  assert.deepStrictEqual(r.filas.map(f => [f.fecha, f.planta, f.conduce, f.fc, f.r7, f.r28]), [
    ['2026-10-01', 'Movil VII', 'M200122790', 350, 391.08, 510.48],
    ['2026-10-03', 'SDN', '00158816', 210, 180, null]]);
  assert.strictEqual(L.parseRoturasSheets([{nombre: 'x', rows: [['Fecha', 'Cliente']]}]), null);
});

test('cumple si la rotura a 28 dias es igual o mayor que el fc; por zona', () => {
  const k = L.resistenciaDelPeriodo([
    muestra('2026-10-01', 'SanIsidro', 'A1', 210, 150, 210),     // justo el f'c: cumple
    muestra('2026-10-01', 'SanIsidro', 'A2', 210, 150, 209.9),   // apenas por debajo: no cumple
    muestra('2026-10-02', 'Movil VII', 'B1', 350, 300, 500),
    muestra('2026-10-02', 'Movil IV', 'B2', 280, 200, 300)]);
  assert.deepStrictEqual([k.n, k.cumplen, k.pct], [4, 3, 75]);
  assert.deepStrictEqual(k.zonas.map(z => [z.zona, z.n, z.cumplen]), [['Santo Domingo', 2, 1], ['Punta Cana', 2, 2]]);
  assert.deepStrictEqual(k.fallas.map(m => m.conduce), ['A2']);
  assert.deepStrictEqual(k.plantas.map(p => [p.planta, p.n]), [['SanIsidro', 2], ['Movil IV', 1], ['Movil VII', 1]]);
});

test('un conduce en dos cargas es una sola muestra; sin fc no cuenta; sin rotura a 28 dias espera', () => {
  const k = L.resistenciaDelPeriodo([
    muestra('2026-10-01', 'SDN', 'C1', 210, 150, 300), muestra('2026-10-01', 'SDN', 'C1', 210, 150, 300),
    muestra('2026-10-01', 'SDN', 'C2', 0, 150, 300),
    muestra('2026-11-10', 'SDN', 'C3', 210, 150, null)]);
  assert.deepStrictEqual([k.n, k.cumplen, k.pendientes, k.ultimoVaciado], [1, 1, 1, '2026-10-01']);
  const vacio = L.resistenciaDelPeriodo([muestra('2026-11-10', 'SDN', 'C3', 210, 150, null)]);
  assert.deepStrictEqual([vacio.n, vacio.pct, vacio.pendientes], [0, null, 1]);
});

test('contra la meta: 99% o mas, por zona', () => {
  const base = {tiempos: {n: 0, zonas: []}, camiones: {zonas: []}};
  const res = L.resistenciaDelPeriodo([muestra('2026-10-01', 'SDN', 'A', 210, 150, 220), muestra('2026-10-01', 'Movil VII', 'B', 210, 150, 200)]);
  const m = L.metasDelPeriodo([], {...base, resistencia: res});
  assert.deepStrictEqual([m.resistencia.valor, m.resistencia.cumple, m.resistencia.meta, m.resistencia.muestras], [50, false, 99, 2]);
  assert.deepStrictEqual(m.resistencia.zonas.map(z => [z.zona, z.valor, z.cumple]), [['Santo Domingo', 100, true], ['Punta Cana', 0, false]]);
  assert.strictEqual(L.metasDelPeriodo([], base).resistencia.valor, null);
});
