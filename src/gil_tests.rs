use crate::mdparser::{core::CoreRule, extset::MarkdownItExt};
use crate::{MDParser, MarkdownIt, Node};
use pyo3::Python;
use std::sync::{mpsc, Mutex};
use std::thread;
use std::time::Duration;

const TIMEOUT: Duration = Duration::from_secs(10);

#[derive(Debug)]
struct GilHandshake {
    render_started: mpsc::Sender<()>,
    gil_acquired: Mutex<mpsc::Receiver<()>>,
}

impl MarkdownItExt for GilHandshake {}

struct WaitForPythonThread;

impl CoreRule for WaitForPythonThread {
    fn run(_: &mut Node, parser: &MarkdownIt) {
        let handshake = parser.ext.get::<GilHandshake>().unwrap();
        handshake.render_started.send(()).unwrap();
        // A Rust channel wait cannot release the GIL itself. The worker can
        // acknowledge this signal only if render() has already released it.
        handshake
            .gil_acquired
            .lock()
            .unwrap()
            .recv_timeout(TIMEOUT)
            .expect("another thread could not acquire the GIL during render()");
    }
}

#[test]
fn render_releases_gil() {
    Python::initialize();
    let (render_started, wait_for_render) = mpsc::channel();
    let (gil_acquired, wait_for_gil) = mpsc::channel();

    let worker = thread::spawn(move || {
        wait_for_render
            .recv_timeout(TIMEOUT)
            .expect("render() did not reach the handshake rule");
        Python::attach(|_py| gil_acquired.send(()))
    });

    let result = Python::attach(|py| {
        let mut parser = MDParser::new("commonmark").unwrap();
        parser.parser.ext.insert(GilHandshake {
            render_started,
            gil_acquired: Mutex::new(wait_for_gil),
        });
        parser.parser.add_rule::<WaitForPythonThread>().before_all();
        parser.render(py, "# Hello", true)
    });

    // Join after releasing the GIL so the worker can finish even when render()
    // fails to detach and the handshake times out.
    let worker_result = worker.join().expect("GIL probe worker panicked");
    assert_eq!(
        result.expect("render() must release the GIL"),
        "<h1>Hello</h1>\n"
    );
    worker_result.expect("render() returned before the worker acquired the GIL");
}
