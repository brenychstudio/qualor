"""Generate or check public JSON Schema without network or third-party code generation."""

import argparse
import json
from pathlib import Path

from qualor.domain import (
    EligibilityGate,
    EvidenceRecord,
    FounderProfile,
    OpportunityRecord,
    ProjectProfile,
    Reward,
    RuleCandidate,
    RuleEvaluation,
)

CONTRACTS = (
    FounderProfile,
    ProjectProfile,
    OpportunityRecord,
    EvidenceRecord,
    RuleCandidate,
    RuleEvaluation,
    EligibilityGate,
    Reward,
)
DEFAULT_OUTPUT = Path(__file__).resolve().parents[3] / "schemas"


def _render() -> dict[str, bytes]:
    return {
        model.__name__ + ".schema.json": (
            json.dumps(
                model.model_json_schema(mode="serialization"),
                sort_keys=True,
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")
        for model in CONTRACTS
    }


def export_schemas(output_dir: Path) -> tuple[Path, ...]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, content in sorted(_render().items()):
        path = output_dir / name
        path.write_bytes(content)
        paths.append(path)
    return tuple(paths)


def check_schemas(output_dir: Path) -> bool:
    expected = _render()
    if {path.name for path in output_dir.glob("*.schema.json")} != set(expected):
        return False
    return all((output_dir / name).read_bytes() == content for name, content in expected.items())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.check:
        valid = check_schemas(args.output)
        print("SCHEMA_EXPORT=" + ("PASS" if valid else "DRIFT"))
        return 0 if valid else 1
    paths = export_schemas(args.output)
    print(f"SCHEMA_EXPORT=PASS\nSCHEMA_FILES={len(paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
