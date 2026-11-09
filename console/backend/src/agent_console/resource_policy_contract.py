"""D11 internal policy evidence. Browser payloads cannot construct this port."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class PolicyReview:
    policy_id: str
    policy_version: str
    policy_digest: str
    decision_id: str
    issuer: str
    subject: str
    work_digest: str

    def record(self, actor):
        if (
            actor != self.issuer
            or not actor.startswith("service:")
            or self.issuer == self.subject
            or not self.decision_id
            or len(self.policy_digest) != 64
            or len(self.work_digest) != 64
        ):
            raise ValueError("RESOURCE_POLICY_PROOF_INVALID")
        return {"type": "POLICY", **asdict(self)}


def reviewed_state(review):
    return "POLICY_REVIEWED" if review.get("policyBasis") else "HUMAN_REVIEWED"


@dataclass(frozen=True, slots=True)
class DevelopmentAdministratorReview:
    """Constructed only by the role-checked internal publication entry (D12)."""

    issuer: str
    generation: int
    command_digest: str

    @property
    def policy_id(self):
        return "D12-development-administrator"

    @property
    def policy_version(self):
        return str(self.generation)

    @property
    def policy_digest(self):
        from .resource_use_domain import canonical_digest

        return canonical_digest([self.policy_id, self.generation, self.issuer])

    @property
    def decision_id(self):
        return "development-role-decision:" + self.command_digest

    @property
    def subject(self):
        return self.issuer

    def record(self, actor):
        if (
            actor != "human:development-admin"
            or actor != self.issuer
            or self.generation < 1
            or len(self.command_digest) != 64
        ):
            raise ValueError("RESOURCE_ADMINISTRATOR_PROOF_INVALID")
        return {
            "type": "DEVELOPMENT_ADMINISTRATOR",
            "issuer": actor,
            "subject": actor,
            "authorityGeneration": self.generation,
            "commandDigest": self.command_digest,
        }
