# Lecciones de la sesión 2026-07-13 (directive-2fa)

Captura técnica condensada. El SKILL.md raíz tiene pitfalls 1-15; aquí van 16-19.

## 16. Máscara por pipe se rompe con rama /dev/tty
Versión previa de `secure_input` abría `/dev/tty` cuando stdin no era TTY.
Eso SECUESTRABA el pipe: el validador leía de la consola del server en vez del
pipe y la clave no llegaba. Regla correcta:
- si stdin NO es tty → leer de stdin (los pipes no ecoan, nunca se expone).
- si stdin es tty → `getpass.getpass` (oculta por diseño, sin flag).
- NUNCA `input()` con eco. NUNCA abrir `/dev/tty` para recuperar el pipe.

## 17. Detección de cambio en SOUL.md sin depender de U+200B
El `.path` unit ya dispara en CUALQUIER edición de SOUL.md. Para que el agente
sepa del cambio (systemd NO puede empujar mensajes a la sesión de chat), el
script de soporte hace `touch <user_home>/.hermes/.soul_changed` SIEMPRE
(no solo al sanear U+200B). El agente, por turno, comprueba la marca:
- si existe / es más nueva que su último check → informa al usuario y pide
  permiso explícito para recargar las directivas, luego BORRA la marca.
- persistir mtime/hash de SOUL.md en MEMORIA (no sensible: metadata de archivo
  de config) para sobrevivir reinicios del Gateway.

Texto de directiva SOUL.md resultante (bloque `#SOUL.md`):
> Reloading SOUL.md after change — On each turn, the agent checks for a change
> marker at <user_home>/.hermes/.soul_changed (created by the soul-sanitize
> service whenever SOUL.md is modified). If present/newer than last check, in
> its next response inform the user and request explicit permission to reload
> and adopt the current directives. Do NOT adopt on its own initiative. After
> informing, clear the marker. Persist last-known mtime/hash in memory.

## 18. Sección 12 del SOUL.md = 2FA es infraestructura crítica
Tocar CUALQUIER componente del ecosistema 2FA (validator, challenger, poller,
wait, stop, scripts de sanitización de SOUL.md, el `.path`/`.service`) requiere
2FA COMPLETO primero, incluso para "mejorarlo". No sugerir alternativas que
eviten el 2FA. `hermes-soul-sanitize.sh` cuenta como parte del ecosistema.

## 19. Al tocar un script del sistema, actualiza su regenerador en bkp/
Los scripts en `<user_home>/.hermes/bkp/bkp_scripts/XX_*.py` son la fuente de
restauración (infra-como-script). Si modificas `/usr/local/bin/hermes-soul-sanitize.sh`
en vivo, refleja el cambio (p.ej. el `touch` de la marca) en el `SUPPORT_SCRIPT`
embebido del regenerador `01_hermes_soul_sanitize.py` y en el README. Así el bkp
nunca queda desactualizado respecto al sistema.

## Nota de colisión (curator)
Existen DOS skills `directive-2fa` (raíz y `system-administration/`). El de raíz
es el construido en esta sesión. Renombrar/fusionar para desambiguar (ver
"Nota de mantenimiento" en el SKILL.md raíz). Mientras tanto, los patches a
SKILL.md deben hacerse por ruta absoluta fuera del skill_manage o resolviendo
la colisión primero.
