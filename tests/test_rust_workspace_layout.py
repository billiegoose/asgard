from pathlib import Path


def test_rust_red2_crate_lives_under_models() -> None:
    cargo_toml = Path("models/rust-red2/Cargo.toml")

    assert cargo_toml.is_file()
    assert not Path("red2-wasm/Cargo.toml").exists()
    assert 'name = "red2-wasm"' in cargo_toml.read_text()


def test_root_cargo_workspace_points_at_moved_crate() -> None:
    assert 'members = ["models/rust-red2"]' in Path("Cargo.toml").read_text()
