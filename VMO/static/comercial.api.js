// Lo que las paginas del modulo Comercial necesitan para hablar con el
// servidor y con el portal (2026-10-19). Separado de comercial.logic.js por
// lo mismo que en Logistica: logic = calculo puro probado con node; api =
// fetch, token e iframes. Es propio del modulo y no reusa logistica.api.js:
// cada modulo es un ambiente separado.
(function (root) {
  'use strict';

  function tokenDelPortal() {
    try { return localStorage.getItem('vmo_token'); } catch (e) { return null; }
  }

  function estaEmbebido() {
    try { return window.self !== window.top; } catch (e) { return true; }
  }

  function errorSinToken() {
    const err = new Error('Iniciá sesión en el portal para usar el módulo Comercial.');
    err.sinToken = true;
    return err;
  }

  async function respuesta(res) {
    let cuerpo = null;
    try { cuerpo = await res.json(); } catch (e) { /* sin cuerpo o no-JSON */ }
    if (!res.ok) {
      const detalle = cuerpo && cuerpo.detail;
      const err = new Error((typeof detalle === 'string' ? detalle : detalle?.detalle) || `Error ${res.status}`);
      err.status = res.status;
      throw err;
    }
    return cuerpo;
  }

  async function apiComercial(ruta) {
    const token = tokenDelPortal();
    if (!token) throw errorSinToken();
    return respuesta(await fetch(ruta, {headers: {'Authorization': `Bearer ${token}`}}));
  }

  // Sube un Excel. Sin `confirmar` el servidor solo lo lee y dice que va a
  // reemplazar; con `confirmar` lo guarda.
  async function subirArchivoComercial(ruta, archivo, confirmar) {
    const token = tokenDelPortal();
    if (!token) throw errorSinToken();
    const form = new FormData();
    form.append('archivo', archivo);
    form.append('confirmar', confirmar ? 'true' : 'false');
    return respuesta(await fetch(ruta, {method: 'POST', headers: {'Authorization': `Bearer ${token}`}, body: form}));
  }

  // Escapar todo texto de datos antes de meterlo en innerHTML: cliente,
  // vendedor, producto salen de los Excel que se suben.
  function esc(v) {
    return String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // Despues de guardar, el dashboard (otro iframe) tiene que releer los datos.
  function avisarDatosComerciales() {
    if (estaEmbebido()) window.parent.postMessage({tipo: 'comercial:datos-guardados'}, window.location.origin);
  }

  const fmtM3 = n => (n ?? 0).toLocaleString('es-DO', {maximumFractionDigits: 1});
  const fmtRD = n => 'RD$ ' + (n ?? 0).toLocaleString('es-DO', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  const fmtRDCorto = n => {
    const v = Math.abs(n ?? 0);
    if (v >= 1e6) return 'RD$ ' + (n / 1e6).toLocaleString('es-DO', {maximumFractionDigits: 1}) + ' M';
    if (v >= 1e3) return 'RD$ ' + (n / 1e3).toLocaleString('es-DO', {maximumFractionDigits: 0}) + ' mil';
    return 'RD$ ' + (n ?? 0).toLocaleString('es-DO', {maximumFractionDigits: 0});
  };

  Object.assign(root, {tokenDelPortal, estaEmbebido, apiComercial, subirArchivoComercial, esc,
                       avisarDatosComerciales, fmtM3, fmtRD, fmtRDCorto});
})(typeof globalThis !== 'undefined' ? globalThis : this);
