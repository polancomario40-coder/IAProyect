// Los parsers: la heuristica que decide que fila es el encabezado y que
// columna es cual. Es lo primero que se rompe cuando alguien renombra una
// columna del Excel del dia, y lo hace en silencio: no tira error, deja
// campos vacios.
//
// Estos tests NO usan la libreria xlsx. Las funciones reciben las hojas ya
// convertidas a filas, que es justo lo que el envoltorio del HTML les pasa.
const test = require('node:test');
const assert = require('node:assert');
const { parseProgramacionSheets, parseCargueSheets, normalizarBomba, esProductoQueCuenta, esClienteInterno } = require('../../static/logistica.logic.js');

const hoja = (nombre, rows) => ({ nombre, rows });

// La "Hora Inicio" de la programacion se lee con +60 min (regla del
// 2026-10-06): 0.3125 es 07:30 en el Excel y queda 08:30 = 510.
test('la programacion se lee saltando los titulos de arriba', () => {
  const filas = parseProgramacionSheets([hoja('Hoja1', [
    ['VMO CONCRETOS'],
    ['Programacion del dia'],
    ['Cliente', 'Obra', 'Hora Inicio', 'Cantidad'],
    ['ACME', 'Torre Alfa', 0.3125, 40],
  ])]);
  assert.equal(filas.length, 1);
  assert.deepEqual(
    { cliente: filas[0].cliente, obra: filas[0].obra, horaMin: filas[0].horaMin, cantidad: filas[0].cantidad },
    { cliente: 'ACME', obra: 'Torre Alfa', horaMin: 510, cantidad: 40 });
});

test('solo entran los hormigones y los morteros (2026-10-08)', () => {
  const filas = parseProgramacionSheets([hoja('Hoja1', [
    ['Cliente', 'Obra', 'Producto', 'Hora Inicio'],
    ['A', 'O1', 'HORMIGON 210 kg/cm2 GRAVILLA', 0.3125],
    ['B', 'O2', 'HORMIGÓN 280 kg/cm2', 0.3125],
    ['C', 'O3', 'Mortero 250 kg/cm2', 0.3125],
    ['D', 'O4', 'PAVIMENTACION', 0],
    ['E', 'O5', 'SERVICIO DE BOMBEO', null],
  ])]);
  assert.deepEqual(filas.map(f => f.cliente), ['A', 'B', 'C']);
});

test('producto: sin tildes, mayusculas o minusculas, y sin producto se deja pasar', () => {
  assert.ok(esProductoQueCuenta('Hormigón 210'));
  assert.ok(esProductoQueCuenta('MORTERO'));
  assert.ok(esProductoQueCuenta(null));
  assert.ok(esProductoQueCuenta(''));
  assert.ok(!esProductoQueCuenta('PAVIMENTACION'));
});

test('VMO CONCRETOS como cliente es uso interno y no entra (2026-10-08)', () => {
  const prog = parseProgramacionSheets([hoja('Hoja1', [
    ['Cliente', 'Obra', 'Producto', 'Hora Inicio'],
    ['VMO CONCRETOS S. A.', '1895-42', ' HORMIGON  DESPERDICIO FALLA EN EQUIPOS. ', 0],
    ['ACME', 'Torre', 'HORMIGON 210', 0.3125],
  ])]);
  assert.deepEqual(prog.map(f => f.cliente), ['ACME']);
  const { rows } = parseCargueSheets([hoja('Hoja1', [
    ['Ficha', 'Hora', 'Cliente', 'Planta', 'Direccion', 'Cantidad'],
    ['F-1', 0.3125, 'VMO CONCRETOS S. A.', 'Movil II', 'OBRA: 1895-42', 3],
    ['F-2', 0.3125, 'ACME', 'Movil II', 'OBRA: Torre', 7],
  ])]);
  assert.deepEqual(rows.map(r => r.cliente), ['ACME'], 'tampoco en el cargue');
  assert.ok(esClienteInterno('VMO CONCRETOS S. A.'));
  assert.ok(!esClienteInterno('CLIENTE DE VMO'));
});

test('una fila sin cliente no entra', () => {
  const filas = parseProgramacionSheets([hoja('Hoja1', [
    ['Cliente', 'Obra', 'Hora Inicio'],
    ['ACME', 'Torre Alfa', 0.3125],
    [null, 'sigue de la anterior', 0.4],
    ['', 'vacia', 0.4],
  ])]);
  assert.equal(filas.length, 1, 'las filas de continuacion no son pedidos');
});

test('se leen TODAS las hojas del libro y se concatenan', () => {
  const filas = parseProgramacionSheets([
    hoja('Santo Domingo', [['Cliente', 'Obra'], ['ACME', 'Torre Alfa']]),
    hoja('Punta Cana', [['Cliente', 'Obra'], ['BETA', 'Nave Beta']]),
  ]);
  assert.equal(filas.length, 2);
  assert.equal(filas[0].zonaSheet, 'Santo Domingo', 'la zona sale del nombre de la hoja');
  assert.equal(filas[1].zonaSheet, 'Punta Cana');
});

test('una hoja sin encabezado reconocible se saltea sin romper el resto', () => {
  const filas = parseProgramacionSheets([
    hoja('Notas', [['algo'], ['otra cosa']]),
    hoja('Hoja1', [['Cliente', 'Obra'], ['ACME', 'Torre Alfa']]),
  ]);
  assert.equal(filas.length, 1);
});

test('si la columna Cantidad no existe, la cantidad es 0 y no NaN', () => {
  const filas = parseProgramacionSheets([hoja('Hoja1', [
    ['Cliente', 'Obra'], ['ACME', 'Torre Alfa'],
  ])]);
  assert.equal(filas[0].cantidad, 0);
  assert.equal(filas[0].horaMin, null, 'sin columna de hora no se inventa una');
});

test('el cargue descarta CARGA VACIA y las filas sin cliente', () => {
  const { rows } = parseCargueSheets([hoja('Hoja1', [
    ['Ficha', 'Hora', 'Cliente', 'Planta', 'Direccion', 'Cantidad'],
    ['F-1', 0.3125, 'ACME', 'Movil II', 'OBRA: Torre Alfa', 7],
    ['CARGA VACIA', 0.35, 'ACME', 'Movil II', 'OBRA: Torre Alfa', 0],
    ['F-2', 0.4, null, 'Movil II', 'OBRA: Torre Alfa', 7],
  ])]);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].ficha, 'F-1');
});

test('el cargue le saca el prefijo OBRA: a la direccion', () => {
  const { rows } = parseCargueSheets([hoja('Hoja1', [
    ['Ficha', 'Hora', 'Cliente', 'Direccion'],
    ['F-1', 0.3125, 'ACME', 'OBRA:   Torre Alfa  '],
  ])]);
  assert.equal(rows[0].obra, 'Torre Alfa');
});

test('la fecha del dia sale del serial del primer cargue', () => {
  const { fecha } = parseCargueSheets([hoja('Hoja1', [
    ['Ficha', 'Hora', 'Cliente'],
    ['F-1', 46295.3125, 'ACME'],
  ])]);
  assert.equal(fecha, '2026-09-30');
});

test('una hora pura no deja fecha: null, no 1899-12-30', () => {
  // Defecto real corregido el 2026-09-29: ese 1899 terminaba en el nombre
  // del archivo exportado.
  const { fecha, rows } = parseCargueSheets([hoja('Hoja1', [
    ['Ficha', 'Hora', 'Cliente'],
    ['F-1', 0.3125, 'ACME'],
  ])]);
  assert.equal(fecha, null);
  assert.equal(rows[0].horaMin, 450, 'la hora si se lee; lo que no hay es fecha');
});

test('la columna Hora exacta le gana a una que solo contiene la palabra', () => {
  const { rows } = parseCargueSheets([hoja('Hoja1', [
    ['Ficha', 'Hora de cargue teorico', 'Hora', 'Cliente'],
    ['F-1', 0.9, 0.3125, 'ACME'],
  ])]);
  assert.equal(rows[0].horaMin, 450, 'tiene que leer 07:30, no 21:36');
});

test('un encabezado con acento y otro sin acento se leen igual', () => {
  const { rows } = parseCargueSheets([hoja('Hoja1', [
    ['Ficha', 'Hora', 'Cliente', 'Dirección'],
    ['F-1', 0.3125, 'ACME', 'OBRA: Torre Alfa'],
  ])]);
  assert.equal(rows[0].obra, 'Torre Alfa');
});


// ── 2026-10-06: +1 hora, bomba, vendedor y zona de la planilla ──────────────

// El encabezado de la planilla real de programacion (programa 29-09-2026.xls).
const ENCABEZADO_REAL = ['Prioridad', 'Cliente', 'Obra', 'Mangueras', 'Bomba', 'Brigada',
  'Supervisor', 'Elemento', 'Producto', 'Cantidad', 'Despachado', 'Pendiente',
  'Hora Inicio', 'Hora Final'];
const filaReal = (bomba, hora) => [1, 'ACME', 'Torre Alfa', null, bomba, null, 'Luis',
  'LOSA', 'HORMIGON 210', 60, 60, 0, hora, null];

test('a la Hora Inicio se le suma SIEMPRE una hora', () => {
  const [f] = parseProgramacionSheets([hoja('Punta Cana', [ENCABEZADO_REAL, filaReal('45', 17/24)])]);
  assert.equal(f.horaMin, 18 * 60, 'en el Excel dice 17:00');
});

test('sin hora no se inventa una, tampoco con el ajuste', () => {
  const [f] = parseProgramacionSheets([hoja('Punta Cana', [ENCABEZADO_REAL, filaReal('45', null)])]);
  assert.equal(f.horaMin, null);
});

test('la bomba se lee por encabezado, y vacia es Directo', () => {
  const filas = parseProgramacionSheets([hoja('Punta Cana', [
    ENCABEZADO_REAL, filaReal('45', 0.5), filaReal(null, 0.5), filaReal('NO', 0.5), filaReal(0, 0.5),
  ])]);
  assert.deepEqual(filas.map(f => f.bomba), ['45', 'Directo', 'Directo', 'Directo']);
});

test('normalizarBomba: todo lo que dice "no hay bomba" es Directo', () => {
  for (const v of [null, undefined, '', ' ', 0, '0', 'no', 'N/A', 'sin bomba', 'Ninguna', 'DIRECTO']) {
    assert.equal(normalizarBomba(v), 'Directo', `para ${JSON.stringify(v)}`);
  }
  assert.equal(normalizarBomba(' 45 '), '45');
});

test('sin encabezado Bomba, la columna E se usa solo si no tiene otro nombre', () => {
  const sinNombre = parseProgramacionSheets([hoja('H', [
    ['Cliente', 'Obra', 'Hora Inicio', 'Cantidad', null], ['ACME', 'X', 0.5, 7, '52'],
  ])]);
  assert.equal(sinNombre[0].bomba, '52');
  // La regla original tomaba la E sin mirar: aca habria leido 'Elemento'.
  const conNombre = parseProgramacionSheets([hoja('H', [
    ['Cliente', 'Obra', 'Hora Inicio', 'Cantidad', 'Elemento'], ['ACME', 'X', 0.5, 7, 'LOSA'],
  ])]);
  assert.equal(conNombre[0].bomba, 'Directo');
});

test('vendedor y zona de la planilla; sin columna Zona queda la de la hoja', () => {
  const [con] = parseProgramacionSheets([hoja('Punta Cana', [
    ['Cliente', 'Obra', 'Vendedor', 'Zona'], ['ACME', 'X', ' Ana ', 'Bavaro'],
  ])]);
  assert.equal(con.vendedor, 'Ana');
  assert.equal(con.zonaProg, 'Bavaro');
  const [sin] = parseProgramacionSheets([hoja('Punta Cana', [ENCABEZADO_REAL, filaReal('45', 0.5)])]);
  assert.equal(sin.vendedor, null, 'la planilla real no trae vendedor');
  assert.equal(sin.zonaProg, 'Punta Cana');
});
