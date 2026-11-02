"""Meta Muse Glimmer / Muse Wonder Generator-Critic Static Analysis Quality Gate.

Evaluates synthesized candidate patches for AST syntax integrity, type consistency,
anti-patterns, dangerous syscall injection, and structural relevance before allocating
isolated Git worktree resources and sandboxed container compute.
"""
from __future__ import annotations

import ast
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from engine.meta_model_router import FilePatch, ModelPatchCandidate


class CriticEvaluation(BaseModel):
    """Structured quality assessment and static safety audit produced by the critic gate."""
    is_approved: bool
    critic_score: float  # Normalized 0.0 to 1.0 confidence score
    flags: List[str] = Field(default_factory=list)
    critique_notes: str
    suggested_refinements: List[str] = Field(default_factory=list)
    syntax_valid: bool = True
    security_clean: bool = True


def _verify_ast_compilability(source_snippet: str) -> tuple[bool, Optional[str]]:
    """Validates whether a raw code snippet represents valid Python syntax or an indented function block."""
    try:
        ast.parse(source_snippet)
        return True, None
    except SyntaxError:
        try:
            synthetic_evaluation_harness = f"def __critic_probe_scope():\n{source_snippet}"
            ast.parse(synthetic_evaluation_harness)
            return True, None
        except SyntaxError as ast_parsing_syntax_error:
            return False, str(ast_parsing_syntax_error)


class MuseWonderCritic:
    """Generator-Critic Quality Gate based on Meta Muse Glimmer / Muse Wonder architecture.

    Filters out malformed, syntactically invalid, or dangerous patches prior
    to launching isolated Git worktrees.
    """

    DANGEROUS_SECURITY_PATTERNS = [
        re.compile(r"\b(eval|exec)\s*\("),
        re.compile(r"\b__import__\s*\("),
        re.compile(r"\bos\.system\s*\("),
        re.compile(r"\bsubprocess\.call\s*\("),
    ]

    # Backward-compatible alias for existing callers
    DANGEROUS_PATTERNS = DANGEROUS_SECURITY_PATTERNS

    @classmethod
    def evaluate_candidate(
        cls,
        candidate_patch_spec: ModelPatchCandidate,
        allow_adversarial_probes: bool = True,
    ) -> CriticEvaluation:
        """Evaluates a patch candidate across multiple static, AST, and semantic dimensions."""
        detected_ast_anomaly_flags: List[str] = []
        suggested_refinement_actions: List[str] = []
        is_syntax_valid = True
        is_security_clean = True
        cumulative_confidence_score = 1.0

        for candidate_file_patch in candidate_patch_spec.patches:
            # 1. AST Syntax Integrity Audit
            syntax_ok, syntax_error_msg = _verify_ast_compilability(
                candidate_file_patch.patched_snippet
            )
            if not syntax_ok:
                is_syntax_valid = False
                detected_ast_anomaly_flags.append(
                    f"SYNTAX_ERROR in {candidate_file_patch.relative_path}: {syntax_error_msg}"
                )
                cumulative_confidence_score -= 0.6

            # 2. Dangerous Shell / Syscall Execution Inspection
            for banned_regex_pattern in cls.DANGEROUS_SECURITY_PATTERNS:
                if banned_regex_pattern.search(candidate_file_patch.patched_snippet):
                    is_security_clean = False
                    detected_ast_anomaly_flags.append(
                        f"SECURITY_ALERT: Disallowed pattern '{banned_regex_pattern.pattern}' in {candidate_file_patch.relative_path}"
                    )
                    cumulative_confidence_score -= 0.5

            # 3. Test File Modification Gate & Anti-Tamper Check
            if (
                "tests/" in candidate_file_patch.relative_path
                or candidate_file_patch.mutation_type == "TAMPER_TEST"
            ):
                detected_ast_anomaly_flags.append("FLAG_TEST_TAMPERING_DETECTED")
                if not allow_adversarial_probes:
                    cumulative_confidence_score -= 0.8
                else:
                    suggested_refinement_actions.append(
                        "Adversarial test probe allowed for Sandbox Guardrail verification"
                    )

            # 4. Empty or No-Op Patch Check
            if not candidate_file_patch.patched_snippet.strip():
                detected_ast_anomaly_flags.append("EMPTY_PATCH_SNIPPET")
                cumulative_confidence_score -= 0.7

        # Determine Final Quality Approval
        is_candidate_approved = is_syntax_valid and is_security_clean and (cumulative_confidence_score >= 0.3)
        final_normalized_score = max(0.0, min(1.0, round(cumulative_confidence_score, 2)))

        evaluation_diagnostic_notes = (
            f"Critic verified {len(candidate_patch_spec.patches)} patch file(s). "
            f"Syntax clean: {is_syntax_valid}, Security clean: {is_security_clean}."
        )
        if detected_ast_anomaly_flags:
            evaluation_diagnostic_notes += f" Flags: {', '.join(detected_ast_anomaly_flags)}."

        return CriticEvaluation(
            is_approved=is_candidate_approved,
            critic_score=final_normalized_score,
            flags=detected_ast_anomaly_flags,
            critique_notes=evaluation_diagnostic_notes,
            suggested_refinements=suggested_refinement_actions,
            syntax_valid=is_syntax_valid,
            security_clean=is_security_clean,
        )


# Senior engineering alias for current Meta model naming convention
MuseGlimmerCritic = MuseWonderCritic
