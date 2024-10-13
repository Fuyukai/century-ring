import os

from century_ring._century_ring import CompletionEvent as CompletionEvent, _RUSTFFI_make_uring_flags
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


def make_uring_flags(
    fixed_file: bool = False,
    io_drain: bool = False,
    io_link: bool = False,
    io_hardlink: bool = False,
    io_async: bool = False,
    buffer_select: bool = False,
    skip_success: bool = False,
) -> int:
    """
    Creates a set of submission queue entry flags for an ``io_uring`` operation.

    :param fixed_file:

        For operations based on file descriptors, this specifies that the ``fd`` parameter passed in
        refers to a file within the file array registered with the ``io_uring``, instead of an
        arbitrary file descriptor a process has open.

        This file must have been registered with the ``io_uring`` before, and not all operations
        support using this flag; those operations will return ``-EBADF`` in their completion queue
        entry.

    :param io_drain:

        Forces the operation for this SQE to wait until all other submitted operations have been
        processed, as well as preventing all submitted operations after this operation from running
        until this operation is completed.

    :param io_link:

        Causes the submission queue entry immediately after this one to be linked to this one;
        it will not be ran until this operation completes. See :ref:`linking` for more information.

    :param io_hardlink:

        Similar to ``io_link``, but if one operation fails subsequent operations will be processed
        as if the first operation did not fail.

    :param io_async:

        By default, ``io_uring`` will try and complete all operations by issuing a non-blocking
        operation first, and if that fails falling back to an asynchronous manner instead (such
        as polling on a socket).

        If this flag is provided, then the operation will be attempted in an asynchronous manner
        first. This is useful for when the programmer knows that issuing a non-blocking operation
        will inevitably fail, and can improve performance.

    :param skip_success: No completion queue entry will be created if this operation is successful.
    :return: An opaque integer bitfield of flags that can be used for a submission queue entry.
    """

    return _RUSTFFI_make_uring_flags(
        fixed_file, io_drain, io_link, io_hardlink, io_async, buffer_select, skip_success
    )
