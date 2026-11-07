// Las zonas del filtro de Estadisticas (pedido del usuario, 2026-10-09).
const test = require('node:test');
const assert = require('node:assert');
const L = require('../../static/logistica.logic.js');

test('Santo Domingo son Movil II, Movil VI, SDN y San Isidro; lo demas es Punta Cana', () => {
  for (const p of ['Movil II', 'Movil VI', 'SDN', 'SanIsidro', 'San Isidro']) assert.equal(L.zonaDePlanta(p), 'Santo Domingo', p);
  for (const p of ['Movil III', 'Movil IV', 'Movil VII', 'Movil VIII', 'Movil IX', 'Planta Nueva']) assert.equal(L.zonaDePlanta(p), 'Punta Cana', p);
  assert.equal(L.zonaDePlanta(null), null);
});

test('el filtro por zona deja solo las filas de esa zona, y los motivos tambien', () => {
  const dias = [{fecha: '2026-10-01', results: [
    {planta: 'Movil II', estado: 'Incumplido', cantReal: 10, zona: 'Santo Domingo'},
    {planta: 'Movil VIII', estado: 'Incumplido', cantReal: 5, zona: 'Punta Cana'},
    {planta: 'SanIsidro', estado: 'Cumplido', cantReal: 7, zona: 'Santo Domingo'},
    {planta: null, estado: 'Sin despachar', cantReal: 0, zona: 'Punta Cana'},
  ], motivos: new Map(), responsables: new Map()}];
  const sd = L.filtrarDiasPorPlanta(dias, L.PREFIJO_ZONA + 'Santo Domingo');
  assert.deepEqual(sd[0].results.map(r => r.planta), ['Movil II', 'SanIsidro']);
  const pc = L.filtrarDiasPorPlanta(dias, L.PREFIJO_ZONA + 'Punta Cana');
  assert.deepEqual(pc[0].results.map(r => r.planta), ['Movil VIII', null], 'sin planta cae a la zona del calculo');
  assert.equal(L.paretoDeMotivos(dias, {planta: L.PREFIJO_ZONA + 'Punta Cana'}).cobertura.incumplidas, 1);
  assert.deepEqual(L.filtrarDiasPorPlanta(dias, 'Movil II')[0].results.length, 1, 'una planta sigue funcionando');
});

test('la zona de una planta es la de los supuestos del dia, en entregas y camiones (#169)', () => {
  // Decision del usuario, 2026-10-23: todo usa la zona de ⚙ Supuestos. Antes
  // el PDF usaba la lista fija y una planta nueva, que entra en Santo Domingo
  // por defecto, salia en Santo Domingo en el dia y en Punta Cana en el PDF.
  const fila = {planta: 'Planta Nueva', estado: 'Cumplido', cantReal: 8, zona: 'Santo Domingo'};
  assert.equal(L.zonaDeFila(fila), 'Santo Domingo', 'gana la zona de los supuestos');
  assert.equal(L.zonaDeFila({planta: 'Planta Nueva', zona: 'Sin zona'}), 'Punta Cana', 'sin zona, la lista fija');
  const cargue = L.cargueConZona([{planta: 'Planta Nueva', cantidad: 8}, {planta: 'Movil II', cantidad: 7}],
                                 {'Planta Nueva': 'Santo Domingo'});
  assert.deepEqual(cargue.filter(c => L.filaDelFiltro(c, L.PREFIJO_ZONA + 'Santo Domingo')).map(c => c.planta),
                   ['Planta Nueva', 'Movil II']);
  assert.equal(L.cargueConZona([{planta: 'X'}], {X: 'Punta Cana'})[0] !== undefined, true);
});
