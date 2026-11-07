// El filtro Bomba / Directo (pedido del usuario, 2026-10-13) y los nombres
// nuevos de las dos unidades.
const test = require('node:test');
const assert = require('node:assert');
const L = require('../../static/logistica.logic.js');

const fila = (bomba, estado, cantReal, extra = {}) =>
  ({cliente: 'C' + cantReal, bomba, estado, cantReal, cargues: 1, planta: 'Movil II',
    matchRows: [{ficha: 'F' + cantReal, cliente: 'C' + cantReal, cantidad: cantReal, planta: 'Movil II'}], ...extra});

const rows = [
  fila('310', 'Cumplido', 100),
  fila('45', 'Incumplido', 20),
  fila('Directo', 'Incumplido', 8),
  fila('Directo', 'Cumplido', 6),
  fila(undefined, 'Sin programación', 7),
];

test('cada fila es con bomba o directa; sin programacion no tiene servicio', () => {
  assert.deepEqual(rows.map(L.servicioDeFila), ['bomba', 'bomba', 'directo', 'directo', null]);
  assert.equal(L.servicioDeFila({bomba: '', estado: 'Cumplido'}), 'directo', 'bomba vacia es directo');
});

test('el filtro deja solo ese servicio, y sin filtro deja todo', () => {
  assert.equal(L.filtrarPorServicio(rows, 'bomba').length, 2);
  assert.equal(L.filtrarPorServicio(rows, 'directo').length, 2);
  assert.equal(L.filtrarPorServicio(rows, null), rows);
});

test('bomba y directo suman exactamente lo evaluado del total', () => {
  const tot = L.resumenDeCumplimiento(rows);
  const b = L.resumenDeCumplimiento(L.filtrarPorServicio(rows, 'bomba'));
  const d = L.resumenDeCumplimiento(L.filtrarPorServicio(rows, 'directo'));
  assert.equal(b.pedidos + d.pedidos, tot.pedidos);
  assert.equal(b.m3 + d.m3, tot.m3);
  assert.equal(b.pct, 83);           // 100 de 120 m3
  assert.equal(d.pctPedidos, 50);    // 1 de 2 entregas
});

test('los dias se conservan aunque queden vacios con el filtro', () => {
  const dias = [{fecha: '2026-10-01', results: rows}, {fecha: '2026-10-02', results: [fila('Directo', 'Cumplido', 5)]}];
  const conBomba = L.filtrarDiasPorServicio(dias, 'bomba');
  assert.deepEqual(conBomba.map(d => d.results.length), [2, 0]);
});

test('la comparacion con servicio saca el despacho de los camiones de esas entregas', () => {
  const dias = [{fecha: '2026-10-01', results: rows, cargue: rows.flatMap(r => r.matchRows),
                 motivos: new Map(), responsables: new Map()}];
  const [bomba] = L.comparacionPorDia(dias, null, 'bomba');
  assert.deepEqual(bomba.despacho, {m3: 120, cargues: 2, camiones: 2, clientes: 2});
  assert.equal(bomba.cumplimiento.pct, 83);
  const [todo] = L.comparacionPorDia(dias, null);
  assert.equal(todo.despacho.m3, 141, 'sin filtro sigue saliendo del cargue entero');
});

test('las dos unidades tienen sus nombres nuevos', () => {
  assert.equal(L.NOMBRE_PCT, 'Frecuencia de despacho');
  assert.equal(L.NOMBRE_PCT_PEDIDOS, 'Inicio de carga');
});
