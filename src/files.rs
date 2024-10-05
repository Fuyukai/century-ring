use std::os::fd::RawFd;

use bytemuck::cast_slice;
use io_uring::types::Fd;
use pyo3::{
    exceptions::{PyNotImplementedError, PyValueError},
    pyfunction, PyResult, Python,
};

use crate::ring::TheIoRing;

#[pyfunction(name = "_RUSTFFI_ioring_prep_openat")]
pub fn ioring_prep_openat(
    ring: &mut TheIoRing,
    dirfd: RawFd,
    file_path: &[u8],
    user_data: u64,
    flags: i32,
    mode: u32,
    py: Python<'_>,
) -> PyResult<()> {
    if !ring.probe.is_supported(io_uring::opcode::OpenAt::CODE) {
        return Err(PyNotImplementedError::new_err("openat"));
    }

    let dir_fd = io_uring::types::Fd(dirfd);
    let mut owned_path = file_path.to_vec();
    owned_path.push(0);  // null-terminate... 
    let path_i8: &[i8] = cast_slice(owned_path.as_slice());

    let openat_op = io_uring::opcode::OpenAt::new(dir_fd, path_i8.as_ptr())
        .flags(flags)
        .mode(mode)
        .build()
        .user_data(user_data);

    let mut needs_submit = false;

    loop {
        if needs_submit {
            ring.submit(py)?;
        }

        let result = unsafe { ring.the_io_uring.submission().push(&openat_op) };
        if result.is_err() {
            if needs_submit {
                return Err(PyValueError::new_err(
                    "submission queue is full and submitting didn't help!",
                ));
            } else {
                needs_submit = true;
                continue;
            }
        }

        ring.add_owned_path(user_data, owned_path);
        return Ok(());
    }
}

#[pyfunction(name = "_RUSTFFI_ioring_prep_read")]
pub fn ioring_prep_read(
    ring: &mut TheIoRing,
    fd: RawFd,
    max_size: u32,
    user_data: u64,
    py: Python<'_>,
) -> PyResult<()> {
    if !ring.probe.is_supported(io_uring::opcode::Read::CODE) {
        return Err(PyNotImplementedError::new_err("read"));
    }

    let mut buf: Vec<u8> = vec![0; max_size as usize];
    let ring_op = io_uring::opcode::Read::new(Fd(fd), buf.as_mut_ptr(), max_size)
        .build()
        .user_data(user_data);

    let mut needs_submit = false;

    loop {
        if needs_submit {
            ring.submit(py)?;
        }

        let result = unsafe { ring.the_io_uring.submission().push(&ring_op) };
        if result.is_err() {
            if needs_submit {
                return Err(PyValueError::new_err(
                    "submission queue is full and submitting didn't help!",
                ));
            } else {
                needs_submit = true;
                continue;
            }
        }

        ring.add_owned_buffer(user_data, buf);
        return Ok(());
    }
}
