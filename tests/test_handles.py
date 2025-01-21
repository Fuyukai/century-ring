import pytest

from century_ring.enums import FileOpenMode
from century_ring.handle import FdHandle
from century_ring.ring import make_io_ring


def test_using_handle_instead_of_int() -> None:
    with make_io_ring() as ring:
        ring.prep_openat(None, b"/dev/zero", FileOpenMode.READ_ONLY)
        ring.submit_and_wait()
        handle = FdHandle.from_completion_event(ring.get_completion_entries()[0])

        with handle:
            assert not handle.close_called()
            ring.prep_read(handle, 8)
            ring.submit_and_wait()
            assert ring.get_completion_entries()[0].buffer == b"\x00" * 8


def test_closing_handle_explicitly() -> None:
    with make_io_ring() as ring:
        ring.prep_openat(None, b"/dev/zero", FileOpenMode.READ_ONLY)
        ring.submit_and_wait()
        handle = FdHandle.from_completion_event(ring.get_completion_entries()[0])
        handle.close()

        assert handle.close_called()

        with pytest.raises(ValueError):
            ring.prep_read(handle, 8)


def test_closing_handle_ctx_manager() -> None:
    with make_io_ring() as ring:
        ring.prep_openat(None, b"/dev/zero", FileOpenMode.READ_ONLY)
        ring.submit_and_wait()
        handle = FdHandle.from_completion_event(ring.get_completion_entries()[0])

        with handle:
            pass
        
        assert handle.close_called()

        with pytest.raises(ValueError):
            ring.prep_read(handle, 8)

def test_closing_handle_via_uring() -> None:
    with make_io_ring() as ring:
        ring.prep_openat(None, b"/dev/zero", FileOpenMode.READ_ONLY)
        ring.submit_and_wait()
        handle = FdHandle.from_completion_event(ring.get_completion_entries()[0])

        ring.prep_close(handle)
        
        assert handle.close_called()

        # *actually* close it for good measure...
        ring.submit_and_wait()
