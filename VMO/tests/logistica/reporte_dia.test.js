// El Reporte del dia (2026-10-15): los numeros del PDF salen de
// computeCumplimiento(), asi que tienen que ser los mismos que el resumen que
// muestra la pantalla, y las partes (zonas, servicios) tienen que sumar el total.
const test = require('node:test');
const assert = require('node:assert');
const L = require('../../static/logistica.logic.js');

const SUPUESTOS = () => ({
  cargue: 15, calidad: 10, tolerancia: 30, toleranciaAdelanto: 60,
  trayecto: {'Movil II': 30, 'Movil IV': 20},
  zonaPlanta: {'Movil II': 'Santo Domingo', 'Movil IV': 'Punta Cana'},
});
const pedido = (cliente, obra, hora, cantidad, bomba = 'Directo', elemento = 'LOSA') =>
  ({cliente, obra, horaMin: hora, cantidad, elemento, bomba, producto: null, prioridad: null});
const camion = (cliente, obra, hora, planta, cantidad = 8, ficha = 'F-' + hora) =>
  ({ficha, horaMin: hora, cliente, obra, elemento: 'LOSA', planta, cantidad, conduce: null});

const estado = () => ({
  fecha: '2026-10-14',
  programacion: [
    pedido('ACME', 'TORRE', 480, 16, '43'),           // a tiempo, con bomba, Santo Domingo
    pedido('BETA', 'CASA', 480, 8),                   // tarde, directo, Punta Cana
    pedido('GAMA', 'PISO', 600, 8),                   // tarde, directo, Santo Domingo, sin motivo
  ],
  cargue: [
    camion('ACME', 'TORRE', 420, 'Movil II'), camion('ACME', 'TORRE', 440, 'Movil II'),
    camion('BETA', 'CASA', 500, 'Movil IV'),
    camion('GAMA', 'PISO', 640, 'Movil II'),
    camion('NADIE', 'OBRA X', 700, 'Movil IV', 5),    // sin programacion
  ],
  trayectoOverrides: new Map(), observaciones: new Map(),
  responsables: new Map(), motivos: new Map(),
});

function conMotivos(){
  const s = estado();
  const {results} = L.computeCumplimiento(s, SUPUESTOS());
  const beta = results.find(r => r.cliente === 'BETA');
  s.responsables.set(beta.rowKey, 'Cliente');
  s.motivos.set(beta.rowKey, 'RETRASOS EN OBRA');
  return s;
}

test('el bloque General es el mismo resumen que la pantalla del dia', () => {
  const s = estado();
  const rep = L.reporteDelDia(s, SUPUESTOS());
  const r = L.resumenDeCumplimiento(L.computeCumplimiento(s, SUPUESTOS()).results);
  const g = rep.bloques[0];
  assert.equal(g.nombre, 'General');
  assert.deepEqual([g.pct, g.pctPedidos, g.pedidos, g.m3], [r.pct, r.pctPedidos, r.pedidos, r.m3]);
  assert.equal(g.incumplidos, 2);
  assert.equal(g.m3Despachado, 37, 'todo el cargue, con lo que no tenia programacion');
  assert.equal(g.cargues, 5);
});

test('zonas y servicios suman el total evaluado', () => {
  const rep = L.reporteDelDia(estado(), SUPUESTOS());
  const [gen, sd, pc, bomba, directo] = rep.bloques;
  assert.deepEqual(rep.bloques.map(b => b.nombre),
    ['General', 'Santo Domingo', 'Punta Cana', 'Con bomba', 'Directo']);
  assert.equal(sd.pedidos + pc.pedidos, gen.pedidos);
  assert.equal(bomba.pedidos + directo.pedidos, gen.pedidos);
  assert.equal(bomba.m3 + directo.m3, gen.m3);
  assert.equal(sd.m3Despachado + pc.m3Despachado, gen.m3Despachado);
});

test('lo que no entra al porcentaje sale aparte', () => {
  const rep = L.reporteDelDia(estado(), SUPUESTOS());
  assert.deepEqual(rep.noEvaluables, [{estado: 'Sin programación', entregas: 1}]);
});

test('motivos y responsables: lo que falta va al final como "Sin ..."', () => {
  const rep = L.reporteDelDia(conMotivos(), SUPUESTOS());
  assert.deepEqual(rep.porResponsable.map(g => [g.nombre, g.entregas, g.pct]),
    [['Cliente', 1, 50], ['Sin responsable', 1, 50]]);
  assert.deepEqual(rep.porMotivo.map(g => g.nombre), ['RETRASOS EN OBRA', 'Sin motivo']);
  assert.equal(rep.porMotivo[0].detalle, 'Cliente 1');
  assert.equal(rep.porMotivo.at(-1).pctAcumulado, 100);
  assert.deepEqual(rep.cobertura, {incumplidos: 2, sinMotivo: 1, sinResponsable: 1});
});

test('el detalle trae todas las entregas, incumplidas primero, con su motivo', () => {
  const rep = L.reporteDelDia(conMotivos(), SUPUESTOS());
  assert.equal(rep.entregas.length, 4);
  assert.deepEqual(rep.entregas.map(e => e.estado),
    ['Incumplido', 'Incumplido', 'Cumplido', 'Sin programación']);
  const beta = rep.entregas.find(e => e.cliente === 'BETA');
  assert.equal(beta.motivo, 'RETRASOS EN OBRA');
  assert.equal(beta.zona, 'Punta Cana');
  assert.equal(beta.servicio, 'Directo');
  assert.equal(rep.entregas.find(e => e.cliente === 'ACME').servicio, 'Con bomba');
});

test('lleva los supuestos del dia y los nombres de las metricas', () => {
  const rep = L.reporteDelDia(estado(), SUPUESTOS());
  assert.equal(rep.desde, '2026-10-14');
  assert.equal(rep.hasta, '2026-10-14', 'un dia es un rango de un dia');
  assert.deepEqual(rep.supuestos, {cargue: 15, calidad: 10, tolerancia: 30, ajusteHora: 60, varian: []});
  assert.deepEqual(rep.nombres, {pct: 'Frecuencia de despacho', pctPedidos: 'Inicio de carga'});
});

// ── Rango de fechas (2026-10-21) ────────────────────────────────────────────

const dia = (fecha, s = estado(), sup = SUPUESTOS()) => ({fecha, state: {...s, fecha}, assumptions: sup});

test('el rango junta las entregas de todos los dias y divide una vez', () => {
  const unDia = L.reporteDelDia(estado(), SUPUESTOS());
  const rep = L.reporteDelPeriodo([dia('2026-10-15'), dia('2026-10-14')]);
  assert.equal(rep.desde, '2026-10-14');
  assert.equal(rep.hasta, '2026-10-15');
  const [g, g1] = [rep.bloques[0], unDia.bloques[0]];
  assert.equal(g.pedidos, 2 * g1.pedidos);
  assert.equal(g.m3, 2 * g1.m3);
  assert.equal(g.pct, g1.pct, 'dos dias iguales dan el mismo %');
  assert.equal(g.cargues, 2 * g1.cargues);
  const todos = ['2026-10-14', '2026-10-15'].flatMap(f =>
    L.computeCumplimiento({...estado(), fecha: f}, SUPUESTOS()).results);
  assert.equal(g.pctPedidos, L.acumuladoDeCumplimiento([{results: todos}]).pctPedidos,
    'el mismo acumulado que Estadisticas');
});

test('el rango trae un renglon por dia, en orden', () => {
  const rep = L.reporteDelPeriodo([dia('2026-10-15'), dia('2026-10-14')]);
  assert.deepEqual(rep.porDia.map(b => b.nombre), ['2026-10-14', '2026-10-15']);
  assert.equal(rep.porDia[0].pedidos + rep.porDia[1].pedidos, rep.bloques[0].pedidos);
});

test('el detalle lleva la fecha y va por dia', () => {
  const rep = L.reporteDelPeriodo([dia('2026-10-15'), dia('2026-10-14')]);
  assert.equal(rep.entregas.length, 8);
  assert.deepEqual([...new Set(rep.entregas.map(e => e.fecha))], ['2026-10-14', '2026-10-15']);
});

test('motivos y responsables de cada dia salen de ese dia', () => {
  const rep = L.reporteDelPeriodo([dia('2026-10-14', conMotivos()), dia('2026-10-15')]);
  assert.deepEqual(rep.cobertura, {incumplidos: 4, sinMotivo: 3, sinResponsable: 3});
  assert.deepEqual(rep.porMotivo.map(g => [g.nombre, g.entregas]), [['RETRASOS EN OBRA', 1], ['Sin motivo', 3]]);
});

test('un supuesto que cambio entre dias no se muestra como si fuera de todos', () => {
  const rep = L.reporteDelPeriodo([dia('2026-10-14'), dia('2026-10-15', estado(), {...SUPUESTOS(), tolerancia: 45})]);
  assert.equal(rep.supuestos.tolerancia, null);
  assert.deepEqual(rep.supuestos.varian, ['tolerancia']);
  assert.equal(rep.supuestos.cargue, 15);
});

test('en un rango, camiones es el promedio de las fichas distintas de cada dia', () => {
  const unDia = L.reporteDelDia(estado(), SUPUESTOS());
  const rep = L.reporteDelPeriodo([dia('2026-10-14'), dia('2026-10-15')]);
  assert.equal(rep.bloques[0].camiones, unDia.bloques[0].camiones,
    'dos dias iguales: el mismo promedio, no el doble ni las fichas del rango');
  const otro = estado();
  otro.cargue = otro.cargue.slice(0, 2);   // el segundo dia, 2 camiones
  const mixto = L.reporteDelPeriodo([dia('2026-10-14'), dia('2026-10-15', otro)]);
  assert.equal(mixto.bloques[0].camiones, (unDia.bloques[0].camiones + 2) / 2);
  assert.deepEqual(mixto.porDia.map(b => b.camiones), [unDia.bloques[0].camiones, 2]);
});

// ── Incumplidas del cliente y de VMO, por servicio y compania ────────────────
// (cliente 2026-10-21; VMO y Con bomba / Directo 2026-10-22)

const resumirResp = rep => rep.incumplidasPorResponsable.map(g => [g.responsable, g.entregas,
  g.servicios.map(s => [s.servicio, s.entregas, s.companias.map(c => [c.nombre, c.entregas, c.pct, c.detalle])])]);

test('las incumplidas del cliente y de VMO salen por servicio y por compania, con sus motivos', () => {
  const s = conMotivos();                    // BETA (directo): Cliente / RETRASOS EN OBRA
  const {results} = L.computeCumplimiento(s, SUPUESTOS());
  const gama = results.find(r => r.cliente === 'GAMA');
  s.responsables.set(gama.rowKey, 'VMO');    // GAMA (directo), sin motivo
  const rep = L.reporteDelDia(s, SUPUESTOS());
  assert.deepEqual(resumirResp(rep), [
    ['Cliente', 1, [['Directo', 1, [['BETA', 1, 100, 'RETRASOS EN OBRA 1']]]]],
    ['VMO', 1, [['Directo', 1, [['GAMA', 1, 100, 'Sin motivo 1']]]]],
  ]);
});

test('companias: las que tienen las mismas incumplidas dicen el mismo %, y falta de motivo se ve (#171)', () => {
  // De 3 companias con 1 incumplida cada una, el reparto que suma 100 daba
  // 34, 33 y 33. Y una sin motivo dejaba la columna en blanco.
  const casos = ['A', 'B', 'C'].map(cliente => ({cliente, m3: 7, motivo: cliente === 'C' ? null : 'RETRASOS EN OBRA'}));
  const g = L.agruparIncumplidos(casos, 'cliente', 'Sin cliente', 'motivo', {sinDesglose: 'Sin motivo', pctPorSeparado: true});
  assert.deepEqual(g.map(c => [c.nombre, c.pct, c.detalle]),
    [['A', 33, 'RETRASOS EN OBRA 1'], ['B', 33, 'RETRASOS EN OBRA 1'], ['C', 33, 'Sin motivo 1']]);
  assert.deepEqual(g.map(c => c.pctAcumulado), [33, 67, 100], 'el acumulado sale de las entregas: nunca pasa de 100');
  assert.deepEqual(L.agruparIncumplidos(casos, 'cliente', 'Sin cliente', 'motivo').map(c => c.pct), [34, 33, 33],
    'sin las opciones sigue sumando 100, como en las tablas de responsable y motivo');
});

test('con bomba y directo van aparte, y un servicio sin incumplidas no aparece', () => {
  // La bomba es parte de la clave de la fila: se cambia antes de marcarla.
  const s = estado();
  s.programacion[1].bomba = '43';            // BETA pasa a ir con bomba
  const {results} = L.computeCumplimiento(s, SUPUESTOS());
  s.responsables.set(results.find(r => r.cliente === 'BETA').rowKey, 'Cliente');
  const rep = L.reporteDelDia(s, SUPUESTOS());
  const cliente = rep.incumplidasPorResponsable.find(g => g.responsable === 'Cliente');
  assert.deepEqual(cliente.servicios.map(x => [x.servicio, x.entregas]), [['Con bomba', 1]]);
});

test('en un rango la misma compania suma las de todos los dias', () => {
  const rep = L.reporteDelPeriodo([dia('2026-10-14', conMotivos()), dia('2026-10-15', conMotivos())]);
  assert.deepEqual(resumirResp(rep)[0], ['Cliente', 2, [['Directo', 2, [['BETA', 2, 100, 'RETRASOS EN OBRA 2']]]]]);
});

test('sin incumplidas del cliente ni de VMO la lista va vacia', () => {
  assert.deepEqual(L.reporteDelDia(estado(), SUPUESTOS()).incumplidasPorResponsable, []);
});
