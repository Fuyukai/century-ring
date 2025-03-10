import ipaddress
import os
import socket
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from os import PathLike

import attr

from century_ring._century_ring import (
    CompletionEvent,
    TheIoRing,
    _RUSTFFI_create_io_ring,
    _RUSTFFI_ioring_prep_close,
    _RUSTFFI_ioring_prep_connect_v4,
    _RUSTFFI_ioring_prep_connect_v6,
    _RUSTFFI_ioring_prep_create_socket,
    _RUSTFFI_ioring_prep_openat,
    _RUSTFFI_ioring_prep_read,
    _RUSTFFI_ioring_prep_recv,
    _RUSTFFI_ioring_prep_send,
    _RUSTFFI_ioring_prep_write,
)
from century_ring.enums import FileOpenFlag, FileOpenMode, enum_flags_to_int_flags
from century_ring.handle import IntoFilelikeHandle

# Q: why wrap all of these in (relatively) identical objects?
# A: ffi API is kinda ugly! also, no default arguments

# for some reason, this isn't defined in ``os``
AT_FDCWD = -100

type AcceptableFile = IntoFilelikeHandle | int


def unwrap_file(fd: AcceptableFile) -> int:
    if isinstance(fd, int):
        return fd

    handle = fd.as_handle()
    if handle.close_called():
        raise ValueError(f"Handle {handle!r} is closed")

    return fd.as_handle().fd


@attr.define
class IoUring:
    """
    Wraps the Rust-level ``io_uring`` object.
    """

    _the_ring: TheIoRing = attr.field(alias="_the_ring")

    @property
    def pending_sq_entries(self) -> int:
        """
        Gets the number of pending submission queue entries.
        """

        return self._the_ring.pending_sq_entries()

    def submit(self) -> int:
        """
        Submits all outstanding entries in the current submission queue.

        :return: The number of events successfully submitted.
        """

        return self._the_ring.submit()

    def submit_and_wait(self, count: int = 1) -> int:
        """
        Submits all outstanding entries in the current submission queue, and waits for completions.

        :param count: The number of completions to wait for.
        :return: The number of events successfully submitted.
        """

        return self._the_ring.wait(count)

    def submit_and_wait_with_timeout(self, seconds: int, nsec: int = 0) -> int:
        """
        Submits all outstanding entries, and waits for completions with a timeout.

        This internally uses a special ``IORING_OP_TIMEOUT`` submission queue entry with a special
        ``user_data`` value of 0xFF_FF_FF_00; any completion entry with this value should be
        ignored.

        :param seconds: The number of seconds to wait for completions.
        :param nsec: The number of nanoseconds to wait, added onto the value passed for ``seconds``.
        :return: The number of events successfully submitted.
        """

        return self._the_ring.wait_with_timeout(seconds, nsec)

    def get_completion_entries(self) -> list[CompletionEvent]:
        """
        Gets a list of completion entries from the completion queue.
        """

        return self._the_ring.get_completion_entries()

    def register_eventfd(self, event_fd: int | None = None) -> int:
        """
        Registers an `eventfd <https://man7.org/linux/man-pages/man2/eventfd.2.html>`_ with the
        ``io_uring``.

        This will be written to every time a new completion queue entry is available in the loop.
        This allows integrating the ``io_uring`` event loop into a more traditional
        select/poll-based event loop without requiring additional code.

        :param event_fd: The actual eventfd to register, typically returned from :func:`os.eventfd`.

            If this is None, then an eventfd will be created with sane flags for you.

        :return: The ``event_fd`` passed in, or one created by this function.

        .. warning::

            The actual value of the eventfd cannot be relied on. Use it purely as a signal to wake
            up and check the completion queue of the ioring.
        """

        if event_fd is None:
            event_fd = os.eventfd(0, os.EFD_CLOEXEC | os.EFD_NONBLOCK)

        self._the_ring.register_eventfd(event_fd)
        return event_fd

    # actual methods
    def prep_openat(
        self,
        relative_to: AcceptableFile | None,
        path: bytes | PathLike[bytes],
        open_mode: FileOpenMode,
        flags: Iterable[FileOpenFlag] | None = None,
        permissions: int = 0o666,
        sqe_flags: int | None = None,
    ) -> int:
        """
        Prepares an openat(2) call. See the relevant man page for more details.

        The completion queue event for this submission will have the file descriptor stored in the
        result field.

        :param relative_to: The fd of a directory to open this file relative to.

            If this is the special constant ``AT_FDCWD``, then this file will be opened relative
            to the current working directory. If this is ``-1`` or ``None``, then this parameter
            will be ignored and the path should be an absolute path.

        :param path: The bytes-encoded path to open.

            If this path is a relative path, the behaviour of how this file is looked up depends on
            the behaviour of the ``relative_to`` parameter. Otherwise, ``relative_to`` is ignored.

        :param open_mode: The mode to open a file in, e.g. read-only or write-only.
        :param flags: The file open flags to use.

            This differs from the traditional ``fopen`` flags that Python uses and should
            be a set of constants from the :class:`.FileOpenMode` enumeration.

        :param permissions: The permissions that the file will be opened with.

            This is masked off by the current umask; for example, if a user's umask is
            ``0o022`` and ``mode`` is the value ``0o666`` (the default value), then the final
            file will be created with ``0o644`` permissions.

        :param sqe_flags: See :func:`.make_uring_flags`.
        :return: The user-data value that was stored in the SQE.
        """

        if relative_to is None:
            dirfd = -1

        elif isinstance(relative_to, int):
            dirfd = relative_to

        else:
            dirfd = relative_to.as_handle().fd

        raw_flags = enum_flags_to_int_flags(flags) if flags else os.O_CLOEXEC
        user_data = self._the_ring.get_next_user_data()

        raw_flags |= open_mode.value
        sqe_flags = sqe_flags if sqe_flags is not None else 0

        _RUSTFFI_ioring_prep_openat(
            self._the_ring, dirfd, os.fsencode(path), user_data, raw_flags, permissions, sqe_flags
        )
        return user_data

    def prep_close(self, fd: AcceptableFile, *, sqe_flags: int | None = None) -> int:
        """
        Prepares a close(2) call. See the relevant man page for more details.

        :param fd: The file handle to close.
        :return: The user-data value that was stored in the SQE.
        :param sqe_flags: See :func:`.make_uring_flags`.
        """

        sqe_flags = sqe_flags if sqe_flags is not None else 0

        user_data = self._the_ring.get_next_user_data()
        _RUSTFFI_ioring_prep_close(self._the_ring, unwrap_file(fd), user_data, sqe_flags)

        if not isinstance(fd, int):
            fd.as_handle().mark_closed()

        return user_data

    def prep_read(
        self, fd: AcceptableFile, byte_count: int, offset: int = -1, *, sqe_flags: int | None = None
    ) -> int:
        """
        Prepares a pread(2) call. See the relevant man page for more details.

        The completion queue event for this submission will have the byte count as the result
        field, and a buffer containing the data read from the file.

        :param fd: The file descriptor to read the data from.
        :param byte_count: The *maximum* number of bytes to read. The actual amount may be lower.
        :param offset: The offset within the file to read from.

            If this is a positive integer, this is an absolute offset within the file to read from.
            If this is the constant ``-1``, then this will read from the current file's seek
            position.

        :param sqe_flags: See :func:`.make_uring_flags`.
        :return: The user-data value that was stored in the SQE.
        """

        if offset < 0 and offset < -1:
            raise ValueError("Can't pass negative offset", offset, "for this operation")

        sqe_flags = sqe_flags if sqe_flags is not None else 0
        user_data = self._the_ring.get_next_user_data()
        _RUSTFFI_ioring_prep_read(
            self._the_ring, unwrap_file(fd), byte_count, offset, user_data, sqe_flags
        )
        return user_data

    def prep_write(
        self,
        fd: AcceptableFile,
        buffer: bytes | bytearray,
        file_offset: int = -1,
        count: int | None = None,
        buffer_offset: int | None = None,
        *,
        sqe_flags: int | None = None,
    ) -> int:
        """
        Prepares a pwrite(2) call. See the relevant man page for more details.

        The completion queue event for this submission will have the actual byte count *written*
        in the result field, as well as a copy of the buffer that was written for memory safetty
        purposes. The byte count may be less than the count requested.

        :param fd: The file descriptor to write the data to.
        :param buffer: The bytestring or bytearray to send.

            This is copied into the Rust-side code before submission; large buffer sizes will cause
            excessive memory usage.

        :param file_offset: The offset within the file to write at.

            If this is a positive integer, this is an absolute offset within the file to write at.
            If this is the constant ``-1``, then this will write at the current file's seek
            position.

        :param count: The number of bytes to write from the provided buffer.

            This defaults to the size of the buffer, and cannot be larger than the buffer.

        :param buffer_offset: The offset within the buffer to start writing from.

            This defaults to the first byte of the buffer, and cannot be beyond the end of the
            buffer.

        :param sqe_flags: See :func:`.make_uring_flags`.
        :return: The user-data value that was stored in the SQE.
        """

        if file_offset < -1:
            raise ValueError("Can't pass negative offset", file_offset, "for this operation")

        size = count if count is not None else len(buffer)
        buffer_offset = buffer_offset if buffer_offset is not None else 0

        user_data = self._the_ring.get_next_user_data()
        sqe_flags = sqe_flags if sqe_flags is not None else 0
        _RUSTFFI_ioring_prep_write(
            self._the_ring,
            unwrap_file(fd),
            buffer,
            size,
            buffer_offset,
            file_offset,
            user_data,
            sqe_flags,
        )
        return user_data

    def prep_create_socket(
        self,
        domain: int,
        type: int,
        protocol: int = 0,
        *,
        nonblocking: bool = False,
        sqe_flags: int | None = None,
    ) -> int:
        """
        Prepares a socket(2) call. See the relevant man page for more information.

        :param domain: The "domain" (better known as protocol family) for this socket.

            In nearly all cases, this will be :attr:`socket.AF_INET` or :attr:`socket.AF_INET6`.

        :param type: The type for this socket.

            In nearly all cases, this will be :attr:`socket.SOCK_STREAM` or
            :attr:`socket.SOCK_DGRAM`.

        :param protocol: The protocol that this socket will carry.

            This should match the value passed for ``type``, i.e. don't pass
            :attr:`socket.IPPROTO_UDP` for a ``SOCK_STREAM`` socket.

        :param nonblocking: If true, then this socket will be created as a non-blocking socket.

            This saves an extra call to fcntl(2) to set O_NONBLOCK.

        :param sqe_flags: See :func:`.make_uring_flags`.
        :return: The user-data value that was stored in the SQE.
        """

        user_data = self._the_ring.get_next_user_data()
        type |= socket.SOCK_CLOEXEC

        if nonblocking:
            type |= socket.SOCK_NONBLOCK

        sqe_flags = sqe_flags if sqe_flags is not None else 0

        _RUSTFFI_ioring_prep_create_socket(
            self._the_ring, domain, type, protocol, user_data, sqe_flags
        )
        return user_data

    def prep_connect_v4(
        self,
        fd: AcceptableFile,
        address: str | ipaddress.IPv4Address,
        port: int,
        *,
        sqe_flags: int | None = None,
    ) -> int:
        """
        Prepares a connect(2) call for an IPv4 address. See the relevant man page for more info.

        :param fd: The file descriptor of the socket to connect using.
        :param address: The IPv4 address to connect to.

            This should either be a :class:`str` containing the four-octet IPv4 address
            (e.g. ``'172.16.39.25``) or a :class:`ipaddress.IPv4Address`.

        :param port: The port to connect to.
        :param sqe_flags: See :func:`.make_uring_flags`.
        :return: The user-data value that was stored in the SQE.
        """

        sqe_flags = sqe_flags if sqe_flags is not None else 0

        user_data = self._the_ring.get_next_user_data()
        _RUSTFFI_ioring_prep_connect_v4(
            self._the_ring, unwrap_file(fd), str(address), port, user_data, sqe_flags
        )
        return user_data

    def prep_connect_v6(
        self,
        fd: AcceptableFile,
        address: str | ipaddress.IPv6Address,
        port: int,
        *,
        sqe_flags: int | None = None,
    ) -> int:
        """
        Prepares a connect(2) call for an IPv4 address. See the relevant man page for more info.

        :param fd: The file descriptor of the socket to connect using.
        :param address: The IPv6 address to connect to.
        :param port: The port to connect to.
        :param sqe_flags: See :func:`.make_uring_flags`.
        :return: The user-data value that was stored in the SQE.
        """

        sqe_flags = sqe_flags if sqe_flags is not None else 0

        user_data = self._the_ring.get_next_user_data()
        _RUSTFFI_ioring_prep_connect_v6(
            self._the_ring, unwrap_file(fd), str(address), port, user_data, sqe_flags
        )
        return user_data

    def prep_recv(
        self, fd: AcceptableFile, byte_count: int, flags: int = 0, *, sqe_flags: int | None = None
    ) -> int:
        """
        Prepares a recv(2) call. See the relevant man page for more info.

        :param fd: The file descriptor of the socket to receive on.
        :param byte_count: The *maximum* number of bytes to read. The actual amount may be lower.
        :param flags: A set of socket-specific flags for this operation.
        :param sqe_flags: See :func:`.make_uring_flags`.
        :return: The user-data value that was stored in the SQE.
        """

        sqe_flags = sqe_flags if sqe_flags is not None else 0
        user_data = self._the_ring.get_next_user_data()
        _RUSTFFI_ioring_prep_recv(
            self._the_ring, unwrap_file(fd), byte_count, flags, user_data, sqe_flags
        )
        return user_data

    def prep_send(
        self,
        fd: AcceptableFile,
        buffer: bytes | bytearray,
        count: int | None = None,
        buffer_offset: int | None = None,
        flags: int = 0,
        *,
        sqe_flags: int | None = None,
    ) -> int:
        """
        Prepares a send(2) call. See the relevant man page for more info.

        The completion queue event for this submission will have the actual byte count *written*
        in the result field, as well as a copy of the buffer that was written for memory safetty
        purposes. The byte count may be less than the count requested.

        :param fd: The file descriptor to write the data to.
        :param buffer: The bytestring or bytearray to send.

            This is copied into the Rust-side code before submission; large buffer sizes will cause
            excessive memory usage.

        :param count: The number of bytes to write from the provided buffer.

            This defaults to the size of the buffer, and cannot be larger than the buffer.

        :param buffer_offset: The offset within the buffer to start writing from.

            This defaults to the first byte of the buffer, and cannot be beyond the end of the
            buffer.

        :param sqe_flags: See :func:`.make_uring_flags`.
        :return: The user-data value that was stored in the SQE.
        """

        size = count if count is not None else len(buffer)
        buffer_offset = buffer_offset if buffer_offset is not None else 0

        sqe_flags = sqe_flags if sqe_flags is not None else 0

        user_data = self._the_ring.get_next_user_data()
        _RUSTFFI_ioring_prep_send(
            self._the_ring,
            unwrap_file(fd),
            buffer,
            size,
            buffer_offset,
            flags,
            user_data,
            sqe_flags,
        )
        return user_data


@contextmanager
def make_io_ring(
    entries: int = 256,
    cq_size: int | None = None,
    sqpoll_idle_ms: int | None = None,
    single_issuer: bool = True,
    autosubmit: bool = True,
) -> Iterator[IoUring]:
    """
    Creates a new :class:`.IoUring` instance. This is a *context manager*; when the ``with`` block
    exits, the ring will be closed and inaccessible.

    .. code-block:: python3

        with make_io_ring() as ring:
            openat = ring.prep_openat(None, b"/dev/zero")
            ring.submit_and_wait()
            results = ring.get_completion_entries()

    :param entries: The maximum number of SQEs before a call to ``io_uring_enter`` must take place.

        If the submission queue is full, and something attempts to place a new entry in the
        submission queue, then an automatic call to ``io_uring_enter`` will take place.

    :param cq_size: The maximum number of entries in the completion queue.

        This only bounds the maximum number that will be copied into userspace across a single
        call; any completion queue entries that would not fit are buffered in kernelspace memory
        first. This means that no entries aree lost.

    :param sqpoll_idle_ms: The time the kernel submission poll thread will wait for a new SQE.

        If this amount of timee passes without a submission queue entry being placed into the queue,
        the submission poll thread will idle and will not wake again until

        If this value is zero or lower, then submission queue polling will be disabled entirely.

    :param single_issuer: Hints the kernel to optimise for single-thread access to the ``io_uring``.

        If you pass this as True and yet attempt to access the ``io_uring`` from multiple threads
        anyway, you may be smited.

    :param autosubmit: If True, the submission queue will automatically be submitted when full.

        If this is False, then trying to submit a new operation whilst the queue is full will
        fail with a :class:`.ValueError`.
    """

    cq_size = cq_size if (cq_size and cq_size > 0) else 0
    sqpoll_idle_ms = sqpoll_idle_ms if (sqpoll_idle_ms and sqpoll_idle_ms > 0) else 0

    ring = _RUSTFFI_create_io_ring(entries, cq_size, sqpoll_idle_ms, single_issuer, autosubmit)
    try:
        yield IoUring(_the_ring=ring)
    finally:
        ring.close()
