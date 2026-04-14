QM_DIR := $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))


install_toolchain:
	# Install rust / cargo
	# https://doc.rust-lang.org/cargo/getting-started/installation.html
	curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
	rustup update
	# Install uv package manager
	curl -LsSf https://astral.sh/uv/install.sh | sh
	uv sync


setup:
	uv sync
	cargo update

clean:
	cargo clean
	# Python Build
	find . -type d -name ".venv" -prune -exec rm -rf {} \;
	find . -type d -name "*.egg-info" -prune -exec rm -rf {} \;
	find . -type f -name "uv.lock" -prune -exec rm -f {} \;
	find . -type f -name "pyproject.toml.lock" -prune -exec rm -rf {} \;
	# Rust Build
	find . -type d -name "target" -prune -exec rm -rf {} \;
	find . -type f -name "Cargo.lock" -prune -exec rm -f {} \;
	find . -type f -name "Cargo.toml.lock" -prune -exec rm -f {} \;


build:
	$(MAKE) setup
	cargo build
	cargo test
	# Run python tests
	uv run pytest -n 4
	# TODO (Matt): Add GFM fixtures from
	# https://github.com/markdown-it-rust/markdown-it-plugins.rs/tree/main/crates/gfm/tests
	# uv run python -m pytest ./python/tests
	uv run maturin build --release

