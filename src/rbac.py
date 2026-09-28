"""
Role-Based Access Control (RBAC) model for the Secure Enterprise RAG system.

Design
------
Every document is tagged with:
    - department            e.g. "Finance", "HR", "Engineering"
    - confidentiality_level int, 0 (Public) -> 3 (Restricted)

Every user is assigned a role. Each role defines:
    - allowed_departments   which departments the role may query at all
                             ("*" means all departments)
    - max_confidentiality   the highest confidentiality level the role may see

Access is granted only if BOTH conditions hold:
    1. doc.department in role.allowed_departments (or role allows "*")
    2. doc.confidentiality_level <= role.max_confidentiality

This mirrors real enterprise access models (e.g. attribute-based access
control layered on top of RBAC) and is intentionally simple to reason about
and unit-test.
"""

from dataclasses import dataclass
from typing import List, Set

CONFIDENTIALITY_LEVELS = {
    "Public": 0,
    "Internal": 1,
    "Confidential": 2,
    "Restricted": 3,
}
LEVEL_NAMES = {v: k for k, v in CONFIDENTIALITY_LEVELS.items()}

DEPARTMENTS = [
    "General",
    "HR",
    "Finance",
    "Engineering",
    "Legal",
    "Sales",
    "Executive",
]


@dataclass(frozen=True)
class Role:
    name: str
    allowed_departments: Set[str]  # {"*"} means all departments
    max_confidentiality: int

    def can_access_department(self, department: str) -> bool:
        return "*" in self.allowed_departments or department in self.allowed_departments

    def can_access_level(self, level: int) -> bool:
        return level <= self.max_confidentiality

    def can_access(self, department: str, confidentiality_level: int) -> bool:
        return self.can_access_department(department) and self.can_access_level(
            confidentiality_level
        )


# ---------------------------------------------------------------------------
# Role catalogue. Adjust freely to match your organisation's real structure.
# ---------------------------------------------------------------------------
ROLES = {
    "intern": Role(
        name="intern",
        allowed_departments={"General"},
        max_confidentiality=CONFIDENTIALITY_LEVELS["Public"],
    ),
    "employee": Role(
        name="employee",
        allowed_departments={"General", "Engineering", "Sales"},
        max_confidentiality=CONFIDENTIALITY_LEVELS["Internal"],
    ),
    "engineering_manager": Role(
        name="engineering_manager",
        allowed_departments={"General", "Engineering"},
        max_confidentiality=CONFIDENTIALITY_LEVELS["Confidential"],
    ),
    "hr_manager": Role(
        name="hr_manager",
        allowed_departments={"General", "HR"},
        max_confidentiality=CONFIDENTIALITY_LEVELS["Confidential"],
    ),
    "finance_manager": Role(
        name="finance_manager",
        allowed_departments={"General", "Finance"},
        max_confidentiality=CONFIDENTIALITY_LEVELS["Confidential"],
    ),
    "legal_counsel": Role(
        name="legal_counsel",
        allowed_departments={"General", "Legal", "HR", "Finance"},
        max_confidentiality=CONFIDENTIALITY_LEVELS["Restricted"],
    ),
    "executive": Role(
        name="executive",
        allowed_departments={"*"},
        max_confidentiality=CONFIDENTIALITY_LEVELS["Restricted"],
    ),
    "admin": Role(
        name="admin",
        allowed_departments={"*"},
        max_confidentiality=CONFIDENTIALITY_LEVELS["Restricted"],
    ),
}


def get_role(role_name: str) -> Role:
    if role_name not in ROLES:
        raise ValueError(f"Unknown role '{role_name}'. Known roles: {list(ROLES)}")
    return ROLES[role_name]


def allowed_departments_for(role: Role) -> List[str]:
    """Expand '*' into the concrete department list for use in DB filters."""
    if "*" in role.allowed_departments:
        return DEPARTMENTS
    return list(role.allowed_departments)
