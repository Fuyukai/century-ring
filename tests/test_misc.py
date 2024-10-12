import os

import pytest

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
