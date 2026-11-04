"""Typed owner port, shared by service and PostgreSQL adapter."""

from typing import Protocol

from .ontology_domain import OntologyCommand


class OntologyRepository(Protocol):
    def read(self, scope: tuple[str, str], identity: str, revision: str) -> dict: ...
    def command(
        self,
        scope: tuple[str, str],
        actor: str,
        identity: str,
        action: str,
        command: OntologyCommand,
    ) -> dict: ...
