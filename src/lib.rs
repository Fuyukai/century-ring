#![deny(clippy::all)]
#![allow(clippy::needless_return)] // fuck off and DIE
#![allow(clippy::too_many_arguments)] // fuck off and die even harder!

mod files;
mod ring;

use files::{ioring_prep_openat, ioring_prep_read, ioring_prep_write};
use pyo3::prelude::*;
use ring::{create_io_ring, CompletionEvent, TheIoRing};

#[pymodule]
fn _century_ring(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<TheIoRing>()?;
    m.add_class::<CompletionEvent>()?;
    m.add_function(wrap_pyfunction!(create_io_ring, m)?)?;

    m.add_function(wrap_pyfunction!(ioring_prep_openat, m)?)?;
    m.add_function(wrap_pyfunction!(ioring_prep_read, m)?)?;
    m.add_function(wrap_pyfunction!(ioring_prep_write, m)?)?;

    return Ok(());
}
