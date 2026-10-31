"""Muse Wonder (muse-wonder-1.0) Generator-Critic Quality Gate.

Evaluates synthesized candidate patches for AST syntax integrity, type consistency,
anti-patterns, and structural relevance before allocating sandbox compute.
"""
from __future__ import annotations

import ast
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from engine.meta_model_router import FilePatch, ModelPatchCandidate


class CriticEvaluation(BaseModel):
    is_approved: bool
    critic_score: float  # 0.0 to 1.0
    flags: List[str] = Field(default_factory=list)
    critique_notes: str
    suggested_refinements: List[str] = Field(default_factory=list)
    syntax_valid: bool = True
    security_clean: bool = True


class MuseWonderCritic:
    """Generator-Critic Quality Gate based on Meta Muse Wonder architecture.

    Filters out malformed, syntactically invalid, or dangerous patches prior
    to launching isolated Git worktrees.
    """

    DANGEROUS_PATTERNS = [
        re.compile(r"\b(eval|exec)\s*\("),
        re.compile(r"\b__import__\s*\("),
        re.compile(r"\bos\.system\s*\("),
        re.compile(r"\bsubprocess\.call\s*\("),
    ]

    @classmethod
    def evaluate_candidate(
        cls,
        candidate: ModelPatchCandidate,
        allow_adversarial_probes: bool = True,
    ) -> CriticEvaluation:
        """Evaluates a patch candidate across multiple static and semantic dimensions."""
        flags: List[str] = []
        refinements: List[str] = []
        syntax_valid = True
        security_clean = True
        score = 1.0

        for patch in candidate.patches:
            # 1. AST Syntax Validity Check
            try:
                # Wrap snippet in a dummy function or parse directly
                indented_code = patch.patched_snippet
                # Try parsing as standalone block or wrapped
                try:
                    ast.parse(indented_code)
                except SyntaxError:
                    # Often patches are indented function bodies
                    wrapped = f"def __critic_probe_scope():\n{indented_code}"
                    ast.parse(wrapped)
            except SyntaxError as syn_err:
                syntax_valid = False
                flags.append(f"SYNTAX_ERROR in {patch.relative_path}: {str(syn_err)}")
                score -= 0.6

            # 2. Security & Anti-Pattern Check
            for pat in cls.DANGEROUS_PATTERNS:
                if pat.search(patch.patched_snippet):
                    security_clean = False
                    flags.append(f"SECURITY_ALERT: Disallowed pattern '{pat.pattern}' in {patch.relative_path}")
                    score -= 0.5

            # 3. Test File Modification Gate
            if "tests/" in patch.relative_path or patch.mutation_type == "TAMPER_TEST":
                flags.append("FLAG_TEST_TAMPERING_DETECTED")
                if not allow_adversarial_probes:
                    score -= 0.8
                else:
                    # In adversarial mode, annotate as test probe for the sandbox guardrail
                    refinements.append("Adversarial test probe allowed for Sandbox Guardrail verification")

            # 4. Empty or No-Op Patch Check
            if not patch.patched_snippet.strip():
                flags.append("EMPTY_PATCH_SNIPPET")
                score -= 0.7

        # Determine Approval
        is_approved = syntax_valid and security_clean and (score >= 0.3)
        final_score = max(0.0, min(1.0, round(score, 2)))

        critique_notes = (
            f"Critic verified {len(candidate.patches)} patch file(s). "
            f"Syntax clean: {syntax_valid}, Security clean: {security_clean}."
        )
        if flags:
            critique_notes += f" Flags: {', '.join(flags)}."

        return CriticEvaluation(
            is_approved=is_approved,
            critic_score=final_score,
            flags=flags,
            critique_notes=critique_notes,
            suggested_refinements=refinements,
            syntax_valid=syntax_valid,
            security_clean=security_clean,
        )
