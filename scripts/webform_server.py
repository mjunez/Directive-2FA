#!/usr/bin/env python3
"""Integrated 2FA web server — wires the web layer to the terminal bridge.

This module integrates the web UI scaffold (task 0) with the terminal 2FA
bridge (task 1, ``terminal_2fa``):

  * POST /step1  -> bridge.begin(challenge_id)  -> unlock step 2 on success.
  * POST /step2  -> bridge.complete(twofa_key)  -> terminate server on success.

SECURITY INVARIANTS (inherited from the bridge, enforced here):
  * No secret (challenge nonce, token, or 2FA key) is ever echoed, logged, or
    returned. The web layer only ever sees a boolean status: ok / fail.
  * The 2FA key travels from the form to the PTY-masked validator and is never
    written to logs, status text, or responses.
  * On successful verification the server process terminates itself (the
    "validation window" closes and the process exits).

The form is only active during the 2FA validation window: step 2 is locked
until step 1 succeeds, and the whole form locks once step 2 is submitted
(success -> process exits; failure -> step 1 re-opens for a fresh challenge).

Usage:
    python3 server.py [port]

If no port is given, an ephemeral port is chosen by the OS (port 0).
The chosen port is printed to stdout as ``LISTENING_ON_PORT=<n>``.
"""

import json
import os
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Make the sibling terminal-2FA module importable. The bridge (terminal_2fa.py)
# lives in the same directory as this consolidated server, so we resolve its
# location relative to this file instead of hardcoding a per-task workspace path.
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import terminal_2fa as t2fa  # noqa: E402

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Directive 2FA</title>
  <style>
    :root {
      --bg: #0f1117;
      --card: #181b24;
      --card-2: #1f2330;
      --border: #2a2f3d;
      --text: #e6e9ef;
      --muted: #8b92a5;
      --accent: #5b8cff;
      --accent-2: #3a6bff;
      --ok: #36d39a;
      --fail: #ff6b6b;
      --term-bg: #0b0e14;
      --term-glow: #4ef0a3;
    }
    * { box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, system-ui, sans-serif;
      background: radial-gradient(1200px 600px at 50% -10%, #1a2030 0%, var(--bg) 60%);
      color: var(--text);
      min-height: 100vh;
      margin: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 2rem 1rem;
    }
    .shell {
      width: 100%;
      max-width: 440px;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 1.5rem;
      box-shadow: 0 20px 60px rgba(0,0,0,0.45);
    }
    h1 {
      font-size: 1.15rem;
      margin: 0 0 0.25rem;
      letter-spacing: 0.2px;
    }
    .subtitle { color: var(--muted); font-size: 0.85rem; margin: 0 0 1.25rem; }
    .step {
      background: var(--card-2);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem;
      margin-bottom: 0.9rem;
      transition: opacity 0.2s ease, box-shadow 0.2s ease;
    }
    .step legend, .step .legend {
      font-weight: 600;
      font-size: 0.82rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.6px;
      margin-bottom: 0.6rem;
      display: block;
    }
    label { display: block; margin-bottom: 0.35rem; font-size: 0.85rem; color: var(--text); }
    input {
      width: 100%;
      padding: 0.65rem 0.75rem;
      background: #0e1118;
      border: 1px solid var(--border);
      border-radius: 9px;
      color: var(--text);
      font-size: 0.95rem;
      outline: none;
      transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }
    input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(91,140,255,0.18); }
    button {
      margin-top: 0.7rem;
      width: 100%;
      padding: 0.7rem 1rem;
      background: linear-gradient(180deg, var(--accent) 0%, var(--accent-2) 100%);
      color: white;
      border: none;
      border-radius: 9px;
      font-size: 0.92rem;
      font-weight: 600;
      cursor: pointer;
      transition: transform 0.05s ease, filter 0.15s ease;
    }
    button:hover:not(:disabled) { filter: brightness(1.08); }
    button:active:not(:disabled) { transform: translateY(1px); }
    input:disabled, button:disabled, .step.disabled {
      opacity: 0.45;
      cursor: not-allowed;
    }
    .step.active { box-shadow: 0 0 0 1px var(--accent), 0 0 0 4px rgba(91,140,255,0.12); }

    /* Terminal-style status window */
    .terminal {
      margin-top: 1.1rem;
      border-radius: 12px;
      overflow: hidden;
      border: 1px solid #000;
      box-shadow: 0 10px 30px rgba(0,0,0,0.5);
      background: var(--term-bg);
    }
    .terminal .bar {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.55rem 0.75rem;
      background: linear-gradient(180deg, #2a2f3d 0%, #1c2030 100%);
      border-bottom: 1px solid #000;
    }
    .terminal .dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
    .terminal .dot.r { background: #ff5f56; }
    .terminal .dot.y { background: #ffbd2e; }
    .terminal .dot.g { background: #27c93f; }
    .terminal .bar-title { color: #b9c0d4; font-size: 0.78rem; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    .terminal .screen {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.82rem;
      line-height: 1.45;
      color: var(--term-glow);
      background: var(--term-bg);
      padding: 0.85rem 0.9rem;
      height: 9rem;
      overflow-y: auto;
      white-space: pre-wrap;
      text-shadow: 0 0 6px rgba(78,240,163,0.25);
    }
    .terminal .screen .line { display: block; }
    .terminal .screen .ts { color: #5b6b7a; }
    .terminal .screen .ok { color: var(--ok); }
    .terminal .screen .fail { color: var(--fail); }
    .terminal .screen .cursor {
      display: inline-block; width: 8px; height: 1em; vertical-align: -2px;
      background: var(--term-glow); animation: blink 1.1s step-end infinite;
    }
    @keyframes blink { 50% { opacity: 0; } }
  </style>
</head>
<body>
  <div class="shell">
    <h1>Directive 2FA</h1>
    <p class="subtitle">Two-step secure identity check.</p>

    <fieldset id="fs-step1" class="step">
      <span class="legend">Step 1 &mdash; Challenge ID</span>
      <label for="challenge">Challenge ID</label>
      <input id="challenge" type="text" autocomplete="off" />
      <button id="submit-step1" type="button">Submit Challenge</button>
    </fieldset>

    <fieldset id="fs-step2" class="step disabled" disabled>
      <span class="legend">Step 2 &mdash; 2FA Key</span>
      <label for="twofa">2FA Key</label>
      <input id="twofa" type="password" autocomplete="off" disabled />
      <button id="submit-step2" type="button" disabled>Submit 2FA</button>
    </fieldset>

    <div class="terminal">
      <div class="bar">
        <span class="dot r"></span><span class="dot y"></span><span class="dot g"></span>
        <span class="bar-title">status — verification.log</span>
      </div>
      <div id="status" class="screen"><span class="cursor"></span></div>
    </div>
  </div>

  <script>
    const statusEl = document.getElementById('status');
    const challengeInput = document.getElementById('challenge');
    const twofaInput = document.getElementById('twofa');
    const fsStep1 = document.getElementById('fs-step1');
    const fsStep2 = document.getElementById('fs-step2');
    const btnStep1 = document.getElementById('submit-step1');
    const btnStep2 = document.getElementById('submit-step2');

    // Only non-revealing status text is ever shown. Never echo the challenge,
    // the key, or raw response bodies.
    function log(msg) {
      const ts = new Date().toLocaleTimeString();
      const line = document.createElement('span');
      line.className = 'line';
      const lower = msg.toLowerCase();
      const kind = lower.includes('successful') ? 'ok'
                 : lower.includes('fail') || lower.includes('invalid') || lower.includes('error') ? 'fail'
                 : '';
      line.innerHTML = '<span class="ts">[' + ts + ']</span> <span class="' + kind + '">' + msg + '</span>';
      // Drop the live cursor, append the new line, re-add cursor.
      const cursor = statusEl.querySelector('.cursor');
      if (cursor) statusEl.removeChild(cursor);
      statusEl.appendChild(line);
      statusEl.appendChild(document.createElement('span')).className = 'cursor';
      statusEl.scrollTop = statusEl.scrollHeight;
    }

    async function postJSON(path, payload) {
      const res = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      let status = 'unknown';
      try { const j = await res.json(); status = j && j.status; } catch (e) {}
      return { ok: res.ok, status: status };
    }

    function setStep(step, enabled) {
      const fs = step === 1 ? fsStep1 : fsStep2;
      fs.disabled = !enabled;
      fs.classList.toggle('disabled', !enabled);
      fs.classList.toggle('active', enabled);
    }

    function lockAll() {
      challengeInput.disabled = true;
      twofaInput.disabled = true;
      setStep(1, false);
      setStep(2, false);
      btnStep1.disabled = true;
      btnStep2.disabled = true;
    }

    function openStep1() {
      setStep(1, true);
      setStep(2, false);
      challengeInput.disabled = false;
      twofaInput.disabled = true;
      btnStep1.disabled = false;
      btnStep2.disabled = true;
      challengeInput.focus();
    }

    btnStep1.addEventListener('click', async () => {
      const challenge = challengeInput.value.trim();
      if (!challenge) { log('Challenge ID is required.'); return; }
      btnStep1.disabled = true;
      log('Submitting Challenge ID...');
      try {
        const r = await postJSON('/step1', { challenge_id: challenge });
        if (r.ok && r.status === 'ok') {
          // Step 1 accepted: open the validation window (step 2).
          challengeInput.disabled = true;
          setStep(1, false);
          setStep(2, true);
          twofaInput.disabled = false;
          btnStep2.disabled = false;
          twofaInput.focus();
          log('Step 1 complete. Enter your verification key.');
        } else {
          btnStep1.disabled = false;
          log('Step 1 failed. Check the Challenge ID and try again.');
        }
      } catch (e) {
        btnStep1.disabled = false;
        log('Step 1 error: unable to reach the server.');
      }
    });

    // Enter key support for Step 1
    challengeInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !btnStep1.disabled) {
        btnStep1.click();
      }
    });

    btnStep2.addEventListener('click', async () => {
      const twofa = twofaInput.value.trim();
      if (!twofa) { log('Verification key is required.'); return; }
      btnStep2.disabled = true;
      log('Submitting verification key...');
      try {
        const r = await postJSON('/step2', { twofa_key: twofa });
        if (r.ok && r.status === 'ok') {
          lockAll();
          log('Verification successful.');
          // The server process will now terminate.
        } else {
          // Step 2 failed: validation window closed. Re-open step 1 only.
          lockAll();
          btnStep1.disabled = false;
          challengeInput.disabled = false;
          setStep(1, true);
          log('Verification failed. Enter a new Challenge ID to retry.');
        }
      } catch (e) {
        lockAll();
        log('Verification error: unable to reach the server.');
      }
    });

    // Enter key support for Step 2
    twofaInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !btnStep2.disabled) {
        btnStep2.click();
      }
    });

    // Initialize visual step state to match the disabled attributes at load.
    setStep(1, !fsStep1.disabled);
    setStep(2, !fsStep2.disabled);
    log('Ready. Enter your Challenge ID to begin.');
  </script>
</body>
</html>
"""


# --- Shared state -----------------------------------------------------------

_BRIDGE = None          # Terminal2FABridge instance used by the handler.
_SERVER = None          # ThreadingHTTPServer instance (for graceful shutdown).
_BRIDGE_LOCK = threading.Lock()
_SHUTDOWN_HOOK = None   # Real success hook; fired AFTER the 200 response flushes.


def _default_shutdown_hook():
    """Success hook: stop the web server and terminate this process.

    Called by the handler on successful 2FA verification, AFTER the 200
    response has been written to the client. The bridge lives inside this
    server process, so we terminate *ourselves*.
    """
    srv = _SERVER
    if srv is not None:
        try:
            srv.shutdown()
        except Exception:
            pass
    # Backstop: hard-exit after the just-sent 200 response has flushed, in
    # case shutdown did not fully unwind the serve_forever loop.
    pid = os.getpid()

    def _terminate():
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    threading.Timer(1.0, _terminate).start()


def init_bridge(shutdown_hook=None):
    """Create and install the bridge. Override the hook only for testing.

    The bridge is wired with a no-op shutdown so that the success-triggered
    process exit is driven by this server module *after* the HTTP 200 response
    is flushed to the client (avoids closing the socket mid-response).
    """
    global _BRIDGE, _SHUTDOWN_HOOK
    hook = shutdown_hook if shutdown_hook is not None else _default_shutdown_hook
    _SHUTDOWN_HOOK = hook
    _BRIDGE = t2fa.Terminal2FABridge(shutdown_hook=lambda: None)
    return _BRIDGE


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(min(length, 1 << 20))
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._send_html()
        else:
            self._send_json(404, {"status": "not_found"})

    def _send_html(self):
        body = INDEX_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_POST(self):
        if self.path not in ("/step1", "/step2"):
            self._send_json(404, {"status": "not_found"})
            return

        data = self._read_json()
        if data is None:
            # Malformed body — never echo it.
            self._send_json(400, {"status": "error"})
            return

        bridge = _BRIDGE
        if bridge is None:
            self._send_json(500, {"status": "error"})
            return

        if self.path == "/step1":
            self._handle_step1(bridge, data)
        else:
            self._handle_step2(bridge, data)

    def _handle_step1(self, bridge, data):
        challenge_id = data.get("challenge_id")
        if not isinstance(challenge_id, str) or not challenge_id.strip():
            self._send_json(400, {"status": "error"})
            return
        try:
            with _BRIDGE_LOCK:
                accepted = bridge.begin(challenge_id.strip())
        except FileNotFoundError:
            # Validator binary missing — report generic failure, no detail.
            self._send_json(403, {"status": "fail"})
            return
        if accepted:
            self._send_json(200, {"status": "ok"})
        else:
            self._send_json(403, {"status": "fail"})

    def _handle_step2(self, bridge, data):
        twofa_key = data.get("twofa_key")
        if not isinstance(twofa_key, str) or not twofa_key:
            self._send_json(400, {"status": "error"})
            return
        try:
            with _BRIDGE_LOCK:
                ok = bridge.complete(twofa_key)
        except Exception:
            # Any unexpected error is reported as a generic failure.
            self._send_json(403, {"status": "fail"})
            return
        if ok:
            # Response first, then trigger the process exit (validation window
            # closes and the web server process terminates).
            self._send_json(200, {"status": "ok"})
            hook = _SHUTDOWN_HOOK
            if callable(hook):
                threading.Thread(target=hook, daemon=True).start()
        else:
            self._send_json(403, {"status": "fail"})

    def log_message(self, fmt, *args):
        # Logs the request line only (never the body, never secrets).
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main():
    # Port resolution order:
    #   1. Explicit CLI arg:  python3 server.py 8080
    #   2. Environment var _2FA_WEB_PORT (set by the user in .env)
    #   3. Fallback to 0 (ephemeral; OS assigns a free port, printed below)
    # The port value is never echoed into logs or responses.
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    else:
        env_port = os.environ.get("_2FA_WEB_PORT")
        port = int(env_port) if env_port and env_port.strip().isdigit() else 0
    init_bridge()
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    global _SERVER
    _SERVER = server
    bound_port = server.server_address[1]
    print("LISTENING_ON_PORT=%d" % bound_port, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
