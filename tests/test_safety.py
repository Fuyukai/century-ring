import pytest

from century_ring import make_sqe_flags
from century_ring.wrappers import make_io_ring

PATTERN = "Can't use 'SKIP_SUCCESS' on submissions with owned data"

# For every op that takes ownership of something and needs to return an error if the user passes
# IOURING_SKIP_SUCCESS, please add a test here.


def test_skip_success_connect_v4():
    with make_io_ring() as ring, pytest.raises(ValueError, match=PATTERN):
        ring.prep_connect_v4(0, "127.0.0.1", 0, sqe_flags=make_sqe_flags(skip_success=True))


def test_skip_success_connect_v6():
    with make_io_ring() as ring, pytest.raises(ValueError, match=PATTERN):
        ring.prep_connect_v6(0, "::", 0, sqe_flags=make_sqe_flags(skip_success=True))


def test_skip_success_read():
    with make_io_ring() as ring, pytest.raises(ValueError, match=PATTERN):
        ring.prep_read(0, 1, sqe_flags=make_sqe_flags(skip_success=True))


def test_skip_success_recv():
    with make_io_ring() as ring, pytest.raises(ValueError, match=PATTERN):
        ring.prep_recv(0, 1, sqe_flags=make_sqe_flags(skip_success=True))


def test_skip_success_write():
    with make_io_ring() as ring, pytest.raises(ValueError, match=PATTERN):
        ring.prep_write(0, b"", sqe_flags=make_sqe_flags(skip_success=True))


def test_skip_success_send():
    with make_io_ring() as ring, pytest.raises(ValueError, match=PATTERN):
        ring.prep_send(0, b"", sqe_flags=make_sqe_flags(skip_success=True))
