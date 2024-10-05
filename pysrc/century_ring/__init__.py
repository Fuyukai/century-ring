import os

from century_ring._century_ring import CompletionEvent as CompletionEvent
from century_ring.files import FileOpenFlag as FileOpenFlag, FileOpenMode as FileOpenMode
from century_ring.wrappers import (
    AT_FDCWD as AT_FDCWD,
    IoUring as IoUring,
    make_io_ring as make_io_ring,
)


def raise_for_cqe(cqe: CompletionEvent) -> None:
    """
    Helper function that raises an :class:`.OSError` if a CQE has an error result.
    """

    if cqe.result < 0:
        errno = abs(cqe.result)
        err = OSError(f"[Errno {errno}] {os.strerror(errno)}")
        err.errno = errno
        raise err
