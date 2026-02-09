"""
Persona Spec Schema

Versioned, user-trained persona artifact definition and validation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import re

from pydantic import BaseModel, Field, field_validator, model_validator


SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class PersonaExample(BaseModel):
    id: Optional[str] = None
    intent_label: str = Field(min_length=1, max_length=100)
    prompt: str = Field(min_length=1, max_length=6000)
    response: str = Field(min_length=1, max_length=6000)
    tags: List[str] = Field(default_factory=list)


class ProceduralModule(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    intent_labels: List[str] = Field(default_factory=list)
    when: Dict[str, Any] = Field(default_factory=dict)
    do: List[str] = Field(default_factory=list)
    say_style: Dict[str, Any] = Field(default_factory=dict)
    ban: List[str] = Field(default_factory=list)
    few_shot_ids: List[str] = Field(default_factory=list)
    priority: int = 100
    active: bool = True

    @field_validator("id")
    @classmethod
    def _validate_module_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not re.match(r"^[a-zA-Z0-9._:-]+$", cleaned):
            raise ValueError("module id may only include letters, numbers, ., _, :, -")
        return cleaned


class PersonaSpec(BaseModel):
    version: str = Field(default="1.0.0")
    identity_voice: Dict[str, Any] = Field(default_factory=dict)
    decision_policy: Dict[str, Any] = Field(default_factory=dict)
    stance_values: Dict[str, Any] = Field(default_factory=dict)
    interaction_style: Dict[str, Any] = Field(default_factory=dict)
    constitution: List[str] = Field(default_factory=list)
    canonical_examples: List[PersonaExample] = Field(default_factory=list)
    anti_examples: List[PersonaExample] = Field(default_factory=list)
    procedural_modules: List[ProceduralModule] = Field(default_factory=list)
    deterministic_rules: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("version")
    @classmethod
    def _validate_semver(cls, value: str) -> str:
        cleaned = value.strip()
        if not SEMVER_RE.match(cleaned):
            raise ValueError("version must be semantic version (e.g., 1.0.0)")
        return cleaned

    @model_validator(mode="after")
    def _validate_examples(self):
        if len(self.canonical_examples) > 30:
            raise ValueError("canonical_examples must contain at most 30 items")
        if len(self.anti_examples) > 30:
            raise ValueError("anti_examples must contain at most 30 items")

        example_ids = {e.id for e in self.canonical_examples if e.id}
        for module in self.procedural_modules:
            unknown = [ex_id for ex_id in module.few_shot_ids if ex_id not in example_ids]
            if unknown:
                raise ValueError(
                    f"module {module.id} references unknown few_shot_ids: {', '.join(unknown)}"
                )
        return self


def parse_semver(version: str) -> tuple[int, int, int]:
    match = SEMVER_RE.match(version.strip())
    if not match:
        raise ValueError("invalid semver")
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def next_patch_version(current: Optional[str]) -> str:
    if not current:
        return "1.0.0"
    major, minor, patch = parse_semver(current)
    return f"{major}.{minor}.{patch + 1}"
