// Logica del dashboard de cumplimiento de despacho — la parte que se puede
// probar sin un navegador.
//
// Por que existe este archivo: hasta el 2026-09-30 todo vivia adentro de
// `static/logistica.html` y no habia una sola prueba que lo cubriera, en un
// proyecto con 777. Los cuatro defectos de logica del 2026-09-29 —uno de
// ellos daba "Cumplido" automatico a un pedido sin hora programada— se
// encontraron leyendo el codigo, no corriendo nada, y no quedo nada que
// impida que vuelvan.
//
// Lo que se movio aca es SOLO lo que no toca el DOM: normalizacion, lectura
// de horas y fechas de Excel, deteccion de encabezados, el cruce
// programacion-vs-cargue y el resumen por cliente. El render, los listeners y
// la lectura del archivo siguen en el HTML.
//
// Dos cambios de forma, ninguno de comportamiento:
//
//   - `computeCumplimiento(state, assumptions)` y `computeResumen(state)`
//     reciben por parametro lo que antes tomaban del closure. Es lo que los
//     vuelve probables sin montar la pagina entera.
//   - Los parsers se partieron en dos: `parse*Sheets(hojas)` es la heuristica
//     —que es lo fragil y lo que hay que probar— y el HTML conserva un
//     envoltorio de tres lineas que usa XLSX para convertir cada hoja en
//     filas. Asi los tests no necesitan la libreria del CDN.
//
// El navegador lo carga con un <script src> normal y sigue viendo las
// funciones como globales; node lo importa con require(). El mismo archivo
// sirve para los dos.

(function (root) {
  'use strict';

  // El viejo piso de adelanto. Desde el 2026-10-09 NO cambia el estado (llegar
  // antes siempre cumple, ver computeCumplimiento); el valor sigue viajando en
  // el dia guardado solo para no cambiar el formato de la base.
  const ADELANTO_POR_DEFECTO = 60;

  // Espaciamiento maximo entre camiones de una misma obra, en minutos
  // (2026-10-06, de la version de la companera). Mismo patron que el adelanto:
  // un dia guardado sin el supuesto cae a este default.
  const ESPACIAMIENTO_POR_DEFECTO = 30;

  // Quien es responsable de un incumplimiento o de un pedido no despachado.
  // Valores fijos de la version de la companera; el backend valida los mismos.
  const RESPONSABLES = ['VMO', 'Cliente', 'Externo'];

  // Por que se incumplio o no se despacho (2026-10-06, lista que paso el
  // usuario; los 7 ultimos se agregaron el 2026-10-08, de la version 13 de la
  // companera, y los 4 de MISMO HORARIO a INICIO DE CARGA el 2026-10-09). El
  // backend valida contra la misma lista: tests/test_logistica_historial.py
  // compara las dos para que no se desincronicen.
  //
  // CLIENTE PIDIO ANTES se agrego el 2026-10-09 y se saco el 2026-10-12: desde
  // que llegar antes cuenta como cumplido, no hay incumplido al que le quepa.
  // Los dos dias que lo tenian se corrigieron en la base (VIGAFILI del 02-10
  // paso a MISMO HORARIO ELEMENTOS; el de Macao del 01-10 se borro).
  const MOTIVOS = ['PROBLEMAS CLIMATICOS', 'RETRASOS EN OBRA', 'SIN COLOCACION', 'ELEMENTO NO LISTO',
    'INCONVENIENTES EN OBRA', 'AVERIA DE BOMBA', 'AVERIA DE PLANTA', 'DISPONIBILIDAD DE CAMIONES',
    'TARDANZA DE BOMBA', 'REVISION CALIDAD', 'RETRASO EN LA SALIDA DE PLANTA',
    'LLEGADA TARDE PERSONAL', 'ACCIDENTE', 'DIFICIL ACCESO EN OBRA',
    'OBSTRUCCION ESTACIONAMIENTO DE LA BOMBA', 'DISPONIBILIDAD DE MANGUERAS', 'PRIORIDAD OTRO ELEMENTO',
    'PERMISOS DE OBRA',
    'MISMO HORARIO ELEMENTOS', 'PASE DE INGRESO A OBRA', 'DESPACHO VMO', 'INICIO DE CARGA VMO',
    'HORARIO PROGRAMADO',
    // 2026-10-12, pedido del usuario
    'CAMBIO DE PEDIDO',
    // 2026-10-21, pedido del usuario
    'SIN SISTEMA', 'OPERACIONES',
    // 2026-10-23, pedido del usuario
    'PRIORIDAD OTRO SERVICIO'];

  // Punta Cana se parte en "Proyecto (Macao)" y "Clientes generales": va al
  // proyecto todo lo que tenga MACAO en el cliente o en la obra.
  const PALABRA_MACAO = 'MACAO';

  // ================= HELPERS =================

function normalize(s){
  if (s===null || s===undefined) return '';
  s = String(s).toUpperCase();
  s = s.replace(/[^A-Z0-9 ]/g,' ');
  s = s.replace(/\s+/g,' ').trim();
  return s;
}
function excelTimeToMinutes(cell){
  if (cell===null || cell===undefined || cell==='') return null;
  if (cell instanceof Date) return cell.getUTCHours()*60 + cell.getUTCMinutes() + cell.getUTCSeconds()/60;
  if (typeof cell === 'number'){
    const frac = cell - Math.floor(cell);
    return Math.round(frac*24*60);
  }
  if (typeof cell === 'string'){
    const m = cell.trim().match(/(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AaPp][Mm])?/);
    if (m){
      let h = parseInt(m[1],10), min = parseInt(m[2],10);
      const ampm = m[4];
      if (ampm){
        const isPM = /p/i.test(ampm);
        if (h===12) h = isPM ? 12 : 0; else if (isPM) h += 12;
      }
      return h*60+min;
    }
  }
  return null;
}
function excelSerialToFechaStr(serial){
  // Convierte un serial numerico de Excel a AAAA-MM-DD usando solo aritmetica UTC (sin Date local del navegador)
  // Un serial < 1 es una hora pura sin parte de fecha: no hay fecha que deducir
  if (typeof serial !== 'number' || serial < 1) return null;
  const days = Math.floor(serial);
  const ms = Date.UTC(1899, 11, 30) + days*86400000;
  const d = new Date(ms);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,'0')}-${String(d.getUTCDate()).padStart(2,'0')}`;
}
function minToStr(min){
  if (min===null || min===undefined || isNaN(min)) return '—';
  min = ((Math.round(min)%1440)+1440)%1440;
  const h = Math.floor(min/60), m = min%60;
  return String(h).padStart(2,'0')+':'+String(m).padStart(2,'0');
}
function fmtDiff(min){
  if (min===null||min===undefined||isNaN(min)) return '—';
  const sign = min < 0 ? '\u2212' : '+';
  const abs = Math.round(Math.abs(min));
  const h = Math.floor(abs/60), m = abs%60;
  return sign + (h>0 ? `${h}h ${m}min` : `${m}min`);
}
function fmtInt(n){ return (n||0).toLocaleString('es-DO'); }

  // ================= ENCABEZADOS Y COLUMNAS =================

function findHeaderRowIndex(rows, mustHave){
  for (let i=0; i<Math.min(rows.length,10); i++){
    const rowText = (rows[i]||[]).map(c=>normalize(c)).join(' | ');
    if (mustHave.every(k => rowText.includes(normalize(k)))) return i;
  }
  return -1;
}
function colIndex(headerRow, candidates){
  // 1. Coincidencia EXACTA primero, en el orden de los candidatos (evita que una columna como
  //    "Hora de cargue teorico" se confunda con "Hora Inicio" solo por contener la palabra "Hora")
  for (const c of candidates){
    const idx = headerRow.findIndex(h => normalize(h)===normalize(c));
    if (idx>=0) return idx;
  }
  // 2. Si no hay ninguna coincidencia exacta, recien ahi se acepta coincidencia parcial
  for (const c of candidates){
    const idx = headerRow.findIndex(h => normalize(h).includes(normalize(c)));
    if (idx>=0) return idx;
  }
  return -1;
}

  // ================= PARSERS (la heuristica, sin XLSX) =================

// La "Hora Inicio" de la programacion siempre va una hora atras de la real:
// se le suma al leerla. Regla de la companera ("ajuste indicado por Melissa"),
// adoptada el 2026-10-06 para todo lo que se cargue desde entonces. Los dias
// guardados antes se borraron y se recargaron con esta regla, asi que en la
// base no conviven horas con y sin ajuste.
const AJUSTE_HORA_PROGRAMADA_MIN = 60;

// Bomba: el numero o nombre de bomba tal cual; vacio, 0, NO, N/A, SIN BOMBA,
// NINGUNA o DIRECTO es un pedido "Directo".
function normalizarBomba(v){
  if (v===null || v===undefined) return 'Directo';
  const txt = String(v).trim();
  const n = normalize(txt);
  if (['','0','NO','N A','NA','N/A','SIN BOMBA','NINGUNA','NINGUNO','DIRECTO'].includes(n)) return 'Directo';
  return txt;
}

// La columna de bomba se busca por nombre. Si no hay encabezado "Bomba", se
// toma la columna E —donde esta en la planilla real— pero SOLO si esa columna
// no tiene otro nombre: con un encabezado distinto (ej. "Cantidad") la regla
// de la companera habria leido la cantidad como si fuera la bomba.
function colBomba(header){
  const i = colIndex(header, ['Bomba']);
  if (i>=0) return i;
  const e = header.length>4 ? header[4] : undefined;
  return (e===null || e===undefined || String(e).trim()==='') && header.length>4 ? 4 : -1;
}

// Solo cuentan los hormigones y los morteros (regla del usuario, 2026-10-08).
// La programacion trae otros renglones —pavimentacion, servicios— que no son
// despachos de planta: con la hora vacia o en 00:00 quedaban programados a la
// 01:00 (por el +1 hora) y salian como incumplidos o sin despachar. Se compara
// sin tildes porque el Excel trae HORMIGON y HORMIGÓN mezclados. Un renglon
// sin producto se deja pasar: no se puede saber que es.
function esProductoQueCuenta(producto){
  if (producto===null || producto===undefined || String(producto).trim()==='') return true;
  const p = String(producto).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase();
  return /HORMIG.?N|MORTERO/.test(p);
}

// VMO CONCRETOS como cliente es uso interno —desperdicio por falla de equipo,
// lechada—, no una entrega: no cuenta ni en la programacion ni en el cargue
// (decision del usuario, 2026-10-08). Venia sin hora, quedaba a la 01:00 y
// salia incumplido por doce horas.
function esClienteInterno(cliente){
  return normalize(cliente).startsWith('VMO CONCRETOS');
}

// MACAO —en el cliente o en la obra— tampoco entra (decision del usuario,
// 2026-10-09): es un cliente muy grande al que se le despacha cuando ellos
// quieren; siempre salia incumplido y bajaba el cumplimiento sin decir nada
// util. Desaparece de todo, igual que VMO CONCRETOS, tambien de los dias ya
// guardados (ver restaurarDia).
function esMacao(cliente, obra){
  return [cliente, obra].some(t => normalize(t).includes(PALABRA_MACAO));
}

function quedaFuera(fila){
  return esClienteInterno(fila.cliente) || esMacao(fila.cliente, fila.obra);
}

// Los conteos de un dia como los ve el resto de la app: sobre el estado de
// restaurarDia(), que ya saco Macao y los clientes internos. El indice del
// servidor cuenta lo guardado tal cual, y el 02/10, guardado antes de la regla
// de Macao, salia en el Historial con 1.186 m3 contra 1.060 en las demas
// pantallas (#171, 2026-10-23).
function conteosDelDia(state){
  const cargue = state.cargue || [];
  return {pedidos: (state.programacion || []).length, cargues: cargue.length,
          m3: cargue.reduce((t, c) => t + (c.cantidad || 0), 0),
          clientes: new Set(cargue.map(c => c.cliente)).size,
          camiones: new Set(cargue.map(c => c.ficha)).size};
}

function leerProgramacionSheets(hojas){
  let out = [];
  hojas.forEach(({nombre: sheetName, rows})=>{
    const hIdx = findHeaderRowIndex(rows, ['CLIENTE']);
    if (hIdx===-1) return;
    const header = rows[hIdx];
    const iCliente = colIndex(header, ['Cliente']);
    const iObra = colIndex(header, ['Obra']);
    const iHora = colIndex(header, ['Hora Inicio','Hora']);
    const iPedido = colIndex(header, ['Pedido']);
    const iCant = colIndex(header, ['Cantidad','Cant']);
    const iElemento = colIndex(header, ['Elemento']);
    const iProducto = colIndex(header, ['Producto']);
    const iPrioridad = colIndex(header, ['Prioridad']);
    // Despachado y Pendiente: el propio archivo dice cuanto de cada renglon
    // salio y cuanto quedo. Se leen desde el 2026-09-30 y valen mucho:
    // `despachado` es lo que permite repartir los camiones entre las horas de
    // una misma obra, y `pendiente` dice que quedo sin despachar sin tener que
    // deducirlo del cruce. Pueden no estar —un archivo viejo, otra planilla— y
    // en ese caso quedan en null y el calculo sigue con lo que hay.
    const iDespachado = colIndex(header, ['Despachado']);
    const iPendiente = colIndex(header, ['Pendiente']);
    const iBomba = colBomba(header);
    const iVendedor = colIndex(header, ['Vendedor']);
    const iZona = colIndex(header, ['Zona']);

    let zona = null;
    const sn = normalize(sheetName);
    if (sn.includes('PUNTA')) zona='Punta Cana';
    else if (sn.includes('SANTO') || sn.includes('SD')) zona='Santo Domingo';

    for (let r=hIdx+1; r<rows.length; r++){
      const row = rows[r];
      if (!row) continue;
      const cliente = iCliente>=0 ? row[iCliente] : null;
      if (!cliente) continue;
      if (esClienteInterno(cliente)) continue;
      if (iProducto>=0 && !esProductoQueCuenta(row[iProducto])) continue;
      const horaLeida = iHora>=0 ? excelTimeToMinutes(row[iHora]) : null;
      const horaMin = horaLeida===null ? null : horaLeida + AJUSTE_HORA_PROGRAMADA_MIN;
      const cantidad = iCant>=0 ? parseFloat(row[iCant]) : null;
      const textoONull = (i) => {
        if (i < 0 || row[i]===null || row[i]===undefined) return null;
        const t = String(row[i]).trim();
        return t==='' ? null : t;
      };
      const numeroONull = (i) => {
        if (i < 0) return null;
        const v = parseFloat(row[i]);
        return isNaN(v) ? null : v;
      };
      out.push({
        cliente: String(cliente).trim(),
        obra: iObra>=0 ? String(row[iObra]||'').trim() : '',
        horaMin: horaMin,
        pedido: iPedido>=0 ? row[iPedido] : null,
        cantidad: isNaN(cantidad) ? 0 : (cantidad||0),
        elemento: iElemento>=0 ? row[iElemento] : null,
        producto: iProducto>=0 ? row[iProducto] : null,
        prioridad: iPrioridad>=0 ? row[iPrioridad] : null,
        despachado: numeroONull(iDespachado),
        pendiente: numeroONull(iPendiente),
        bomba: iBomba>=0 ? normalizarBomba(row[iBomba]) : 'Directo',
        vendedor: textoONull(iVendedor),
        // la zona de la planilla, si la trae; si no, la de la hoja
        zonaProg: textoONull(iZona) || zona,
        zonaSheet: zona,
      });
    }
  });
  return out;
}

function parseProgramacionSheets(hojas){
  return leerProgramacionSheets(hojas).filter(f => !esMacao(f.cliente, f.obra));
}

// Los renglones de Macao, que el dia guarda aparte para el Reporte de
// cancelados (2026-11-03). El cumplimiento no los ve: restaurarDia los separa.
function parseProgramacionMacao(hojas){
  return leerProgramacionSheets(hojas).filter(f => !esClienteInterno(f.cliente) && esMacao(f.cliente, f.obra));
}

function parseCargueSheets(hojas){
  let out = [];
  let fechaDetectada = null;
  hojas.forEach(({nombre: sheetName, rows})=>{
    const hIdx = findHeaderRowIndex(rows, ['FICHA']);
    if (hIdx===-1) return;
    const header = rows[hIdx];
    const iFicha = colIndex(header, ['Ficha']);
    const iHora = colIndex(header, ['Hora']);
    const iTiempo = colIndex(header, ['Tiempo']);
    const iCliente = colIndex(header, ['Cliente']);
    const iConduce = colIndex(header, ['Conduce']);
    const iElemento = colIndex(header, ['Elemento']);
    const iPlanta = colIndex(header, ['Planta']);
    const iDireccion = colIndex(header, ['Direccion','Dirección']);
    const iCant = colIndex(header, ['Cantidad','Cant']);

    for (let r=hIdx+1; r<rows.length; r++){
      const row = rows[r];
      if (!row) continue;
      const ficha = iFicha>=0 ? row[iFicha] : null;
      if (!ficha) continue;
      if (normalize(ficha)==='CARGA VACIA') continue;
      const cliente = iCliente>=0 ? row[iCliente] : null;
      if (!cliente) continue;
      if (esClienteInterno(cliente)) continue;
      let obra = iDireccion>=0 ? String(row[iDireccion]||'') : '';
      obra = obra.replace(/^OBRA:\s*/i,'').trim();
      const horaCell = iHora>=0 ? row[iHora] : null;
      if (!fechaDetectada){
        if (typeof horaCell === 'number'){
          fechaDetectada = excelSerialToFechaStr(horaCell);
        } else if (horaCell instanceof Date){
          fechaDetectada = `${horaCell.getUTCFullYear()}-${String(horaCell.getUTCMonth()+1).padStart(2,'0')}-${String(horaCell.getUTCDate()).padStart(2,'0')}`;
        }
      }
      const horaMin = excelTimeToMinutes(horaCell);
      const cantidad = iCant>=0 ? parseFloat(row[iCant]) : null;
      out.push({
        ficha: String(ficha).trim(),
        horaMin: horaMin,
        cliente: String(cliente).trim(),
        conduce: iConduce>=0 ? row[iConduce] : null,
        elemento: iElemento>=0 ? row[iElemento] : null,
        planta: iPlanta>=0 ? String(row[iPlanta]||'').trim() : '',
        obra: obra,
        cantidad: isNaN(cantidad) ? 0 : (cantidad||0),
      });
    }
  });
  // Macao sigue fuera del cumplimiento, pero desde el 2026-10-28 sus viajes se
  // guardan aparte (`macao`) para el indicador de camiones, que lo incluye.
  return {rows: out.filter(f => !esMacao(f.cliente, f.obra)),
          macao: out.filter(f => esMacao(f.cliente, f.obra)), fecha: fechaDetectada};
}

  // ================= CRUCE Y CUMPLIMIENTO =================

function obraScore(a,b){
  const wa = new Set(normalize(a).split(' ').filter(w=>w.length>=3));
  const wb = new Set(normalize(b).split(' ').filter(w=>w.length>=3));
  if (wa.size===0 || wb.size===0) return 0;
  let inter=0;
  wa.forEach(w=>{ if (wb.has(w)) inter++; });
  return inter/Math.max(wa.size,wb.size);
}

function groupBy(arr, keyFn){
  const m = new Map();
  arr.forEach(item=>{
    const k = keyFn(item);
    if (!m.has(k)) m.set(k, []);
    m.get(k).push(item);
  });
  return m;
}

  // ================= PEDIDOS POR HORA =================
  //
  // Un renglon de la programacion es un pedido con su hora. Varios renglones a
  // la MISMA hora para la misma obra son el mismo pedido: cambian el producto o
  // el elemento, no el compromiso de entrega.

  // Lo que quedo sin despachar, tomado de la columna `Pendiente` de la propia
  // programacion (2026-09-30). Es un dato EXACTO del archivo, no una deduccion
  // del cruce: antes "no despachado" significaba "no le encontre cargue", que
  // mezclaba una entrega que no salio con un cruce que fallo.
  //
  // De rebote arregla un falso positivo real: un renglon programado en 0 m3
  // tiene pendiente 0 y deja de figurar como incumplido. El 29-09, CORALES DEL
  // CARIBE aparecia como no despachado y estaba programado en cero.
  //
  // Si el archivo no trae la columna, devuelve lista vacia y la pantalla se
  // apoya en lo de siempre.
  function noDespachado(programacion){
    const por = new Map();
    (programacion || []).forEach(f => {
      if (f.pendiente === null || f.pendiente === undefined || !(f.pendiente > 0)) return;
      const k = claveFila(f.cliente, f.obra, f.bomba, f.elemento, f.horaMin);
      if (!por.has(k)) por.set(k, {cliente: f.cliente, obra: f.obra, hora: f.horaMin,
                                   bomba: f.bomba || 'Directo', elemento: f.elemento ?? null,
                                   vendedor: f.vendedor ?? null, zonaProg: f.zonaProg ?? null,
                                   producto: f.producto ?? null,
                                   rowKey: k, programado: 0, despachado: 0, pendiente: 0});
      const p = por.get(k);
      p.programado += f.cantidad || 0;
      p.despachado += f.despachado || 0;
      p.pendiente += f.pendiente;
    });
    return [...por.values()].sort((a, b) => (a.hora ?? 9999) - (b.hora ?? 9999));
  }

  function pedidosPorHora(filas){
    const por = new Map();
    filas.forEach(f => {
      const k = f.horaMin === null ? 'sinhora' : String(f.horaMin);
      if (!por.has(k)) por.set(k, {hora: f.horaMin, cantidad: 0, despachado: 0, pendiente: 0,
                                   tieneDespachado: false, tienePendiente: false});
      const p = por.get(k);
      p.cantidad += f.cantidad || 0;
      if (f.despachado !== null && f.despachado !== undefined){ p.despachado += f.despachado; p.tieneDespachado = true; }
      if (f.pendiente !== null && f.pendiente !== undefined){ p.pendiente += f.pendiente; p.tienePendiente = true; }
    });
    return [...por.values()]
      .map(p => ({...p,
                  despachado: p.tieneDespachado ? p.despachado : null,
                  pendiente: p.tienePendiente ? p.pendiente : null}))
      // Las que no tienen hora van al final: no compiten por los camiones de
      // las que si la tienen.
      .sort((a, b) => (a.hora === null) - (b.hora === null) || a.hora - b.hora);
  }

  // Reparte los camiones de una obra entre sus horas, en orden cronologico:
  // los primeros m3 que salieron son los del primer compromiso.
  //
  // La cuota de cada hora es su `despachado`, que el propio archivo trae. Si esa
  // columna no esta —otra planilla, un archivo viejo— se usa la cantidad
  // programada, que es la mejor aproximacion disponible. El ultimo pedido se
  // queda con lo que sobre, para que ningun camion se pierda.
  const HOLGURA_CUOTA_M3 = 1;
  function repartirCamiones(horas, camionesOrdenados){
    const salida = horas.map(p => ({pedido: p, camiones: []}));
    if (!salida.length) return salida;
    let i = 0;
    salida.forEach((slot, n) => {
      const ultimo = n === salida.length - 1;
      if (ultimo){ slot.camiones = camionesOrdenados.slice(i); i = camionesOrdenados.length; return; }
      const cuota = slot.pedido.despachado !== null ? slot.pedido.despachado : slot.pedido.cantidad;
      if (!(cuota > 0)) return;   // nada despachado en esa hora: no se le da ningun camion
      let acum = 0;
      // La cuota se da por cubierta si falta menos de HOLGURA_CUOTA_M3 (#165,
      // 2026-10-23). Antes habia que llegar o pasarla: el 01/10, FELIX GUERRA
      // 11:00 (cuota 16,5) con camiones de 7 y 9 = 16 tomaba tambien el de 6 m3
      // de las 13:18, y el pedido de las 14:00 (6 m3, despachado completo)
      // quedaba "Sin despachar". Se probo antes "el camion que deje el total mas
      // cerca de la cuota" y rompia el 13/10 de ALBA SANCHEZ: un camion de 6 m3
      // a las 00:00 dejaba el de 8 m3 de las 13:38 para el pedido de las 15:00.
      // El primer camion se toma siempre: una cuota de 1 m3 o menos tambien recibe.
      while (i < camionesOrdenados.length && (acum === 0 || acum < cuota - HOLGURA_CUOTA_M3)){
        slot.camiones.push(camionesOrdenados[i]);
        acum += camionesOrdenados[i].cantidad;
        i++;
      }
    });
    return salida;
  }

  // ================= BOMBA Y ELEMENTO (2026-10-06) =================
  //
  // La fila del cumplimiento es cliente + obra + bomba + elemento, y si ese
  // mismo grupo tiene pedidos a varias horas, una fila por hora. Decision del
  // usuario, tomada de la version de la companera, que agrupaba por elemento.
  // La hora se conserva porque sin ella el 8% de los grupos (9 de 107 en los
  // tres primeros dias) juntaba pedidos de horas distintas —THE SEE / MURO
  // 08:00 y 19:00— y el de la tarde dejaba de evaluarse.

  function claveFila(cliente, obra, bomba, elemento, hora){
    return [normalize(cliente), normalize(obra), normalize(bomba || 'Directo'),
            normalize(elemento), hora === null || hora === undefined ? 'sinhora' : hora].join('||');
  }

  function gruposBombaElemento(filas){
    const por = new Map();
    filas.forEach(f => {
      const bomba = f.bomba || 'Directo';
      const elemento = f.elemento === null || f.elemento === undefined ? '' : String(f.elemento).trim();
      const k = normalize(bomba) + '||' + normalize(elemento);
      if (!por.has(k)) por.set(k, {bomba, elemento, filas: []});
      por.get(k).filas.push(f);
    });
    return [...por.values()];
  }

  // A que elemento de la obra va un camion. Exacto primero. Si no hay exacto,
  // se acepta que uno sea el comienzo del otro —el cargue trae textos cortados
  // como "MURO DE CONTENCI"—, pero SOLO con un unico candidato: "COLUMNA" es el
  // comienzo de "COLUMNA M1", y aceptar varios mandaria un camion de COLUMNA
  // M1 a los dos.
  function elementoDestino(elementosObra, elementoCargue){
    const c = normalize(elementoCargue);
    if (!c) return null;
    if (elementosObra.includes(c)) return c;
    const pref = elementosObra.filter(e => e && (e.startsWith(c) || c.startsWith(e)));
    return pref.length === 1 ? pref[0] : null;
  }

  // Reparte los camiones de una obra entre sus grupos de bomba + elemento, y
  // dentro de cada elemento entre sus horas (repartirCamiones, como antes).
  //
  // Con un solo elemento en la obra no se mira el elemento del camion: todos
  // van a ese grupo, que es exactamente el comportamiento anterior. Los
  // grupos con el MISMO elemento y distinta bomba comparten los camiones de
  // ese elemento, en orden de hora: el camion no dice de que bomba es.
  //
  // Un camion cuyo elemento no coincide con ninguno no se pierde: va al primer
  // elemento que no recibio ningun camion propio, o si todos recibieron, al
  // que tiene la ultima hora — la misma regla de "el ultimo se queda con lo
  // que sobre" de repartirCamiones. `sinElemento` los cuenta.
  function repartirPorGrupo(filas, camionesOrdenados){
    const grupos = gruposBombaElemento(filas);
    const familias = new Map();   // elemento normalizado -> {slots, camiones}
    grupos.forEach(g => {
      const k = normalize(g.elemento);
      if (!familias.has(k)) familias.set(k, {slots: [], camiones: []});
      pedidosPorHora(g.filas).forEach(ph => familias.get(k).slots.push({grupo: g, pedido: ph}));
    });
    const elementos = [...familias.keys()];
    const comodin = [];
    camionesOrdenados.forEach(c => {
      if (elementos.length === 1){ familias.get(elementos[0]).camiones.push(c); return; }
      const destino = elementoDestino(elementos, c.elemento);
      if (destino === null) comodin.push(c); else familias.get(destino).camiones.push(c);
    });
    if (comodin.length){
      const orden = [...familias.values()];
      const ultimaHora = f => Math.max(...f.slots.map(s => s.pedido.hora ?? -1));
      const vacia = orden.filter(f => !f.camiones.length)
                         .sort((a, b) => (a.slots[0].pedido.hora ?? 9999) - (b.slots[0].pedido.hora ?? 9999))[0];
      const destino = vacia || orden.sort((a, b) => ultimaHora(b) - ultimaHora(a))[0];
      destino.camiones = destino.camiones.concat(comodin).sort((a, b) => a.horaMin - b.horaMin);
    }
    const salida = [];
    familias.forEach(f => {
      const slots = f.slots.sort((a, b) =>
        (a.pedido.hora === null) - (b.pedido.hora === null) || a.pedido.hora - b.pedido.hora);
      repartirCamiones(slots.map(s => s.pedido), f.camiones)
        .forEach((r, i) => salida.push({grupo: slots[i].grupo, pedido: r.pedido, camiones: r.camiones}));
    });
    return {salida, sinElemento: comodin.length};
  }

  // Una fila que el usuario paso a cumplida a mano y que tiene motivo.
  function esCumplidoManual(state, rowKey){
    return !!(state.cumplidosManuales && state.cumplidosManuales.has(rowKey)
              && MOTIVOS.includes((state.motivos || new Map()).get(rowKey)));
  }
  // Lo que se lee en la columna Estado: el calculo, o "Cumplido (manual)".
  const estadoVisible = r => r.manual ? 'Cumplido (manual)' : r.estado;

function esProgramadoEnCero(p){
  return p.cantidad !== null && p.cantidad !== undefined && p.cantidad !== '' && Number(p.cantidad) === 0;
}

function computeCumplimiento(state, assumptions){
  if (!state.programacion || !state.cargue) return null;

  // Un renglon programado en 0 m3 es un pedido que quedo en cero: no recibe
  // camiones ni se evalua. El 2026-10-14 ALBA SANCHEZ tenia una LOSA de las
  // 14:00 en 0 m3 y de noche hizo CALLE sin programar; como era el unico
  // renglon de la obra, repartirPorGrupo() le pego los 7 camiones y salio
  // incumplido por +5h32. Sin el, esos camiones quedan "Sin programacion".
  // Un null (cantidad desconocida) si se cruza: solo se saca el cero explicito.
  const programacion = state.programacion.filter(p => !esProgramadoEnCero(p));

  const progGroups = groupBy(programacion, p => normalize(p.cliente)+'||'+normalize(p.obra));
  const cargueGroups = groupBy(state.cargue, c => normalize(c.cliente)+'||'+normalize(c.obra));
  const cargueByCliente = groupBy(state.cargue, c => normalize(c.cliente));

  // cuantas obras DISTINTAS tiene cada cliente en la programacion (para poder cruzar
  // sin ambiguedad cuando el texto de la obra no coincide en nada, pero cliente y cantidad
  // de obras son 1 a 1 en ambos archivos)
  const progObraCountPorCliente = new Map();
  groupBy(programacion, p=>normalize(p.cliente)).forEach((rows, ck)=>{
    progObraCountPorCliente.set(ck, new Set(rows.map(r=>normalize(r.obra))).size);
  });

  const results = [];
  const sinCruce = [];
  const usedCargueKeys = new Set();
  let camionesSinElemento = 0;

  const pushResultado = (pedido, matchRows, confianza)=>{
    const {cliente, obraProg, filas} = pedido;
    const obraReal = matchRows[0].obra;
    const sorted = [...matchRows].filter(r=>r.horaMin!==null).sort((a,b)=>a.horaMin-b.horaMin);
    if (sorted.length===0){
      sinCruce.push({cliente, obra:obraProg, horaProg:pedido.horaProg, cantProg:pedido.cantProg,
                     rowKey: normalize(cliente)+'||'+normalize(obraProg),
                     motivo:'Sin hora de cargue válida'});
      return;
    }

    // UNA fila de resultado POR HORA PROGRAMADA (2026-09-30). Antes era una por
    // cliente+obra, y sobre datos reales eso escondia el dia entero: PARMOL
    // tenia 10 renglones de 09:00 a 20:00 y 70 camiones en UNA sola fila,
    // juzgada por el primer camion del dia — que ese dia fue uno de 2 m3 a las
    // 00:10, y hacia "Cumplido" a los 70.
    const {salida: reparto, sinElemento} = repartirPorGrupo(filas, sorted);
    camionesSinElemento += sinElemento;

    // El trayecto es de la OBRA, no de la hora: el camino no cambia durante el
    // dia, asi que las horas de una misma obra comparten el override. La
    // observacion si es por hora, que es donde uno quiere anotar algo.
    const claveObra = normalize(cliente)+'||'+normalize(obraReal);
    const hasOverride = state.trayectoOverrides.has(claveObra);
    // La zona es de la OBRA, igual que el trayecto. Una hora sin camiones
    // ("Sin despachar") no tiene planta propia, y hasta el 2026-10-07 caia en
    // 'Sin zona': desaparecia de Santo Domingo y Punta Cana y disparaba el
    // aviso de "planta sin zona" con la lista vacia. El 29-09 eran tres horas
    // de MACAO, cuyas otras horas salieron de plantas de Punta Cana. Se toma
    // la planta del primer camion de la obra; la programacion no sirve de
    // respaldo porque ese archivo no trae columna Zona.
    const plantaObra = (sorted.find(r => r.planta) || {}).planta || null;

    reparto.forEach(({grupo, pedido: ph, camiones})=>{
      const primero = camiones[0] || null;
      const planta = primero ? primero.planta : null;
      const trayecto = hasOverride ? state.trayectoOverrides.get(claveObra)
                                   : (planta ? assumptions.trayecto[planta] : null);
      const horaLlegadaEst = (primero && trayecto!==undefined && trayecto!==null)
        ? (primero.horaMin + assumptions.cargue + assumptions.calidad + trayecto) : null;
      // sin hora programada valida no hay contra que comparar: eso NO puede dar Cumplido
      const diff = (horaLlegadaEst!==null && ph.hora!==null) ? (horaLlegadaEst - ph.hora) : null;
      // Llegar antes CUMPLE, por mucho que sea (pedido del usuario, 2026-10-09):
      // solo incumple lo que llega tarde mas alla de la tolerancia. Del
      // 2026-10-02 al 2026-10-09 hubo un piso (toleranciaAdelanto, 60 min por
      // defecto) que hacia incumplir los adelantos grandes; en la practica eran
      // clientes que pidieron antes, y se saco. Aplica tambien a los dias ya
      // guardados: el piso que tengan guardado ya no se usa.
      const calculado = (diff!==null)
                   ? (diff<=assumptions.tolerancia ? 'Cumplido' : 'Incumplido')
                   : (ph.hora===null ? 'Sin hora programada'
                   : !primero ? 'Sin despachar' : 'Sin dato de planta');
      const plantaZona = planta || plantaObra;
      const zona = plantaZona ? (assumptions.zonaPlanta[plantaZona] || 'Sin zona') : 'Sin zona';
      const rowKey = claveFila(cliente, obraReal, grupo.bomba, grupo.elemento, ph.hora);
      // Pasada a cumplido a mano (pedido del usuario, 2026-10-26): el 23/10 la
      // escalera de 4 m3 de TERRAMARE y la columna de 8 m3 de IRUYA salian
      // incumplidas porque iban despues de otro elemento con la misma bomba,
      // aunque el servicio arranco a tiempo. Solo una incumplida y solo con
      // motivo: sin motivo vuelve a ser incumplida, para que siempre quede
      // dicho por que se movio. Cuenta como cumplida en todo; `manual` es lo
      // que hace que la pantalla y el PDF digan "Cumplido (manual)".
      const manual = calculado === 'Incumplido' && esCumplidoManual(state, rowKey);
      const estado = manual ? 'Cumplido' : calculado;

      results.push({
        cliente, obraProg, obraReal, horaProg: ph.hora, cantProg: ph.cantidad,
        bomba: grupo.bomba, elemento: grupo.elemento,
        despachado: ph.despachado, pendiente: ph.pendiente,
        rowKey, claveObra, isOverride: hasOverride,
        // La clave con la que la pantalla tiene que guardar el trayecto
        // corregido. Hasta el 2026-10-06 la casilla usaba rowKey (que lleva la
        // hora) y el calculo leia claveObra: lo que se escribia no se aplicaba.
        claveTrayecto: claveObra,
        horaCargue: primero ? primero.horaMin : null, planta, trayecto, horaLlegadaEst,
        diff, estado, manual, zona, confianza,
        cantReal: camiones.reduce((s,r)=>s+r.cantidad,0),
        cargues: camiones.length, matchRows: camiones,
        // La observacion va por fila: cliente, obra, bomba, elemento y hora.
        // Sin respaldo a claves viejas: los dias guardados con las claves
        // anteriores se borraron y recargaron el 2026-10-06.
        observacion: state.observaciones.get(rowKey) || ''
      });
    });
  };

  // Pasada 1: coincidencias exactas cliente+obra, que reservan su grupo de cargue
  const sinMatchExacto = [];
  progGroups.forEach((rows, key)=>{
    const horasProg = rows.map(r=>r.horaMin).filter(v=>v!==null);
    const pedido = {
      cliente: rows[0].cliente,
      obraProg: rows[0].obra,
      // `filas` son los renglones crudos de la programacion de esa obra: es lo
      // que permite partirla por hora despues de cruzar. horaProg y cantProg
      // se conservan para los avisos de "sin cruce", que hablan de la obra
      // entera y no de una hora.
      filas: rows,
      horaProg: horasProg.length ? Math.min(...horasProg) : null,
      cantProg: rows.reduce((s,r)=>s+r.cantidad,0),
    };
    const matchRows = cargueGroups.get(key);
    if (matchRows){
      usedCargueKeys.add(key);
      pushResultado(pedido, matchRows, 'Alta');
    } else {
      sinMatchExacto.push(pedido);
    }
  });

  // Pasada 2: coincidencia difusa SOLO sobre grupos de cargue que nadie reservo,
  // y cada grupo elegido queda reservado tambien, para que dos pedidos del mismo
  // cliente no "cumplan" los dos con los mismos camiones.
  //
  // La asignacion es GLOBAL, por puntaje (#164, 2026-10-23). Antes cada pedido
  // tomaba el mejor cargue libre en el orden de la programacion, y con puntaje
  // empatado ganaba el primero: el 19/10 "EPOKAL - AREA HOTEL" (ESCALERA) y
  // "EPOKAL - COMERCIAL" (COLUMNA) empataban 0,40 contra el unico cargue,
  // "EPOKAL AREA COMERCIAL" (camiones de COLUMNA), y se lo llevaba HOTEL:
  // COMERCIAL salia como 10 m3 cancelados aunque se despacho. Ahora se ordenan
  // todos los pares pedido-obra por puntaje y, en empate, por cuantos camiones
  // de esa obra traen un elemento del pedido; recien despues por el orden de la
  // programacion, que es lo unico que decidia antes.
  const elementosDelPedido = pedido => [...new Set(pedido.filas.map(f => normalize(f.elemento)).filter(Boolean))];
  const coincidenciaDeElemento = (pedido, orows) => {
    const elementos = elementosDelPedido(pedido);
    if (!elementos.length || !orows.length) return 0;
    return orows.filter(c => elementoDestino(elementos, c.elemento) !== null).length / orows.length;
  };
  const libresDelCliente = clienteKey => {
    const porObra = new Map();
    groupBy(cargueByCliente.get(clienteKey) || [], c=>normalize(c.obra)).forEach((orows, ok)=>{
      if (!usedCargueKeys.has(clienteKey+'||'+ok)) porObra.set(ok, orows);
    });
    return porObra;
  };
  const pares = [];
  sinMatchExacto.forEach((pedido, orden)=>{
    const clienteKey = normalize(pedido.cliente);
    libresDelCliente(clienteKey).forEach((orows, ok)=>{
      const score = obraScore(pedido.obraProg, orows[0].obra);
      if (score > 0) pares.push({orden, clienteKey, ok, orows, score, elemento: coincidenciaDeElemento(pedido, orows)});
    });
  });
  pares.sort((a, b) => b.score - a.score || b.elemento - a.elemento || a.orden - b.orden);
  const asignado = new Map();   // orden del pedido -> {ok, orows, confianza}
  pares.forEach(par => {
    const clave = par.clienteKey+'||'+par.ok;
    if (asignado.has(par.orden) || usedCargueKeys.has(clave)) return;
    usedCargueKeys.add(clave);
    asignado.set(par.orden, {ok: par.ok, orows: par.orows, confianza: 'Revisar'});
  });

  sinMatchExacto.forEach((pedido, orden)=>{
    const {cliente, obraProg, horaProg, cantProg} = pedido;
    const clienteKey = normalize(cliente);
    const descartar = motivo => sinCruce.push({cliente, obra:obraProg, horaProg, cantProg, rowKey: clienteKey+'||'+normalize(obraProg), motivo});
    let elegido = asignado.get(orden);
    if (!elegido){
      if (!(cargueByCliente.get(clienteKey)||[]).length){ descartar('Cliente no aparece en el cargue real'); return; }
      const porObra = libresDelCliente(clienteKey);
      const totalProgObras = progObraCountPorCliente.get(clienteKey) || 0;
      if (porObra.size===1 && totalProgObras===1){
        // el cliente tiene una sola obra programada y una sola obra real ese dia:
        // se cruzan igual aunque el texto no coincida (codigo de proyecto vs. direccion), sin ambiguedad posible
        const [ok, orows] = [...porObra][0];
        usedCargueKeys.add(clienteKey+'||'+ok);
        elegido = {ok, orows, confianza: 'Única obra'};
      } else {
        descartar('No se encontró obra coincidente'); return;
      }
    }
    pushResultado(pedido, elegido.orows, elegido.confianza);
  });

  // grupos de cargue real (cliente+obra) que despacharon pero nunca quedaron emparejados
  // con ninguna fila de programacion (ni exacto ni por coincidencia de texto)
  cargueGroups.forEach((rows, key)=>{
    if (usedCargueKeys.has(key)) return;
    const sorted = [...rows].filter(r=>r.horaMin!==null).sort((a,b)=>a.horaMin-b.horaMin);
    if (sorted.length===0) return;
    const primero = sorted[0];
    const planta = primero.planta;
    const zona = assumptions.zonaPlanta[planta] || 'Sin zona';
    const cantReal = rows.reduce((s,r)=>s+r.cantidad,0);
    const rowKeySinProg = normalize(primero.cliente)+'||'+normalize(primero.obra);
    results.push({
      cliente: primero.cliente, obraProg: '', obraReal: primero.obra, horaProg: null, cantProg: 0,
      rowKey: rowKeySinProg, isOverride: false,
      horaCargue: primero.horaMin, planta, trayecto: null, horaLlegadaEst: null, diff: null,
      estado: 'Sin programación', zona, confianza: '—', cantReal, cargues: rows.length, matchRows: rows,
      trayecto: assumptions.trayecto[planta] ?? null, observacion: state.observaciones.get(rowKeySinProg) || ''
    });
  });

  const cargueClientesSinProg = new Set(results.filter(r=>r.estado==='Sin programación').map(r=>r.cliente));

  return {results, sinCruce,
          // Lo que la programacion declara sin despachar. Va aparte de
          // `sinCruce` a proposito: eso son cruces que fallaron, esto son
          // entregas que no salieron. Son dos problemas distintos.
          noDespachado: noDespachado(state.programacion),
          // camiones cuyo elemento no coincidio con ninguno de su obra y se
          // asignaron por la regla de respaldo de repartirPorGrupo()
          camionesSinElemento,
          cargueSinProg: results.filter(r=>r.estado==='Sin programación'),
          cargueSinProgCount: cargueClientesSinProg.size};
}

  // ================= RESUMEN POR CLIENTE =================

// Espaciamiento entre camiones de una obra: los minutos entre cargues
// consecutivos. "No cumple" si alguno supera el maximo. Con menos de dos
// cargues no hay intervalo que medir y es N/A. Se mide sobre el cargue real,
// no sobre la programacion: es cuanto espero la obra entre un camion y otro.
function evaluarEspaciamiento(horas, maximo){
  const h = horas.filter(v => v !== null && v !== undefined && !isNaN(v)).sort((a, b) => a - b);
  const gaps = [];
  for (let i = 1; i < h.length; i++) gaps.push(h[i] - h[i - 1]);
  if (!gaps.length) return {estado: 'N/A', intervalos: 0, excedidos: 0, maxGap: null};
  const excedidos = gaps.filter(g => g > maximo).length;
  return {estado: excedidos ? 'No cumple' : 'Cumple', intervalos: gaps.length, excedidos,
          maxGap: Math.max(...gaps)};
}

// El espaciamiento de una obra, medido POR ELEMENTO y sumado (2026-10-08).
// Cada elemento es su propia colada: el hueco entre el ultimo camion de un
// elemento y el primero de otro no es espera de la obra. Medido junto daba un
// "No cumple" falso —el 02-10, VIGAFILI: fino de techo 08:35 y el piso pulido
// 11:09, 154 minutos "entre camiones" de dos elementos distintos—.
const claveElemento = r => normalize(r.elemento);
function espaciamientoPorElemento(rows, maximo){
  const evs = [...groupBy(rows, claveElemento).values()]
    .map(g => evaluarEspaciamiento(g.map(r => r.horaMin), maximo))
    .filter(e => e.estado !== 'N/A');
  if (!evs.length) return {estado: 'N/A', intervalos: 0, excedidos: 0, maxGap: null};
  const excedidos = evs.reduce((s, e) => s + e.excedidos, 0);
  return {estado: excedidos ? 'No cumple' : 'Cumple', excedidos,
          intervalos: evs.reduce((s, e) => s + e.intervalos, 0),
          maxGap: Math.max(...evs.map(e => e.maxGap))};
}

function computeResumen(state, assumptions = {}){
  if (!state.cargue) return null;
  const maximo = assumptions.espaciamiento ?? ESPACIAMIENTO_POR_DEFECTO;
  // m3 programados por cliente y por cliente+obra, para ponerlos al lado de
  // los despachados. null cuando el cliente u obra no estaba programado.
  const progCliente = new Map(), progObra = new Map();
  (state.programacion || []).forEach(p => {
    const kc = normalize(p.cliente), ko = kc + '||' + normalize(p.obra);
    progCliente.set(kc, (progCliente.get(kc) || 0) + (p.cantidad || 0));
    progObra.set(ko, (progObra.get(ko) || 0) + (p.cantidad || 0));
  });
  const byCliente = groupBy(state.cargue, c=>c.cliente);
  const clientes = [];
  byCliente.forEach((rows, cliente)=>{
    const m3 = rows.reduce((s,r)=>s+r.cantidad,0);
    const camiones = new Set(rows.map(r=>r.ficha)).size;
    const obrasSet = groupBy(rows, r=>r.obra);
    const obras = obrasSet.size;
    const horas = rows.map(r=>r.horaMin).filter(v=>v!==null);
    const primera = horas.length? Math.min(...horas): null;
    const ultima = horas.length? Math.max(...horas): null;
    const obras_detail = [];
    obrasSet.forEach((orows, obra)=>{
      const ko = normalize(cliente) + '||' + normalize(obra);
      obras_detail.push({
        obra, m3: orows.reduce((s,r)=>s+r.cantidad,0), cargues: orows.length,
        camiones: new Set(orows.map(r=>r.ficha)).size,
        m3Prog: progObra.has(ko) ? progObra.get(ko) : null,
        espaciamiento: espaciamientoPorElemento(orows, maximo),
      });
    });
    obras_detail.sort((a,b)=>b.m3-a.m3);
    // `delta`: minutos desde el cargue anterior A LA MISMA OBRA Y ELEMENTO, que
    // es lo que mide el espaciamiento. null en el primero de cada elemento.
    const previo = new Map();
    const cargues_detail = [...rows].sort((a,b)=>(a.horaMin??0)-(b.horaMin??0)).map(r => {
      const valida = r.horaMin !== null && r.horaMin !== undefined && !isNaN(r.horaMin);
      const ko = normalize(r.obra) + '||' + claveElemento(r), ant = previo.get(ko);
      const delta = valida && ant !== undefined ? r.horaMin - ant : null;
      if (valida) previo.set(ko, r.horaMin);
      return {...r, delta, tipo: tipoDeElemento(r.elemento)};
    });
    // Agrupados por tipo de elemento (pedido del usuario, 2026-10-08), el que
    // mas m3 movio primero, y dentro de cada tipo por hora. El `delta` ya se
    // calculo en orden de hora, antes de reordenar.
    const m3Tipo = new Map();
    cargues_detail.forEach(c => m3Tipo.set(c.tipo, (m3Tipo.get(c.tipo) || 0) + (c.cantidad || 0)));
    cargues_detail.sort((a, b) => m3Tipo.get(b.tipo) - m3Tipo.get(a.tipo)
      || a.tipo.localeCompare(b.tipo) || (a.horaMin ?? 0) - (b.horaMin ?? 0));
    const evs = obras_detail.map(o => o.espaciamiento).filter(e => e.estado !== 'N/A');
    const espaciamiento = !evs.length
      ? {estado: 'N/A', intervalos: 0, excedidos: 0, maxGap: null}
      : (() => {
          const excedidos = evs.reduce((s, e) => s + e.excedidos, 0);
          return {estado: excedidos ? 'No cumple' : 'Cumple', excedidos,
                  intervalos: evs.reduce((s, e) => s + e.intervalos, 0),
                  maxGap: Math.max(...evs.map(e => e.maxGap))};
        })();
    const kc = normalize(cliente);
    clientes.push({cliente, m3, m3Prog: progCliente.has(kc) ? progCliente.get(kc) : null,
                   cargues:rows.length, camiones, obras, primera, ultima, espaciamiento,
                   obras_detail, cargues_detail});
  });
  clientes.sort((a,b)=>b.m3-a.m3);
  const kpi = {
    m3_total: clientes.reduce((s,c)=>s+c.m3,0),
    cargues_total: state.cargue.length,
    camiones_total: new Set(state.cargue.map(r=>r.ficha)).size,
    clientes_total: clientes.length,
    obras_total: groupBy(state.cargue, r=>r.obra).size
  };
  return {kpi, clientes};
}

  // ================= EL DIA, DE IDA Y DE VUELTA =================
  //
  // Convertir el estado del dashboard en lo que se guarda, y al reves. Las dos
  // son puras a proposito: el viaje de ida y vuelta se prueba sin navegador ni
  // servidor, y lo que se prueba es que no se pierda nada por el camino.
  //
  // Los supuestos viajan CON el dia —incluido el trayecto y la zona de cada
  // planta— y eso es lo que hace que reabrir un dia viejo muestre lo que se vio
  // ese dia, en vez de recalcularlo con los supuestos de hoy.

  function payloadDelDia(state, assumptions, fecha){
    const plantas = Object.keys(assumptions.trayecto).sort().map(planta => ({
      planta,
      trayecto: assumptions.trayecto[planta] ?? null,
      zona: assumptions.zonaPlanta[planta] || null,
    }));
    return {
      fecha,
      cargue: assumptions.cargue,
      calidad: assumptions.calidad,
      tolerancia: assumptions.tolerancia,
      toleranciaAdelanto: assumptions.toleranciaAdelanto ?? ADELANTO_POR_DEFECTO,
      espaciamiento: assumptions.espaciamiento ?? ESPACIAMIENTO_POR_DEFECTO,
      plantas,
      // Con los pedidos de Macao (2026-11-03): restaurarDia los vuelve a separar.
      programacion: [...(state.programacion || []), ...(state.programacionMacao || [])],
      // Con los viajes de Macao (2026-10-28): restaurarDia los vuelve a separar.
      cargue_rows: [...(state.cargue || []), ...(state.cargueMacao || [])],
      trayectoOverrides: Object.fromEntries(state.trayectoOverrides || new Map()),
      // Las vacias no se mandan: una observacion borrada es una observacion
      // que no existe, no una cadena vacia guardada.
      observaciones: Object.fromEntries(
        [...(state.observaciones || new Map())].filter(([, v]) => (v || '').trim() !== '')),
      // Solo los valores validos: un "—" en la pantalla es que no hay responsable.
      responsables: Object.fromEntries(
        [...(state.responsables || new Map())].filter(([, v]) => RESPONSABLES.includes(v))),
      motivos: Object.fromEntries(
        [...(state.motivos || new Map())].filter(([, v]) => MOTIVOS.includes(v))),
      // Solo las que tienen motivo: sin motivo no cuentan como cumplidas
      // (esCumplidoManual), y guardarlas dejaria una marca que no se ve.
      cumplidosManuales: [...(state.cumplidosManuales || new Set())]
        .filter(k => MOTIVOS.includes((state.motivos || new Map()).get(k))).sort(),
    };
  }

  function restaurarDia(dia){
    const trayecto = {}, zonaPlanta = {};
    (dia.supuestos.plantas || []).forEach(p => {
      if (p.trayecto !== null && p.trayecto !== undefined) trayecto[p.planta] = p.trayecto;
      if (p.zona) zonaPlanta[p.planta] = p.zona;
    });
    return {
      state: {
        // Lo que hoy no entra (Macao, VMO CONCRETOS) se saca tambien de los
        // dias guardados antes de que se decidiera.
        programacion: (dia.programacion || []).filter(f => !quedaFuera(f)),
        cargue: (dia.cargue || []).filter(f => !quedaFuera(f)),
        // Los viajes de Macao, solo para Indicadores (camiones).
        cargueMacao: (dia.cargue || []).filter(f => !esClienteInterno(f.cliente) && esMacao(f.cliente, f.obra)),
        // Los pedidos de Macao, solo para el Reporte de cancelados.
        programacionMacao: (dia.programacion || []).filter(f => !esClienteInterno(f.cliente) && esMacao(f.cliente, f.obra)),
        trayectoOverrides: new Map(Object.entries(dia.trayectoOverrides || {})),
        observaciones: new Map(Object.entries(dia.observaciones || {})),
        responsables: new Map(Object.entries(dia.responsables || {})),
        motivos: new Map(Object.entries(dia.motivos || {})),
        cumplidosManuales: new Set(dia.cumplidosManuales || []),
        fecha: dia.fecha,
      },
      assumptions: {
        cargue: dia.supuestos.cargue,
        calidad: dia.supuestos.calidad,
        tolerancia: dia.supuestos.tolerancia,
        // Un dia guardado ANTES del 2026-10-02 no trae este supuesto y llega
        // null. Cae al default, igual que un dia nuevo: la alternativa seria
        // dejarlo sin piso y que esos dias siguieran contando como cumplidos
        // adelantos de ocho horas, que es justo el defecto que se corrigio.
        // Es el mismo criterio que cuando cambio el modelo de cumplimiento el
        // 30-09: una correccion del calculo arregla el historial hacia atras.
        toleranciaAdelanto: dia.supuestos.toleranciaAdelanto ?? ADELANTO_POR_DEFECTO,
        espaciamiento: dia.supuestos.espaciamiento ?? ESPACIAMIENTO_POR_DEFECTO,
        trayecto, zonaPlanta,
      },
    };
  }

  // ================= ESTADISTICAS SOBRE VARIOS DIAS =================
  //
  // Todo lo de aca parte de lo que devuelve computeCumplimiento(), o sea que
  // el cumplimiento se sigue calculando en un solo lugar. Estas funciones solo
  // lo agrupan.
  //
  // La regla que comparten todas: **solo Cumplido e Incumplido entran al
  // porcentaje**. "Sin programacion", "Sin hora programada" y "Sin dato de
  // planta" se cuentan aparte y NUNCA en el denominador — es la misma regla
  // que la pantalla del dia, y el 2026-09-29 ya costo que el Excel exportado
  // usara otra y diera un numero distinto al del dashboard.

  function _evaluables(results){
    return results.filter(r => r.estado === 'Cumplido' || r.estado === 'Incumplido');
  }

  // Los nombres de las dos unidades (pedido del usuario, 2026-10-13). Solo
  // cambiaron los nombres, no la cuenta: `pct` (pesado por m3) se llama
  // "Frecuencia de despacho" y `pctPedidos` (cada entrega vale 1, juzgada por
  // su primer camion) se llama "Inicio de carga". Viven aca para que las tres
  // pantallas digan lo mismo.
  const NOMBRE_PCT = 'Frecuencia de despacho';
  const NOMBRE_PCT_PEDIDOS = 'Inicio de carga';

  function resumenDeCumplimiento(results){
    // **Se devuelven las DOS unidades** (decision de Axel, 2026-10-01), porque
    // ninguna de las dos es la correcta en abstracto y medirlas sobre los dos
    // primeros dias reales mostro algo que obliga a ver ambas: no solo dan
    // distinto, dan distinto EN SENTIDOS OPUESTOS.
    //
    //                 por volumen   por pedido
    //   29-09-2026          8%          23%
    //   30-09-2026         23%          19%
    //
    // Por volumen el despacho MEJORO entre los dos dias; contando pedidos
    // EMPEORO. Un indicador que cambia de signo segun la unidad no se puede
    // publicar con una sola, asi que se muestran las dos y la discrepancia
    // queda a la vista — que es justo el caso que vale mirar.
    //
    // `pct` pesa por M3 desde el 2026-10-02. Antes pesaba por CARGUE, y el
    // cambio lo pidio la companera de Axel con un argumento correcto: contar
    // cargues asume que todos mueven el mismo volumen, y no es cierto. Medido
    // sobre los tres dias guardados, los 435 cargues evaluables van de **1 a
    // 16 m3** (mediana 7, promedio 7,89; el 9% esta por debajo de 5 m3). Los
    // m3 reales ya venian en cada fila (`cantReal`), asi que la suposicion era
    // evitable sin pedir ningun dato nuevo.
    //
    // Cuanto mueve el cambio, medido ANTES de hacerlo: poco. El acumulado pasa
    // de 19% a 17%, y por planta la diferencia va de 0 a 3 puntos, siempre
    // hacia abajo (los cargues que cumplieron son algo mas chicos que el
    // promedio). O sea que es una correccion de rigor, no un numero distinto:
    // la unidad que de verdad cambia el resultado sigue siendo `pctPedidos`,
    // que se separa hasta 25 puntos.
    //
    // Por que m3 REEMPLAZA a la unidad por cargue en vez de sumarse: las dos
    // decian lo mismo con 2 puntos de diferencia, y tres unidades en pantalla
    // obligan a explicar por que estan las tres. m3 gana porque es lo que se
    // factura y no asume nada.
    //
    // `camiones`/`camionesCumplidos` se siguen devolviendo, pero SOLO como
    // cuenta informativa: son cargues, o sea viajes, no camiones distintos (un
    // camion que hace tres viajes cuenta tres veces — el 29-09 tuvo 178
    // cargues de 63 camiones). Ningun porcentaje sale de ellos.
    //
    // Por que pesar por volumen y no contar entregas: cada hora programada se
    // juzga por su primer camion —si la colada arranco a tiempo— y despues
    // pesa por lo que movio, asi que una colada de 64 cargues no pesa igual
    // que un pedido de uno. `pctPedidos` es la unidad de la version de la
    // companera de Axel, y responde la otra pregunta: a cuantos clientes se
    // dejo esperando.
    //
    // Por que NO juzgar cada camion contra la hora (la tercera variante, que
    // sigue descartada): una colada continua manda camiones durante diez horas
    // contra un "11:00", asi que el camion 50 sale tarde por definicion aunque
    // todo haya ido bien. Medido sobre el 29-09: daba 5%, y seria 5% siempre.
    const ev = _evaluables(results);
    const cumplidos = ev.filter(r => r.estado === 'Cumplido');
    const cam = ev.reduce((s, r) => s + (r.cargues || 0), 0);
    const camOk = cumplidos.reduce((s, r) => s + (r.cargues || 0), 0);
    const m3 = ev.reduce((s, r) => s + (r.cantReal || 0), 0);
    const m3Ok = cumplidos.reduce((s, r) => s + (r.cantReal || 0), 0);
    return {
      pedidos: ev.length,
      pedidosCumplidos: cumplidos.length,
      camiones: cam,
      camionesCumplidos: camOk,
      m3,
      m3Cumplidos: m3Ok,
      // null, no 0, en las dos: "no hubo nada que evaluar" y "no cumplio nada"
      // son cosas distintas y se ven igual si las dos dan 0.
      pct: m3 ? Math.round(100 * m3Ok / m3) : null,
      pctPedidos: ev.length ? Math.round(100 * cumplidos.length / ev.length) : null,
      noEvaluables: results.length - ev.length,
    };
  }

  function cumplimientoPorPlanta(results){
    // La planta de un pedido es la de su PRIMER camion, que es la misma que
    // decide su trayecto. Un pedido servido por dos plantas cuenta entero en
    // la primera: partirlo exigiria un cumplimiento por camion, que es otra
    // medida.
    const por = new Map();
    _evaluables(results).forEach(r => {
      // plantaDe() y no `r.planta || '...'`: el selector, el filtro y esta
      // tabla tienen que llamar igual a la planta ausente o la vista filtrada
      // de "Sin planta" saldria vacia.
      const planta = plantaDe(r);
      if (!por.has(planta)) por.set(planta, {planta, zona: r.zona, pedidos: 0,
                                             pedidosCumplidos: 0,
                                             camiones: 0, camionesCumplidos: 0,
                                             m3: 0, m3Cumplidos: 0});
      const acc = por.get(planta);
      acc.pedidos++;
      acc.camiones += r.cargues || 0;
      acc.m3 += r.cantReal || 0;
      if (r.estado === 'Cumplido'){
        acc.pedidosCumplidos++;
        acc.camionesCumplidos += r.cargues || 0;
        acc.m3Cumplidos += r.cantReal || 0;
      }
    });
    // Las dos unidades, mismo criterio que el total — y el mismo peso: `pct`
    // es por M3 desde el 2026-10-02, igual que en resumenDeCumplimiento(). Por
    // planta la brecha entre ambas es todavia mas grande que en el total
    // —Movil VI da 75% por volumen y 50% por pedido sobre los tres dias,
    // porque sus horas cumplidas movieron las coladas grandes— asi que mostrar
    // una sola ordenaria mal las plantas.
    return [...por.values()]
      .map(a => ({...a,
                  pct: a.m3 ? Math.round(100 * a.m3Cumplidos / a.m3) : null,
                  pctPedidos: a.pedidos ? Math.round(100 * a.pedidosCumplidos / a.pedidos) : null}))
      // Ordenadas por volumen, que es la unidad del porcentaje: la planta que
      // mas mueve va primero.
      .sort((a, b) => b.m3 - a.m3 || a.planta.localeCompare(b.planta));
  }

  // ================= POR TIPO DE ELEMENTO (2026-10-08) =================
  //
  // El usuario quiere ver siempre el cumplimiento por tipo de elemento, y la
  // tabla del dia en ese mismo orden. El tipo es el elemento sin el sufijo de
  // modulo o numero que trae Macao: "COLUMNA M1" y "COLUMNA M5" son COLUMNA,
  // "MURO M4" es MURO. Lo demas se respeta tal cual ("FINO DE TECHO").
  function tipoDeElemento(elemento){
    const t = normalize(elemento).split(' ').filter(Boolean);
    while (t.length > 1 && /^(M\d+|\d+)$/.test(t[t.length - 1])) t.pop();
    return t.length ? t.join(' ') : 'SIN ELEMENTO';
  }

  // Mismo calculo y mismas dos unidades que cumplimientoPorPlanta(), agrupado
  // por tipo. Ordenado por volumen: el tipo que mas mueve va primero.
  function cumplimientoPorElemento(results){
    const por = new Map();
    _evaluables(results).forEach(r => {
      const tipo = tipoDeElemento(r.elemento);
      if (!por.has(tipo)) por.set(tipo, {tipo, pedidos: 0, pedidosCumplidos: 0, m3: 0, m3Cumplidos: 0});
      const acc = por.get(tipo);
      acc.pedidos++;
      acc.m3 += r.cantReal || 0;
      if (r.estado === 'Cumplido'){ acc.pedidosCumplidos++; acc.m3Cumplidos += r.cantReal || 0; }
    });
    return [...por.values()]
      .map(a => ({...a,
                  pct: a.m3 ? Math.round(100 * a.m3Cumplidos / a.m3) : null,
                  pctPedidos: a.pedidos ? Math.round(100 * a.pedidosCumplidos / a.pedidos) : null}))
      .sort((a, b) => b.m3 - a.m3 || a.tipo.localeCompare(b.tipo));
  }

  // Las filas del dia en el orden del cuadro por elemento. Dentro de cada tipo
  // sigue el orden de antes: incumplidos primero, el mas atrasado arriba. Lo
  // que no se evalua (sin programacion) va al final, por tipo.
  function ordenarPorElemento(rows){
    const orden = new Map(cumplimientoPorElemento(rows).map((e, i) => [e.tipo, i]));
    const pos = r => orden.has(tipoDeElemento(r.elemento)) ? orden.get(tipoDeElemento(r.elemento)) : orden.size;
    return [...rows].sort((a, b) =>
      pos(a) - pos(b)
      || tipoDeElemento(a.elemento).localeCompare(tipoDeElemento(b.elemento))
      || (a.estado === b.estado ? (b.diff ?? 0) - (a.diff ?? 0) : (a.estado === 'Incumplido' ? -1 : 1)));
  }

  // La tabla "Cumplimiento por cliente / obra" (pedido del usuario, 2026-10-09):
  // primero los incumplidos, despues los cumplidos y al final lo que no se
  // evalua; dentro de cada estado, por compania de la A a la Z. El cuadro por
  // elemento y la imagen siguen con ordenarPorElemento.
  const RANGO_ESTADO = {'Incumplido': 0, 'Cumplido': 1, 'Sin despachar': 2,
                        'Sin hora programada': 3, 'Sin dato de planta': 4, 'Sin programación': 5};
  function ordenarParaTablaDelDia(rows){
    const rango = r => RANGO_ESTADO[r.estado] ?? 6;
    const az = (a, b) => (a || '').localeCompare(b || '', 'es', {sensitivity: 'base'});
    return [...rows].sort((a, b) =>
      rango(a) - rango(b)
      || az(a.cliente, b.cliente)
      || az(a.obraReal || a.obraProg, b.obraReal || b.obraProg)
      || (a.horaProg ?? Infinity) - (b.horaProg ?? Infinity));
  }

  function serieDeCumplimiento(dias){
    // `dias` es [{fecha, results}] — un dia ya recalculado por cada fecha del
    // historial. Sale ordenada por fecha ascendente para dibujarla.
    return [...dias]
      .sort((a, b) => a.fecha.localeCompare(b.fecha))
      .map(d => ({fecha: d.fecha, ...resumenDeCumplimiento(d.results)}));
  }

  function acumuladoDeCumplimiento(dias){
    // El porcentaje de todo el rango junto. NO es el promedio de los
    // porcentajes diarios: un dia con 2 pedidos pesaria lo mismo que uno con
    // 80. Se suman los pedidos y se divide una sola vez.
    const todos = dias.flatMap(d => d.results);
    return {...resumenDeCumplimiento(todos), dias: dias.length};
  }

  function plantasOatYDelDia(dias, fechaDelDia){
    // Una fila por planta con sus DOS ventanas: el OAT —of all time, todo el
    // historial guardado— y el dia elegido.
    //
    // El OAT se calcula sobre TODOS los dias que se le pasen, no sobre un
    // rango: si algun dia hay filtro de fechas en la pantalla, tiene que
    // seguir recibiendo el historial entero o dejaria de ser "of all time".
    //
    // Una planta que existe en el historial pero no trabajo ese dia sale igual,
    // con `dia: null`. Desaparecer de la tabla se leeria como que cumplio.
    const oat = cumplimientoPorPlanta(dias.flatMap(d => d.results));
    const delDia = new Map(
      cumplimientoPorPlanta(
        (dias.find(d => d.fecha === fechaDelDia) || {results: []}).results
      ).map(p => [p.planta, p]));
    // Las dos ventanas se arman con la MISMA funcion, para que no pueda pasar
    // que una lleve un campo que la otra no — el OAT y el dia se muestran uno
    // al lado del otro y tienen que ser comparables campo a campo.
    const ventana = p => p ? {pedidos: p.pedidos, pedidosCumplidos: p.pedidosCumplidos,
                              camiones: p.camiones, camionesCumplidos: p.camionesCumplidos,
                              m3: p.m3, m3Cumplidos: p.m3Cumplidos,
                              pct: p.pct, pctPedidos: p.pctPedidos} : null;
    return oat.map(p => ({
      planta: p.planta,
      zona: p.zona,
      oat: ventana(p),
      dia: ventana(delDia.get(p.planta)),
    }));
  }

  // ================= LA PAGINA, FILTRADA POR UNA PLANTA =================
  //
  // La jefa de Axel pidio ver las estadisticas por movil (2026-10-01). El
  // filtro se hace ACA y no en la pantalla por una razon concreta: si la
  // pantalla filtrara por su cuenta, el porcentaje de una planta se calcularia
  // en dos lugares distintos —aca para la tabla de todas, alla para la vista
  // filtrada— y podrian discrepar. Con el filtro aca, las dos vistas pasan por
  // resumenDeCumplimiento() y hay un test que exige que den el mismo numero.

  // El nombre de planta que usa TODO lo de arriba cuando la fila no la trae.
  // Una sola constante para que el selector, el filtro y cumplimientoPorPlanta
  // no se desincronicen.
  const SIN_PLANTA = 'Sin planta';
  const plantaDe = r => r.planta || SIN_PLANTA;

  // La zona de una planta es la de ⚙ Supuestos de ese dia, en todos lados:
  // pestanas del dia, PDF, Estadisticas y Comparacion (decision del usuario,
  // 2026-10-23, #169). Hasta ese dia el PDF, Estadisticas y Comparacion usaban
  // esta lista fija (decision del 2026-10-09) y el dia usaba los supuestos:
  // una planta nueva, que entra en Santo Domingo por defecto, salia en una
  // zona en la pantalla y en otra en el PDF. La lista queda solo de respaldo
  // para una fila o un camion sin zona en los supuestos: Santo Domingo son
  // Movil II, Movil VI, SDN y San Isidro; todas las demas, Punta Cana.
  const PLANTAS_SANTO_DOMINGO = ['MOVILII', 'MOVILVI', 'SDN', 'SANISIDRO'];
  const ZONAS = ['Santo Domingo', 'Punta Cana'];
  const PREFIJO_ZONA = 'zona:';
  function zonaDePlanta(planta){
    if (!planta || planta === SIN_PLANTA) return null;
    return PLANTAS_SANTO_DOMINGO.includes(normalize(planta).replace(/ /g, '')) ? 'Santo Domingo' : 'Punta Cana';
  }
  // `r.zona` la pone computeCumplimiento con los supuestos del dia, y
  // cargueConZona() a los camiones; sin ella, la lista fija.
  const zonaDeFila = r => (ZONAS.includes(r.zona) ? r.zona : null) || zonaDePlanta(r.planta);
  // Los camiones del cargue con la zona de su planta en los supuestos del dia,
  // para que m3 y camiones por zona usen la misma regla que las entregas. Copia:
  // el cargue del estado es lo que se guarda y no lleva zona.
  const cargueConZona = (cargue, zonaPlanta = {}) =>
    (cargue || []).map(c => zonaPlanta[c.planta] ? {...c, zona: zonaPlanta[c.planta]} : c);
  // El filtro: vacio = todo, 'zona:<zona>' = una zona, si no el nombre de una planta.
  function filaDelFiltro(r, filtro){
    if (!filtro) return true;
    if (filtro.startsWith(PREFIJO_ZONA)) return zonaDeFila(r) === filtro.slice(PREFIJO_ZONA.length);
    return plantaDe(r) === filtro;
  }

  // ================= FILTRO BOMBA / DIRECTO (2026-10-13) =================
  // Pedido del usuario: ver el cumplimiento solo de los pedidos con bomba o
  // solo de los directos, en el dia, en Estadisticas y en Comparacion. El
  // servicio sale del renglon de la programacion (normalizarBomba: vacio, 0,
  // NO... es Directo). Los camiones sin programacion no tienen servicio y
  // quedan fuera de los dos filtros; tampoco entran al porcentaje.
  const SERVICIOS = ['bomba', 'directo'];
  const NOMBRE_SERVICIO = {bomba: 'Con bomba', directo: 'Directo'};
  function servicioDeFila(r){
    if (!r || r.estado === 'Sin programación') return null;
    return r.bomba && r.bomba !== 'Directo' ? 'bomba' : 'directo';
  }
  function filtrarPorServicio(rows, servicio){
    if (!servicio) return rows;
    return (rows || []).filter(r => servicioDeFila(r) === servicio);
  }
  // Igual que filtrarDiasPorPlanta: se conservan todos los dias, aunque queden
  // sin filas, para que el eje de fechas no mienta.
  function filtrarDiasPorServicio(dias, servicio){
    if (!servicio) return dias;
    return dias.map(d => ({...d, results: filtrarPorServicio(d.results || [], servicio)}));
  }

  function plantasDelHistorial(dias){
    // Las plantas que aparecen en el historial, con su zona, ordenadas por
    // volumen igual que la tabla. Sale de las filas y no de los supuestos del
    // dia a proposito: los supuestos pueden tener una planta cargada que nunca
    // despacho, y el selector solo tiene que ofrecer plantas con datos.
    const por = new Map();
    dias.forEach(d => (d.results || []).forEach(r => {
      const planta = plantaDe(r);
      if (!por.has(planta)) por.set(planta, {planta, zona: r.zona || null, filas: 0,
                                             camiones: 0, m3: 0});
      const acc = por.get(planta);
      acc.filas++;
      acc.camiones += r.cargues || 0;
      acc.m3 += r.cantReal || 0;
    }));
    // Por m3, que es la unidad del porcentaje desde el 2026-10-02 — el
    // comentario de arriba decia "por volumen" cuando todavia ordenaba por
    // cargues, y ahora lo es de verdad.
    return [...por.values()]
      .sort((a, b) => b.m3 - a.m3 || a.planta.localeCompare(b.planta));
  }

  function filtrarDiasPorPlanta(dias, planta){
    // `planta` null o vacio = todas, y devuelve los dias tal cual.
    //
    // Los dias se conservan TODOS, incluso los que quedan sin ninguna fila de
    // esa planta: un dia en que la planta no despacho tiene que seguir
    // apareciendo en el grafico como "sin datos", porque desaparecer del eje
    // se leeria como que ese dia no existio.
    if (!planta) return dias;
    return dias.map(d => ({...d, results: (d.results || []).filter(r => filaDelFiltro(r, planta))}));
  }

  // ================= COMPARACION POR DIA (2026-10-12) =================
  //
  // La pestana Comparacion: un renglon por dia guardado, para ponerlos uno al
  // lado del otro. Reemplaza el HTML aparte de la companera de Axel, que leia
  // los Excel consolidados descargados dia por dia; esto sale directo del
  // historial y con el MISMO calculo que el resto del sitio (decision del
  // usuario): por m3 y por entrega, Macao fuera, lo temprano cumplido.
  //
  // `dias` es [{fecha, results, cargue, motivos, responsables}], con `cargue`
  // las filas ya restauradas (sin Macao ni clientes internos). `filtro` es el
  // mismo de filtrarDiasPorPlanta: vacio, 'zona:<zona>' o una planta.
  //
  // Los m3, cargues, camiones y clientes salen del CARGUE filtrado, no del
  // indice del servidor: el indice cuenta las filas crudas, Macao incluido, y
  // la comparacion de una zona tiene que poder sumar lo mismo que el General.
  //
  // Con `servicio` (bomba o directo) el despacho sale de los camiones de las
  // entregas de ese servicio (matchRows), porque el cargue no dice si el
  // pedido iba con bomba: los camiones sin programacion quedan fuera.
  function comparacionPorDia(dias, filtro, servicio = null){
    return [...dias]
      .sort((a, b) => a.fecha.localeCompare(b.fecha))
      .map(d => {
        const results = filtrarPorServicio((d.results || []).filter(r => filaDelFiltro(r, filtro)), servicio);
        const cargue = servicio ? results.flatMap(r => r.matchRows || [])
                                : (d.cargue || []).filter(c => filaDelFiltro(c, filtro));
        const mot = d.motivos || new Map(), resp = d.responsables || new Map();
        const incumplidos = results.filter(r => r.estado === 'Incumplido')
          .map(r => ({cliente: r.cliente, obra: r.obraReal || r.obraProg || '', planta: r.planta || null,
                      zona: zonaDeFila(r), elemento: r.elemento || null, horaProg: r.horaProg,
                      llegada: r.horaLlegadaEst, diff: r.diff, m3: r.cantReal || 0,
                      responsable: resp.get(r.rowKey) || null, motivo: mot.get(r.rowKey) || null,
                      observacion: r.observacion || ''}))
          // Por compania y despues por hora, como la tabla del dia.
          .sort((a, b) => String(a.cliente).localeCompare(String(b.cliente), 'es', {sensitivity: 'base'})
                       || (a.horaProg ?? 9999) - (b.horaProg ?? 9999));
        // Dos bloques aparte porque el resumen ya trae `m3` y `camiones` con
        // otro significado: los evaluados, no todo lo despachado.
        return {
          fecha: d.fecha,
          despacho: {
            m3: cargue.reduce((s, c) => s + (c.cantidad || 0), 0),
            cargues: cargue.length,
            camiones: new Set(cargue.map(c => c.ficha).filter(Boolean)).size,
            clientes: new Set(cargue.map(c => normalize(c.cliente)).filter(Boolean)).size,
          },
          cumplimiento: resumenDeCumplimiento(results),
          incumplidas: incumplidos.length,
          sinDespachar: results.filter(r => r.estado === 'Sin despachar').length,
          incumplidos,
        };
      });
  }

  function entregasDePlanta(dias, planta){
    // El detalle plano que se muestra cuando hay una planta elegida: una fila
    // por entrega, de la mas reciente a la mas vieja, y dentro del dia por
    // hora programada. Las que no tienen hora van al final del dia, mismo
    // criterio que pedidosPorHora().
    return filtrarDiasPorPlanta(dias, planta)
      .flatMap(d => (d.results || []).map(r => ({...r, fecha: d.fecha})))
      .sort((a, b) => b.fecha.localeCompare(a.fecha)
                   || (a.horaProg === null) - (b.horaProg === null)
                   || (a.horaProg ?? 0) - (b.horaProg ?? 0));
  }

  // ================= MOTIVOS DE INCUMPLIMIENTO (2026-10-06) =================
  //
  // Que motivo pesa mas, sobre todos los dias guardados, para saber por donde
  // atacar. SOLO entregas INCUMPLIDAS (decision del usuario): un pedido no
  // despachado tiene su propia pestana y no entra a esta metrica.
  //
  // Todo incumplido tiene responsable (VMO, Cliente o Externo) y motivo; el
  // que todavia no los tiene es un dato que falta cargar, no una categoria.
  // Por eso no entra al ranking y se devuelve como `cobertura`: un Pareto
  // armado con el 10% de los casos parece una conclusion y no lo es.
  //
  // Dos pesos, porque responden cosas distintas: `entregas` (cuantas veces
  // paso) y `m3` (cuanto volumen afecto: los m3 que llegaron tarde, cantReal,
  // la misma unidad que el % de cumplimiento).
  //
  // `dias` es [{results, motivos, responsables}], con los Map tal como los
  // devuelve restaurarDia(). `planta` y `responsable` filtran.
  function casosDeIncumplimiento(dias, planta){
    const casos = [];
    dias.forEach(d => {
      const mot = d.motivos || new Map(), resp = d.responsables || new Map();
      (d.results || []).forEach(r => {
        if (r.estado !== 'Incumplido') return;
        if (!filaDelFiltro(r, planta)) return;
        casos.push({m3: r.cantReal || 0, motivo: mot.get(r.rowKey) || null,
                    responsable: resp.get(r.rowKey) || null});
      });
    });
    return casos;
  }

  // Porcentajes enteros de partes de un total que SUMAN 100. Redondear cada
  // uno por su lado no lo garantiza: 14, 12 y 3 de 29 dan 48 + 41 + 10 = 99,
  // y eso se mostro en pantalla el 2026-10-06. Se redondea todo para abajo y
  // los puntos que faltan van a los de mayor decimal (resto mayor). Con total 0
  // devuelve ceros.
  function porcentajesQueSuman100(valores){
    const total = valores.reduce((s, v) => s + v, 0);
    if (!total) return valores.map(() => 0);
    const exactos = valores.map(v => 100 * v / total);
    const pisos = exactos.map(Math.floor);
    let faltan = 100 - pisos.reduce((s, v) => s + v, 0);
    exactos.map((e, i) => [e - pisos[i], i])
      .sort((a, b) => b[0] - a[0] || a[1] - b[1])
      .forEach(([, i]) => { if (faltan > 0){ pisos[i] += 1; faltan -= 1; } });
    return pisos;
  }

  function coberturaDe(casos){
    return {incumplidas: casos.length,
            completas: casos.filter(c => c.motivo && c.responsable).length,
            sinMotivo: casos.filter(c => !c.motivo).length,
            sinResponsable: casos.filter(c => !c.responsable).length,
            m3Incompletos: casos.filter(c => !(c.motivo && c.responsable)).reduce((s, c) => s + c.m3, 0)};
  }

  const pesoDe = (orden) => orden === 'm3' ? (c => c.m3) : (() => 1);

  function paretoDeMotivos(dias, {planta = null, orden = 'entregas', responsable = null} = {}){
    const todos = casosDeIncumplimiento(dias, planta);
    const casos = todos.filter(c => c.motivo && c.responsable
                                    && (!responsable || c.responsable === responsable));
    const clave = orden === 'm3' ? 'm3' : 'entregas', peso = pesoDe(clave);
    const por = new Map();
    casos.forEach(c => {
      if (!por.has(c.motivo)) por.set(c.motivo, {motivo: c.motivo, entregas: 0, m3: 0, porResponsable: {}});
      const m = por.get(c.motivo);
      m.entregas += 1; m.m3 += c.m3;
      m.porResponsable[c.responsable] = (m.porResponsable[c.responsable] || 0) + 1;
    });
    const ordenados = [...por.values()]
      .sort((a, b) => b[clave] - a[clave] || b.entregas - a.entregas || a.motivo.localeCompare(b.motivo));
    const pcts = porcentajesQueSuman100(ordenados.map(m => m[clave]));
    // el acumulado es la suma de los % mostrados, asi la ultima fila da 100
    let acum = 0;
    const motivos = ordenados.map((m, i) => { acum += pcts[i]; return {...m, pct: pcts[i], pctAcumulado: acum}; });
    return {motivos, orden: clave, responsable, cobertura: coberturaDe(todos)};
  }

  // Los tres circulos: VMO, Cliente y Externo, cada uno con su reparto de
  // motivos. Llevan color propio los `top` motivos que mas pesan en el TOTAL
  // y ademas los `porCirculo` principales de CADA responsable, hasta `max`
  // (los 8 colores de la paleta validada); el resto va como "Otros". Los dos
  // criterios juntos porque con solo el total, un responsable cuyos motivos
  // son chicos en el total quedaba con el circulo entero en gris — justo lo
  // que se queria ver. La lista es una sola para los tres circulos, asi un
  // motivo tiene el mismo color en todos.
  function motivosPorResponsable(dias, {planta = null, orden = 'entregas', top = 5,
                                        porCirculo = 2, max = 8} = {}){
    const todos = casosDeIncumplimiento(dias, planta);
    const casos = todos.filter(c => c.motivo && c.responsable);
    const clave = orden === 'm3' ? 'm3' : 'entregas', peso = pesoDe(clave);
    const global = paretoDeMotivos(dias, {planta, orden: clave}).motivos.map(m => m.motivo);
    const principales = new Set(global.slice(0, top));
    RESPONSABLES.forEach(quien => paretoDeMotivos(dias, {planta, orden: clave, responsable: quien})
      .motivos.slice(0, porCirculo).forEach(m => principales.add(m.motivo)));
    // en el orden del total, para que los colores vayan del que mas pesa al que menos
    const destacados = global.filter(m => principales.has(m)).slice(0, max);
    const total = casos.reduce((s, c) => s + peso(c), 0);
    // `todos` es el mismo calculo sobre todos los casos: el circulo cuando no
    // hay un responsable elegido.
    const armar = (quien, suyos) => {
      const valor = suyos.reduce((s, c) => s + peso(c), 0);
      const porMotivo = new Map();
      suyos.forEach(c => porMotivo.set(c.motivo, (porMotivo.get(c.motivo) || 0) + peso(c)));
      const segmentos = destacados.map(m => ({motivo: m, valor: porMotivo.get(m) || 0}));
      const otros = [...porMotivo].filter(([m]) => !destacados.includes(m)).reduce((s, [, v]) => s + v, 0);
      if (otros) segmentos.push({motivo: 'Otros', valor: otros});
      const conValor = segmentos.filter(g => g.valor > 0);
      const pctSeg = porcentajesQueSuman100(conValor.map(g => g.valor));
      const lista = [...porMotivo].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
      const pctMot = porcentajesQueSuman100(lista.map(([, v]) => v));
      return {
        responsable: quien, valor, casos: suyos.length, pct: 100,
        segmentos: conValor.map((g, i) => ({...g, pct: pctSeg[i]})),
        motivos: lista.map(([motivo, v], i) => ({motivo, valor: v, pct: pctMot[i]})),
      };
    };
    const responsables = RESPONSABLES.map(quien => armar(quien, casos.filter(c => c.responsable === quien)));
    // la parte de cada responsable, que suma 100 entre los tres
    const pctResp = porcentajesQueSuman100(responsables.map(r => r.valor));
    responsables.forEach((r, i) => { r.pct = total ? pctResp[i] : 0; });
    return {responsables, todos: armar('Todos', casos), destacados, orden: clave, total,
            cobertura: coberturaDe(todos)};
  }

  // ================= EXCEL DE CANCELADOS =================
  //
  // El formato del reporte de cancelados de la companera, columna por columna.
  // Lista lo NO DESPACHADO segun la propia programacion (columna Pendiente),
  // decision del usuario del 2026-10-06 — no los cruces fallidos, que son
  // otro problema. Devuelve valores planos; el HTML los vuelve celdas de Excel.
  const MESES_ES = ['ENERO','FEBRERO','MARZO','ABRIL','MAYO','JUNIO','JULIO',
                    'AGOSTO','SEPTIEMBRE','OCTUBRE','NOVIEMBRE','DICIEMBRE'];
  const ENCABEZADO_CANCELADOS = ['FECHA','SEMANAS PROGRAMADAS','HORA PROGRAMADA','CLIENTE',
    'VENDEDOR','ZONA','ELEMENTO','TIPO DE SERVICIO','PRODUCTO','VOL. PROGRAMADO','RAZON','RESPONSABLE',
    'MOTIVO'];

  function filasCancelados(noDespachadoLista, state, fecha){
    const [Y, M, D] = String(fecha).split('-').map(Number);
    // serial de Excel calculado en UTC, sin la zona horaria del navegador
    const serialFecha = Date.UTC(Y, M - 1, D) / 86400000 + 25569;
    const semana = `SEMANA ${Math.ceil(D / 7)}- ${MESES_ES[M - 1]}`;
    const obs = state.observaciones || new Map(), resp = state.responsables || new Map();
    const mot = state.motivos || new Map();
    const filas = [...noDespachadoLista]
      .sort((a, b) => (a.hora ?? 9999) - (b.hora ?? 9999))
      .map(n => ({
        fechaSerial: serialFecha,
        semana,
        // La hora del reloj, sin el dia (#170, 2026-10-23): con el +60 de
        // AJUSTE_HORA_PROGRAMADA_MIN un pedido de las 23:30 queda en 1470 min,
        // la fraccion daba 1,02 y el servidor rechazaba el reporte entero (422).
        horaFraccion: n.hora === null || n.hora === undefined ? null : (n.hora % 1440) / 1440,
        cliente: n.cliente || '',
        vendedor: n.vendedor || '',
        zona: String(n.zonaProg || '').toUpperCase(),
        elemento: n.elemento ? String(n.elemento).toUpperCase() : '',
        servicio: n.bomba && n.bomba !== 'Directo' ? 'BOMBA' : 'DIRECTO',
        producto: n.producto || '',
        volumen: n.programado || 0,
        razon: obs.get(n.rowKey) || '',
        responsable: resp.get(n.rowKey) || '',
        motivo: mot.get(n.rowKey) || '',
        // Para el Reporte de cancelados de varios dias (2026-10-12), que lleva
        // ademas la obra y los m3. El Excel de un dia no los usa.
        fecha,
        obra: n.obra || '',
        despachado: n.despachado || 0,
        pendiente: n.pendiente || 0,
      }));
    return {encabezado: ENCABEZADO_CANCELADOS, filas};
  }

  // ================= REPORTE DE CANCELADOS (2026-10-12) =================
  //
  // Lo cancelado de un rango de dias, para la pestana Reporte cancelados. Cada
  // dia pasa por filasCancelados(), la misma del Excel de un dia, asi que un
  // pedido sale igual en los dos.
  //
  // Cancelado aca es lo que NO SE DESPACHO NADA (decision del usuario, el mismo
  // 2026-10-12): un pedido con despacho parcial no entra, aunque le quede
  // pendiente. Medido sobre los 9 dias guardados: de 31 renglones con
  // pendiente, 14 eran parciales (270,5 m3). Solo en este reporte: el Excel de
  // cancelados de un dia y el panel "No despachado" siguen con todo lo
  // pendiente.
  //
  // "Nada" es pendiente igual a lo programado, y no solo despachado en 0: un
  // dia guardado sin la columna Despachado la trae vacia, y vacio no es cero.
  //
  // Y "nada" tambien es que el cruce no le haya asignado ningun camion. La
  // columna Despachado de la programacion no siempre se actualiza: el 08-10
  // THE ONE CAP CANA salia con 300 m3 cancelados y tenia 27 camiones (261 m3)
  // cruzados. En los 13 dias guardados al 2026-10-16, 22 de los 35 renglones
  // del reporte tenian camiones. El cruce es lo que de verdad salio de planta.
  //
  // `dias` es [{fecha, state, assumptions}] de restaurarDia() — o sea ya sin
  // Macao ni clientes internos (Macao viene aparte, ver canceladosMacao). Sin
  // `assumptions` o sin cargues no hay cruce y queda solo la columna. Como no se despacho nada, los m3 cancelados son
  // los programados.
  const SIN_MOTIVO = 'Sin motivo', SIN_RESPONSABLE = 'Sin responsable', SIN_CLIENTE = 'Sin cliente';
  const noSeDespachoNada = n => !(n.despachado > 0) && n.pendiente >= n.programado;
  // Las claves de la programacion (noDespachado) que recibieron al menos un
  // camion en el cruce. Con la obra programada y no la real, que es la que
  // usa noDespachado: un override de obra no la cambia.
  function filasConCamiones(state, assumptions){
    if (!assumptions || !(state.cargue || []).length) return new Set();
    return new Set(computeCumplimiento(state, assumptions).results
      .filter(r => r.cargues > 0)
      .map(r => claveFila(r.cliente, r.obraProg, r.bomba, r.elemento, r.horaProg)));
  }
  // Macao entra a este reporte y a ningun otro (decision del usuario,
  // 2026-11-03: todo Macao, no solo MACAO II). Su columna Despachado se
  // actualiza menos todavia: 131 de los 261 renglones de Macao de octubre
  // venian en 0, y la LOSA M2 del 20/10 entre ellos con 540 m3 cargados. Y el
  // cruce solo no alcanza: un vaciado grande va en dos renglones, uno por
  // bomba, y el cruce le da todos los camiones a uno; ese dia salian 320 m3
  // cancelados de esa losa. Por eso un pedido de Macao es cancelado solo si
  // ademas ningun camion de ese cliente fue ese dia al mismo elemento de la
  // misma obra. La obra cambia de nombre entre la programacion y el cargue
  // ("MALESPIN..." / "MALESPIN MACAO II", "CONCAVA1" / "CONCAVA", "CEDIS MACAO
  // II GOBAMEX" / "MOON PALACE GOBAMEX"): es la misma si comparten una palabra
  // de 4 letras o mas, sin los numeros del final.
  const raicesObra = obra => normalize(obra).split(' ').map(w => w.replace(/\d+$/, ''))
    .filter(w => w.length >= 4 && w !== 'OBRA');
  function fueCamionMacao(cargue, n){
    const raices = raicesObra(n.obra);
    return cargue.some(c => normalize(c.cliente) === normalize(n.cliente)
      && normalize(c.elemento) === normalize(n.elemento)
      && raicesObra(c.obra).some(w => raices.includes(w)));
  }
  function canceladosMacao(d){
    const prog = d.state.programacionMacao || [];
    if (!prog.length) return [];
    const cargue = d.state.cargueMacao || [];
    const conCamiones = filasConCamiones({...d.state, programacion: prog, cargue}, d.assumptions);
    return noDespachado(prog).filter(n => noSeDespachoNada(n) && !conCamiones.has(n.rowKey)
      && !fueCamionMacao(cargue, n));
  }
  function reporteCancelados(dias){
    const ordenados = [...dias].sort((a, b) => a.fecha.localeCompare(b.fecha));
    const filas = ordenados.flatMap(d => {
      const conCamiones = filasConCamiones(d.state, d.assumptions);
      return filasCancelados([...noDespachado(d.state.programacion)
        .filter(n => noSeDespachoNada(n) && !conCamiones.has(n.rowKey)), ...canceladosMacao(d)], d.state, d.fecha).filas;
    });
    const m3 = lista => lista.reduce((s, f) => s + (f.volumen || 0), 0);
    // Agrupa y ordena por m3; lo que falta cargar va al final aunque pese
    // mas, porque no es una categoria sino un dato que falta.
    const agrupar = (campo, vacio) => {
      const por = new Map();
      filas.forEach(f => {
        const k = f[campo] || vacio;
        if (!por.has(k)) por.set(k, {nombre: k, entregas: 0, m3Cancelado: 0});
        const g = por.get(k);
        g.entregas++; g.m3Cancelado += f.volumen || 0;
      });
      const grupos = [...por.values()].sort((a, b) => (a.nombre === vacio) - (b.nombre === vacio)
        || b.m3Cancelado - a.m3Cancelado || a.nombre.localeCompare(b.nombre));
      const pcts = porcentajesQueSuman100(grupos.map(g => g.m3Cancelado));
      grupos.forEach((g, i) => { g.pct = pcts[i]; });
      return grupos;
    };
    return {
      encabezado: ['FECHA', 'SEMANAS PROGRAMADAS', 'HORA PROGRAMADA', 'CLIENTE', 'OBRA', 'VENDEDOR',
                   'ZONA', 'ELEMENTO', 'TIPO DE SERVICIO', 'PRODUCTO', 'VOL. PROGRAMADO',
                   'RAZON', 'RESPONSABLE', 'MOTIVO'],
      filas,
      resumen: {
        diasRevisados: ordenados.length,
        diasConCancelados: new Set(filas.map(f => f.fecha)).size,
        entregas: filas.length,
        m3Cancelado: m3(filas),
        // Todos los dias del rango, tambien los que no cancelaron nada: un dia
        // sin renglon se leeria como un dia que no se reviso.
        porDia: ordenados.map(d => {
          const delDia = filas.filter(f => f.fecha === d.fecha);
          return {fecha: d.fecha, entregas: delDia.length, m3Cancelado: m3(delDia)};
        }),
        porMotivo: agrupar('motivo', SIN_MOTIVO),
        porResponsable: agrupar('responsable', SIN_RESPONSABLE),
      },
    };
  }

  // ================= IMAGEN DE CUMPLIMIENTO =================
  //
  // Los datos de la imagen que se manda por WhatsApp: los incumplidos, del mas
  // tarde al menos tarde, con las columnas de la version de la companera
  // (incluida Bomba, que agrego en la v17 (11)). Los KPIs NO son su conteo de
  // pedidos: son los de resumenDeCumplimiento, los mismos que la pantalla, por
  // m3 y por entrega — la imagen no puede decir un numero distinto al tablero.
  function filasImagenCumplimiento(rows, state){
    const obs = state.observaciones || new Map(), resp = state.responsables || new Map();
    const mot = state.motivos || new Map();
    // En el orden por tipo de elemento, como la tabla (2026-10-08); dentro de
    // cada tipo, el mas atrasado primero.
    const incumplidos = ordenarPorElemento(rows).filter(r => r.estado === 'Incumplido');
    return {
      resumen: resumenDeCumplimiento(rows),
      incumplidos: incumplidos.map(r => [
        r.cliente, r.obraReal || r.obraProg || '—', r.bomba || 'Directo', r.elemento || '—',
        fmtInt(r.cantProg), minToStr(r.horaProg), minToStr(r.horaLlegadaEst), fmtDiff(r.diff),
        resp.get(r.rowKey) || '—', mot.get(r.rowKey) || '—', obs.get(r.rowKey) || '',
      ]),
    };
  }

  // ================= REPORTE DEL DIA (2026-10-15) =================
  //
  // La estadistica de un solo dia, para el PDF de la pestana Reporte del dia.
  // Sale de computeCumplimiento() como todo lo demas: el navegador arma los
  // numeros y el servidor solo los dibuja. Los bloques usan los mismos filtros
  // que Estadisticas (zona por planta, Bomba/Directo por la programacion), asi
  // que un numero del PDF es el mismo que en pantalla.
  function bloqueDelReporte(nombre, rows, cargue){
    const r = resumenDeCumplimiento(rows);
    return {nombre, pct: r.pct, pctPedidos: r.pctPedidos, pedidos: r.pedidos,
            pedidosCumplidos: r.pedidosCumplidos, m3: r.m3, m3Cumplidos: r.m3Cumplidos,
            incumplidos: rows.filter(x => x.estado === 'Incumplido').length,
            m3Despachado: cargue.reduce((s, c) => s + (c.cantidad || 0), 0),
            cargues: cargue.length,
            camiones: new Set(cargue.map(c => c.ficha).filter(Boolean)).size};
  }

  // Incumplidos agrupados por una clave (motivo, responsable o cliente). Lo
  // que no tiene va como "Sin motivo" / "Sin responsable" y al final, como en
  // Cancelados. `detalle` es el desglose de cada grupo por otra clave
  // ("Cliente 2, VMO 1"): por responsable en los motivos, por motivo en los
  // clientes.
  // Para la tabla de companias (#171, 2026-10-23), `opciones`:
  //  - `sinDesglose`: como se llama un caso sin desglose. Sin esto una compania
  //    con 2 incumplidas mostraba "TARDANZA DE BOMBA 1" y no se veia que la otra
  //    no tenia motivo.
  //  - `pctPorSeparado`: cada % redondeado por su lado. Con el reparto que suma
  //    100, de 43 companias con 1 incumplida unas salian con 2% y otras con 3%;
  //    en una lista larga de iguales importa mas que iguales digan lo mismo.
  function agruparIncumplidos(casos, clave, sinNombre, desglose = 'responsable', opciones = {}){
    const por = new Map();
    casos.forEach(c => {
      const nombre = c[clave] || sinNombre;
      if (!por.has(nombre)) por.set(nombre, {nombre, entregas: 0, m3: 0, detalle: {}});
      const g = por.get(nombre);
      g.entregas += 1; g.m3 += c.m3;
      const parte = c[desglose] || opciones.sinDesglose;
      if (parte) g.detalle[parte] = (g.detalle[parte] || 0) + 1;
    });
    const lista = [...por.values()].sort((a, b) =>
      (a.nombre === sinNombre) - (b.nombre === sinNombre)
      || b.entregas - a.entregas || b.m3 - a.m3 || a.nombre.localeCompare(b.nombre));
    const total = lista.reduce((t, g) => t + g.entregas, 0);
    const pcts = opciones.pctPorSeparado
      ? lista.map(g => total ? Math.round(g.entregas / total * 100) : 0)
      : porcentajesQueSuman100(lista.map(g => g.entregas));
    // Con `pctPorSeparado` el acumulado sale de las entregas, no de sumar
    // redondeos: sumados pasaban de 100 y el servidor rechazaba el PDF.
    let acum = 0, acumEntregas = 0;
    return lista.map((g, i) => {
      acum += pcts[i]; acumEntregas += g.entregas;
      const pctAcumulado = opciones.pctPorSeparado ? Math.round(acumEntregas / total * 100) : acum;
      return {nombre: g.nombre, entregas: g.entregas, m3: g.m3, pct: pcts[i], pctAcumulado,
              detalle: Object.entries(g.detalle).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
                .map(([quien, n]) => `${quien} ${n}`).join(', ')};
    });
  }

  // Desde el 2026-10-21 tambien de un rango de fechas (pedido del usuario): de
  // fecha x a fecha y, o solo el ultimo dia. `dias` es [{fecha, state,
  // assumptions}] de restaurarDia(). Los porcentajes del rango juntan todas las
  // entregas y dividen una vez, como acumuladoDeCumplimiento — no promedian
  // los porcentajes diarios. Cada dia se calcula con SUS supuestos.
  function bloquesDelReporte(results, cargue){
    const zona = z => PREFIJO_ZONA + z;
    return [
      bloqueDelReporte('General', results, cargue),
      ...ZONAS.map(z => bloqueDelReporte(z, results.filter(r => filaDelFiltro(r, zona(z))),
                                         cargue.filter(c => filaDelFiltro(c, zona(z))))),
      // Con un servicio el despacho sale de los camiones de esas entregas,
      // igual que en Comparacion: el cargue no dice si fue con bomba.
      ...SERVICIOS.map(s => {
        const rows = filtrarPorServicio(results, s);
        return bloqueDelReporte(NOMBRE_SERVICIO[s], rows, rows.flatMap(r => r.matchRows || []));
      }),
    ];
  }

  // Responsables con pagina propia en el reporte, en este orden.
  const RESPONSABLES_DEL_REPORTE = ['Cliente', 'VMO'];
  function incumplidasPorResponsable(casos){
    return RESPONSABLES_DEL_REPORTE.map(responsable => {
      const suyos = casos.filter(c => c.responsable === responsable);
      const servicios = SERVICIOS.map(s => {
        const del = suyos.filter(c => c.servicio === s);
        return {servicio: NOMBRE_SERVICIO[s], entregas: del.length,
                m3: del.reduce((t, c) => t + c.m3, 0),
                companias: agruparIncumplidos(del, 'cliente', SIN_CLIENTE, 'motivo',
                                              {sinDesglose: SIN_MOTIVO, pctPorSeparado: true})};
      }).filter(s => s.entregas);
      return {responsable, entregas: suyos.length, servicios};
    }).filter(r => r.entregas);
  }

  function reporteDelPeriodo(dias){
    const calculados = [...dias].sort((a, b) => a.fecha.localeCompare(b.fecha)).map(d => {
      const {results} = computeCumplimiento(d.state, d.assumptions);
      return {...d, results, cargue: cargueConZona(d.state.cargue, d.assumptions.zonaPlanta),
              resp: d.state.responsables || new Map(), mot: d.state.motivos || new Map()};
    });
    const results = calculados.flatMap(d => d.results);
    const cargue = calculados.flatMap(d => d.cargue);
    const noEvaluables = Object.entries(results.reduce((acc, r) => {
      if (r.estado !== 'Cumplido' && r.estado !== 'Incumplido') acc[r.estado] = (acc[r.estado] || 0) + 1;
      return acc;
    }, {})).map(([estado, entregas]) => ({estado, entregas}));
    const casos = calculados.flatMap(d => d.results.filter(r => r.estado === 'Incumplido')
      .map(r => ({m3: r.cantReal || 0, motivo: d.mot.get(r.rowKey) || null,
                  responsable: d.resp.get(r.rowKey) || null, cliente: r.cliente || null,
                  servicio: servicioDeFila(r)})));
    const entregas = calculados.flatMap(d => ordenarParaTablaDelDia(d.results).map(r => ({
      fecha: d.fecha,
      cliente: r.cliente || '', obra: r.obraReal || r.obraProg || '', elemento: r.elemento || '',
      servicio: servicioDeFila(r) ? NOMBRE_SERVICIO[servicioDeFila(r)] : '',
      horaProg: r.horaProg ?? null, cantProg: r.cantProg || 0, cantReal: r.cantReal || 0,
      cargues: r.cargues || 0, primerCargue: r.horaCargue ?? null, planta: r.planta || '',
      zona: zonaDeFila(r) || '', llegada: r.horaLlegadaEst ?? null, diff: r.diff ?? null,
      estado: estadoVisible(r), responsable: d.resp.get(r.rowKey) || '', motivo: d.mot.get(r.rowKey) || '',
      observacion: r.observacion || '',
    })));
    // Un supuesto que cambio entre dias va en null y en `varian`: el PDF dice
    // "varía" en vez de mostrar el de un solo dia como si fuera de todos.
    const supuestos = {ajusteHora: AJUSTE_HORA_PROGRAMADA_MIN}, varian = [];
    ['cargue', 'calidad', 'tolerancia'].forEach(k => {
      const valores = new Set(calculados.map(d => d.assumptions[k] ?? null));
      if (valores.size > 1) varian.push(k);
      supuestos[k] = valores.size === 1 ? [...valores][0] : null;
    });
    supuestos.varian = varian;
    // Camiones es el promedio de las fichas distintas de cada dia (pedido
    // del usuario, 2026-10-21): contar fichas distintas en todo el rango
    // decia cuantos camiones distintos se usaron, no cuantos salen por dia.
    // En un dia el promedio es el mismo numero de siempre.
    const bloques = bloquesDelReporte(results, cargue);
    const bloquesPorDia = calculados.map(d => bloquesDelReporte(d.results, d.cargue));
    bloques.forEach((b, i) => {
      const suma = bloquesPorDia.reduce((s, dia) => s + dia[i].camiones, 0);
      b.camiones = calculados.length ? Math.round(suma / calculados.length * 10) / 10 : 0;
    });
    return {
      desde: calculados.length ? calculados[0].fecha : null,
      hasta: calculados.length ? calculados[calculados.length - 1].fecha : null,
      supuestos,
      nombres: {pct: NOMBRE_PCT, pctPedidos: NOMBRE_PCT_PEDIDOS},
      bloques,
      porDia: calculados.map(d => bloqueDelReporte(d.fecha, d.results, d.cargue)),
      noEvaluables,
      porResponsable: agruparIncumplidos(casos, 'responsable', SIN_RESPONSABLE),
      porMotivo: agruparIncumplidos(casos, 'motivo', SIN_MOTIVO),
      // Las incumplidas del cliente y las de VMO, cada una partida en Con
      // bomba y Directo y por compania, con sus motivos (pedido del usuario:
      // el cliente el 2026-10-21; VMO y el servicio el 2026-10-22).
      incumplidasPorResponsable: incumplidasPorResponsable(casos),
      cobertura: {incumplidos: casos.length, sinMotivo: casos.filter(c => !c.motivo).length,
                  sinResponsable: casos.filter(c => !c.responsable).length},
      entregas,
    };
  }

  function reporteDelDia(state, assumptions){
    return reporteDelPeriodo([{fecha: state.fecha, state, assumptions}]);
  }

  // ================= INDICADORES (2026-10-28) =================
  //
  // La pagina Indicadores, aprobada con boceto por Axel y la ingeniera:
  //  1. Metros bombeados por equipo: el reporte "Metros bombeados por equipo"
  //     del sistema, tal cual (Macao incluido).
  //  2. Metros transportados por camion: el Excel de cargue de cada dia, con
  //     los viajes de Macao.
  //  3. Cumplimiento de tiempos de despacho: el reporte del sistema del mismo
  //     nombre, sin MACAO II.
  // Todo va separado por zona. Los dos reportes se suben por rango de fechas;
  // aca se leen y se calculan, el servidor solo los guarda.

  const ZONA_SIN = 'Sin zona';
  // Una fecha de un encabezado o celda del sistema: "10/01/2026" (mes/dia),
  // un serial de Excel o un Date.
  function fechaDeCelda(v){
    if (v === null || v === undefined || v === '') return null;
    if (typeof v === 'number') return excelSerialToFechaStr(v);
    if (v instanceof Date) return `${v.getUTCFullYear()}-${String(v.getUTCMonth() + 1).padStart(2, '0')}-${String(v.getUTCDate()).padStart(2, '0')}`;
    const m = String(v).trim().match(/^(\d{1,2})\/(\d{1,2})\/(\d{2}|\d{4})\b/);
    if (!m) return null;
    const y = m[3].length === 2 ? 2000 + Number(m[3]) : Number(m[3]);
    return `${y}-${m[1].padStart(2, '0')}-${m[2].padStart(2, '0')}`;
  }
  const numeroDe = v => { const n = typeof v === 'number' ? v : parseFloat(String(v ?? '').replace(/,/g, '')); return isNaN(n) ? null : n; };
  const textoDe = v => v === null || v === undefined || String(v).trim() === '' ? null : String(v).trim();
  const rangoDe = fechas => fechas.length ? {desde: fechas.reduce((a, b) => a < b ? a : b), hasta: fechas.reduce((a, b) => a > b ? a : b)} : null;

  // "Metros bombeados por equipo": una fila por equipo, una columna por dia.
  // El rango es el de las columnas de fecha (aunque algun dia venga vacio:
  // subir el reporte de nuevo tiene que poder borrar un dia que quedo en 0).
  function parseBombeoSheets(hojas){
    for (const {rows} of hojas){
      const h = findHeaderRowIndex(rows, ['IDEQUIPO']);
      if (h === -1) continue;
      const header = rows[h];
      const iId = colIndex(header, ['idEquipo']), iNombre = colIndex(header, ['Equipo']);
      const fechas = header.map(fechaDeCelda);
      const columnas = fechas.map((f, i) => f ? i : -1).filter(i => i >= 0);
      if (iId < 0 || !columnas.length) continue;
      const filas = [];
      for (let r = h + 1; r < rows.length; r++){
        const row = rows[r] || [], equipo = textoDe(row[iId]);
        if (!equipo) continue;   // la fila de totales viene sin equipo
        columnas.forEach(i => { const m3 = numeroDe(row[i]);
          if (m3) filas.push({fecha: fechas[i], equipo, nombre: iNombre >= 0 ? textoDe(row[iNombre]) : null, m3}); });
      }
      return {...rangoDe(columnas.map(i => fechas[i])), filas};
    }
    return null;
  }

  // "Cumplimiento de tiempos de despacho": un renglon por pedido. Una hora
  // en 00:00 es que el sistema no la tiene (la celda trae solo la fecha).
  function parseTiemposSheets(hojas){
    const hora = v => { const m = excelTimeToMinutes(v); return m ? m : null; };
    for (const {rows} of hojas){
      const h = findHeaderRowIndex(rows, ['ORDCOMP']);
      if (h === -1) continue;
      const H = rows[h], c = nombres => colIndex(H, nombres);
      const i = {ord: c(['OrdComp']), planta: c(['Planta']), cliente: c(['Cliente']), fecha: c(['Fecha']),
                 hora: c(['Hora']), fin: c(['HoraFin']), cant: c(['Cantidad']), tin: c(['Total In']),
                 logro: c(['Logro']), desp: c(['TotalDespachado']), vprog: c(['ViajesProgramados']),
                 vef: c(['ViajesEfectuados']), bomba: c(['Bomba'])};
      if ([i.fecha, i.cant, i.tin, i.desp, i.vef].some(x => x < 0)) continue;
      const filas = [];
      for (let r = h + 1; r < rows.length; r++){
        const row = rows[r] || [], fecha = fechaDeCelda(row[i.fecha]);
        if (!fecha) continue;
        filas.push({fecha, ordComp: i.ord >= 0 ? textoDe(row[i.ord]) : null,
                    planta: i.planta >= 0 ? textoDe(row[i.planta]) : null, cliente: i.cliente >= 0 ? textoDe(row[i.cliente]) : null,
                    horaIni: i.hora >= 0 ? hora(row[i.hora]) : null, horaFin: i.fin >= 0 ? hora(row[i.fin]) : null,
                    cantidad: numeroDe(row[i.cant]) || 0, totalIn: numeroDe(row[i.tin]) || 0,
                    logro: i.logro >= 0 ? textoDe(row[i.logro]) : null, totalDespachado: numeroDe(row[i.desp]) || 0,
                    viajesProgramados: i.vprog >= 0 ? numeroDe(row[i.vprog]) : null, viajesEfectuados: numeroDe(row[i.vef]) || 0,
                    bomba: i.bomba >= 0 ? textoDe(row[i.bomba]) : null});
      }
      return {...rangoDe(filas.map(f => f.fecha)), filas};
    }
    return null;
  }

  // Las filas de logistica_tiempo_pedido como las devuelve el servidor
  // (snake_case) a la forma de parseTiemposSheets.
  const tiempoDeServidor = f => ({fecha: f.fecha, ordComp: f.ord_comp, planta: f.planta, cliente: f.cliente,
    horaIni: f.hora_ini, horaFin: f.hora_fin, cantidad: f.cantidad, totalIn: f.total_in, logro: f.logro,
    totalDespachado: f.total_despachado, viajesProgramados: f.viajes_programados,
    viajesEfectuados: f.viajes_efectuados, bomba: f.bomba});

  function medianaDe(valores){
    if (!valores.length) return null;
    const s = [...valores].sort((a, b) => a - b), m = Math.floor(s.length / 2);
    return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
  }
  const sumaDe = (filas, f) => filas.reduce((t, x) => t + (f(x) || 0), 0);
  const masPesado = mapa => [...mapa].sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0])))[0]?.[0] ?? null;
  const sumarEn = (mapa, k, v) => mapa.set(k, (mapa.get(k) || 0) + v);
  const digitosDe = v => String(v ?? '').replace(/\D/g, '');
  const ZONAS_INDICADORES = [...ZONAS, ZONA_SIN];
  const porZona = (lista, zonaDe, armar) => ZONAS_INDICADORES
    .map(zona => ({zona, ...armar(lista.filter(x => zonaDe(x) === zona))}))
    .filter(z => z.zona !== ZONA_SIN || z.n);

  // 3. Cumplimiento de tiempos: m3 cargados antes de la Hora Fin ("Total In",
  // del sistema) / m3 programados. Entran los pedidos con algun viaje y con
  // Hora Fin; sin Hora Fin y sin viajes van aparte (el sistema los cuenta como
  // 0%). Un grupo con Hora Fin en menos de la mitad de sus pedidos con viaje
  // es "Sin dato": Movil IV salia con 100% por 1 pedido de 122.
  const esMacaoII = cliente => /\bMACAO II\b/.test(normalize(cliente));
  const tieneHoraFin = r => r.horaIni !== null && r.horaIni !== undefined && r.horaFin !== null && r.horaFin !== undefined && r.horaFin > r.horaIni;
  function estadisticaDeTiempos(conViaje){
    const ev = conViaje.filter(tieneHoraFin), prog = sumaDe(ev, r => r.cantidad), aTiempo = sumaDe(ev, r => r.totalIn);
    const sin = conViaje.length - ev.length;
    return {n: ev.length, sin, prog, aTiempo, logro: ev.filter(r => normalize(r.logro) === 'SI').length,
            pct: prog ? 100 * aTiempo / prog : null, hayDato: conViaje.length > 0 && ev.length / conViaje.length >= 0.5};
  }
  function cumplimientoDeTiempos(filas){
    const todas = filas.filter(r => !esMacaoII(r.cliente)).map(r => ({...r, zona: zonaDePlanta(r.planta) || ZONA_SIN}));
    const conViaje = todas.filter(r => r.viajesEfectuados > 0);
    const agrupar = (rs, k) => [...groupBy(rs, r => r[k] || '—')].map(([nombre, g]) => ({nombre, ...estadisticaDeTiempos(g)}));
    return {
      ...estadisticaDeTiempos(conViaje),
      sinViajes: todas.length - conViaje.length,
      zonas: porZona(conViaje, r => r.zona, rs => ({...estadisticaDeTiempos(rs),
        plantas: agrupar(rs, 'planta').sort((a, b) => b.prog - a.prog || b.sin - a.sin || a.nombre.localeCompare(b.nombre)),
        clientes: agrupar(rs, 'cliente').filter(c => c.n).sort((a, b) => b.prog - a.prog || a.nombre.localeCompare(b.nombre)),
        dias: agrupar(rs, 'fecha').sort((a, b) => a.nombre.localeCompare(b.nombre))})),
    };
  }

  // 1. Bombeo: tal cual el reporte. La zona de cada equipo sale del reporte
  // de tiempos del mismo rango: la de las plantas donde hizo pedidos (la que
  // suma mas m3). En octubre 2026 cada bomba trabajo en una sola zona.
  function bombeoPorEquipo(filas, tiempos){
    const zonas = new Map();
    tiempos.filter(r => r.totalDespachado > 0 && digitosDe(r.bomba) && zonaDePlanta(r.planta)).forEach(r => {
      const b = digitosDe(r.bomba); if (!zonas.has(b)) zonas.set(b, new Map());
      sumarEn(zonas.get(b), zonaDePlanta(r.planta), r.totalDespachado); });
    const equipos = [...groupBy(filas, f => f.equipo)].map(([equipo, fs]) => {
      const m3 = sumaDe(fs, f => f.m3), dias = new Set(fs.map(f => f.fecha)).size;
      return {equipo, nombre: fs.find(f => f.nombre)?.nombre || null, m3, dias, m3PorDia: m3 / dias,
              celdas: fs.map(f => f.m3), zona: zonas.has(digitosDe(equipo)) ? masPesado(zonas.get(digitosDe(equipo))) : ZONA_SIN};
    }).sort((a, b) => b.m3 - a.m3 || a.equipo.localeCompare(b.equipo));
    const resumen = es => ({n: es.length, m3: sumaDe(es, e => e.m3), mediana: medianaDe(es.flatMap(e => e.celdas)), equipos: es});
    return {...resumen(equipos), zonas: porZona(equipos, e => e.zona, resumen)};
  }

  // 2. Camiones: por ficha, m3 / dias trabajados y viajes / dias trabajados.
  // La zona y su total son la suma de la columna de cada camion / cantidad de
  // camiones (pedido de la ingeniera, 2026-10-28). Cada camion va en la zona
  // donde hizo mas viajes; la zona de un viaje es la de su planta en los
  // supuestos del dia. Sin "Carga Vacia" ni VMO CONCRETOS (ya fuera del cargue).
  function transportePorCamion(dias){
    const cam = new Map();
    dias.forEach(d => [...(d.state.cargue || []), ...(d.state.cargueMacao || [])].forEach(c => {
      const ficha = String(c.ficha || '').trim(); if (!ficha) return;
      if (!cam.has(ficha)) cam.set(ficha, {ficha, m3: 0, viajes: 0, dias: new Set(), plantas: new Map(), zonas: new Map(), macao: 0});
      const k = cam.get(ficha), zona = (d.assumptions.zonaPlanta || {})[c.planta] || zonaDePlanta(c.planta) || ZONA_SIN;
      k.m3 += c.cantidad || 0; k.viajes++; k.dias.add(d.fecha);
      sumarEn(k.plantas, c.planta || SIN_PLANTA, 1); sumarEn(k.zonas, zona, 1);
      if (esMacao(c.cliente, c.obra)) k.macao++;
    }));
    const camiones = [...cam.values()].map(k => ({ficha: k.ficha, zona: masPesado(k.zonas), planta: masPesado(k.plantas),
      plantas: [...k.plantas.keys()].sort(), m3: k.m3, viajes: k.viajes, dias: k.dias.size, macao: k.macao,
      m3PorDia: k.m3 / k.dias.size, m3PorViaje: k.m3 / k.viajes, viajesPorDia: k.viajes / k.dias.size,
      otraZona: k.viajes - Math.max(...k.zonas.values())}))
      .sort((a, b) => b.m3 - a.m3 || a.ficha.localeCompare(b.ficha));
    const resumen = cs => ({n: cs.length, m3: sumaDe(cs, c => c.m3), viajes: sumaDe(cs, c => c.viajes),
      sumaM3PorDia: sumaDe(cs, c => c.m3PorDia), sumaViajesPorDia: sumaDe(cs, c => c.viajesPorDia),
      m3PorCamionDia: cs.length ? sumaDe(cs, c => c.m3PorDia) / cs.length : null,
      viajesPorCamionDia: cs.length ? sumaDe(cs, c => c.viajesPorDia) / cs.length : null, camiones: cs});
    return {...resumen(camiones), viajesMacao: sumaDe(camiones, c => c.macao), dias: dias.length,
            zonas: porZona(camiones, c => c.zona, resumen)};
  }

  // `dias`: [{fecha, state, assumptions}] de restaurarDia(), ya del rango.
  // `reportes`: {bombeo, tiempos} con las filas del servidor en el rango.
  function indicadoresDelPeriodo(dias, reportes = {}){
    const tiempos = (reportes.tiempos || []).map(f => 'ord_comp' in f ? tiempoDeServidor(f) : f);
    return {bombeo: bombeoPorEquipo(reportes.bombeo || [], tiempos),
            camiones: transportePorCamion(dias),
            tiempos: cumplimientoDeTiempos(tiempos)};
  }

  const api = {
    normalize, excelTimeToMinutes, excelSerialToFechaStr, minToStr, fmtDiff, fmtInt,
    normalizarBomba, AJUSTE_HORA_PROGRAMADA_MIN, claveFila, repartirPorGrupo,
    findHeaderRowIndex, colIndex,
    parseProgramacionSheets, parseProgramacionMacao, parseCargueSheets, esProductoQueCuenta, esClienteInterno, esMacao,
    tipoDeElemento, cumplimientoPorElemento, ordenarPorElemento, ordenarParaTablaDelDia,
    obraScore, groupBy, computeCumplimiento, computeResumen,
    pedidosPorHora, repartirCamiones, noDespachado,
    payloadDelDia, restaurarDia, esCumplidoManual, estadoVisible,
    resumenDeCumplimiento, cumplimientoPorPlanta, serieDeCumplimiento,
    acumuladoDeCumplimiento, plantasOatYDelDia,
    plantasDelHistorial, filtrarDiasPorPlanta, entregasDePlanta, SIN_PLANTA,
    ZONAS, PREFIJO_ZONA, zonaDePlanta, zonaDeFila, cargueConZona, filaDelFiltro, comparacionPorDia,
    SERVICIOS, NOMBRE_SERVICIO, servicioDeFila, filtrarPorServicio, filtrarDiasPorServicio,
    NOMBRE_PCT, NOMBRE_PCT_PEDIDOS,
    ADELANTO_POR_DEFECTO, ESPACIAMIENTO_POR_DEFECTO, RESPONSABLES, MOTIVOS,
    evaluarEspaciamiento, filasCancelados, reporteCancelados, reporteDelDia, reporteDelPeriodo, indicadoresDelPeriodo, parseBombeoSheets, parseTiemposSheets, medianaDe, filasImagenCumplimiento, paretoDeMotivos, motivosPorResponsable, porcentajesQueSuman100, agruparIncumplidos, conteosDelDia,
  };

  // El navegador: las funciones quedan globales, como cuando vivian en el HTML.
  Object.assign(root, api);
  // Node: mismo archivo, importado con require() desde los tests.
  if (typeof module !== 'undefined' && module.exports) module.exports = api;

})(typeof globalThis !== 'undefined' ? globalThis : this);
