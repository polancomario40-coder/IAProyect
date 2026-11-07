// Las estadisticas sobre varios dias. Todo parte de lo que devuelve
// computeCumplimiento(), asi que aca no se recalcula nada: se agrupa.
const test = require('node:test');
const assert = require('node:assert');
const {
  resumenDeCumplimiento, cumplimientoPorPlanta, serieDeCumplimiento,
  acumuladoDeCumplimiento,
} = require('../../static/logistica.logic.js');

// Una fila de resultado, en la forma que la devuelve computeCumplimiento.
const M3_POR_CARGUE = 7;   // la mediana real de los tres primeros dias

const fila = (estado, opts = {}) => ({
  estado,
  // `cargues` = cuantos VIAJES movio ese pedido. Ya no manda en el porcentaje
  // —desde el 2026-10-02 pesa `cantReal`, los m3— pero se sigue devolviendo
  // como cuenta y hay tests que lo miran.
  cargues: opts.cargues !== undefined ? opts.cargues : 1,
  // `cantReal` = los m3 que movio ese pedido, y es lo que PESA en `pct`.
  // Por defecto son cargues x 7 —la mediana real— para que un caso que no se
  // interesa por el tamano del camion siga dando el mismo porcentaje que
  // cuando la unidad era el cargue. Un caso que SI quiere probar la diferencia
  // pasa `cantReal` a mano.
  cantReal: opts.cantReal !== undefined
    ? opts.cantReal
    : (opts.cargues !== undefined ? opts.cargues : 1) * M3_POR_CARGUE,
  // `planta` se compara contra undefined y no con ||, para poder pasar '' a
  // proposito: una planta vacia es un caso real (el Excel a veces no la trae)
  // y tiene que poder probarse.
  planta: opts.planta !== undefined ? opts.planta : 'Movil II',
  zona: opts.zona || 'Santo Domingo',
  cliente: opts.cliente || 'ACME', obraReal: opts.obra || 'TORRE ALFA',
});

test('el porcentaje cuenta solo los evaluables', () => {
  const r = resumenDeCumplimiento([
    fila('Cumplido'), fila('Cumplido'), fila('Incumplido'),
    fila('Sin programación'), fila('Sin hora programada'), fila('Sin dato de planta'),
  ]);
  assert.equal(r.pedidos, 3);
  assert.equal(r.pedidosCumplidos, 2);
  assert.equal(r.camiones, 3);
  assert.equal(r.camionesCumplidos, 2);
  assert.equal(r.pct, 67);
  assert.equal(r.noEvaluables, 3, 'los otros tres se cuentan, pero aparte');
});

test('el porcentaje PESA POR VOLUMEN, no por pedido', () => {
  // La decision del 2026-09-30, y el caso que la motivo: sobre el 29-09 real,
  // una colada de 64 camiones pesaba lo mismo que un pedido de uno.
  const r = resumenDeCumplimiento([
    fila('Cumplido',   {cargues: 1}),
    fila('Incumplido', {cargues: 9}),
  ]);
  assert.equal(r.pct, 10, '7 m3 cumplidos de 70');
  assert.equal(r.pedidos, 2);
  assert.equal(r.pedidosCumplidos, 1);
  assert.notEqual(r.pct, 50, 'por volumen no puede dar lo mismo que por pedido en este caso');
});

test('el porcentaje pesa por M3 y NO por cantidad de cargues', () => {
  // El cambio del 2026-10-02, pedido por la companera de Axel: contar cargues
  // asume que todos mueven el mismo volumen, y sobre los tres dias guardados
  // van de 1 a 16 m3. Este caso separa las dos unidades a proposito: el pedido
  // que cumplio es UN cargue grande y el que fallo son TRES cargues chicos.
  //
  //            cargues   m3
  //  Cumplido      1     16
  //  Incumplido    3      6   (2 m3 cada uno)
  //
  // Por cargue daria 25% (1 de 4). Por m3 da 73% (16 de 22). Es el mismo dia.
  const r = resumenDeCumplimiento([
    fila('Cumplido',   {cargues: 1, cantReal: 16}),
    fila('Incumplido', {cargues: 3, cantReal: 6}),
  ]);
  assert.equal(r.pct, 73, '16 m3 de 22');
  assert.notEqual(r.pct, 25, 'si pesara por cargue daria 25% — es justo lo que se dejo de hacer');
  assert.equal(r.m3, 22);
  assert.equal(r.m3Cumplidos, 16);
  // Los cargues se siguen devolviendo, pero solo como cuenta.
  assert.equal(r.camiones, 4);
  assert.equal(r.camionesCumplidos, 1);
});

test('un pedido sin m3 no pesa, aunque tenga cargues', () => {
  // `cantReal` es la suma de lo que trajeron los camiones cruzados. Si un
  // pedido cruzo cargues sin cantidad, no puede mover el porcentaje: antes
  // pesaba por existir.
  const r = resumenDeCumplimiento([
    fila('Cumplido',   {cargues: 5, cantReal: 0}),
    fila('Incumplido', {cargues: 1, cantReal: 10}),
  ]);
  assert.equal(r.pct, 0, 'los 5 cargues sin m3 no aportan nada al numerador');
  assert.equal(r.pctPedidos, 50, 'por entrega sigue contando 1 de 2');
});

test('sin m3 evaluables el porcentaje es null, no 0', () => {
  // Misma regla que ya tenia la unidad anterior: "no hubo nada que evaluar" y
  // "no cumplio nada" se ven igual si las dos dan 0.
  const r = resumenDeCumplimiento([
    fila('Cumplido',   {cargues: 1, cantReal: 0}),
    fila('Incumplido', {cargues: 1, cantReal: 0}),
  ]);
  assert.equal(r.pct, null);
  assert.equal(r.pctPedidos, 50, 'por entrega si se puede calcular');
});

test('se devuelven las DOS unidades, y en este caso no coinciden', () => {
  // Decision del 2026-10-01: las dos a la vista. El mismo caso de arriba sirve
  // para fijar la segunda unidad — 1 de 2 entregas cumplidas es 50%, mientras
  // el pesado por camion da 10%. Que una sola fila devuelva los dos numeros es
  // lo que impide que la pantalla y una exportacion usen criterios distintos,
  // que ya paso una vez con el denominador del Excel.
  const r = resumenDeCumplimiento([
    fila('Cumplido',   {cargues: 1}),
    fila('Incumplido', {cargues: 9}),
  ]);
  assert.equal(r.pct, 10, 'por camion');
  assert.equal(r.pctPedidos, 50, 'por entrega: 1 de 2 horas programadas');
});

test('las dos unidades pueden moverse en sentidos OPUESTOS', () => {
  // Esto es el porque de mostrar las dos, y salio de los dos primeros dias
  // reales: por camion el despacho mejoro de 9% a 25% entre el 29 y el 30 de
  // septiembre, y contando entregas empeoro de 23% a 19%. El test reproduce la
  // forma de ese caso con dos dias chicos: de un dia al otro, una unidad sube
  // y la otra baja.
  const dia1 = resumenDeCumplimiento([
    fila('Cumplido',   {cargues: 1}),
    fila('Incumplido', {cargues: 9}),
  ]);
  const dia2 = resumenDeCumplimiento([
    fila('Cumplido',   {cargues: 9}),
    fila('Incumplido', {cargues: 1}),
    fila('Incumplido', {cargues: 1}),
    fila('Incumplido', {cargues: 1}),
  ]);
  assert.ok(dia2.pct > dia1.pct, `por camion sube: ${dia1.pct}% -> ${dia2.pct}%`);
  assert.ok(dia2.pctPedidos < dia1.pctPedidos,
            `por entrega baja: ${dia1.pctPedidos}% -> ${dia2.pctPedidos}%`);
});

test('sin nada que evaluar las DOS unidades son null, no cero', () => {
  const r = resumenDeCumplimiento([fila('Sin programación')]);
  assert.equal(r.pct, null);
  assert.equal(r.pctPedidos, null, 'la segunda unidad tiene el mismo criterio que la primera');
  assert.equal(resumenDeCumplimiento([]).pctPedidos, null);
});

test('sin nada que evaluar el porcentaje es null, no cero', () => {
  // "no hubo nada que evaluar" y "no cumplio nada" son cosas distintas, y se
  // ven igual si las dos dan 0%.
  const r = resumenDeCumplimiento([fila('Sin programación')]);
  assert.equal(r.pct, null);
  assert.equal(r.camiones, 0);
  assert.equal(resumenDeCumplimiento([]).pct, null);
});

test('por planta agrupa solo evaluables y ordena por volumen', () => {
  const porPlanta = cumplimientoPorPlanta([
    fila('Cumplido',   {planta: 'Movil II'}),
    fila('Incumplido', {planta: 'Movil II'}),
    fila('Cumplido',   {planta: 'Movil II'}),
    fila('Cumplido',   {planta: 'Movil III', zona: 'Punta Cana'}),
    fila('Sin programación', {planta: 'Movil III', zona: 'Punta Cana'}),
  ]);
  assert.equal(porPlanta.length, 2);
  assert.deepEqual(porPlanta[0], {planta: 'Movil II', zona: 'Santo Domingo',
                                  pedidos: 3, pedidosCumplidos: 2,
                                  camiones: 3, camionesCumplidos: 2,
                                  m3: 21, m3Cumplidos: 14,
                                  pct: 67, pctPedidos: 67});
  assert.deepEqual(porPlanta[1], {planta: 'Movil III', zona: 'Punta Cana',
                                  pedidos: 1, pedidosCumplidos: 1,
                                  camiones: 1, camionesCumplidos: 1,
                                  m3: 7, m3Cumplidos: 7,
                                  pct: 100, pctPedidos: 100});
});

test('por planta las dos unidades se separan cuando el volumen no esta parejo', () => {
  // Con un camion por fila las dos unidades dan igual, asi que el test de
  // arriba no las distingue. Este si: es el caso Movil VI del 30-09 real, donde
  // las entregas cumplidas eran las que movian los camiones — 84% por camion
  // contra 40% por entrega.
  const porPlanta = cumplimientoPorPlanta([
    fila('Cumplido',   {planta: 'Movil VI', cargues: 16}),
    fila('Incumplido', {planta: 'Movil VI', cargues: 1}),
    fila('Incumplido', {planta: 'Movil VI', cargues: 1}),
    fila('Incumplido', {planta: 'Movil VI', cargues: 1}),
  ]);
  assert.equal(porPlanta[0].pct, 84, 'por camion: 16 de 19');
  assert.equal(porPlanta[0].pctPedidos, 25, 'por entrega: 1 de 4');
});

test('un pedido sin planta no se pierde: va a "Sin planta"', () => {
  const porPlanta = cumplimientoPorPlanta([fila('Cumplido', {planta: ''})]);
  assert.equal(porPlanta[0].planta, 'Sin planta');
});

test('la serie sale ordenada por fecha aunque entre desordenada', () => {
  const serie = serieDeCumplimiento([
    {fecha: '2026-09-30', results: [fila('Cumplido')]},
    {fecha: '2026-09-28', results: [fila('Incumplido')]},
    {fecha: '2026-09-29', results: [fila('Cumplido'), fila('Incumplido')]},
  ]);
  assert.deepEqual(serie.map(d => d.fecha), ['2026-09-28', '2026-09-29', '2026-09-30']);
  assert.deepEqual(serie.map(d => d.pct), [0, 50, 100]);
});

test('el acumulado pondera por pedidos, NO promedia los porcentajes diarios', () => {
  // Un dia de 1 pedido cumplido y otro de 9 con 3 cumplidos.
  // Promediar los % daria (100 + 33) / 2 = 67, que es mentira.
  // Ponderado: 4 cumplidos de 10 = 40%.
  const dias = [
    {fecha: '2026-09-28', results: [fila('Cumplido')]},
    {fecha: '2026-09-29', results: [
      fila('Cumplido'), fila('Cumplido'), fila('Cumplido'),
      fila('Incumplido'), fila('Incumplido'), fila('Incumplido'),
      fila('Incumplido'), fila('Incumplido'), fila('Incumplido')]},
  ];
  const acc = acumuladoDeCumplimiento(dias);
  assert.equal(acc.camiones, 10);
  assert.equal(acc.camionesCumplidos, 4);
  assert.equal(acc.pct, 40);
  assert.equal(acc.dias, 2);

  const promedioIngenuo = Math.round(serieDeCumplimiento(dias)
    .reduce((s, d) => s + d.pct, 0) / 2);
  assert.notEqual(acc.pct, promedioIngenuo, 'y no puede coincidir con el promedio ingenuo');
});

test('un dia sin evaluables no arrastra el acumulado', () => {
  const acc = acumuladoDeCumplimiento([
    {fecha: '2026-09-28', results: [fila('Cumplido')]},
    {fecha: '2026-09-29', results: [fila('Sin programación')]},
  ]);
  assert.equal(acc.pct, 100, 'un dia sin pedidos evaluables no baja el porcentaje');
  assert.equal(acc.dias, 2);
});

// ── OAT (of all time) por planta, contra el dia ──

const { plantasOatYDelDia } = require('../../static/logistica.logic.js');

const HISTORIAL = () => ([
  {fecha: '2026-09-28', results: [
    fila('Cumplido',   {planta: 'Movil II'}),
    fila('Incumplido', {planta: 'Movil II'}),
    fila('Cumplido',   {planta: 'Movil VII', zona: 'Punta Cana'}),
  ]},
  {fecha: '2026-09-29', results: [
    fila('Cumplido',   {planta: 'Movil II'}),
    fila('Cumplido',   {planta: 'Movil II'}),
    fila('Incumplido', {planta: 'Movil II'}),
  ]},
]);

test('cada planta trae su OAT y su numero del dia', () => {
  const filas = plantasOatYDelDia(HISTORIAL(), '2026-09-29');
  const movilII = filas.find(f => f.planta === 'Movil II');
  assert.deepEqual(movilII.oat, {camiones: 5, camionesCumplidos: 3, pedidos: 5,
                                 pedidosCumplidos: 3, m3: 35, m3Cumplidos: 21,
                                 pct: 60, pctPedidos: 60},
    'OAT de Movil II: 21 de 35 m3 sobre los dos dias');
  assert.deepEqual(movilII.dia, {camiones: 3, camionesCumplidos: 2, pedidos: 3,
                                 pedidosCumplidos: 2, m3: 21, m3Cumplidos: 14,
                                 pct: 67, pctPedidos: 67},
    'y el 29 solo: 14 de 21');
});

test('las dos ventanas traen los MISMOS campos, para poder compararlas', () => {
  // El OAT y el dia se muestran uno al lado del otro en la tabla por planta.
  // Si una ventana llevara un campo que la otra no, la tabla mostraria una
  // celda vacia que se lee como un cero.
  const filas = plantasOatYDelDia(HISTORIAL(), '2026-09-29');
  const conDia = filas.find(f => f.dia !== null);
  assert.deepEqual(Object.keys(conDia.oat).sort(), Object.keys(conDia.dia).sort());
});

test('el OAT NO cambia segun el dia que se este mirando', () => {
  const ayer = plantasOatYDelDia(HISTORIAL(), '2026-09-28');
  const hoy = plantasOatYDelDia(HISTORIAL(), '2026-09-29');
  assert.deepEqual(ayer.map(f => f.oat), hoy.map(f => f.oat),
    'of all time significa todo el historial, no el rango que se este viendo');
});

test('una planta que no trabajo ese dia sale igual, con dia en null', () => {
  // Desaparecer de la tabla se leeria como que cumplio. Sale con su OAT y un
  // hueco donde va el numero del dia.
  const filas = plantasOatYDelDia(HISTORIAL(), '2026-09-29');
  const movilVII = filas.find(f => f.planta === 'Movil VII');
  assert.deepEqual(movilVII.oat, {camiones: 1, camionesCumplidos: 1, pedidos: 1,
                                  pedidosCumplidos: 1, m3: 7, m3Cumplidos: 7,
                                  pct: 100, pctPedidos: 100});
  assert.equal(movilVII.dia, null);
  assert.equal(movilVII.zona, 'Punta Cana');
});

test('un dia que no existe en el historial no rompe la tabla', () => {
  const filas = plantasOatYDelDia(HISTORIAL(), '2020-01-01');
  assert.equal(filas.length, 2, 'los OAT siguen estando');
  assert.ok(filas.every(f => f.dia === null));
});

test('sin historial la tabla queda vacia, no revienta', () => {
  assert.deepEqual(plantasOatYDelDia([], '2026-09-29'), []);
});

// ── La pagina filtrada por una planta (pedido de la jefa, 2026-10-01) ──

const { plantasDelHistorial, filtrarDiasPorPlanta, entregasDePlanta,
        SIN_PLANTA } = require('../../static/logistica.logic.js');

const MIXTO = () => ([
  {fecha: '2026-09-28', results: [
    fila('Cumplido',   {planta: 'Movil II', cargues: 2}),
    fila('Incumplido', {planta: 'Movil VI', zona: 'Punta Cana', cargues: 8}),
  ]},
  {fecha: '2026-09-29', results: [
    fila('Incumplido', {planta: 'Movil II', cargues: 1}),
    fila('Cumplido',   {planta: 'Movil VI', zona: 'Punta Cana', cargues: 10}),
    fila('Sin programación', {planta: 'Movil VI', zona: 'Punta Cana', cargues: 3}),
  ]},
]);

test('el selector ofrece las plantas del historial, por volumen', () => {
  const plantas = plantasDelHistorial(MIXTO());
  assert.deepEqual(plantas.map(p => p.planta), ['Movil VI', 'Movil II'],
    'la de mas camiones primero, igual que la tabla');
  assert.equal(plantas[0].zona, 'Punta Cana', 'trae la zona para mostrarla al lado del selector');
  assert.equal(plantas[0].camiones, 21, 'cuenta TODAS sus filas, evaluables o no');
});

test('una planta sin nombre se ofrece como "Sin planta" y se puede filtrar', () => {
  const dias = [{fecha: '2026-09-29', results: [fila('Cumplido', {planta: ''})]}];
  assert.equal(plantasDelHistorial(dias)[0].planta, SIN_PLANTA);
  const filtrados = filtrarDiasPorPlanta(dias, SIN_PLANTA);
  assert.equal(filtrados[0].results.length, 1,
    'si el selector la ofrece, el filtro tiene que encontrarla');
});

test('filtrar por planta da EXACTAMENTE el mismo numero que la tabla de todas', () => {
  // La invariante que justifica filtrar en el calculo y no en la pantalla: la
  // vista filtrada y la fila de la tabla no pueden discrepar, porque las dos
  // son el cumplimiento de esa planta.
  const dias = MIXTO();
  const tabla = cumplimientoPorPlanta(dias.flatMap(d => d.results));
  for (const p of tabla){
    const filtrado = acumuladoDeCumplimiento(filtrarDiasPorPlanta(dias, p.planta));
    assert.equal(filtrado.pct, p.pct, `${p.planta} por camion`);
    assert.equal(filtrado.pctPedidos, p.pctPedidos, `${p.planta} por entrega`);
    assert.equal(filtrado.camiones, p.camiones, `${p.planta} camiones`);
  }
});

test('filtrar NO borra los dias en que esa planta no despacho', () => {
  // Desaparecer del eje del grafico se leeria como que ese dia no existio.
  const dias = MIXTO().concat([{fecha: '2026-09-30', results: [
    fila('Cumplido', {planta: 'Movil VI', zona: 'Punta Cana'})]}]);
  const filtrados = filtrarDiasPorPlanta(dias, 'Movil II');
  assert.equal(filtrados.length, 3, 'los tres dias siguen estando');
  assert.deepEqual(filtrados.map(d => d.results.length), [1, 1, 0]);
  assert.equal(serieDeCumplimiento(filtrados)[2].pct, null,
    'el dia sin filas sale sin dato, no en cero');
});

test('sin planta elegida el filtro devuelve los dias intactos', () => {
  const dias = MIXTO();
  assert.equal(filtrarDiasPorPlanta(dias, null), dias, 'la misma referencia: no copia al vacio');
  assert.equal(filtrarDiasPorPlanta(dias, ''), dias);
});

test('filtrar no modifica los dias originales', () => {
  // El filtrado corre en cada cambio del selector sobre el mismo historial
  // cargado una vez; si mutara, la segunda eleccion partiria de datos ya
  // recortados.
  const dias = MIXTO();
  const antes = JSON.stringify(dias);
  filtrarDiasPorPlanta(dias, 'Movil II');
  assert.equal(JSON.stringify(dias), antes);
});

test('el detalle de una planta sale de la fecha mas nueva a la mas vieja', () => {
  const dias = MIXTO();
  const filas = entregasDePlanta(dias, 'Movil VI');
  assert.deepEqual(filas.map(f => f.fecha), ['2026-09-29', '2026-09-29', '2026-09-28']);
  assert.ok(filas.every(f => f.planta === 'Movil VI'), 'solo esa planta');
  assert.equal(filas.length, 3, 'incluye las no evaluables: son parte del detalle del dia');
});

test('dentro de un dia el detalle ordena por hora programada, y las sin hora al final', () => {
  const dias = [{fecha: '2026-09-29', results: [
    fila('Cumplido',   {planta: 'Movil II'}),
    fila('Incumplido', {planta: 'Movil II'}),
    fila('Cumplido',   {planta: 'Movil II'}),
  ]}];
  dias[0].results[0].horaProg = 600;
  dias[0].results[1].horaProg = null;
  dias[0].results[2].horaProg = 480;
  assert.deepEqual(entregasDePlanta(dias, 'Movil II').map(f => f.horaProg), [480, 600, null]);
});
