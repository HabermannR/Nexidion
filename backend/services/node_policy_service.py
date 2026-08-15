"""Central, inherited access-policy decisions for nodes.

Vault roles decide who may access a vault. These policies only add restrictions.
"""
from dataclasses import dataclass

from backend.models import db, Node, User, UserType


AI_READ_LEVEL = {"allow": 0, "explicit_only": 1, "deny": 2}
AI_READ_VALUES = frozenset(AI_READ_LEVEL)


@dataclass(frozen=True)
class EffectiveNodePolicy:
    ai_read: str = "allow"
    ai_write_locked: bool = False
    human_write_locked: bool = False
    inherited: bool = False

    def to_dict(self) -> dict:
        return {
            "ai_read": self.ai_read,
            "ai_write_locked": self.ai_write_locked,
            "human_write_locked": self.human_write_locked,
            "inherited": self.inherited,
        }


def is_ai_actor(user_id: int, actor_type: str | None = None) -> bool:
    if actor_type in {"mcp", "ai", "agent"}:
        return True
    user = db.session.get(User, user_id)
    return bool(user and user.user_type == UserType.LLM_ASSISTANT)


def effective_policy(node: Node) -> EffectiveNodePolicy:
    current = node
    read = "allow"
    ai_locked = False
    human_locked = False
    inherited = False
    first = True
    seen: set[str] = set()
    while current is not None and current.id not in seen:
        seen.add(current.id)
        local_read = current.ai_read_policy or "allow"
        if AI_READ_LEVEL.get(local_read, 0) > AI_READ_LEVEL[read]:
            read = local_read
            inherited = inherited or not first
        if current.human_write_locked:
            human_locked = True
            ai_locked = True
            inherited = inherited or not first
        elif current.ai_write_locked:
            ai_locked = True
            inherited = inherited or not first
        current = current.parent
        first = False
    return EffectiveNodePolicy(read, ai_locked, human_locked, inherited)


def assert_readable(node: Node, user_id: int, *, actor_type: str | None = None,
                    include_quarantined: bool = False) -> None:
    if not is_ai_actor(user_id, actor_type):
        return
    policy = effective_policy(node)
    if policy.ai_read == "deny":
        raise PermissionError("This node is unavailable to AI-mediated access.")
    if policy.ai_read == "explicit_only" and not include_quarantined:
        raise PermissionError(
            "This node is quarantined. Explicit include_quarantined=true is required."
        )


def assert_writable(node: Node, user_id: int, *, actor_type: str | None = None) -> None:
    policy = effective_policy(node)
    if policy.human_write_locked:
        raise PermissionError("This node or an ancestor is write-locked.")
    if is_ai_actor(user_id, actor_type) and policy.ai_write_locked:
        raise PermissionError("This node or an ancestor is AI write-locked.")


def set_local_policy(node: Node, *, ai_read: str, ai_write_locked: bool,
                     human_write_locked: bool, note: str | None) -> None:
    if ai_read not in AI_READ_VALUES:
        raise ValueError("ai_read must be allow, explicit_only, or deny.")
    node.ai_read_policy = ai_read
    node.human_write_locked = bool(human_write_locked)
    # A human write-lock always implies an AI write-lock.
    node.ai_write_locked = bool(ai_write_locked or human_write_locked or ai_read != "allow")
    node.policy_note = note.strip() if isinstance(note, str) and note.strip() else None


def stamp_quarantine_subtree(node: Node) -> None:
    """Persist quarantine downward without weakening AI-invisible descendants.

    This is deliberately one-way: removing quarantine from an ancestor never
    clears descendants that were stamped earlier.
    """
    stack = [node]
    seen: set[str] = set()
    while stack:
        current = stack.pop()
        if current.id in seen:
            continue
        seen.add(current.id)
        if (current.ai_read_policy or "allow") != "deny":
            current.ai_read_policy = "explicit_only"
        current.ai_write_locked = True
        stack.extend(current.children)
