import sys

import pytest

from century_ring import FileOpenFlag, FileOpenMode, make_io_ring, raise_for_cqe
from tests import AutoclosingScope


def test_reading_zero():
    with make_io_ring() as ring, AutoclosingScope() as scope:
        openat = ring.prep_openat(None, b"/dev/zero", FileOpenMode.READ_ONLY)
        assert ring.submit_and_wait(1) == 1
        open_cqe = ring.get_completion_entries()[0]
        raise_for_cqe(open_cqe)
        assert open_cqe.result > 0
        assert open_cqe.user_data == openat
        scope.fds.append(open_cqe.result)

        read = ring.prep_read(open_cqe.result, 4096)
        assert ring.submit_and_wait(1) == 1
        read_cqe = ring.get_completion_entries()[0]
        raise_for_cqe(read_cqe)

        assert read_cqe.user_data == read
        assert read_cqe.result == 4096
        assert read_cqe.buffer is not None
        assert len(read_cqe.buffer) == read_cqe.result
        assert sum(read_cqe.buffer) == 0


def test_openat():
    with make_io_ring() as ring, AutoclosingScope() as scope:
        ring.prep_openat(
            None,
            b"/dev",
            FileOpenMode.READ_ONLY,
            {FileOpenFlag.MUST_BE_DIRECTORY, FileOpenFlag.PATH},
        )
        assert ring.submit_and_wait(1) == 1
        open_dir_cqe = ring.get_completion_entries()[0]
        raise_for_cqe(open_dir_cqe)
        scope.fds.append(open_dir_cqe.result)

        ring.prep_openat(open_dir_cqe.result, b"zero", FileOpenMode.READ_ONLY)
        assert ring.submit_and_wait(1) == 1
        open_zero_cqe = ring.get_completion_entries()[0]
        raise_for_cqe(open_zero_cqe)
        scope.add(open_zero_cqe.result)


def test_write_and_read():
    with make_io_ring() as ring, AutoclosingScope() as scope:
        ring.prep_openat(
            None, b"/tmp", FileOpenMode.READ_WRITE, flags={FileOpenFlag.TEMPORARY_FILE}
        )
        ring.submit_and_wait()
        raw_cqe = ring.get_completion_entries()[0]
        raise_for_cqe(raw_cqe)
        open_fd = scope.add(raw_cqe.result)

        ring.prep_write(open_fd, b"wow!")
        ring.submit_and_wait()
        raise_for_cqe(ring.get_completion_entries()[0])

        ring.prep_read(open_fd, 4096, offset=0)
        ring.submit_and_wait()
        read_cqe = ring.get_completion_entries()[0]
        raise_for_cqe(read_cqe)
        assert read_cqe.result == 4
        buffer = read_cqe.buffer
        assert buffer is not None
        assert len(buffer) == 4
        assert buffer == b"wow!"


def test_invalid_writes():
    with make_io_ring() as ring:
        # just reuse stdout here
        with pytest.raises(ValueError) as e1:
            ring.prep_write(sys.stderr.fileno(), b"123", count=4)

        assert e1.match("can't write")

        with pytest.raises(ValueError) as e2:
            ring.prep_write(sys.stderr.fileno(), b"123", count=3, buffer_offset=2)

        assert e2.match("out of range")

        with pytest.raises(ValueError):
            ring.prep_write(sys.stderr.fileno(), b"123", file_offset=-100)
