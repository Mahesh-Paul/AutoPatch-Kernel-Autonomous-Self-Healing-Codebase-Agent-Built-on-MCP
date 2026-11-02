"""Model Context Protocol (MCP) Server: Dual-Plane AST Graph & Kernel Telemetry.

Provides surgical 2-hop neighborhood AST slicing and operating-system level crash telemetry
conforming to the Anthropic/Model Context Protocol (MCP) tool specification standard.
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from pydantic import BaseModel, Field


# ==============================================================================
# Domain Exceptions
# ==============================================================================

class MCPInstrumentationError(Exception):
    """Base exception for Model Context Protocol instrumentation failures."""
    pass


class ASTResolutionError(MCPInstrumentationError):
    """Raised when an AST node coordinate cannot be resolved within source boundaries."""
    pass


class TelemetryCaptureError(MCPInstrumentationError):
    """Raised when an isolated subprocess execution fails to emit valid telemetry."""
    pass


class UnknownMCPToolException(MCPInstrumentationError):
    """Raised when an unsupported MCP tool identifier is invoked."""
    pass


# ==============================================================================
# Pydantic v2 Schemas for MCP Tool Contracts
# ==============================================================================

class ASTNodeInfo(BaseModel):
    """Represents a discrete Python function, method, or coroutine within an AST."""
    name: str
    file_path: str
    start_line: int
    end_line: int
    docstring: Optional[str] = None
    signature: str = ""
    source_slice: str = ""
    ast_type: str = "FunctionDef"


class ASTSubGraphResponse(BaseModel):
    """Surgical 2-hop causal neighborhood extracted around a crash frame."""
    focal_node: ASTNodeInfo
    upstream_callers: List[ASTNodeInfo] = Field(default_factory=list)
    downstream_callees: List[ASTNodeInfo] = Field(default_factory=list)
    module_imports: List[str] = Field(default_factory=list)
    hop_depth: int = 2
    total_nodes_in_neighborhood: int = 0
    extracted_at_unix: float = Field(default_factory=time.time)


class StackFrameInfo(BaseModel):
    """Parsed stack trace execution frame."""
    file_path: str
    line_number: int
    function_name: str
    code_statement: Optional[str] = None


class SyscallTelemetry(BaseModel):
    """Low-level operating system and runtime crash telemetry envelope."""
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
    """Performs static syntax tree analysis to isolate 2-hop causal neighborhoods.
    
    Rather than streaming whole-file or whole-repo contexts to language models (which
    introduces context dilution and hallucination bugs), this engine extracts only:
    - The focal crashing function definition.
    - 2-hop upstream caller sites invoking the target routine.
    - 1-hop downstream functions and mathematical helpers called by the target.
    """

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()
        # In-memory syntax tree cache to prevent redundant disk I/O on large multi-file targets
        self._parsed_ast_cache: Dict[str, Tuple[ast.AST, List[str]]] = {}

    def _load_and_parse_syntax_tree(
        self, source_path_str: str
    ) -> Tuple[Optional[ast.AST], List[str]]:
        """Reads and compiles Python source into an Abstract Syntax Tree with line-index cache."""
        normalized_path = Path(source_path_str).resolve()
        canonical_key = str(normalized_path)

        if canonical_key in self._parsed_ast_cache:
            return self._parsed_ast_cache[canonical_key]

        if not normalized_path.exists() or not normalized_path.is_file():
            return None, []

        try:
            raw_source_bytes = normalized_path.read_text(encoding="utf-8")
            abstract_syntax_tree = ast.parse(raw_source_bytes, filename=canonical_key)
            source_token_lines = raw_source_bytes.splitlines()
            self._parsed_ast_cache[canonical_key] = (abstract_syntax_tree, source_token_lines)
            return abstract_syntax_tree, source_token_lines
        except (SyntaxError, UnicodeDecodeError, OSError):
            return None, []

    def _slice_source_tokens(
        self, token_lines: List[str], line_start: int, line_end: int
    ) -> str:
        """Extracts exact character ranges corresponding to an AST statement block."""
        if not token_lines or line_start <= 0:
            return ""
        zero_indexed_start = max(0, line_start - 1)
        clamped_end = min(len(token_lines), line_end)
        return "\n".join(token_lines[zero_indexed_start:clamped_end])

    def find_enclosing_function(
        self,
        abstract_syntax_tree: ast.AST,
        source_token_lines: List[str],
        crash_line_number: int,
        source_file_path: str,
    ) -> Optional[ASTNodeInfo]:
        """Identifies the most tightly bounded FunctionDef or AsyncFunctionDef enclosing crash_line_number."""
        innermost_target_node: Optional[ast.FunctionDef | ast.AsyncFunctionDef] = None

        for candidate_element in ast.walk(abstract_syntax_tree):
            if isinstance(candidate_element, (ast.FunctionDef, ast.AsyncFunctionDef)):
                element_start_lineno = getattr(candidate_element, "lineno", 0)
                element_end_lineno = getattr(candidate_element, "end_lineno", element_start_lineno)

                if element_start_lineno <= crash_line_number <= element_end_lineno:
                    if innermost_target_node is None:
                        innermost_target_node = candidate_element
                    else:
                        # Favor inner nested routines or inner closures over outer container routines
                        current_span = element_end_lineno - element_start_lineno
                        existing_span = (
                            getattr(innermost_target_node, "end_lineno", 0)
                            - getattr(innermost_target_node, "lineno", 0)
                        )
                        if current_span < existing_span:
                            innermost_target_node = candidate_element

        if innermost_target_node is None:
            return None

        resolved_start = getattr(innermost_target_node, "lineno", 1)
        resolved_end = getattr(innermost_target_node, "end_lineno", resolved_start)
        docstring_content = ast.get_docstring(innermost_target_node)

        raw_signature_line = ""
        if source_token_lines and resolved_start <= len(source_token_lines):
            raw_signature_line = source_token_lines[resolved_start - 1].strip()

        return ASTNodeInfo(
            name=innermost_target_node.name,
            file_path=source_file_path,
            start_line=resolved_start,
            end_line=resolved_end,
            docstring=docstring_content,
            signature=raw_signature_line,
            source_slice=self._slice_source_tokens(source_token_lines, resolved_start, resolved_end),
            ast_type=type(innermost_target_node).__name__,
        )

    def _collect_callee_identifiers(self, root_ast_node: ast.AST) -> Set[str]:
        """Traverses an AST block to discover all direct function and attribute call names."""
        callee_identifier_set: Set[str] = set()
        for syntax_element in ast.walk(root_ast_node):
            if isinstance(syntax_element, ast.Call):
                target_callable = syntax_element.func
                if isinstance(target_callable, ast.Name):
                    callee_identifier_set.add(target_callable.id)
                elif isinstance(target_callable, ast.Attribute):
                    callee_identifier_set.add(target_callable.attr)
        return callee_identifier_set

    def _collect_import_statements(self, abstract_syntax_tree: ast.AST) -> List[str]:
        """Harvests module-level import statements to preserve necessary namespace dependencies."""
        collected_import_directives: List[str] = []
        for syntax_element in ast.iter_child_nodes(abstract_syntax_tree):
            if isinstance(syntax_element, ast.Import):
                for alias_spec in syntax_element.names:
                    suffix = f" as {alias_spec.asname}" if alias_spec.asname else ""
                    collected_import_directives.append(f"import {alias_spec.name}{suffix}")
            elif isinstance(syntax_element, ast.ImportFrom):
                originating_module = syntax_element.module or ""
                symbol_names = ", ".join(
                    f"{a.name} as {a.asname}" if a.asname else a.name
                    for a in syntax_element.names
                )
                collected_import_directives.append(f"from {originating_module} import {symbol_names}")
        return collected_import_directives

    def scan_project_functions(
        self, search_root_path: Path
    ) -> List[Tuple[Path, ast.FunctionDef | ast.AsyncFunctionDef, List[str]]]:
        """Scans the repository working tree to discover all candidate routine definitions."""
        discovered_routines: List[Tuple[Path, ast.FunctionDef | ast.AsyncFunctionDef, List[str]]] = []
        ignored_dir_fragments = {".git", ".autopatch", "venv", ".venv", "__pycache__"}

        for python_source_path in search_root_path.glob("**/*.py"):
            if any(fragment in python_source_path.parts for fragment in ignored_dir_fragments):
                continue
            syntax_tree, token_lines = self._load_and_parse_syntax_tree(str(python_source_path))
            if not syntax_tree:
                continue
            for element in ast.walk(syntax_tree):
                if isinstance(element, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    discovered_routines.append((python_source_path, element, token_lines))
        return discovered_routines

    def _build_project_symbol_manifest(
        self, search_root_path: Path
    ) -> Dict[str, List[Tuple[ASTNodeInfo, Set[str]]]]:
        """Constructs an inverted call-graph index: function_name -> [(NodeInfo, set_of_callees)]."""
        project_functions = self.scan_project_functions(search_root_path)
        symbol_manifest: Dict[str, List[Tuple[ASTNodeInfo, Set[str]]]] = {}

        for py_path, function_element, token_lines in project_functions:
            routine_name = function_element.name
            start_lineno = getattr(function_element, "lineno", 1)
            end_lineno = getattr(function_element, "end_lineno", start_lineno)

            node_descriptor = ASTNodeInfo(
                name=routine_name,
                file_path=str(py_path),
                start_line=start_lineno,
                end_line=end_lineno,
                docstring=ast.get_docstring(function_element),
                signature=token_lines[start_lineno - 1].strip() if start_lineno <= len(token_lines) else "",
                source_slice=self._slice_source_tokens(token_lines, start_lineno, end_lineno),
                ast_type=type(function_element).__name__,
            )
            invoked_callees = self._collect_callee_identifiers(function_element)
            symbol_manifest.setdefault(routine_name, []).append((node_descriptor, invoked_callees))

        return symbol_manifest

    def extract_subgraph(
        self, file_path: str, line_number: int, hop_depth: int = 2
    ) -> ASTSubGraphResponse:
        """Extracts the 2-hop causal dependency subgraph centered on the target line."""
        target_file_path = Path(file_path).resolve()
        syntax_tree, token_lines = self._load_and_parse_syntax_tree(str(target_file_path))

        if not syntax_tree:
            raise FileNotFoundError(f"Source file unparseable or inaccessible: {file_path}")

        # 1. Isolate Focal Node
        focal_symbol_descriptor = self.find_enclosing_function(
            syntax_tree, token_lines, line_number, str(target_file_path)
        )
        if not focal_symbol_descriptor:
            # Fallback to bounded module slice if crash occurred at module scope
            lower_bound = max(1, line_number - 10)
            upper_bound = min(len(token_lines), line_number + 10)
            focal_symbol_descriptor = ASTNodeInfo(
                name="<module>",
                file_path=str(target_file_path),
                start_line=lower_bound,
                end_line=upper_bound,
                source_slice=self._slice_source_tokens(token_lines, lower_bound, upper_bound),
                ast_type="Module",
            )

        module_import_directives = self._collect_import_statements(syntax_tree)

        # 2. Build Symbol Manifest across project boundary
        analysis_search_root = (
            self.workspace_root
            if self.workspace_root in target_file_path.parents
            else target_file_path.parent
        )
        symbol_manifest = self._build_project_symbol_manifest(analysis_search_root)

        # 3. Upstream Callers Traversal (BFS / DFS bounded by hop_depth)
        upstream_caller_nodes: List[ASTNodeInfo] = []
        visited_caller_coordinates: Set[Tuple[str, str]] = set()

        def _traverse_upstream_callers(target_symbol_name: str, current_hop: int) -> None:
            if current_hop > hop_depth:
                return
            for registered_name, manifest_entries in symbol_manifest.items():
                for candidate_info, candidate_callees in manifest_entries:
                    if target_symbol_name in candidate_callees:
                        coordinate_key = (candidate_info.file_path, candidate_info.name)
                        focal_key = (focal_symbol_descriptor.file_path, focal_symbol_descriptor.name)
                        if coordinate_key != focal_key and coordinate_key not in visited_caller_coordinates:
                            visited_caller_coordinates.add(coordinate_key)
                            upstream_caller_nodes.append(candidate_info)
                            _traverse_upstream_callers(candidate_info.name, current_hop + 1)

        _traverse_upstream_callers(focal_symbol_descriptor.name, 1)

        # 4. Downstream Callees Traversal
        downstream_callee_nodes: List[ASTNodeInfo] = []
        visited_callee_coordinates: Set[Tuple[str, str]] = set()

        # Extract direct callees invoked within focal block
        focal_ast_node = None
        for element in ast.walk(syntax_tree):
            if (
                isinstance(element, (ast.FunctionDef, ast.AsyncFunctionDef))
                and element.name == focal_symbol_descriptor.name
            ):
                focal_ast_node = element
                break

        direct_callee_identifiers = (
            self._collect_callee_identifiers(focal_ast_node) if focal_ast_node else set()
        )

        def _traverse_downstream_callees(target_callees: Set[str], current_hop: int) -> None:
            if current_hop > hop_depth:
                return
            for callee_id in target_callees:
                if callee_id in symbol_manifest:
                    for downstream_info, child_callees in symbol_manifest[callee_id]:
                        coordinate_key = (downstream_info.file_path, downstream_info.name)
                        focal_key = (focal_symbol_descriptor.file_path, focal_symbol_descriptor.name)
                        if coordinate_key != focal_key and coordinate_key not in visited_callee_coordinates:
                            visited_callee_coordinates.add(coordinate_key)
                            downstream_callee_nodes.append(downstream_info)
                            _traverse_downstream_callees(child_callees, current_hop + 1)

        _traverse_downstream_callees(direct_callee_identifiers, 1)

        return ASTSubGraphResponse(
            focal_node=focal_symbol_descriptor,
            upstream_callers=upstream_caller_nodes,
            downstream_callees=downstream_callee_nodes,
            module_imports=module_import_directives,
            hop_depth=hop_depth,
            total_nodes_in_neighborhood=1 + len(upstream_caller_nodes) + len(downstream_callee_nodes),
        )


# ==============================================================================
# Kernel Syscall & Crash Telemetry Capturer
# ==============================================================================

class SyscallTelemetryEngine:
    """Subprocess supervisor that captures OS-level syscall signatures and runtime exception traces.
    
    Standard stderr output often obscures underlying kernel anomalies. This engine extracts:
    - POSIX / Win32 syscall error codes (ENOENT, EACCES, EPERM, ENOMEM).
    - Unhandled Python exception hierarchy signatures.
    - Deepest project-internal stack frame coordinate for surgical AST pinning.
    """

    KNOWN_SYSCALL_SIGNATURES = (
        "ENOENT",       # Path or library target not found
        "EACCES",       # Filesystem permission barrier
        "EPERM",        # Operation disallowed by kernel capabilities
        "ECONNREFUSED", # TCP socket rejected
        "ETIMEDOUT",    # Network roundtrip timeout
        "ENOMEM",       # Cgroup or virtual memory allocation failure
        "EDEADLK",      # Futex deadlock condition
    )

    REGEX_TRACEBACK_FRAME = re.compile(
        r'File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<func>\w+)(?:\n\s+(?P<stmt>.+))?',
        re.MULTILINE,
    )
    REGEX_RUNTIME_EXCEPTION = re.compile(
        r"^(?P<exc>[A-Za-z_][A-Za-z0-9_]*Error|[A-Za-z_][A-Za-z0-9_]*Exception): (?P<msg>.+)$",
        re.MULTILINE,
    )
    REGEX_UNRESOLVED_PATH = re.compile(
        r"(?:No such file or directory|cannot open file|cannot find module|ModuleNotFoundError|KeyError)[:\s]+['\"]?(?P<path>[^'\"\n\r]+)['\"]?",
        re.IGNORECASE,
    )

    @classmethod
    def capture(
        cls,
        command: Union[str, List[str]],
        cwd: Optional[str] = None,
        timeout_seconds: float = 30.0,
        env_overrides: Optional[Dict[str, str]] = None,
    ) -> SyscallTelemetry:
        """Executes a target binary/test suite in a controlled subprocess, capturing complete telemetry."""
        execution_working_dir = Path(cwd or os.getcwd()).resolve()
        shell_command_representation = command if isinstance(command, str) else " ".join(command)

        execution_environment = os.environ.copy()
        if env_overrides:
            execution_environment.update(env_overrides)

        clock_start_ns = time.perf_counter()
        try:
            isolated_proc = subprocess.run(
                command,
                cwd=str(execution_working_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=isinstance(command, str),
                timeout=timeout_seconds,
                env=execution_environment,
            )
            raw_stdout_stream = isolated_proc.stdout
            raw_stderr_stream = isolated_proc.stderr
            process_exit_code = isolated_proc.returncode
        except subprocess.TimeoutExpired as timeout_err:
            raw_stdout_stream = timeout_err.stdout or "" if isinstance(timeout_err.stdout, str) else ""
            raw_stderr_stream = f"TIMEOUT: Execution exceeded {timeout_seconds}s SLA"
            process_exit_code = -9
        except Exception as invocation_err:
            raw_stdout_stream = ""
            raw_stderr_stream = f"Process invocation failure: {str(invocation_err)}"
            process_exit_code = -1

        elapsed_duration_ms = round((time.perf_counter() - clock_start_ns) * 1000.0, 2)
        aggregated_stream = f"{raw_stdout_stream}\n{raw_stderr_stream}"

        # 1. Parse Syscall / Kernel Signatures
        trapped_os_signals = [
            code for code in cls.KNOWN_SYSCALL_SIGNATURES if code in aggregated_stream
        ]

        # 2. Extract Top-Level Runtime Exceptions
        captured_runtime_faults = [
            f"{match.group('exc')}: {match.group('msg')}"
            for match in cls.REGEX_RUNTIME_EXCEPTION.finditer(aggregated_stream)
        ]

        # 3. Parse Stack Frames
        parsed_stack_frames: List[StackFrameInfo] = []
        for frame_match in cls.REGEX_TRACEBACK_FRAME.finditer(aggregated_stream):
            parsed_stack_frames.append(
                StackFrameInfo(
                    file_path=frame_match.group("file"),
                    line_number=int(frame_match.group("line")),
                    function_name=frame_match.group("func"),
                    code_statement=(frame_match.group("stmt") or "").strip(),
                )
            )

        # 4. Pin Primary Failure Frame (Filter out stdlib and vendor site-packages)
        focal_root_cause_frame: Optional[StackFrameInfo] = None
        for candidate_frame in reversed(parsed_stack_frames):
            frame_path = Path(candidate_frame.file_path)
            if "site-packages" not in str(frame_path) and "Lib" not in str(frame_path) and frame_path.exists():
                focal_root_cause_frame = candidate_frame
                break
        if not focal_root_cause_frame and parsed_stack_frames:
            focal_root_cause_frame = parsed_stack_frames[-1]

        # 5. Extract Missing Dependency Paths
        unresolved_dependency_paths = list({
            path_match.group("path").strip()
            for path_match in cls.REGEX_UNRESOLVED_PATH.finditer(aggregated_stream)
        })

        return SyscallTelemetry(
            command=shell_command_representation,
            cwd=str(execution_working_dir),
            exit_code=process_exit_code,
            duration_ms=elapsed_duration_ms,
            stdout=raw_stdout_stream,
            stderr=raw_stderr_stream,
            detected_exceptions=captured_runtime_faults,
            detected_syscall_errors=trapped_os_signals,
            failing_frames=parsed_stack_frames,
            primary_failure_frame=focal_root_cause_frame,
            missing_paths_or_configs=unresolved_dependency_paths,
        )


# ==============================================================================
# Model Context Protocol (MCP) Server Tool Interface
# ==============================================================================

class AutoPatchMCPServer:
    """Production-grade Model Context Protocol (MCP) tool implementation server."""

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()
        self.ast_engine = ASTCallGraphEngine(str(self.workspace_root))
        self.telemetry_engine = SyscallTelemetryEngine()

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Returns MCP tool declarations for dynamic client capability discovery."""
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
            subgraph_result = self.ast_engine.extract_subgraph(
                file_path=arguments["file_path"],
                line_number=int(arguments["line_number"]),
                hop_depth=int(arguments.get("hop_depth", 2)),
            )
            return subgraph_result.model_dump()
        elif tool_name == "capture_syscall_telemetry":
            telemetry_result = self.telemetry_engine.capture(
                command=arguments["command"],
                cwd=arguments.get("cwd", str(self.workspace_root)),
            )
            return telemetry_result.model_dump()
        else:
            raise UnknownMCPToolException(f"Unsupported MCP tool identifier requested: '{tool_name}'")
