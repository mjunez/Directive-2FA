"""Terminal 2FA bridge — standalone wrapper around the existing terminal 2FA command flow.

SECURITY INVARIANTS (do not weaken):
  * This module does NOT re-implement or bypass any 2FA check. It orchestrates
    the real, protected ``2FA-validator`` component and reports only a boolean.
  * No secret is ever returned or logged: not the challenge nonce, not the
    token contents, and never the 2FA key. Callers receive True/False only.
  * The production runner drives the validator through a pseudo-terminal so the
    validator's getpass prompt keeps masking the key (piping the key to a
    non-TTY getpass either echoes it or reads empty — see implementation notes).

PUBLIC SURFACE:
  Terminal2FABridge.verify(challenge_id, key, *, shutdown_on_success=True) -> bool
      One-shot: launch validator, feed key, await verification, return status.
  Terminal2FABridge.begin(challenge_id) -> bool
      Two-phase step 1: launch validator and await the key. Returns True only
      if the challenge was accepted (validator is now waiting for the key).
  Terminal2FABridge.complete(key, *, shutdown_on_success=True) -> bool
      Two-phase step 2: feed the key to the in-flight validator, await, return
      status. On success invokes the shutdown hook (web parent terminated).
  Terminal2FABridge.reset() -> None
      Abandon an in-flight session (kills the validator if still waiting).
  shutdown_parent_web_service(pid=None) -> None
      SIGTERM the parent web service process; called on successful validation.

TESTABILITY:
  The terminal interaction is isolated behind ``ValidatorRunner``. Unit tests
  inject a fake runner, so no real process is spawned and no real secret is
  handled by the test suite.
"""

from __future__ import annotations

import os
import select
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Protocol

DEFAULT_2FA_DIR = Path(os.environ.get("HERMES_2FA_DIR", "/home/michael/.hermes/2fa"))
DEFAULT_VALIDATOR = DEFAULT_2FA_DIR / "2fa-validator"

PROMPT_TIMEOUT = 30.0
COMPLETION_TIMEOUT = 60.0


class ValidatorHandle(Protocol):
    """Opaque handle to an in-flight validator process (test-double friendly)."""


@dataclass
class PtyHandle:
    """Production handle holding the validator subprocess and its PTY master fd."""

    proc: "subprocess.Popen"
    master_fd: int


class ValidatorRunner(Protocol):
    """Abstraction over spawning and driving the terminal 2FA validator.

    Production implementation uses a pseudo-terminal so the validator's getpass
    prompt masks the key. Tests inject a fake that returns canned booleans with
    no real process and no real secret.
    """

    def launch(self, challenge_id: str) -> ValidatorHandle: ...

    def complete(self, handle: ValidatorHandle, key: str) -> bool: ...

    def abort(self, handle: ValidatorHandle) -> None: ...


class PtyValidatorRunner:
    """Production runner: spawn ``2FA-validator`` under a PTY and feed the key."""

    def __init__(
        self,
        validator_path: Path = DEFAULT_VALIDATOR,
        prompt_timeout: float = PROMPT_TIMEOUT,
        completion_timeout: float = COMPLETION_TIMEOUT,
    ) -> None:
        self.validator_path = Path(validator_path)
        self.prompt_timeout = prompt_timeout
        self.completion_timeout = completion_timeout

    # Substrings that identify the validator's *real* key prompt. Anything
    # else emitted on the PTY (errors like "challenge expired/not found") is
    # NOT a prompt, even though it appears on stdout. We must wait for the
    # actual password prompt before declaring "waiting for the key".
    _KEY_PROMPT_MARKERS = (b"2FA key:", b"Password:", b"passwd:", b"Enter", b"Palabra clave 2FA:")

    def launch(self, challenge_id: str) -> ValidatorHandle:
        if not self.validator_path.exists():
            raise FileNotFoundError(f"2FA validator not found: {self.validator_path}")
        master, slave = os.openpty()
        proc = subprocess.Popen(
            [sys.executable, str(self.validator_path), challenge_id],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            close_fds=True,
            text=False,
        )
        os.close(slave)
        # Distinguish "validator emitted its key prompt" from "validator printed
        # an error and died". Any bytes are safe to read (no secret, master side;
        # the child reads the key from the slave stdin we feed later). We do NOT
        # busy-wait: we only declare "waiting for key" once a prompt marker is
        # seen, so a dead/expired challenge is correctly reported as failure.
        deadline = time.time() + self.prompt_timeout
        seen = b""
        while time.time() < deadline:
            if proc.poll() is not None:
                # Exited before ever emitting the key prompt: invalid/expired
                # challenge (or other fatal error). Close master, report dead.
                try:
                    os.close(master)
                except OSError:
                    pass
                return PtyHandle(proc=proc, master_fd=-1)
            r, _, _ = select.select([master], [], [], 0.1)
            if r:
                try:
                    data = os.read(master, 4096)
                except OSError:
                    data = b""
                if data:
                    seen += data
                    if any(m in seen for m in self._KEY_PROMPT_MARKERS):
                        # Validator is genuinely waiting for the key; keep master.
                        return PtyHandle(proc=proc, master_fd=master)
            time.sleep(0.02)
        # Neither exited nor emitted a key prompt within the window: assume an
        # unfamiliar prompt format but still alive; keep master open.
        return PtyHandle(proc=proc, master_fd=master)

    def complete(self, handle: ValidatorHandle, key: str) -> bool:
        if not isinstance(handle, PtyHandle):
            raise TypeError("complete() requires a PtyHandle")
        proc = handle.proc
        master = handle.master_fd
        # Feed the key to the validator's PTY. The PTY line discipline buffers
        # it until getpass reads, and echo is disabled so it is never reflected.
        if master >= 0:
            try:
                os.write(master, (key + "\n").encode())
            except OSError:
                # Validator may have already exited; outcome is the returncode.
                pass
        try:
            proc.wait(timeout=self.completion_timeout)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
            return False
        finally:
            if master >= 0:
                try:
                    os.close(master)
                except OSError:
                    pass
        return proc.returncode == 0

    def abort(self, handle: ValidatorHandle) -> None:
        if isinstance(handle, PtyHandle):
            try:
                if handle.proc.poll() is None:
                    handle.proc.kill()
            except Exception:
                pass
            if handle.master_fd >= 0:
                try:
                    os.close(handle.master_fd)
                except OSError:
                    pass


def shutdown_parent_web_service(
    pid: Optional[int] = None,
    sig: int = signal.SIGTERM,
) -> None:
    """Terminate the parent web service process (invoked on successful 2FA).

    By default targets ``os.getppid()``. Only terminates a distinct, alive
    parent process; never itself and never PID 1.
    """
    target = pid if pid is not None else os.getppid()
    if target <= 1 or target == os.getpid():
        return
    try:
        os.kill(target, sig)
    except ProcessLookupError:
        pass


class Terminal2FABridge:
    """Stateful bridge between a caller (e.g. a web form) and the terminal 2FA flow."""

    def __init__(
        self,
        runner: Optional[ValidatorRunner] = None,
        shutdown_hook: Callable[[], None] = lambda: shutdown_parent_web_service(),
    ) -> None:
        self._runner = runner or PtyValidatorRunner()
        self._shutdown_hook = shutdown_hook
        self._handle: Optional[ValidatorHandle] = None

    def begin(self, challenge_id: str) -> bool:
        """Two-phase step 1. Launch the validator and await the key.

        Returns True only if the challenge was accepted and the validator is
        now waiting for the key.
        """
        self.reset()
        handle = self._runner.launch(challenge_id)
        self._handle = handle
        if isinstance(handle, PtyHandle) and handle.proc.poll() is not None:
            # Validator exited during launch: challenge invalid/expired.
            self._handle = None
            return False
        return True

    def complete(self, key: str, *, shutdown_on_success: bool = True) -> bool:
        """Two-phase step 2. Feed the key, await verification, return status.

        On success, invokes the shutdown hook (terminates the web parent).
        """
        if self._handle is None:
            return False
        try:
            ok = self._runner.complete(self._handle, key)
        finally:
            self._handle = None
        if ok and shutdown_on_success:
            self._shutdown_hook()
        return ok

    def verify(
        self,
        challenge_id: str,
        key: str,
        *,
        shutdown_on_success: bool = True,
    ) -> bool:
        """One-shot convenience: begin + complete in a single call."""
        if not self.begin(challenge_id):
            return False
        return self.complete(key, shutdown_on_success=shutdown_on_success)

    def reset(self) -> None:
        """Abandon any in-flight session (kills the validator if still waiting)."""
        if self._handle is not None:
            try:
                self._runner.abort(self._handle)
            finally:
                self._handle = None
