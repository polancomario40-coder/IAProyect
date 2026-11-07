// Lo que el modulo de Logistica necesita para hablar con el servidor y con el
// portal. Esta aparte de logistica.logic.js a proposito:
//
//   logistica.logic.js  = calculo puro, sin DOM ni red, probado con node
//   logistica.api.js    = fetch, localStorage e iframes, o sea el navegador
//
// Vive en su propio archivo porque lo usan las TRES paginas del modulo (el dia,
// el historial y las estadisticas) y tres copias de la misma funcion de fetch
// se separan sin que nadie lo note.

(function (root) {
  'use strict';

  function tokenDelPortal(){
    // Mismo origen que el portal, asi que su localStorage es el mismo: no hace
    // falta postMessage ni pasar el token por la URL.
    try { return localStorage.getItem('vmo_token'); } catch (e) { return null; }
  }

  function estaEmbebido(){
    // Adentro del portal el sidebar ya hace de navegacion, asi que las paginas
    // esconden sus propios enlaces entre si. Sueltas los muestran.
    try { return window.self !== window.top; } catch (e) { return true; }
  }

  async function apiLogistica(ruta, opciones = {}){
    const token = tokenDelPortal();
    if (!token){
      const err = new Error('Iniciá sesión en el portal para usar el historial.');
      err.sinToken = true;
      throw err;
    }
    const res = await fetch(ruta, {
      ...opciones,
      headers: {'Content-Type': 'application/json', 'Authorization': `Bearer ${token}`,
                ...(opciones.headers || {})},
    });
    let cuerpo = null;
    try { cuerpo = await res.json(); } catch (e) { /* sin cuerpo o no-JSON */ }
    if (!res.ok){
      const err = new Error((cuerpo && (cuerpo.detail?.detalle || cuerpo.detail)) || `Error ${res.status}`);
      err.status = res.status;
      err.cuerpo = cuerpo;
      throw err;
    }
    return cuerpo;
  }

  // Escapar TODO texto que venga de datos antes de meterlo en innerHTML o en
  // un atributo entre comillas. Cliente, obra, planta, ficha, bomba y elemento
  // salen de los Excel que se suben y quedan guardados en el servidor: una
  // celda con `<img src=x onerror=...>` se ejecutaba en el navegador de quien
  // abriera ese dia, con acceso al token del portal (auditoria de seguridad
  // 2026-10-07). Escapa las comillas tambien, asi sirve para atributos.
  function esc(v){
    return String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // Color de un porcentaje (decision de Axel, 2026-10-01): hasta 33 rojo, de
  // 33 a 66 vira suave de rojo a amarillo, y arriba de 66 verde. El viraje es
  // continuo para que una mejora de 40% a 60% se VEA. Vive aca porque lo usan
  // el dashboard del dia y las estadisticas.
  const COLOR_PCT = {ok: '#34D399', warn: '#F59E0B', err: '#F87171'};
  function colorPct(p){
    if (p === null || p === undefined) return 'var(--muted)';
    if (p <= 33) return COLOR_PCT.err;
    if (p > 66) return COLOR_PCT.ok;
    const hex = c => [1, 3, 5].map(i => parseInt(c.slice(i, i + 2), 16));
    const [a, b] = [hex(COLOR_PCT.err), hex(COLOR_PCT.warn)], t = (p - 33) / 33;
    return '#' + a.map((v, i) => Math.round(v + (b[i] - v) * t).toString(16).padStart(2, '0')).join('');
  }

  function pedirAbrirDia(fecha){
    // Desde el historial, abrir un dia en el dashboard del dia. Adentro del
    // portal se le avisa al portal, que cambia de panel; suelta, se navega.
    if (estaEmbebido()){
      window.parent.postMessage({tipo: 'logistica:abrir-dia', fecha}, window.location.origin);
    } else {
      window.location.href = '/logistica.html#dia=' + encodeURIComponent(fecha);
    }
  }

  function avisarDiaGuardado(fecha){
    // Despues de "Guardar dia", adentro del portal: el Historial y las
    // Estadisticas son otros iframes que ya cargaron su lista y no se
    // enteraban; el portal los recarga (2026-10-08). Suelta no hace falta.
    if (estaEmbebido()){
      window.parent.postMessage({tipo: 'logistica:dia-guardado', fecha}, window.location.origin);
    }
  }

  function fechaPedidaEnLaUrl(){
    // `#dia=AAAA-MM-DD` — como llega el pedido de abrir un dia puntual.
    const m = /(?:^|[#&])dia=(\d{4}-\d{2}-\d{2})/.exec(window.location.hash || '');
    return m ? m[1] : null;
  }

  Object.assign(root, {tokenDelPortal, estaEmbebido, apiLogistica, esc, colorPct, pedirAbrirDia, avisarDiaGuardado, fechaPedidaEnLaUrl});
})(typeof globalThis !== 'undefined' ? globalThis : this);
