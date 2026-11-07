// Auditoria de seguridad del 2026-10-07: el texto de los Excel (cliente, obra,
// planta, ficha, bomba, elemento) se metia crudo en innerHTML. Una celda con
// `<img src=x onerror=...>` se ejecutaba en el navegador de quien abriera el
// dia y se llevaba el token del portal.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

require('../../static/logistica.api.js');
const {esc} = globalThis;

test('esc neutraliza html y comillas', () => {
  assert.equal(esc('<img src=x onerror="alert(1)">'),
               '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;');
  assert.equal(esc("O'Neil & Hijos"), 'O&#39;Neil &amp; Hijos');
});

test('esc con null, undefined y numeros', () => {
  assert.equal(esc(null), '');
  assert.equal(esc(undefined), '');
  assert.equal(esc(25), '25');
});

// Red contra el olvido: ninguna de las tres paginas mete un campo de texto de
// los datos en el HTML sin pasar por esc(). Busca `${x.cliente}`,
// `${r.obraReal || ...}`, etc. —un acceso a esos campos justo despues de `${`.
const CAMPOS = 'cliente|obra|obraReal|obraProg|planta|ficha|bomba|elemento|zona|responsable|motivo|observacion';
const CRUDO = new RegExp('\\$\\{\\s*\\(?\\s*[a-z]\\.(' + CAMPOS + ')\\b', 'g');

for (const pagina of ['logistica.html', 'logistica-historial.html', 'logistica-estadisticas.html',
                      'logistica-comparacion.html', 'logistica-cancelados.html',
                      'logistica-reporte-dia.html', 'logistica-indicadores.html']){
  test(`${pagina}: ningun campo de texto de los datos va crudo al HTML`, () => {
    const html = fs.readFileSync(path.join(__dirname, '..', '..', 'static', pagina), 'utf8');
    const crudos = [...html.matchAll(CRUDO)].map(m => {
      const linea = html.slice(0, m.index).split('\n').length;
      return `linea ${linea}: ${m[0]}`;
    });
    assert.deepEqual(crudos, []);
  });
}

// Lo mismo para el modulo Comercial (2026-10-19): ahi los textos de los datos
// viajan como `nombre` (cliente, vendedor, zona...) y `archivo`.
const CRUDO_COM = /\$\{\s*\(?\s*[a-z]\.(nombre|archivo|cliente|vendedor|zona|planta|producto)\b/g;
for (const pagina of ['comercial-dashboard.html', 'comercial-subir.html']){
  test(`${pagina}: ningun texto de los datos va crudo al HTML`, () => {
    const html = fs.readFileSync(path.join(__dirname, '..', '..', 'static', pagina), 'utf8');
    const crudos = [...html.matchAll(CRUDO_COM)].map(m => `linea ${html.slice(0, m.index).split('\n').length}: ${m[0]}`);
    assert.deepEqual(crudos, []);
  });
}

test('la libreria de Excel es la corregida y se sirve desde la app', () => {
  const html = fs.readFileSync(path.join(__dirname, '..', '..', 'static', 'logistica.html'), 'utf8');
  assert.ok(html.includes('src="/vendor/xlsx-0.20.3.full.min.js"'));
  assert.ok(!html.includes('cdnjs.cloudflare.com/ajax/libs/xlsx'));
  assert.ok(fs.existsSync(path.join(__dirname, '..', '..', 'static', 'vendor', 'xlsx-0.20.3.full.min.js')));
});
