# Hark Triton, hark!
# These functions are the raw, Rust-level functions that the rest of the library uses. These are
# *not* designed to be used by end-user code!
#
# Only the ``CompletionEvent`` class is exposed as it has a trivial definition. The rest of the
# functionality of this file is *private*, may change under any circumstances, and may be confusing
# to use. The only guarantee is that you can't *explicitly* break anything by using these
# operations directly.

class CompletionEvent:
    """
    A single completion event returned from the io_uring.
    """

    #: The system call result for this event.
    result: int

    #: The internal user_data field. Not relevant.
    user_data: int

    #: If this operation had a buffer, either the provided buffer from the application or the
    #: allocated buffer (writes and reads, respectively).
    buffer: bytes | None

    def should_be_ignored(self) -> bool:
        """
        If True, this is a special completion event that should be ignored by user code.
        """

class TheIoRing:
    def wait(self, count: int) -> int:
        """
        Submits all pending events and waits for the specified number of completions.
        """

    def submit(self) -> int:
        """
        Submits all pending events, returning the number of events submitted.
        """

    def wait_with_timeout(self, secs: int, nsec: int) -> int:
        """
        Submits all pending events, then waits for the specified time.
        """

    def pending_sq_entries(self) -> int:
        """
        Gets the number of pending submission queue entries.
        """

    def get_completion_entries(self) -> list[CompletionEvent]:
        """
        Gets the list of ready completion events.
        """

    def get_next_user_data(self) -> int:
        """
        Gets the next user-data value, used for tracking objects internally.
        """

    def register_eventfd(self, event_fd: int) -> None:
        """
        Registers an eventfd with the loop.
        """

    def close(self) -> None:
        """
        Closes the io_uring. This method is idempotent.
        """

def _RUSTFFI_create_io_ring(
    entries: int, cq_entries: int, sqlpoll_idle_ms: int, single_issuer: bool, autosubmit: bool, /
) -> TheIoRing:
    """
    Creates a new ``io_uring``.
    """

def _RUSTFFI_make_uring_flags(
    fixed_file: bool,
    io_drain: bool,
    io_link: bool,
    io_hardlink: bool,
    io_async: bool,
    buffer_select: bool,
    skip_success: bool,
    /,
) -> int:
    """
    Sets up a set of io_uring flags based on the input booleans.
    """

def _RUSTFFI_ioring_prep_openat(
    ring: TheIoRing,
    dirfd: int,
    file_path: bytes,
    user_data: int,
    flags: int,
    mode: int,
    sqe_flags: int,
    /,
) -> int:
    """
    Prepares an openat(2) call through ``io_uring``.
    """

def _RUSTFFI_ioring_prep_read(
    ring: TheIoRing, fd: int, max_size: int, offset: int, user_data: int, sqe_flags: int, /
) -> None:
    """
    Prepares a pread(2) call through ``io_uring``.
    """

def _RUSTFFI_ioring_prep_write(
    ring: TheIoRing,
    fd: int,
    buf: bytes | bytearray,
    size: int,
    buffer_offset: int,
    file_offset: int,
    user_data: int,
    sqe_flags: int,
    /,
) -> None:
    """
    Prepares a pwrite(2) call through ``io_uring``.
    """

def _RUSTFFI_ioring_prep_close(ring: TheIoRing, fd: int, user_data: int, sqe_flags: int, /) -> None:
    """
    Prepares a close(2) call through ``io_uring``.
    """

def _RUSTFFI_ioring_prep_create_socket(
    ring: TheIoRing, domain: int, type: int, protocol: int, user_data: int, sqe_flags: int, /
) -> None:
    """
    Prepares a socket(2) call through ``io_uring``.
    """

def _RUSTFFI_ioring_prep_connect_v4(
    ring: TheIoRing, fd: int, addr: str, port: int, user_data: int, sqe_flags: int, /
) -> None:
    """
    Prepares a IPv4 connect(2) call through ``io_uring``.
    """

def _RUSTFFI_ioring_prep_connect_v6(
    ring: TheIoRing, fd: int, addr: str, port: int, user_data: int, sqe_flags: int, /
) -> None:
    """
    Prepares a IPv6 connect(2) call through ``io_uring``.
    """

def _RUSTFFI_ioring_prep_recv(
    ring: TheIoRing, fd: int, max_size: int, flags: int, user_data: int, sqe_flags: int, /
) -> None:
    """
    Prepares a recv(2) call through ``io_uring``.
    """

def _RUSTFFI_ioring_prep_send(
    ring: TheIoRing,
    fd: int,
    data: bytes | bytearray,
    size: int,
    buffer_offset: int,
    flags: int,
    user_data: int,
    sqe_flags: int,
    /,
) -> None:
    """
    Prepares a send(2) call through ``io_uring``.
    """
