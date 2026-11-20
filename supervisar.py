#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tu Vecina Cotilla — Supervisor diario.

Comprueba que:
  - la actualización del día se ha ejecutado;
  - hay noticias y todas tienen imagen local;
  - news-data.js coincide con el histórico;
  - existe la página estática de cada noticia y responde por HTTP;
  - el workflow sigue versionando `noticias/` (regresión del 404);
  - no han vuelto los huecos de publicidad.

Sale con código 1 si algo falla, para que el workflow quede en rojo.
"""

import json
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import actualizar_noticias as gen

BASE = Path(__file__).resolve().parent


def estado_enlace(url):
    """Devuelve None si responde, o un texto con el error."""
    for intento in range(2):
        try:
            req = urllib.request.Request(
                url, method='HEAD', headers={'User-Agent': 'TVC-Supervisor/1.0'})
            with urllib.request.urlopen(req, timeout=12) as resp:
                if 200 <= resp.status < 400:
                    return None
                return f'HTTP {resp.status}'
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 'HTTP 404'
            if intento == 1:
                return f'HTTP {e.code}'
        except Exception as e:
            if intento == 1:
                return str(e)[:80]
    return None


def comprobar_enlaces(noticias):
    urls = sorted({gen.url_para(n) for n in noticias})
    if not urls:
        return [], 0
    fallos = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for url, error in zip(urls, pool.map(estado_enlace, urls)):
            if error:
                fallos.append(f'{url}: {error}')
    return fallos, len(urls)


def main():
    errores = []
    avisos = []

    historico = BASE / 'datos' / 'historico.json'
    if not historico.exists():
        print('FALLO: no existe datos/historico.json')
        return 1

    datos = json.loads(historico.read_text(encoding='utf-8'))
    noticias = datos.get('noticias', [])
    actualizado = datos.get('actualizado', '')
    hoy = datetime.now(timezone.utc).date().isoformat()

    if not actualizado.startswith(hoy):
        errores.append(f'la última actualización es {actualizado!r}, no de hoy ({hoy})')
    if len(noticias) < 100:
        errores.append(f'solo hay {len(noticias)} noticias')

    sin_imagen = []
    imagenes_faltan = []
    for n in noticias:
        img = n.get('image', '')
        ident = n.get('id', '?')
        if not img:
            sin_imagen.append(ident)
            continue
        ruta = BASE / img if not Path(img).is_absolute() else Path(img)
        if not ruta.exists():
            imagenes_faltan.append(f'{ident}: {img}')
    if sin_imagen:
        errores.append(f'{len(sin_imagen)} noticias sin imagen')
    if imagenes_faltan:
        errores.append(f'{len(imagenes_faltan)} imágenes ausentes: {imagenes_faltan[:3]}')

    js = BASE / 'js' / 'news-data.js'
    if not js.exists():
        errores.append('falta js/news-data.js')
    else:
        texto = js.read_text(encoding='utf-8')
        if texto.count('  A("') != len(noticias):
            errores.append('news-data.js no coincide con el histórico')

    paginas = list((BASE / 'noticias').glob('*.html'))
    if len(paginas) != len(noticias):
        avisos.append(f'{len(paginas)} páginas estáticas para {len(noticias)} noticias')
    for n in noticias:
        nombre = gen.slug_para(n) + '.html'
        if not (BASE / 'noticias' / nombre).exists():
            errores.append(f'falta la página local de {n.get("id", "?")}: {nombre}')
            break

    fallos_enlaces, total_enlaces = comprobar_enlaces(noticias)
    if fallos_enlaces:
        errores.append(
            f'{len(fallos_enlaces)} de {total_enlaces} enlaces fallan: {fallos_enlaces[:3]}')

    for archivo in ('index.html', 'sitemap.xml', 'robots.txt'):
        ruta = BASE / archivo
        if not ruta.exists() or ruta.stat().st_size < 40:
            errores.append(f'{archivo} ausente o vacío')

    index = (BASE / 'index.html').read_text(encoding='utf-8')
    if 'PON AQUÍ TU PUBLICIDAD' in index:
        errores.append('han vuelto los huecos de publicidad en index.html')

    workflow = BASE / '.github' / 'workflows' / 'actualizar-noticias.yml'
    if not workflow.exists() or 'noticias/' not in workflow.read_text(encoding='utf-8'):
        errores.append('el workflow no versiona noticias/ (riesgo de 404)')

    print('=== SUPERVISOR TU VECINA COTILLA ===')
    print(f'Fecha UTC: {datetime.now(timezone.utc).isoformat()}')
    print(f'Actualizado: {actualizado}')
    print(f'Noticias: {len(noticias)}')
    print(f'Con imagen: {sum(1 for n in noticias if n.get("image"))}')
    print(f'Páginas estáticas: {len(paginas)}')
    print(f'Enlaces comprobados: {total_enlaces} ({len(fallos_enlaces)} fallidos)')
    for aviso in avisos:
        print('AVISO:', aviso)
    if errores:
        print('RESULTADO: FALLIDO')
        for e in errores:
            print('  -', e)
        return 1
    print('RESULTADO: CORRECTO')
    return 0


if __name__ == '__main__':
    sys.exit(main())
