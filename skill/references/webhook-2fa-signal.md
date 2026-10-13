# Webhook 2FA Signal (Mecánica cross-sesión)

## Problema
`2fa-wait` corre desacoplado del agente (Popen detached, stdout devnull). El agente no puede confiar en stdout/background para saber cuándo confirmar. Necesita una señal mecánica que llegue a la sesión original.

## Solución aceptada: Webhook Hermes
Hermes expone webhook platform (port 8644 por defecto). El 2fa-wait puede POSTear a Hermes y el agente recibe la señal vía evento webhooks, no vía proceso hijo.

## Flujo objetivo
1. `2fa-challenger <accion>` crea challenge, lanza poller+webform+wait vía 2fa-stop-childs.
2. Wait espera executed.log.
3. Al CONFIRMED, wait hace:
   - POST a `http://localhost:8644/webhook/2fa-confirmed`
   - Auto-lanza `2fa-stop-childs stop` (cleanup)
   - Exit 0
4. Hermes webhook recibe POST → inyecta mensaje en sesión origen → agente revela respuesta.

## Configuración Hermes

```bash
# Habilitar webhooks
~/.hermes/config.yaml
platforms:
  webhook:
    enabled: true
    extra:
      port: 8644
      secret: "<SECRET>"
```

```bash
# Suscripción webhook 2FA
hermes webhook subscribe 2fa-confirmed \
  --prompt "2FA CONFIRMED: nonce {payload.nonce} - Challenge resuelto. Proceder con operación sensible." \
  --events "2fa_confirmed" \
  --deliver origin
```

## Implementación en 2fa-wait

Bloque post-confirmed:
```python
import urllib.request, json, time
payload = {"nonce": nonce, "timestamp": time.time()}
try:
    req = urllib.request.Request(
        "http://localhost:8644/webhook/2fa-confirmed",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-Webhook-Secret": SECRET}
    )
    urllib.request.urlopen(req, timeout=5)
except Exception:
    pass  # no bloquear confirmación
```

## Por qué no file-signal
Un archivo `signal/<nonce>.ready` vuelve a depender de que el agente esté mirando disco. El watcher es el propio 2fa-wait y eso es el bug original: el agente olvida lanzar wait. Webhook desacopla proceso hijo de sesión del agente.

## Pitfall
No usar `subprocess.Popen` sin stdout capturado para señal. stdout devnull = señal perdida. Usar webhook o mecanismo de evento de Hermes.
