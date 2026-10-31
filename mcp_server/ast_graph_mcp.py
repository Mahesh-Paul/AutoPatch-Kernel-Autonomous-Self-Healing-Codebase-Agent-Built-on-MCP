"""AST 2-Hop Call-Graph MCP Server & Kernel Syscall Telemetry.

Provides surgical 2-hop neighborhood AST slices and kernel-level crash telemetry
via standardized Model Context Protocol (MCP) tool interfaces.
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field


# ==============================================================================
# Pydantic v2 Schemas for MCP Payloads
# ==============================================================================

class ASTNodeInfo(BaseModel):
    name: str
    file_path: str
    start_line: int
    end_line: int
    docstring: Optional[str] = None
    signature: str = ""
    source_slice: str = ""
    ast_type: str = "FunctionDef"


class ASTSubGraphResponse(BaseModel):
    focal_node: ASTNodeInfo
    upstream_callers: List[ASTNodeInfo] = Field(default_factory=list)
    downstream_callees: List[ASTNodeInfo] = Field(default_factory=list)
    module_imports: List[str] = Field(default_factory=list)
    hop_depth: int = 2
    total_nodes_in_neighborhood: int = 0
    extracted_at_unix: float = Field(default_factory=time.time)


class StackFrameInfo(BaseModel):
    file_path: str
    line_number: int
    function_name: str
    code_statement: Optional[str] = None


class SyscallTelemetry(BaseModel):
    command: str
    cwd: str
    exit_code: int
    duration_ms: float
    stdout: str
    stderr: str
    detected_exceptions: List[str] = Field(default_factory=list)
    detected_syscall_errors: List[str] = Field(default_factory=list)
    failing_frames: List[StackFrameInfo] = Field(default_factory=list)
    primary_failure_frame: Optional[StackFrameInfo] = None
    missing_paths_or_configs: List[str] = Field(default_factory=list)


# ==============================================================================
# AST Call-Graph Analyzer Engine
# ==============================================================================

class ASTCallGraphEngine:
    """Parses Python source files using standard library `ast`, builds caller/callee

    dependency graphs, and extracts surgical 2-hop subgraphs.
    """

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()
        self._file_ast_cache: Dict[str, Tuple[ast.AST, List[str]]] = {}

    def _get_ast(self, file_path: str) -> Tuple[Optional[ast.AST], List[str]]:
        path_obj = Path(file_path).resolve()
        path_str = str(path_obj)
        if path_str in self._file_ast_cache:
            return self._file_ast_cache[path_str]

        if not path_obj.exists() or not path_obj.is_file():
            return None, []

        try:
            content = path_obj.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=path_str)
            lines = content.splitlines()
            self._file_ast_cache[path_str] = (tree, lines)
            return tree, lines
        except Exception:
            return None, []

    def _get_node_source(self, lines: List[str], start_line: int, end_line: int) -> str:
        if not lines or start_line <= 0:
            return ""
        s = max(0, start_line - 1)
        e = min(len(lines), end_line)
        return "\n".join(lines[s:e])

    def find_enclosing_function(
        self, tree: ast.AST, lines: List[str], line_number: int, file_path: str
    ) -> Optional[ASTNodeInfo]:
        """Finds the most specific FunctionDef or AsyncFunctionDef containing line_number."""
        matching_func: Optional[ast.FunctionDef | ast.AsyncFunctionDef] = None

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = getattr(node, "lineno", 0)
                end = getattr(node, "end_lineno", start)
                if start <= line_number <= end:
                    if matching_func is None:
                        matching_func = node
                    else:
                        # Pick tighter enclosing function (e.g. inner func or nested method)
                        if (end - start) < (
                            getattr(matching_func, "end_lineno", 0)
                            - getattr(matching_func, "lineno", 0)
                        ):
                            matching_func = node

        if not matching_func:
            return None

        start = getattr(matching_func, "lineno", 1)
        end = getattr(matching_func, "end_lineno", start)
        doc = ast.get_docstring(matching_func)

        # Extract signature line
        sig = ""
        if lines and start <= len(lines):
            sig = lines[start - 1].strip()

        return ASTNodeInfo(
            name=matching_func.name,
            file_path=file_path,
            start_line=start,
            end_line=end,
            docstring=doc,
            signature=sig,
            source_slice=self._get_node_source(lines, start, end),
            ast_type=type(matching_func).__name__,
        )

    def _collect_callee_names(self, func_node: ast.AST) -> Set[str]:
        """Collects function and method call names invoked inside an AST node."""
        callees: Set[str] = set()
        for sub in ast.walk(func_node):
            if isinstance(sub, ast.Call):
                if isinstance(sub.func, ast.Name):
                    callees.add(sub.func.id)
                elif isinstance(sub.func, ast.Attribute):
                    callees.add(sub.func.attr)
        return callees

    def _collect_imports_in_module(self, tree: ast.AST) -> List[str]:
        imports = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(f"import {alias.name}" + (f" as {alias.asname}" if alias.asname else ""))
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                names = ", ".join(
                    a.name + (f" as {a.asname}" if a.asname else "") for a in node.names
                )
                imports.append(f"from {mod} import {names}")
        return imports

    def scan_project_functions(self, root_dir: Path) -> List[Tuple[Path, ast.FunctionDef | ast.AsyncFunctionDef, List[str]]]:
        """Discovers all Python functions across the target workspace."""
        functions = []
        for py_path in root_dir.glob("**/*.py"):
            if ".git" in py_path.parts or ".autopatch" in py_path.parts or "venv" in py_path.parts:
                continue
            tree, lines = self._get_ast(str(py_path))
            if not tree:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    functions.append((py_path, node, lines))
        return functions

    def extract_subgraph(
        self, file_path: str, line_number: int, hop_depth: int = 2
    ) -> ASTSubGraphResponse:
        """Extracts the 2-hop AST neighborhood centered around a crash frame."""
        resolved_path = Path(file_path).resolve()
        tree, lines = self._get_ast(str(resolved_path))
        if not tree:
            raise FileNotFoundError(f"Source file not accessible or unparseable: {file_path}")

        # 1. Locate Focal Node
        focal_node = self.find_enclosing_function(tree, lines, line_number, str(resolved_path))
        if not focal_node:
            # Fallback to whole file slice if not in a function
            focal_node = ASTNodeInfo(
                name="<module>",
                file_path=str(resolved_path),
                start_line=max(1, line_number - 10),
                end_line=min(len(lines), line_number + 10),
                source_slice=self._get_node_source(lines, max(1, line_number - 10), min(len(lines), line_number + 10)),
                ast_type="Module",
            )

        module_imports = self._collect_imports_in_module(tree)

        # 2. Discover Project-Wide Functions for Graph Traversal
        search_root = resolved_path.parent
        # Go up to workspace root or target project boundary
        if self.workspace_root in resolved_path.parents:
            search_root = self.workspace_root

        project_funcs = self.scan_project_functions(search_root)

        # Build mapping of function name -> Node info & callees
        func_registry: Dict[str, List[Tuple[ASTNodeInfo, Set[str]]]] = {}
        for p_path, node, f_lines in project_funcs:
            name = node.name
            start = getattr(node, "lineno", 1)
            end = getattr(node, "end_lineno", start)
            info = ASTNodeInfo(
                name=name,
                file_path=str(p_path),
                start_line=start,
                end_line=end,
                docstring=ast.get_docstring(node),
                signature=f_lines[start - 1].strip() if start <= len(f_lines) else "",
                source_slice=self._get_node_source(f_lines, start, end),
                ast_type=type(node).__name__,
            )
            callees = self._collect_callee_names(node)
            func_registry.setdefault(name, []).append((info, callees))

        # 3. Upstream Callers (Who calls focal_node?)
        upstream_callers: List[ASTNodeInfo] = []
        visited_callers: Set[Tuple[str, str]] = set()

        def find_callers_for(target_name: str, current_hop: int):
            if current_hop > hop_depth:
                return
            for fname, entries in func_registry.items():
                for c_info, c_callees in entries:
                    if target_name in c_callees:
                        key = (c_info.file_path, c_info.name)
                        if key != (focal_node.file_path, focal_node.name) and key not in visited_callers:
                            visited_callers.add(key)
                            upstream_callers.append(c_info)
                            find_callers_for(c_info.name, current_hop + 1)

        find_callers_for(focal_node.name, 1)

        # 4. Downstream Callees (Who does focal_node call?)
        downstream_callees: List[ASTNodeInfo] = []
        visited_callees: Set[Tuple[str, str]] = set()

        # Find direct focal node ast
        focal_ast_node = None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == focal_node.name:
                focal_ast_node = node
                break

        focal_direct_callees = self._collect_callee_names(focal_ast_node) if focal_ast_node else set()

        def find_callees_for(callee_names: Set[str], current_hop: int):
            if current_hop > hop_depth:
                return
            for cname in callee_names:
                if cname in func_registry:
                    for d_info, d_callees in func_registry[cname]:
                        key = (d_info.file_path, d_info.name)
                        if key != (focal_node.file_path, focal_node.name) and key not in visited_callees:
                            visited_callees.add(key)
                            downstream_callees.append(d_info)
                            find_callees_for(d_callees, current_hop + 1)

        find_callees_for(focal_direct_callees, 1)

        return ASTSubGraphResponse(
            focal_node=focal_node,
            upstream_callers=upstream_callers,
            downstream_callees=downstream_callees,
            module_imports=module_imports,
            hop_depth=hop_depth,
            total_nodes_in_neighborhood=1 + len(upstream_callers) + len(downstream_callees),
        )


# ==============================================================================
# Kernel Syscall & Crash Telemetry Capturer
# ==============================================================================

class SyscallTelemetryEngine:
    """Executes a failing command in an isolated subprocess and inspects OS-level

    failures and Python runtime crash traces.
    """

    KNOWN_SYSCALL_ERRORS = [
        "ENOENT",  # File or directory not found
        "EACCES",  # Permission denied
        "EPERM",   # Operation not permitted
        "ECONNREFUSED",  # Connection refused
        "ETIMEDOUT",     # Operation timed out
        "ENOMEM",  # Out of memory
    ]

    FRAME_REGEX = re.compile(
        r'File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<func>\w+)(?:\n\s+(?P<stmt>.+))?',
        re.MULTILINE,
    )
    EXCEPTION_REGEX = re.compile(
        r"^(?P<exc>[A-Za-z_][A-Za-z0-9_]*Error|[A-Za-z_][A-Za-z0-9_]*Exception): (?P<msg>.+)$",
        re.MULTILINE,
    )
    MISSING_PATH_REGEX = re.compile(
        r"(?:No such file or directory|cannot open file|cannot find module|ModuleNotFoundError|KeyError)[:\s]+['\"]?(?P<path>[^'\"\n\r]+)['\"]?",
        re.IGNORECASE,
    )

    @classmethod
    def capture(
        cls,
        command: str | List[str],
        cwd: Optional[str] = None,
        timeout_seconds: float = 30.0,
        env_overrides: Optional[Dict[str, str]] = None,
    ) -> SyscallTelemetry:
        """Runs the given command, recording runtime output and extracting root failure coordinates."""
        execution_cwd = Path(cwd or os.getcwd()).resolve()
        cmd_str = command if isinstance(command, str) else " ".join(command)

        env = os.environ.copy()
        if env_overrides:
            env.update(env_overrides)

        start_time = time.perf_counter()
        try:
            process = subprocess.run(
                command,
                cwd=str(execution_cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=isinstance(command, str),
                timeout=timeout_seconds,
                env=env,
            )
            stdout = process.stdout
            stderr = process.stderr
            exit_code = process.returncode
        except subprocess.TimeoutExpired as te:
            stdout = te.stdout or "" if isinstance(te.stdout, str) else ""
            stderr = f"TIMEOUT: Command exceeded {timeout_seconds}s"
            exit_code = -9
        except Exception as ex:
            stdout = ""
            stderr = f"Execution invocation failed: {str(ex)}"
            exit_code = -1

        duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        combined_output = f"{stdout}\n{stderr}"

        # 1. Detect Syscall and OS Errors
        detected_syscalls: List[str] = []
        for code in cls.KNOWN_SYSCALL_ERRORS:
            if code in combined_output:
                detected_syscalls.append(code)

        # 2. Extract Python Exceptions
        detected_exceptions = [
            f"{m.group('exc')}: {m.group('msg')}"
            for m in cls.EXCEPTION_REGEX.finditer(combined_output)
        ]

        # 3. Parse Stack Frames
        frames: List[StackFrameInfo] = []
        for m in cls.FRAME_REGEX.finditer(combined_output):
            frames.append(
                StackFrameInfo(
                    file_path=m.group("file"),
                    line_number=int(m.group("line")),
                    function_name=m.group("func"),
                    code_statement=(m.group("stmt") or "").strip(),
                )
            )

        # Identify Primary Failure Frame (deepest frame inside the user's project)
        primary_frame: Optional[StackFrameInfo] = None
        for frame in reversed(frames):
            p = Path(frame.file_path)
            # Prioritize project files over python stdlib / site-packages
            if "site-packages" not in str(p) and "Lib" not in str(p) and p.exists():
                primary_frame = frame
                break
        if not primary_frame and frames:
            primary_frame = frames[-1]

        # 4. Extract Missing Paths / Environment Variables
        missing_paths = [
            m.group("path").strip()
            for m in cls.MISSING_PATH_REGEX.finditer(combined_output)
        ]

        return SyscallTelemetry(
            command=cmd_str,
            cwd=str(execution_cwd),
            exit_code=exit_code,
            duration_ms=duration_ms,
            stdout=stdout,
            stderr=stderr,
            detected_exceptions=detected_exceptions,
            detected_syscall_errors=detected_syscalls,
            failing_frames=frames,
            primary_failure_frame=primary_frame,
            missing_paths_or_configs=list(set(missing_paths)),
        )


# ==============================================================================
# Model Context Protocol (MCP) Server Tool Interface
# ==============================================================================

class AutoPatchMCPServer:
    """Production-grade MCP Server exposing AST subgraph extraction and syscall telemetry."""

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()
        self.ast_engine = ASTCallGraphEngine(str(self.workspace_root))
        self.telemetry_engine = SyscallTelemetryEngine()

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Returns standard MCP tool declarations for client discovery."""
        return [
            {
                "name": "extract_ast_subgraph",
                "description": "Extracts the exact 2-hop AST neighborhood (upstream callers, downstream callees, and signatures) centered around a failing stack frame.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Absolute or workspace-relative path to the Python source file.",
                        },
                        "line_number": {
                            "type": "integer",
                            "description": "Line number of the crash or focal point.",
                        },
                        "hop_depth": {
                            "type": "integer",
                            "default": 2,
                            "description": "Neighborhood depth (1 or 2 hops).",
                        },
                    },
                    "required": ["file_path", "line_number"],
                },
            },
            {
                "name": "capture_syscall_telemetry",
                "description": "Executes a failing command in an isolated subprocess, capturing stdout/stderr, stack traces, and OS-level syscall error codes (ENOENT, EACCES).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Shell command line to execute.",
                        },
                        "cwd": {
                            "type": "string",
                            "description": "Optional working directory.",
                        },
                    },
                    "required": ["command"],
                },
            },
        ]

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches tool execution according to MCP specification."""
        if tool_name == "extract_ast_subgraph":
            res = self.ast_engine.extract_subgraph(
                file_path=arguments["file_path"],
                line_number=int(arguments["line_number"]),
                hop_depth=int(arguments.get("hop_depth", 2)),
            )
            return res.model_dump()
        elif tool_name == "capture_syscall_telemetry":
            res = self.telemetry_engine.capture(
                command=arguments["command"],
                cwd=arguments.get("cwd", str(self.workspace_root)),
            )
            return res.model_dump()
        else:
            raise ValueError(f"Unknown MCP tool requested: {tool_name}")
