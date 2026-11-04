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
