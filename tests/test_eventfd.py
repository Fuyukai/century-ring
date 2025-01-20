import os
import select

import pytest

from century_ring import make_io_ring
from tests import AutoclosingScope


def test_eventfd():
    with make_io_ring() as ring, AutoclosingScope() as scope:
        efd = ring.register_eventfd()
        scope.add(efd)

        file = scope.add(os.open("/dev/zero", os.O_RDONLY))

        ring.prep_read(file, 8)
        ring.submit_and_wait()

        # io_uring should have notified on the eventfd now, so select on it and make sure
        # it shows up in the readable list.
        (
            read,
            _,
            _,
        ) = select.select([efd], [], [], 0.0)
        assert read[0] == efd


def test_invalid_efd():
    with make_io_ring() as ring, AutoclosingScope() as scope:
        file = os.open("/dev/null", os.O_RDONLY)
        scope.add(file)

        with pytest.raises(OSError):
            ring.register_eventfd(file)
