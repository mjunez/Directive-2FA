# Child lifecycle — 2fa-stop-childs

Canonical recipe for `2fa-stop-childs` (`~/.hermes/2fa/2fa-stop-childs`), the
owner of the 2FA-pure child processes (poller + webform server).

## What it owns
- `2fa-poller --once <challenge>` — ephemeral; waits for token, executes action.
- `webform_server.py` — optional browser frontend for the 2FA key entry.

It does NOT own `2fa-wait`. That process is the agent's CONFIRMED sensor and
self-terminates (see design note below). Keeping it out of stop-childs preserves
the separation: mechanism 2FA puro vs. agent-side orchestration.

## CLI
- `2fa-stop-childs stop` — kill any live poller + webform. Idempotent (reports
  "ninguno" if nothing was alive). Used by the agent at the END of the flow
  (after CONFIRMED/TIMEOUT) and internally by `start`.
- `2fa-stop-childs start <challenge>` — `stop` first, then launch a FRESH
  poller + webform for THIS challenge.

## Safety mechanisms
- **Bracket trick**: patterns are `[2]fa-poller` and `[w]ebform_server.py` so the
  `pgrep` command never matches its own literal. The script also excludes its
  own PID (`os.getpid()`).
- **SIGTERM then SIGKILL**: first a graceful SIGTERM to all matched PIDs, then
  after 0.4s a SIGKILL sweep for any survivors.

## KEY TECHNIQUE (why Popen, not a shell wrapper)
Children are launched with `subprocess.Popen([sys.executable, path, ...])`,
NOT via a `bash -c '...'` wrapper. Reason: the poller has an anti-duplicate
guard (`other_poller_watching()`) that runs `pgrep -af 2fa-poller` and treats
any line carrying the challenge string + a different PID as "another poller
already watching" → it exits immediately.

If the poller were launched by `terminal(background=true)` or any shell wrapper,
the wrapping `bash -c '... 2fa-poller --once <challenge> ...'` carries the
challenge in its cmdline with a DIFFERENT PID than the python child. The guard
then false-positives and the poller dies at once (symptom: "otro poller ya
vigila este challenge; salgo"). Launching via `subprocess.Popen` with the
challenge only in `argv` of the python child means pgrep sees ONE match (the
child, PID == me) and the guard does NOT exit. This is pitfall 25 — fixed by
moving the launch into code (2fa-stop-childs), never manual argv from a shell.

## 2fa-wait is agent-owned (design note)
- Launched by the agent with `notify_on_complete=true`.
- Self-terminates: `sys.exit(0)` on CONFIRMED, `sys.exit(1)` on TIMEOUT.
- Intentionally NOT in stop-childs' kill list. If you ever add it there, you
  break the agent's ability to receive the CONFIRMED notification.

## Verify all children are dead
```
pgrep -af '[2]fa-poller'      # none
pgrep -af '[2]fa-wait'        # none (agent-owned, already exited)
pgrep -af '[w]ebform_server.py'  # none
```
Never use `pgrep -f 'server.py'` (no bracket): the verification shell itself
contains 'server.py' and self-matches → false "VIVO".
