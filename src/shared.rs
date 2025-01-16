use std::os::fd::RawFd;

use io_uring::{squeue::Flags, types::Fd};
use pyo3::{
    exceptions::{PyNotImplementedError, PyValueError},
    pyfunction, PyResult,
};

use crate::ring::TheIoRing;

pub(crate) fn check_write_buffer(buf: &[u8], size: usize, offset: usize) -> PyResult<usize> {
    if size > buf.len() {
        let message = format!("can't write {} bytes from a vec of {}", size, buf.len());
        return Err(PyValueError::new_err(message));
    }

    if offset > buf.len() {
        let message = format!("offset {} out of range from vec of {}", offset, buf.len());
        return Err(PyValueError::new_err(message));
    }

    let end_offset = offset + size;
    if end_offset > buf.len() {
        let message = format!(
            "offset {} out of range from vec of {}",
            end_offset,
            buf.len()
        );
        return Err(PyValueError::new_err(message));
    }

    return Ok(end_offset);
}

/// Performs a ``close(2)`` call using io_uring.
#[pyfunction(name = "_RUSTFFI_ioring_prep_close")]
pub fn ioring_prep_close(
    ring: &mut TheIoRing,
    fd: RawFd,
    user_data: u64,
    sqe_flags: u8,
) -> PyResult<()> {
    if !ring.probe.is_supported(io_uring::opcode::Close::CODE) {
        return Err(PyNotImplementedError::new_err("read"));
    }

    let ring_op = io_uring::opcode::Close::new(Fd(fd))
        .build()
        .flags(Flags::from_bits_truncate(sqe_flags))
        .user_data(user_data);

    ring.autosubmit(&ring_op)?;

    return Ok(());
}
