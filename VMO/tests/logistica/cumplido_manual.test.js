// Pasar una incumplida a cumplido a mano (2026-10-26). El 23/10 la escalera
// de 4 m3 de TERRAMARE salia incumplida por ir despues de la columna con la
// misma bomba, aunque el servicio arranco a tiempo. Solo con motivo, y cuenta
// como cumplida en todo; la pantalla y el PDF dicen "Cumplido (manual)".
const test = require('node:test');
const assert = require('node:assert');
const L = require('../../static/logistica.logic.js');

const SUPUESTOS = () => ({
  cargue: 15, calidad: 10, tolerancia: 30, toleranciaAdelanto: 60,
  trayecto: {'SanIsidro': 60}, zonaPlanta: {'SanIsidro': 'Santo Domingo'},
});
const pedido = (elemento, cantidad) => ({cliente: 'TERRAMARE', obra: 'M RESIDENCIAS', horaMin: 480,
  cantidad, elemento, bomba: '40', producto: null, prioridad: null});
const camion = (elemento, hora, cantidad) => ({ficha: 'F-' + hora, horaMin: hora, cliente: 'TERRAMARE',
  obra: 'M RESIDENCIAS', elemento, planta: 'SanIsidro', cantidad, conduce: null});

const estado = () => ({
  fecha: '2026-10-23',
  programacion: [pedido('COLUMNA', 22), pedido('ESCALERA', 4)],
  cargue: [camion('COLUMNA', 419, 14), camion('COLUMNA', 483, 8), camion('ESCALERA', 548, 4)],
  trayectoOverrides: new Map(), observaciones: new Map(),
  responsables: new Map(), motivos: new Map(), cumplidosManuales: new Set(),
});
const fila = (s, elemento) => L.computeCumplimiento(s, SUPUESTOS()).results.find(r => r.elemento === elemento);

test('sin tocar nada, la escalera sale incumplida (+2h33)', () => {
  const r = fila(estado(), 'ESCALERA');
  assert.equal(r.estado, 'Incumplido');
  assert.equal(r.diff, 153);
  assert.equal(r.manual, false);
});

test('con motivo y marcada, pasa a cumplida y cuenta en los porcentajes', () => {
  const s = estado();
  const k = fila(s, 'ESCALERA').rowKey;
  s.motivos.set(k, 'PRIORIDAD OTRO ELEMENTO');
  s.cumplidosManuales.add(k);
  const r = fila(s, 'ESCALERA');
  assert.equal(r.estado, 'Cumplido');
  assert.equal(r.manual, true);
  assert.equal(r.diff, 153, 'la diferencia real no se esconde');
  assert.equal(L.estadoVisible(r), 'Cumplido (manual)');
  const res = L.resumenDeCumplimiento(L.computeCumplimiento(s, SUPUESTOS()).results);
  assert.deepEqual([res.pedidosCumplidos, res.pedidos, res.pctPedidos, res.pct], [2, 2, 100, 100]);
});

test('sin motivo, la marca no alcanza: sigue incumplida', () => {
  const s = estado();
  s.cumplidosManuales.add(fila(s, 'ESCALERA').rowKey);
  const r = fila(s, 'ESCALERA');
  assert.equal(r.estado, 'Incumplido');
  assert.equal(r.manual, false);
});

test('una cumplida marcada no cambia: solo va de incumplido a cumplido', () => {
  const s = estado();
  const k = fila(s, 'COLUMNA').rowKey;
  s.motivos.set(k, 'PRIORIDAD OTRO ELEMENTO');
  s.cumplidosManuales.add(k);
  const r = fila(s, 'COLUMNA');
  assert.equal(r.estado, 'Cumplido');
  assert.equal(r.manual, false);
});

test('se guarda con el dia y vuelve igual; sin motivo no se guarda', () => {
  const s = estado();
  const esc = fila(s, 'ESCALERA').rowKey, col = fila(s, 'COLUMNA').rowKey;
  s.motivos.set(esc, 'PRIORIDAD OTRO ELEMENTO');
  s.cumplidosManuales.add(esc);
  s.cumplidosManuales.add(col);   // sin motivo
  const p = L.payloadDelDia(s, {...SUPUESTOS(), espaciamiento: 30}, s.fecha);
  assert.deepEqual(p.cumplidosManuales, [esc]);
  const dia = {fecha: s.fecha, supuestos: {cargue: 15, calidad: 10, tolerancia: 30, plantas: p.plantas},
               programacion: p.programacion, cargue: p.cargue_rows, motivos: p.motivos,
               cumplidosManuales: p.cumplidosManuales};
  const vuelta = L.restaurarDia(dia);
  assert.equal(fila(vuelta.state, 'ESCALERA').estado, 'Cumplido');
  // Un dia guardado antes de esto no trae la lista
  delete dia.cumplidosManuales;
  assert.equal(fila(L.restaurarDia(dia).state, 'ESCALERA').estado, 'Incumplido');
});

test('el PDF la muestra como "Cumplido (manual)" y no la cuenta entre las incumplidas', () => {
  const s = estado();
  const k = fila(s, 'ESCALERA').rowKey;
  s.responsables.set(k, 'Cliente');
  s.motivos.set(k, 'PRIORIDAD OTRO ELEMENTO');
  s.cumplidosManuales.add(k);
  const rep = L.reporteDelDia(s, SUPUESTOS());
  assert.equal(rep.entregas.find(e => e.elemento === 'ESCALERA').estado, 'Cumplido (manual)');
  assert.equal(rep.bloques[0].incumplidos, 0);
  assert.equal(rep.cobertura.incumplidos, 0);
});
