// El Reporte de cancelados de un rango de dias (pedido del usuario, 2026-10-12).
// Cancelado = no se despacho NADA; los parciales no entran.
const test = require('node:test');
const assert = require('node:assert');
const L = require('../../static/logistica.logic.js');

const prog = (cliente, hora, cantidad, despachado, pendiente, extra = {}) => ({
  cliente, obra: 'OBRA ' + cliente, horaMin: hora, cantidad, despachado, pendiente,
  bomba: null, elemento: 'losa', vendedor: 'Ana', zonaProg: 'Santo Domingo', producto: 'H210', ...extra});

const estado = (programacion, responsables = {}, motivos = {}, observaciones = {}) => ({
  programacion,
  responsables: new Map(Object.entries(responsables)),
  motivos: new Map(Object.entries(motivos)),
  observaciones: new Map(Object.entries(observaciones)),
});

const k = (p) => L.claveFila(p.cliente, p.obra, p.bomba, p.elemento, p.horaMin);

const a1 = prog('ACME', 600, 10, 3, 7);         // parcial: no es cancelado
const b1 = prog('BETA', 480, 20, 0, 20);
const e1 = prog('EPSI', 900, 12, 0, 12);
const c2 = prog('CETA', 540, 8, 8, 0);          // se despacho entero
const d2 = prog('DELTA', 700, 6, 0, 6);
const dias = [
  {fecha: '2026-10-03', state: estado([c2, d2], {[k(d2)]: 'Cliente'}, {[k(d2)]: 'PERMISOS DE OBRA'})},
  {fecha: '2026-10-02', state: estado([a1, b1, e1], {[k(b1)]: 'VMO', [k(e1)]: 'VMO'},
                                      {[k(a1)]: 'AVERIA DE BOMBA', [k(b1)]: 'AVERIA DE BOMBA',
                                       [k(e1)]: 'AVERIA DE BOMBA'},
                                      {[k(b1)]: 'llovio'})},
  {fecha: '2026-10-04', state: estado([])},
];

test('solo lo que no se despacho nada, por fecha y hora, con la obra', () => {
  const {filas} = L.reporteCancelados(dias);
  assert.deepEqual(filas.map(f => [f.fecha, f.cliente]),
    [['2026-10-02', 'BETA'], ['2026-10-02', 'EPSI'], ['2026-10-03', 'DELTA']]);
  const beta = filas[0];
  assert.equal(beta.obra, 'OBRA BETA');
  assert.equal(beta.volumen, 20);
  assert.equal(beta.responsable, 'VMO');
  assert.equal(beta.motivo, 'AVERIA DE BOMBA');
  assert.equal(beta.razon, 'llovio');
});

test('un despacho parcial no entra, aunque le quede pendiente', () => {
  const {filas} = L.reporteCancelados(dias);
  assert.ok(!filas.some(f => f.cliente === 'ACME'));
});

test('sin la columna Despachado, cuenta como nada si lo pendiente es todo lo programado', () => {
  const sinCol = [prog('NADA', 600, 10, null, 10), prog('PARTE', 700, 10, null, 4)];
  const {filas} = L.reporteCancelados([{fecha: '2026-10-05', state: estado(sinCol)}]);
  assert.deepEqual(filas.map(f => f.cliente), ['NADA']);
});

test('cada fila sale igual que en el Excel de cancelados de un dia', () => {
  const {filas} = L.reporteCancelados(dias);
  const delDia = L.filasCancelados(L.noDespachado([b1, e1]), dias[1].state, '2026-10-02').filas;
  assert.deepEqual(filas.slice(0, 2), delDia);
});

test('el encabezado agrega la obra al formato de la companera', () => {
  const {encabezado} = L.reporteCancelados(dias);
  assert.deepEqual(encabezado, ['FECHA', 'SEMANAS PROGRAMADAS', 'HORA PROGRAMADA', 'CLIENTE', 'OBRA',
    'VENDEDOR', 'ZONA', 'ELEMENTO', 'TIPO DE SERVICIO', 'PRODUCTO', 'VOL. PROGRAMADO',
    'RAZON', 'RESPONSABLE', 'MOTIVO']);
});

test('el resumen: totales, todos los dias del rango, y motivos y responsables por m3', () => {
  const {resumen} = L.reporteCancelados(dias);
  assert.equal(resumen.diasRevisados, 3);
  assert.equal(resumen.diasConCancelados, 2);
  assert.equal(resumen.entregas, 3);
  assert.equal(resumen.m3Cancelado, 38);
  assert.deepEqual(resumen.porDia.map(d => [d.fecha, d.entregas, d.m3Cancelado]),
    [['2026-10-02', 2, 32], ['2026-10-03', 1, 6], ['2026-10-04', 0, 0]]);
  assert.deepEqual(resumen.porMotivo.map(m => [m.nombre, m.entregas, m.m3Cancelado, m.pct]),
    [['AVERIA DE BOMBA', 2, 32, 84], ['PERMISOS DE OBRA', 1, 6, 16]]);
  assert.deepEqual(resumen.porResponsable.map(r => [r.nombre, r.m3Cancelado]), [['VMO', 32], ['Cliente', 6]]);
});

test('lo que no tiene motivo o responsable va al final, aunque pese mas', () => {
  const grande = prog('GRANDE', 900, 50, 0, 50);
  const {resumen} = L.reporteCancelados([...dias, {fecha: '2026-10-05', state: estado([grande])}]);
  assert.equal(resumen.porMotivo.at(-1).nombre, 'Sin motivo');
  assert.equal(resumen.porMotivo.at(-1).m3Cancelado, 50);
  assert.equal(resumen.porResponsable.at(-1).nombre, 'Sin responsable');
  assert.equal(resumen.porMotivo.reduce((s, m) => s + m.pct, 0), 100);
});

test('un rango sin cancelados da un reporte vacio, sin romperse', () => {
  const {filas, resumen} = L.reporteCancelados([{fecha: '2026-10-04', state: estado([c2, a1])}]);
  assert.deepEqual(filas, []);
  assert.equal(resumen.m3Cancelado, 0);
  assert.deepEqual(resumen.porMotivo, []);
});

// 2026-10-16: la columna Despachado no siempre se actualiza. El 08-10 THE ONE
// CAP CANA salia con 300 m3 cancelados y tenia 27 camiones cruzados.
test('un pedido con camiones cruzados no es cancelado, aunque la columna diga 0', () => {
  const SUP = {cargue: 15, calidad: 10, tolerancia: 30, toleranciaAdelanto: 60,
               trayecto: {'Movil II': 30}, zonaPlanta: {'Movil II': 'Santo Domingo'}};
  const conCamion = prog('THE ONE', 780, 300, 0, 300, {elemento: null});
  const sinCamion = prog('IRUYA', 780, 8, 0, 8, {elemento: null});
  const cargue = [{ficha: 'F-1', horaMin: 700, cliente: 'THE ONE', conduce: null, elemento: null,
                   planta: 'Movil II', obra: 'OBRA THE ONE', cantidad: 10}];
  const state = {...estado([conCamion, sinCamion]), cargue, trayectoOverrides: new Map()};
  const {filas} = L.reporteCancelados([{fecha: '2026-10-08', state, assumptions: SUP}]);
  assert.deepEqual(filas.map(f => f.cliente), ['IRUYA']);
  // Sin los supuestos no hay cruce: queda la columna, como antes.
  const solo = L.reporteCancelados([{fecha: '2026-10-08', state}]);
  assert.deepEqual(solo.filas.map(f => f.cliente), ['THE ONE', 'IRUYA']);
});

// 2026-11-03: Macao entra a este reporte, y solo a este; todo Macao, no solo
// MACAO II. Su Despachado muchas veces viene en 0 aunque se haya despachado,
// asi que cuenta el cargue: cancelado si ademas ningun camion de ese cliente
// fue ese dia al mismo elemento de la misma obra.
const MACAO2 = 'MACAO ALTO RESORT S.R.L, (MACAO II, ESTRUCTURA)';
const CEDIS = 'MACAO ALTO RESORT SRL (CEDIS)';
const m2 = (obra, elemento, hora, cantidad, bomba = '421', cliente = MACAO2) => ({cliente, obra, horaMin: hora, cantidad,
  despachado: 0, pendiente: cantidad, bomba, elemento, vendedor: null, zonaProg: 'PUNTA CANA', producto: 'H350'});
const viajeM2 = (obra, elemento, horaMin = 600, cliente = MACAO2) => ({ficha: 'EDU-577', horaMin, cliente, conduce: null,
  elemento, planta: 'Movil III', obra, cantidad: 8});
const conMacao = (programacionMacao, cargueMacao) =>
  ({...estado([]), cargue: [], cargueMacao, programacionMacao, trayectoOverrides: new Map()});

test('Macao: sale el pedido al que no fue ningun camion de esa obra y elemento', () => {
  const st = conMacao([m2('PARMOL', 'COLUMNA M5', 1140, 18), m2('MALESPIN...', 'LOSA M2', 600, 160)],
                      [viajeM2('MALESPIN MACAO II', 'LOSA M2')]);
  const {filas, resumen} = L.reporteCancelados([{fecha: '2026-10-21', state: st}]);
  assert.deepEqual(filas.map(f => [f.cliente, f.obra, f.elemento, f.volumen]), [[MACAO2, 'PARMOL', 'COLUMNA M5', 18]]);
  assert.equal(resumen.m3Cancelado, 18);
});

test('Macao: un vaciado en dos renglones, uno por bomba, no sale si hubo camiones de ese elemento', () => {
  // El 20/10: la LOSA M2 iba en dos renglones y el cruce le daba los camiones
  // a uno solo; el otro salia con 320 m3 cancelados habiendo cargado 540.
  const SUP = {cargue: 15, calidad: 10, tolerancia: 30, toleranciaAdelanto: 60,
               trayecto: {'Movil III': 15}, zonaPlanta: {'Movil III': 'Punta Cana'}};
  const st = conMacao([m2('MALESPIN...', 'LOSA M2', 600, 320, '421'), m2('MALESPIN...', 'LOSA M2', 600, 320, '422')],
                      [viajeM2('MALESPIN MACAO II', 'LOSA M2', 560), viajeM2('MALESPIN MACAO II', 'LOSA M2', 580)]);
  assert.deepEqual(L.reporteCancelados([{fecha: '2026-10-20', state: st, assumptions: SUP}]).filas, []);
});

test('Macao: la obra puede cambiar de nombre entre programacion y cargue, el cliente no', () => {
  // CEDIS: "CONCAVA1" en la programacion y "CONCAVA" en el cargue (17/10);
  // "CEDIS MACAO II GOBAMEX" y "MOON PALACE GOBAMEX" (26/10).
  const st = conMacao([m2('CONCAVA1', 'VIGAS', 600, 18, '', CEDIS), m2('CEDIS MACAO II GOBAMEX', 'PISOS', 660, 28, '', CEDIS),
                       m2('MALESPIN...', 'VIGAS', 700, 10)],
                      [viajeM2('CONCAVA', 'VIGAS', 600, CEDIS), viajeM2('MOON PALACE GOBAMEX', 'PISOS', 640, CEDIS)]);
  const {filas} = L.reporteCancelados([{fecha: '2026-10-17', state: st}]);
  assert.deepEqual(filas.map(f => [f.cliente, f.obra]), [[MACAO2, 'MALESPIN...']],
    'las VIGAS de CEDIS no cuentan para MACAO II');
});

test('Macao entra solo al reporte de cancelados: el dia lo guarda aparte y el cumplimiento no lo ve', () => {
  const hojas = [{nombre: 'x', rows: [
    ['Prioridad', 'Cliente', 'Obra', 'Bomba', 'Elemento', 'Producto', 'Cantidad', 'Despachado', 'Pendiente', 'Hora Inicio'],
    [1, 'ACME', 'TORRE', '40', 'LOSA', 'HORMIGON 210', 10, 10, 0, 46296 + 8 / 24],
    [1, MACAO2, 'PARMOL', '421', 'COLUMNA M5', 'HORMIGON 350', 18, 0, 18, 46296 + 18 / 24],
    [1, CEDIS, 'MOON PALACE', '', 'COLUMNA', 'HORMIGON 210', 4, 0, 4, 46296 + 9 / 24],
    [1, 'VMO CONCRETOS S. A.', 'MACAO', '', 'LECHADA', 'HORMIGON 210', 1, 0, 1, 46296 + 9 / 24],
  ]}];
  assert.deepEqual(L.parseProgramacionSheets(hojas).map(r => r.cliente), ['ACME'], 'el dia sigue sin Macao');
  assert.deepEqual(L.parseProgramacionMacao(hojas).map(r => r.cliente), [MACAO2, CEDIS], 'VMO CONCRETOS no entra');
  const state = {...conMacao(L.parseProgramacionMacao(hojas), []), programacion: L.parseProgramacionSheets(hojas),
                 cumplidosManuales: new Set(), fecha: '2026-10-21'};
  const pay = L.payloadDelDia(state, {cargue: 15, calidad: 10, tolerancia: 30, toleranciaAdelanto: 60,
                                      espaciamiento: 30, trayecto: {}, zonaPlanta: {}}, '2026-10-21');
  assert.equal(pay.programacion.length, 3, 'se guardan los tres');
  const vuelta = L.restaurarDia({fecha: '2026-10-21', supuestos: {cargue: 15, calidad: 10, tolerancia: 30, plantas: []},
                                 programacion: pay.programacion, cargue: []});
  assert.deepEqual(vuelta.state.programacion.map(r => r.cliente), ['ACME'], 'el cumplimiento sigue sin Macao');
  assert.deepEqual(vuelta.state.programacionMacao.map(r => r.obra), ['PARMOL', 'MOON PALACE']);
  assert.equal(L.conteosDelDia(vuelta.state).pedidos, 1, 'el Historial tampoco lo cuenta');
  const {filas} = L.reporteCancelados([{fecha: '2026-10-21', ...vuelta}]);
  assert.deepEqual(filas.map(f => f.obra), ['MOON PALACE', 'PARMOL']);
});
