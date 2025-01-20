import errno
import os
import sys
import time

import pytest

from century_ring import raise_for_cqe
from century_ring.files import FileOpenMode
from century_ring.wrappers import make_io_ring
from tests import AutoclosingScope


def test_batching():
    with make_io_ring(entries=256, cq_size=512) as ring, AutoclosingScope() as scope:
        file = scope.add(os.open("/dev/zero", os.O_RDONLY))

        for _ in range(30):
            ring.prep_read(file, 4096)

        assert ring.submit() == 30
        assert len(ring.get_completion_entries()) == 30


def test_auto_submit():
    with make_io_ring(entries=256, cq_size=512) as ring, AutoclosingScope() as scope:
        file = scope.add(os.open("/dev/zero", os.O_RDONLY))

        for _ in range(257):
            ring.prep_read(file, 4096)

        assert ring.submit() == 1
        assert len(ring.get_completion_entries()) == 257


def test_disabling_auto_submit():
    with (
        make_io_ring(entries=1, cq_size=256, autosubmit=False) as ring,
        AutoclosingScope() as scope,
    ):
        file = scope.add(os.open("/dev/zero", os.O_RDONLY))

        ring.prep_read(file, 4096)

        with pytest.raises(ValueError):
            ring.prep_read(file, 4096)


def test_closing() -> None:
    with make_io_ring() as ring:
        r, w = os.pipe()
        ring.prep_close(r)
        ring.submit()

        with pytest.raises(OSError):
            os.read(r, 1234)


def test_raise_for_cqe() -> None:
    with make_io_ring() as ring:
        ring.prep_openat(None, b"/dev/definitely-does-not-exist", FileOpenMode.READ_ONLY)
        ring.submit_and_wait(1)
        cqe = ring.get_completion_entries()[0]

        with pytest.raises(OSError) as e:
            raise_for_cqe(cqe)

        assert e.value.errno == errno.ENOENT


def test_ring_closed() -> None:
    with make_io_ring() as ring:
        pass

    with pytest.raises(ValueError) as e:
        ring.prep_close(sys.stderr.fileno())

    assert e.match("The ring is closed")


def test_empty_timeout() -> None:
    with make_io_ring() as ring:
        before = time.monotonic()
        assert ring.submit_and_wait_with_timeout(seconds=1) == 0
        after = time.monotonic()
        assert after - before >= 1.0


def test_real_timeout() -> None:
    with make_io_ring() as ring:
        ring.prep_openat(None, b"/dev/zero", FileOpenMode.READ_ONLY)
        before = time.monotonic()
        assert ring.submit_and_wait_with_timeout(seconds=1) == 1
        after = time.monotonic()

        assert (after - before) < 1.0
        # make sure no extra SQE got posted for the timeout event
        result = ring.get_completion_entries()
        assert len(result) == 1
        os.close(result[0].result)


def test_multiple_timeouts_ignoring_completions() -> None:
    # make sure that submitting with timeouts doesn't work until we actually reap the completion
    # queue.
    with make_io_ring() as ring:
        ring.prep_openat(None, b"/dev/zero", FileOpenMode.READ_ONLY)

        before = time.monotonic()
        for _ in range(10):
            ring.submit_and_wait_with_timeout(seconds=1)

        after = time.monotonic()
        assert (after - before) < 5

        result = ring.get_completion_entries()
        assert len(result) == 1
        os.close(result[0].result)

        before = time.monotonic()
        ring.submit_and_wait_with_timeout(seconds=1)
        after = time.monotonic()
        assert (after - before) >= 1.0


def test_pending_sq_entries() -> None:
    with make_io_ring() as ring:
        ring.prep_openat(None, b"/dev/zero", FileOpenMode.READ_ONLY)

        assert ring.pending_sq_entries == 1
