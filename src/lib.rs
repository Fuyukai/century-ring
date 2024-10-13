#![deny(clippy::all)]
#![allow(clippy::needless_return)] // fuck off and DIE
#![allow(clippy::too_many_arguments)] // fuck off and die even harder!

mod files;
mod flags;
mod network;
mod ring;
mod shared;

use files::{ioring_prep_openat, ioring_prep_read, ioring_prep_write};
use flags::make_uring_flags;
use network::{
    ioring_prep_connect_v4, ioring_prep_connect_v6, ioring_prep_create_socket, ioring_prep_recv,
    ioring_prep_send,
};
use pyo3::prelude::*;
use ring::{create_io_ring, CompletionEvent, TheIoRing};
use shared::ioring_prep_close;

#[pymodule]
fn _century_ring(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<TheIoRing>()?;
    m.add_class::<CompletionEvent>()?;
    m.add_function(wrap_pyfunction!(create_io_ring, m)?)?;

    m.add_function(wrap_pyfunction!(make_uring_flags, m)?)?;

    m.add_function(wrap_pyfunction!(ioring_prep_openat, m)?)?;
    m.add_function(wrap_pyfunction!(ioring_prep_read, m)?)?;
    m.add_function(wrap_pyfunction!(ioring_prep_write, m)?)?;
    m.add_function(wrap_pyfunction!(ioring_prep_close, m)?)?;
    m.add_function(wrap_pyfunction!(ioring_prep_create_socket, m)?)?;
    m.add_function(wrap_pyfunction!(ioring_prep_connect_v4, m)?)?;
    m.add_function(wrap_pyfunction!(ioring_prep_connect_v6, m)?)?;
    m.add_function(wrap_pyfunction!(ioring_prep_send, m)?)?;
    m.add_function(wrap_pyfunction!(ioring_prep_recv, m)?)?;

    return Ok(());
}
