// El calculo del dashboard Comercial (2026-10-19). Replica las tablas
// dinamicas de "DASHBOARD COMERCIAL 2026.xlsx", hoja DASHB COMERCIAL 2026:
//
//   M3 VENDIDOS      B19   suma de CANTIDAD
//   RD$ VENDIDOS     B300  suma de LINE TOTAL
//   TOTAL CLIENTES   A291  clientes distintos (*)
//   PPVENTA RD$      C45   PROMEDIO de PRECIO, fila por fila — no ponderado por
//                          m3: septiembre da 8.341,59 y el ponderado 8.362,47
//   MES VS PPTO      B337  m3 del mes / plan del mes (DESPACHOS HORMIGON)
//   PRECIO VS PPTO   (nuevo, no esta en el Excel) RD$/m3 del mes / PRECIO
//                          DIRECTO, MES del plan
//   VENTAS VS PPTO   (nuevo) RD$ del mes / INGRESOS DIRECTO, MES del plan
//
// y los 8 graficos: m3 por mes, por zona, por vendedor, por rango FC, por
// cliente y por planta; RD$ por zona y por vendedor. Los 7 filtros son los
// segmentadores del Excel (mes, vendedor, zona, planta, rango FC, condicion y
// cliente) y, como alla, filtran TODO, cumplimiento incluido.
//
// (*) El Excel cuenta COUNTA(A57:A288) sobre la tabla de clientes, que mete
// la fila "Total general": septiembre muestra 95 y son 94. Aca se cuentan los
// clientes de verdad.
//
// Calculo puro, sin DOM ni red: se prueba con node (tests/logistica/
// comercial.test.js). `datos` es lo que devuelve GET /api/comercial/datos:
// {anio, dimensiones, valores: {dim: [texto...]}, filas: [[mes, i_dim..., cantidad, precio, line_total]], plan: {mes: m3}}.
(function (root) {
  'use strict';

  const DIMENSIONES = ['vendedor', 'planta', 'cliente', 'condicion', 'zona', 'rango_fc'];
  const COL = {mes: 0, vendedor: 1, planta: 2, cliente: 3, condicion: 4, zona: 5, rango_fc: 6,
               cantidad: 7, precio: 8, lineTotal: 9};
  const MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto',
                 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
  const SIN_VALOR = '(vacío)';

  // En "m³ por vendedor" estas vendedoras van dentro de la barra de Oficina
  // (pedido del usuario, 2026-10-21). Solo en ese grafico: en "% RD$ por
  // vendedor" y en el filtro siguen por su nombre. Se comparan sin mayusculas
  // ni espacios de mas, que el Excel trae "Nikaulis de la cruz".
  const OFICINA = 'Oficina';
  const VENDEDORAS_EN_OFICINA = ['Ana Taveras', 'Katherine Concepcion', 'Nikaulis de la Cruz'];
  const normalizarNombre = s => String(s || '').trim().replace(/\s+/g, ' ').toLowerCase();
  const VAN_A_OFICINA = new Set(VENDEDORAS_EN_OFICINA.map(normalizarNombre));

  // "m³ por tipo de vendedor" (pedido del usuario, 2026-10-21): Interno es
  // Oficina (con las vendedoras de arriba) mas Denisse Rosario; Externo, todos
  // los demas.
  const INTERNO = 'Interno', EXTERNO = 'Externo';
  const VENDEDORES_INTERNOS = [OFICINA, ...VENDEDORAS_EN_OFICINA, 'Denisse Rosario'];
  const SON_INTERNOS = new Set(VENDEDORES_INTERNOS.map(normalizarNombre));

  // En "m³ por cliente" todos los MACAO ALTO RESORT (Macao II, exteriores,
  // podium, Cavernas, CEDIS...) van en una sola barra (pedido del usuario,
  // 2026-10-21). Solo en ese grafico: el filtro y Total clientes siguen por
  // nombre.
  const MACAO = 'MACAO ALTO RESORT';
  const esMacao = n => normalizarNombre(n).includes('macao alto resort');

  // `filtros` es {mes: [1, 9], vendedor: ['Ana Taveras'], ...}; un filtro
  // vacio o ausente deja pasar todo, como un segmentador sin seleccion.
  function filtrar(datos, filtros = {}) {
    const meses = filtros.mes && filtros.mes.length ? new Set(filtros.mes.map(Number)) : null;
    const porDim = DIMENSIONES.map(d => {
      const elegidos = filtros[d];
      if (!elegidos || !elegidos.length) return null;
      const quiero = new Set(elegidos);
      return new Set(datos.valores[d].map((v, i) => quiero.has(v || SIN_VALOR) ? i : -1).filter(i => i >= 0));
    });
    return datos.filas.filter(f => (!meses || meses.has(f[COL.mes]))
      && porDim.every((s, k) => !s || s.has(f[k + 1])));
  }

  // `renombrar` junta valores bajo otro nombre (la barra de Oficina).
  function agrupar(datos, filas, dim, renombrar = n => n) {
    const por = new Map();
    for (const f of filas) {
      const nombre = renombrar(dim === 'mes' ? f[COL.mes] : (datos.valores[dim][f[COL[dim]]] || SIN_VALOR));
      let g = por.get(nombre);
      if (!g) por.set(nombre, g = {nombre, m3: 0, rd: 0, sumaPrecio: 0, nPrecio: 0});
      g.m3 += f[COL.cantidad] || 0;
      g.rd += f[COL.lineTotal] || 0;
      if (typeof f[COL.precio] === 'number') { g.sumaPrecio += f[COL.precio]; g.nPrecio++; }
    }
    return [...por.values()].map(g => ({nombre: g.nombre, m3: g.m3, rd: g.rd,
      precioPromedio: g.nPrecio ? g.sumaPrecio / g.nPrecio : null}));
  }

  // Porcentajes enteros que suman 100 (mayor resto), para que la leyenda de
  // una dona no diga 101%.
  function porcentajes(valores) {
    const total = valores.reduce((s, v) => s + v, 0);
    if (!total) return valores.map(() => 0);
    const crudos = valores.map(v => v * 100 / total);
    const base = crudos.map(Math.floor);
    let falta = 100 - base.reduce((s, v) => s + v, 0);
    crudos.map((v, i) => [v - base[i], i]).sort((a, b) => b[0] - a[0])
      .forEach(([, i]) => { if (falta > 0) { base[i]++; falta--; } });
    return base;
  }

  // Valores de `dim` juntados en barras con otro nombre (`aGrupo`). Una barra
  // que junta a otros lleva en `incluye` a quienes junta (el del mismo nombre
  // primero, despues por m3), para el detalle y para que un clic filtre por
  // todos ellos y no por un valor que no existe.
  //
  // `valores` son TODOS los nombres del ano que caen en la barra, aunque no
  // tengan filas con los filtros de ahora: es por lo que filtra el clic (#178,
  // 2026-10-23). Antes el clic filtraba por `incluye`, que sale de las filas
  // filtradas: con Septiembre elegido, Oficina filtraba por [Oficina, Ana,
  // Katherine], y al sacar el mes Nikaulis quedaba afuera y la barra no se veia
  // marcada.
  function juntar(datos, filas, dim, aGrupo) {
    const grupos = agrupar(datos, filas, dim, aGrupo);
    const propios = agrupar(datos, filas, dim);
    const delAnio = datos.valores[dim] || [];
    grupos.forEach(g => {
      const suyos = propios.filter(p => aGrupo(p.nombre) === g.nombre)
        .sort((a, b) => (b.nombre === g.nombre) - (a.nombre === g.nombre) || b.m3 - a.m3);
      if (suyos.length > 1 || suyos[0].nombre !== g.nombre)
        g.incluye = suyos.map(p => ({nombre: p.nombre, m3: p.m3}));
      const todos = delAnio.filter(n => aGrupo(n || SIN_VALOR) === g.nombre);
      if (todos.length > 1 || (todos.length === 1 && todos[0] !== g.nombre)) g.valores = todos;
    });
    return grupos;
  }

  // m3 por vendedor, con las vendedoras de oficina dentro de Oficina.
  const m3PorVendedor = (datos, filas) => juntar(datos, filas, 'vendedor',
    n => VAN_A_OFICINA.has(normalizarNombre(n)) ? OFICINA : n);

  const m3PorTipoVendedor = (datos, filas) => juntar(datos, filas, 'vendedor',
    n => SON_INTERNOS.has(normalizarNombre(n)) ? INTERNO : EXTERNO);

  const porValor = campo => (a, b) => b[campo] - a[campo] || String(a.nombre).localeCompare(String(b.nombre));

  // Los meses del cumplimiento: los elegidos en el filtro o, sin filtro,
  // todos los meses con despachos contra su plan (pedido del usuario,
  // 2026-10-22: sin filtro tomaba solo el ultimo mes, como el "MES/SEPTIEMBRE
  // VS PPTO" del Excel, y tiene que ser el acumulado).
  function mesesDelCumplimiento(datos, filtros = {}) {
    if (filtros.mes && filtros.mes.length) return [...new Set(filtros.mes.map(Number))].sort((a, b) => a - b);
    return [...new Set(datos.filas.map(f => f[COL.mes]))].sort((a, b) => a - b);
  }

  function dashboard(datos, filtros = {}) {
    const filas = filtrar(datos, filtros);
    const total = agrupar(datos, filas.map(f => [0, ...f.slice(1)]), 'mes')[0]
      || {m3: 0, rd: 0, precioPromedio: null};
    const clientes = new Set(filas.map(f => f[COL.cliente])).size;

    const meses = mesesDelCumplimiento(datos, filtros);
    const m3Meses = filas.filter(f => meses.includes(f[COL.mes])).reduce((s, f) => s + (f[COL.cantidad] || 0), 0);
    const planMeses = meses.every(m => typeof datos.plan[m] === 'number')
      ? meses.reduce((s, m) => s + datos.plan[m], 0) : null;
    // `acumulado`: sin filtro de mes, para que la pantalla lo diga.
    const acumulado = !(filtros.mes && filtros.mes.length);
    const cumplimiento = {meses, acumulado, m3: m3Meses, plan: planMeses,
      pct: planMeses ? m3Meses / planMeses * 100 : null};

    // Precio real vs presupuestado (2026-10-21). Los dos son RD$ / m3: el
    // real, RD$ vendidos / m3 vendidos; el presupuestado, como lo calcula el
    // plan (ingresos / m3), asi que con varios meses es el de cada mes pesado
    // por sus m3 de plan.
    // Solo en los meses que tienen precio de plan (#180, 2026-10-23): Ene-Jun
    // van contra el plan original, que no trae precio, y el precio del rolling
    // en esos meses es el real. Sin filtro, "Ene-Sep vs ppto" y "Jul-Sep
    // precio vs ppto": cada tarjeta dice sus meses.
    const planPrecio = datos.planPrecio || {};
    const mesesPrecio = meses.filter(m => typeof planPrecio[m] === 'number' && typeof datos.plan[m] === 'number');
    const filasPrecio = filas.filter(f => mesesPrecio.includes(f[COL.mes]));
    const m3MesesPrecio = filasPrecio.reduce((s, f) => s + (f[COL.cantidad] || 0), 0);
    const rdMeses = filasPrecio.reduce((s, f) => s + (f[COL.lineTotal] || 0), 0);
    const conPrecio = mesesPrecio.length > 0;
    const m3Plan = conPrecio ? mesesPrecio.reduce((s, m) => s + datos.plan[m], 0) : 0;
    const precioPpto = conPrecio && m3Plan ? mesesPrecio.reduce((s, m) => s + planPrecio[m] * datos.plan[m], 0) / m3Plan : null;
    const precioReal = conPrecio && m3MesesPrecio ? rdMeses / m3MesesPrecio : null;
    const precioVsPpto = {meses: mesesPrecio, real: precioReal, plan: precioPpto,
      pct: precioReal !== null && precioPpto ? precioReal / precioPpto * 100 : null};

    // Ventas RD$ vs ppto (2026-10-21): RD$ vendidos de esos meses contra los
    // INGRESOS DIRECTO, MES del plan, que el plan arma como PRECIO DIRECTO x
    // DESPACHOS HORMIGON — por eso salen de lo que ya esta guardado. "Directo"
    // es solo hormigon, que es lo unico que traen los despachos.
    const rdPlan = conPrecio ? mesesPrecio.reduce((s, m) => s + planPrecio[m] * datos.plan[m], 0) : null;
    const ventasVsPpto = {meses: mesesPrecio, real: rdMeses, plan: rdPlan, pct: rdPlan ? rdMeses / rdPlan * 100 : null};

    const porMes = agrupar(datos, filas, 'mes').sort((a, b) => a.nombre - b.nombre)
      .map(g => ({...g, mes: g.nombre, nombre: MESES[g.nombre - 1],
                  plan: typeof datos.plan[g.nombre] === 'number' ? datos.plan[g.nombre] : null,
                  // El precio de venta del mes, RD$ / m3 (2026-10-21): la linea
                  // de precio sobre las barras, la misma cuenta que precio vs ppto.
                  precioVenta: g.m3 ? g.rd / g.m3 : null}));
    const conPct = (lista, campo) => {
      const pcts = porcentajes(lista.map(g => g[campo]));
      return lista.map((g, i) => ({...g, pct: pcts[i]}));
    };
    return {
      filas: filas.length,
      m3: total.m3, rd: total.rd, precioPromedio: total.precioPromedio, clientes, cumplimiento, precioVsPpto, ventasVsPpto,
      porMes,
      porZona: conPct(agrupar(datos, filas, 'zona').sort(porValor('m3')), 'm3'),
      porVendedor: m3PorVendedor(datos, filas).sort(porValor('m3')),
      porTipoVendedor: conPct(m3PorTipoVendedor(datos, filas)
        .sort((a, b) => (a.nombre === EXTERNO) - (b.nombre === EXTERNO)), 'm3'),
      porRango: conPct(agrupar(datos, filas, 'rango_fc').sort(porValor('m3')), 'm3'),
      porCliente: juntar(datos, filas, 'cliente', n => esMacao(n) ? MACAO : n).sort(porValor('m3')),
      rdPorZona: agrupar(datos, filas, 'zona').sort(porValor('rd')),
      porPlanta: agrupar(datos, filas, 'planta').sort(porValor('m3')),
      rdPorVendedor: conPct(agrupar(datos, filas, 'vendedor').sort(porValor('rd')), 'rd'),
    };
  }

  // Las opciones de cada filtro: todos los valores del ano, ordenados.
  function opcionesDeFiltro(datos) {
    const opciones = {mes: [...new Set(datos.filas.map(f => f[COL.mes]))].sort((a, b) => a - b)};
    DIMENSIONES.forEach(d => {
      opciones[d] = [...new Set(datos.valores[d].map(v => v || SIN_VALOR))].sort((a, b) => a.localeCompare(b));
    });
    return opciones;
  }

  // Una dona con mas de `max` porciones junta el resto en "Otros": mas de
  // ocho colores ya no se distinguen.
  function plegar(lista, campo, max = 8) {
    if (lista.length <= max) return lista;
    const resto = lista.slice(max - 1);
    const otros = {nombre: `Otros (${resto.length})`, otros: true, m3: 0, rd: 0};
    resto.forEach(g => { otros.m3 += g.m3; otros.rd += g.rd; });
    const plegada = [...lista.slice(0, max - 1), otros];
    const pcts = porcentajes(plegada.map(g => g[campo]));
    return plegada.map((g, i) => ({...g, pct: pcts[i]}));
  }

  const api = {dashboard, filtrar, opcionesDeFiltro, porcentajes, plegar, mesesDelCumplimiento,
               MESES_COMERCIAL: MESES, SIN_VALOR, VENDEDORAS_EN_OFICINA, VENDEDORES_INTERNOS};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else Object.assign(root, api);
})(typeof window !== 'undefined' ? window : globalThis);
