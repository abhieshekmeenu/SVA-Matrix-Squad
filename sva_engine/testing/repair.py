from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RepairAction:
    """One proposed repair action."""

    action: str
    path: str | None = None
    content: str | None = None
    old_text: str | None = None
    new_text: str | None = None


@dataclass
class RepairProposal:
    """Structured repair proposal produced by an analyzer/AI."""

    failure_category: str
    diagnosis: str
    fix_type: str
    confidence: float
    actions: list[RepairAction] = field(default_factory=list)
    requires_approval: bool = True

    def validate(self) -> dict[str, object]:
        errors: list[str] = []

        if not self.failure_category:
            errors.append("failure_category is required")

        if not self.diagnosis:
            errors.append("diagnosis is required")

        if not self.fix_type:
            errors.append("fix_type is required")

        if not 0 <= self.confidence <= 1:
            errors.append("confidence must be between 0 and 1")

        for index, action in enumerate(self.actions):
            if action.action not in {
                "write_file",
                "patch_file",
            }:
                errors.append(
                    f"actions[{index}]: unsupported action '{action.action}'"
                )

            if not action.path:
                errors.append(
                    f"actions[{index}]: path is required"
                )

        return {
            "valid": not errors,
            "errors": errors,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "failure_category": self.failure_category,
            "diagnosis": self.diagnosis,
            "fix_type": self.fix_type,
            "confidence": self.confidence,
            "requires_approval": self.requires_approval,
            "actions": [
                {
                    "action": action.action,
                    "path": action.path,
                    "content": action.content,
                    "old_text": action.old_text,
                    "new_text": action.new_text,
                }
                for action in self.actions
            ],
        }


def proposal_from_dict(data: dict[str, object]) -> RepairProposal:
    """Validate and construct a repair proposal from structured data."""

    if not isinstance(data, dict):
        raise ValueError("Repair proposal must be a dictionary")

    raw_actions = data.get("actions", [])

    if not isinstance(raw_actions, list):
        raise ValueError("actions must be a list")

    actions: list[RepairAction] = []

    for raw in raw_actions:
        if not isinstance(raw, dict):
            raise ValueError("Each repair action must be a dictionary")

        actions.append(
            RepairAction(
                action=str(raw.get("action") or ""),
                path=(
                    str(raw["path"])
                    if raw.get("path") is not None
                    else None
                ),
                content=(
                    str(raw["content"])
                    if raw.get("content") is not None
                    else None
                ),
                old_text=(
                    str(raw["old_text"])
                    if raw.get("old_text") is not None
                    else None
                ),
                new_text=(
                    str(raw["new_text"])
                    if raw.get("new_text") is not None
                    else None
                ),
            )
        )

    proposal = RepairProposal(
        failure_category=str(data.get("failure_category") or ""),
        diagnosis=str(data.get("diagnosis") or ""),
        fix_type=str(data.get("fix_type") or ""),
        confidence=float(data.get("confidence", 0)),
        actions=actions,
        requires_approval=bool(data.get("requires_approval", True)),
    )

    validation = proposal.validate()

    if not validation["valid"]:
        raise ValueError(
            "Invalid repair proposal: "
            + "; ".join(validation["errors"])
        )

    return proposal
