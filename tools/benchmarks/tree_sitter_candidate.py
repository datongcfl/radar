#!/usr/bin/env python3
"""Isolated Tree-sitter syntax coverage probe; not Radar runtime code."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
import time
from pathlib import Path

from tree_sitter import Language, Parser
import tree_sitter_python
import tree_sitter_javascript
import tree_sitter_java
import tree_sitter_go

SAMPLES = {
    "python": {
        "module": tree_sitter_python,
        "source": (
            "from radar import analyze\n"
            "class Receipt:\n"
            "    def submit(self, qty: int):\n"
            "        if self.status == 'Draft':\n"
            "            self.status = 'Submitted'\n"
            "        return qty > 0\n"
        ),
        "expected": ["import_from_statement", "class_definition", "function_definition"],
        "broken": "def broken(:\n    return True\n",
    },
    "javascript": {
        "module": tree_sitter_javascript,
        "source": (
            'import { Client } from "./client";\n'
            "export class Receipt {\n"
            "  submit(qty) { return qty > 0; }\n"
            "}\n"
            'export function approve(order) { return order.status === "Draft"; }\n'
        ),
        "expected": ["import_statement", "class_declaration", "function_declaration"],
        "broken": "function broken( {\n",
    },
    "java": {
        "module": tree_sitter_java,
        "source": (
            "package demo;\n"
            "import java.util.List;\n"
            "public class Receipt {\n"
            "  public boolean submit(int qty) { return qty > 0; }\n"
            "}\n"
        ),
        "expected": ["import_declaration", "class_declaration", "method_declaration"],
        "broken": "class Broken { void submit( { }\n",
    },
    "go": {
        "module": tree_sitter_go,
        "source": (
            "package procurement\n"
            'import "fmt"\n'
            "type Receipt struct { Qty int }\n"
            "func (r Receipt) Submit() bool {\n"
            "    fmt.Println(r.Qty)\n"
            "    return r.Qty > 0\n"
            "}\n"
        ),
        "expected": ["import_declaration", "type_declaration", "method_declaration"],
        "broken": "func broken( {\n",
    },
}


def descendants(root):
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.children))


def parse_one(name, spec):
    grammar = Language(spec["module"].language())
    parser = Parser(grammar)
    source = spec["source"].encode("utf-8")
    started = time.perf_counter()
    tree = parser.parse(source)
    parse_seconds = time.perf_counter() - started
    nodes = list(descendants(tree.root_node))
    counts = {}
    for node in nodes:
        counts[node.type] = counts.get(node.type, 0) + 1

    expected = spec["expected"]
    expected_present = {node_type: counts.get(node_type, 0) > 0 for node_type in expected}
    first_locators = {}
    for node in nodes:
        if node.type in expected and node.type not in first_locators:
            first_locators[node.type] = {
                "start_point": list(node.start_point),
                "end_point": list(node.end_point),
                "start_byte": node.start_byte,
                "end_byte": node.end_byte,
            }

    broken_tree = parser.parse(spec["broken"].encode("utf-8"))
    return {
        "language": name,
        "grammar_package": spec["module"].__name__,
        "grammar_version": importlib.metadata.version(spec["module"].__name__.replace("_", "-")),
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "source_lines": len(spec["source"].splitlines()),
        "parse_seconds": round(parse_seconds, 7),
        "root_type": tree.root_node.type,
        "root_has_error": tree.root_node.has_error,
        "expected_node_types": expected_present,
        "first_node_locators": first_locators,
        "broken_input_detected": broken_tree.root_node.has_error,
        "named_node_count": sum(1 for node in nodes if node.is_named),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    results = [parse_one(name, spec) for name, spec in SAMPLES.items()]

    from radar.code_analyzer import analyze_python_source
    python_ast = analyze_python_source(SAMPLES["python"]["source"], "receipt.py")
    report = {
        "benchmark": "tree-sitter-multilanguage-syntax-probe",
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "tree_sitter_version": importlib.metadata.version("tree-sitter"),
        "grammar_versions": {
            module.__name__: importlib.metadata.version(module.__name__.replace("_", "-"))
            for module in [tree_sitter_python, tree_sitter_javascript, tree_sitter_java, tree_sitter_go]
        },
        "languages": results,
        "radar_python_ast_baseline": {
            "status": python_ast["status"],
            "imports": len(python_ast["imports"]),
            "state_transitions": len(python_ast["state_transitions"]),
        },
        "scope_warning": (
            "Synthetic syntax fixtures only. This does not benchmark semantic correctness, "
            "cross-file relationships, runtime behavior, or business state-machine inference."
        ),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
