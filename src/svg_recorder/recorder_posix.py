"""Record a shell session through a pty on Linux and macOS."""

from __future__ import annotations

import fcntl
import os
import pty
import secrets
import select
import struct
import sys
import termios
import time
import tty
from pathlib import Path

from .asciicast import Header, Writer
from .palette import KITTY_DEFAULT, OSC_QUERY, Palette, apply_osc_replies
from .recorder import RecordError


def build_script(pre_commands: list[str], command: str | None, shell: str, token: str) -> str:
    """The -c script: pre-commands, clear, sentinel, then the command or a shell."""
    parts = list(pre_commands) + ["clear", f"printf '%s' {token}", command or shell]
    return "; ".join(parts)


def _fileno(stream) -> int:
    """stream.fileno(), or -1 when the stream has none (e.g. captured stdin)."""
    try:
        return stream.fileno()
    except OSError:
        return -1


class PosixRecorder:
    def __init__(self, term_in: int | None = None, term_out: int | None = None,
                 shell: str | None = None, query_timeout: float = 0.2):
        self.term_in = _fileno(sys.stdin) if term_in is None else term_in
        self.term_out = _fileno(sys.stdout) if term_out is None else term_out
        self.shell = shell or os.environ.get("SHELL") or "/bin/sh"
        self.query_timeout = query_timeout

    # ----- helpers --------------------------------------------------------

    def _size(self) -> tuple[int, int]:
        try:
            cols, lines = os.get_terminal_size(self.term_out)
            return cols, lines
        except OSError:
            return 80, 24

    def _query_palette(self) -> Palette:
        try:
            os.write(self.term_out, OSC_QUERY)
        except OSError:
            return KITTY_DEFAULT
        buf = b""
        deadline = time.monotonic() + self.query_timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            ready, _, _ = select.select([self.term_in], [], [], remaining)
            if not ready:
                break
            try:
                data = os.read(self.term_in, 4096)
            except OSError:
                break
            if not data:
                break
            buf += data
        return apply_osc_replies(buf, KITTY_DEFAULT)

    @staticmethod
    def _write_all(fd: int, data: bytes) -> None:
        while data:
            n = os.write(fd, data)
            data = data[n:]

    # ----- main -----------------------------------------------------------

    def record(self, command: str | None, pre_commands: list[str], cast_path: Path) -> Header:
        cols, lines = self._size()
        saved = None
        if os.isatty(self.term_in):
            saved = termios.tcgetattr(self.term_in)
            tty.setraw(self.term_in, termios.TCSANOW)  # TCSANOW: do not flush pending input
        try:
            palette = self._query_palette()
            token = "SVGREC" + secrets.token_hex(8)
            script = build_script(pre_commands, command, self.shell, token)
            pid, master = pty.fork()
            if pid == 0:  # child
                try:
                    os.execvp(self.shell, [self.shell, "-c", script])
                finally:
                    os._exit(127)
            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", lines, cols, 0, 0))
            try:
                rest = self._wait_for_sentinel(master, token.encode())
                header = Header(cols, lines, int(time.time()), palette)
                with Writer(cast_path, header) as writer:
                    self._shuttle(master, writer, rest)
            finally:
                os.close(master)
                os.waitpid(pid, 0)
            return header
        finally:
            if saved is not None:
                termios.tcsetattr(self.term_in, termios.TCSADRAIN, saved)

    def _read_master(self, master: int) -> bytes:
        try:
            return os.read(master, 65536)
        except OSError:  # EIO when the child closes the slave
            return b""

    def _read_term(self) -> bytes:
        try:
            return os.read(self.term_in, 4096)
        except OSError:
            return b""

    def _wait_for_sentinel(self, master: int, token: bytes) -> bytes:
        buf = b""
        watch_in = True
        while True:
            fds = [master] + ([self.term_in] if watch_in else [])
            ready, _, _ = select.select(fds, [], [])
            if master in ready:
                data = self._read_master(master)
                if not data:
                    raise RecordError("shell exited before recording started (pre-commands failed?)")
                buf += data
                i = buf.find(token)
                if i >= 0:
                    return buf[i + len(token):]
                buf = buf[-len(token):]  # keep a tail in case the token straddles reads
            if self.term_in in ready:
                data = self._read_term()
                if not data:
                    watch_in = False
                else:
                    self._write_all(master, data)

    def _shuttle(self, master: int, writer: Writer, first: bytes) -> None:
        t0 = time.monotonic()
        if first:
            self._write_all(self.term_out, first)
            writer.write(0.0, "o", first)
        watch_in = True
        while True:
            fds = [master] + ([self.term_in] if watch_in else [])
            ready, _, _ = select.select(fds, [], [])
            if master in ready:
                data = self._read_master(master)
                if not data:
                    return
                self._write_all(self.term_out, data)
                writer.write(time.monotonic() - t0, "o", data)
            if self.term_in in ready:
                data = self._read_term()
                if not data:
                    watch_in = False
                    continue
                self._write_all(master, data)
                writer.write(time.monotonic() - t0, "i", data)
