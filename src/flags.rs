use io_uring::squeue::Flags;

// gross!
// but I can't think of a better way to do it than this... I don't want to duplicate the io_uring
// flag values on the python-side.

#[pyo3::pyfunction(name = "_RUSTFFI_make_uring_flags")]
pub fn make_uring_flags(
    fixed_file: bool,
    io_drain: bool,
    io_link: bool,
    io_hardlink: bool,
    io_async: bool,
    buffer_select: bool,
    skip_success: bool,
) -> u8 {
    let mut flags = Flags::empty();

    if fixed_file {
        flags |= Flags::FIXED_FILE
    };
    if io_drain {
        flags |= Flags::IO_DRAIN
    };
    if io_link {
        flags |= Flags::IO_LINK
    };
    if io_hardlink {
        flags |= Flags::IO_HARDLINK
    };
    if io_async {
        flags |= Flags::ASYNC
    };
    if buffer_select {
        flags |= Flags::BUFFER_SELECT
    };
    if skip_success {
        flags |= Flags::SKIP_SUCCESS
    };

    return flags.bits();
}
