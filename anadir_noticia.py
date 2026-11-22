#!/usr/bin/env python3
"""Añade una noticia desde un enlace y regenera el portal.

La llama el workflow .github/workflows/anadir-noticia.yml con las variables
INPUT_URL, INPUT_TITULO, INPUT_ENTRADILLA, INPUT_SECCION, INPUT_EXTRA e INPUT_AUTOR.
Sirve igual para Tu Vecina Cotilla y para AnimeChronicle: detecta el tipo de
portal por la presencia de GENEROS en actualizar_noticias.py.
"""
import json
import os
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import actualizar_noticias as gen

BASE = Path(__file__).resolve().parent
MANUAL = BASE / 'datos' / 'noticias-manuales.json'
UA = 'Mozilla/5.0 (compatible; MCadHub/1.0; +https://github.com/Mcad76/MCad-Hub)'


class MetaParser(HTMLParser):
    """Extrae og:title, og:description, og:image, site_name y <title>."""

    def __init__(self):
        super().__init__()
        self.datos = {}
        self._titulo = []
        self._en_titulo = False

    def handle_starttag(self, tag, attrs):
        atrib = dict(attrs)
        if tag.lower() == 'title':
            self._en_titulo = True
            return
        if tag.lower() != 'meta':
            return
        clave = (atrib.get('property') or atrib.get('name') or '').lower()
        utiles = ('og:title', 'twitter:title', 'og:description',
                  'twitter:description', 'description', 'og:image',
                  'twitter:image', 'og:image:secure_url', 'og:site_name',
                  'author')
        valor = atrib.get('content', '').strip()
        if clave in utiles and valor and clave not in self.datos:
            self.datos[clave] = valor

    def handle_data(self, dato):
        if self._en_titulo:
            self._titulo.append(dato)

    def handle_endtag(self, tag):
        if tag.lower() == 'title':
            self._en_titulo = False


def leer_metadatos(url):
    peticion = urllib.request.Request(url, headers={'User-Agent': UA,
                                                    'Accept-Language': 'es-ES,es;q=0.9'})
    with urllib.request.urlopen(peticion, timeout=25) as respuesta:
        html = respuesta.read(700_000).decode(respuesta.headers.get_content_charset()
                                              or 'utf-8', errors='replace')
    parser = MetaParser()
    parser.feed(html)
    if 'og:title' not in parser.datos and parser._titulo:
        parser.datos['og:title'] = ''.join(parser._titulo).strip()
    return parser.datos


def imagen_local_respaldo(ident, texto):
    """Crea una imagen propia si la fuente no trae foto (la web exige imagen)."""
    from PIL import Image, ImageDraw

    imagen = Image.new('RGB', (1000, 560), (24, 34, 48))
    dibujo = ImageDraw.Draw(imagen)
    dibujo.rectangle([0, 0, 1000, 12], fill=(255, 138, 61))
    dibujo.text((44, 250), 'MCad Hub', fill=(255, 255, 255))
    dibujo.text((44, 285), gen.limpiar(texto, 60), fill=(170, 190, 210))
    destino = gen.IMGS / f'{ident}.jpg'
    destino.parent.mkdir(parents=True, exist_ok=True)
    imagen.save(destino, 'JPEG', quality=82, optimize=True)
    return 'imagenes/' + ident + '.jpg'


def principal():
    url = os.environ.get('INPUT_URL', '').strip()
    if not url.startswith(('http://', 'https://')):
        raise SystemExit('Falta un enlace http(s) válido en INPUT_URL')

    meta = {}
    try:
        meta = leer_metadatos(url)
    except Exception as error:
        print('! No se pudieron leer los metadatos:', str(error)[:120])

    titulo = (gen.limpiar(os.environ.get('INPUT_TITULO', ''), 190)
              or gen.limpiar(meta.get('og:title') or meta.get('twitter:title', ''), 190)
              or url)
    entradilla = (gen.limpiar(os.environ.get('INPUT_ENTRADILLA', ''), 250)
                  or gen.limpiar(meta.get('og:description')
                                 or meta.get('twitter:description')
                                 or meta.get('description', ''), 250)
                  or titulo)

    es_anime = hasattr(gen, 'GENEROS')
    seccion = gen.limpiar(os.environ.get('INPUT_SECCION', ''), 40)
    if es_anime:
        validas = {s['id'] for s in gen.SECCIONES}
        seccion = seccion if seccion in validas else 'estrenos'
    else:
        validas = {s['id'] for s in gen.SECCIONES}
        seccion = seccion if seccion in validas else 'sociedad'

    extra = gen.limpiar(os.environ.get('INPUT_EXTRA', ''), 40)
    if es_anime:
        generos = {g['id'] for g in gen.GENEROS}
        extra = extra if extra in generos else 'todos'
    else:
        regiones = {r['id'] for r in gen.REGIONES}
        extra = extra if extra in regiones else 'nacional'

    ident = gen.id_para(url)
    img_url = (meta.get('og:image:secure_url') or meta.get('og:image')
               or meta.get('twitter:image', ''))
    imagen = gen.descargar_imagen(img_url, ident) if img_url else ''
    if not imagen:
        try:
            imagen = gen.imagen_respaldo(seccion if es_anime else titulo)
        except Exception:
            imagen = ''
    if not imagen:
        imagen = imagen_local_respaldo(ident, titulo)

    entrada = {
        'id': ident,
        'sec': seccion,
        'titulo': titulo,
        'entradilla': entradilla,
        'cuerpo': [entradilla],
        'autor': gen.limpiar(os.environ.get('INPUT_AUTOR', ''), 60) or 'MCad',
        'fecha': datetime.now(timezone.utc).isoformat(),
        'image': imagen,
        'link': url,
        'medio': gen.limpiar(meta.get('og:site_name') or gen.medio_de(url), 60),
        'viral': 0,
    }
    if es_anime:
        entrada['genero'] = extra
    else:
        entrada['region'] = extra

    MANUAL.parent.mkdir(parents=True, exist_ok=True)
    if MANUAL.exists():
        try:
            actual = json.loads(MANUAL.read_text(encoding='utf-8'))
        except Exception:
            actual = {'noticias': []}
    else:
        actual = {'noticias': []}
    noticias = [n for n in actual.get('noticias', []) if n.get('id') != ident]
    noticias.insert(0, entrada)
    actual['noticias'] = noticias[:60]
    MANUAL.write_text(json.dumps(actual, ensure_ascii=False, indent=2) + '\n',
                      encoding='utf-8')

    print(f'Noticia añadida: {titulo}')
    gen.main()


if __name__ == '__main__':
    principal()
