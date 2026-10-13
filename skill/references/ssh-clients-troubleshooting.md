# Troubleshooting: clientes SSH (Windows / iOS) para 2FA-validator

Errores comunes al correr `2fa-validator` remotamente y sus fixes.

## Windows CMD / PowerShell

### Error: "The system cannot find the file specified."
Causas (en orden de probabilidad):
1. **`<host>` no reemplazado.** Si pegaste el comando con el literal `<host>`,
   Windows no resuelve esa "IP". Usa la IP real de Zorin (p.ej. `192.168.1.50`).
2. **Comillas simples.** CMD/PowerShell de Windows NO soporta comillas simples;
   las toma como literales y rompe el comando remoto. Usar comillas dobles.
3. **OpenSSH Client no instalado.** Si `ssh` dice "no se reconoce", habilitarlo:
   Configuración → Aplicaciones → Funciones opcionales → Agregar →
   "Cliente OpenSSH". O en PowerShell (admin):
   `Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0`

### Comando correcto (CMD de Windows)
```
ssh michael@192.168.1.XXX "~/.hermes/2fa/2fa-validator <challenge_id>"
```
- Reemplaza `192.168.1.XXX` por la IP real.
- Comillas DOBLES.
- El `<challenge_id>` es publico (puede ir en el chat).

### getpass sin TTY (solo en pruebas con pipe)
Si el validador se invoca con stdin redirigido (pipe), getpass cae a fallback y
MUESTRA la clave. Uso real es interactivo (SSH/terminal); nunca pipear la clave
en produccion. El pipe solo se usa en pruebas controladas con clave de prueba.

## iOS (Termius / Blink Shell / Prompt 2)
1. Crea host: `michael@<host>`, puerto 22, auth password o llave (keychain).
2. Abre la sesion SSH.
3. En el shell del server: `~/.hermes/2fa/2fa-validator <challenge_id>`
4. Teclea la palabra clave en el telefono (campo oculto).

## Nota de entorno (load_env_var)
Las sesiones SSH NO tienen `2FA_SECRET` en el entorno (el .env de Hermes no se
sources). El 2FA-validator lo lee directamente del .env parseando el archivo.
Si ves "verifier no configurado", el bug es que el validador no lee el .env —
revisar `load_env_var()` en 2fa-validator.
