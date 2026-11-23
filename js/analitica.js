/* MCad Analytics — contador de visitas sin cookies ni datos personales.
   Usa CountAPI (countapi.mileshilliard.com), gratuito y sin registro.
   Cuenta: total, día, sección y lectores distintos aproximados por día. */
(function () {
  'use strict';

  var API = 'https://countapi.mileshilliard.com/api/v1';
  var PREFIJO = 'mcad76_web_noticias';

  try {
    if (navigator.doNotTrack === '1' || window.doNotTrack === '1') return;
    var host = location.hostname;
    if (host === 'localhost' || host === '127.0.0.1' || host === '') return;
  } catch (error) {
    return;
  }

  function dosDigitos(n) {
    return n < 10 ? '0' + n : String(n);
  }

  function fechaLocal() {
    var d = new Date();
    return d.getFullYear() + '-' + dosDigitos(d.getMonth() + 1) + '-' + dosDigitos(d.getDate());
  }

  function hit(clave) {
    try {
      fetch(API + '/hit/' + encodeURIComponent(clave), {
        mode: 'cors',
        cache: 'no-store',
        keepalive: true
      }).catch(function () {});
    } catch (error) { /* el contador nunca debe romper la web */ }
  }

  var seccion = 'portada';
  try {
    seccion = document.body.getAttribute('data-seccion') || 'portada';
  } catch (error) { /* noop */ }

  var hoy = fechaLocal();
  hit(PREFIJO + '_total');
  hit(PREFIJO + '_dia_' + hoy);
  hit(PREFIJO + '_sec_' + seccion);

  // Una "visita" cuenta una vez por sesión; las páginas vistas cuentan cada carga.
  var nuevaSesion = true;
  try {
    var claveSesion = 'mcad_sesion_' + PREFIJO;
    nuevaSesion = !sessionStorage.getItem(claveSesion);
    if (nuevaSesion) sessionStorage.setItem(claveSesion, '1');
  } catch (error) { /* sin sessionStorage se cuenta como sesión nueva */ }
  if (nuevaSesion) {
    hit(PREFIJO + '_visitas');
    hit(PREFIJO + '_visitas_dia_' + hoy);
  }

  try {
    var clave = 'mcad_analitica_' + PREFIJO + '_' + hoy;
    if (!localStorage.getItem(clave)) {
      localStorage.setItem(clave, '1');
      hit(PREFIJO + '_unicos_' + hoy);
    }
  } catch (error) { /* modo privado: no se cuenta el único */ }
})();
