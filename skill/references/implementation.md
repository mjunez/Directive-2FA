# directive-2fa — Implementation Notes (REALES)

## Race condition (BUG CRITICO encontrado y corregido en build)
Sintoma: validator escribe token, pero poller no ejecuta la accion y deja token
huerfano + pending viejo.
Causa: 2FA-validator borraba `pending/<challenge>.json` al validar OK. El poller
itera `pending/*.json` para saber la accion; al haberse borrado, no ejecuta.
Fix: validator SOLO escribe `tokens/<challenge>.token` (mode 600) y resetea fails.
El poller, al ver el token, ejecuta la accion desde el pending y luego borra token+pending.

## Receta de testing END-TO-END (sin clave real, cumple L210)
```bash
BASE=~/.hermes/2fa; VENV=$BASE/.venv
TEST_HASH=$($VENV/bin/python -c "from argon2 import PasswordHasher; print(PasswordHasher().hash('clave_prueba_DEMO'))")
CHALLENGE=$($VENV/bin/python $BASE/2fa-challenger "revocar L208 (PRUEBA)")
printf 'clave_prueba_DEMO\n' | env "2FA_SECRET=$TEST_HASH" $VENV/bin/python $BASE/2fa-validator "$CHALLENGE"
sleep 4
cat $BASE/executed.log
ls $BASE/tokens $BASE/pending
```
FALLO: clave incorrecta -> exit 1 + "Hubo un error con el proceso de 2FA".

## Parametros Argon2id (verifier en 2FA_SECRET)
- argon2id, m=19456 KiB (~19MB, piso OWASP; NO 19 solo=19KiB), t=2, p=1, hash_len=16
- salt 16 bytes. Formato Encoded: $argon2id$v=19$m=19456,t=2,p=1$SALT$HASH
- Validar con PasswordHasher().verify(encoded, key). NUNCA comparar a mano.

## Instalacion entorno (Zorin: Python sin pip/venv)
sudo apt-get install -y python3.12-venv
python3 -m venv ~/.hermes/2fa/.venv
~/.hermes/2fa/.venv/bin/pip install argon2-cffi

## Persistencia poller
nohup ~/.hermes/2fa/.venv/bin/python ~/.hermes/2fa/2fa-poller > ~/.hermes/2fa/poller.log 2>&1 &
NO es systemd; relanzar manualmente tras reinicio (o crear unit systemd aparte).
