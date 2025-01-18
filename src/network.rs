use std::net::{Ipv4Addr, Ipv6Addr, SocketAddr};
use std::str::FromStr;
use std::{net::IpAddr, os::fd::RawFd};

use io_uring::squeue::Flags;
use io_uring::types::Fd;
use nix::sys::socket::SockaddrLike;
use pyo3::exceptions::{PyNotImplementedError, PyValueError};
use pyo3::PyResult;

use crate::ring::TheIoRing;
use crate::shared::check_write_buffer;

/// Performs a ``socket(2)`` call via io_uring.
#[pyo3::pyfunction(name = "_RUSTFFI_ioring_prep_create_socket")]
pub fn ioring_prep_create_socket(
    ring: &mut TheIoRing,
    domain: i32,
    socket_type: i32,
    protocol: i32,
    user_data: u64,
    sqe_flags: u8,
) -> PyResult<()> {
    if !ring.probe.is_supported(io_uring::opcode::Socket::CODE) {
        return Err(PyNotImplementedError::new_err("socket"));
    }

    let entry = io_uring::opcode::Socket::new(domain, socket_type, protocol)
        .build()
        .flags(Flags::from_bits_truncate(sqe_flags))
        .user_data(user_data);

    ring.autosubmit(&entry)?;
    return Ok(());
}

// does the conversion sockaddr dance
fn do_sockaddr_submit(
    ring: &mut TheIoRing,
    fd: RawFd,
    addr: SocketAddr,
    user_data: u64,
    sqe_flags: u8,
) -> PyResult<()> {
    let c_addr: Box<dyn SockaddrLike + Send + Sync> = match addr {
        SocketAddr::V4(it) => Box::new(nix::sys::socket::SockaddrIn::from(it)),
        SocketAddr::V6(it) => Box::new(nix::sys::socket::SockaddrIn6::from(it)),
    };

    let flags = Flags::from_bits_truncate(sqe_flags);
    if flags.contains(Flags::SKIP_SUCCESS) {
        return Err(PyValueError::new_err(
            "Can't use 'SKIP_SUCCESS' on submissions with owned data",
        ));
    }

    let entry = io_uring::opcode::Connect::new(Fd(fd), c_addr.as_ptr(), c_addr.len())
        .build()
        .flags(flags)
        .user_data(user_data);

    ring.autosubmit(&entry)?;
    ring.add_owned_sockaddr(user_data, c_addr);
    return Ok(());
}

/// Performs a ``connect(2)`` call via io_uring for AF_INET sockets.
#[pyo3::pyfunction(name = "_RUSTFFI_ioring_prep_connect_v4")]
pub fn ioring_prep_connect_v4(
    ring: &mut TheIoRing,
    fd: RawFd,
    ip: &str,
    port: u16,
    user_data: u64,
    sqe_flags: u8,
) -> PyResult<()> {
    if !ring.probe.is_supported(io_uring::opcode::Connect::CODE) {
        return Err(PyNotImplementedError::new_err("connect"));
    }

    let v4 = Ipv4Addr::from_str(ip)?;
    let rust_addr = SocketAddr::new(IpAddr::V4(v4), port);

    do_sockaddr_submit(ring, fd, rust_addr, user_data, sqe_flags)?;

    return Ok(());
}

/// Performs a ``connect(2)`` call via io_uring for AF_INET6 sockets.
#[pyo3::pyfunction(name = "_RUSTFFI_ioring_prep_connect_v6")]
pub fn ioring_prep_connect_v6(
    ring: &mut TheIoRing,
    fd: RawFd,
    ip: &str,
    port: u16,
    user_data: u64,
    sqe_flags: u8,
) -> PyResult<()> {
    if !ring.probe.is_supported(io_uring::opcode::Connect::CODE) {
        return Err(PyNotImplementedError::new_err("connect"));
    }

    let v6 = Ipv6Addr::from_str(ip)?;
    let rust_addr = SocketAddr::new(IpAddr::V6(v6), port);

    do_sockaddr_submit(ring, fd, rust_addr, user_data, sqe_flags)?;

    return Ok(());
}

/// Performs a ``send(2)`` call via io_uring.
#[pyo3::pyfunction(name = "_RUSTFFI_ioring_prep_send")]
pub fn ioring_prep_send(
    ring: &mut TheIoRing,
    fd: RawFd,
    data: &[u8],
    size: usize,
    buffer_offset: usize,
    flags: i32,
    user_data: u64,
    sqe_flags: u8,
) -> PyResult<()> {
    if !ring.probe.is_supported(io_uring::opcode::Send::CODE) {
        return Err(PyNotImplementedError::new_err("send"));
    }

    let parsed_sqe_flags = Flags::from_bits_truncate(sqe_flags);
    if parsed_sqe_flags.contains(Flags::SKIP_SUCCESS) {
        return Err(PyValueError::new_err(
            "Can't use 'SKIP_SUCCESS' on submissions with owned data",
        ));
    }

    let end_offset = check_write_buffer(data, size, buffer_offset)?;
    let vec = data[buffer_offset..end_offset].to_vec();
    let entry = io_uring::opcode::Send::new(Fd(fd), vec.as_ptr(), vec.len() as u32)
        .flags(flags)
        .build()
        .flags(parsed_sqe_flags)
        .user_data(user_data);

    ring.autosubmit(&entry)?;
    ring.add_owned_buffer(user_data, vec);

    return Ok(());
}

/// Performs a ``recv(2)`` call via io_uring.
#[pyo3::pyfunction(name = "_RUSTFFI_ioring_prep_recv")]
pub fn ioring_prep_recv(
    ring: &mut TheIoRing,
    fd: RawFd,
    max_size: u32,
    flags: i32,
    user_data: u64,
    sqe_flags: u8,
) -> PyResult<()> {
    if !ring.probe.is_supported(io_uring::opcode::Recv::CODE) {
        return Err(PyNotImplementedError::new_err("recv"));
    }
    
    let parsed_sqe_flags = Flags::from_bits_truncate(sqe_flags);
    if parsed_sqe_flags.contains(Flags::SKIP_SUCCESS) {
        return Err(PyValueError::new_err(
            "Can't use 'SKIP_SUCCESS' on submissions with owned data",
        ));
    }

    let mut buf: Vec<u8> = vec![0; max_size as usize];
    let entry = io_uring::opcode::Recv::new(Fd(fd), buf.as_mut_ptr(), max_size)
        .flags(flags)
        .build()
        .flags(parsed_sqe_flags)
        .user_data(user_data);

    ring.autosubmit(&entry)?;
    ring.add_owned_buffer(user_data, buf);

    return Ok(());
}
