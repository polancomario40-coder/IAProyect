// El dashboard Comercial (2026-10-19): la misma logica que las tablas
// dinamicas de "DASHBOARD COMERCIAL 2026.xlsx". Vive en esta carpeta porque es
// la que corre test_logistica_js.py; el modulo es otro (static/comercial.logic.js).
const test = require('node:test');
const assert = require('node:assert');
const C = require('../../static/comercial.logic.js');

// Como lo devuelve GET /api/comercial/datos.
// filas: [mes, vendedor, planta, cliente, condicion, zona, rango, cantidad, precio, line_total]
const datos = {
  anio: 2026,
  dimensiones: ['vendedor', 'planta', 'cliente', 'condicion', 'zona', 'rango_fc'],
  valores: {
    vendedor: ['Ana', 'Kathy'], planta: ['Movil II', 'Movil VIII'], cliente: ['ACME', 'BETA', 'GAMA'],
    condicion: ['30 DIAS'], zona: ['SDQ', 'PROYECTOS', ''], rango_fc: ['FC 210', 'FC 280'],
  },
  filas: [
    [8, 0, 0, 0, 0, 0, 0, 10, 7000, 70000],
    [9, 0, 0, 0, 0, 0, 0, 6, 7000, 42000],
    [9, 0, 1, 1, 0, 1, 1, 20, 9000, 180000],
    [9, 1, 1, 2, 0, 2, 1, 4, 8000, 32000],
  ],
  plan: {8: 20, 9: 40},
};

test('los cuatro numeros de arriba, como el Excel', () => {
  const r = C.dashboard(datos, {mes: [9]});
  assert.equal(r.m3, 30);
  assert.equal(r.rd, 254000);
  assert.equal(r.clientes, 3);
  // PROMEDIO de PRECIO fila por fila (el Excel), no RD$ / m3.
  assert.equal(r.precioPromedio, 8000);
  assert.notEqual(r.precioPromedio, 254000 / 30);
});

test('el cumplimiento sin filtro de mes es el acumulado de los meses con despachos vs su plan', () => {
  // Hasta el 2026-10-22 era solo el ultimo mes (9): 30 de 40.
  const c = C.dashboard(datos, {}).cumplimiento;
  assert.deepEqual(c.meses, [8, 9]);
  assert.equal(c.acumulado, true);
  assert.equal(c.m3, 40);
  assert.equal(c.plan, 60);
  assert.equal(Math.round(c.pct), 67);
  assert.equal(C.dashboard(datos, {mes: [9]}).cumplimiento.acumulado, false);
});

test('con meses elegidos, suma esos meses y su plan; sin plan no inventa', () => {
  const c = C.dashboard(datos, {mes: [8, 9]}).cumplimiento;
  assert.equal(c.m3, 40);
  assert.equal(c.plan, 60);
  const sinPlan = C.dashboard({...datos, plan: {9: 40}}, {mes: [8]}).cumplimiento;
  assert.equal(sinPlan.plan, null);
  assert.equal(sinPlan.pct, null);
});

test('los filtros filtran todo, cumplimiento incluido (como los segmentadores)', () => {
  const r = C.dashboard(datos, {vendedor: ['Ana']});
  assert.equal(r.m3, 36);
  assert.equal(r.cumplimiento.m3, 36, 'sin filtro de mes, el acumulado de Ana');
  assert.deepEqual(r.porVendedor.map(g => g.nombre), ['Ana']);
  const dos = C.dashboard(datos, {zona: ['SDQ'], planta: ['Movil II']});
  assert.equal(dos.m3, 16);
});

test('los graficos agrupan y ordenan por valor; lo vacio va como (vacío)', () => {
  const r = C.dashboard(datos, {mes: [9]});
  assert.deepEqual(r.porZona.map(g => [g.nombre, g.m3, g.pct]), [['PROYECTOS', 20, 67], ['SDQ', 6, 20], ['(vacío)', 4, 13]]);
  assert.deepEqual(r.porCliente.map(g => g.nombre), ['BETA', 'ACME', 'GAMA']);
  assert.deepEqual(r.porRango.map(g => [g.nombre, g.precioPromedio]), [['FC 280', 8500], ['FC 210', 7000]]);
  assert.deepEqual(r.rdPorVendedor.map(g => [g.nombre, g.pct]), [['Ana', 87], ['Kathy', 13]]);
  assert.deepEqual(C.dashboard(datos, {}).porMes.map(m => [m.nombre, m.m3, m.plan]), [['Agosto', 10, 20], ['Septiembre', 30, 40]]);
  // El vacio se puede filtrar como cualquier otro valor.
  assert.equal(C.dashboard(datos, {zona: ['(vacío)']}).m3, 4);
});

test('sin despachos no se rompe', () => {
  const vacio = {...datos, filas: []};
  const r = C.dashboard(vacio, {});
  assert.equal(r.m3, 0);
  assert.equal(r.clientes, 0);
  assert.equal(r.precioPromedio, null);
  assert.deepEqual(r.cumplimiento.meses, []);
});

test('los porcentajes de una dona suman 100 y mas de 8 porciones van a Otros', () => {
  assert.equal(C.porcentajes([1, 1, 1]).reduce((s, v) => s + v, 0), 100);
  const lista = Array.from({length: 10}, (_, i) => ({nombre: `V${i}`, m3: 10 - i, rd: 10 - i}));
  const plegada = C.plegar(lista, 'rd', 8);
  assert.equal(plegada.length, 8);
  assert.equal(plegada[7].nombre, 'Otros (3)');
  assert.equal(plegada[7].rd, 3 + 2 + 1);
  assert.equal(plegada.reduce((s, g) => s + g.pct, 0), 100);
});

test('las opciones de cada filtro salen de todo el ano', () => {
  const o = C.opcionesDeFiltro(datos);
  assert.deepEqual(o.mes, [8, 9]);
  assert.deepEqual(o.zona, ['(vacío)', 'PROYECTOS', 'SDQ']);
});

// ── Vendedoras de oficina dentro de Oficina (2026-10-21) ────────────────────

const conOficina = {
  ...datos,
  valores: {...datos.valores, vendedor: ['Oficina', 'Ana Taveras', 'Katherine Concepcion', 'Nikaulis de la cruz', 'Denisse']},
  filas: [
    [9, 0, 0, 0, 0, 0, 0, 10, 7000, 70000],
    [9, 1, 0, 0, 0, 0, 0, 5, 7000, 35000],
    [9, 2, 0, 0, 0, 0, 0, 3, 7000, 21000],
    [9, 3, 0, 0, 0, 0, 0, 2, 7000, 14000],
    [9, 4, 0, 0, 0, 0, 0, 12, 7000, 84000],
  ],
};

test('en m3 por vendedor, Ana Taveras, Katherine Concepcion y Nikaulis van en Oficina', () => {
  const r = C.dashboard(conOficina, {});
  assert.deepEqual(r.porVendedor.map(g => [g.nombre, g.m3]), [['Oficina', 20], ['Denisse', 12]]);
  assert.deepEqual(r.porVendedor[0].incluye.map(i => [i.nombre, i.m3]),
    [['Oficina', 10], ['Ana Taveras', 5], ['Katherine Concepcion', 3], ['Nikaulis de la cruz', 2]]);
  assert.equal(r.porVendedor[1].incluye, undefined);
});

test('solo en ese grafico: RD$ por vendedor y el filtro siguen por nombre', () => {
  const r = C.dashboard(conOficina, {});
  assert.deepEqual(r.rdPorVendedor.map(g => g.nombre).sort(),
    ['Ana Taveras', 'Denisse', 'Katherine Concepcion', 'Nikaulis de la cruz', 'Oficina']);
  assert.ok(C.opcionesDeFiltro(conOficina).vendedor.includes('Ana Taveras'));
});

test('el clic en Oficina filtra por todos los del ano, no solo los del mes elegido (#178)', () => {
  // Nikaulis no vendio en octubre: con ese mes filtrado no esta en `incluye`,
  // pero tiene que estar en lo que filtra el clic.
  const d = {...conOficina, filas: [...conOficina.filas, [10, 0, 0, 0, 0, 0, 0, 4, 7000, 28000]]};
  const r = C.dashboard(d, {mes: [10]});
  assert.deepEqual(r.porVendedor[0].incluye, undefined, 'en octubre solo vendio Oficina');
  assert.deepEqual(r.porVendedor[0].valores,
    ['Oficina', 'Ana Taveras', 'Katherine Concepcion', 'Nikaulis de la cruz']);
  assert.equal(r.porVendedor.find(g => g.nombre === 'Denisse'), undefined);
  assert.deepEqual(C.dashboard(d, {}).porTipoVendedor.find(g => g.nombre === 'Interno').valores,
    ['Oficina', 'Ana Taveras', 'Katherine Concepcion', 'Nikaulis de la cruz']);
});

test('filtrar por todos los de Oficina da la misma barra', () => {
  const todos = ['Oficina', 'Ana Taveras', 'Katherine Concepcion', 'Nikaulis de la cruz'];
  const r = C.dashboard(conOficina, {vendedor: todos});
  assert.deepEqual(r.porVendedor.map(g => [g.nombre, g.m3]), [['Oficina', 20]]);
});

// ── m3 por tipo de vendedor (2026-10-21) ────────────────────────────────────

test('Interno es Oficina, las vendedoras de oficina y Denisse; Externo, el resto', () => {
  const d = {...conOficina, valores: {...conOficina.valores,
    vendedor: ['Oficina', 'Ana Taveras', 'Katherine Concepcion', 'Nikaulis de la cruz', 'Denisse Rosario']}};
  d.filas = [...d.filas, [9, 0, 0, 0, 0, 0, 0, 0, 0, 0]];
  d.valores.vendedor.push('Marisol Lugo');
  d.filas.push([9, 5, 0, 0, 0, 0, 0, 8, 7000, 56000]);
  const r = C.dashboard(d, {});
  assert.deepEqual(r.porTipoVendedor.map(g => [g.nombre, g.m3, g.pct]), [['Interno', 32, 80], ['Externo', 8, 20]]);
  assert.deepEqual(r.porTipoVendedor[0].incluye.map(i => i.nombre),
    ['Denisse Rosario', 'Oficina', 'Ana Taveras', 'Katherine Concepcion', 'Nikaulis de la cruz']);
  assert.deepEqual(r.porTipoVendedor[1].incluye.map(i => i.nombre), ['Marisol Lugo'],
    'aun con uno solo, el clic filtra por su nombre y no por "Externo"');
});

test('el tipo de vendedor suma lo mismo que el total', () => {
  const r = C.dashboard(conOficina, {mes: [9]});
  assert.equal(r.porTipoVendedor.reduce((s, g) => s + g.m3, 0), r.m3);
});

// ── Macao en una sola barra de m3 por cliente (2026-10-21) ─────────────────

test('en m3 por cliente todos los MACAO ALTO RESORT van en una barra', () => {
  const d = {...datos, valores: {...datos.valores, cliente: [
    'MACAO ALTO RESORT S.R.L, (MACAO II, ESTRUCTURA)', 'MACAO ALTO RESORT SRL (CEDIS)', 'ACME']}};
  const r = C.dashboard(d, {});
  assert.deepEqual(r.porCliente.map(g => [g.nombre, g.m3]), [['MACAO ALTO RESORT', 36], ['ACME', 4]]);
  assert.deepEqual(r.porCliente[0].incluye.map(i => [i.nombre, i.m3]),
    [['MACAO ALTO RESORT SRL (CEDIS)', 20], ['MACAO ALTO RESORT S.R.L, (MACAO II, ESTRUCTURA)', 16]]);
  assert.equal(r.clientes, 3, 'Total clientes sigue contando cada nombre');
  assert.ok(C.opcionesDeFiltro(d).cliente.includes('MACAO ALTO RESORT SRL (CEDIS)'));
});

// ── Precio vs ppto (2026-10-21) ─────────────────────────────────────────────

test('precio vs ppto: RD$ / m3 del mes contra el precio del plan', () => {
  const p = C.dashboard({...datos, planPrecio: {8: 7000, 9: 8000}}, {mes: [9]}).precioVsPpto;
  assert.deepEqual(p.meses, [9]);
  assert.equal(p.real, 254000 / 30, 'RD$ vendidos / m3, no el promedio de PRECIO');
  assert.equal(p.plan, 8000);
  assert.equal(p.pct, 254000 / 30 / 8000 * 100);
});

test('con varios meses, el precio del plan pesa cada mes por sus m3 de plan', () => {
  const p = C.dashboard({...datos, planPrecio: {8: 7000, 9: 8000}}, {mes: [8, 9]}).precioVsPpto;
  assert.equal(p.plan, (7000 * 20 + 8000 * 40) / 60);
  assert.equal(p.real, (70000 + 254000) / 40);
  // Sin filtro de mes es el acumulado: los mismos dos meses.
  assert.deepEqual(C.dashboard({...datos, planPrecio: {8: 7000, 9: 8000}}, {}).precioVsPpto, p);
});

test('sin precio de plan no inventa', () => {
  const p = C.dashboard(datos, {}).precioVsPpto;
  assert.equal(p.plan, null);
  assert.equal(p.pct, null);
});

test('precio y ventas vs ppto van solo en los meses con precio de plan, y dicen cuales (#180)', () => {
  // Ene-Jun van contra el plan original, que no trae precio: sin filtro, el
  // volumen es "Ene-Sep" y el precio y las ventas "Jul-Sep".
  const d = {...datos, planPrecio: {9: 8000}};
  const r = C.dashboard(d, {mes: [8, 9]});
  assert.deepEqual(r.cumplimiento.meses, [8, 9]);
  assert.deepEqual(r.precioVsPpto.meses, [9]);
  assert.equal(r.precioVsPpto.real, 254000 / 30, 'el real tambien solo de septiembre');
  assert.equal(r.precioVsPpto.plan, 8000);
  assert.deepEqual(r.ventasVsPpto.meses, [9]);
  assert.equal(r.ventasVsPpto.real, 254000);
  assert.equal(C.dashboard(d, {mes: [8]}).precioVsPpto.pct, null, 'un mes sin precio de plan no inventa');
});

// ── Ventas RD$ vs ppto (2026-10-21) ─────────────────────────────────────────

test('ventas vs ppto: RD$ vendidos contra precio x m3 del plan de esos meses', () => {
  const d = {...datos, planPrecio: {8: 7000, 9: 8000}};
  const v = C.dashboard(d, {mes: [9]}).ventasVsPpto;
  assert.equal(v.real, 254000);
  assert.equal(v.plan, 8000 * 40);
  assert.equal(v.pct, 254000 / 320000 * 100);
  const dos = C.dashboard(d, {mes: [8, 9]}).ventasVsPpto;
  assert.equal(dos.plan, 7000 * 20 + 8000 * 40);
  assert.equal(dos.real, 70000 + 254000);
  assert.deepEqual(C.dashboard(d, {}).ventasVsPpto, dos, 'sin filtro de mes, el acumulado');
  assert.equal(C.dashboard(datos, {}).ventasVsPpto.pct, null, 'sin precio de plan no inventa');
});

// ── Linea del precio de venta por mes (2026-10-21) ──────────────────────────

test('cada mes lleva su precio de venta, RD$ / m3', () => {
  const porMes = C.dashboard(datos, {}).porMes;
  assert.deepEqual(porMes.map(m => [m.nombre, m.precioVenta]), [['Agosto', 7000], ['Septiembre', 254000 / 30]]);
});
