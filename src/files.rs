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
    owned_path.push(0); // null-terminate...
    let path_i8: &[i8] = cast_slice(owned_path.as_slice());

    let openat_op = io_uring::opcode::OpenAt::new(dir_fd, path_i8.as_ptr())
        .flags(flags)
        .mode(mode)
        .build()
        .user_data(user_data);

    ring.autosubmit(py, &openat_op)?;
    ring.add_owned_path(user_data, owned_path);
    return Ok(());
}

#[pyfunction(name = "_RUSTFFI_ioring_prep_read")]
pub fn ioring_prep_read(
    ring: &mut TheIoRing,
    fd: RawFd,
    max_size: u32,
    offset: i64,
    user_data: u64,
    py: Python<'_>,
) -> PyResult<()> {
    if !ring.probe.is_supported(io_uring::opcode::Read::CODE) {
        return Err(PyNotImplementedError::new_err("read"));
    }

    let mut buf: Vec<u8> = vec![0; max_size as usize];
    let ring_op = io_uring::opcode::Read::new(Fd(fd), buf.as_mut_ptr(), max_size)
        .offset(offset as u64)
        .build()
        .user_data(user_data);

    ring.autosubmit(py, &ring_op)?;
    ring.add_owned_buffer(user_data, buf);
    return Ok(());
}

#[pyfunction(name = "_RUSTFFI_ioring_prep_write")]
pub fn ioring_prep_write(
    ring: &mut TheIoRing,
    fd: RawFd,
    data: &[u8],
    size: u32,
    buffer_offset: usize,
    file_offset: i64,
    user_data: u64,
    py: Python<'_>,
) -> PyResult<()> {
    if !ring.probe.is_supported(io_uring::opcode::Write::CODE) {
        return Err(PyNotImplementedError::new_err("read"));
    }

    if size as usize > data.len() {
        let message = format!("can't write {} bytes from a vec of {}", size, data.len());
        return Err(PyValueError::new_err(message));
    }

    if buffer_offset > data.len() {
        let message = format!(
            "offset {} out of range from vec of {}",
            buffer_offset,
            data.len()
        );
        return Err(PyValueError::new_err(message));
    }

    let end_offset = buffer_offset + (size as usize);
    if end_offset > data.len() {
        let message = format!(
            "offset {} out of range from vec of {}",
            end_offset,
            data.len()
        );
        return Err(PyValueError::new_err(message));
    }

    // like the read op, we need to make sure the read-from buffer outlives us.
    // so we copy it to our own buffer, let the ring own it, and then it's deallocated later on
    let vec = data[buffer_offset..end_offset].to_vec();

    let ring_op = io_uring::opcode::Write::new(Fd(fd), vec.as_ptr(), vec.len() as u32)
        .offset(file_offset as u64)
        .build()
        .user_data(user_data);

    ring.autosubmit(py, &ring_op)?;
    ring.add_owned_buffer(user_data, vec);

    return Ok(());
}
