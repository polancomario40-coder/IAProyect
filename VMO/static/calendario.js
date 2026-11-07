// Calendario de la app (2026-10-19): reemplaza el selector de fecha del
// navegador por uno propio, el mismo en todas las paginas, con el diseno
// estilo Apple que pidio el usuario adaptado a la app: rojo VMO, tema oscuro,
// semana de lunes a domingo, solo fecha (sin hora ni boton de tema).
//
// El <input type="date"> original se queda en la pagina, escondido: sigue
// siendo la fuente del valor (YYYY-MM-DD) y sigue disparando `input` y
// `change`, asi que el codigo de cada pagina no cambia. Al lado se pone un
// boton que muestra la fecha y abre el calendario. Asignar `input.value` por
// codigo tambien actualiza el boton.
//
// Se aplica solo a todo <input type="date"> que haya o que aparezca despues
// (Estimaciones los crea al vuelo). `data-sin-calendario` lo evita. Para
// limitar los dias que se pueden elegir (Reporte del dia: solo los guardados)
// VMOCalendario.mejorar(input, {permitidos: ['2026-10-16', ...]}).
//
// Los filtros Desde/Hasta del portal (Consultas, Facturas, Estimaciones)
// usan el modo rango: VMOCalendario.rango({...}), un solo calendario donde el
// primer clic es el inicio y el segundo el final.
(function (root) {
  'use strict';

  const MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
                 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
  const SEMANA = ['LUN', 'MAR', 'MIÉ', 'JUE', 'VIE', 'SÁB', 'DOM'];
  const DIAS_CORTOS = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'];

  const dos = n => String(n).padStart(2, '0');
  const aIso = (y, m, d) => `${y}-${dos(m + 1)}-${dos(d)}`;
  function leerIso(s) {
    const r = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(s || ''));
    if (!r) return null;
    const y = +r[1], m = +r[2] - 1, d = +r[3];
    const f = new Date(Date.UTC(y, m, d));
    return f.getUTCMonth() === m && f.getUTCDate() === d ? {y, m, d} : null;
  }

  // "jue 16 oct 2026": lo que muestra el boton.
  function etiquetaFecha(iso) {
    const p = leerIso(iso);
    if (!p) return '';
    const dia = DIAS_CORTOS[new Date(Date.UTC(p.y, p.m, p.d)).getUTCDay()];
    return `${dia} ${p.d} ${MESES[p.m].slice(0, 3).toLowerCase()} ${p.y}`;
  }

  // Las 42 casillas (6 semanas) de un mes, empezando en lunes; null es una
  // casilla vacia. Siempre 6 filas para que el calendario no cambie de alto.
  function celdasDelMes(y, m) {
    const primero = (new Date(Date.UTC(y, m, 1)).getUTCDay() + 6) % 7;
    const total = new Date(Date.UTC(y, m + 1, 0)).getUTCDate();
    const celdas = [];
    for (let i = 0; i < 42; i++) {
      const d = i - primero + 1;
      celdas.push(d >= 1 && d <= total ? d : null);
    }
    return celdas;
  }

  // Si un dia se puede elegir: dentro de min/max y, si hay lista, en ella.
  function sePuedeElegir(iso, {min, max, permitidos} = {}) {
    if (min && iso < min) return false;
    if (max && iso > max) return false;
    return !permitidos || permitidos.has(iso);
  }

  // Como se pinta un dia en el modo rango. Con el inicio elegido y sin final,
  // `hover` (el dia bajo el mouse) muestra el rango que quedaria.
  function claseEnRango(iso, {inicio, fin, hover} = {}) {
    if (!inicio) return [];
    const otro = fin || hover;
    const lo = otro && otro < inicio ? otro : inicio, hi = otro && otro > inicio ? otro : inicio;
    if (iso === lo || iso === hi) return lo === hi ? ['sel'] : ['sel', iso === lo ? 'ini' : 'fin'];
    if (iso > lo && iso < hi) return fin ? ['entre'] : ['entre', 'previa'];
    return [];
  }

  const api = {etiquetaFecha, celdasDelMes, sePuedeElegir, leerIso, claseEnRango};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document === 'undefined') return;

  // ================= EN LA PAGINA =================

  const CSS = `
  /* :where() deja estos valores sin peso: si la pagina ya le da estilo al
     campo (.form-input, su propio input[type=date]), gana el de la pagina. */
  :where(.cal-campo){display:flex; align-items:center; justify-content:space-between; gap:8px;
    cursor:pointer; text-align:left; font-family:inherit; font-weight:600;
    color:var(--ink, var(--text-primary, #EEF2F7));
    background:var(--elevated, var(--bg-elevated, #1C3045));}
  .cal-campo:disabled{cursor:not-allowed; opacity:.55;}
  .cal-campo .cal-vacio{color:var(--muted, var(--text-muted, rgba(238,242,247,.45))); font-weight:500;}
  .cal-campo svg{flex:none; opacity:.7;}
  .cal-pop{position:fixed; z-index:10000; width:300px; box-sizing:border-box; padding:16px;
    background:#1C3045; color:#EEF2F7; border:1px solid rgba(255,255,255,.1); border-radius:22px;
    box-shadow:0 18px 50px rgba(0,0,0,.55); font-family:Inter, system-ui, sans-serif;
    animation:cal-entra .14s ease-out;}
  @keyframes cal-entra{from{opacity:0; transform:scale(.97)} to{opacity:1; transform:none}}
  @media (prefers-reduced-motion: reduce){.cal-pop{animation:none}}
  :where(.cal-pop button){font-family:inherit; border:0; background:none; color:inherit; cursor:pointer;}
  .cal-pop button:focus-visible{outline:2px solid #F87171; outline-offset:1px;}
  .cal-cab{display:flex; align-items:center; justify-content:space-between; margin-bottom:12px;}
  .cal-titulo{display:flex; align-items:center; gap:5px; font-size:16px; font-weight:700;
    color:#F87171; padding:4px 6px; margin-left:-6px; border-radius:8px;}
  .cal-titulo:hover{background:rgba(255,255,255,.06);}
  .cal-titulo svg{transition:transform .2s;}
  .cal-titulo[aria-expanded="true"] svg{transform:rotate(180deg);}
  .cal-flechas{display:flex; gap:2px;}
  .cal-ic{width:30px; height:30px; border-radius:50%; display:flex; align-items:center;
    justify-content:center; color:#F87171;}
  .cal-ic:hover{background:rgba(255,255,255,.08);}
  .cal-semana, .cal-dias{display:grid; grid-template-columns:repeat(7, 1fr); justify-items:center;}
  .cal-semana{margin-bottom:4px;}
  .cal-semana span{font-size:10px; font-weight:700; letter-spacing:.06em; color:rgba(238,242,247,.4);}
  .cal-cuerpo{position:relative; height:228px;}
  .cal-dias{row-gap:2px;}
  .cal-dia{width:36px; height:36px; border-radius:50%; font-size:14.5px; font-weight:600;
    display:flex; align-items:center; justify-content:center; color:#EEF2F7;
    transition:background .12s, transform .12s;}
  .cal-dia:hover{background:rgba(255,255,255,.08);}
  .cal-dia.hoy{color:#F87171; box-shadow:inset 0 0 0 1.5px rgba(248,113,113,.55);}
  .cal-dia.sel{background:#D32F2F; color:#fff; box-shadow:0 3px 10px rgba(211,47,47,.45);
    transform:scale(1.04);}
  .cal-dia:disabled{color:rgba(238,242,247,.22); cursor:default; background:none;
    box-shadow:none;}
  .cal-dias.rango{column-gap:0;}
  .cal-dia.entre{width:100%; border-radius:0; background:rgba(211,47,47,.24); color:#fff;}
  .cal-dia.entre.previa{background:rgba(211,47,47,.13);}
  .cal-dia.sel.ini, .cal-dia.sel.fin{width:100%; transform:none; box-shadow:none;}
  .cal-dia.sel.ini{border-radius:18px 0 0 18px;}
  .cal-dia.sel.fin{border-radius:0 18px 18px 0;}
  .cal-meses{position:absolute; inset:0; display:flex; flex-direction:column; padding:4px 2px;
    background:#1C3045;}
  .cal-anio{display:flex; align-items:center; justify-content:space-between; padding-bottom:8px;
    margin-bottom:8px; border-bottom:1px solid rgba(255,255,255,.07); font-size:15px; font-weight:700;}
  .cal-lista-meses{display:grid; grid-template-columns:repeat(3, 1fr); gap:6px; flex:1;}
  .cal-mes{border-radius:9px; font-size:12.5px; font-weight:700;}
  .cal-mes:hover{background:rgba(255,255,255,.08);}
  .cal-mes.sel{background:#D32F2F; color:#fff;}
  .cal-pie{display:flex; justify-content:space-between; align-items:center; margin-top:10px;
    padding-top:10px; border-top:1px solid rgba(255,255,255,.07); font-size:12px; color:rgba(238,242,247,.55);}
  .cal-hoy{font-size:13px; font-weight:700; color:#F87171; padding:5px 10px; border-radius:8px;}
  .cal-hoy:hover{background:rgba(255,255,255,.08);}
  .cal-hoy:disabled{opacity:.35; cursor:default; background:none;}`;

  const svg = (d, t = 14, g = 2.5) => `<svg xmlns="http://www.w3.org/2000/svg" width="${t}" height="${t}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${g}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const IC_IZQ = svg('<path d="m15 18-6-6 6-6"/>');
  const IC_DER = svg('<path d="m9 18 6-6-6-6"/>');
  const IC_ABAJO = svg('<path d="m6 9 6 6 6-6"/>', 11, 3);
  const IC_CAL = svg('<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>', 15, 2);

  const valorNativo = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
  const hoyIso = () => { const h = new Date(); return aIso(h.getFullYear(), h.getMonth(), h.getDate()); };

  function ponerCss() {
    if (document.getElementById('vmo-cal-css')) return;
    const s = document.createElement('style');
    s.id = 'vmo-cal-css';
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  let abierto = null;   // {campo, pop, vista:{y,m}, enMeses}

  function cerrar(devolverFoco) {
    if (!abierto) return;
    const {campo, pop} = abierto;
    pop.remove();
    campo.boton.setAttribute('aria-expanded', 'false');
    abierto = null;
    campo.alCerrar?.();
    if (devolverFoco) campo.boton.focus();
  }

  function ubicar() {
    if (!abierto) return;
    const {campo, pop} = abierto;
    const r = campo.boton.getBoundingClientRect();
    const alto = pop.offsetHeight, ancho = pop.offsetWidth, m = 8;
    let top = r.bottom + 6;
    if (top + alto > innerHeight - m && r.top - 6 - alto >= m) top = r.top - 6 - alto;
    top = Math.max(m, Math.min(top, innerHeight - alto - m));
    const left = Math.max(m, Math.min(r.left, innerWidth - ancho - m));
    pop.style.top = top + 'px';
    pop.style.left = left + 'px';
  }

  // El campo decide que hace con el dia; devuelve true si ya termino (un
  // dia suelto, o el final de un rango) y el calendario se cierra.
  function elegir(campo, iso) {
    if (campo.elegir(iso)) cerrar(true);
    else marcar();
  }

  function claseDia(campo, iso, hoy) {
    const c = ['cal-dia'];
    if (iso === hoy) c.push('hoy');
    if (campo.rango) c.push(...claseEnRango(iso, campo.rango));
    else if (iso === campo.valor()) c.push('sel');
    return c.join(' ');
  }

  // Repinta los dias sin rehacer la grilla (el rango sigue al mouse).
  function marcar() {
    if (!abierto) return;
    const hoy = hoyIso();
    abierto.pop.querySelectorAll('.cal-dia').forEach(b => { b.className = claseDia(abierto.campo, b.dataset.iso, hoy); });
    const nota = abierto.pop.querySelector('.cal-nota');
    if (nota) nota.textContent = notaDelPie(abierto.campo);
  }

  function notaDelPie(campo) {
    if (campo.rango) return campo.rango.inicio && !campo.rango.fin ? 'Ahora elegí el final' : 'Elegí el inicio y el final';
    return campo.limites().permitidos ? 'Solo días guardados' : '';
  }

  function dibujar(enfocar) {
    const a = abierto;
    if (!a) return;
    const {campo, pop, vista} = a;
    const lim = campo.limites();
    const hoy = hoyIso();
    const dias = celdasDelMes(vista.y, vista.m).map(d => {
      if (d === null) return '<span></span>';
      const iso = aIso(vista.y, vista.m, d);
      const ok = sePuedeElegir(iso, lim);
      return `<button type="button" class="${claseDia(campo, iso, hoy)}" data-iso="${iso}" tabindex="-1"${ok ? '' : ' disabled'}
        aria-label="${etiquetaFecha(iso)}">${d}</button>`;
    }).join('');
    const meses = a.enMeses ? `<div class="cal-meses">
        <div class="cal-anio"><button type="button" class="cal-ic" data-anio="-1" aria-label="Año anterior">${IC_IZQ}</button>
          <span>${vista.y}</span>
          <button type="button" class="cal-ic" data-anio="1" aria-label="Año siguiente">${IC_DER}</button></div>
        <div class="cal-lista-meses">${MESES.map((n, i) =>
          `<button type="button" class="cal-mes${i === vista.m ? ' sel' : ''}" data-mes="${i}">${n.slice(0, 3)}</button>`).join('')}</div>
      </div>` : '';
    pop.innerHTML = `
      <div class="cal-cab">
        <button type="button" class="cal-titulo" data-accion="meses" aria-expanded="${a.enMeses}">
          <span>${MESES[vista.m]} ${vista.y}</span>${IC_ABAJO}</button>
        <div class="cal-flechas">
          <button type="button" class="cal-ic" data-paso="-1" aria-label="Mes anterior">${IC_IZQ}</button>
          <button type="button" class="cal-ic" data-paso="1" aria-label="Mes siguiente">${IC_DER}</button>
        </div>
      </div>
      <div class="cal-semana" aria-hidden="true">${SEMANA.map(s => `<span>${s}</span>`).join('')}</div>
      <div class="cal-cuerpo"><div class="cal-dias${campo.rango ? ' rango' : ''}">${dias}</div>${meses}</div>
      <div class="cal-pie"><span class="cal-nota">${notaDelPie(campo)}</span>
        ${campo.rango ? '' : `<button type="button" class="cal-hoy" data-accion="hoy"${sePuedeElegir(hoy, lim) ? '' : ' disabled'}>Hoy</button>`}</div>`;
    // Un solo dia de la grilla entra con Tab; las flechas mueven entre dias.
    const botones = [...pop.querySelectorAll('.cal-dia:not(:disabled)')];
    const foco = botones.find(b => b.dataset.iso === enfocar) || botones.find(b => b.classList.contains('sel'))
      || botones.find(b => b.dataset.iso === hoy) || botones[0];
    if (foco) foco.tabIndex = 0;
    if (enfocar && foco) foco.focus();
  }

  function mover(dias) {
    const actual = document.activeElement?.dataset?.iso;
    const p = leerIso(actual);
    if (!p) return;
    const f = new Date(Date.UTC(p.y, p.m, p.d + dias));
    abierto.vista = {y: f.getUTCFullYear(), m: f.getUTCMonth()};
    dibujar(aIso(f.getUTCFullYear(), f.getUTCMonth(), f.getUTCDate()));
  }

  function abrir(campo) {
    if (abierto?.campo === campo) { cerrar(true); return; }
    cerrar(false);
    const lim = campo.limites();
    const valor = leerIso(campo.valor());
    // Sin valor, abre en el ultimo dia que se puede elegir (o en hoy).
    const ultimo = lim.permitidos ? [...lim.permitidos].sort().pop() : null;
    const base = valor || leerIso(ultimo) || leerIso(hoyIso());
    const pop = document.createElement('div');
    pop.className = 'cal-pop';
    pop.setAttribute('role', 'dialog');
    pop.setAttribute('aria-label', 'Elegir fecha');
    document.body.appendChild(pop);
    abierto = {campo, pop, vista: {y: base.y, m: base.m}, enMeses: false};
    campo.boton.setAttribute('aria-expanded', 'true');
    dibujar(valor ? aIso(valor.y, valor.m, valor.d) : (ultimo || hoyIso()));
    ubicar();

    pop.addEventListener('click', e => {
      const b = e.target.closest('button');
      if (!b || b.disabled || !abierto) return;
      const v = abierto.vista;
      if (b.dataset.iso) return elegir(campo, b.dataset.iso);
      if (b.dataset.paso) {
        const f = new Date(Date.UTC(v.y, v.m + Number(b.dataset.paso), 1));
        abierto.vista = {y: f.getUTCFullYear(), m: f.getUTCMonth()};
      } else if (b.dataset.anio) {
        v.y += Number(b.dataset.anio);
      } else if (b.dataset.mes) {
        v.m = Number(b.dataset.mes);
        abierto.enMeses = false;
      } else if (b.dataset.accion === 'meses') {
        abierto.enMeses = !abierto.enMeses;
      } else if (b.dataset.accion === 'hoy') {
        return elegir(campo, hoyIso());
      }
      // Redibujar borra el boton que tenia el foco: se lo devuelve al nuevo.
      const clave = ['paso', 'anio', 'accion'].find(k => b.dataset[k]);
      dibujar();
      if (b.dataset.mes) pop.querySelector('.cal-titulo')?.focus();
      else if (clave) pop.querySelector(`[data-${clave}="${b.dataset[clave]}"]`)?.focus();
    });
    // Con el inicio elegido, el mouse va mostrando el rango que quedaria.
    pop.addEventListener('mouseover', e => {
      const r = campo.rango;
      if (!r || !r.inicio || r.fin) return;
      const iso = e.target.closest('.cal-dia:not(:disabled)')?.dataset.iso || null;
      if (iso !== r.hover) { r.hover = iso; marcar(); }
    });
    pop.addEventListener('keydown', e => {
      if (e.key === 'Escape') { e.preventDefault(); return cerrar(true); }
      if (!document.activeElement?.dataset?.iso) return;
      const pasos = {ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7};
      if (pasos[e.key]) { e.preventDefault(); mover(pasos[e.key]); }
    });
  }

  function mejorar(input, opciones = {}) {
    if (input.campoCalendario) {
      if ('permitidos' in opciones) input.campoCalendario.permitidos = opciones.permitidos ? new Set(opciones.permitidos) : null;
      input.campoCalendario.pintar();
      return input.campoCalendario;
    }
    ponerCss();
    const boton = document.createElement('button');
    boton.type = 'button';
    boton.className = [input.className, 'cal-campo'].filter(Boolean).join(' ');
    boton.style.cssText = input.style.cssText;
    boton.setAttribute('aria-haspopup', 'dialog');
    boton.setAttribute('aria-expanded', 'false');
    const campo = {
      input, boton,
      permitidos: opciones.permitidos ? new Set(opciones.permitidos) : null,
      limites() { return {min: input.min || null, max: input.max || null, permitidos: this.permitidos}; },
      valor: () => valorNativo.get.call(input),
      elegir(iso) {
        valorNativo.set.call(input, iso);
        campo.pintar();
        input.dispatchEvent(new Event('input', {bubbles: true}));
        input.dispatchEvent(new Event('change', {bubbles: true}));
        return true;
      },
      pintar() {
        const v = valorNativo.get.call(input);
        boton.innerHTML = (v ? `<span>${etiquetaFecha(v)}</span>` : '<span class="cal-vacio">Elegir fecha</span>') + IC_CAL;
        boton.disabled = input.disabled;
        const nombre = [...(input.labels || [])].map(l => l.textContent.trim()).join(' ') || 'Fecha';
        boton.setAttribute('aria-label', `${nombre}: ${v ? etiquetaFecha(v) : 'sin elegir'}`);
      },
    };
    input.campoCalendario = campo;
    // Asignar el valor por codigo (cargar un dia, limpiar) tambien repinta.
    Object.defineProperty(input, 'value', {
      configurable: true,
      get() { return valorNativo.get.call(this); },
      set(v) { valorNativo.set.call(this, v); campo.pintar(); },
    });
    new MutationObserver(() => campo.pintar()).observe(input, {attributes: true, attributeFilter: ['disabled', 'min', 'max']});
    boton.addEventListener('click', () => abrir(campo));
    // El <label for> apuntaba al input, que ahora esta escondido.
    [...(input.labels || [])].forEach(l => l.addEventListener('click', e => { e.preventDefault(); boton.focus(); }));
    input.hidden = true;
    input.style.display = 'none';
    input.after(boton);
    campo.pintar();
    return campo;
  }

  // Modo rango: `desde` y `hasta` son los campos que se ven (texto de solo
  // lectura) y `desdeOculto`/`hastaOculto` los que lee la pagina (YYYY-MM-DD).
  // Cualquiera de los dos abre el mismo calendario; el rango solo se guarda
  // cuando tiene final, y si se cierra a medias queda el que habia.
  function rango({desde, hasta, desdeOculto, hastaOculto}) {
    ponerCss();
    const mostrar = () => {
      desde.value = etiquetaFecha(desdeOculto.value);
      hasta.value = etiquetaFecha(hastaOculto.value);
    };
    [desde, hasta].forEach(visible => {
      visible.placeholder = 'Elegir fecha';
      visible.setAttribute('aria-haspopup', 'dialog');
      visible.setAttribute('aria-expanded', 'false');
      const campo = {
        boton: visible, rango: null,
        limites: () => ({}),
        valor: () => campo.rango.fin || campo.rango.inicio,
        elegir(iso) {
          const r = campo.rango;
          if (!r.inicio || r.fin) {
            Object.assign(r, {inicio: iso, fin: null, hover: null});
            desde.value = etiquetaFecha(iso);
            hasta.value = '';
            return false;
          }
          [r.inicio, r.fin] = iso < r.inicio ? [iso, r.inicio] : [r.inicio, iso];
          desdeOculto.value = r.inicio;
          hastaOculto.value = r.fin;
          [desdeOculto, hastaOculto].forEach(i => i.dispatchEvent(new Event('change', {bubbles: true})));
          return true;
        },
        alCerrar: mostrar,
      };
      const abrirRango = () => {
        campo.rango = {inicio: desdeOculto.value || null, fin: hastaOculto.value || null, hover: null};
        abrir(campo);
      };
      visible.addEventListener('click', abrirRango);
      visible.addEventListener('keydown', e => {
        if (['Enter', ' ', 'ArrowDown'].includes(e.key)) { e.preventDefault(); abrirRango(); }
      });
    });
    mostrar();
  }

  function mejorarDentro(nodo) {
    if (nodo.nodeType !== 1) return;
    const sel = 'input[type="date"]:not([data-sin-calendario])';
    if (nodo.matches(sel)) mejorar(nodo);
    nodo.querySelectorAll(sel).forEach(i => mejorar(i));
  }

  function iniciar() {
    mejorarDentro(document.body);
    new MutationObserver(cambios => cambios.forEach(c => c.addedNodes.forEach(mejorarDentro)))
      .observe(document.body, {childList: true, subtree: true});
    document.addEventListener('mousedown', e => {
      if (abierto && !abierto.pop.contains(e.target) && !abierto.campo.boton.contains(e.target)) cerrar(false);
    });
    addEventListener('resize', () => cerrar(false));
    addEventListener('scroll', ubicar, true);
  }

  root.VMOCalendario = {mejorar, rango, ...api};
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
  else iniciar();
})(typeof window !== 'undefined' ? window : globalThis);
