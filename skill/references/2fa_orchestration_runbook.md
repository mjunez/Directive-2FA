# 2FA Orchestration Runbook (agent side)

Verified-correct sequence for the agent when a sensitive action needs 2FA.
Bug reference: 2026-08-13, task t_5a21c429 — wait was launched BLOCKING in the
same turn the challenge_id had not yet been delivered; user interrupted the
wait, which also killed the background poller, leaving the challenge unguarded.

## Correct sequence (proven)
1. `2fa-stop` to clear stale pollers/waits. If the script lacks the exec bit,
   run it with `python3 /home/michael/.hermes/2fa/2fa-stop`.
2. Generate challenge: `python3 /home/michael/.hermes/2fa/2fa-challenger "<accion>"`.
   Capture challenge + nonce from the JSON.
3. Launch poller in BACKGROUND (terminal background=true):
   `python3 /home/michael/.hermes/2fa/2fa-poller --once <challenge>`
   Confirm it lives with `pgrep -af '[2]fa-poller'`.
4. DELIVER the challenge_id to the user IN THE SAME message — plain text, one
   piece per line (no code fences). Include the validator command. Never defer
   the ID to the next turn.
5. Launch the wait in BACKGROUND with notify_on_complete=true (NOT blocking):
   `python3 /home/michael/.hermes/2fa/2fa-wait <nonce> 295`
   This way the user sees nothing "hung" and the poller stays alive.
6. On CONFIRMED notification: verify on disk
   (`grep "nonce=<nonce>" ~/.hermes/2fa/executed.log` contains
   "ACCION AUTORIZADA"), then proceed autonomously.

## Hard rules
- wait is ALWAYS background; challenge_id is ALWAYS in the immediate message.
- Never couple the wait to the delivery turn.
- Kanban workspace cwd can vanish between turns
  (`/home/michael/.hermes/kanban/workspaces/<id>`). Run 2fa commands with a
  valid workdir (e.g. `/home/michael/.hermes`) to avoid
  "No such file or directory".
- 2FA authorizes INTENT only. Writing config.yaml/.env is still blocked by the
  file-guard independently of 2FA (pitfall 22/16): deliver the exact terminal
  command to the user and verify after with grep.
