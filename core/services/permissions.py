"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de comprobación de los permisos de cada rol.
"""

from __future__ import annotations

from enum import Enum, auto

from core.models.user_role import UserRole
from core.persistence.user_repository import User, UserRepository


class PermissionDenied(Exception):
    # El rol de la cuenta no autoriza la acción solicitada.

    pass


class Action(Enum):
    # Acciones protegidas del alcance implementado.

    PRACTICE = auto()
    CALIBRATE = auto()
    # Validar o rechazar una calibración, restringido a la cartera.
    REVIEW_CALIBRATION = auto()
    LIST_PENDING_CALIBRATIONS = auto()
    # Consultar sesiones y progreso, propios o de la cartera.
    VIEW_PROGRESS = auto()


# Roles que pueden ejercer cada acción.
_ALLOWED_ROLES: dict[Action, frozenset[UserRole]] = {
    Action.PRACTICE: frozenset({UserRole.ATHLETE}),
    Action.CALIBRATE: frozenset({UserRole.ATHLETE}),
    Action.REVIEW_CALIBRATION: frozenset({UserRole.TRAINER}),
    Action.LIST_PENDING_CALIBRATIONS: frozenset({UserRole.TRAINER}),
    Action.VIEW_PROGRESS: frozenset({UserRole.ATHLETE, UserRole.TRAINER}),
}

# Acciones qu se ejercen sobre un atleta concreto, y exigen comprobar la relación de supervisión.
_SCOPED_ACTIONS = frozenset(
    {Action.REVIEW_CALIBRATION, Action.VIEW_PROGRESS}
)


class PermissionChecker:
    # Única autoridad sobre quién puede hacer qué.

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    def may(
        self, actor: User, action: Action, *, subject_id: int | None = None
    ) -> bool:
        # Indica si una cuenta puede ejercer una acción.

        if actor.role not in _ALLOWED_ROLES[action]:
            return False
        if action not in _SCOPED_ACTIONS:
            return True
        if subject_id is None:
            # Una acción sobre un atleta sin decir sobre cuál no se concede.
            return False
        return self._supervises_or_is(actor, subject_id)

    def require(
        self, actor: User, action: Action, *, subject_id: int | None = None
    ) -> None:
        # Deja pasar o lanza PermissionDenied.

        if self.may(actor, action, subject_id=subject_id):
            return
        raise PermissionDenied(
            f"El rol {actor.role.value} no puede ejercer {action.name}"
            + (f" sobre la cuenta {subject_id}." if subject_id is not None else ".")
        )


    def _supervises_or_is(self, actor: User, subject_id: int) -> bool:
        # Un atleta solo accede a lo propio; un entrenador, a su cartera.

        if actor.role is UserRole.ATHLETE:
            return actor.user_id == subject_id

        subject = self._users.get(subject_id)
        if subject is None:
            return False
        return subject.assigned_trainer_id == actor.user_id