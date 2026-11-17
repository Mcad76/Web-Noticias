/* ============================================================
   TU VECINA COTILLA — Lógica de la aplicación
   - Portada por categorías: 3 noticias recientes y relevantes por sección
   - Accesos rápidos a cada sección
   - Archivo: noticias anteriores con su fecha de publicación
   - Modal: noticia ampliada al pulsar
   ============================================================ */

const MS_DIA = 86400000;
const ANCLAJE = new Date(2026, 0, 1); // Referencia fija para la rotación
const HOY = new Date();
let regionActual = 'nacional';

/* ---------- Utilidades de fecha ---------- */
function inicioDelDia(d) { return new Date(d.getFullYear(), d.getMonth(), d.getDate()); }
function sumarDias(d, n) { return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n); }
function indiceDia(d) { return Math.round((inicioDelDia(d) - ANCLAJE) / MS_DIA); }

const fechaLarga = new Intl.DateTimeFormat('es-ES', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
const fechaCorta = new Intl.DateTimeFormat('es-ES', { day: '2-digit', month: 'short', year: 'numeric' });

const DIA_ACTUAL = indiceDia(HOY);
const TAMANO_SECCION = 6;

function seccionPorId(id) { return SECCIONES.find(s => s.id === id); }
function indiceSeccion(id) { return SECCIONES.findIndex(s => s.id === id); }

/* ---------- Rotación diaria ---------- */
function inicioRotacion(idxSeccion, dia) {
  // Multiplicador 5 coprimo con 6 => las 6 combinaciones se recorren en 6 días
  return (((dia * 5 + idxSeccion) % TAMANO_SECCION) + TAMANO_SECCION) % TAMANO_SECCION;
}

function tieneFechaReal(n) {
  return !!(n.fecha && !isNaN(new Date(n.fecha).getTime()));
}

function noticiasDeHoy(idxSeccion, region = regionActual) {
  const sec = SECCIONES[idxSeccion];
  const lista = NOTICIAS.filter(n => n.sec === sec.id &&
    (n.region || 'nacional') === region);
  // Las más recientes y relevantes de cada categoría
  const reales = lista.filter(tieneFechaReal).sort((a, b) =>
    (b.viral || 0) - (a.viral || 0) || new Date(b.fecha) - new Date(a.fecha));
  if (reales.length) return reales.slice(0, 3);
  if (!lista.length) return [];
  const ini = inicioRotacion(idxSeccion, DIA_ACTUAL);
  return [0, 1, 2].map(k => lista[(ini + k) % lista.length]);
}

function fechaPublicacion(articulo, idxSeccion) {
  for (let d = DIA_ACTUAL; d >= DIA_ACTUAL - (TAMANO_SECCION - 1); d--) {
    const ini = inicioRotacion(idxSeccion, d);
    if ([0, 1, 2].some(k => (ini + k) % TAMANO_SECCION === articulo.slot)) {
      return sumarDias(ANCLAJE, d);
    }
  }
  return sumarDias(ANCLAJE, DIA_ACTUAL);
}

// Mapa de fechas y conjunto de noticias de hoy
const FECHAS_PUBLICACION = {};
NOTICIAS.forEach(n => {
  FECHAS_PUBLICACION[n.id] = tieneFechaReal(n)
    ? new Date(n.fecha)
    : fechaPublicacion(n, indiceSeccion(n.sec));
});
let IDS_HOY = new Set();
function actualizarIdsHoy() {
  IDS_HOY = new Set();
  SECCIONES.forEach((_, i) => noticiasDeHoy(i).forEach(n => IDS_HOY.add(n.id)));
}
actualizarIdsHoy();

function minutosLectura(articulo) {
  const palabras = (articulo.entradilla + ' ' + articulo.cuerpo.join(' ')).split(/\s+/).length;
  return Math.max(1, Math.round(palabras / 200));
}

/* ---------- Imágenes de respaldo ---------- */
function imgFallback(el, color) {
  el.onerror = null;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="640">
    <rect width="100%" height="100%" fill="${color}"/>
    <text x="50%" y="48%" fill="#ffffff" font-family="Arial,sans-serif" font-size="64" font-weight="bold" text-anchor="middle">TU VECINA COTILLA</text>
    <text x="50%" y="60%" fill="#ffffff" opacity="0.75" font-family="Arial,sans-serif" font-size="26" text-anchor="middle">IMAGEN ILUSTRATIVA</text>
  </svg>`;
  el.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
}

function imagenHTML(noticia, clase, color) {
  return `<div class="${clase}">
    <img src="${noticia.image}" alt="${noticia.titulo}" loading="lazy"
         onerror="imgFallback(this,'${color}')">
  </div>`;
}

/* Fila de categoría, encima de la foto */
function categoriaHTML(noticia, extra = '') {
  const sec = seccionPorId(noticia.sec);
  return `<div class="noticia__cat" style="--secc-color:${sec.color}">
    <span class="noticia__cat-nombre">${sec.nombre}</span>${extra}
  </div>`;
}

/* ---------- Tarjetas ---------- */
function tarjetaHTML(noticia, variante = '') {
  const color = seccionPorId(noticia.sec).color;
  const fecha = FECHAS_PUBLICACION[noticia.id];
  return `<article class="tarjeta ${variante}" data-id="${noticia.id}"
             style="--secc-color:${color}" tabindex="0" role="button"
             aria-label="Leer noticia: ${noticia.titulo}">
    ${categoriaHTML(noticia)}
    ${imagenHTML(noticia, 'tarjeta__img', color)}
    <div class="tarjeta__cuerpo">
      <h3 class="tarjeta__titulo">${noticia.titulo}</h3>
      <p class="tarjeta__entradilla">${noticia.entradilla}</p>
      <div class="tarjeta__meta">${noticia.autor} · ${fechaCorta.format(fecha)} · ${minutosLectura(noticia)} min</div>
    </div>
  </article>`;
}

/* ---------- Espacios publicitarios ---------- */
const AD_HTML = '<aside class="ad ad--inline"><span class="ad__label">PUBLICIDAD</span><strong>PON AQUÍ TU PUBLICIDAD</strong><span class="ad__small">¿Quieres destacar aquí? Escríbenos</span></aside>';

/* ---------- Navegación, accesos rápidos y ticker ---------- */
function construirNavegacion() {
  const tabs = document.getElementById('tabs-regiones');
  if (tabs && typeof REGIONES !== 'undefined') {
    tabs.innerHTML = REGIONES.map(r =>
      `<button type="button" data-region="${r.id}" class="${r.id === regionActual ? 'activa' : ''}">${r.nombre}</button>`
    ).join('');
  }
  const nav = document.getElementById('nav-secciones');
  const accesos = document.getElementById('accesos-rapidos');
  const selector = document.getElementById('archivo-seccion');
  const menuSecciones = document.getElementById('menu-secciones');
  if (menuSecciones) {
    menuSecciones.innerHTML = '<div class="menu-desplegable__titulo">Secciones</div>';
  }
  SECCIONES.forEach(s => {
    nav.insertAdjacentHTML('beforeend',
      `<a href="#${s.id}" style="--secc-color:${s.color}">${s.nombre}</a>`);
    if (accesos) accesos.insertAdjacentHTML('beforeend',
      `<a class="acceso" href="#${s.id}" style="--secc-color:${s.color}">${s.nombre}</a>`);
    if (menuSecciones) menuSecciones.insertAdjacentHTML('beforeend',
      `<a href="#${s.id}" style="--secc-color:${s.color}">${s.nombre}</a>`);
    selector.insertAdjacentHTML('beforeend', `<option value="${s.id}">${s.nombre}</option>`);
  });
}

function construirTicker() {
  const titulares = NOTICIAS.filter(n => tieneFechaReal(n) &&
      (n.region || 'nacional') === regionActual)
    .sort((a, b) => (b.viral || 0) - (a.viral || 0) || new Date(b.fecha) - new Date(a.fecha))
    .slice(0, 6)
    .map(n => `<span data-id="${n.id}" role="button" tabindex="0" aria-label="Leer noticia: ${n.titulo}">🔥 ${n.titulo}</span>`)
    .join('');
  document.getElementById('ticker-track').innerHTML = titulares + titulares; // duplicado para bucle continuo
}

/* ---------- Secciones temáticas ---------- */
function construirSecciones() {
  const contenedor = document.getElementById('secciones');
  contenedor.innerHTML = '';
  SECCIONES.forEach((sec, idx) => {
    const noticias = noticiasDeHoy(idx);
    const bloque = document.createElement('section');
    bloque.className = 'seccion bloque';
    bloque.id = sec.id;
    bloque.style.setProperty('--secc-color', sec.color);
    const contenido = noticias.length
      ? `<div class="rejilla">${noticias.map(n => tarjetaHTML(n)).join('')}</div>`
      : '<p class="seccion__vacia">No hay noticias nuevas hoy en esta sección. Consulta el archivo.</p>';
    bloque.innerHTML = `
      <div class="wrap">
        <div class="seccion__cabecera">
          <div class="seccion__nombre"><span class="punto"></span>${sec.nombre}
            <span class="seccion__num">${noticias.length} noticias</span>
          </div>
          <a class="seccion__ver" href="#archivo" data-filtrar="${sec.id}">Ver todas las de ${sec.nombre.toLowerCase()} →</a>
        </div>
        ${contenido}
      </div>`;
    contenedor.appendChild(bloque);
    if (idx === 3) contenedor.insertAdjacentHTML('beforeend', AD_HTML);
  });
}

/* ---------- Archivo ---------- */
function construirArchivo() {
  const buscar = document.getElementById('archivo-buscar').value.trim().toLowerCase();
  const seccion = document.getElementById('archivo-seccion').value;
  const lista = document.getElementById('archivo-lista');

  let noticias = [...NOTICIAS].sort((a, b) => {
    const dif = FECHAS_PUBLICACION[b.id] - FECHAS_PUBLICACION[a.id];
    return dif !== 0 ? dif : a.slot - b.slot;
  });

  noticias = noticias.filter(n => (n.region || 'nacional') === regionActual);
  if (seccion !== 'todas') noticias = noticias.filter(n => n.sec === seccion);
  if (buscar) noticias = noticias.filter(n =>
    (n.titulo + ' ' + n.entradilla + ' ' + n.cuerpo.join(' ')).toLowerCase().includes(buscar));

  document.getElementById('archivo-contador').textContent =
    `${noticias.length} noticia${noticias.length === 1 ? '' : 's'}`;
  document.getElementById('archivo-vacio').hidden = noticias.length > 0;

  lista.innerHTML = noticias.map(n => {
    const sec = seccionPorId(n.sec);
    const f = FECHAS_PUBLICACION[n.id];
    return `<article class="archivo__item" data-id="${n.id}" style="--secc-color:${sec.color}"
               tabindex="0" role="button" aria-label="Leer noticia: ${n.titulo}">
      <img class="archivo__thumb" src="${n.image}" alt="" loading="lazy"
           onerror="imgFallback(this,'${sec.color}')">
      <div class="archivo__info">
        <div class="archivo__item-titulo">${n.titulo}</div>
        <div class="archivo__item-sub">${sec.nombre} · ${n.autor} · ${minutosLectura(n)} min de lectura</div>
      </div>
      <div class="archivo__fecha">
        <strong>${sec.nombre}</strong>
        ${fechaCorta.format(f)}
        ${IDS_HOY.has(n.id) ? '<span class="archivo__hoy">HOY</span>' : ''}
      </div>
    </article>`;
  }).join('');
}

/* ---------- Modal de noticia ampliada ---------- */
const modal = document.getElementById('modal');

function abrirNoticia(id) {
  const n = NOTICIAS.find(x => x.id === id);
  if (!n) return;
  // Página estática real: texto en el HTML inicial y URL limpia e indexable
  if (n.url) { window.location.href = n.url; return; }
  const sec = seccionPorId(n.sec);
  const f = FECHAS_PUBLICACION[n.id];

  const relacionadas = NOTICIAS
    .filter(x => x.sec === n.sec && x.id !== n.id &&
      (x.region || 'nacional') === (n.region || 'nacional'))
    .sort((a, b) => (IDS_HOY.has(b.id) ? 1 : 0) - (IDS_HOY.has(a.id) ? 1 : 0))
    .slice(0, 2);

  document.getElementById('modal-contenido').innerHTML = `
    <img class="modal__img" src="${n.image}" alt="${n.titulo}" onerror="imgFallback(this,'${sec.color}')">
    <div class="modal__contenido-pad" style="--secc-color:${sec.color}">
      <span class="modal__tag">${sec.nombre}</span>
      <h1 class="modal__titulo" id="modal-titulo">${n.titulo}</h1>
      <div class="modal__meta">
        <span>Por <strong>${n.autor}</strong></span>
        <span>${fechaLarga.format(f)}</span>
        <span>${minutosLectura(n)} min de lectura</span>
      </div>
      <p class="modal__entradilla">${n.entradilla}</p>
      <div class="modal__cuerpo">${n.cuerpo.map(p => `<p>${p}</p>`).join('')}</div>
      ${n.link ? `<a class="modal__fuente" href="${n.link}" target="_blank" rel="noopener noreferrer">Leer la noticia original en ${n.medio || 'la fuente'} ↗</a>` : ''}
      <div class="relacionadas">
        <h3>También en ${sec.nombre.toLowerCase()}</h3>
        ${relacionadas.map(r => `<a data-id="${r.id}">${r.titulo}</a>`).join('')}
      </div>
    </div>`;

  modal.hidden = false;
  document.body.classList.add('modal-abierto');
  modal.querySelector('.modal__panel').scrollTop = 0;
  document.getElementById('modal-close').focus();
}

function cerrarNoticia() {
  modal.hidden = true;
  document.body.classList.remove('modal-abierto');
}

/* ---------- Eventos ---------- */
document.addEventListener('click', (e) => {
  const cerrar = e.target.closest('[data-cerrar]');
  if (cerrar) { cerrarNoticia(); return; }

  const filtrar = e.target.closest('[data-filtrar]');
  if (filtrar) {
    document.getElementById('archivo-seccion').value = filtrar.dataset.filtrar;
    construirArchivo();
    return;
  }

  const noticia = e.target.closest('[data-id]');
  if (noticia) abrirNoticia(noticia.dataset.id);
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !modal.hidden) cerrarNoticia();
  if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('[data-id][role="button"]')) {
    e.preventDefault();
    abrirNoticia(e.target.dataset.id);
  }
});

document.getElementById('archivo-buscar').addEventListener('input', construirArchivo);
document.getElementById('archivo-seccion').addEventListener('change', construirArchivo);

document.getElementById('buscador-top').addEventListener('input', (e) => {
  document.getElementById('archivo-buscar').value = e.target.value;
  construirArchivo();
});
document.getElementById('buscador-top').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') document.getElementById('archivo').scrollIntoView({ behavior: 'smooth' });
});

/* ---------- Menú desplegable de 3 barras ---------- */
const menuBtn = document.getElementById('menu-btn');
const menuDesplegable = document.getElementById('menu-desplegable');

function alternarMenu(forzar) {
  const abierto = typeof forzar === 'boolean' ? forzar : menuDesplegable.hidden;
  menuDesplegable.hidden = !abierto;
  menuBtn.setAttribute('aria-expanded', String(abierto));
  menuBtn.setAttribute('aria-label', abierto ? 'Cerrar menú de secciones' : 'Abrir menú de secciones');
  menuBtn.innerHTML = abierto ? '&#10005;' : '&#9776;';
}

menuBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  alternarMenu();
});

menuDesplegable.addEventListener('click', (e) => {
  if (e.target.closest('a')) alternarMenu(false);
});

document.addEventListener('click', (e) => {
  if (!e.target.closest('.menu-wrap')) alternarMenu(false);
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !menuDesplegable.hidden) {
    alternarMenu(false);
    menuBtn.focus();
  }
});

/* ---------- Pestañas por comunidad ---------- */
document.getElementById('tabs-regiones').addEventListener('click', (e) => {
  const boton = e.target.closest('button[data-region]');
  if (!boton || boton.dataset.region === regionActual) return;
  regionActual = boton.dataset.region;
  document.querySelectorAll('#tabs-regiones button').forEach(b =>
    b.classList.toggle('activa', b === boton));
  actualizarIdsHoy();
  construirTicker();
  construirSecciones();
  construirArchivo();
});

/* ---------- Inicio ---------- */
document.getElementById('fecha-topbar').textContent = fechaLarga.format(HOY);
document.getElementById('anio').textContent = HOY.getFullYear();
if (typeof ACTUALIZADO !== 'undefined' && ACTUALIZADO) {
  document.querySelector('.topbar__edicion').textContent =
    'Actualizado el ' + new Date(ACTUALIZADO).toLocaleString('es-ES',
      { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
  document.querySelector('.footer__nota').textContent =
    'Noticias obtenidas de fuentes públicas RSS · cada imagen pertenece a su noticia original';
}
construirNavegacion();
construirTicker();
construirSecciones();
construirArchivo();

/* ---------- Contador de visitas ---------- */
(async function contadorDeVisitas() {
  const hueco = document.getElementById('contador-visitas');
  if (!hueco) return;
  try {
    const respuesta = await fetch(
      'https://countapi.mileshilliard.com/api/v1/hit/tuvecinacotilla-visitas-2026',
      { cache: 'no-store' }
    );
    if (!respuesta.ok) throw new Error('Contador no disponible');
    const datos = await respuesta.json();
    hueco.textContent = new Intl.NumberFormat('es-ES').format(datos.value);
  } catch (error) {
    hueco.textContent = '—';
    hueco.title = 'El contador no está disponible temporalmente';
    console.warn('Contador de visitas:', error);
  }
})();
