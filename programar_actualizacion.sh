#!/data/data/com.termux/files/usr/bin/bash
# Instala la actualización diaria a las 07:30 mediante cron de Termux.
DIR="/storage/emulated/0/Download/Opencode/portal-noticias"
LANZADOR="/data/data/com.termux/files/home/bin/actualizar-vecina"

chmod +x "$DIR/actualizar_noticias.py" "$DIR/actualizar_diario.sh" "$LANZADOR"

# Sustituye cualquier entrada anterior de este proyecto
TMP="/data/data/com.termux/files/usr/tmp/cron-vecina.tmp"
(crontab -l 2>/dev/null | grep -v -e 'actualizar-cronica' -e 'actualizar-vecina') > "$TMP"
echo "30 7 * * * $LANZADOR >> \"$DIR/cron.log\" 2>&1" >> "$TMP"
crontab "$TMP"
rm -f "$TMP"

# Arrancar el demonio de cron si no está corriendo
pgrep -x crond >/dev/null 2>&1 || crond

echo "Actualización diaria programada a las 07:30."
echo "--- crontabActual ---"
crontab -l
