class CompletionEvent:
    result: int
    user_data: int
    buffer: bytes | None

class TheIoRing:
    def wait(self, count: int) -> int:
        """
        Submits all pending events and waits for the specified number of completions.
        """

    def submit(self) -> int:
        """
        Submits all pending events, returning the number of events submitted.
        """

    def get_completion_entries(self) -> list[CompletionEvent]:
        """
        Gets the list of ready completion events.
        """

    def get_next_user_data(self) -> int:
        """
        Gets the next user-data value, used for tracking objects internally.
        """

def _RUSTFFI_create_io_ring(
    entries: int, cq_entries: int, sqlpoll_idle_ms: int, single_issuer: bool, /
) -> TheIoRing:
    """
    Creates a new ``io_uring``.
    """

def _RUSTFFI_ioring_prep_openat(
    ring: TheIoRing, dirfd: int, file_path: bytes, user_data: int, flags: int, mode: int, /
) -> None:
    """
    Prepares an openat(2) call through ``io_uring``.
    """

def _RUSTFFI_ioring_prep_read(ring: TheIoRing, fd: int, max_size: int, user_data: int, /) -> None:
    """
    Prepares a read(2) call through ``io_uring``.
    """
