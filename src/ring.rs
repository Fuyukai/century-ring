use std::{collections::HashMap, os::fd::RawFd, sync::atomic::AtomicU64};

use io_uring::{cqueue::Entry, squeue::Flags, types::Timespec};
use nix::sys::socket::SockaddrLike;
use pyo3::{
    exceptions::{PyOSError, PyValueError},
    pyclass, pyfunction, pymethods,
    types::PyModule,
    Bound, PyResult, Python,
};

#[pyclass]
pub struct CompletionEvent {
    pub user_data: u64,
    pub result: i32,
    pub buffer: Option<Vec<u8>>,
}

#[pymethods]
impl CompletionEvent {
    #[getter]
    pub fn user_data(&self) -> u64 {
        return self.user_data;
    }

    #[getter]
    pub fn result(&self) -> i32 {
        return self.result;
    }

    #[getter]
    pub fn buffer(&mut self) -> Option<&[u8]> {
        return self.buffer.as_deref();
    }

    pub fn should_be_ignored(&self) -> bool {
        return (self.user_data & (1 << 63)) != 0;
    }
}

#[allow(dead_code)]
pub enum OwnedData {
    OnePath(Vec<u8>),
    TwoPaths(Vec<u8>, Vec<u8>),
    Buffer(Vec<u8>),
    SockAddr(Box<dyn SockaddrLike + Send>),
}

#[pyclass(weakref)]
pub struct TheIoRing {
    pub(crate) the_io_uring: Option<io_uring::IoUring>,
    pub(crate) probe: io_uring::Probe,

    user_data_counter: AtomicU64,
    autosubmit: bool,

    owned_data: HashMap<u64, OwnedData>,
}

// non-python methods
impl TheIoRing {
    pub fn add_owned_path(&mut self, user_data: u64, path: Vec<u8>) {
        let data = OwnedData::OnePath(path);
        self.owned_data.insert(user_data, data);
    }

    pub fn add_owned_buffer(&mut self, user_data: u64, buf: Vec<u8>) {
        let data = OwnedData::Buffer(buf);
        self.owned_data.insert(user_data, data);
    }

    pub fn add_owned_sockaddr(&mut self, user_data: u64, addr: Box<dyn SockaddrLike + Send>) {
        self.owned_data.insert(user_data, OwnedData::SockAddr(addr));
    }

    pub fn autosubmit(&mut self, entry: &io_uring::squeue::Entry) -> PyResult<()> {
        let Some(ring) = &mut self.the_io_uring else {
            return Err(PyValueError::new_err("The ring is closed"));
        };

        let mut needs_submit = false;

        loop {
            if needs_submit {
                ring.submit()?;
            }

            let result = unsafe { ring.submission().push(entry) };
            if result.is_err() {
                if needs_submit || !self.autosubmit {
                    return Err(PyValueError::new_err(
                        "submission queue is full and submitting didn't help!",
                    ));
                } else {
                    needs_submit = true;
                    continue;
                }
            }
            return Ok(());
        }
    }
}

// exposed python methods
#[pymethods]
impl TheIoRing {
    pub fn get_next_user_data(&mut self) -> u64 {
        return self
            .user_data_counter
            .fetch_add(1, std::sync::atomic::Ordering::Relaxed);
    }

    pub fn submit(&mut self) -> PyResult<usize> {
        if let Some(ring) = &self.the_io_uring {
            return Ok(ring.submit()?);
        }

        return Err(PyValueError::new_err("The ring is closed"));
    }

    pub fn wait(&mut self, py: Python<'_>, want: usize) -> PyResult<usize> {
        if let Some(ring) = &self.the_io_uring {
            let result = py.allow_threads(|| Ok(ring.submit_and_wait(want)?));
            return result;
        }

        return Err(PyValueError::new_err("The ring is closed"));
    }

    pub fn wait_with_timeout(&mut self, py: Python<'_>, sec: u64, nsec: u32) -> PyResult<usize> {
        let Some(ring) = &mut self.the_io_uring else {
            return Err(PyValueError::new_err("The ring is closed"));
        };

        // purge the queue!! don't want to push a timeout op and just have it... not do anything
        let count = ring.submit()?;

        // playing stack-frame chicken with rust here
        let timespec = Timespec::new().sec(sec).nsec(nsec);
        let timeout = io_uring::opcode::Timeout::new(&timespec)
            .build()
            .flags(Flags::SKIP_SUCCESS)
            .user_data(0xFFFF_FF00);

        unsafe { ring.submission().push(&timeout) }
            .map_err(|_| PyValueError::new_err("Couldn't submit timeout operation"))?;

        py.allow_threads(|| ring.submit_and_wait(1))?;
        return Ok(count);
    }

    pub fn get_completion_entries(&mut self) -> PyResult<Vec<CompletionEvent>> {
        let mut entries = Vec::<Entry>::new();
        let Some(ring) = &mut self.the_io_uring else {
            return Err(PyValueError::new_err("The ring is closed"));
        };

        // arcane borrow checker incantations, because completion() returns an entirely new object
        // that actually points to
        loop {
            let completion = ring.completion();

            if completion.is_empty() {
                break;
            }
            entries.extend(completion);

            ring.completion().sync();
        }

        let completed_results: Vec<CompletionEvent> = entries
            .iter()
            .map(|e| {
                let buffer = self
                    .owned_data
                    .remove(&e.user_data())
                    .and_then(|owned| match owned {
                        OwnedData::Buffer(mut buf) => {
                            if e.result() < 0 || buf.len() == (e.result() as usize) {
                                return Some(buf);
                            }

                            buf.resize(e.result() as usize, 0);
                            return Some(buf);
                        }
                        _ => {
                            return None;
                        }
                    });

                return CompletionEvent {
                    user_data: e.user_data(),
                    result: e.result(),
                    buffer,
                };
            })
            .collect();

        return Ok(completed_results);
    }

    pub fn register_eventfd(&mut self, event_fd: RawFd) -> PyResult<()> {
        let Some(ring) = &mut self.the_io_uring else {
            return Err(PyValueError::new_err("The ring is closed"));
        };
        ring.submitter().register_eventfd(event_fd)?;
        return Ok(());
    }

    pub fn close(&mut self) -> PyResult<()> {
        self.the_io_uring = None;
        return Ok(());
    }
}

#[pyfunction(name = "_RUSTFFI_create_io_ring", pass_module)]
pub fn create_io_ring(
    module: &Bound<'_, PyModule>,
    entries: u32,
    cq_entries: u32,
    sqlpoll_idle_ms: u32,
    single_issuer: bool,
    autosubmit: bool,
) -> PyResult<TheIoRing> {
    return module.py().allow_threads(|| {
        // sanity checking for better errors
        if entries == 0 {
            return Err(PyValueError::new_err("Entries should be more than zero"));
        }

        // certain things are locked behind newer kernels, ee.g. setup_coop_taskrun, or unprivileged
        // sqpoll
        let kernel_version =
            procfs::KernelVersion::current().unwrap_or(procfs::KernelVersion::new(5, 18, 0));
        if kernel_version.major < 5 || (kernel_version.major < 6 && kernel_version.minor < 18) {
            let message = format!(
                "Kernel version unsupported; needs >=5.18, got {}.{}",
                kernel_version.major, kernel_version.minor
            );
            return Err(PyOSError::new_err(message));
        }

        let mut probe = io_uring::Probe::new();

        let mut builder: &mut io_uring::Builder<io_uring::squeue::Entry, io_uring::cqueue::Entry> =
            &mut io_uring::IoUring::builder();

        // we *always* want submit_all, because it makes for saner behaviour
        // likewise, making it "don't fork" makes things easier to reason about.
        builder = builder.dontfork().setup_submit_all();

        if kernel_version.major >= 6 && single_issuer {
            builder = builder.setup_single_issuer();
        };

        // It looks like this binding doesn't correctly handle this (sigh...)
        /*if kernel_version.major >= 6 || kernel_version.minor >= 19 {
            builder = builder.setup_coop_taskrun();
            builder = builder.setup_taskrun_flag();
        }*/

        if sqlpoll_idle_ms > 0 {
            builder = builder.setup_sqpoll(sqlpoll_idle_ms);
        }

        if cq_entries > entries {
            builder = builder.setup_cqsize(cq_entries);
        }

        let ring = builder.setup_submit_all().build(entries)?;

        assert!(
            ring.params().is_feature_nodrop(),
            "io_uring doesn't support nodrop even though it should!"
        );

        ring.submitter().register_probe(&mut probe)?;

        let our_ring = TheIoRing {
            the_io_uring: Some(ring),
            probe,
            user_data_counter: AtomicU64::new(0),
            autosubmit,
            owned_data: HashMap::new(),
        };

        return Ok(our_ring);
    });
}
