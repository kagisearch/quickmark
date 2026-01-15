QM_DIR := $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))


install_toolchain:
	# Install rust / cargo
	# https://doc.rust-lang.org/cargo/getting-started/installation.html
	curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
	rustup update
	# Install uv package manager
	curl -LsSf https://astral.sh/uv/install.sh | sh
	uv sync


clean:
	rm -rf $(QM_DIR)/target
	rm -rf $(QM_DIR)/quickmark/.venv
	rm -f  $(QM_DIR)/quickmark/pyproject.toml.lock
	rm -f  $(QM_DIR)/quickmark/Cargo.toml.lock
	rm -f  $(QM_DIR)/quickmark/uv.lock
	cargo clean

build:
	uv sync
	cargo clean
	cargo update
	cargo build
	cargo test
	# Run python tests
	uv run tox run
	# TODO: Make this work; more tests run
	# TODO: Also add GFM fixtures from
	# https://github.com/markdown-it-rust/markdown-it-plugins.rs/tree/main/crates/gfm/tests
	# uv run python -m pytest ./python/tests
	uv run maturin build --release

