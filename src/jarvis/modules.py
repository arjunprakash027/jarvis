"""Module base contract and folder loader for Jarvis."""

from dataclasses import dataclass
from pathlib import Path
import tomllib
from typing import Literal

TaskSize = Literal["short", "long"]

BASE_PARTS: tuple[str, str, str, str] = (
    "gate_rule",
    "dag_contract",
    "test_node_rule",
    "compaction_step",
)

ALLOWED_MODULE_KEYS: frozenset[str] = frozenset(
    {
        "name",
        "description",
        "agent",
        "model",
        "directory",
        "task_size",
        "required_gates",
        "mcp_servers",
    }
)

FORBIDDEN_BASE_KEYS: frozenset[str] = frozenset(
    {
        "base",
        "gate_rule",
        "engine_owns_gates",
        "disable_gates",
        "skip_gates",
        "dag_contract",
        "requires_dag",
        "disable_dag",
        "skip_dag",
        "test_node",
        "test_node_rule",
        "requires_test_node",
        "disable_test_node",
        "skip_test_node",
        "skip_test",
        "compaction",
        "compaction_step",
        "compact_on_run_end",
        "disable_compaction",
        "skip_compaction",
    }
)

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
DEFAULT_MODULES_DIR: Path = REPO_ROOT / "modules"
DEFAULT_BASE_DIR: Path = DEFAULT_MODULES_DIR / "_base"


class ModuleConfigError(ValueError):
    """Raised when a module folder or module.toml violates the module contract."""


@dataclass(frozen=True)
class ModuleBase:
    """Immutable base contract inherited by every Jarvis module."""

    gate_rule: bool = True
    dag_contract: bool = True
    test_node_rule: bool = True
    compaction_step: bool = True
    node_types: tuple[str, str, str] = ("step", "test", "gate")
    dag_relpath: str = "tasks/{task_id}/dag.json"
    base_dir: Path = DEFAULT_BASE_DIR

    def __post_init__(self) -> None:
        if not (
            self.gate_rule
            and self.dag_contract
            and self.test_node_rule
            and self.compaction_step
        ):
            raise ModuleConfigError("All four module base parts must remain enabled.")

    @property
    def base_claude_md(self) -> Path:
        """Return the path to the base CLAUDE.md loaded into every module session."""
        return self.base_dir / "CLAUDE.md"

    @property
    def parts(self) -> dict[str, bool]:
        """Return the status map of the four mandatory base rules."""
        return {
            "gate_rule": self.gate_rule,
            "dag_contract": self.dag_contract,
            "test_node_rule": self.test_node_rule,
            "compaction_step": self.compaction_step,
        }


@dataclass(frozen=True)
class Module:
    """Loaded Jarvis module definition combining module.toml with the mandatory ModuleBase."""

    name: str
    description: str
    agent: str
    model: str
    directory: str
    task_size: TaskSize
    required_gates: tuple[str, ...]
    mcp_servers: tuple[str, ...]
    path: Path
    base: ModuleBase = ModuleBase()

    @property
    def gate_rule(self) -> bool:
        """Confirm the engine owns gates and enforces required_gates."""
        return self.base.gate_rule

    @property
    def dag_contract(self) -> bool:
        """Confirm tasks execute as validated DAGs in tasks/<id>/dag.json."""
        return self.base.dag_contract

    @property
    def test_node_rule(self) -> bool:
        """Confirm every task DAG must include at least one test node."""
        return self.base.test_node_rule

    @property
    def compaction_step(self) -> bool:
        """Confirm the module's session compacts its context when a run ends."""
        return self.base.compaction_step

    @property
    def base_parts(self) -> dict[str, bool]:
        """Return the four mandatory base parts attached to this module."""
        return self.base.parts

    @property
    def claude_md_files(self) -> tuple[Path, ...]:
        """Return the ordered CLAUDE.md files loaded for this module's session."""
        module_claude = self.path / "CLAUDE.md"
        if module_claude.is_file():
            return (self.base.base_claude_md, module_claude)
        return (self.base.base_claude_md,)

    @property
    def skills_dir(self) -> Path:
        """Return the module's skills directory path."""
        return self.path / "skills"

    @property
    def extensions_dir(self) -> Path:
        """Return the module's extensions directory path."""
        return self.path / "extensions"

    @property
    def tasks_dir(self) -> Path:
        """Return the module's tasks directory path."""
        return self.path / "tasks"


def _validate_non_empty_str(raw: object, field_name: str, toml_path: Path) -> str:
    """Validate that a TOML field is a non-empty string."""
    if not isinstance(raw, str) or not raw.strip():
        raise ModuleConfigError(
            f"{toml_path}: '{field_name}' must be a non-empty string."
        )
    return raw.strip()


def _validate_str_tuple(
    raw: object, field_name: str, toml_path: Path
) -> tuple[str, ...]:
    """Validate that a TOML field is a list of non-empty strings."""
    if not isinstance(raw, list) or any(
        not isinstance(item, str) or not item.strip() for item in raw
    ):
        raise ModuleConfigError(
            f"{toml_path}: '{field_name}' must be a list of non-empty strings."
        )
    return tuple(item.strip() for item in raw)


def _resolve_base(module_dir: Path) -> ModuleBase:
    """Resolve the ModuleBase for a given module directory."""
    sibling_base = module_dir.parent / "_base"
    if (sibling_base / "CLAUDE.md").is_file():
        return ModuleBase(base_dir=sibling_base)
    return ModuleBase(base_dir=DEFAULT_BASE_DIR)


def load_module(module_dir: Path) -> Module:
    """Load and validate a single Jarvis module from its directory."""
    resolved_dir = module_dir.resolve()
    if not resolved_dir.is_dir():
        raise ModuleConfigError(f"Module path is not a directory: {resolved_dir}")

    toml_path = resolved_dir / "module.toml"
    if not toml_path.is_file():
        raise ModuleConfigError(f"Missing module.toml in {resolved_dir}")

    try:
        with toml_path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ModuleConfigError(f"Invalid TOML in {toml_path}: {exc}") from exc

    forbidden_present = sorted(set(data.keys()) & FORBIDDEN_BASE_KEYS)
    if forbidden_present:
        joined = ", ".join(forbidden_present)
        raise ModuleConfigError(
            f"{toml_path}: module cannot override or disable base parts ({joined})."
        )

    unknown_keys = sorted(set(data.keys()) - ALLOWED_MODULE_KEYS)
    if unknown_keys:
        joined = ", ".join(unknown_keys)
        raise ModuleConfigError(f"{toml_path}: unsupported keys in module.toml ({joined}).")

    missing_keys = sorted(ALLOWED_MODULE_KEYS - set(data.keys()))
    if missing_keys:
        joined = ", ".join(missing_keys)
        raise ModuleConfigError(f"{toml_path}: missing required keys ({joined}).")

    name = _validate_non_empty_str(data["name"], "name", toml_path)
    description = _validate_non_empty_str(data["description"], "description", toml_path)
    agent = _validate_non_empty_str(data["agent"], "agent", toml_path)
    model = _validate_non_empty_str(data["model"], "model", toml_path)
    directory = _validate_non_empty_str(data["directory"], "directory", toml_path)

    raw_task_size = _validate_non_empty_str(data["task_size"], "task_size", toml_path)
    if raw_task_size not in ("short", "long"):
        raise ModuleConfigError(
            f"{toml_path}: 'task_size' must be 'short' or 'long', got '{raw_task_size}'."
        )
    task_size: TaskSize = "short" if raw_task_size == "short" else "long"

    required_gates = _validate_str_tuple(
        data["required_gates"], "required_gates", toml_path
    )
    mcp_servers = _validate_str_tuple(data["mcp_servers"], "mcp_servers", toml_path)

    return Module(
        name=name,
        description=description,
        agent=agent,
        model=model,
        directory=directory,
        task_size=task_size,
        required_gates=required_gates,
        mcp_servers=mcp_servers,
        path=resolved_dir,
        base=_resolve_base(resolved_dir),
    )


def load_modules(modules_dir: Path = DEFAULT_MODULES_DIR) -> list[Module]:
    """Load all non-underscore module folders from modules_dir in sorted order."""
    resolved_root = modules_dir.resolve()
    if not resolved_root.is_dir():
        raise ModuleConfigError(f"Modules directory does not exist: {resolved_root}")

    loaded: list[Module] = []
    for entry in sorted(resolved_root.iterdir(), key=lambda p: p.name):
        if not entry.is_dir() or entry.name.startswith("_") or entry.name.startswith("."):
            continue
        loaded.append(load_module(entry))
    return loaded
