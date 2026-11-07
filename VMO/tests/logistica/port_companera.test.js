// Lo que se porto el 2026-10-06 de la version de la companera
// (dashboard_cumplimiento_v17 (11)): espaciamiento entre camiones, m3
// programados en el resumen, Punta Cana partido en Proyecto Macao, el Excel
// de cancelados, los datos de la imagen y el responsable por fila.
//
// Se porto la FUNCION y no el codigo: su archivo desciende de un original
// anterior a los arreglos del repo, asi que cada pieza se escribio sobre lo
// nuestro y se prueba aca.
const test = require('node:test');
const assert = require('node:assert');
const L = require('../../static/logistica.logic.js');

// ── espaciamiento ───────────────────────────────────────────────────────────

test('espaciamiento: cumple si ningun intervalo supera el maximo', () => {
  assert.deepEqual(L.evaluarEspaciamiento([480, 500, 530], 30),
                   {estado: 'Cumple', intervalos: 2, excedidos: 0, maxGap: 30});
});

test('espaciamiento: 31 minutos con maximo 30 no cumple, y los cuenta', () => {
  const e = L.evaluarEspaciamiento([480, 511, 520, 600], 30);
  assert.equal(e.estado, 'No cumple');
  assert.equal(e.excedidos, 2);
  assert.equal(e.maxGap, 80);
});

test('espaciamiento: ordena las horas y con un solo cargue es N/A', () => {
  assert.equal(L.evaluarEspaciamiento([530, 480, 500], 30).maxGap, 30);
  assert.equal(L.evaluarEspaciamiento([480], 30).estado, 'N/A');
  assert.equal(L.evaluarEspaciamiento([480, null], 30).estado, 'N/A', 'una hora vacia no es un cargue');
});

const cargue = (cliente, obra, hora, cantidad = 7) =>
  ({ficha: 'F-' + hora, horaMin: hora, cliente, obra, cantidad, planta: 'Movil II', elemento: null});

test('el resumen evalua espaciamiento por obra y por cliente, con el default de 30', () => {
  const r = L.computeResumen({
    cargue: [cargue('ACME', 'A', 480), cargue('ACME', 'A', 540),   // 60 min: no cumple
             cargue('ACME', 'B', 600), cargue('ACME', 'B', 620)],  // 20 min: cumple
    programacion: [],
  });
  const acme = r.clientes[0];
  const por = Object.fromEntries(acme.obras_detail.map(o => [o.obra, o.espaciamiento.estado]));
  assert.deepEqual(por, {A: 'No cumple', B: 'Cumple'});
  assert.equal(acme.espaciamiento.estado, 'No cumple');
  assert.equal(acme.espaciamiento.excedidos, 1);
  assert.equal(acme.espaciamiento.maxGap, 60);
});

test('el maximo de espaciamiento sale de los supuestos', () => {
  const r = L.computeResumen({cargue: [cargue('ACME', 'A', 480), cargue('ACME', 'A', 540)]},
                             {espaciamiento: 90});
  assert.equal(r.clientes[0].espaciamiento.estado, 'Cumple');
});

test('cada cargue trae los minutos desde el anterior DE SU MISMA OBRA', () => {
  const r = L.computeResumen({cargue: [cargue('ACME', 'A', 480), cargue('ACME', 'B', 500),
                                       cargue('ACME', 'A', 530)]});
  assert.deepEqual(r.clientes[0].cargues_detail.map(c => [c.obra, c.delta]),
                   [['A', null], ['B', null], ['A', 50]]);
});

test('el espaciamiento se mide por elemento: el hueco entre dos elementos no cuenta (2026-10-08)', () => {
  // Caso real del 02-10, VIGAFILI: fino de techo 08:35 y el piso pulido desde las 11:09.
  const c = (hora, elemento) => ({...cargue('VIGAFILI', 'A', hora), elemento});
  const r = L.computeResumen({cargue: [c(515, 'FINO DE TECHO'), c(669, 'PISO PULIDO'), c(677, 'PISO PULIDO')]});
  const v = r.clientes[0];
  assert.equal(v.obras_detail[0].espaciamiento.estado, 'Cumple');
  assert.equal(v.espaciamiento.maxGap, 8);
  // agrupados por tipo, el de mas m3 primero: el piso pulido (14) antes que el fino (7)
  assert.deepEqual(v.cargues_detail.map(x => [x.tipo, x.delta]),
                   [['PISO PULIDO', null], ['PISO PULIDO', 8], ['FINO DE TECHO', null]]);
});

test('dentro de un mismo elemento el espaciamiento se sigue midiendo', () => {
  const c = (hora) => ({...cargue('ACME', 'A', hora), elemento: 'LOSA'});
  const r = L.computeResumen({cargue: [c(480), c(560)]});
  assert.equal(r.clientes[0].espaciamiento.estado, 'No cumple');
});

test('el resumen trae los m3 programados por cliente y por obra, o null si no estaba', () => {
  const r = L.computeResumen({
    cargue: [cargue('ACME', 'A', 480), cargue('BETA', 'X', 500)],
    programacion: [{cliente: 'Acme', obra: 'a', cantidad: 10}, {cliente: 'ACME', obra: 'A', cantidad: 5}],
  });
  const acme = r.clientes.find(c => c.cliente === 'ACME'), beta = r.clientes.find(c => c.cliente === 'BETA');
  assert.equal(acme.m3Prog, 15, 'se compara normalizado');
  assert.equal(acme.obras_detail[0].m3Prog, 15);
  assert.equal(beta.m3Prog, null, 'no programado no es 0');
});

// ── Macao fuera del cumplimiento (2026-10-09) ───────────────────────────────

test('es Macao lo que dice MACAO en el cliente o en la obra', () => {
  assert.equal(L.esMacao('MACAO ALTO RESORT S.R.L', 'PARMOL'), true);
  assert.equal(L.esMacao('X', 'Malespin Macao II'), true);
  assert.equal(L.esMacao('FIDEICOMISO UNIKO', 'UNIKO RESIDENCES'), false);
});

test('Macao no entra: ni al leer los Excel ni al reabrir un dia guardado', () => {
  const prog = L.parseProgramacionSheets([{nombre: 'PUNTA CANA', rows: [
    ['Cliente', 'Obra', 'Producto', 'Hora Inicio'],
    ['MACAO ALTO RESORT S.R.L', 'PARMOL', 'HORMIGON 210', 0.3125],
    ['X', 'Malespin Macao II', 'HORMIGON 210', 0.3125],
    ['ACME', 'Torre', 'HORMIGON 210', 0.3125],
  ]}]);
  assert.deepEqual(prog.map(f => f.cliente), ['ACME']);
  const { rows } = L.parseCargueSheets([{nombre: 'Hoja1', rows: [
    ['Ficha', 'Hora', 'Cliente', 'Planta', 'Direccion', 'Cantidad'],
    ['F-1', 0.3125, 'MACAO ALTO RESORT S.R.L', 'Movil VIII', 'OBRA: PARMOL', 7],
    ['F-2', 0.3125, 'ACME', 'Movil II', 'OBRA: Torre', 7],
  ]}]);
  assert.deepEqual(rows.map(r => r.cliente), ['ACME'], 'tampoco en el cargue');

  const {state} = L.restaurarDia({fecha: '2026-10-01', supuestos: {cargue: 15, calidad: 10, tolerancia: 30, plantas: []},
    programacion: [{cliente: 'MACAO ALTO RESORT', obra: 'PARMOL'}, {cliente: 'VMO CONCRETOS S. A.', obra: '1'},
                   {cliente: 'ACME', obra: 'Torre'}],
    cargue: [{cliente: 'X', obra: 'MALESPIN MACAO II'}, {cliente: 'ACME', obra: 'Torre'}]});
  assert.deepEqual(state.programacion.map(f => f.cliente), ['ACME'], 'los dias guardados antes tambien');
  assert.deepEqual(state.cargue.map(f => f.cliente), ['ACME']);
});

// ── Excel de cancelados ─────────────────────────────────────────────────────

const ND = (hora, extra = {}) => ({cliente: 'ACME', obra: 'X', hora, bomba: 'Directo', elemento: 'losa',
  vendedor: 'Ana', zonaProg: 'Punta Cana', producto: 'H210', rowKey: 'K' + hora,
  programado: 10, despachado: 3, pendiente: 7, ...extra});

test('cancelados: el encabezado es el del reporte, en ese orden', () => {
  assert.deepEqual(L.filasCancelados([], {}, '2026-09-29').encabezado,
    ['FECHA', 'SEMANAS PROGRAMADAS', 'HORA PROGRAMADA', 'CLIENTE', 'VENDEDOR', 'ZONA', 'ELEMENTO',
     'TIPO DE SERVICIO', 'PRODUCTO', 'VOL. PROGRAMADO', 'RAZON', 'RESPONSABLE', 'MOTIVO']);
});

test('cancelados: fecha como serial de Excel y la semana del mes', () => {
  const [f] = L.filasCancelados([ND(600)], {}, '2026-09-29').filas;
  assert.equal(f.fechaSerial, 46294, '29/09/2026 en Excel');
  assert.equal(f.semana, 'SEMANA 5- SEPTIEMBRE');
  const [g] = L.filasCancelados([ND(600)], {}, '2026-10-07').filas;
  assert.equal(g.semana, 'SEMANA 1- OCTUBRE', 'dias 1 a 7 son la semana 1');
});

test('cancelados: un pedido de las 23:30 da la hora del reloj, no una fraccion mayor a 1 (#170)', () => {
  // 23:30 + el ajuste de 60 min = 1470: daba 1,02 y el servidor rechazaba el
  // reporte entero porque la hora tiene que ser menor a 1.
  const filas = L.filasCancelados([ND(1470), ND(600)], {}, '2026-09-29').filas;
  assert.deepEqual(filas.map(f => f.horaFraccion), [600 / 1440, 30 / 1440]);
  assert.ok(filas.every(f => f.horaFraccion >= 0 && f.horaFraccion < 1));
});

test('cancelados: bomba o directo, mayusculas, razon y responsable de la fila, por hora', () => {
  const state = {observaciones: new Map([['K540', 'no habia bomba']]),
                 responsables: new Map([['K540', 'VMO']])};
  const filas = L.filasCancelados([ND(600), ND(540, {bomba: '45'})], state, '2026-09-29').filas;
  assert.deepEqual(filas.map(f => f.horaFraccion), [540 / 1440, 600 / 1440], 'ordenado por hora');
  assert.deepEqual([filas[0].servicio, filas[1].servicio], ['BOMBA', 'DIRECTO']);
  assert.equal(filas[0].zona, 'PUNTA CANA');
  assert.equal(filas[0].elemento, 'LOSA');
  assert.equal(filas[0].razon, 'no habia bomba');
  assert.equal(filas[0].responsable, 'VMO');
  assert.equal(filas[1].responsable, '');
  assert.equal(filas[0].volumen, 10, 'VOL. PROGRAMADO es lo programado, no lo pendiente');
});

// ── imagen ──────────────────────────────────────────────────────────────────

const fila = (estado, diff, extra = {}) => ({cliente: 'ACME', obraReal: 'X', obraProg: 'X', estado, diff,
  cantProg: 7, horaProg: 480, horaLlegadaEst: 480 + (diff ?? 0), cantReal: 7, cargues: 1,
  bomba: '45', elemento: 'LOSA', rowKey: 'R' + diff, ...extra});

test('imagen: solo los incumplidos, del mas tarde al menos, con la bomba', () => {
  const rows = [fila('Cumplido', 5), fila('Incumplido', 40), fila('Incumplido', 95), fila('Sin despachar', null)];
  const {incumplidos} = L.filasImagenCumplimiento(rows, {responsables: new Map([['R95', 'Cliente']])});
  assert.equal(incumplidos.length, 2);
  assert.equal(incumplidos[0][7], L.fmtDiff(95));
  assert.equal(incumplidos[0][2], '45', 'columna Bomba, nueva en la v17 (11)');
  assert.equal(incumplidos[0][8], 'Cliente');
  assert.equal(incumplidos[1][8], '—');
});

test('imagen: los KPIs son los mismos que la pantalla', () => {
  const rows = [fila('Cumplido', 5), fila('Incumplido', 40)];
  assert.deepEqual(L.filasImagenCumplimiento(rows, {}).resumen, L.resumenDeCumplimiento(rows));
});

// ── responsable y espaciamiento en el dia guardado ──────────────────────────

test('responsable y espaciamiento viajan al guardar y vuelven al abrir', () => {
  const state = {programacion: [], cargue: [], trayectoOverrides: new Map(), observaciones: new Map(),
                 responsables: new Map([['K1', 'VMO'], ['K2', ''], ['K3', 'Otro']])};
  const p = L.payloadDelDia(state, {cargue: 15, calidad: 10, tolerancia: 30, espaciamiento: 45,
                                    trayecto: {}, zonaPlanta: {}}, '2026-09-29');
  assert.deepEqual(p.responsables, {K1: 'VMO'}, 'vacio o fuera de la lista no se guarda');
  assert.equal(p.espaciamiento, 45);
  const {state: st, assumptions: asm} = L.restaurarDia({fecha: '2026-09-29', responsables: p.responsables,
    supuestos: {cargue: 15, calidad: 10, tolerancia: 30, plantas: [], espaciamiento: null}});
  assert.equal(st.responsables.get('K1'), 'VMO');
  assert.equal(asm.espaciamiento, L.ESPACIAMIENTO_POR_DEFECTO, 'un dia sin el supuesto cae al default');
});

// ── motivo (2026-10-06) ─────────────────────────────────────────────────────

test('la lista de motivos es la que paso el usuario, en ese orden', () => {
  assert.deepEqual(L.MOTIVOS, ['PROBLEMAS CLIMATICOS', 'RETRASOS EN OBRA', 'SIN COLOCACION',
    'ELEMENTO NO LISTO', 'INCONVENIENTES EN OBRA', 'AVERIA DE BOMBA', 'AVERIA DE PLANTA',
    'DISPONIBILIDAD DE CAMIONES', 'TARDANZA DE BOMBA', 'REVISION CALIDAD',
    'RETRASO EN LA SALIDA DE PLANTA', 'LLEGADA TARDE PERSONAL', 'ACCIDENTE',
    'DIFICIL ACCESO EN OBRA', 'OBSTRUCCION ESTACIONAMIENTO DE LA BOMBA',
    'DISPONIBILIDAD DE MANGUERAS', 'PRIORIDAD OTRO ELEMENTO', 'PERMISOS DE OBRA',
    'MISMO HORARIO ELEMENTOS', 'PASE DE INGRESO A OBRA', 'DESPACHO VMO',
    'INICIO DE CARGA VMO', 'HORARIO PROGRAMADO', 'CAMBIO DE PEDIDO', 'SIN SISTEMA', 'OPERACIONES',
    'PRIORIDAD OTRO SERVICIO']);
});

test('el motivo viaja al guardar y vuelve al abrir; vacio o desconocido no se guarda', () => {
  const state = {programacion: [], cargue: [], trayectoOverrides: new Map(), observaciones: new Map(),
                 motivos: new Map([['K1', 'AVERIA DE BOMBA'], ['K2', ''], ['K3', 'LLOVIO']])};
  const p = L.payloadDelDia(state, {cargue: 15, calidad: 10, tolerancia: 30, trayecto: {}, zonaPlanta: {}}, '2026-09-29');
  assert.deepEqual(p.motivos, {K1: 'AVERIA DE BOMBA'});
  const {state: st} = L.restaurarDia({fecha: '2026-09-29', motivos: p.motivos,
    supuestos: {cargue: 15, calidad: 10, tolerancia: 30, plantas: []}});
  assert.equal(st.motivos.get('K1'), 'AVERIA DE BOMBA');
});

test('el motivo va en el Excel de cancelados y en la imagen, entre responsable y observaciones', () => {
  const state = {motivos: new Map([['K540', 'SIN COLOCACION']]), responsables: new Map([['K540', 'Cliente']]),
                 observaciones: new Map([['K540', 'nota']])};
  const [f] = L.filasCancelados([ND(540)], state, '2026-09-29').filas;
  assert.equal(f.motivo, 'SIN COLOCACION');
  const img = L.filasImagenCumplimiento([fila('Incumplido', 40, {rowKey: 'K540'})], state).incumplidos[0];
  assert.deepEqual(img.slice(8), ['Cliente', 'SIN COLOCACION', 'nota']);
});

// ── Motivos de incumplimiento: Pareto y circulos por responsable ────────────

const inc = (rowKey, cantReal, planta = 'Movil II') => ({estado: 'Incumplido', rowKey, cantReal, planta});
const diaP = (results, motivos, responsables) => ({
  results, noDespachado: [{rowKey: 'nd', pendiente: 50}],
  motivos: new Map(motivos), responsables: new Map(responsables)});
// cada caso: [rowKey, m3, motivo, responsable]
const casos = lista => diaP(lista.map(([k, m3]) => inc(k, m3)),
                            lista.map(([k, , m]) => [k, m]), lista.map(([k, , , r]) => [k, r]));

test('pareto: ordena por entregas con % y acumulado, sobre varios dias', () => {
  const p = L.paretoDeMotivos([
    casos([['a', 7, 'AVERIA DE BOMBA', 'VMO'], ['b', 7, 'AVERIA DE BOMBA', 'VMO'], ['c', 7, 'SIN COLOCACION', 'Cliente']]),
    casos([['a', 7, 'AVERIA DE BOMBA', 'VMO']]),
  ]);
  assert.deepEqual(p.motivos.map(m => [m.motivo, m.entregas, m.pct, m.pctAcumulado]),
                   [['AVERIA DE BOMBA', 3, 75, 75], ['SIN COLOCACION', 1, 25, 100]]);
});

test('pareto: por m3 cambia el orden — una sola entrega grande puede pesar mas', () => {
  const dias = [casos([['a', 2, 'RETRASOS EN OBRA', 'Cliente'], ['b', 2, 'RETRASOS EN OBRA', 'Cliente'],
                       ['c', 40, 'AVERIA DE PLANTA', 'VMO']])];
  assert.equal(L.paretoDeMotivos(dias).motivos[0].motivo, 'RETRASOS EN OBRA');
  const m3 = L.paretoDeMotivos(dias, {orden: 'm3'});
  assert.equal(m3.motivos[0].motivo, 'AVERIA DE PLANTA');
  assert.equal(m3.motivos[0].pct, 91);
});

test('pareto: SOLO incumplidos — ni lo no despachado ni una cumplida con motivo', () => {
  const d = casos([['a', 7, 'SIN COLOCACION', 'Cliente']]);
  d.results.push({estado: 'Cumplido', rowKey: 'ok', cantReal: 7});
  d.motivos.set('ok', 'SIN COLOCACION'); d.responsables.set('ok', 'VMO');
  d.motivos.set('nd', 'SIN COLOCACION'); d.responsables.set('nd', 'VMO');
  const p = L.paretoDeMotivos([d]);
  assert.deepEqual([p.motivos[0].entregas, p.motivos[0].m3], [1, 7]);
});

test('pareto: sin motivo o sin responsable no entra; se cuenta como dato por cargar', () => {
  const p = L.paretoDeMotivos([casos([['a', 7, 'AVERIA DE BOMBA', 'VMO'], ['b', 5, null, 'VMO'],
                                      ['c', 3, 'AVERIA DE BOMBA', null]])]);
  assert.deepEqual(p.cobertura, {incumplidas: 3, completas: 1, sinMotivo: 1, sinResponsable: 1, m3Incompletos: 8});
  assert.equal(p.motivos[0].entregas, 1);
  assert.equal(p.motivos[0].pct, 100);
});

test('pareto: filtrado por responsable, que es lo que hace tocar un circulo', () => {
  const p = L.paretoDeMotivos([casos([['a', 7, 'AVERIA DE BOMBA', 'VMO'], ['b', 7, 'SIN COLOCACION', 'Cliente'],
                                      ['c', 7, 'SIN COLOCACION', 'Cliente']])], {responsable: 'Cliente'});
  assert.deepEqual(p.motivos.map(m => [m.motivo, m.pct]), [['SIN COLOCACION', 100]]);
});

test('pareto: con planta elegida, solo sus incumplidas', () => {
  const d = diaP([inc('a', 7, 'Movil II'), inc('b', 7, 'Movil III')], [['a', 'X'], ['b', 'Y']], [['a', 'VMO'], ['b', 'VMO']]);
  assert.deepEqual(L.paretoDeMotivos([d], {planta: 'Movil III'}).motivos.map(m => m.motivo), ['Y']);
});

test('circulos: uno por responsable, en orden fijo, con su parte del total', () => {
  const r = L.motivosPorResponsable([casos([
    ['a', 7, 'AVERIA DE BOMBA', 'VMO'], ['b', 7, 'AVERIA DE PLANTA', 'VMO'], ['c', 7, 'SIN COLOCACION', 'Cliente'],
    ['d', 7, 'PROBLEMAS CLIMATICOS', 'Externo']])]);
  assert.deepEqual(r.responsables.map(x => [x.responsable, x.casos, x.pct]),
                   [['VMO', 2, 50], ['Cliente', 1, 25], ['Externo', 1, 25]]);
  assert.deepEqual(r.responsables[0].motivos.map(m => [m.motivo, m.pct]),
                   [['AVERIA DE BOMBA', 50], ['AVERIA DE PLANTA', 50]]);
});

test('circulos: un responsable sin casos sale igual, vacio', () => {
  const r = L.motivosPorResponsable([casos([['a', 7, 'AVERIA DE BOMBA', 'VMO']])]);
  const ext = r.responsables.find(x => x.responsable === 'Externo');
  assert.deepEqual([ext.casos, ext.pct, ext.segmentos], [0, 0, []]);
});

test('circulos: se colorean los top del TOTAL y los principales de CADA circulo', () => {
  // REGRESION de la primera version: solo el top del total tenia color, y el
  // circulo de Externo —motivos chicos en el total— salia entero en gris.
  const lista = [];
  ['A', 'B', 'C', 'D', 'E', 'F'].forEach((m, i) => { for (let j = 0; j < 7 - i; j++) lista.push(['v' + m + j, 7, m, 'VMO']); });
  lista.push(['x1', 7, 'CLIMA', 'Externo']);
  const r = L.motivosPorResponsable([casos(lista)], {top: 5, porCirculo: 2});
  assert.deepEqual(r.destacados, ['A', 'B', 'C', 'D', 'E', 'CLIMA'],
    'F es sexto en el total y no es principal de nadie: va a Otros; CLIMA es el principal de Externo');
  assert.deepEqual(r.responsables.find(x => x.responsable === 'Externo').segmentos,
                   [{motivo: 'CLIMA', valor: 1, pct: 100}]);
  assert.ok(r.responsables[0].segmentos.some(g => g.motivo === 'Otros'));
});

test('circulos: el tope de motivos con color se respeta', () => {
  const lista = [];
  'ABCDEFGHIJK'.split('').forEach((m, i) => { for (let j = 0; j < 12 - i; j++) lista.push([m + j, 7, m, RESP3[i % 3]]); });
  const r = L.motivosPorResponsable([casos(lista)], {max: 4});
  assert.deepEqual(r.destacados, ['A', 'B', 'C', 'D'], 'tope respetado, y en el orden del total');
  assert.ok(L.motivosPorResponsable([casos(lista)]).destacados.length <= 8);
});
const RESP3 = ['VMO', 'Cliente', 'Externo'];

test('circulos: el peso sigue el selector — por m3 la parte de cada uno cambia', () => {
  const d = [casos([['a', 30, 'X', 'VMO'], ['b', 5, 'Y', 'Cliente'], ['c', 5, 'Y', 'Cliente']])];
  assert.equal(L.motivosPorResponsable(d).responsables[0].pct, 33);
  assert.equal(L.motivosPorResponsable(d, {orden: 'm3'}).responsables[0].pct, 75);
});

test('motivos: un historial sin casos no revienta', () => {
  assert.deepEqual(L.paretoDeMotivos([]).motivos, []);
  assert.equal(L.motivosPorResponsable([]).total, 0);
});

test('circulo Todos: el reparto de motivos de todos los responsables juntos', () => {
  const r = L.motivosPorResponsable([casos([['a', 7, 'X', 'VMO'], ['b', 7, 'X', 'Cliente'], ['c', 7, 'Y', 'Externo'],
                                            ['d', 7, null, 'VMO']])]);
  assert.deepEqual([r.todos.responsable, r.todos.casos, r.todos.pct], ['Todos', 3, 100],
    'el que no tiene motivo no entra, igual que en los botones');
  assert.deepEqual(r.todos.motivos.map(m => [m.motivo, m.pct]), [['X', 67], ['Y', 33]]);
});

// ── porcentajes que suman 100 ───────────────────────────────────────────────

test('porcentajes: 14, 12 y 3 de 29 suman 100, no 99', () => {
  // REGRESION 2026-10-06: redondeado cada uno por su lado daba 48 + 41 + 10.
  // Exactos 48,28 / 41,38 / 10,34: el punto que falta va al resto mayor, Cliente.
  assert.deepEqual(L.porcentajesQueSuman100([14, 12, 3]), [48, 42, 10]);
});

test('porcentajes: siempre suman 100, y un total 0 da ceros', () => {
  for (const v of [[1, 1, 1], [2, 2, 2, 1], [6, 5, 4, 4, 3, 3, 2, 1, 1], [7], [0, 5]]) {
    assert.equal(L.porcentajesQueSuman100(v).reduce((s, x) => s + x, 0), 100, JSON.stringify(v));
  }
  assert.deepEqual(L.porcentajesQueSuman100([0, 0]), [0, 0]);
});

test('botones, circulo y Pareto suman 100, y el ultimo acumulado es 100', () => {
  const lista = [];
  [['A', 'VMO', 14], ['B', 'Cliente', 12], ['C', 'Externo', 3]].forEach(([m, r, n]) => {
    for (let j = 0; j < n; j++) lista.push([m + j, 7, m, r]);
  });
  const r = L.motivosPorResponsable([casos(lista)]);
  assert.deepEqual(r.responsables.map(x => x.pct), [48, 42, 10]);
  const p = L.paretoDeMotivos([casos(lista)]);
  assert.equal(p.motivos.reduce((s, m) => s + m.pct, 0), 100);
  assert.equal(p.motivos[p.motivos.length - 1].pctAcumulado, 100);
  assert.equal(r.todos.segmentos.reduce((s, g) => s + g.pct, 0), 100);
});
