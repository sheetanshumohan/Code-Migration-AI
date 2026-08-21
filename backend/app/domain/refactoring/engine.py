"""
AST-Driven Code Refactoring Engine
Executes semantic transformations: symbol renaming, dead code removal, method extraction, and SOLID optimizations.
"""

import ast
import re

from app.core.logging import get_logger

logger = get_logger("codemigration.refactor.engine")


class RefactoringEngine:
    @staticmethod
    def remove_unused_imports_python(code: str) -> str:
        """Analyze Python AST to identify and eliminate unused top-level imports."""
        try:
            tree = ast.parse(code)
        except Exception:
            return code

        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name)

        # Collect used names
        used_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Store):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    used_names.add(node.value.id)

        # Clean lines
        lines = code.splitlines()
        filtered_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                # If any imported symbol on this line is used, keep it
                tokens = re.findall(r"\b\w+\b", stripped)
                if any(t in used_names for t in tokens if t not in ["import", "from"]):
                    filtered_lines.append(line)
            else:
                filtered_lines.append(line)

        return "\n".join(filtered_lines)

    @staticmethod
    def rename_symbol(code: str, old_symbol: str, new_symbol: str) -> str:
        """Safely rename a function or variable symbol using word boundary regex matching."""
        pattern = re.compile(rf"\b{re.escape(old_symbol)}\b")
        return pattern.sub(new_symbol, code)

    @staticmethod
    def extract_method(
        code: str, target_lines_start: int, target_lines_end: int, new_method_name: str
    ) -> str:
        """Extract a block of lines into a new helper function and replace with function call."""
        lines = code.splitlines()
        if target_lines_start < 1 or target_lines_end > len(lines):
            return code

        extracted_block = lines[target_lines_start - 1 : target_lines_end]
        indent = "    "
        new_func = f"\ndef {new_method_name}():\n" + "\n".join(f"{indent}{line.strip()}" for line in extracted_block) + "\n"

        call_line = f"{indent}{new_method_name}()"
        updated_lines = (
            lines[: target_lines_start - 1]
            + [call_line]
            + lines[target_lines_end:]
        )
        return "\n".join(updated_lines) + "\n" + new_func


    @staticmethod
    def extract_class(
        code: str, target_methods: list[str], new_class_name: str
    ) -> str:
        """Extract designated functions into a new cohesive class (SOLID improvements)."""
        try:
            tree = ast.parse(code)
        except Exception:
            return code

        lines = code.splitlines()
        funcs_to_extract = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in target_methods:
                funcs_to_extract.append(node)

        if not funcs_to_extract:
            return code

        # Sort by line number descending to safely delete from bottom to top
        funcs_to_extract.sort(key=lambda n: n.lineno, reverse=True)

        extracted_code_blocks = []
        for func in funcs_to_extract:
            start_line = func.lineno - 1
            end_line = getattr(func, "end_lineno", len(lines))
            # Extract lines and indent them
            func_lines = lines[start_line:end_line]
            # Replace `def func_name(` with `def func_name(self, `
            if len(func_lines) > 0 and func_lines[0].startswith("def "):
                func_lines[0] = func_lines[0].replace("(", "(self, ", 1).replace("(self, )", "(self)")

            extracted_code_blocks.append("\n".join(f"    {line}" for line in func_lines))
            # Remove from original lines
            del lines[start_line:end_line]

        extracted_code_blocks.reverse()

        new_class_str = f"\nclass {new_class_name}:\n" + "\n\n".join(extracted_code_blocks) + "\n"
        return "\n".join(lines) + "\n" + new_class_str

refactoring_engine = RefactoringEngine()
