"""Tests for Jarvis module base, loader, and CLI."""

from pathlib import Path
import pytest

from jarvis.cli import main
from jarvis.modules import (
    BASE_PARTS,
    DEFAULT_BASE_DIR,
    DEFAULT_MODULES_DIR,
    ModuleBase,
    ModuleConfigError,
    load_module,
    load_modules,
)


def _write_module_toml(module_dir: Path, extra_lines: str = "", task_size: str = "short") -> Path:
    """Create a module folder with module.toml, skills/, and extensions/."""
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / "skills").mkdir(exist_ok=True)
    (module_dir / "extensions").mkdir(exist_ok=True)
    toml_content = (
        'name = "shopping"\n'
        'description = "Buy groceries on Tesco"\n'
        'agent = "pi"\n'
        'model = "claude-sonnet-4-5"\n'
        'directory = "modules/shopping"\n'
        f'task_size = "{task_size}"\n'
        'required_gates = ["pay"]\n'
        'mcp_servers = ["ego-browser"]\n'
    )
    if extra_lines:
        toml_content += extra_lines + "\n"
    toml_path = module_dir / "module.toml"
    toml_path.write_text(toml_content, encoding="utf-8")
    return module_dir


def test_new_folder_with_only_toml_skills_extensions_shows_in_cli_and_gets_base(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify a new folder with only module.toml, skills/, and extensions/ loads and gets all four base parts."""
    _write_module_toml(tmp_path / "shopping")

    loaded = load_modules(tmp_path)
    assert len(loaded) == 1

    mod = loaded[0]
    assert mod.name == "shopping"
    assert mod.description == "Buy groceries on Tesco"
    assert mod.agent == "pi"
    assert mod.model == "claude-sonnet-4-5"
    assert mod.directory == "modules/shopping"
    assert mod.task_size == "short"
    assert mod.required_gates == ("pay",)
    assert mod.mcp_servers == ("ego-browser",)

    assert mod.gate_rule is True
    assert mod.dag_contract is True
    assert mod.test_node_rule is True
    assert mod.compaction_step is True
    assert mod.base_parts == {part: True for part in BASE_PARTS}
    assert mod.claude_md_files == (DEFAULT_BASE_DIR / "CLAUDE.md",)
    assert mod.skills_dir.is_dir()
    assert mod.extensions_dir.is_dir()

    rc = main(["modules", "--modules-dir", str(tmp_path)])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.strip() == "shopping: Buy groceries on Tesco"


def test_underscore_and_dot_folders_are_skipped_by_loader_and_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify folders starting with '_' or '.' are ignored during discovery."""
    _write_module_toml(tmp_path / "_base_custom")
    _write_module_toml(tmp_path / "_example")
    _write_module_toml(tmp_path / ".hidden")

    assert load_modules(tmp_path) == []

    rc = main(["modules", "--modules-dir", str(tmp_path)])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == ""


def test_repo_default_modules_and_example_template() -> None:
    """Verify repository _base and _example exist and _example satisfies the contract."""
    assert (DEFAULT_BASE_DIR / "CLAUDE.md").is_file()
    example_mod = load_module(DEFAULT_MODULES_DIR / "_example")
    assert example_mod.name == "example"
    assert example_mod.base_parts == {part: True for part in BASE_PARTS}
    assert example_mod.claude_md_files == (
        DEFAULT_BASE_DIR / "CLAUDE.md",
        (DEFAULT_MODULES_DIR / "_example" / "CLAUDE.md").resolve(),
    )


def test_long_task_size_and_empty_lists_accepted(tmp_path: Path) -> None:
    """Verify boundary values task_size='long' and empty list fields are accepted."""
    mod_dir = tmp_path / "builder"
    mod_dir.mkdir()
    (mod_dir / "module.toml").write_text(
        'name = "builder"\n'
        'description = "Build a new Jarvis module"\n'
        'agent = "pi"\n'
        'model = "claude-opus-4-5"\n'
        'directory = "modules/builder"\n'
        'task_size = "long"\n'
        "required_gates = []\n"
        "mcp_servers = []\n",
        encoding="utf-8",
    )
    mod = load_module(mod_dir)
    assert mod.task_size == "long"
    assert mod.required_gates == ()
    assert mod.mcp_servers == ()


@pytest.mark.parametrize(
    "forbidden_line",
    [
        "gate_rule = false",
        "dag_contract = false",
        "test_node_rule = false",
        "compaction_step = false",
        "engine_owns_gates = false",
        "requires_test_node = false",
        "compact_on_run_end = false",
        "disable_gates = true",
        "skip_test = true",
        "disable_compaction = true",
        "[base]\ngate_rule = false",
    ],
)
def test_module_attempting_to_turn_off_base_part_is_refused(
    tmp_path: Path, forbidden_line: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify any module.toml key that tries to disable or override a base part is refused."""
    mod_dir = _write_module_toml(tmp_path / "rogue", extra_lines=forbidden_line)

    with pytest.raises(ModuleConfigError, match="base parts"):
        load_module(mod_dir)

    rc = main(["modules", "--modules-dir", str(tmp_path)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "base parts" in captured.err


@pytest.mark.parametrize(
    "kwargs",
    [
        {"gate_rule": False},
        {"dag_contract": False},
        {"test_node_rule": False},
        {"compaction_step": False},
    ],
)
def test_module_base_cannot_be_instantiated_with_disabled_part(
    kwargs: dict[str, bool],
) -> None:
    """Verify ModuleBase refuses instantiation if any of the four rules is False."""
    with pytest.raises(ModuleConfigError, match="All four module base parts"):
        ModuleBase(**kwargs)


def test_invalid_inputs_raise_module_config_error(tmp_path: Path) -> None:
    """Verify missing files, malformed TOML, missing keys, and invalid types fail fast."""
    missing_dir = tmp_path / "does_not_exist"
    with pytest.raises(ModuleConfigError, match="not a directory"):
        load_module(missing_dir)

    empty_dir = tmp_path / "empty_mod"
    empty_dir.mkdir()
    with pytest.raises(ModuleConfigError, match="Missing module.toml"):
        load_module(empty_dir)

    bad_toml_dir = tmp_path / "bad_toml"
    bad_toml_dir.mkdir()
    (bad_toml_dir / "module.toml").write_text("name = [unclosed", encoding="utf-8")
    with pytest.raises(ModuleConfigError, match="Invalid TOML"):
        load_module(bad_toml_dir)

    bad_size_dir = _write_module_toml(tmp_path / "bad_size", task_size="medium")
    with pytest.raises(ModuleConfigError, match="must be 'short' or 'long'"):
        load_module(bad_size_dir)

    missing_key_dir = tmp_path / "missing_key"
    missing_key_dir.mkdir()
    (missing_key_dir / "module.toml").write_text('name = "only_name"\n', encoding="utf-8")
    with pytest.raises(ModuleConfigError, match="missing required keys"):
        load_module(missing_key_dir)

    bad_gates_dir = tmp_path / "bad_gates"
    bad_gates_dir.mkdir()
    (bad_gates_dir / "module.toml").write_text(
        'name = "bad_gates"\n'
        'description = "Bad gates type"\n'
        'agent = "pi"\n'
        'model = "claude-sonnet-4-5"\n'
        'directory = "modules/bad_gates"\n'
        'task_size = "short"\n'
        'required_gates = "pay"\n'
        "mcp_servers = []\n",
        encoding="utf-8",
    )
    with pytest.raises(ModuleConfigError, match="must be a list of non-empty strings"):
        load_module(bad_gates_dir)
