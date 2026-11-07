// El cumplimiento por tipo de elemento y la tabla del dia en ese orden
// (pedido del usuario, 2026-10-08).
const test = require('node:test');
const assert = require('node:assert');
const L = require('../../static/logistica.logic.js');

const fila = (elemento, estado, cantReal, diff = 0) => ({elemento, estado, cantReal, diff});

test('el tipo es el elemento sin el sufijo de modulo o numero de Macao', () => {
  assert.equal(L.tipoDeElemento('COLUMNA M1'), 'COLUMNA');
  assert.equal(L.tipoDeElemento('Columna M5'), 'COLUMNA');
  assert.equal(L.tipoDeElemento('MURO M4'), 'MURO');
  assert.equal(L.tipoDeElemento('FINO DE TECHO'), 'FINO DE TECHO');
  assert.equal(L.tipoDeElemento('LOSA 2'), 'LOSA');
  assert.equal(L.tipoDeElemento(null), 'SIN ELEMENTO');
});

test('por elemento: las dos unidades, ordenado por m3', () => {
  const r = L.cumplimientoPorElemento([
    fila('LOSA', 'Cumplido', 30), fila('LOSA', 'Incumplido', 10),
    fila('COLUMNA M1', 'Incumplido', 50), fila('COLUMNA M5', 'Cumplido', 50),
    fila('MURO', 'Sin programación', 99),
  ]);
  assert.deepEqual(r.map(e => [e.tipo, e.pct, e.pctPedidos, e.m3]),
                   [['COLUMNA', 50, 50, 100], ['LOSA', 75, 50, 40]],
                   'lo que no se evalua no entra');
});

test('la tabla va en el orden del cuadro; dentro del tipo, incumplidos primero y el mas atrasado arriba', () => {
  const filas = [
    fila('LOSA', 'Cumplido', 30, -5), fila('COLUMNA M1', 'Cumplido', 60, 10),
    fila('LOSA', 'Incumplido', 10, 40), fila('COLUMNA M5', 'Incumplido', 50, 90),
    fila('COLUMNA M1', 'Incumplido', 5, 200), fila('MURO', 'Sin programación', 7),
  ];
  assert.deepEqual(L.ordenarPorElemento(filas).map(r => [L.tipoDeElemento(r.elemento), r.estado, r.diff]), [
    ['COLUMNA', 'Incumplido', 200], ['COLUMNA', 'Incumplido', 90], ['COLUMNA', 'Cumplido', 10],
    ['LOSA', 'Incumplido', 40], ['LOSA', 'Cumplido', -5],
    ['MURO', 'Sin programación', 0],
  ]);
});

test('la tabla del dia: incumplidos primero, despues cumplidos, y cada grupo por compania A-Z', () => {
  const f = (cliente, estado, horaProg = 600) => ({cliente, obraReal: 'OBRA', estado, horaProg});
  const filas = [f('ZETA SRL', 'Cumplido'), f('Beta', 'Sin despachar'), f('MACAO', 'Incumplido'),
                 f('alfa', 'Cumplido'), f('ÁGUILA', 'Incumplido', 900), f('Águila', 'Incumplido', 480),
                 f('Casa', 'Sin programación'), f('Delta', 'Cumplido')];
  assert.deepEqual(L.ordenarParaTablaDelDia(filas).map(r => [r.estado, r.cliente, r.horaProg]), [
    ['Incumplido', 'Águila', 480], ['Incumplido', 'ÁGUILA', 900], ['Incumplido', 'MACAO', 600],
    ['Cumplido', 'alfa', 600], ['Cumplido', 'Delta', 600], ['Cumplido', 'ZETA SRL', 600],
    ['Sin despachar', 'Beta', 600], ['Sin programación', 'Casa', 600],
  ]);
});
