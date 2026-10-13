# Como autorizar 2FA desde el cliente SSH (Windows / iOS)

El `challenge_id` es PUBLIC (puede viajar por el chat). Lo unico secreto es la
palabra clave que tecleas FUERA del chat. El agente NUNCA la ve.

## Prerrequisitos en el server (una sola vez)
- `sshd` activo: `sudo systemctl enable --now ssh`
- El usuario `michael` puede loguearse por SSH (password o, mejor, llave).
- Ruta del validador: `~/.hermes/2fa/2fa-validator`

## Windows
**OpenSSH nativo (Win10/11, sin instalar):** en PowerShell/CMD:
```
ssh michael@<host> '~/.hermes/2fa/2fa-validator <challenge_id>'
```
Aparece `Palabra clave 2FA:` (oculta) -> tecleas tu clave. Nada en el chat.
Alt: PuTTY/Termius -> conectas a `<host>` y corres el comando arriba.
Recomendado: usar llave SSH + passphrase (dos factores distintos).

## iOS
App: Termius (free) / Blink Shell / Prompt 2.
1. Crear host: `michael@<host>`, puerto 22, auth password o llave (Termius
   guarda llaves en el keychain del dispositivo).
2. Abrir sesion SSH.
3. En el shell del server: `~/.hermes/2fa/2fa-validator <challenge_id>`
4. `Palabra clave 2FA:` -> tecleas la clave en el telefono (campo oculto).

Este es el caso que resolvio el diseno: pides "revoca X" por Telegram, recibes
el `challenge_id` en el chat, y autorizas desde el movil via SSH (canal
separado del origen).

## Notas de seguridad
- `<challenge_id>` publico; solo la PALABRA CLAVE es secreta y se teclea en SSH.
- El validador corre en el server; escribe token file (mode 600) ahi.
- El agente no ve la clave ni actua por claims del chat.
