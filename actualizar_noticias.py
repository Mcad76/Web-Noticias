#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tu Vecina Cotilla — Actualizador automático de noticias.

Descarga noticias reales desde fuentes RSS públicas, elimina duplicados,
calcula un ranking deviralidad y regenera js/news-data.js.

Uso manual:  bash actualizar_diario.sh
"""

import os
import re
import json
import html
import time
import hashlib
import urllib.request
from urllib.parse import quote, urlparse, parse_qs
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from PIL import Image

# ------------------------------------------------------------------ config
BASE = Path(__file__).resolve().parent
DATOS = BASE / 'datos'
IMGS = BASE / 'imagenes'
JS = BASE / 'js' / 'news-data.js'
HISTORICO = DATOS / 'historico.json'
MANUALES = DATOS / 'noticias-manuales.json'   # se edita directamente en GitHub
LOG = BASE / 'actualizar_noticias.log'

BASE_URL = 'https://mcad76.github.io/Web-Noticias-/'
ELP = 'https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/'
UA = 'Mozilla/5.0 (compatible; TuVecinaCotilla/2.0; +RSS)'
TIMEOUT = 20
MAX_POR_SECCION = 12      # candidatos por sección y fuente
MAX_IMAGENES = 500        # descargas de imagen por ejecución
DIAS_HISTORICO = 30
MAX_EN_ARCHIVO = 450
MAX_POR_REGION = 42       # candidatos por comunidad (3 x 7 secciones)
TOP_N = 10                # noticias del ranking diario

# Orden de captura de las secciones nacionales
ORDEN_CAPTURA = ['politica', 'deportes', 'sociedad', 'tecnologia',
                 'cultura', 'economia', 'industria']

IMPORTANTES = [
    'gobierno', 'elecciones', 'electoral', 'crisis', 'guerra', 'ue', 'espana',
    'congreso', 'senado', 'ministro', 'presidente', 'tribunal', 'justicia',
    'investigacion', 'escandalo', 'dimision', 'huelga', 'paro', 'inflacion',
    'vivienda', 'salario', 'pension', 'sanidad', 'clima', 'acuerdo', 'ley',
    'banco', 'bolsa', 'inteligencia artificial', 'china', 'ee uu', 'rusia',
    'ucrania', 'palestina', 'israel', 'champions', 'seleccion', 'olimpicos',
    'muere', 'muertos', 'accidente', 'desastre', 'campeon', 'final',
]
RUIDO = ['videos', 'vota', 'opina', 'gemelos', 'ajedrez', 'horoscopo',
         'recetas', 'moda', 'famosos']

SECCIONES = [
    {'id': 'industria',  'nombre': 'Industria',  'color': '#e65100'},
    {'id': 'politica',   'nombre': 'Política',   'color': '#1565c0'},
    {'id': 'deportes',   'nombre': 'Deportes',   'color': '#2e7d32'},
    {'id': 'sociedad',   'nombre': 'Sociedad',   'color': '#c2185b'},
    {'id': 'tecnologia', 'nombre': 'Tecnología', 'color': '#6a1b9a'},
    {'id': 'economia',   'nombre': 'Economía',   'color': '#f9a825'},
    {'id': 'cultura',    'nombre': 'Cultura',    'color': '#5d4037'},
]

# (url, palabras clave, sección por defecto si no encaja con la sección destino)
FUENTES = {
    'industria':  [(ELP + 'section/economia/portada',
                    ['industria', 'fábrica', 'empresa', 'producción', 'exporta',
                     'empleo', 'automóvil', 'acero', 'energía'], 'economia')],
    'politica':   [(ELP + 'section/espana/portada', [], 'politica')],
    'deportes':   [(ELP + 'section/deportes/portada', [], 'deportes')],
    'sociedad':   [(ELP + 'section/sociedad/portada', [], 'sociedad')],
    'tecnologia': [(ELP + 'section/tecnologia/portada', [], 'tecnologia')],
    'economia':   [(ELP + 'section/economia/portada', [], 'economia')],
    'cultura':    [(ELP + 'section/cultura/portada', [], 'cultura')],
}

# Secciones "estrictas": solo se aplican si el titular habla claramente de ellas
SECCIONES_ESTRICTAS = ('industria',)

# Pestañas por comunidad. La primera es Nacional; el resto son noticias locales
# obtenidas de Google News RSS (fuente pública, sin clave de API).
REGIONES = [
    {'id': 'nacional',            'nombre': 'Nacional'},
    {'id': 'andalucia',           'nombre': 'Andalucía'},
    {'id': 'aragon',              'nombre': 'Aragón'},
    {'id': 'asturias',            'nombre': 'Asturias'},
    {'id': 'cantabria',           'nombre': 'Cantabria'},
    {'id': 'castilla-leon',       'nombre': 'Castilla y León'},
    {'id': 'castilla-la-mancha',  'nombre': 'Castilla-La Mancha'},
    {'id': 'cataluna',            'nombre': 'Cataluña'},
    {'id': 'comunidad-valenciana','nombre': 'Comunidad Valenciana'},
    {'id': 'extremadura',         'nombre': 'Extremadura'},
    {'id': 'galicia',             'nombre': 'Galicia'},
    {'id': 'islas-baleares',      'nombre': 'Islas Baleares'},
    {'id': 'islas-canarias',      'nombre': 'Islas Canarias'},
    {'id': 'la-rioja',            'nombre': 'La Rioja'},
    {'id': 'madrid',              'nombre': 'Madrid'},
    {'id': 'murcia',              'nombre': 'Murcia'},
    {'id': 'navarra',             'nombre': 'Navarra'},
    {'id': 'pais-vasco',          'nombre': 'País Vasco'},
]
# Bing News RSS: incluye imagen y el enlace original del artículo
BING_NEWS = 'https://www.bing.com/news/search?q={q}&format=rss'
CONSULTAS_REGION = [
    '{nombre} noticias',
    '{nombre} política economía',
    '{nombre} deportes sociedad cultura tecnología',
]

# Detección de tema por palabras del titular, para no etiquetar mal una noticia
DETECTAR = [
    ('tecnologia', ['5g', 'inteligencia artificial', 'internet', 'digital',
                    'ciberseguridad', 'software', 'ordenador', 'móvil', 'datos']),
    ('deportes', ['fútbol', 'baloncesto', 'deporte', 'selección', 'champions',
                  'liga', 'atleta', 'olímpic']),
    ('politica', ['gobierno', 'elecciones', 'ministro', 'congreso', 'xunta',
                  'psoe', 'pp', 'parlamento', 'alcalde']),
    ('economia', ['empleo', 'salario', 'banco', 'bolsa', 'inversión', 'vivienda',
                  'inflación', 'pensiones']),
    ('cultura', ['cine', 'música', 'libro', 'cultura', 'teatro', 'arte', 'serie']),
]

# ------------------------------------------------------------------ utiles
def log(msg):
    linea = f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  {msg}'
    print(linea)
    with LOG.open('a', encoding='utf-8') as f:
        f.write(linea + '\n')


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    ultimo = None
    for intento in range(3):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read()
        except Exception as e:
            ultimo = e
            time.sleep(1 + intento)
    raise ultimo


def local(tag):
    return tag.split('}')[-1].lower()


def limpiar(texto, maxlen=None):
    if not texto:
        return ''
    texto = html.unescape(texto)
    texto = re.sub(r'<[^>]+>', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    if maxlen and len(texto) > maxlen:
        texto = texto[:maxlen].rsplit(' ', 1)[0] + '…'
    return texto


def hijo_texto(item, nombre):
    for c in item:
        if local(c.tag) == nombre and c.text:
            return c.text.strip()
    return ''


def fecha_de(item):
    raw = hijo_texto(item, 'pubdate') or hijo_texto(item, 'date')
    if not raw:
        return datetime.now(timezone.utc).isoformat()
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def cuerpo_de(item, entradilla, medio):
    crudo = ''
    for c in item:
        if local(c.tag) in ('encoded', 'content') and c.text and '<' in c.text:
            crudo = c.text
            break
    parrafos = []
    if crudo:
        for p in re.findall(r'<p[^>]*>(.*?)</p>', crudo, flags=re.S | re.I):
            t = limpiar(p, 700)
            if len(t) > 60:
                parrafos.append(t)
    if not parrafos and entradilla:
        parrafos.append(entradilla)
    if not parrafos:
        parrafos.append(f'Noticia publicada por {medio}. Consulta el artículo original para más información.')
    return parrafos[:3]


def score_keywords(texto, keywords):
    return sum(1 for k in keywords
               if re.search(r'\b' + re.escape(k) + r'\b', texto, flags=re.I))


def detectar_categoria(texto):
    t = normalizar_titulo(texto)
    for cat, palabras in DETECTAR:
        if any(re.search(r'\b' + re.escape(p) + r'\b', t) for p in palabras):
            return cat
    return ''


def og_image(url):
    try:
        pagina = fetch(url).decode('utf-8', 'ignore')[:400000]
        for patron in (r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
                       r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']'):
            m = re.search(patron, pagina, flags=re.I)
            if m:
                return html.unescape(m.group(1))
    except Exception:
        pass
    return ''


def imagen_de(item):
    for c in item:
        attrs = {local(k): v for k, v in c.attrib.items()}
        url = attrs.get('url') or attrs.get('src')
        if url and url.startswith('http'):
            return url
    for c in item:
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', c.text or '', flags=re.I)
        if m and m.group(1).startswith('http'):
            return m.group(1)
    return ''


def descargar_imagen(url, ident):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            ctype = (r.headers.get('Content-Type') or '').lower()
            datos = r.read(12 * 1024 * 1024)
        if not ctype.startswith('image/') or len(datos) < 2000:
            return ''
        imagen = Image.open(BytesIO(datos)).convert('RGB')
        imagen.thumbnail((1000, 640), Image.LANCZOS)
        salida = BytesIO()
        imagen.save(salida, 'JPEG', quality=78, optimize=True)
        nombre = ident + '.jpg'
        (IMGS / nombre).write_bytes(salida.getvalue())
        return 'imagenes/' + nombre
    except Exception as e:
        log(f'  ! imagen no descargada ({ident}): {str(e)[:90]}')
        return ''


def id_para(link):
    """ID único por noticia (ya no depende de la sección)."""
    return 'n-' + hashlib.md5(link.encode('utf-8')).hexdigest()[:11]


def medio_de(link):
    m = re.match(r'https?://(?:www\.)?([^/]+)', link)
    return m.group(1) if m else 'la fuente original'


def normalizar_link(link):
    return re.sub(r'[?#].*$', '', link).rstrip('/').lower()


def normalizar_titulo(titulo):
    t = html.unescape(titulo).lower()
    t = re.sub(r'[^a-záéíóúüñ0-9 ]', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()


# ------------------------------------------------------------------ RSS
def parsear_feed(url, sec, keywords, fallback):
    salida = []
    try:
        texto = fetch(url).decode('utf-8', 'ignore')
        texto = ''.join(c for c in texto if ord(c) > 31 or c in '\n\r\t')
        root = ET.fromstring(texto.encode('utf-8'))
    except Exception as e:
        log(f'  ! feed {url}: {str(e)[:100]}')
        return salida

    for item in root.findall('.//item'):
        titulo = limpiar(hijo_texto(item, 'title'), 180)
        link = hijo_texto(item, 'link')
        if not titulo or not link:
            continue
        fuente = medio_de(link)
        entradilla = limpiar(hijo_texto(item, 'description'), 240) or titulo
        score = score_keywords(titulo + ' ' + entradilla, keywords)
        sec_final = sec
        # En secciones estrictas solo cuenta el titular: mencionar "pescado al
        # horno" en la entradilla no convierte una noticia en pesquera.
        if sec in SECCIONES_ESTRICTAS and score_keywords(titulo, keywords) == 0:
            sec_final = detectar_categoria(titulo + ' ' + entradilla) or fallback
        salida.append({
            'id': id_para(link),
            'sec': sec_final,
            'region': 'nacional',
            'slot': 0,
            'titulo': titulo,
            'entradilla': entradilla,
            'cuerpo': cuerpo_de(item, entradilla, fuente),
            'autor': limpiar(hijo_texto(item, 'creator'), 60) or 'Redacción',
            'fecha': fecha_de(item),
            'image': '',
            'link': link,
            'medio': fuente,
            'viral': 0,
            '_score': score,
            '_imgurl': imagen_de(item),
            '_fuentes': 1,
        })
    return salida


def imagen_de_bing(item):
    for c in item:
        if local(c.tag) == 'image' and c.text and c.text.startswith('http'):
            return c.text
    return ''


def parsear_feed_region(url, region, nombre_region, forzar_sec=None):
    """Noticias locales desde Bing News RSS (con foto y enlace original)."""
    salida = []
    try:
        texto = fetch(url).decode('utf-8', 'ignore')
        texto = ''.join(c for c in texto if ord(c) > 31 or c in '\n\r\t')
        root = ET.fromstring(texto.encode('utf-8'))
    except Exception as e:
        log(f'  ! feed regional {nombre_region}: {str(e)[:100]}')
        return salida

    for item in root.findall('.//item'):
        titulo = limpiar(hijo_texto(item, 'title'), 180)
        enlace = hijo_texto(item, 'link')
        if not titulo or not enlace:
            continue
        # El enlace de Bing lleva la URL real en el parámetro ?url=
        link = parse_qs(urlparse(enlace).query).get('url', [enlace])[0]
        medio = limpiar(hijo_texto(item, 'source'), 60) or 'la fuente original'
        if titulo.endswith(' - ' + medio):
            titulo = titulo[:-(len(medio) + 3)].strip()
        entradilla = limpiar(hijo_texto(item, 'description'), 240) or titulo
        detectada = detectar_categoria(titulo)
        sec = forzar_sec or detectada or 'sociedad'
        salida.append({
            'id': id_para(link),
            'sec': sec,
            'region': region,
            'slot': 0,
            'titulo': titulo,
            'entradilla': entradilla,
            'cuerpo': [entradilla,
                       f'Noticia publicada por {medio}. Consulta el artículo original '
                       f'en {medio} para más información.'],
            'autor': 'Redacción',
            'fecha': fecha_de(item),
            'image': '',
            'link': link,
            'medio': medio,
            'viral': 0,
            '_detectada': bool(detectada),
            '_score': 0,
            '_imgurl': imagen_de_bing(item),
            '_fuentes': 1,
        })
    return salida


def imagen_respaldo(titulo):
    """Busca una imagen real por titular cuando el feed no la trae."""
    palabras = titulo.split()
    consultas = [' '.join(palabras[:8]), ' '.join(palabras[:5]), titulo[:60]]
    for consulta in consultas:
        if not consulta:
            continue
        try:
            url = BING_NEWS.format(q=quote(consulta))
            texto = fetch(url).decode('utf-8', 'ignore')
            root = ET.fromstring(texto.encode('utf-8'))
            for item in root.findall('.//item'):
                img = imagen_de_bing(item)
                if img:
                    return img
        except Exception:
            pass
    return ''


# ------------------------------------------------------------------ ranking
def peso_titulo(titulo):
    t = normalizar_titulo(titulo)
    plus = sum(1 for k in IMPORTANTES if re.search(r'\b' + re.escape(k) + r'\b', t))
    minus = sum(1 for k in RUIDO if re.search(r'\b' + re.escape(k) + r'\b', t))
    return max(-2, min(5, plus - minus))


def calcular_viral(n, menciones, ahora):
    try:
        f = datetime.fromisoformat(n['fecha'])
        if f.tzinfo is None:
            f = f.replace(tzinfo=timezone.utc)
    except Exception:
        f = ahora
    horas = max(0.0, (ahora - f).total_seconds() / 3600)
    frescura = max(0.0, 1 - horas / 48)
    fuentes = min(n.get('_fuentes', 1), 4) / 4
    mencion = min(menciones.get(normalizar_titulo(n['titulo']), 1), 3) / 3
    clave = min(n.get('_score', 0), 3) / 3
    peso = (peso_titulo(n['titulo']) + 2) / 7
    imagen = 0.05 if n.get('image') else 0
    return round(0.30 * frescura + 0.20 * fuentes + 0.32 * peso +
                 0.13 * clave + 0.05 * mencion + imagen, 4)


# ------------------------------------------------------------------ datos
def cargar_historico():
    if HISTORICO.exists():
        try:
            datos = json.loads(HISTORICO.read_text(encoding='utf-8'))
            for n in datos.get('noticias', []):
                n.setdefault('region', 'nacional')
                if 'lavozdegalicia' in (n.get('medio') or ''):
                    n['region'] = 'galicia'
            return datos
        except Exception as e:
            log(f'! histórico corrupto, se empieza de cero: {e}')
    return {'actualizado': '', 'noticias': [], 'top': []}


def cargar_manuales():
    """Noticias escritas a mano en datos/noticias-manuales.json (se editan en GitHub)."""
    if not MANUALES.exists():
        return []
    try:
        raw = json.loads(MANUALES.read_text(encoding='utf-8'))
    except Exception as e:
        log(f'! noticias-manuales.json corrupto, se ignoran: {e}')
        return []
    secciones_validas = {s['id'] for s in SECCIONES}
    salida = []
    for m in raw.get('noticias', []):
        titulo = limpiar(m.get('titulo', ''), 180)
        if not titulo:
            continue
        sec = m.get('sec', 'sociedad')
        if sec not in secciones_validas:
            sec = 'sociedad'
        idn = m.get('id') or ('m-' + hashlib.md5(titulo.encode('utf-8')).hexdigest()[:11])
        cuerpo = [limpiar(p, 700) for p in m.get('cuerpo', [])]
        cuerpo = [p for p in cuerpo if p]
        if not cuerpo:
            cuerpo = [limpiar(m.get('entradilla', ''), 240) or titulo]
        salida.append({
            'id': idn,
            'sec': sec,
            'region': m.get('region') or 'nacional',
            'slot': 0,
            'titulo': titulo,
            'entradilla': limpiar(m.get('entradilla', ''), 240) or titulo,
            'cuerpo': cuerpo[:3],
            'autor': limpiar(m.get('autor', ''), 60) or 'Redacción',
            'fecha': m.get('fecha') or datetime.now(timezone.utc).isoformat(),
            'image': m.get('image', ''),
            'link': m.get('link', ''),
            'medio': limpiar(m.get('medio', ''), 60) or 'Redacción propia',
            'viral': 0,
        })
    return salida


def guardar_historico(datos):
    DATOS.mkdir(parents=True, exist_ok=True)
    tmp = HISTORICO.with_suffix('.tmp')
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(tmp, HISTORICO)


def jstr(s):
    return json.dumps(s or '', ensure_ascii=False)


def generar_js(historico):
    JS.parent.mkdir(parents=True, exist_ok=True)
    secciones_js = ',\n'.join('  ' + json.dumps(s, ensure_ascii=False) for s in SECCIONES)
    regiones_js = ',\n'.join('  ' + json.dumps(r, ensure_ascii=False) for r in REGIONES)
    lines = [
        '/* ============================================================',
        '   TU VECINA COTILLA — Banco de noticias',
        '   Generado automáticamente por actualizar_noticias.py.',
        '   NO EDITAR A MANO: tus cambios se pierden en la próxima actualización.',
        '   ============================================================ */',
        '',
        'const ACTUALIZADO = ' + jstr(historico.get('actualizado', '')) + ';',
        '',
        'const SECCIONES = [',
        secciones_js,
        '];',
        '',
        'const REGIONES = [',
        regiones_js,
        '];',
        '',
        "const A = (id, sec, slot, titulo, entradilla, cuerpo, autor = 'Redacción',",
        "          fecha = '', image = '', link = '', medio = '', viral = 0,",
        "          region = 'nacional', url = '') => ({",
        '  id, sec, slot, titulo, entradilla, cuerpo, autor, fecha, image, link, medio, viral, region, url',
        '});',
        '',
        'const NOTICIAS = [',
    ]
    for sec in SECCIONES:
        items = [n for n in historico['noticias'] if n['sec'] == sec['id']]
        items.sort(key=lambda n: n['fecha'], reverse=True)
        lines.append(f'  /* -------- {sec["nombre"].upper()} -------- */')
        for i, n in enumerate(items):
            cuerpo = ', '.join(jstr(p) for p in n.get('cuerpo', []))
            lines.append(
                f"  A({jstr(n['id'])}, {jstr(n['sec'])}, {i}, "
                f"{jstr(n['titulo'])}, {jstr(n['entradilla'])}, "
                f"[{cuerpo}], {jstr(n.get('autor'))}, {jstr(n.get('fecha'))}, "
                f"{jstr(n.get('image'))}, {jstr(n.get('link'))}, "
                f"{jstr(n.get('medio'))}, {n.get('viral', 0)}, "
                f"{jstr(n.get('region', 'nacional'))}, {jstr(url_para(n))}),"
            )
    lines += ['];', '']
    JS.write_text('\n'.join(lines), encoding='utf-8')


def slug_para(n):
    base = re.sub(r'[^a-z0-9]+', '-', normalizar_titulo(n['titulo'])).strip('-')[:58].rstrip('-')
    return (base + '-' + n['id']) if base else n['id']


def url_para(n):
    return BASE_URL + 'noticias/' + slug_para(n) + '.html'


def generar_paginas(historico):
    """Crea una página HTML real por noticia, indexable por buscadores."""
    carpeta = BASE / 'noticias'
    carpeta.mkdir(exist_ok=True)
    usados = set()
    e = html.escape

    estilos = '''
<style>
body{margin:0;background:#eee;color:#111;font-family:Roboto,Arial,sans-serif;line-height:1.7}
.cabecera{background:#fff;border-bottom:4px solid #e30613;padding:18px 5%}
.cabecera a{color:#e30613;font-weight:700;text-decoration:none;font-family:'Roboto Condensed',Arial,sans-serif;font-size:22px;text-transform:uppercase}
.articulo{max-width:900px;margin:28px auto;background:#fff;padding:32px clamp(20px,5vw,56px) 48px;box-shadow:0 2px 14px rgba(0,0,0,.12)}
.seccion{display:inline-block;color:#fff;font:700 13px 'Roboto Condensed',Arial,sans-serif;text-transform:uppercase;padding:4px 10px;letter-spacing:.04em}
h1{font:900 clamp(30px,5vw,52px)/1.05 'Roboto Condensed',Arial,sans-serif;text-transform:uppercase;margin:16px 0}
.meta{color:#777;font-size:13px;text-transform:uppercase;border-top:1px solid #ddd;border-bottom:1px solid #ddd;padding:10px 0;margin-bottom:24px}
img.portada{width:100%;max-width:100%;height:auto;display:block;margin:0 0 24px}
.entradilla{font-size:20px;font-weight:700;line-height:1.5;border-left:4px solid #e30613;padding-left:16px}
.cuerpo p{font-size:19px;line-height:1.85;margin:0 0 22px}
.fuente,.volver{display:inline-block;margin:16px 12px 0 0;color:#b80510;font-weight:700}
.pie{max-width:900px;margin:0 auto 40px;padding:0 20px;color:#666;font-size:13px}
</style>'''

    for n in historico['noticias']:
        nombre = slug_para(n) + '.html'
        usados.add(nombre)
        url = url_para(n)
        titulo = n['titulo']
        titulo_seo = titulo if len(titulo) <= 60 else titulo[:57].rsplit(' ', 1)[0] + '…'
        descripcion = limpiar(n.get('entradilla') or titulo, 155)
        imagen = n.get('image') or ''
        img_url = BASE_URL + imagen if imagen else ''
        fecha = n.get('fecha', '')
        autor = n.get('autor') or 'Redacción'
        medio = n.get('medio') or 'Tu Vecina Cotilla'
        info_sec = next((s for s in SECCIONES if s['id'] == n['sec']), None)
        nombre_sec = info_sec['nombre'] if info_sec else n['sec']
        color = info_sec['color'] if info_sec else '#e30613'

        ld = {
            '@context': 'https://schema.org',
            '@type': 'NewsArticle',
            'headline': titulo,
            'description': descripcion,
            'datePublished': fecha,
            'dateModified': fecha,
            'author': {'@type': 'Person', 'name': autor},
            'publisher': {'@type': 'Organization', 'name': 'Tu Vecina Cotilla'},
            'mainEntityOfPage': url,
            'url': url,
            'articleSection': nombre_sec,
        }
        if img_url:
            ld['image'] = [img_url]
        ld_json = json.dumps(ld, ensure_ascii=False).replace('</', '<\\/')

        pagina = [
            '<!DOCTYPE html>', '<html lang="es">', '<head>',
            '  <meta charset="UTF-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1.0">',
            f'  <title>{e(titulo_seo)}</title>',
            f'  <meta name="description" content="{e(descripcion, quote=True)}">',
            f'  <link rel="canonical" href="{url}">',
            f'  <meta property="og:type" content="article">',
            f'  <meta property="og:title" content="{e(titulo, quote=True)}">',
            f'  <meta property="og:description" content="{e(descripcion, quote=True)}">',
            f'  <meta property="og:url" content="{url}">',
        ]
        if img_url:
            pagina.append(f'  <meta property="og:image" content="{img_url}">')
        pagina += [
            f'  <meta name="twitter:card" content="summary_large_image">',
            '  <script type="application/ld+json">' + ld_json + '</script>',
            '  <link rel="stylesheet" href="../css/styles.css">',
            estilos,
            '</head>', '<body>',
            '  <div class="cabecera"><a href="../index.html">Tu Vecina Cotilla — Inicio</a></div>',
            '  <article class="articulo">',
            f'    <span class="seccion" style="background:{color}">{e(nombre_sec)}</span>',
            f'    <h1>{e(titulo)}</h1>',
            f'    <div class="meta">{e(autor)} · {e(fecha[:10])} · {e(medio)}</div>',
        ]
        if imagen:
            pagina.append(f'    <img class="portada" src="../{imagen}" alt="{e(titulo, quote=True)}">')
        pagina.append(f'    <p class="entradilla">{e(n.get("entradilla") or titulo)}</p>')
        pagina.append('    <div class="cuerpo">')
        for parrafo in n.get('cuerpo', []):
            pagina.append(f'      <p>{e(parrafo)}</p>')
        pagina.append('    </div>')
        if n.get('link'):
            pagina.append(
                f'    <a class="fuente" href="{e(n["link"], quote=True)}" target="_blank" '
                f'rel="noopener noreferrer">Leer la noticia original en {e(medio)} ↗</a>')
        pagina += [
            '    <a class="volver" href="../index.html">← Volver a la portada</a>',
            '  </article>',
            '  <div class="pie">Tu Vecina Cotilla · Noticias de fuentes públicas RSS</div>',
            '</body>', '</html>',
        ]
        (carpeta / nombre).write_text('\n'.join(pagina), encoding='utf-8')

    borradas = 0
    for f in carpeta.glob('*.html'):
        if f.name not in usados:
            f.unlink()
            borradas += 1
    if borradas:
        log(f'Páginas estáticas: se borraron {borradas} archivos sin uso')


def generar_sitemap(historico):
    lineas = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        '  <url><loc>' + BASE_URL + '</loc><changefreq>daily</changefreq><priority>1.0</priority></url>',
    ]
    for n in historico['noticias']:
        fecha = (n.get('fecha') or '')[:10]
        lineas.append('  <url><loc>' + url_para(n) + '</loc><lastmod>' + fecha +
                      '</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>')
    lineas.append('</urlset>')
    (BASE / 'sitemap.xml').write_text('\n'.join(lineas), encoding='utf-8')
    (BASE / 'robots.txt').write_text(
        'User-agent: *\nAllow: /\n\nSitemap: ' + BASE_URL + 'sitemap.xml\n',
        encoding='utf-8')


def limpiar_imagenes(noticias):
    usadas = {Path(n['image']).name for n in noticias if n.get('image')}
    borradas = 0
    for f in IMGS.iterdir():
        if f.is_file() and f.name not in usadas:
            f.unlink()
            borradas += 1
    if borradas:
        log(f'Imágenes: se borraron {borradas} archivos sin uso')


# ------------------------------------------------------------------ main
def main():
    IMGS.mkdir(exist_ok=True)
    log('=== Inicio de actualización ===')
    ahora = datetime.now(timezone.utc)

    hist = cargar_historico()
    noticias = hist.get('noticias', [])

    # Noticias escritas a mano en GitHub: se reinsertan en cada ejecución para
    # que no se pierdan y siempre reflejen la última edición del JSON.
    manuales = cargar_manuales()
    ids_manuales = {n['id'] for n in manuales}
    noticias = [n for n in noticias if n['id'] not in ids_manuales]
    noticias.extend(manuales)
    # Todas las noticias publicadas deben tener foto real
    noticias = [n for n in noticias if n.get('image')]

    corte = (ahora - timedelta(days=DIAS_HISTORICO)).isoformat()
    noticias = [n for n in noticias if n.get('fecha', '') >= corte]
    noticias = [n for n in noticias if n.get('sec') != 'pesca']  # sección eliminada
    existentes = {n['id']: n for n in noticias}

    # 1) Recoger candidatos de todos los feeds, sin duplicados por enlace
    pool = {}
    for sec in ORDEN_CAPTURA:
        for url, keywords, fallback in FUENTES[sec]:
            candidatos = parsear_feed(url, sec, keywords, fallback)
            candidatos.sort(key=lambda n: (n['_score'], n['fecha']), reverse=True)
            for n in candidatos[:MAX_POR_SECCION]:
                clave = normalizar_link(n['link'])
                if clave in pool:
                    prev = pool[clave]
                    prev['_fuentes'] += 1
                    if n['_score'] > prev['_score']:
                        prev['sec'] = n['sec']
                        prev['_score'] = n['_score']
                    if not prev['_imgurl'] and n['_imgurl']:
                        prev['_imgurl'] = n['_imgurl']
                else:
                    n['_clave'] = clave
                    pool[clave] = n
        log(f'{sec:11} -> {len([v for v in pool.values() if v["sec"] == sec]):2} candidatos únicos')

    # 1a) Suplemento nacional con Bing: asegura 3 noticias por sección y foto
    for s in SECCIONES:
        url = BING_NEWS.format(q=quote('España ' + s['nombre']))
        for n in parsear_feed_region(url, 'nacional', 'España', forzar_sec=s['id']):
            clave = normalizar_link(n['link'])
            if clave not in pool:
                n['_clave'] = clave
                pool[clave] = n

    # 1b) Noticias locales de cada comunidad (Bing News RSS, con imagen)
    for reg in REGIONES[1:]:
        vistos = set()
        candidatos = []
        for plantilla in CONSULTAS_REGION:
            consulta = plantilla.format(nombre=reg['nombre'])
            for n in parsear_feed_region(
                    BING_NEWS.format(q=quote(consulta)), reg['id'], reg['nombre']):
                clave = normalizar_link(n['link'])
                if clave in vistos:
                    continue
                vistos.add(clave)
                candidatos.append(n)
        candidatos.sort(key=lambda n: n['fecha'], reverse=True)
        candidatos = candidatos[:MAX_POR_REGION]
        por_sec = {s['id']: [] for s in SECCIONES}
        sin_sec = []
        for n in candidatos:
            if n.get('_detectada') and len(por_sec[n['sec']]) < 3:
                por_sec[n['sec']].append(n)
            else:
                sin_sec.append(n)
        for s in SECCIONES:
            while len(por_sec[s['id']]) < 3 and sin_sec:
                por_sec[s['id']].append(sin_sec.pop(0))
        # Si aún falta material en alguna sección, se pide más a Bing
        for s in SECCIONES:
            if len(por_sec[s['id']]) >= 3:
                continue
            consulta = reg['nombre'] + ' ' + s['nombre']
            extra = parsear_feed_region(
                BING_NEWS.format(q=quote(consulta)), reg['id'], reg['nombre'],
                forzar_sec=s['id'])
            for n in extra:
                if len(por_sec[s['id']]) >= 3:
                    break
                clave = normalizar_link(n['link'])
                if clave not in vistos:
                    vistos.add(clave)
                    por_sec[s['id']].append(n)
        for items in por_sec.values():
            for n in items:
                clave = normalizar_link(n['link'])
                if clave not in pool:
                    n['_clave'] = clave
                    pool[clave] = n
        total_reg = len([v for v in pool.values() if v['region'] == reg['id']])
        log(f'{reg["nombre"][:22]:22} -> {total_reg:2} candidatos únicos')

    # 2) Descargar imagen de los candidatos nuevos
    restantes = [MAX_IMAGENES]
    nuevas = 0
    for n in pool.values():
        antiguo = existentes.get(n['id'])
        if antiguo and antiguo.get('image'):
            n['image'] = antiguo['image']
            continue
        if restantes[0] > 0:
            url = n['_imgurl']
            if not url and n.get('region', 'nacional') == 'nacional':
                url = og_image(n['link'])
            if not url:
                url = imagen_respaldo(n['titulo'])
            if url:
                n['image'] = descargar_imagen(url, n['id'])
                if not n['image']:
                    url2 = imagen_respaldo(n['titulo'])
                    if url2 and url2 != url:
                        n['image'] = descargar_imagen(url2, n['id'])
                if n['image']:
                    restantes[0] -= 1
        if not antiguo:
            nuevas += 1

    # 3) Fusionar con el archivo histórico
    for n in pool.values():
        idn = n['id']
        if idn in existentes:
            viejo = existentes[idn]
            if not viejo.get('image') and n.get('image'):
                viejo['image'] = n['image']
        else:
            noticias.append({k: v for k, v in n.items() if not k.startswith('_')})

    # 4) Ranking de viralidad y Top 10 del día
    menciones = Counter(normalizar_titulo(n['titulo']) for n in noticias)
    for n in noticias:
        n['viral'] = calcular_viral(n, menciones, ahora)
    noticias.sort(key=lambda n: n['fecha'], reverse=True)
    if len(noticias) > MAX_EN_ARCHIVO:
        log(f'Archivo: se recortaron {len(noticias) - MAX_EN_ARCHIVO} noticias antiguas')
        noticias = noticias[:MAX_EN_ARCHIVO]

    hoy = ahora.astimezone().date().isoformat()
    de_hoy = []
    for n in noticias:
        try:
            fhoy = datetime.fromisoformat(n['fecha']).astimezone().date().isoformat()
        except Exception:
            fhoy = ''
        if fhoy == hoy:
            de_hoy.append(n)
    de_hoy.sort(key=lambda n: (n['viral'], n['fecha']), reverse=True)
    top_ids = [n['id'] for n in de_hoy[:TOP_N]]
    if len(top_ids) < TOP_N:
        for n in noticias:
            if n['id'] not in top_ids and len(top_ids) < TOP_N:
                top_ids.append(n['id'])

    # 4b) Rellenar secciones vacías: todas las pestañas deben tener 3 por sección
    ids_actuales = {n['id'] for n in noticias}
    for reg in REGIONES:
        for s in SECCIONES:
            while len([n for n in noticias
                       if n['region'] == reg['id'] and n['sec'] == s['id']]) < 3:
                base = reg['nombre'] if reg['id'] != 'nacional' else 'España'
                consulta = base + ' ' + s['nombre']
                candidatos = parsear_feed_region(
                    BING_NEWS.format(q=quote(consulta)), reg['id'], reg['nombre'],
                    forzar_sec=s['id'])
                anadido = False
                for n in candidatos:
                    if n['id'] in ids_actuales:
                        continue
                    url = n['_imgurl'] or imagen_respaldo(n['titulo'])
                    img = descargar_imagen(url, n['id']) if url else ''
                    if not img:
                        continue
                    n['image'] = img
                    n['viral'] = calcular_viral(n, menciones, ahora)
                    noticias.append({k: v for k, v in n.items() if not k.startswith('_')})
                    ids_actuales.add(n['id'])
                    anadido = True
                    break
                if not anadido:
                    break
    noticias.sort(key=lambda n: n['fecha'], reverse=True)

    # Garantía final: ninguna noticia sin foto llega a la web
    noticias = [n for n in noticias if n.get('image')]
    hist['noticias'] = noticias
    hist['top'] = top_ids
    hist['actualizado'] = ahora.isoformat()
    guardar_historico(hist)
    generar_js(hist)
    generar_paginas(hist)
    generar_sitemap(hist)
    limpiar_imagenes(noticias)
    log(f'=== Fin: {nuevas} nuevas únicas, {len(noticias)} en archivo, '
        f'{sum(1 for n in noticias if n.get("image"))} con imagen, Top {len(top_ids)} ===')


if __name__ == '__main__':
    main()
