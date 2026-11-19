// Cumplimiento a cubicacion por empleado (2026-11-19): lo cubicado (la
// programacion que la app guarda cada dia) contra lo realizado (el reporte
// "Cumplimiento de tiempos de despacho" de CBS, que trae el empleado).
const test = require('node:test');
const assert = require('node:assert');
const L = require('../../static/logistica.logic.js');

// La programacion del dia ya trae la hora ajustada (+60); la de CBS no.
const prog = (cliente, horaMin, cantidad) => ({cliente, obra: 'OBRA', horaMin, cantidad, elemento: 'LOSA', bomba: null});
const dia = (fecha, programacion, programacionMacao = []) => ({fecha, state: {programacion, programacionMacao, cargue: []}, assumptions: {}});
const linea = (ordComp, cliente, horaIni, totalDespachado, empleado = null, fecha = '2026-11-17') =>
  ({fecha, ordComp, planta: 'SanIsidro', cliente, horaIni, totalDespachado, empleado});

test('lee la columna Empleado del reporte de tiempos (vacia es null)', () => {
  const rows = [['OrdComp', 'Planta', 'Cliente', 'Fecha', 'Hora', 'HoraFin', 'Cantidad', 'Total In', 'Logro', 'TotalDespachado', 'ViajesEfectuados', 'Bomba', 'Empleado'],
    ['00113483', 'SDN', 'CONSTRUCTORA A E SRL', 46343, 46343.3333333, 46343.5, 38, 38, 'SI', 38, 5, 40, 'ZABDIEL FRUCTUOSO'],
    ['00113484', 'SDN', 'OTRO', 46343, 46343.5, 46343.6, 8, 8, 'SI', 8, 1, '', '']];
  const t = L.parseTiemposSheets([{nombre: 'x', rows}]);
  assert.deepStrictEqual(t.filas.map(f => [f.ordComp, f.horaIni, f.empleado]), [['00113483', 480, 'ZABDIEL FRUCTUOSO'], ['00113484', 720, null]]);
});

test('el caso del 17/11: 74 m3 cubicados, 90 despachados en dos lineas del mismo pedido: falto', () => {
  const dias = [dia('2026-11-17', [prog('CONSTRUCTORA A E SRL', 540, 23), prog('CONSTRUCTORA A E SRL', 540, 51)])];
  const c = L.cubicacionPorEmpleado(dias, [linea('00113483', 'CONSTRUCTORA A E SRL', 480, 38, 'ZABDIEL FRUCTUOSO'),
                                           linea('00113483', 'CONSTRUCTORA A E SRL', 480, 52)]);
  assert.strictEqual(c.n, 1);
  const [e] = c.empleados;
  assert.deepStrictEqual([e.empleado, e.cubicado, e.realizado, e.cumplen, e.falto], ['ZABDIEL FRUCTUOSO', 74, 90, 0, 1]);
  assert.strictEqual(c.fallas[0].diferencia, 16);
});

test('cumple a ±5% de lo cubicado, por arriba o por abajo', () => {
  const dias = [dia('2026-11-17', [prog('A', 540, 100), prog('B', 540, 100), prog('C', 540, 100), prog('D', 540, 100)])];
  const c = L.cubicacionPorEmpleado(dias, [linea('1', 'A', 480, 105, 'X'), linea('2', 'B', 480, 95, 'X'),
                                           linea('3', 'C', 480, 106, 'X'), linea('4', 'D', 480, 94, 'X')]);
  assert.deepStrictEqual([c.n, c.cumplen, c.falto, c.sobro, c.pct], [4, 2, 1, 1, 50]);
});

test('una linea agregada que no estaba programada cuenta en lo realizado', () => {
  // WTD el 16/11: losa 08:00 (80) y zapata 10:00 (6) programadas; se agrego una linea a las 18:00.
  const dias = [dia('2026-11-16', [prog('WTD', 540, 80), prog('WTD', 660, 6)])];
  const c = L.cubicacionPorEmpleado(dias, [linea('9', 'WTD', 480, 80, null, '2026-11-16'), linea('9', 'WTD', 600, 16, null, '2026-11-16'),
                                           linea('9', 'WTD', 1080, 28.5, 'K', '2026-11-16')]);
  assert.deepStrictEqual([c.empleados[0].cubicado, c.empleados[0].realizado, c.falto], [86, 124.5, 1]);
});

test('lo que no se puede cruzar queda afuera, contado', () => {
  const dias = [dia('2026-11-17', [prog('A', 540, 10), prog('B', 540, 10)], [prog('MACAO', 600, 20)])];
  const c = L.cubicacionPorEmpleado(dias, [
    linea('1', 'A', 480, 10, 'X', '2026-11-18'),        // dia no guardado
    linea('2', 'ZETA', 480, 10, 'X'),                   // cliente fuera de la programacion
    linea('3', 'A', 600, 10, 'X'),                      // otra hora
    linea('4', 'B', 480, 5, 'X'), linea('5', 'B', 480, 5, 'Y'),   // comparten hora
    linea('6', 'A', 480, 0, 'X'),                       // sin despacho: ni se cuenta
    linea('7', 'MACAO', 540, 20, 'X'),                  // la programacion de Macao tambien sirve
  ]);
  assert.deepStrictEqual(c.fuera, {diaNoGuardado: 1, sinCliente: 1, otraHora: 1, compartida: 2});
  assert.deepStrictEqual([c.pedidos, c.evaluados, c.n, c.cumplen], [6, 1, 1, 1]);
});

test('los pedidos sin empleado van aparte y no entran al %', () => {
  const dias = [dia('2026-11-17', [prog('A', 540, 10), prog('B', 540, 10)])];
  const c = L.cubicacionPorEmpleado(dias, [linea('1', 'A', 480, 10, 'X'), linea('2', 'B', 480, 20)]);
  assert.deepStrictEqual([c.n, c.pct, c.sinEmpleado.n, c.sinEmpleado.pct, c.traeEmpleado], [1, 100, 1, 0, true]);
  assert.strictEqual(L.cubicacionPorEmpleado(dias, [linea('2', 'B', 480, 20)]).traeEmpleado, false);
});

test('contra la meta: 93% o mas', () => {
  const base = {tiempos: {n: 0, zonas: []}, camiones: {zonas: []}};
  const m = L.metasDelPeriodo([], {...base, cubicacion: {n: 282, cumplen: 164, pct: 58.2}});
  assert.deepStrictEqual([m.cubicacion.valor, m.cubicacion.cumple, m.cubicacion.meta, m.cubicacion.pedidos], [58, false, 93, 282]);
  assert.strictEqual(L.metasDelPeriodo([], base).cubicacion.valor, null);
});
