// Rotacion de cartera (2026-11-19): la lista de CBS "Solicitudes" (antiguedad
// de saldos) y la cuenta de la hoja de Creditos y Cobros, por zona.
const test = require('node:test');
const assert = require('node:assert');
const L = require('../../static/logistica.logic.js');

const ENCABEZADO = ['Moneda', 'Nombre', 'Factura', 'Fecha', 'Vencimiento', 'Total', 'No venc.', '30 dias', '60 dias', '90 dias', '120 dias+', 'Balance Final'];
const fila = (moneda, nombre, factura, tramos) => [moneda, nombre, factura, 46310, '', tramos.reduce((a, v) => a + v, 0),
  ...tramos, tramos.reduce((a, v) => a + v, 0)];
// Una factura por cliente; `tramos` en la moneda de la factura.
const corte = (filas, fecha = '2026-10-31', tasa = 60) => filas.map(([moneda, cliente, tramos]) => ({
  fecha, tasa, moneda, cliente, factura: 'FT-1', fechaFactura: '2026-10-01',
  ...Object.fromEntries(L.TRAMOS_CARTERA.map((t, i) => [t.clave, tramos[i]])), balance: tramos.reduce((a, v) => a + v, 0)}));
const sd = cliente => ({cliente, zona: 'Santo Domingo', trato: 'normal'});

test('lee Solicitudes: RD$ y US$, los cinco tramos, y deja afuera la fila de totales', () => {
  const rows = [ENCABEZADO,
    fila('RD$', 'ACME SRL', 'FT-00061555', [100, 50, 0, 0, 0]),
    fila('US$', 'BETA (PUNTA CANA)', 'FT-00061644', [10, 0, 0, 0, 5]),
    fila('RD$', 'ACME SRL', 'RC-00026957', [-20, 0, 0, 0, 0]),
    ['', '', '', '', '', '', '', '', '', '', '', 999999]];
  const l = L.parseCarteraSheets([{nombre: 'Solcitudes', rows}]);
  assert.strictEqual(l.filas.length, 3);
  assert.strictEqual(l.clientes, 2);
  assert.strictEqual(l.conDolares, true);
  assert.deepStrictEqual(l.filas[1], {moneda: 'US$', cliente: 'BETA (PUNTA CANA)', factura: 'FT-00061644', fechaFactura: '2026-10-15',
                                      no_venc: 10, d30: 0, d60: 0, d90: 0, d120: 5, balance: 15});
  assert.strictEqual(L.parseCarteraSheets([{nombre: 'otra', rows: [['Fecha', 'Cliente', 'm3']]}]), null);
});

test('la rotacion es la de la hoja de octubre: cada tramo por 30, 60, 90, 120 y 150 dias', () => {
  // Los totales de la hoja de Jose Antonio al 31/10/2026 (Santo Domingo, ya en RD$): 51.73 dias.
  const tramos = [143400265.08, 84232158.45, 30866027.35, 14545291.79, 2508459.21];
  const c = L.carteraDelPeriodo(corte([['RD$', 'TODO SD', tramos]]), [sd('TODO SD')]);
  const z = c.zonas.find(x => x.zona === 'Santo Domingo');
  assert.strictEqual(Math.round(z.rotacion * 100) / 100, 51.73);
  assert.strictEqual(c.zonas.find(x => x.zona === 'Punta Cana').rotacion, null);
});

test('los US$ pasan a RD$ con la tasa del corte', () => {
  const c = L.carteraDelPeriodo(corte([['RD$', 'A', [600, 0, 0, 0, 0]], ['US$', 'B', [0, 10, 0, 0, 0]]], '2026-10-31', 60),
                                [sd('A'), sd('B')]);
  const z = c.zonas[0];
  assert.deepStrictEqual(z.tramos, [600, 600, 0, 0, 0]);
  assert.strictEqual(z.rotacion, 45);   // (600×30 + 600×60) / 1200
  assert.strictEqual(c.clientes.find(x => x.cliente === 'B').saldo, 600);
});

test('gestion especial entra sin el tramo de 121 o mas; fuera no entra', () => {
  const filas = corte([['RD$', 'NORMAL', [100, 0, 0, 0, 0]], ['RD$', 'ESPECIAL', [100, 0, 0, 0, 900]], ['RD$', 'VIEJO', [0, 0, 0, 0, 500]]]);
  const c = L.carteraDelPeriodo(filas, [sd('NORMAL'), {cliente: 'ESPECIAL', zona: 'Santo Domingo', trato: 'especial'},
                                        {cliente: 'VIEJO', zona: null, trato: 'fuera'}]);
  const z = c.zonas[0];
  assert.deepStrictEqual(z.tramos, [200, 0, 0, 0, 0]);
  assert.strictEqual(z.rotacion, 30);
  assert.deepStrictEqual(c.especial, {n: 1, quitado: 900});
  assert.deepStrictEqual(c.fuera, {n: 1, saldo: 500});
});

test('Santo Domingo y Punta Cana por separado', () => {
  const c = L.carteraDelPeriodo(corte([['RD$', 'A', [100, 0, 0, 0, 0]], ['RD$', 'B', [0, 0, 0, 0, 100]]]),
                                [sd('A'), {cliente: 'B', zona: 'Punta Cana', trato: 'normal'}]);
  assert.deepStrictEqual(c.zonas.map(z => [z.zona, z.rotacion, z.clientes]), [['Santo Domingo', 30, 1], ['Punta Cana', 150, 1]]);
});

test('un cliente sin clasificar: por el nombre, por el cargue, o queda afuera', () => {
  const filas = corte([['RD$', 'NUEVO (PUNTA CANA)', [100, 0, 0, 0, 0]], ['US$', 'MACAO ALTO RESORT CANCHAS', [1, 0, 0, 0, 0]],
                       ['RD$', 'ERIMIL SRL', [0, 100, 0, 0, 0]], ['RD$', 'NADIE SRL', [0, 0, 100, 0, 0]]]);
  const c = L.carteraDelPeriodo(filas, [], new Map([['ERIMIL SRL', 'Santo Domingo']]));
  const de = n => c.clientes.find(x => x.cliente === n);
  assert.deepStrictEqual([de('NUEVO (PUNTA CANA)').zona, de('NUEVO (PUNTA CANA)').origen], ['Punta Cana', 'nombre']);
  assert.deepStrictEqual([de('MACAO ALTO RESORT CANCHAS').zona, de('MACAO ALTO RESORT CANCHAS').origen], ['Punta Cana', 'nombre']);
  assert.deepStrictEqual([de('ERIMIL SRL').zona, de('ERIMIL SRL').origen], ['Santo Domingo', 'cargue']);
  assert.deepStrictEqual([de('NADIE SRL').zona, de('NADIE SRL').trato], [null, null]);
  assert.deepStrictEqual(c.sinClasificar, {n: 1, saldo: 100});
  assert.strictEqual(c.automaticos, 3);
  // Lo guardado manda sobre el nombre.
  const g = L.carteraDelPeriodo(filas, [sd('NUEVO (PUNTA CANA)')]);
  assert.strictEqual(g.clientes.find(x => x.cliente === 'NUEVO (PUNTA CANA)').zona, 'Santo Domingo');
});

test('con varios cortes en las fechas se usa el ultimo', () => {
  const filas = [...corte([['RD$', 'A', [100, 0, 0, 0, 0]]], '2026-10-31'), ...corte([['RD$', 'A', [0, 100, 0, 0, 0]]], '2026-11-30')];
  const c = L.carteraDelPeriodo(filas, [sd('A')]);
  assert.strictEqual(c.corte, '2026-11-30');
  assert.deepStrictEqual(c.cortes, ['2026-10-31', '2026-11-30']);
  assert.strictEqual(c.zonas[0].rotacion, 60);
  assert.strictEqual(L.carteraDelPeriodo([], []).corte, null);
});

test('la zona de un cliente en el cargue es la de las plantas que suman mas m3', () => {
  const dia = (cargue) => ({state: {cargue, cargueMacao: []}, assumptions: {zonaPlanta: {SanIsidro: 'Santo Domingo', 'Movil IV': 'Punta Cana'}}});
  const z = L.zonasDeClientesDelCargue([dia([{cliente: 'Erimil SRL', planta: 'SanIsidro', cantidad: 9}, {cliente: 'Erimil SRL', planta: 'Movil IV', cantidad: 6}])]);
  assert.strictEqual(z.get('ERIMIL SRL'), 'Santo Domingo');
});

test('contra la meta: 55 dias o menos cumple, por zona', () => {
  const ind = {tiempos: {n: 0, zonas: []}, camiones: {zonas: []},
    cartera: {corte: '2026-10-31', zonas: [{zona: 'Santo Domingo', rotacion: 51.73, saldo: 1, clientes: 1},
                                           {zona: 'Punta Cana', rotacion: 66.95, saldo: 2, clientes: 1}]}};
  const m = L.metasDelPeriodo([], ind);
  assert.deepStrictEqual([m.carteraSD.valor, m.carteraSD.cumple, m.carteraPC.valor, m.carteraPC.cumple], [51.7, true, 67, false]);
  assert.strictEqual(m.carteraSD.meta, 55);
  const vacio = L.metasDelPeriodo([], {tiempos: {n: 0, zonas: []}, camiones: {zonas: []}});
  assert.deepStrictEqual([vacio.carteraSD.valor, vacio.carteraSD.cumple], [null, null]);
});
