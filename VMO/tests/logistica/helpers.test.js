// Helpers del dashboard de logistica: normalizacion, horas, fechas y la
// deteccion de encabezados. Correr con:  node --test tests/logistica/
const test = require('node:test');
const assert = require('node:assert');
const {
  normalize, excelTimeToMinutes, excelSerialToFechaStr, minToStr, fmtDiff,
  findHeaderRowIndex, colIndex, obraScore,
} = require('../../static/logistica.logic.js');

test('normalize deja solo mayusculas, numeros y espacios simples', () => {
  assert.equal(normalize('  Constructora   Rebesa, S.R.L. '), 'CONSTRUCTORA REBESA S R L');
  assert.equal(normalize(null), '');
  assert.equal(normalize(undefined), '');
  assert.equal(normalize(123), '123');
});

test('normalize NO distingue dos nombres que solo difieren en puntuacion', () => {
  // Es a proposito y hay que saberlo: es lo que hace que "REBESA SRL" y
  // "REBESA, SRL" crucen igual. La contra es que tampoco los puede separar.
  assert.equal(normalize('REBESA SRL'), normalize('REBESA, SRL'));
});

test('excelTimeToMinutes lee la fraccion de un serial de Excel', () => {
  assert.equal(excelTimeToMinutes(0.5), 720);            // 12:00
  assert.equal(excelTimeToMinutes(46295.25), 360);       // 06:00 de un dia cualquiera
  assert.equal(excelTimeToMinutes(0), 0);
});

test('excelTimeToMinutes lee un Date en UTC, no en la zona del navegador', () => {
  // Si usara getHours() local, el mismo archivo daria horas distintas segun
  // la maquina que abra el dashboard.
  assert.equal(excelTimeToMinutes(new Date(Date.UTC(2026, 8, 29, 7, 30))), 450);
});

test('excelTimeToMinutes lee texto, con y sin AM/PM', () => {
  assert.equal(excelTimeToMinutes('7:30'), 450);
  assert.equal(excelTimeToMinutes('07:30:00'), 450);
  assert.equal(excelTimeToMinutes('7:30 AM'), 450);
  assert.equal(excelTimeToMinutes('7:30 PM'), 1170);
  assert.equal(excelTimeToMinutes('12:15 AM'), 15,   'medianoche es la hora 0, no la 12');
  assert.equal(excelTimeToMinutes('12:15 PM'), 735,  'mediodia se queda en 12');
});

test('excelTimeToMinutes devuelve null en vez de inventar una hora', () => {
  for (const v of [null, undefined, '', 'sin hora', {}]) {
    assert.equal(excelTimeToMinutes(v), null, JSON.stringify(v));
  }
});

test('excelSerialToFechaStr no confunde una hora pura con el 30/12/1899', () => {
  // Defecto real corregido el 2026-09-29: una columna Hora con hora pura
  // (serial < 1) detectaba fecha 1899-12-30 y se metia en el nombre del
  // archivo exportado.
  assert.equal(excelSerialToFechaStr(0.5), null);
  assert.equal(excelSerialToFechaStr(0), null);
  assert.equal(excelSerialToFechaStr('46295'), null, 'un string no es un serial');
  assert.equal(excelSerialToFechaStr(46295), '2026-09-30');
  assert.equal(excelSerialToFechaStr(46295.7), '2026-09-30', 'la parte fraccionaria no mueve el dia');
});

test('minToStr y fmtDiff formatean lo que la tabla muestra', () => {
  assert.equal(minToStr(450), '07:30');
  assert.equal(minToStr(null), '—');
  assert.equal(minToStr(1485), '00:45', 'pasada la medianoche vuelve a empezar');
  assert.equal(fmtDiff(25), '+25min');
  assert.equal(fmtDiff(-25), '−25min');
  assert.equal(fmtDiff(95), '+1h 35min');
  assert.equal(fmtDiff(null), '—');
});

test('findHeaderRowIndex encuentra el encabezado aunque haya titulos arriba', () => {
  const rows = [['VMO CONCRETOS'], [], ['Programacion del dia'], ['Cliente', 'Obra', 'Hora Inicio']];
  assert.equal(findHeaderRowIndex(rows, ['CLIENTE']), 3);
});

test('findHeaderRowIndex solo mira las primeras 10 filas', () => {
  const rows = Array.from({length: 12}, () => []);
  rows[11] = ['Cliente', 'Obra'];
  assert.equal(findHeaderRowIndex(rows, ['CLIENTE']), -1,
    'un encabezado mas abajo de la fila 10 no se encuentra: es un limite, no un bug');
});

test('colIndex prefiere la coincidencia exacta a la parcial', () => {
  // El caso que motivo la regla: "Hora de cargue teorico" contiene "Hora"
  // pero no es la columna que se busca.
  const header = ['Cliente', 'Hora de cargue teorico', 'Hora Inicio'];
  assert.equal(colIndex(header, ['Hora Inicio', 'Hora']), 2);
});

test('colIndex cae a la parcial solo si no hay ninguna exacta', () => {
  assert.equal(colIndex(['Cliente', 'Hora de inicio programada'], ['Hora Inicio', 'Hora']), 1);
  assert.equal(colIndex(['Cliente', 'Obra'], ['Ficha']), -1);
});

test('obraScore mide palabras compartidas de 3 letras o mas', () => {
  assert.equal(obraScore('TORRE ALFA', 'TORRE ALFA'), 1);
  assert.equal(obraScore('PROYECTO TORRE ALFA', 'TORRE ALFA'), 2 / 3);
  assert.equal(obraScore('TORRE ALFA', 'EDIFICIO BETA'), 0);
  assert.equal(obraScore('', 'TORRE'), 0);
  assert.equal(obraScore('LA EL DE', 'LA EL DE'), 0,
    'palabras de menos de 3 letras no cuentan, asi que no hay con que puntuar');
});
