use std::os::fd::RawFd;

use io_uring::types::Fd;
use pyo3::{exceptions::PyNotImplementedError, pyfunction, PyResult, Python};

use crate::ring::TheIoRing;

#[pyfunction(name = "_RUSTFFI_ioring_prep_close")]
pub fn ioring_prep_close(
    ring: &mut TheIoRing,
    fd: RawFd,
    user_data: u64,
    py: Python<'_>,
) -> PyResult<()> {
    if !ring.probe.is_supported(io_uring::opcode::Close::CODE) {
        return Err(PyNotImplementedError::new_err("read"));
    }

    let ring_op = io_uring::opcode::Close::new(Fd(fd))
        .build()
        .user_data(user_data);
    ring.autosubmit(py, &ring_op)?;

    return Ok(());
}
