# secure_input — enmascaramiento OBLIGATORIO de la palabra clave 2FA

## Requisito duro (corrección del usuario, alta prioridad)
> "no quiero depender de un argumento para proteger la exposicion de la palabra
> clave a travez del comando interactivo... la palabra clave debe si o si ser
> tratada como un password y su input debe de reflejar esa premisa. Es muy
> critico para mi."

La clave 2FA **SIEMPRE** se trata como password: nunca se ecoa a nivel de
programa, por ninguna via de invocacion. No basta con `getpass` por defecto —
hay casos donde `getpass` retrocede a `input()` y hace eco. Hay que garantizar
el enmascaramado explícitamente.

## Dos vias seguras (ninguna expone la clave)
1. **Terminal interactiva** (`ssh -t`, shell local, PTY): desactivar `ECHO`
   con `termios` y leer carácter a carácter. El input queda VACIO en pantalla
   (sin `*`, sin texto).
2. **Pipe / archivo** (sin PTY, p.ej. `secret_get | ssh host validator`):
   leer de `stdin`. Los pipes NO ecoan nunca. **NO requiere `-t`**.

NUNCA usar `input()` con eco. NUNCA usar `getpass.getpass` como unica defensa
(ver pitfalls).

## Implementacion canónica (2FA-validator :: secure_input)
```python
import termios, os

def secure_input(prompt):
    sfd = None
    try:
        sfd = sys.stdin.fileno()
    except (OSError, ValueError, AttributeError):
        sfd = None
    has_tty = (sfd is not None and os.isatty(sfd))

    # Via 1: terminal interactiva -> ECHO off con termios
    if has_tty:
        fd = sfd
        old = termios.tcgetattr(fd)
        new = termios.tcgetattr(fd)
        new[3] = new[3] & ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSAFLUSH, new)
        try:
            os.write(fd, prompt.encode())
            buf = b""
            while True:
                ch = os.read(fd, 1)
                if ch in (b"", b"\n", b"\r"):
                    break
                if ch in (b"\x7f", b"\x08"):   # backspace / DEL
                    if buf:
                        buf = buf[:-1]
                    continue
                buf += ch
            return buf.decode(errors="replace")
        finally:
            termios.tcsetattr(fd, termios.TCSAFLUSH, old)

    # Via 2: sin terminal (pipe/archivo) -> leer stdin, no ecoa nunca
    if not sys.stdin.isatty():
        try:
            return sys.stdin.readline().rstrip("\n")
        except Exception:
            pass

    # Fallback: sin tty ni pipe legible -> RECHAZAR, no exponer
    print("Hubo un error con el proceso de 2FA")
    sys.exit(1)
```

## Pitfalls (raíz de los leaks que se corrigieron en sesión)
- **Pitfall A — fallback inseguro a getpass/input**: si `secure_input` caía en
  `getpass.getpass` cuando no habia TTY controlable, `getpass` emitia
  `GetPassWarning: Can not control echo ... Password input may be echoed` y
  retrocedia a `input()`, que HACE ECO. Sintoma visto: la clave aparecia en
  claro. Fix: no usar getpass como fallback; leer pipe (Via 2) o rechazar.
- **Pitfall B — `/dev/tty` secuestra el pipe**: una rama que abria `/dev/tty`
  cuando `stdin` no era TTY hizo que, en invocacion por pipe, el validador
  leyera de la CONSOLA del servidor en vez del pipe -> el pipe "no funcionaba"
  (validacion fallaba). Fix: si `stdin` no es TTY, asumir pipe y leer de ahi;
  NO intentar `/dev/tty`.
- **Pitfall C — `TCSADRAIN` vs `TCSAFLUSH`**: usar `TCSAFLUSH` para descartar
  input pendiente y evitar eco de caracteres en cola.

## Nota sobre eco LOCAL (limite honesto)
Cuando se TIPEA en una terminal real, el eco lo produce el terminal del
CLIENTE; solo se oculta si hay PTY (`ssh -t`). Para NO depender de `-t`, pasar
la clave por **pipe desde un secret-store** (Via 2) — ese camino queda
garantizado sin eco.

## Como validar el enmascaramado (test determinista)
- Via 1 (PTY): lanzar el validator bajo `pty.fork()`, escribir la clave por el
  fd, y afirmar que la salida NO contiene la clave (`ECO_LEAK == False`) y que
  valida (`OK`).
- Via 2 (pipe): `echo clave | python .venv/bin/2fa-validator <challenge>`
  (usar el binario del venv donde esta argon2) y afirmar `ECO_LEAK == False`
  y validacion OK.
- Usar SIEMPRE el binario del `.venv` (`2fa-validator` importa `argon2` solo
  ahi); con `python3` del sistema la verificacion falla y parece "pipe roto".
