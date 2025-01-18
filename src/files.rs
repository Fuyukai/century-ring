use std::os::fd::RawFd;

use bytemuck::cast_slice;
use io_uring::{squeue::Flags, types::Fd};
use pyo3::{exceptions::{PyNotImplementedError, PyValueError}, pyfunction, PyResult};

use crate::{ring::TheIoRing, shared::check_write_buffer};

/// Performs an ``openat(2)`` call via io_uring.
#[pyfunction(name = "_RUSTFFI_ioring_prep_openat")]
pub fn ioring_prep_openat(
    ring: &mut TheIoRing,
    dirfd: RawFd,
    file_path: &[u8],
    user_data: u64,
    file_flags: i32,
    mode: u32,
    sqe_flags: u8,
) -> PyResult<()> {
    if !ring.probe.is_supported(io_uring::opcode::OpenAt::CODE) {
        return Err(PyNotImplementedError::new_err("openat"));
    }

    let parsed_sqe_flags = Flags::from_bits_truncate(sqe_flags);
    if parsed_sqe_flags.contains(Flags::SKIP_SUCCESS) {
        return Err(PyValueError::new_err(
            "Can't use 'SKIP_SUCCESS' on submissions with owned data",
        ));
    }

    let dir_fd = io_uring::types::Fd(dirfd);
    let mut owned_path = file_path.to_vec();
    owned_path.push(0); // null-terminate...
    let path_i8: &[i8] = cast_slice(owned_path.as_slice());

    let openat_op = io_uring::opcode::OpenAt::new(dir_fd, path_i8.as_ptr())
        .flags(file_flags)
        .mode(mode)
        .build()
        .flags(parsed_sqe_flags)
        .user_data(user_data);

    ring.autosubmit(&openat_op)?;
    ring.add_owned_path(user_data, owned_path);
    return Ok(());
}

/// Performs a ``read(2)`` call via io_uring.
#[pyfunction(name = "_RUSTFFI_ioring_prep_read")]
pub fn ioring_prep_read(
    ring: &mut TheIoRing,
    fd: RawFd,
    max_size: u32,
    offset: i64,
    user_data: u64,
    sqe_flags: u8,
) -> PyResult<()> {
    if !ring.probe.is_supported(io_uring::opcode::Read::CODE) {
        return Err(PyNotImplementedError::new_err("read"));
    }

    let parsed_sqe_flags = Flags::from_bits_truncate(sqe_flags);
    if parsed_sqe_flags.contains(Flags::SKIP_SUCCESS) {
        return Err(PyValueError::new_err(
            "Can't use 'SKIP_SUCCESS' on submissions with owned data",
        ));
    }

    let mut buf: Vec<u8> = vec![0; max_size as usize];
    let ring_op = io_uring::opcode::Read::new(Fd(fd), buf.as_mut_ptr(), max_size)
        .offset(offset as u64)
        .build()
        .flags(parsed_sqe_flags)
        .user_data(user_data);

    ring.autosubmit(&ring_op)?;
    ring.add_owned_buffer(user_data, buf);
    return Ok(());
}

/// Performs a ``writw(2)`` call via io_uring.
#[pyfunction(name = "_RUSTFFI_ioring_prep_write")]
pub fn ioring_prep_write(
    ring: &mut TheIoRing,
    fd: RawFd,
    data: &[u8],
    size: usize,
    buffer_offset: usize,
    file_offset: i64,
    user_data: u64,
    sqe_flags: u8,
) -> PyResult<()> {
    if !ring.probe.is_supported(io_uring::opcode::Write::CODE) {
        return Err(PyNotImplementedError::new_err("write"));
    }

    let parsed_sqe_flags = Flags::from_bits_truncate(sqe_flags);
    if parsed_sqe_flags.contains(Flags::SKIP_SUCCESS) {
        return Err(PyValueError::new_err(
            "Can't use 'SKIP_SUCCESS' on submissions with owned data",
        ));
    }

    let end_offset = check_write_buffer(data, size, buffer_offset)?;

    // like the read op, we need to make sure the read-from buffer outlives us.
    // so we copy it to our own buffer, let the ring own it, and then it's deallocated later on
    let vec = data[buffer_offset..end_offset].to_vec();

    let ring_op = io_uring::opcode::Write::new(Fd(fd), vec.as_ptr(), vec.len() as u32)
        .offset(file_offset as u64)
        .build()
        .flags(parsed_sqe_flags)
        .user_data(user_data);

    ring.autosubmit(&ring_op)?;
    ring.add_owned_buffer(user_data, vec);

    return Ok(());
}
