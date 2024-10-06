import os
import select

from century_ring.wrappers import make_io_ring
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
