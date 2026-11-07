// La pestana Comparacion (pedido del usuario, 2026-10-12): un renglon por dia,
// con el mismo calculo que el resto del sitio.
const test = require('node:test');
const assert = require('node:assert');
const L = require('../../static/logistica.logic.js');

const motivos = new Map([['k1', 'TRAFICO']]);
const responsables = new Map([['k1', 'VMO']]);
const dias = [
  {fecha: '2026-10-02', motivos, responsables,
   cargue: [
     {ficha: 'A1', cliente: 'Zeta', planta: 'Movil II', cantidad: 8},
     {ficha: 'A1', cliente: 'Zeta', planta: 'Movil II', cantidad: 8},
     {ficha: 'B2', cliente: 'alfa', planta: 'Movil VIII', cantidad: 10},
   ],
   results: [
     {rowKey: 'k1', cliente: 'Zeta', obraReal: 'Torre', planta: 'Movil II', zona: 'Santo Domingo',
      estado: 'Incumplido', cantReal: 16, cargues: 2, horaProg: 600, diff: 40, observacion: 'tapon'},
     {rowKey: 'k2', cliente: 'alfa', obraReal: 'Hotel', planta: 'Movil VIII', zona: 'Punta Cana',
      estado: 'Cumplido', cantReal: 10, cargues: 1, horaProg: 480, diff: -5},
     {rowKey: 'k3', cliente: 'Beta', obraProg: 'Casa', planta: null, zona: 'Punta Cana',
      estado: 'Sin despachar', cantReal: 0, cargues: 0, horaProg: 700, diff: null},
   ]},
  {fecha: '2026-10-01', motivos: new Map(), responsables: new Map(), cargue: [], results: []},
];

test('un renglon por dia, de la fecha mas vieja a la mas nueva', () => {
  assert.deepEqual(L.comparacionPorDia(dias, null).map(d => d.fecha), ['2026-10-01', '2026-10-02']);
});

test('el despacho sale del cargue y el porcentaje del mismo resumen que el resto del sitio', () => {
  const d = L.comparacionPorDia(dias, null)[1];
  assert.deepEqual(d.despacho, {m3: 26, cargues: 3, camiones: 2, clientes: 2});
  assert.deepEqual(d.cumplimiento, L.resumenDeCumplimiento(dias[0].results));
  assert.equal(d.cumplimiento.pct, 38);          // 10 de 26 m3
  assert.equal(d.cumplimiento.pctPedidos, 50);   // 1 de 2 entregas
  assert.equal(d.incumplidas, 1);
  assert.equal(d.sinDespachar, 1);
});

test('un dia sin nada da porcentajes nulos, no cero', () => {
  const d = L.comparacionPorDia(dias, null)[0];
  assert.equal(d.cumplimiento.pct, null);
  assert.equal(d.cumplimiento.pctPedidos, null);
  assert.deepEqual(d.despacho, {m3: 0, cargues: 0, camiones: 0, clientes: 0});
});

test('los incumplidos traen responsable, motivo y observacion del dia', () => {
  const [inc] = L.comparacionPorDia(dias, null)[1].incumplidos;
  assert.equal(inc.cliente, 'Zeta');
  assert.equal(inc.obra, 'Torre');
  assert.equal(inc.zona, 'Santo Domingo');
  assert.equal(inc.responsable, 'VMO');
  assert.equal(inc.motivo, 'TRAFICO');
  assert.equal(inc.observacion, 'tapon');
  assert.equal(inc.m3, 16);
});

test('por zona: el cargue y las entregas se filtran juntos, y las dos zonas suman el General', () => {
  const sd = L.comparacionPorDia(dias, L.PREFIJO_ZONA + 'Santo Domingo')[1];
  const pc = L.comparacionPorDia(dias, L.PREFIJO_ZONA + 'Punta Cana')[1];
  const gen = L.comparacionPorDia(dias, null)[1];
  assert.deepEqual(sd.despacho, {m3: 16, cargues: 2, camiones: 1, clientes: 1});
  assert.equal(sd.cumplimiento.pct, 0);
  assert.equal(pc.cumplimiento.pct, 100);
  assert.equal(pc.sinDespachar, 1, 'lo no despachado cae a la zona del calculo');
  assert.equal(sd.despacho.m3 + pc.despacho.m3, gen.despacho.m3);
  assert.equal(sd.despacho.cargues + pc.despacho.cargues, gen.despacho.cargues);
});

test('los incumplidos van por compania, sin importar mayusculas, y despues por hora', () => {
  const d = {fecha: '2026-10-03', motivos: new Map(), responsables: new Map(), cargue: [], results: [
    {rowKey: 'a', cliente: 'zeta', estado: 'Incumplido', horaProg: 500},
    {rowKey: 'b', cliente: 'Alfa', estado: 'Incumplido', horaProg: 900},
    {rowKey: 'c', cliente: 'alfa', estado: 'Incumplido', horaProg: 400},
  ]};
  assert.deepEqual(L.comparacionPorDia([d], null)[0].incumplidos.map(i => i.horaProg), [400, 900, 500]);
});
