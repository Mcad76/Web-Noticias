#!/data/data/com.termux/files/usr/bin/bash
# Script que ejecuta el programador de tareas de Termux una vez al día.
DIR="/storage/emulated/0/Download/Opencode/portal-noticias"
PY="/data/data/com.termux/files/usr/bin/python3"
cd "$DIR" || exit 1
"$PY" "$DIR/actualizar_noticias.py" >> "$DIR/actualizar_noticias.log" 2>&1
