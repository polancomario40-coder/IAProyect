// Cinco listas mas de CBSListas para los indicadores de gestion (2026-11-17):
// disponibilidad de equipos, batchadas del PLC (eficiencia de carga y control
// de insumos), bitacora de incidencias, reclamaciones y conduces anulados.
const test = require('node:test');
const assert = require('node:assert');
const L = require('../../static/logistica.logic.js');

const hoja = rows => [{nombre: 'x', rows}];
const s = dia => 46295 + dia;   // serial de Excel: 46296 = 2026-10-01

// ---- lectores ----
test('disponibilidad: un renglon por equipo y dia; vacio no es 0 y la fila de totales no entra', () => {
  const r = L.parseDisponibilidadSheets(hoja([
    ['Tipo', 'Equipo', 'Utilizado', 'Disponible', 'Fecha'],
    ['CAMION BOMBA', 'Bom.20', 3, 0, s(1)],
    ['TROMPOS', 'F-823-10', 2, 1, s(1)],
    ['TROMPOS', 'F-823-11', 0, null, s(2)],
    [null, null, 5, 1, null],
  ]));
  assert.deepEqual([r.desde, r.hasta], ['2026-10-01', '2026-10-02']);
  assert.deepEqual(r.filas.map(f => [f.equipo, f.disponible]), [['Bom.20', 0], ['F-823-10', 1], ['F-823-11', null]]);
});

test('batchadas de SDN: minutos de TiempoCarga y desvio de cada material contra su teorico', () => {
  const r = L.parseBatchadasSheets(hoja([
    ['idProducto', 'Planta', 'Fecha', 'FichaCamion', 'Metros', 'Agua', 'AguaTeorico', 'Cemento', 'CementoTeorico',
     'Arena', 'ArenaTeorico', 'Grava', 'GravaTeorico', 'Gravillita', 'GravillitaTeorico', 'TiempoCarga', 'txt_Conduce',
     'Ejec_Adit1', 'SP_Adit1'],
    [null, 'SDN', s(1) + 0.5, 89, 9, 2776, 2825, 6155, 6147, 20381, 20790, 14615, 14625, 0, 0, 5.066667, '158558', 10, 10],
    [null, null, null, null, 30, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 9, null, 0, 0],
  ]));
  assert.equal(r.fuente, 'sdn');
  assert.equal(r.filas.length, 1, 'la fila de totales no entra');
  const b = r.filas[0];
  assert.deepEqual([b.fecha, b.planta, b.conduce, b.m3, b.minutos, b.estado], ['2026-10-01', 'SDN', '158558', 9, 5.066667, 'Realizado']);
  assert.equal(b.dev_cemento.toFixed(2), '0.13');
  assert.equal(b.dev_agregados.toFixed(2), '-1.97', 'de arena y grava, la que mas se aleja');
  assert.equal(b.dev_agua.toFixed(2), '-1.73');
  assert.equal(b.dev_aditivos, 0);
});

test('batchadas de las moviles: TimeBatch hh:mm:ss, el nombre de la planta como en el cargue y el estado', () => {
  const r = L.parseBatchadasSheets(hoja([
    ['idPlanta', 'Fecha', 'Remision', 'BatchStatus', 'MetrosCubicos', 'TCemento1', 'RCemento1', 'TAgregado1', 'RAgregado1',
     'TAgregado2', 'RAgregado2', 'TAgua', 'RAgua', 'TAditivo1', 'RAditivo1', 'TimeBatch'],
    ['MOVIL II', s(1), 'M200122790', 'Realizado', 11, 4840, 4850, 9956, 9980, 9626, 9620, 1572, 1568, 27.4, 27.41, '00:10:59'],
    ['MOVIL VIII', s(2), 'M800016622', 'Cancelado', 7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, null],
  ]));
  assert.equal(r.fuente, 'moviles');
  assert.deepEqual(r.filas.map(f => [f.planta, f.estado]), [['Movil II', 'Realizado'], ['Movil VIII', 'Cancelado']]);
  const b = r.filas[0];
  assert.equal(b.minutos.toFixed(2), '10.98');
  assert.equal(b.dev_agregados.toFixed(2), '0.24');
  assert.equal(r.filas[1].dev_cemento, null, 'sin teorico no hay desvio');
});

test('bitacora, reclamaciones y anulados: cada uno con lo suyo y sin la fila de totales', () => {
  const inc = L.parseIncidenciasSheets(hoja([
    ['Count', 'Cliente', 'contacto', 'Vendedor', 'Fecha', 'VolumenServido', 'Percepcion', 'Planta'],
    [1, '7PALMS', 'Carlos', 'Katherine', s(19), 59, 'Retraso en Inicio del Servicio', 'Movil IV'],
    [643, null, null, null, null, 99, null, null],
  ]));
  assert.deepEqual(inc.filas, [{fecha: '2026-10-19', planta: 'Movil IV', cliente: '7PALMS', volumen: 59, percepcion: 'Retraso en Inicio del Servicio'}]);
  const rec = L.parseReclamosSheets(hoja([
    ['Reclamo', 'Fecha', 'Usuario', 'idCliente', 'Cliente', 'FechaReclamacion', 'TipoReclamo', 'Estado', 'Procede', 'CostoReclamacion'],
    ['00001166', s(5), 'k', 5102, 'DICONFO', s(5), 'Reclamo', 'PENDIENTE', 'PROCEDE', 1151.44],
  ]));
  assert.deepEqual(rec.filas, [{fecha: '2026-10-05', reclamo: '00001166', cliente: 'DICONFO', tipo: 'Reclamo', estado: 'PENDIENTE', procede: 'PROCEDE', costo: 1151.44}]);
  const anu = L.parseAnuladosSheets(hoja([
    ['idPlanta', 'Conduce', 'Fecha', 'Cliente', 'Producto', 'Cantidad', 'CausaAnulacion', 'ComentarioAnulacion'],
    ['Movil VIII', 'M800016622', s(1), 'MACAO', 'H350', 3.5, 'DESPERDICIO', 'tuberia tapada'],
    [null, null, null, null, null, 3.5, null, null],
  ]));
  assert.deepEqual(anu.filas, [{fecha: '2026-10-01', conduce: 'M800016622', planta: 'Movil VIII', cliente: 'MACAO', m3: 3.5, causa: 'DESPERDICIO', comentario: 'tuberia tapada'}]);
});

test('cada lector reconoce solo su reporte', () => {
  const tiempos = hoja([['OrdComp', 'Planta', 'Cliente', 'Fecha', 'Cantidad', 'Total In', 'TotalDespachado', 'ViajesEfectuados'], ['1', 'SDN', 'A', s(1), 1, 1, 1, 1]]);
  for (const p of ['parseDisponibilidadSheets', 'parseBatchadasSheets', 'parseIncidenciasSheets', 'parseReclamosSheets', 'parseAnuladosSheets'])
    assert.equal(L[p](tiempos), null, p);
});

// ---- cuentas ----
test('disponibilidad: sobre los registros con dato y, aparte, contando los vacios como no disponibles', () => {
  const f = (equipo, disponible, tipo = 'TROMPOS') => ({fecha: '2026-10-01', tipo, equipo, utilizado: 1, disponible});
  const d = L.disponibilidadDeEquipos([f('A', 1), f('B', 1), f('C', 0), f('D', null), f('B-1', 0, 'CAMION BOMBA')]);
  const cam = d.tipos.find(t => t.tipo === 'Camiones'), bom = d.tipos.find(t => t.tipo === 'Bombas');
  assert.deepEqual([cam.registros, cam.conDato, cam.sinDato, cam.disponibles], [4, 3, 1, 2]);
  assert.equal(cam.pct.toFixed(1), '66.7');
  assert.equal(cam.pctTodos, 50);
  assert.equal(bom.pct, 0);
  assert.equal(cam.equipos[0].equipo, 'C', 'primero el que mas dias no estuvo disponible');
});

test('carga en planta: ritmo real, las dos versiones de insumos y solo las cargas realizadas', () => {
  const b = (planta, m3, minutos, dev = {}, estado = 'Realizado') => ({fecha: '2026-10-01', planta, m3, minutos, estado,
    dev_cemento: 0, dev_agregados: 0, dev_agua: 0, dev_aditivos: null, ...dev});
  const k = L.cargaEnPlanta([
    b('SDN', 8, 4), b('SDN', 6, 4, {dev_agua: 3}),                // el agua se sale: cuenta solo en "todos"
    b('Movil VIII', 7, 6, {dev_agregados: -2.5}),                   // los agregados se salen
    b('Movil VIII', 7, 6, {}, 'Cancelado'),                         // no entra
  ], ['SDN', 'Movil VIII', 'Movil VI']);
  assert.equal(k.n, 3);
  assert.equal(k.ritmo, 60 * 21 / 14);
  assert.equal(k.insumos.toFixed(1), '66.7');
  assert.equal(k.insumosTodos.toFixed(1), '33.3');
  assert.deepEqual(k.fallas, {cemento: 0, agregados: 1, agua: 1, aditivos: 0});
  assert.deepEqual(k.sinBatchadas, ['Movil VI']);
  assert.equal(k.eficiencia, null, 'sin la capacidad de la planta no hay eficiencia');
  const sdn = k.plantas.find(p => p.planta === 'SDN');
  assert.deepEqual([sdn.zona, sdn.n, sdn.ritmo, sdn.minutosPorCarga], ['Santo Domingo', 2, 105, 4]);
  assert.deepEqual(k.zonas.map(z => [z.zona, z.n]), [['Santo Domingo', 2], ['Punta Cana', 1]]);
});

test('eficiencia de carga: tiempo segun la capacidad / tiempo real, cuando la planta tiene capacidad', () => {
  L.CAPACIDAD_PLANTA.SDN = 120;   // 120 m3/h: 8 m3 en 4 minutos
  try {
    const k = L.cargaEnPlanta([{fecha: '2026-10-01', planta: 'SDN', m3: 8, minutos: 5 + 1 / 3, estado: 'Realizado'}]);
    assert.equal(Math.round(k.eficiencia), 75);
    assert.equal(k.plantas[0].capacidad, 120);
  } finally { delete L.CAPACIDAD_PLANTA.SDN; }
});

test('incidencias: lo que no es "sin novedad" / servicios; la zona puede venir escrita', () => {
  const i = (percepcion, planta) => ({fecha: '2026-10-01', planta, cliente: 'A', volumen: 10, percepcion});
  const r = L.incidenciasDeClientes([i('Realizado sin novedad', 'Santo Domingo'), i('Realizada sin novedad', 'Movil IV'),
    i('Tardanza Bomba', 'Santo Domingo'), i('Tardanza Bomba', 'Movil IV'), i('Averia en Bomba', 'SDN')]);
  assert.deepEqual([r.n, r.conIncidencia, r.pct], [5, 3, 60]);
  assert.deepEqual(r.zonas.map(z => [z.zona, z.n, z.conIncidencia]), [['Santo Domingo', 3, 2], ['Punta Cana', 2, 1]]);
  assert.deepEqual(r.tipos.map(t => [t.tipo, t.n]), [['Tardanza Bomba', 2], ['Averia en Bomba', 1]]);
});

test('reclamos solucionados: solucionados o cerrados / reclamos', () => {
  const r = L.reclamosDelPeriodo(['PENDIENTE', 'SOLUCIONADO', 'Cerrado', 'PENDIENTE'].map((estado, n) =>
    ({fecha: '2026-10-05', reclamo: String(n), estado, procede: n ? 'PROCEDE' : 'NO PROCEDE', costo: 100})));
  assert.deepEqual([r.n, r.solucionados, r.pct, r.procede, r.costo], [4, 2, 50, 3, 400]);
  assert.deepEqual(r.estados[0], {estado: 'PENDIENTE', n: 2});
});

test('concreto devuelto: solo los anulados por DESPERDICIO, sobre los m3 transportados', () => {
  const a = (causa, m3) => ({fecha: '2026-10-01', conduce: causa + m3, causa, m3});
  const r = L.concretoDevuelto([a('DESPERDICIO', 8), a('DESPERDICIO', 2), a('DESVIO A OTRO CLIENTE', 11)], 1000);
  assert.deepEqual([r.anulados, r.m3Anulados, r.conduces, r.m3, r.pct], [3, 21, 2, 10, 1]);
  assert.equal(r.causas[0].causa, 'DESVIO A OTRO CLIENTE');
});

test('contra la meta: los reportes nuevos con su meta, y "Sin dato" si no se subieron', () => {
  const vacio = L.metasDelPeriodo([], {tiempos: {n: 0, zonas: []}, camiones: {zonas: []}});
  for (const k of ['disponibilidadCamiones', 'disponibilidadBombas', 'eficiencia', 'insumos', 'incidencias', 'reclamos'])
    assert.deepEqual([vacio[k].valor, vacio[k].cumple], [null, null], k);
  const ind = L.indicadoresDelPeriodo([], {
    disponibilidad: [{fecha: '2026-10-01', tipo: 'TROMPOS', equipo: 'A', utilizado: 1, disponible: 1}],
    batchadas: [{fecha: '2026-10-01', planta: 'SDN', m3: 6, minutos: 6, estado: 'Realizado', dev_cemento: 0, dev_agregados: 0, dev_agua: 5}],
    incidencias: [{fecha: '2026-10-01', planta: 'SDN', percepcion: 'Tardanza Bomba'}],
    reclamos: [{fecha: '2026-10-01', reclamo: '1', estado: 'PENDIENTE'}],
  });
  const m = L.metasDelPeriodo([], ind);
  assert.deepEqual([m.disponibilidadCamiones.valor, m.disponibilidadCamiones.cumple, m.disponibilidadBombas.valor], [100, true, null]);
  assert.deepEqual([m.eficiencia.valor, m.eficiencia.ritmo], [null, 60]);
  assert.deepEqual([m.insumos.valor, m.insumos.cumple, m.insumos.todos], [100, true, 0]);
  assert.deepEqual([m.incidencias.valor, m.incidencias.cumple], [100, false]);
  assert.deepEqual([m.reclamos.valor, m.reclamos.cumple, m.reclamos.total], [0, false, 1]);
});
