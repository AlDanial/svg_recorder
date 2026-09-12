import fcntl
import os
import signal
import struct
import termios
import tty

import pytest

from svg_recorder.asciicast import read
from svg_recorder.recorder import RecordError, get_recorder
from svg_recorder.recorder_posix import PosixRecorder, build_script, split_utf8_tail


class FakeTerminal:
    """A pty pair standing in for the user's real terminal.

    Deliberately thread-free: pty.fork() in a multi-threaded process warns and
    can deadlock the child. Output the recorder writes to the slave sits in the
    pty buffer (several kilobytes, far more than these tests produce) and is
    collected by drain() when the recording is over.
    """

    def __init__(self, cols=40, lines=10):
        self.master, self.slave = os.openpty()
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack("HHHH", lines, cols, 0, 0))
        tty.setraw(self.slave)
        os.set_blocking(self.master, False)
        self.seen = b""

    def drain(self):
        """Collect everything the recorder has echoed to the terminal so far."""
        while True:
            try:
                data = os.read(self.master, 65536)
            except (BlockingIOError, OSError):
                break
            if not data:
                break
            self.seen += data

    def type(self, data: bytes):
        os.write(self.master, data)

    def type_after(self, delay: float, data: bytes):
        """Type after a delay without a thread, so pty.fork() stays single-threaded.

        fork() clears interval timers in the child, so only the recorder's own
        process ever sees the alarm.
        """
        signal.signal(signal.SIGALRM, lambda *_: self.type(data))
        signal.setitimer(signal.ITIMER_REAL, delay)

    def close(self):
        signal.setitimer(signal.ITIMER_REAL, 0)
        self.drain()
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
    term.type_after(0.3, b"q\n")
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


def test_multibyte_character_split_across_reads_is_not_split_across_events(tmp_path):
    term = FakeTerminal()
    path = tmp_path / "r.cast"
    record(term, r"printf '\344\275'; sleep 0.1; printf '\240'", path=path)
    term.close()
    for line in path.read_text(encoding="utf-8").splitlines():
        assert "\\ud" not in line.lower()
    _, events = read(path)
    for _, _, data in events:
        data.decode("utf-8")  # every event stands alone as valid UTF-8
    out = b"".join(d for _, k, d in events if k == "o")
    assert out.decode("utf-8") == "你"


def test_split_utf8_tail_holds_back_only_incomplete_sequences():
    assert split_utf8_tail(b"") == (b"", b"")
    assert split_utf8_tail(b"abc") == (b"abc", b"")
    assert split_utf8_tail("你".encode()) == ("你".encode(), b"")
    assert split_utf8_tail(b"a\xe4\xbd") == (b"a", b"\xe4\xbd")
    assert split_utf8_tail(b"a\xe4") == (b"a", b"\xe4")
    assert split_utf8_tail(b"a\xf0\x9f\x92") == (b"a", b"\xf0\x9f\x92")
    assert split_utf8_tail("😀".encode()) == ("😀".encode(), b"")
    # invalid bytes are not an incomplete tail: they must still be written
    assert split_utf8_tail(b"a\xff") == (b"a\xff", b"")
    assert split_utf8_tail(b"a\x80\x80") == (b"a\x80\x80", b"")
    # a lone continuation run longer than any sequence is not held back
    assert split_utf8_tail(b"\xbd\xa0") == (b"\xbd\xa0", b"")


def test_record_without_a_terminal_raises_record_error(tmp_path):
    rec = PosixRecorder(term_in=-1, term_out=-1, shell="/bin/sh")
    with pytest.raises(RecordError, match="no terminal"):
        rec.record("true", [], tmp_path / "r.cast")


def test_os_errors_from_the_pty_become_record_errors(tmp_path, monkeypatch):
    term = FakeTerminal()
    monkeypatch.setattr("svg_recorder.recorder_posix.pty.fork",
                        lambda: (_ for _ in ()).throw(OSError("out of ptys")))
    rec = PosixRecorder(term_in=term.slave, term_out=term.slave, shell="/bin/sh", query_timeout=0.0)
    with pytest.raises(RecordError, match="out of ptys"):
        rec.record("true", [], tmp_path / "r.cast")
    term.close()
