# 2FA Diagnostics (reference)

Casos reales de la sesion 2026-07-13 y como diagnosticarlos sin reventar el flujo.

## A. Validator da error al ingresar el Challenge ID

Sintoma reportado por el usuario: "el validator me da error cuando pongo el
challenge id". NO es (casi nunca) que el challenge sea invalido.

Causa real: TTY ausente. El validator CARGA el challenge, llega a
`secure_input()` (getpass) y revienta:

```
GetPassWarning: Can not control echo on the terminal.
Warning: Password input may be echoed.
termios.error: (25, 'Inappropriate ioctl for device')
```

Esto ocurre si se corrio SIN TTY: `ssh user@host "comando"` sin `-t`, o por
pipe/subshell no interactivo. Relacionado con pitfall 11 del SKILL.md.

Diagnostico seguro (no escribe token, NO incrementa lockout):

```bash
printf '' | ~/.hermes/2fa/2fa-validator <challenge>
```

- Si imprime `Palabra clave 2FA: ` y luego falla por EOF/termios => el challenge
  CARGO BIEN; solo falta TTY.
- Fix: `ssh -t michael@<host> "~/.hermes/2fa/2fa-validator <challenge>"` (la `-t`
  es obligatoria) o terminal local interactiva.
- NO regenerar el challenge por este error: se gasta el TTL y confunde al usuario.

## B. Falsa alarma de "poller huerfano resucitado"

Al inspeccionar procesos vivos con `pgrep -f 2fa-poller`, el propio shell del
agente coincide consigo mismo y devuelve un PID que CAMBIA en cada invocacion.
Usar el bracket trick para evitar auto-match:

```bash
pgrep -af '[2]fa-poller'   # reales, si los hay
pgrep -af '[2]fa-wait'     # reales, si los hay
```

`2fa-stop` ya aplica este patron internamente.

## C. Verificar autorizacion por disco, no por exit code

Las notificaciones de proceso en background traen exit code del entorno
(137/143 = SIGTERM, -9 = kill) que NO reflejan CONFIRMED/TIMEOUT del 2FA.
Tras cualquier notificacion, leer:

```bash
grep "<nonce>" ~/.hermes/2fa/executed.log
ls ~/.hermes/2fa/pending/ ~/.hermes/2fa/tokens/   # deben quedar vacios
```

Solo revelar si `executed.log` contiene `ACCION AUTORIZADA ... nonce=<nonce>`.

## D. Entrega del challenge por Telegram

El cliente del usuario no muestra boton "copiar" en code blocks. Entregar el
challenge y el comando como TEXTO PLANO, UNA PIEZA POR MENSAJE (ver pitfall 20
del SKILL.md). Generar el challenge solo cuando el usuario diga "ahora" para no
gastar el TTL de 5 min entre mensajes.
