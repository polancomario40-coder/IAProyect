// El cruce programacion-vs-cargue y el calculo de cumplimiento: la pieza mas
// delicada del dashboard, y de donde salieron los cuatro defectos de logica
// del 2026-09-29. Los que aquel dia se corrigieron llevan su fecha escrita.
const test = require('node:test');
const assert = require('node:assert');
const { computeCumplimiento, computeResumen } = require('../../static/logistica.logic.js');

// Supuestos por defecto del dashboard, explicitos para que cada test pueda
// moverlos sin depender de cual es el default hoy.
const SUPUESTOS = () => ({
  cargue: 15, calidad: 10, tolerancia: 30, toleranciaAdelanto: 60,
  trayecto: { 'Movil II': 30, 'Movil III': 15 },
  zonaPlanta: { 'Movil II': 'Santo Domingo', 'Movil III': 'Punta Cana' },
});

const pedido = (cliente, obra, hora, cantidad = 10) =>
  ({ cliente, obra, horaMin: hora, pedido: null, cantidad, elemento: null, producto: null, prioridad: null, zonaSheet: null });

const camion = (cliente, obra, hora, opts = {}) =>
  ({ ficha: opts.ficha || 'F-1', horaMin: hora, cliente, conduce: opts.conduce || null,
     elemento: null, planta: opts.planta || 'Movil II', obra, cantidad: opts.cantidad ?? 7 });

const estado = (programacion, cargue, supuestos = SUPUESTOS(), overrides = new Map()) =>
  computeCumplimiento(
    { programacion, cargue, trayectoOverrides: overrides, observaciones: new Map() },
    supuestos);

// 07:00 de cargue + 15 + 10 + 30 de trayecto = llegada 07:55.
const CARGUE_7 = 420, LLEGADA_ESPERADA = 475;

test('sin alguno de los dos archivos no calcula nada', () => {
  assert.equal(computeCumplimiento({ programacion: null, cargue: [] }, SUPUESTOS()), null);
  assert.equal(computeCumplimiento({ programacion: [], cargue: null }, SUPUESTOS()), null);
});

test('la llegada estimada es cargue + tiempo de cargue + calidad + trayecto', () => {
  const { results } = estado([pedido('ACME', 'TORRE ALFA', 480)],
                             [camion('ACME', 'TORRE ALFA', CARGUE_7)]);
  assert.equal(results.length, 1);
  assert.equal(results[0].horaLlegadaEst, LLEGADA_ESPERADA);
  assert.equal(results[0].diff, LLEGADA_ESPERADA - 480);
});

test('cumple si la diferencia entra en la tolerancia, e incumple si la pasa', () => {
  // Programado 07:25 -> llega 07:55 -> +30, justo el borde de la tolerancia.
  const justo = estado([pedido('ACME', 'TORRE ALFA', 445)], [camion('ACME', 'TORRE ALFA', CARGUE_7)]);
  assert.equal(justo.results[0].diff, 30);
  assert.equal(justo.results[0].estado, 'Cumplido', 'el borde de la tolerancia cumple');

  const pasado = estado([pedido('ACME', 'TORRE ALFA', 444)], [camion('ACME', 'TORRE ALFA', CARGUE_7)]);
  assert.equal(pasado.results[0].estado, 'Incumplido');
});

test('llegar antes cumple, por mucho que sea (2026-10-09)', () => {
  // Del 2026-10-02 al 2026-10-09 hubo un piso de 60 min que hacia incumplir
  // los adelantos grandes; el usuario lo saco: llegar antes siempre cumple.
  const lejos = estado([pedido('ACME', 'TORRE ALFA', 900)], [camion('ACME', 'TORRE ALFA', CARGUE_7)]);
  assert.ok(lejos.results[0].diff < -400);
  assert.equal(lejos.results[0].estado, 'Cumplido');

  // Aunque el dia guardado traiga un piso, ya no se usa.
  const sup = {...SUPUESTOS(), toleranciaAdelanto: 0};
  const unMinuto = estado([pedido('ACME', 'TORRE ALFA', 476)], [camion('ACME', 'TORRE ALFA', CARGUE_7)], sup);
  assert.equal(unMinuto.results[0].diff, -1);
  assert.equal(unMinuto.results[0].estado, 'Cumplido');
});

test('tarde: el borde de la tolerancia cumple y un minuto mas no', () => {
  const justo = estado([pedido('ACME', 'TORRE ALFA', 445)], [camion('ACME', 'TORRE ALFA', CARGUE_7)]);
  assert.equal(justo.results[0].diff, 30);
  assert.equal(justo.results[0].estado, 'Cumplido');
  const pasado = estado([pedido('ACME', 'TORRE ALFA', 444)], [camion('ACME', 'TORRE ALFA', CARGUE_7)]);
  assert.equal(pasado.results[0].diff, 31);
  assert.equal(pasado.results[0].estado, 'Incumplido');
});

test('un pedido sin hora programada NO puede dar Cumplido', () => {
  // Defecto real corregido el 2026-09-29: Math.min de una lista vacia da
  // Infinity, la diferencia daba -Infinity y pasaba cualquier tolerancia, asi
  // que el pedido salia Cumplido solo.
  const { results } = estado([pedido('ACME', 'TORRE ALFA', null)], [camion('ACME', 'TORRE ALFA', CARGUE_7)]);
  assert.equal(results[0].estado, 'Sin hora programada');
  assert.equal(results[0].diff, null);
});

test('una planta sin trayecto configurado no cumple ni incumple: avisa', () => {
  const { results } = estado([pedido('ACME', 'TORRE ALFA', 480)],
                             [camion('ACME', 'TORRE ALFA', CARGUE_7, { planta: 'Planta Nueva' })]);
  assert.equal(results[0].estado, 'Sin dato de planta');
  assert.equal(results[0].horaLlegadaEst, null);
  assert.equal(results[0].zona, 'Sin zona');
});

test('solo Cumplido e Incumplido son evaluables', () => {
  // La regla que el % de pantalla y el del Excel exportado tienen que
  // compartir: el 2026-09-29 el exportado usaba el total de filas como
  // denominador y por eso daba un numero mas bajo que el dashboard.
  const { results } = estado(
    [pedido('ACME', 'TORRE ALFA', 480), pedido('BETA', 'EDIFICIO BETA', null)],
    [camion('ACME', 'TORRE ALFA', CARGUE_7), camion('BETA', 'EDIFICIO BETA', CARGUE_7, { ficha: 'F-2' }),
     camion('GAMMA', 'NAVE GAMMA', CARGUE_7, { ficha: 'F-3' })]);
  const evaluables = results.filter(r => r.estado === 'Cumplido' || r.estado === 'Incumplido');
  assert.equal(results.length, 3);
  assert.equal(evaluables.length, 1, 'de tres filas visibles, una sola entra al porcentaje');
  assert.deepEqual(results.map(r => r.estado).sort(),
                   ['Cumplido', 'Sin hora programada', 'Sin programación']);
});

test('el cruce exacto de cliente+obra tiene confianza Alta', () => {
  const { results } = estado([pedido('ACME', 'Torre Alfa', 480)], [camion('ACME', 'TORRE  ALFA!', CARGUE_7)]);
  assert.equal(results[0].confianza, 'Alta', 'la normalizacion los vuelve iguales');
});

test('si el texto de la obra no coincide, cruza por parecido y marca Revisar', () => {
  const { results } = estado(
    [pedido('ACME', 'PROYECTO TORRE ALFA', 480), pedido('ACME', 'NAVE BETA', 480)],
    [camion('ACME', 'TORRE ALFA', CARGUE_7), camion('ACME', 'NAVE BETA', CARGUE_7, { ficha: 'F-9' })]);
  const alfa = results.find(r => r.obraProg === 'PROYECTO TORRE ALFA');
  assert.equal(alfa.confianza, 'Revisar');
  assert.equal(alfa.obraReal, 'TORRE ALFA');
});

test('cliente con UNA obra programada y UNA real cruza aunque el texto no se parezca', () => {
  // El caso del codigo de proyecto contra la direccion de la calle: no hay
  // con que puntuar, pero tampoco hay ambiguedad posible.
  const { results } = estado([pedido('ACME', 'OBRA-4417', 480)],
                             [camion('ACME', 'CALLE DUARTE ESQ MELLA', CARGUE_7)]);
  assert.equal(results.length, 1);
  assert.equal(results[0].confianza, 'Única obra');
});

test('dos obras empatadas por texto: gana la que coincide en elemento, no la primera (#164)', () => {
  // El 19/10 "EPOKAL - AREA HOTEL" (ESCALERA) y "EPOKAL - COMERCIAL" (COLUMNA)
  // empataban 0,40 contra el unico cargue, "EPOKAL AREA COMERCIAL", con
  // camiones de COLUMNA. Ganaba HOTEL por estar primera en la programacion, y
  // COMERCIAL salia como cancelada aunque se despacho.
  const conElemento = (p, elemento) => ({...p, elemento});
  const hotel = conElemento(pedido('EPOKAL', 'EPOKAL - AREA HOTEL', 1020, 7), 'ESCALERA');
  const comercial = conElemento(pedido('EPOKAL', 'EPOKAL - COMERCIAL', 1020, 10), 'COLUMNA');
  const cargue = [
    {...camion('EPOKAL', 'EPOKAL AREA COMERCIAL', 915), elemento: 'COLUMNA'},
    {...camion('EPOKAL', 'EPOKAL AREA COMERCIAL', 918, { ficha: 'F-2' }), elemento: 'COLUMNA'},
    {...camion('EPOKAL', 'EPOKAL AREA COMERCIAL', 830, { ficha: 'F-3' }), elemento: 'ZAPATA'},
  ];
  for (const programacion of [[hotel, comercial], [comercial, hotel]]){
    const { results, sinCruce } = estado(programacion, cargue);
    const cruzada = results.find(r => r.obraReal === 'EPOKAL AREA COMERCIAL');
    assert.equal(cruzada.obraProg, 'EPOKAL - COMERCIAL', 'el orden de la programacion no decide');
    assert.equal(cruzada.confianza, 'Revisar');
    assert.deepEqual(sinCruce.map(s => s.obra), ['EPOKAL - AREA HOTEL']);
  }
});

test('con dos obras reales y ningun parecido NO adivina: descarta', () => {
  const { results, sinCruce } = estado(
    [pedido('ACME', 'OBRA-4417', 480)],
    [camion('ACME', 'CALLE DUARTE', CARGUE_7), camion('ACME', 'AVENIDA MELLA', CARGUE_7, { ficha: 'F-2' })]);
  assert.equal(sinCruce.length, 1);
  assert.equal(sinCruce[0].motivo, 'No se encontró obra coincidente');
  assert.ok(results.every(r => r.estado === 'Sin programación'),
    'los cargues quedan visibles como sin programacion, no desaparecen');
});

test('dos pedidos del mismo cliente no pueden cumplir con los MISMOS camiones', () => {
  // Defecto real corregido el 2026-09-29: el cruce difuso elegia el mejor
  // candidato por pedido sin reservar el grupo de cargue, asi que dos pedidos
  // del mismo cliente podian apoyarse los dos en el mismo camion.
  const { results, sinCruce } = estado(
    [pedido('ACME', 'TORRE ALFA NORTE', 480), pedido('ACME', 'TORRE ALFA SUR', 480)],
    [camion('ACME', 'TORRE ALFA', CARGUE_7)]);
  const cruzados = results.filter(r => r.obraProg);
  assert.equal(cruzados.length, 1, 'un solo grupo de cargue alcanza para un solo pedido');
  assert.equal(sinCruce.length, 1, 'el otro queda declarado sin cruce, no silenciosamente cumplido');
});

test('el cruce exacto reserva antes de que corra el difuso', () => {
  const { results } = estado(
    [pedido('ACME', 'TORRE ALFA', 480), pedido('ACME', 'TORRE ALFA NORTE', 480)],
    [camion('ACME', 'TORRE ALFA', CARGUE_7), camion('ACME', 'TORRE ALFA NORTE', CARGUE_7, { ficha: 'F-2' })]);
  const porProg = new Map(results.filter(r => r.obraProg).map(r => [r.obraProg, r.obraReal]));
  assert.equal(porProg.get('TORRE ALFA'), 'TORRE ALFA');
  assert.equal(porProg.get('TORRE ALFA NORTE'), 'TORRE ALFA NORTE');
});

test('un pedido sin ningun cargue va a Cancelado con su motivo', () => {
  const { results, sinCruce } = estado([pedido('ACME', 'TORRE ALFA', 480, 40)],
                                       [camion('BETA', 'OTRA', CARGUE_7)]);
  assert.equal(sinCruce.length, 1);
  assert.equal(sinCruce[0].motivo, 'Cliente no aparece en el cargue real');
  assert.equal(sinCruce[0].cantProg, 40);
  assert.ok(results.every(r => r.cliente !== 'ACME'));
});

test('un cargue sin hora valida no cumple: cae en Cancelado', () => {
  const { sinCruce } = estado([pedido('ACME', 'TORRE ALFA', 480)],
                              [camion('ACME', 'TORRE ALFA', null)]);
  assert.equal(sinCruce.length, 1);
  assert.equal(sinCruce[0].motivo, 'Sin hora de cargue válida');
});

test('manda el PRIMER camion, y los demas solo suman m3', () => {
  const { results } = estado([pedido('ACME', 'TORRE ALFA', 480)], [
    camion('ACME', 'TORRE ALFA', 540, { ficha: 'F-2', cantidad: 8 }),
    camion('ACME', 'TORRE ALFA', CARGUE_7, { ficha: 'F-1', cantidad: 7 }),
    camion('ACME', 'TORRE ALFA', 600, { ficha: 'F-3', cantidad: 9 }),
  ]);
  assert.equal(results[0].horaCargue, CARGUE_7, 'el mas temprano, aunque venga ultimo en la lista');
  assert.equal(results[0].cargues, 3);
  assert.equal(results[0].cantReal, 24);
});

test('el trayecto se guarda con la clave que la pantalla recibe, y se aplica', () => {
  // REGRESION 2026-10-06: la casilla guardaba con rowKey (cliente||obra||hora)
  // y el calculo leia cliente||obra, asi que el valor escrito no hacia nada.
  // El test de abajo no lo veia porque arma el Map a mano con la clave buena.
  const p = [pedido('ACME', 'TORRE ALFA', 480)];
  const c = [camion('ACME', 'TORRE ALFA', CARGUE_7)];
  const antes = estado(p, c, SUPUESTOS()).results[0];
  const overrides = new Map([[antes.claveTrayecto, 90]]);
  const despues = estado(p, c, SUPUESTOS(), overrides).results[0];
  assert.equal(despues.isOverride, true);
  assert.equal(despues.trayecto, 90);
  assert.notEqual(antes.claveTrayecto, antes.rowKey, 'si fueran iguales este test no probaria nada');
});

test('el trayecto editado a mano le gana al promedio de la planta', () => {
  const overrides = new Map([['ACME||TORRE ALFA', 90]]);
  const { results } = estado([pedido('ACME', 'TORRE ALFA', 480)],
                             [camion('ACME', 'TORRE ALFA', CARGUE_7)], SUPUESTOS(), overrides);
  assert.equal(results[0].trayecto, 90);
  assert.equal(results[0].isOverride, true);
  assert.equal(results[0].horaLlegadaEst, CARGUE_7 + 15 + 10 + 90);
  assert.equal(results[0].estado, 'Incumplido');
});

test('la zona sale de la planta del primer camion', () => {
  const { results } = estado(
    [pedido('ACME', 'TORRE ALFA', 480), pedido('BETA', 'NAVE BETA', 480)],
    [camion('ACME', 'TORRE ALFA', CARGUE_7, { planta: 'Movil II' }),
     camion('BETA', 'NAVE BETA', CARGUE_7, { ficha: 'F-2', planta: 'Movil III' })]);
  const porCliente = new Map(results.map(r => [r.cliente, r.zona]));
  assert.equal(porCliente.get('ACME'), 'Santo Domingo');
  assert.equal(porCliente.get('BETA'), 'Punta Cana');
});

test('computeResumen cuenta camiones por ficha distinta, no por cargue', () => {
  const resumen = computeResumen({ cargue: [
    camion('ACME', 'TORRE ALFA', CARGUE_7, { ficha: 'F-1', cantidad: 7 }),
    camion('ACME', 'TORRE ALFA', 540, { ficha: 'F-1', cantidad: 7 }),
    camion('ACME', 'NAVE BETA', 600, { ficha: 'F-2', cantidad: 6 }),
  ]});
  const acme = resumen.clientes[0];
  assert.equal(acme.cargues, 3);
  assert.equal(acme.camiones, 2, 'dos viajes de la misma ficha son un camion, no dos');
  assert.equal(acme.obras, 2);
  assert.equal(acme.m3, 20);
  assert.equal(acme.primera, CARGUE_7);
  assert.equal(acme.ultima, 600);
  assert.equal(resumen.kpi.m3_total, 20);
});

// ── un pedido por HORA programada (2026-09-30) ──
//
// Antes una obra era UNA fila juzgada por el primer camion del dia. Sobre datos
// reales eso escondia el dia entero: PARMOL tenia 10 renglones de 09:00 a 20:00
// y 70 camiones en una sola fila, y el primer camion fue uno de 2 m3 a las
// 00:10 — que hacia "Cumplido" a los 70.

const { pedidosPorHora, repartirCamiones, noDespachado, resumenDeCumplimiento } =
  require('../../static/logistica.logic.js');

const ped = (cliente, obra, hora, cantidad, opts = {}) => ({
  cliente, obra, horaMin: hora, cantidad,
  despachado: opts.despachado !== undefined ? opts.despachado : null,
  pendiente: opts.pendiente !== undefined ? opts.pendiente : null,
  pedido: null, elemento: null, producto: null, prioridad: null, zonaSheet: null,
});

test('una obra con varias horas programadas da una fila por hora', () => {
  const { results } = estado(
    [ped('ACME', 'TORRE ALFA', 480, 30, {despachado: 30}),
     ped('ACME', 'TORRE ALFA', 600, 20, {despachado: 20})],
    [camion('ACME', 'TORRE ALFA', CARGUE_7, {ficha: 'F-1', cantidad: 30}),
     camion('ACME', 'TORRE ALFA', 620, {ficha: 'F-2', cantidad: 20})]);
  assert.equal(results.length, 2);
  assert.deepEqual(results.map(r => r.horaProg).sort((a, b) => a - b), [480, 600]);
});

test('renglones a la MISMA hora son un solo pedido', () => {
  // Cambian el producto o el elemento, no el compromiso de entrega.
  const horas = pedidosPorHora([
    ped('A', 'O', 480, 30, {despachado: 30}),
    ped('A', 'O', 480, 20, {despachado: 15}),
    ped('A', 'O', 600, 10, {despachado: 10}),
  ]);
  assert.equal(horas.length, 2);
  assert.deepEqual(horas[0], {hora: 480, cantidad: 50, despachado: 45, pendiente: null,
                              tieneDespachado: true, tienePendiente: false});
});

test('los camiones se reparten por Despachado, en orden cronologico', () => {
  const horas = pedidosPorHora([ped('A','O',480,20,{despachado:15}), ped('A','O',600,20,{despachado:20})]);
  const cs = [
    camion('A','O',420,{ficha:'F-1',cantidad:7}),
    camion('A','O',430,{ficha:'F-2',cantidad:8}),   // aca se llena la cuota de 15
    camion('A','O',610,{ficha:'F-3',cantidad:9}),
  ];
  const reparto = repartirCamiones(horas, cs);
  assert.deepEqual(reparto[0].camiones.map(c => c.ficha), ['F-1', 'F-2']);
  assert.deepEqual(reparto[1].camiones.map(c => c.ficha), ['F-3']);
});

test('si a la cuota le falta menos de 1 m3 no se toma otro camion (#165)', () => {
  // El 01/10 FELIX GUERRA 11:00 tenia cuota 16,5 y camiones de 7 y 9 = 16: se
  // tomaba tambien el de 6 m3 de las 13:18 y el pedido de las 14:00 (6 m3,
  // despachado completo) quedaba "Sin despachar".
  const horas = pedidosPorHora([ped('A','O',660,16.5,{despachado:16.5}), ped('A','O',840,6,{despachado:6})]);
  const cs = [camion('A','O',521,{ficha:'F-1',cantidad:7}),
              camion('A','O',539,{ficha:'F-2',cantidad:9}),
              camion('A','O',798,{ficha:'F-3',cantidad:6})];
  const reparto = repartirCamiones(horas, cs);
  assert.deepEqual(reparto[0].camiones.map(c => c.ficha), ['F-1', 'F-2']);
  assert.deepEqual(reparto[1].camiones.map(c => c.ficha), ['F-3']);
});

test('una cuota de 1 m3 o menos igual recibe su camion', () => {
  const horas = pedidosPorHora([ped('A','O',480,1,{despachado:1}), ped('A','O',600,7,{despachado:7})]);
  const reparto = repartirCamiones(horas, [camion('A','O',420,{ficha:'F-1',cantidad:1}),
                                           camion('A','O',560,{ficha:'F-2',cantidad:7})]);
  assert.deepEqual(reparto[0].camiones.map(c => c.ficha), ['F-1']);
  assert.deepEqual(reparto[1].camiones.map(c => c.ficha), ['F-2']);
});

test('el ultimo pedido se queda con lo que sobre: ningun camion se pierde', () => {
  const horas = pedidosPorHora([ped('A','O',480,10,{despachado:7}), ped('A','O',600,10,{despachado:7})]);
  const cs = [camion('A','O',420,{ficha:'F-1',cantidad:7}),
              camion('A','O',430,{ficha:'F-2',cantidad:7}),
              camion('A','O',440,{ficha:'F-3',cantidad:7}),
              camion('A','O',450,{ficha:'F-4',cantidad:7})];
  const reparto = repartirCamiones(horas, cs);
  assert.equal(reparto.reduce((s, r) => s + r.camiones.length, 0), 4);
  assert.deepEqual(reparto[1].camiones.map(c => c.ficha), ['F-2', 'F-3', 'F-4']);
});

test('una hora con 0 despachado no recibe camiones y queda Sin despachar', () => {
  const { results } = estado(
    [ped('ACME','TORRE ALFA',480,20,{despachado:20}), ped('ACME','TORRE ALFA',1080,30,{despachado:0})],
    [camion('ACME','TORRE ALFA',CARGUE_7,{cantidad:20})]);
  const tarde = results.find(r => r.horaProg === 1080);
  assert.equal(tarde.estado, 'Sin despachar');
  assert.equal(tarde.cargues, 0);
  assert.equal(tarde.diff, null, 'sin camion no hay diferencia que calcular');
});

test('sin columna Despachado se reparte por la cantidad programada', () => {
  // Una planilla vieja o de otra fuente no la trae: el calculo sigue con lo
  // que hay en vez de dejar todo en el primer pedido.
  const horas = pedidosPorHora([ped('A','O',480,15), ped('A','O',600,15)]);
  assert.equal(horas[0].despachado, null);
  const reparto = repartirCamiones(horas, [
    camion('A','O',420,{ficha:'F-1',cantidad:8}),
    camion('A','O',430,{ficha:'F-2',cantidad:8}),
    camion('A','O',610,{ficha:'F-3',cantidad:8})]);
  assert.deepEqual(reparto[0].camiones.map(c => c.ficha), ['F-1', 'F-2']);
});

test('EL CASO PARMOL: un camion chico y temprano no hace cumplir a los que siguen', () => {
  // Reproduce lo que paso el 29-09: 2 m3 a las 00:10 contra un programado de
  // las 09:00, y despues la colada de verdad a las 11:00 con 60 camiones.
  const { results } = estado(
    [ped('MACAO','PARMOL', 540, 10, {despachado: 9.5}),
     ped('MACAO','PARMOL', 660, 420, {despachado: 420})],
    [camion('MACAO','PARMOL', 10, {ficha:'F-0', cantidad: 9.5, planta:'Movil II'}),
     ...Array.from({length: 60}, (_, i) =>
       camion('MACAO','PARMOL', 741 + i * 5, {ficha: 'F-' + (i+1), cantidad: 7, planta:'Movil II'}))]);

  const temprano = results.find(r => r.horaProg === 540);
  const colada   = results.find(r => r.horaProg === 660);
  assert.equal(temprano.cargues, 1, 'el de las 00:10 solo responde por si mismo');
  assert.equal(colada.cargues, 60);
  assert.equal(colada.estado, 'Incumplido', 'la colada real arranco tarde y se ve');

  // El camion de las 00:10 responde solo por SU hora. Llegar antes cumple
  // desde el 2026-10-09 (pedido del usuario): sale Cumplido con −7h55, pero
  // pesa sus 9.5 m3 y no los 420 de la colada.
  assert.equal(temprano.diff, -475);
  assert.equal(temprano.estado, 'Cumplido');

  const r = resumenDeCumplimiento(results);
  assert.equal(r.pct, 2, 'solo los 9.5 m3 del temprano: la colada tarde no se tapa');
});

test('lo no despachado sale de la columna Pendiente, no del cruce', () => {
  const nd = noDespachado([
    ped('ACME','TORRE ALFA',480,30,{despachado:30, pendiente:0}),
    ped('ACME','TORRE ALFA',600,20,{despachado:12, pendiente:8}),
    ped('BETA','NAVE BETA',540,0,{despachado:0, pendiente:0}),
  ]);
  assert.equal(nd.length, 1);
  assert.deepEqual(
    {cliente: nd[0].cliente, hora: nd[0].hora, programado: nd[0].programado, pendiente: nd[0].pendiente},
    {cliente: 'ACME', hora: 600, programado: 20, pendiente: 8});
});

test('un renglon programado en CERO no figura como no despachado', () => {
  // Falso positivo real del 29-09: CORALES DEL CARIBE salia como incumplido y
  // estaba programado en 0 m3 — era un marcador, no una entrega.
  assert.deepEqual(noDespachado([ped('CORALES','OBRA',540,0,{despachado:0, pendiente:0})]), []);
});

test('sin columna Pendiente la lista queda vacia en vez de inventar', () => {
  assert.deepEqual(noDespachado([ped('A','O',480,30)]), []);
});


// ── 2026-10-06: la fila es cliente + obra + bomba + elemento (+ hora) ───────

const conGrupo = (p, elemento, bomba) => ({ ...p, elemento, bomba });
const conElemento = (c, elemento) => ({ ...c, elemento });

test('cada elemento de la obra es su propia fila, y recibe los camiones de su elemento', () => {
  // PARMOL el 30-09: COLUMNA, COLUMNA M1 y ESCALERA M5 en la misma obra.
  const { results } = estado(
    [conGrupo(pedido('ACME', 'PARMOL', 480), 'COLUMNA', '45'),
     conGrupo(pedido('ACME', 'PARMOL', 480), 'COLUMNA M1', '45')],
    [conElemento(camion('ACME', 'PARMOL', 300, { ficha: 'A' }), 'COLUMNA M1'),
     conElemento(camion('ACME', 'PARMOL', 420, { ficha: 'B' }), 'COLUMNA')]);
  assert.equal(results.length, 2);
  const por = Object.fromEntries(results.map(r => [r.elemento, r]));
  assert.deepEqual(por['COLUMNA'].matchRows.map(c => c.ficha), ['B']);
  assert.deepEqual(por['COLUMNA M1'].matchRows.map(c => c.ficha), ['A'],
    'la coincidencia exacta va antes que la de texto cortado');
  assert.equal(por['COLUMNA'].bomba, '45');
});

test('la clave de fila lleva cliente, obra, bomba, elemento y hora', () => {
  const { results } = estado(
    [conGrupo(pedido('Acme', 'Torre Alfa', 480), 'Losa', null)],
    [camion('Acme', 'Torre Alfa', CARGUE_7)]);
  assert.equal(results[0].rowKey, 'ACME||TORRE ALFA||DIRECTO||LOSA||480');
});

test('el mismo grupo a dos horas da dos filas, y la de la tarde se evalua', () => {
  // THE SEE / MURO el 30-09: 08:00 y 19:00. Sin la hora en la fila, el de la
  // tarde quedaba escondido detras del primero.
  const { results } = estado(
    [conGrupo(pedido('ACME', 'THE SEE', 480, 7), 'MURO', 'Directo'),
     conGrupo(pedido('ACME', 'THE SEE', 1140, 7), 'MURO', 'Directo')],
    [conElemento(camion('ACME', 'THE SEE', 420, { ficha: 'A', cantidad: 7 }), 'MURO'),
     conElemento(camion('ACME', 'THE SEE', 1080, { ficha: 'B', cantidad: 7 }), 'MURO')]);
  assert.deepEqual(results.map(r => [r.horaProg, r.horaCargue]), [[480, 420], [1140, 1080]]);
});

test('un elemento escrito cortado en el cargue igual encuentra su fila', () => {
  const { results, camionesSinElemento } = estado(
    [conGrupo(pedido('ACME', 'X', 480), 'MURO DE CONTENCION', null),
     conGrupo(pedido('ACME', 'X', 600), 'LOSA', null)],
    [conElemento(camion('ACME', 'X', 420, { ficha: 'A' }), 'MURO DE CONTENCI')]);
  const muro = results.find(r => r.elemento === 'MURO DE CONTENCION');
  assert.deepEqual(muro.matchRows.map(c => c.ficha), ['A']);
  assert.equal(camionesSinElemento, 0);
});

test('un camion de un elemento que no esta en la obra no se pierde', () => {
  const { results, camionesSinElemento } = estado(
    [conGrupo(pedido('ACME', 'X', 480), 'LOSA', null),
     conGrupo(pedido('ACME', 'X', 600), 'COLUMNA', null)],
    [conElemento(camion('ACME', 'X', 420, { ficha: 'A' }), 'LOSA'),
     conElemento(camion('ACME', 'X', 540, { ficha: 'Z' }), 'ZAPATA')]);
  const total = results.reduce((s, r) => s + r.cargues, 0);
  assert.equal(total, 2, 'ningun camion se pierde');
  assert.equal(camionesSinElemento, 1);
  assert.deepEqual(results.find(r => r.elemento === 'COLUMNA').matchRows.map(c => c.ficha), ['Z'],
    'va al elemento que se quedo sin camiones');
});

test('con un solo elemento en la obra no se mira el elemento del camion', () => {
  // Es el comportamiento de antes: si la obra tiene un solo grupo, todos sus
  // camiones son de ese grupo aunque el texto del elemento no coincida.
  const { results, camionesSinElemento } = estado(
    [conGrupo(pedido('ACME', 'X', 480), 'LOSA', null)],
    [conElemento(camion('ACME', 'X', 420), 'PLATEA')]);
  assert.equal(results[0].cargues, 1);
  assert.equal(camionesSinElemento, 0);
});

test('dos bombas con el mismo elemento comparten sus camiones por hora', () => {
  const { results } = estado(
    [conGrupo(pedido('ACME', 'X', 480, 7), 'LOSA', '45'),
     conGrupo(pedido('ACME', 'X', 600, 7), 'LOSA', '52')],
    [conElemento(camion('ACME', 'X', 420, { ficha: 'A', cantidad: 7 }), 'LOSA'),
     conElemento(camion('ACME', 'X', 540, { ficha: 'B', cantidad: 7 }), 'LOSA')]);
  assert.deepEqual(results.map(r => [r.bomba, r.matchRows.map(c => c.ficha)]),
                   [['45', ['A']], ['52', ['B']]]);
});

test('lo no despachado usa la misma clave de fila y trae bomba y elemento', () => {
  const r = estado([{ ...conGrupo(pedido('ACME', 'X', 480), 'LOSA', '45'), despachado: 3, pendiente: 7 }], []);
  assert.equal(r.noDespachado[0].rowKey, 'ACME||X||45||LOSA||480');
  assert.equal(r.noDespachado[0].bomba, '45');
  assert.equal(r.noDespachado[0].elemento, 'LOSA');
});

test('un texto cortado que encaja en DOS elementos no se asigna a ninguno', () => {
  // "COLUMNA M" es el comienzo de "COLUMNA M1" y de "COLUMNA M5". Elegir uno
  // seria adivinar; el camion va por la regla de respaldo y se cuenta.
  // Verificado por mutacion: aceptar el primer candidato hace fallar este test.
  const { results, camionesSinElemento } = estado(
    [conGrupo(pedido('ACME', 'X', 480), 'COLUMNA M1', null),
     conGrupo(pedido('ACME', 'X', 600), 'COLUMNA M5', null)],
    [conElemento(camion('ACME', 'X', 420, { ficha: 'A' }), 'COLUMNA M1'),
     conElemento(camion('ACME', 'X', 540, { ficha: 'C' }), 'COLUMNA M')]);
  assert.equal(camionesSinElemento, 1);
  assert.deepEqual(results.find(r => r.elemento === 'COLUMNA M5').matchRows.map(c => c.ficha), ['C'],
    'por respaldo, al elemento que se quedo sin camiones — no por el texto');
});

test('una hora sin despachar toma la zona de la planta que sirvio la obra', () => {
  // El 29-09 MACAO tuvo tres horas sin camiones: sin planta propia caian en
  // 'Sin zona', no salian en Punta Cana y el aviso de "planta sin zona" se
  // mostraba con la lista vacia. La zona es de la obra, como el trayecto.
  const { results } = estado(
    [pedido('MACAO', 'PARMOL', 480, 7), pedido('MACAO', 'PARMOL', 1140, 7)],
    [camion('MACAO', 'PARMOL', 420, { planta: 'Movil III', cantidad: 7 })]);
  const sinDespachar = results.find(r => r.horaProg === 1140);
  assert.equal(sinDespachar.estado, 'Sin despachar');
  assert.equal(sinDespachar.planta, null, 'la fila sigue sin planta propia');
  assert.equal(sinDespachar.zona, 'Punta Cana');
  assert.equal(results.find(r => r.horaProg === 480).zona, 'Punta Cana');
});

test('si la planta de la obra no tiene zona, la hora sin despachar queda en Sin zona', () => {
  const { results } = estado(
    [pedido('MACAO', 'PARMOL', 480, 7), pedido('MACAO', 'PARMOL', 1140, 7)],
    [camion('MACAO', 'PARMOL', 420, { planta: 'Planta Nueva', cantidad: 7 })]);
  assert.deepEqual(results.map(r => [r.horaProg, r.planta, r.zona]),
                   [[480, 'Planta Nueva', 'Sin zona'], [1140, null, 'Sin zona']]);
});

test('un renglon programado en 0 m3 no recibe camiones ni se evalua (2026-10-14)', () => {
  // ALBA SANCHEZ: LOSA de las 14:00 en 0 m3 y de noche CALLE sin programar.
  // Era el unico renglon de la obra, asi que se llevaba los 7 camiones y
  // salia incumplido por +5h32.
  const r = estado([pedido('ALBA', 'PARQUEO AIPC', 840, 0)],
                   [camion('ALBA', 'PARQUEO AIPC', 1127), camion('ALBA', 'PARQUEO AIPC', 1144)]);
  assert.deepEqual(r.results.map(x => x.estado), ['Sin programación']);
  assert.equal(r.results[0].cargues, 2);
  assert.deepEqual(r.noDespachado, [], 'tampoco es algo sin despachar');
});

test('si la obra tiene otro renglon con m3, los camiones van a ese', () => {
  const r = estado([pedido('ACME', 'TORRE ALFA', 840, 0), pedido('ACME', 'TORRE ALFA', 480, 14)],
                   [camion('ACME', 'TORRE ALFA', CARGUE_7)]);
  assert.deepEqual(r.results.map(x => [x.horaProg, x.estado]), [[480, 'Cumplido']]);
});

test('una cantidad desconocida (null) si se cruza: solo se saca el cero explicito', () => {
  const r = estado([pedido('ACME', 'TORRE ALFA', 480, null)], [camion('ACME', 'TORRE ALFA', CARGUE_7)]);
  assert.equal(r.results[0].estado, 'Cumplido');
});
