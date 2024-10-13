import errno
import os

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


def test_error() -> None:
    with make_io_ring() as ring:
        ring.prep_openat(None, b"/dev/definitely-does-not-exist", FileOpenMode.READ_ONLY)
        ring.submit_and_wait(1)
        cqe = ring.get_completion_entries()[0]

        with pytest.raises(OSError) as e:
            raise_for_cqe(cqe)

        assert e.value.errno == errno.ENOENT
