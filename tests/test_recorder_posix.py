import fcntl
import os
import struct
import termios
import threading
import tty

import pytest

from svg_recorder.asciicast import read
from svg_recorder.recorder import RecordError, get_recorder
from svg_recorder.recorder_posix import PosixRecorder, build_script


class FakeTerminal:
    """A pty pair standing in for the user's real terminal."""

    def __init__(self, cols=40, lines=10):
        self.master, self.slave = os.openpty()
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack("HHHH", lines, cols, 0, 0))
        tty.setraw(self.slave)
        self.seen = b""
        self._thread = threading.Thread(target=self._drain, daemon=True)
        self._thread.start()

    def _drain(self):
        while True:
            try:
                data = os.read(self.master, 4096)
            except OSError:
                break
            if not data:
                break
            self.seen += data

    def type(self, data: bytes):
        os.write(self.master, data)

    def close(self):
        os.close(self.slave)
        os.close(self.master)


def record(term, command, pre=(), path=None):
    rec = PosixRecorder(term_in=term.slave, term_out=term.slave, shell="/bin/sh", query_timeout=0.05)
    return rec.record(command, list(pre), path)


def test_build_script_orders_pre_commands_clear_sentinel_command():
    s = build_script(["cd /tmp", "export A=1"], "echo hi", "/bin/sh", "TOK")
    assert s == "cd /tmp; export A=1; clear; printf '%s' TOK; echo hi"
    assert build_script([], None, "/bin/zsh", "TOK") == "clear; printf '%s' TOK; /bin/zsh"


def test_records_output_with_header_size_and_no_sentinel(tmp_path):
    term = FakeTerminal(cols=33, lines=7)
    path = tmp_path / "r.cast"
    header = record(term, "printf 'hello'; sleep 0.1; printf '\\033[31mworld'", path=path)
    term.close()
    assert (header.width, header.height) == (33, 7)
    h2, events = read(path)
    assert h2 == header
    out = b"".join(d for _, k, d in events if k == "o")
    assert b"hello" in out and b"\x1b[31mworld" in out
    assert b"printf" not in out and b"SVGREC" not in out
    times = [t for t, _, _ in events]
    assert times == sorted(times) and times[0] >= 0
    assert b"hello" in term.seen and b"world" in term.seen


def test_pre_commands_affect_environment_and_are_not_recorded(tmp_path):
    term = FakeTerminal()
    path = tmp_path / "r.cast"
    record(term, 'printf "%s" "$FOO-$PWD"', pre=["export FOO=bar", "cd /tmp"], path=path)
    term.close()
    _, events = read(path)
    out = b"".join(d for _, k, d in events if k == "o")
    assert out.strip() == b"bar-/tmp"


def test_input_is_forwarded_and_recorded(tmp_path):
    term = FakeTerminal()
    path = tmp_path / "r.cast"
    threading.Timer(0.3, term.type, args=(b"q\n",)).start()
    record(term, "read x; printf 'got:%s' \"$x\"", path=path)
    term.close()
    _, events = read(path)
    assert any(k == "i" and d == b"q\n" for _, k, d in events)
    out = b"".join(d for _, k, d in events if k == "o")
    assert b"got:q" in out


def test_palette_reply_is_captured(tmp_path):
    term = FakeTerminal()
    term.type(b"\x1b]11;rgb:1111/2222/3333\x1b\\")
    header = record(term, "true", path=tmp_path / "r.cast")
    term.close()
    assert header.palette.bg == "#112233"


def test_failed_pre_command_raises(tmp_path):
    term = FakeTerminal()
    with pytest.raises(RecordError):
        record(term, "true", pre=["exit 3"], path=tmp_path / "r.cast")
    term.close()


def test_get_recorder_returns_posix_here():
    assert isinstance(get_recorder(), PosixRecorder)
