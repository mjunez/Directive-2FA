# Directive 2FA Project

Framework de autenticación de dos factores con reacción automática del agente.

## Screenshots

![Webform Directive 2FA](docs/webform-screenshot.png)

*Webform de "Directive 2FA" mostrando STEP 1 – CHALLENGE ID activo, con campos Challenge ID y 2FA Key y soporte Enter key.*

## Archivos

```
Directive-2FA/
├── scripts/
│   ├── 2fa-challenger      # Genera challenge, lanza poller+webform
│   ├── 2fa-poller          # Espera token, ejecuta acción, log
│   ├── 2fa-validator       # Verifica clave (Argon2id) → token
│   ├── 2fa-wait            # Espera executed.log, cleanup, notifica
│   ├── 2fa-stop-childs     # Lifecycle manager (start/stop poller+webform)
│   ├── terminal_2fa.py     # Bridge PTY para validador terminal
│   └── webform_server.py   # Web UI "Directive 2FA" (puerto _2FA_WEB_PORT)
├── skill/
│   ├── SKILL.md            # Skill directive-2fa para Hermes
│   └── references/         # Documentación adicional
└── docs/
    └── webform-screenshot.png   # Captura UI
```