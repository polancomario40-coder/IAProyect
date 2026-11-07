// El calendario propio de la app (2026-10-19), que reemplaza el selector de
// fecha del navegador en todas las paginas. Aca se prueba la parte de
// calculo; el dibujo se revisa en el navegador.
const test = require('node:test');
const assert = require('node:assert');
const C = require('../../static/calendario.js');

test('el mes arranca en lunes y siempre ocupa 6 semanas', () => {
  const oct = C.celdasDelMes(2026, 9);   // 1-oct-2026 es jueves
  assert.equal(oct.length, 42);
  assert.deepEqual(oct.slice(0, 4), [null, null, null, 1]);
  assert.equal(oct.filter(d => d !== null).length, 31);
  const feb = C.celdasDelMes(2026, 1);   // 1-feb-2026 es domingo
  assert.equal(feb[6], 1);
  assert.equal(feb.filter(d => d !== null).length, 28);
  assert.equal(C.celdasDelMes(2028, 1).filter(d => d !== null).length, 29, 'bisiesto');
});

test('la etiqueta del boton lleva el dia de la semana', () => {
  assert.equal(C.etiquetaFecha('2026-10-16'), 'vie 16 oct 2026');
  assert.equal(C.etiquetaFecha('2026-10-14'), 'mié 14 oct 2026');
  assert.equal(C.etiquetaFecha(''), '');
  assert.equal(C.etiquetaFecha('2026-02-30'), '', 'una fecha que no existe no se muestra');
});

test('solo se eligen los dias dentro de min/max y de la lista', () => {
  const permitidos = new Set(['2026-10-13', '2026-10-15']);
  assert.ok(C.sePuedeElegir('2026-10-13', {permitidos}));
  assert.ok(!C.sePuedeElegir('2026-10-14', {permitidos}));
  assert.ok(C.sePuedeElegir('2026-10-14', {}));
  assert.ok(!C.sePuedeElegir('2026-10-01', {min: '2026-10-05'}));
  assert.ok(!C.sePuedeElegir('2026-10-31', {max: '2026-10-20'}));
});

test('el rango marca inicio, final y lo de en medio, y sigue al mouse antes del final', () => {
  const r = {inicio: '2026-10-05', fin: '2026-10-08'};
  assert.deepEqual(C.claseEnRango('2026-10-05', r), ['sel', 'ini']);
  assert.deepEqual(C.claseEnRango('2026-10-06', r), ['entre']);
  assert.deepEqual(C.claseEnRango('2026-10-08', r), ['sel', 'fin']);
  assert.deepEqual(C.claseEnRango('2026-10-09', r), []);
  // Solo el inicio, con el mouse ANTES: el rango se da vuelta.
  const previa = {inicio: '2026-10-10', fin: null, hover: '2026-10-07'};
  assert.deepEqual(C.claseEnRango('2026-10-07', previa), ['sel', 'ini']);
  assert.deepEqual(C.claseEnRango('2026-10-08', previa), ['entre', 'previa']);
  assert.deepEqual(C.claseEnRango('2026-10-10', previa), ['sel', 'fin']);
  assert.deepEqual(C.claseEnRango('2026-10-10', {inicio: '2026-10-10'}), ['sel']);
  assert.deepEqual(C.claseEnRango('2026-10-10', {}), []);
});
