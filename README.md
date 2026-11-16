# Tu Vecina Cotilla — Portal de noticias

Diario web de actualidad con estilo de prensa española, alojado en
`/storage/emulated/0/Download/Opencode/portal-noticias`.

## Noticias reales, actualizadas cada día

El portal ya **no usa noticias de demostración ni fotos genéricas de Picsum**.

- `actualizar_noticias.py` descarga noticias reales de fuentes RSS públicas
  (El País y La Voz de Galicia, configurables en `FUENTES`).
- **Deduplicación global**: un mismo artículo se publica una sola vez, aunque
  aparezca en varios feeds o encaje en varias secciones.
- **Portada por categorías**: cada sección muestra sus **3 noticias más
  recientes y relevantes**. La relevancia combina frescura, presencia en varias
  fuentes y peso del titular. No hay números ni ranking visible.
- **Clasificación estricta**: Pesca e Industria solo se aplican si el titular
  habla claramente de ello; si no, la noticia pasa a su sección real (por
  ejemplo, una noticia del 5G va a Tecnología, no a Pesca).
- Extrae de cada noticia su **imagen original**, la guarda en `imagenes/` y la
  muestra en la tarjeta y en el artículo ampliado.
- Reescribe `js/news-data.js` con titular, entradilla, cuerpo, autor, fecha real
  y enlace a la fuente.
- Cada imagen se redimensiona a 1000×640 y se comprime para no llenar el móvil.
- El histórico se guarda en `datos/historico.json` (máximo 240 noticias y 30 días).

## Portada y publicidad

- Frase superior: **«TODOS LOS PERIÓDICOS EN UNO · ÚLTIMA ACTUALIDAD»**.
- Fila de **accesos directos** a las 8 categorías justo bajo la cabecera.
- Categorías con 3 noticias cada una; la **categoría aparece en una fila de
  color encima de la foto**, no superpuesta a la imagen.
- Tres huecos de publicidad: cabecera, entre secciones y pie de página, con el
  texto «PON AQUÍ TU PUBLICIDAD».
- Archivo con filtro, buscador y fecha real de publicación.

## Actualización automática

Instalada mediante `cron` de Termux (cronie), a las **07:30** todos los días:

```
30 7 * * * /data/data/com.termux/files/home/bin/actualizar-vecina
```

- Para reinstalar el trabajo: `bash programar_actualizacion.sh`
- Para actualizar ahora mismo: `bash actualizar_diario.sh`
- Para ver el log: `tail -f actualizar_noticias.log`
- Para ver los trabajos: `crontab -l`

> Como Android cierra procesos en segundo plano, el cron puede retrasarse si el
> teléfono lleva mucho tiempo apagado o en reposo profundo. Al abrir Termux se
> pone al día en el siguiente disparo; también puedes ejecutarlo a mano.

Si prefieres otro proveedor de noticias, edita el diccionario `FUENTES` de
`actualizar_noticias.py` (puedes mezclar varios feeds por sección).

## Estructura

```
portal-noticias/
├── index.html                 Estructura de la página
├── css/styles.css             Diseño responsive
├── js/
│   ├── news-data.js           GENERADO: noticias reales + secciones
│   └── app.js                 Portada, secciones, archivo, modal y fuentes
├── actualizar_noticias.py     Descarga RSS, imágenes y genera news-data.js
├── actualizar_diario.sh       Envuelve la ejecución diaria
├── programar_actualizacion.sh Instala el cron
├── datos/historico.json       Archivo acumulado (generado)
├── imagenes/                  Fotos reales de las noticias (generado)
└── actualizar_noticias.log    Registro de actualizaciones
```

## Cómo verlo

```bash
cd /storage/emulated/0/Download/Opencode/portal-noticias
python3 -m http.server 8899
```

y abre `http://localhost:8899` en el navegador.

## Secciones

Industria, Política, Deportes, Sociedad, Pesca, Tecnología, Economía y Cultura.
Cada día se muestran hasta 3 noticias recientes y relevantes por sección; el
resto queda consultable en el archivo, con filtro, buscador y fecha real de
publicación.
