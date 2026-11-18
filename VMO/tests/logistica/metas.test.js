// Contra la meta (2026-11-11): los indicadores de Logistica que la app ya
// calcula, al lado de su meta de la hoja de indicadores de gestion.
const test = require('node:test');
const assert = require('node:assert');
const L = require('../../static/logistica.logic.js');

const prog = (cliente, hora, cantidad, despachado, pendiente, extra = {}) => ({
  cliente, obra: 'OBRA ' + cliente, horaMin: hora, cantidad, despachado, pendiente,
  bomba: null, elemento: 'losa', vendedor: null, zonaProg: null, producto: 'H210', ...extra});
const estado = (programacion, programacionMacao = []) => ({programacion, programacionMacao,
  responsables: new Map(), motivos: new Map(), observaciones: new Map()});
// Sin camiones ni supuestos: no hay cruce y cuenta solo la columna Despachado.
const dia = (fecha, programacion, programacionMacao, results = []) => ({fecha, state: estado(programacion, programacionMacao), results});
const IND_VACIO = {tiempos: {n: 0, pct: null, zonas: []}, camiones: {viajesPorCamionDia: null, zonas: []}};

test('servicio cancelado: renglones del Reporte de cancelados / servicios programados, Macao incluido', () => {
  const dias = [
    dia('2026-10-01', [prog('ACME', 600, 10, 10, 0), prog('BETA', 480, 20, 0, 20),
                       // la misma clave en dos renglones es un solo servicio
                       prog('CETA', 540, 8, 8, 0), prog('CETA', 540, 4, 4, 0),
                       // sin m3 no es un servicio
                       prog('NADA', 700, 0, 0, 0)],
        [prog('MACAO ALTO RESORT (MACAO II, ESTRUCTURA)', 900, 40, 0, 40)]),
    dia('2026-10-02', [prog('DELTA', 600, 6, 6, 0)], []),
  ];
  const c = L.canceladosDelPeriodo(dias);
  assert.equal(c.cancelados, L.reporteCancelados(dias).resumen.entregas, 'los mismos renglones del reporte');
  assert.deepEqual([c.cancelados, c.servicios, c.m3, c.pct], [2, 5, 60, 40]);
});

test('cumple se juzga con el numero redondeado, como se muestra', () => {
  const ind = v => ({tiempos: {n: 1, pct: v.tiempos, zonas: []}, camiones: {viajesPorCamionDia: v.flota, zonas: []}});
  let m = L.metasDelPeriodo([], ind({tiempos: 89.6, flota: 2.56}));
  assert.deepEqual([m.tiempos.valor, m.tiempos.cumple, m.flota.valor, m.flota.cumple], [90, true, 2.6, true]);
  m = L.metasDelPeriodo([], ind({tiempos: 89.4, flota: 2.54}));
  assert.deepEqual([m.tiempos.valor, m.tiempos.cumple, m.flota.valor, m.flota.cumple], [89, false, 2.5, false]);
  assert.deepEqual([m.tiempos.meta, m.flota.meta, m.cancelados.meta], [90, 2.6, 15]);
});

test('servicio cancelado cumple si no pasa la meta', () => {
  // 3 de 20 = 15% cumple; 4 de 20 = 20% no
  const servicios = n => Array.from({length: 20}, (_, i) => prog('C' + i, 600 + i, 5, i < n ? 0 : 5, i < n ? 5 : 0));
  assert.deepEqual(['valor', 'cumple'].map(k => L.metasDelPeriodo([dia('2026-10-01', servicios(3))], IND_VACIO).cancelados[k]), [15, true]);
  assert.deepEqual(['valor', 'cumple'].map(k => L.metasDelPeriodo([dia('2026-10-01', servicios(4))], IND_VACIO).cancelados[k]), [20, false]);
});

test('la primera carga no va en Contra la meta: vive en Estadisticas (2026-11-17)', () => {
  const m = L.metasDelPeriodo([], IND_VACIO);
  assert.ok(!('inicioDeCarga' in m) && !('frecuencia' in m));
  assert.ok(!('primeraCarga' in L.METAS));
});

test('tiempos: una zona "Sin dato" no se juzga y "Sin zona" no sale', () => {
  const ind = {tiempos: {n: 5, pct: 93, zonas: [
    {zona: 'Santo Domingo', pct: 93, hayDato: true}, {zona: 'Punta Cana', pct: 100, hayDato: false}, {zona: 'Sin zona', pct: 50, hayDato: true}]},
    camiones: {viajesPorCamionDia: 2.7, zonas: [{zona: 'Santo Domingo', viajesPorCamionDia: 2.62}, {zona: 'Punta Cana', viajesPorCamionDia: 2.81}]}};
  const m = L.metasDelPeriodo([], ind);
  assert.deepEqual(m.tiempos.zonas, [{zona: 'Santo Domingo', valor: 93, cumple: true}, {zona: 'Punta Cana', valor: null, cumple: null, sinDato: true}]);
  assert.deepEqual(m.flota.zonas.map(z => [z.zona, z.valor]), [['Santo Domingo', 2.6], ['Punta Cana', 2.8]]);
});

test('sin datos: todo "Sin dato", nada se juzga', () => {
  const m = L.metasDelPeriodo([], IND_VACIO);
  assert.deepEqual([m.tiempos, m.flota, m.cancelados].map(x => [x.valor, x.cumple]),
    [[null, null], [null, null], [null, null]]);
});
