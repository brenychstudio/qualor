"""Exercise the real maintained compiler; npm ci is a prerequisite, never skipped."""

import json
import os
import subprocess
from pathlib import Path

from qualor.schemas.export import CONTRACTS

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps/web"
GENERATOR = WEB / "scripts/generate-domain.mjs"


def generate(*args):
    return subprocess.run(
        ["node", str(GENERATOR), *map(str, args)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )


def compile_types(path):
    return subprocess.run(
        [str(WEB / "node_modules/.bin/tsc.cmd") if os.name == "nt"
         else str(WEB / "node_modules/.bin/tsc"),
         "--ignoreConfig", "--noEmit", "--strict", "--skipLibCheck", str(path)],
        cwd=WEB, capture_output=True, text=True, check=False,
    )


def test_generation_is_deterministic_and_check_detects_drift_without_writing(tmp_path):
    output = tmp_path / "domain.ts"
    first = generate("--output", output)
    assert first.returncode == 0, first.stderr
    before = output.read_bytes()
    assert b"json-schema-to-typescript" in before
    assert generate("--output", output).returncode == 0
    assert output.read_bytes() == before
    assert generate("--check", "--output", output).returncode == 0
    output.write_bytes(b"stale")
    assert generate("--check", "--output", output).returncode != 0
    assert output.read_bytes() == b"stale"
    assert generate("--check").returncode == 0


def test_all_public_types_compile_and_reject_invalid_contracts(tmp_path):
    output = tmp_path / "domain.ts"
    result = generate("--output", output)
    assert result.returncode == 0, result.stderr
    consumer = tmp_path / "consumer.ts"
    consumer.write_text(
        "import type {" + ",".join(model.__name__ for model in CONTRACTS)
        + ", Money} from './domain';\n"
        "const amount: Money = {amount: '12.50', currency: 'USD'};\n"
        "const mode: DecisionFixture['mode'] = 'FIXTURE';\n"
        "const recommendation: DecisionResult['recommendation'] = 'WATCH';\n"
        "const score: DecisionRecord['strategy_score'] = null;\n"
        "const rank: InboxItem['priority_rank'] = 0;\n"
        "const discovered: InboxItem['discovered_at'] = '2026-09-05T12:00:00Z';\n"
        "// @ts-expect-error rank is a server integer, not a string\n"
        "const badRank: InboxItem['priority_rank'] = 'first';\n"
        "// @ts-expect-error discovery time is a required datetime string\n"
        "const badDiscovered: InboxItem['discovered_at'] = null;\n"
        "declare const rule: RuleCandidate;\n"
        "const nested: RuleCandidate = {...rule, children: [rule]};\n"
        "// @ts-expect-error canonical recursive children remain rules\n"
        "const badChild: RuleCandidate = {...rule, children: [1]};\n"
        "// @ts-expect-error money serializes to decimal strings\n"
        "const badAmount: Money = {amount: 12.5, currency: 'USD'};\n"
        "// @ts-expect-error fixture is not live\n"
        "const live: DecisionFixture['mode'] = 'LIVE';\n"
        "// @ts-expect-error unknown does not mean apply\n"
        "const badRecommendation: DecisionResult['recommendation'] = 'READY';\n"
        "// @ts-expect-error required contract fields cannot disappear\n"
        "const empty: DecisionRecord = {};\n",
        encoding="utf-8",
    )
    result = compile_types(consumer)
    assert result.returncode == 0, result.stdout + result.stderr


def test_recursive_shared_definitions_and_incompatible_collisions(tmp_path):
    schemas = tmp_path / "schemas"
    schemas.mkdir()
    node = {"title": "Tree", "type": "object", "additionalProperties": False,
            "properties": {"value": {"type": "string"},
                           "child": {"$ref": "#/$defs/Tree"}}, "required": ["value"]}
    for name in ("Tree", "Forest"):
        schema = {"$defs": {"Tree": node}, "$ref": "#/$defs/Tree"} if name == "Tree" else {
            "$defs": {"Tree": node}, "title": "Forest", "type": "array",
            "items": {"$ref": "#/$defs/Tree"}}
        (schemas / f"{name}.schema.json").write_text(json.dumps(schema))
    output = tmp_path / "domain.ts"
    result = generate("--schema-dir", schemas, "--output", output)
    assert result.returncode == 0, result.stderr
    assert output.read_text().count("export interface Tree {") == 1
    consumer = tmp_path / "consumer.ts"
    consumer.write_text("import type {Tree, Forest} from './domain';\n"
                        "const tree: Tree = {value: 'a', child: {value: 'b'}};\n"
                        "const forest: Forest = [tree];\n"
                        "// @ts-expect-error recursive value stays a string\n"
                        "const bad: Tree = {value: 'a', child: {value: 1}};\n")
    result = compile_types(consumer)
    assert result.returncode == 0, result.stdout + result.stderr
    node["properties"]["value"] = {"type": "number"}
    (schemas / "Other.schema.json").write_text(json.dumps({
        "title": "Other", "type": "object", "$defs": {"Tree": node}}))
    before = output.read_bytes()
    result = generate("--schema-dir", schemas, "--output", output)
    assert result.returncode != 0
    assert "Incompatible definition collision: Tree" in result.stderr
    assert output.read_bytes() == before
