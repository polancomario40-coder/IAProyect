// El dia, de ida y de vuelta: lo que se manda a guardar y lo que se recibe al
// reabrirlo. Lo que se prueba es que no se pierda nada por el camino, que es
// lo unico que puede salir mal en una capa que no calcula.
const test = require('node:test');
const assert = require('node:assert');
const { payloadDelDia, restaurarDia, computeCumplimiento } = require('../../static/logistica.logic.js');

const ESTADO = () => ({
  programacion: [{cliente:'ACME', obra:'TORRE ALFA', horaMin:480, pedido:4417, cantidad:10,
                  elemento:null, producto:null, prioridad:null, zonaSheet:'Santo Domingo'}],
  cargue: [{ficha:'F-1', horaMin:420, cliente:'ACME', conduce:98765, elemento:null,
            planta:'Movil II', obra:'TORRE ALFA', cantidad:7}],
  trayectoOverrides: new Map([['ACME||TORRE ALFA', 45]]),
  observaciones: new Map([['ACME||TORRE ALFA||DIRECTO||||480', 'salio tarde de planta']]),
  fecha: '2026-09-29',
});

const SUPUESTOS = () => ({
  cargue: 15, calidad: 10, tolerancia: 30,
  trayecto: {'Movil II': 30, 'Movil III': 15},
  zonaPlanta: {'Movil II': 'Santo Domingo', 'Movil III': 'Punta Cana'},
});

test('el payload lleva los supuestos de plantas como lista, no como objeto suelto', () => {
  const p = payloadDelDia(ESTADO(), SUPUESTOS(), '2026-09-29');
  assert.deepEqual(p.plantas, [
    {planta:'Movil II', trayecto:30, zona:'Santo Domingo'},
    {planta:'Movil III', trayecto:15, zona:'Punta Cana'},
  ]);
  assert.equal(p.fecha, '2026-09-29');
  assert.equal(p.cargue, 15);
  assert.equal(p.tolerancia, 30);
});

test('los Map se mandan como objetos planos', () => {
  const p = payloadDelDia(ESTADO(), SUPUESTOS(), '2026-09-29');
  assert.deepEqual(p.trayectoOverrides, {'ACME||TORRE ALFA': 45});
  assert.deepEqual(p.observaciones, {'ACME||TORRE ALFA||DIRECTO||||480': 'salio tarde de planta'});
});

test('una observacion vacia no se guarda', () => {
  const st = ESTADO();
  st.observaciones.set('OTRO||OBRA', '   ');
  const p = payloadDelDia(st, SUPUESTOS(), '2026-09-29');
  assert.deepEqual(Object.keys(p.observaciones), ['ACME||TORRE ALFA||DIRECTO||||480'],
    'borrar el texto de una fila tiene que borrar la observacion, no guardar un espacio');
});

test('un dashboard sin archivos cargados no revienta al armar el payload', () => {
  const p = payloadDelDia({programacion:null, cargue:null}, SUPUESTOS(), '2026-09-29');
  assert.deepEqual(p.programacion, []);
  assert.deepEqual(p.cargue_rows, []);
  assert.deepEqual(p.observaciones, {});
});

test('una planta sin zona viaja con zona null, no se pierde de la lista', () => {
  const asm = SUPUESTOS();
  asm.trayecto['Planta Nueva'] = 25;
  const p = payloadDelDia(ESTADO(), asm, '2026-09-29');
  const nueva = p.plantas.find(x => x.planta === 'Planta Nueva');
  assert.deepEqual(nueva, {planta:'Planta Nueva', trayecto:25, zona:null});
});

// ── la vuelta: reabrir el dia ──

// Lo que devuelve la API para un dia guardado, en la forma exacta en que lo
// devuelve (GET /api/logistica/dias/{fecha}).
const DIA_GUARDADO = () => ({
  fecha: '2026-09-29',
  guardado_en: '2026-09-29T18:04:11',
  supuestos: {
    cargue: 15, calidad: 10, tolerancia: 30,
    plantas: [{planta:'Movil II', trayecto:30, zona:'Santo Domingo'},
              {planta:'Movil III', trayecto:15, zona:'Punta Cana'}],
  },
  programacion: [{cliente:'ACME', obra:'TORRE ALFA', horaMin:480, pedido:'4417', cantidad:10,
                  elemento:null, producto:null, prioridad:null, zonaSheet:'Santo Domingo'}],
  cargue: [{ficha:'F-1', horaMin:420, cliente:'ACME', conduce:'98765', elemento:null,
            planta:'Movil II', obra:'TORRE ALFA', cantidad:7}],
  trayectoOverrides: {'ACME||TORRE ALFA': 45},
  // La observacion va por fila desde el 2026-10-06: cliente, obra, bomba,
  // elemento y hora. Sin bomba es Directo; sin elemento, vacio.
  observaciones: {'ACME||TORRE ALFA||DIRECTO||||480': 'salio tarde de planta'},
});

test('restaurar devuelve el estado y los supuestos en la forma que usa el dashboard', () => {
  const {state, assumptions} = restaurarDia(DIA_GUARDADO());
  assert.ok(state.trayectoOverrides instanceof Map, 'los overrides vuelven a ser Map');
  assert.ok(state.observaciones instanceof Map);
  assert.equal(state.trayectoOverrides.get('ACME||TORRE ALFA'), 45);
  assert.equal(state.observaciones.get('ACME||TORRE ALFA||DIRECTO||||480'), 'salio tarde de planta');
  assert.deepEqual(assumptions.trayecto, {'Movil II': 30, 'Movil III': 15});
  assert.deepEqual(assumptions.zonaPlanta, {'Movil II': 'Santo Domingo', 'Movil III': 'Punta Cana'});
  assert.equal(state.fecha, '2026-09-29');
});

test('ida y vuelta: guardar y reabrir no pierde nada', () => {
  const ida = payloadDelDia(ESTADO(), SUPUESTOS(), '2026-09-29');
  // La API devuelve los supuestos anidados; se arma esa forma a partir del payload.
  const comoLoDevuelveLaApi = {
    fecha: ida.fecha, guardado_en: '2026-09-29T18:04:11',
    supuestos: {cargue: ida.cargue, calidad: ida.calidad, tolerancia: ida.tolerancia,
                plantas: ida.plantas},
    programacion: ida.programacion, cargue: ida.cargue_rows,
    trayectoOverrides: ida.trayectoOverrides, observaciones: ida.observaciones,
  };
  const vuelta = payloadDelDia(restaurarDia(comoLoDevuelveLaApi).state,
                               restaurarDia(comoLoDevuelveLaApi).assumptions, '2026-09-29');
  assert.deepEqual(vuelta, ida, 'el segundo viaje tiene que dar exactamente lo mismo que el primero');
});

test('reabrir un dia da el MISMO cumplimiento que calcular ese dia en vivo', () => {
  // Es la prueba que justifica todo el diseno de la base: no se guarda el
  // resultado, se guardan los crudos y los supuestos, asi que reabrir tiene
  // que dar identico. Si esto falla, el historial miente.
  const enVivo = computeCumplimiento(ESTADO(), SUPUESTOS());
  const {state, assumptions} = restaurarDia(DIA_GUARDADO());
  const reabierto = computeCumplimiento(state, assumptions);

  const resumir = c => c.results.map(r => ({
    cliente: r.cliente, obra: r.obraReal, estado: r.estado, diff: r.diff,
    trayecto: r.trayecto, llegada: r.horaLlegadaEst, obs: r.observacion,
  }));
  assert.deepEqual(resumir(reabierto), resumir(enVivo));

  // Y que el dia reabierto use de verdad lo guardado, no los defaults: con el
  // trayecto corregido a mano (45) la llegada es 07:00+15+10+45 = 490; con el
  // de la planta (30) seria 475. Que de 490 prueba que el override sobrevivio.
  assert.equal(reabierto.results[0].trayecto, 45);
  assert.equal(reabierto.results[0].horaLlegadaEst, 490);
  assert.equal(reabierto.results[0].isOverride, true);
  assert.equal(reabierto.results[0].observacion, 'salio tarde de planta');
});

test('los supuestos de HOY no contaminan un dia viejo', () => {
  // Si alguien sube la tolerancia manana, el dia guardado tiene que seguir
  // dando lo que dio: sus supuestos viajan con el.
  const dia = DIA_GUARDADO();
  dia.supuestos.tolerancia = 5;
  const {state, assumptions} = restaurarDia(dia);
  assert.equal(assumptions.tolerancia, 5);
  assert.notEqual(assumptions.tolerancia, SUPUESTOS().tolerancia);
});

test('los conteos del Historial no cuentan Macao aunque el dia se haya guardado con Macao (#171)', () => {
  const L2 = require('../../static/logistica.logic.js');
  const dia = {fecha: '2026-10-02', supuestos: {cargue: 15, calidad: 10, tolerancia: 30, plantas: []},
    programacion: [{cliente: 'ACME', obra: 'TORRE', horaMin: 480, cantidad: 10},
                   {cliente: 'MACAO ALTO RESORT SRL', obra: 'MACAO II', horaMin: 480, cantidad: 30}],
    cargue: [{cliente: 'ACME', obra: 'TORRE', ficha: 'F-1', cantidad: 10, horaMin: 420, planta: 'Movil II'},
             {cliente: 'MACAO ALTO RESORT SRL', obra: 'MACAO II', ficha: 'F-2', cantidad: 30, horaMin: 430, planta: 'Movil IV'}],
    trayectoOverrides: {}, observaciones: {}, responsables: {}, motivos: {}};
  assert.deepEqual(L2.conteosDelDia(L2.restaurarDia(dia).state),
    {pedidos: 1, cargues: 1, m3: 10, clientes: 1, camiones: 1});
});
