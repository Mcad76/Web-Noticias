# Tu Vecina Cotilla — Portal de noticias

Diario web de actualidad con estilo de prensa española. Desarrollado y
actualizado íntegramente desde GitHub:
`https://github.com/Mcad76/Web-Noticias-` → `https://Mcad76.github.io/Web-Noticias-/`.

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

## Actualización automática (todo en GitHub, sin Termux)

El portal ya **no depende del móvil**. Un GitHub Action hace el trabajo en la nube:

- `.github/workflows/actualizar-noticias.yml` ejecuta `actualizar_noticias.py`
  cada día a las **07:30 UTC** y también bajo demanda.
- El Action instala `Pillow` desde `requirements.txt`, descarga las noticias y
  hace `commit` de `js/news-data.js`, `datos/historico.json` y `imagenes/`.
- Para actualizar **cuando quieras**: entra en la pestaña **Actions** del repo,
  elige *Actualizar noticias* y pulsa **Run workflow**.
- Para publicar la web: **Settings → Pages → Source: Deploy from a branch →
  main → /(root) → Save**. La web queda en
  `https://Mcad76.github.io/Web-Noticias-/`.

> El repo debe ser **público** para usar GitHub Pages en el plan gratis.
> GitHub puede retrasar unos minutos las ejecuciones programadas; el botón
> manual siempre funciona al instante.

### Añadir o editar noticias a mano desde GitHub

No edites `js/news-data.js` (se regenera solo). Edita
`datos/noticias-manuales.json` desde el editor web de GitHub y el siguiente
Action lo incorporará:

```json
{
  "noticias": [
    {
      "id": "mi-noticia-1",
      "sec": "sociedad",
      "titulo": "Titular de la noticia",
      "entradilla": "Resumen corto que aparece en la tarjeta.",
      "cuerpo": ["Primer párrafo...", "Segundo párrafo..."],
      "autor": "Redacción",
      "fecha": "2026-11-16T09:00:00+00:00",
      "image": "imagenes/nombre.jpg",
      "link": "https://...",
      "medio": "Tu Vecina Cotilla"
    }
  ]
}
```

`id` es opcional (si falta se genera a partir del titular). `sec` debe ser una
de: `industria`, `politica`, `deportes`, `sociedad`, `pesca`, `tecnologia`,
`economia`, `cultura`. `fecha` en formato ISO con zona horaria.

Si prefieres otro proveedor de noticias, edita el diccionario `FUENTES` de
`actualizar_noticias.py` (puedes mezclar varios feeds por sección). Para subir
cualquier cambio al repo: edítalo en GitHub y haz commit, o desde Termux con
`git add . && git commit -m "..." && git push`.

## Estructura

```
portal-noticias/
├── index.html                    Estructura de la página
├── css/styles.css                Diseño responsive
├── js/
│   ├── news-data.js              GENERADO: noticias reales + secciones
│   └── app.js                    Portada, secciones, archivo, modal y fuentes
├── .github/workflows/
│   └── actualizar-noticias.yml   GitHub Action: actualiza y hace commit
├── .nojekyll                     Evita que Pages procese el sitio con Jekyll
├── requirements.txt              Dependencias del Action (Pillow)
├── actualizar_noticias.py        Descarga RSS, imágenes y genera news-data.js
├── datos/
│   ├── historico.json            Archivo acumulado (generado)
│   └── noticias-manuales.json    Noticias escritas a mano en GitHub
├── imagenes/                     Fotos reales de las noticias (generado)
├── actualizar_diario.sh          (legado) ejecución manual local
├── programar_actualizacion.sh    (legado) instalaba el cron en Termux
└── actualizar_noticias.log       Registro de actualizaciones (no se sube)
```

## Cómo verlo

Ya publicado: **`https://Mcad76.github.io/Web-Noticias-/`**

Solo para probar en local antes de subir cambios:

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
