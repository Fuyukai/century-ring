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
    _RUSTFFI_ioring_prep_write,
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

    def register_eventfd(self, event_fd: int | None = None) -> int:
        """
        Registers an `eventfd <https://man7.org/linux/man-pages/man2/eventfd.2.html>`_ with the
        ``io_uring``.

        This will be written to every time a new completion queue entry is available in the loop.
        This allows integrating the ``io_uring`` event loop into a more traditional
        select/poll-based event loop without requiring additional code.

        :param event_fd:

            The actual eventfd to register, typically returned from :func:`os.eventfd`. If this is
            None, then an eventfd will be created with sane flags.

        :return: The ``event_fd`` passed in, or one created by this function.

        .. warning::

            The actual value of the eventfd cannot be relied on. Use it purely as a signal to wake
            up and check the completion queue of the ioring.
        """

        if not (ring := self._the_ring()):
            raise RuntimeError("The ring is closed")

        if event_fd is None:
            event_fd = os.eventfd(0, os.EFD_CLOEXEC | os.EFD_NONBLOCK)

        ring.register_eventfd(event_fd)
        return event_fd

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

        :return: The user-data value that was stored in the SQE.
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

    def prep_read(self, fd: int, byte_count: int, offset: int = -1) -> int:
        """
        Prepares a pread(2) call. See the relevant man page for more details.

        The completion queue event for this submission will have the byte count as the result
        field, and a buffer containing the data read from the file.

        :param fd: The file descriptor to read the data from.
        :param byte_count: The *maximum* number of bytes to read. The actual amount may be lower.
        :param offset:

            The offset within the file to read from. If this is a positive integer, this is an
            absolute offset within the file to read from.

            If this is the constant ``-1``, then this will read from the current file's seek
            position.

        :return: The user-data value that was stored in the SQE.
        """

        if not (ring := self._the_ring()):
            raise RuntimeError("The ring is closed")

        if offset < 0 and offset < -1:
            raise ValueError("Can't pass negative offset", offset, "for this operation")

        user_data = ring.get_next_user_data()
        _RUSTFFI_ioring_prep_read(ring, fd, byte_count, offset, user_data)
        return user_data

    def prep_write(
        self,
        fd: int,
        buffer: bytes | bytearray,
        file_offset: int = -1,
        count: int | None = None,
        buffer_offset: int | None = None,
    ) -> int:
        """
        Prepares a pwrite(2) call. See the relevant man page for more details.

        The completion queue event for this submission will have the actual byte count *written*
        in the result field, as well as a copy of the buffer that was written for memory safetty
        purposes. The byte count may be less than the count requested.

        :param fd: The file descriptor to write the data to.
        :param buffer:

            The data buffer to read from. This will be copied into the Rust function's memory,
            so for large buffers this will use more memory.

        :param offset:

            The offset within the file to write at. If this is a positive integer, this is an
            absolute offset within the file to write at.

            If this is the constant ``-1``, then this will write at the current file's seek
            position.

        :param count:

            The number of bytes to write from the provided buffer. This defaults to the size of
            the buffer, and cannot be larger than the buffer.

        :param buffer_offset:

            The offset within the buffer to start writing from. This defaults to the first byte
            of the buffer, and cannot be beyond the end of the buffer.
        """

        if not (ring := self._the_ring()):
            raise RuntimeError("The ring is closed")

        if file_offset < 0 and file_offset < -1:
            raise ValueError("Can't pass negative offset", file_offset, "for this operation")

        size = count if count is not None else len(buffer)
        buffer_offset = buffer_offset if buffer_offset is not None else 0

        user_data = ring.get_next_user_data()
        _RUSTFFI_ioring_prep_write(ring, fd, buffer, size, buffer_offset, file_offset, user_data)
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
