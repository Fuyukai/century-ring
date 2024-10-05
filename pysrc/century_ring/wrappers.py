import os
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from os import PathLike
from weakref import ref

import attr

from century_ring._century_ring import (
    CompletionEvent,
    TheIoRing,
    _RUSTFFI_create_io_ring,
    _RUSTFFI_ioring_prep_openat,
    _RUSTFFI_ioring_prep_read,
)
from century_ring.files import FileOpenFlag, FileOpenMode, enum_flags_to_int_flags

# Q: why wrap all of these in (relatively) identical objects?
# A: ffi API is kinda ugly! also, no default arguments

# for some reason, this isn't defined in ``os``
AT_FDCWD = -100


@attr.define
class IoUring:
    """
    Wraps the Rust-level ``io_uring`` object.
    """

    # this is a weakref so that when the context manager goes out of scope, the io_uring is
    # dropped and we no longer need to care.
    _the_ring: ref[TheIoRing] = attr.field(alias="_the_ring")  # pyright fix

    def submit(self) -> int:
        """
        Submits all outstanding entries in the current submission queue.
        """

        if not (ring := self._the_ring()):
            raise RuntimeError("The ring is closed")

        return ring.submit()

    def submit_and_wait(self, count: int = 1) -> int:
        """
        Submits all outstanding entries in the current submission queue, and waits for completions.

        :param count: The number of completions to wait for.
        """

        if not (ring := self._the_ring()):
            raise RuntimeError("The ring is closed")

        return ring.wait(count)

    def get_completion_entries(self) -> list[CompletionEvent]:
        """
        Gets a list of completion entries from the completion queue.
        """

        if not (ring := self._the_ring()):
            raise RuntimeError("The ring is closed")

        return ring.get_completion_entries()

    # actual methods
    def prep_openat(
        self,
        relative_to: int | None,
        path: bytes | PathLike[bytes],
        open_mode: FileOpenMode,
        flags: Iterable[FileOpenFlag] | None = None,
        permissions: int = 0o666,
    ) -> int:
        """
        Prepares an openat(2) call. See the relevant man page for more details.

        The completion queue event for this submission will have the file descriptor stored in the
        result field.

        :param relative_to:

            A file descriptor that signifies the directory that this file should be opened relative
            to. If this is the special constant ``AT_FDCWD``, then this file will be opened relative
            to the current working directory. If this is ``-1``, then this parameter will be ignored
            and the path should be an absolute path.

        :param path:

            The bytes-encoded path to open.

            If this path is a relative path, the behaviour of how this file is looked up depends on
            the behaviour of the ``relative_to`` parameter. Otherwise, ``relative_to`` is ignored.

        :param open_mode:

            The mode to open a file in, e.g. read-only or write-only.

        :param flags:

            The file open flags to use. This differs from the traditional ``fopen`` flags that
            Python uses and should be a set of constants from the :class:`.FileOpenMode`
            enumeration.

        :param permissions:

            The permissions that the file will be opened with. This is masked off by the current
            umask; for example, if a user's umask is ``0o022`` and ``mode`` is the value ``0o666``
            (the default value), then the final file will be created with ``0o644`` permissions.

        :return: The user-data value that was stored in the CQE.
        """

        if not (ring := self._the_ring()):
            raise RuntimeError("The ring is closed")

        dirfd = relative_to if relative_to is not None else -1
        raw_flags = enum_flags_to_int_flags(flags) if flags else 0
        user_data = ring.get_next_user_data()

        raw_flags |= open_mode.value

        _RUSTFFI_ioring_prep_openat(
            ring, dirfd, os.fsencode(path), user_data, raw_flags, permissions
        )
        return user_data

    def prep_read(self, fd: int, byte_count: int) -> int:
        """
        Prepares a read(2) call. See the relevant man page for more details.

        The completion queue event for this submission will have the byte count as the result
        field, and a buffer containing the data read from the file.

        :param fd: The file descriptor to read the data from.
        :param byte_count: The *maximum* number of bytes to read. The actual amount may be lower.
        """

        if not (ring := self._the_ring()):
            raise RuntimeError("The ring is closed")

        user_data = ring.get_next_user_data()
        _RUSTFFI_ioring_prep_read(ring, fd, byte_count, user_data)
        return user_data


@contextmanager
def make_io_ring(
    entries: int = 256,
    cq_size: int | None = None,
    sqpoll_idle_ms: int | None = None,
    single_issuer: bool = True,
) -> Iterator[IoUring]:
    """
    Creates a new :class:`.IoUring` instance. This is a *context manager*; when the ``with`` block
    exits, the ring will be closed and inaccessible.

    :param entries:

        The maximum number of submission queue entries in the ring before a call to
        ``io_uring_enter`` must take place.

        If the submission queue is full, and something attempts to place a new entry in the
        submission queue, then an automatic call to ``io_uring_enter`` will take place.

    :param cq_size:

        The maximum number of entries in the completion queue. This only bounds the maximum
        number that will be copied into userspace across a single call; any completion queue
        entries that would not fit are buffered in kernelspace memory first.

    :param sqpoll_idle_ms:

        The number of milliseconds the kernel submission queue polling thread should wait for a new
        submission queue entry before returning to idle.

        If this value is zero or lower, then submission queue polling will be disabled entirely.

    :param single_issuer:

        Hints to the kernel that it should optimise for single-threaded access to the ``io_uring``
        ring. Given that this is Python, this should always be true.

        If you pass this as True and yet attempt to access the ``io_uring`` from multiple threads
        anyway, you may be smited.
    """

    cq_size = cq_size if (cq_size and cq_size > 0) else 0
    sqpoll_idle_ms = sqpoll_idle_ms if (sqpoll_idle_ms and sqpoll_idle_ms > 0) else 0

    ring = _RUSTFFI_create_io_ring(entries, cq_size, sqpoll_idle_ms, single_issuer)
    yield IoUring(_the_ring=ref(ring))
