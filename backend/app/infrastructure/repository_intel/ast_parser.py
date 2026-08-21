"""
Tree-sitter Multi-Language AST Parser & Symbol Extraction Engine
Parses source code into Abstract Syntax Trees, extracts functions, classes, imports, and docstrings.
"""

import os
import re
from typing import Any

try:
    import tree_sitter_languages
    from tree_sitter import Parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    tree_sitter_languages = None
    Parser = None
    TREE_SITTER_AVAILABLE = False

from app.core.logging import get_logger
from app.core.telemetry import AST_PARSE_DURATION_HISTOGRAM

logger = get_logger("codemigration.intel.ast")

# Language Extension Mapping
EXT_TO_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".cs": "c_sharp",
    ".rb": "ruby",
    ".php": "php",
    ".cpp": "cpp",
    ".c": "c",
}


class ASTSymbolParser:
    def __init__(self) -> None:
        self._parsers: dict[str, Parser] = {}

    def _get_parser(self, language: str) -> Any:
        """Load or retrieve a cached Tree-sitter parser for a specific language."""
        if not TREE_SITTER_AVAILABLE or not tree_sitter_languages or not Parser:
            return None

        if language in self._parsers:
            return self._parsers[language]

        try:
            ts_lang = tree_sitter_languages.get_language(language)

            # tree-sitter >= 0.22.0 has removed set_language and expects a Language object in the constructor.
            # However, tree_sitter_languages may return an incompatible Language object from an older bundled version.
            # We must recreate the Language object using the new API if possible.
            try:
                # Check if we are using newer tree-sitter API
                if not hasattr(Parser, "set_language"):
                    from tree_sitter import Language
                    # Reconstruct the Language object using the pointer from the old object
                    if hasattr(ts_lang, "language_id"): # tree_sitter_languages older Language object
                        ts_lang = Language(ts_lang.language_id, language)
                    elif hasattr(ts_lang, "ptr"): # Newer object
                        ts_lang = Language(ts_lang.ptr, language)
                    parser = Parser(ts_lang)
                else:
                    # Old API fallback
                    parser = Parser()
                    parser.set_language(ts_lang)
            except Exception:
                # If reconstruction fails, just try the constructor directly (might work on some versions)
                parser = Parser(ts_lang)

            self._parsers[language] = parser
            return parser
        except Exception as e:
            logger.warning("Could not initialize Tree-sitter parser for language", language=language, error=str(e))
            return None

    def detect_language(self, file_path: str) -> str | None:
        """Detect programming language from file extension."""
        _, ext = os.path.splitext(file_path)
        return EXT_TO_LANG.get(ext.lower())

    def parse_file(self, file_path: str, source_code: str) -> dict[str, Any]:
        """Parse source code into AST and extract structured symbols."""
        lang_name = self.detect_language(file_path)
        if not lang_name:
            return {
                "file_path": file_path,
                "language": "unknown",
                "loc": len(source_code.splitlines()),
                "symbols": [],
                "imports": [],
                "classes": [],
                "functions": [],
            }

        parser = self._get_parser(lang_name)
        if not parser:
            return self._fallback_regex_parse(file_path, lang_name, source_code)

        lines = source_code.splitlines()
        loc = len(lines)
        code_bytes = source_code.encode("utf-8")

        with AST_PARSE_DURATION_HISTOGRAM.labels(language=lang_name).time():
            tree = parser.parse(code_bytes)

        symbols: list[dict[str, Any]] = []
        classes: list[dict[str, Any]] = []
        functions: list[dict[str, Any]] = []
        imports: list[dict[str, Any]] = []
        calls: list[dict[str, Any]] = []

        def traverse(node, current_function_id=None):
            node_type = node.type
            # 1. Functions / Methods
            if node_type in (
                "function_definition",
                "function_declaration",
                "method_definition",
                "method_declaration",
                "arrow_function",
            ):
                name = self._extract_identifier(node, code_bytes) or "anonymous_function"
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1
                is_async = "async" in node_type or (node.prev_sibling and "async" in node.prev_sibling.type)

                current_function_id = f"{file_path}::{name}::{start_line}"
                func_data = {
                    "id": current_function_id,
                    "name": name,
                    "type": "function",
                    "file_path": file_path,
                    "start_line": start_line,
                    "end_line": end_line,
                    "is_async": is_async,
                    "complexity": self._estimate_cyclomatic_complexity(node),
                }
                functions.append(func_data)
                symbols.append(func_data)

            # 2. Classes
            elif node_type in ("class_definition", "class_declaration"):
                name = self._extract_identifier(node, code_bytes) or "AnonymousClass"
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1

                class_data = {
                    "id": f"{file_path}::{name}::{start_line}",
                    "name": name,
                    "type": "class",
                    "file_path": file_path,
                    "start_line": start_line,
                    "end_line": end_line,
                    "complexity": 1,
                }
                classes.append(class_data)
                symbols.append(class_data)

            # 3. Imports
            elif "import" in node_type or "use_declaration" in node_type:
                raw_text = code_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")

                target_file = None
                match = re.search(r'[\'"]([^\'"]+)[\'"]', raw_text)
                if match:
                    target_file = match.group(1)
                else:
                    match = re.search(r'(?:from|import)\s+([a-zA-Z0-9_\.]+)', raw_text)
                    if match:
                        target_file = match.group(1).replace('.', '/')

                imports.append({
                    "source_file": file_path,
                    "raw_import": raw_text.strip(),
                    "target_file": target_file or "unknown",
                    "line": node.start_point[0] + 1,
                })

            # 4. Calls
            elif node_type in ("call", "call_expression"):
                if current_function_id:
                    callee_name = None
                    if node.child_count > 0:
                        callee_node = node.children[0]
                        raw_callee = code_bytes[callee_node.start_byte : callee_node.end_byte].decode("utf-8", errors="ignore")
                        callee_name = raw_callee.split(".")[-1] # Simple heuristic to get the function name

                    if callee_name:
                        calls.append({
                            "caller_id": current_function_id,
                            "callee_name": callee_name,
                            "line": node.start_point[0] + 1,
                        })

            for child in node.children:
                traverse(child, current_function_id)

        traverse(tree.root_node)

        return {
            "file_path": file_path,
            "language": lang_name,
            "loc": loc,
            "symbols": symbols,
            "classes": classes,
            "functions": functions,
            "imports": imports,
            "calls": calls,
        }

    def _extract_identifier(self, node, code_bytes: bytes) -> str | None:
        """Find identifier child node."""
        for child in node.children:
            if child.type in ("identifier", "name", "property_identifier"):
                return code_bytes[child.start_byte : child.end_byte].decode("utf-8", errors="ignore")
        return None

    def _estimate_cyclomatic_complexity(self, node) -> int:
        """Calculate cyclomatic complexity by counting branch AST nodes."""
        branch_types = {
            "if_statement", "elif_clause", "else_clause", "for_statement", "while_statement",
            "case_clause", "catch_clause", "conditional_expression", "try_statement",
        }
        complexity = 1

        def count_branches(n):
            nonlocal complexity
            if n.type in branch_types:
                complexity += 1
            for child in n.children:
                count_branches(child)

        count_branches(node)
        return complexity

    def _fallback_regex_parse(self, file_path: str, language: str, source_code: str) -> dict[str, Any]:
        """Regex-based fallback if Tree-sitter grammar is not available."""
        lines = source_code.splitlines()
        symbols = []
        for idx, line in enumerate(lines, 1):
            # Match python/js classes, functions, and exported functions/consts
            if re.search(r"^\s*(?:export\s+)?(?:default\s+)?(def|class|async def|function|const\s+\w+\s*=)\s+([a-zA-Z_]\w*)", line):
                match = re.search(r"(?:export\s+)?(?:default\s+)?(?:def|class|async def|function|const)\s+([a-zA-Z_]\w*)", line)
                if match:
                    name = match.group(1)
                    sym_type = "class" if "class" in line else "function"
                    symbols.append({
                        "id": f"{file_path}::{name}::{idx}",
                        "name": name,
                        "type": sym_type,
                        "file_path": file_path,
                        "start_line": idx,
                        "end_line": idx,
                        "complexity": 1,
                    })
        return {
            "file_path": file_path,
            "language": language,
            "loc": len(lines),
            "symbols": symbols,
            "classes": [s for s in symbols if s["type"] == "class"],
            "functions": [s for s in symbols if s["type"] == "function"],
            "imports": [],
        }


ast_parser = ASTSymbolParser()
