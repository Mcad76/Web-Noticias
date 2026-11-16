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
LOG = BASE / 'actualizar_noticias.log'

ELP = 'https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/'
UA = 'Mozilla/5.0 (compatible; TuVecinaCotilla/2.0; +RSS)'
TIMEOUT = 20
MAX_POR_SECCION = 12      # candidatos por sección y fuente
MAX_IMAGENES = 160        # descargas de imagen por ejecución
DIAS_HISTORICO = 30
MAX_EN_ARCHIVO = 240
TOP_N = 10                # noticias del ranking diario

# Orden de captura: primero las secciones con feed propio, para que las que
# comparten feed (industria, pesca) no se queden sin material.
ORDEN_CAPTURA = ['politica', 'deportes', 'sociedad', 'tecnologia',
                 'cultura', 'economia', 'industria', 'pesca']

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
    {'id': 'pesca',      'nombre': 'Pesca',      'color': '#00838f'},
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
    'pesca':      [('https://www.lavozdegalicia.es/galicia/index.xml',
                    ['pesca', 'pescado', 'pescador', 'flota', 'lonja',
                     'acuicultura', 'atún', 'sardina', 'ría', 'marisc'], 'sociedad'),
                   (ELP + 'section/economia/portada',
                    ['pesca', 'pescado', 'pescador', 'flota', 'lonja',
                     'acuicultura', 'atún', 'sardina'], 'economia')],
    'tecnologia': [(ELP + 'section/tecnologia/portada', [], 'tecnologia')],
    'economia':   [(ELP + 'section/economia/portada', [], 'economia')],
    'cultura':    [(ELP + 'section/cultura/portada', [], 'cultura')],
}

# Secciones "estrictas": solo se aplican si el titular habla claramente de ellas
SECCIONES_ESTRICTAS = ('pesca', 'industria')

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
            return json.loads(HISTORICO.read_text(encoding='utf-8'))
        except Exception as e:
            log(f'! histórico corrupto, se empieza de cero: {e}')
    return {'actualizado': '', 'noticias': [], 'top': []}


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
        "const A = (id, sec, slot, titulo, entradilla, cuerpo, autor = 'Redacción',",
        "          fecha = '', image = '', link = '', medio = '', viral = 0) => ({",
        '  id, sec, slot, titulo, entradilla, cuerpo, autor, fecha, image, link, medio, viral',
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
                f"{jstr(n.get('medio'))}, {n.get('viral', 0)}),"
            )
    lines += ['];', '']
    JS.write_text('\n'.join(lines), encoding='utf-8')


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
    corte = (ahora - timedelta(days=DIAS_HISTORICO)).isoformat()
    noticias = [n for n in noticias if n.get('fecha', '') >= corte]
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

    # 2) Descargar imagen de los candidatos nuevos
    restantes = [MAX_IMAGENES]
    nuevas = 0
    for n in pool.values():
        antiguo = existentes.get(n['id'])
        if antiguo and antiguo.get('image'):
            n['image'] = antiguo['image']
            continue
        if restantes[0] > 0:
            url = n['_imgurl'] or og_image(n['link'])
            if url:
                n['image'] = descargar_imagen(url, n['id'])
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

    hist['noticias'] = noticias
    hist['top'] = top_ids
    hist['actualizado'] = ahora.isoformat()
    guardar_historico(hist)
    generar_js(hist)
    limpiar_imagenes(noticias)
    log(f'=== Fin: {nuevas} nuevas únicas, {len(noticias)} en archivo, '
        f'{sum(1 for n in noticias if n.get("image"))} con imagen, Top {len(top_ids)} ===')


if __name__ == '__main__':
    main()
