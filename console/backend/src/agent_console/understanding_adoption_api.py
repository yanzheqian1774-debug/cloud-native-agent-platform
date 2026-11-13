"""Explicit adoption and readback, unavailable without the successor owner."""

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import AuthorityError
from .draft_assistance import DraftAssistanceError
from .private_conversation import ConversationError
from .workbench_bff import PREFIX


class AdoptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requestKey: str = Field(min_length=1, max_length=128)


def install(app, authenticate, csrf):
    path = (
        f"{PREFIX}/conversations/{{conversation}}/understanding-results/"
        "{message}/adoption"
    )

    def invoke(request, conversation, message, key, *, write):
        session, context = authenticate(request)
        if write:
            csrf(request, session)
        owner = getattr(app.state, "understanding_adoption", None)
        if owner is None:
            return JSONResponse(
                status_code=404,
                content={"reasonCode": "UNDERSTANDING_ADOPTION_UNAVAILABLE"},
            )
        try:
            action = owner.apply if write else owner.read
            return {"result": action(context, conversation, message, key)}
        except ConversationError as exc:
            return JSONResponse(
                status_code=exc.status, content={"reasonCode": exc.reason}
            )
        except DraftAssistanceError as exc:
            code = 404 if exc.reason_code.endswith("NOT_FOUND") else 409
            return JSONResponse(
                status_code=code, content={"reasonCode": exc.reason_code}
            )
        except AuthorityError:
            return JSONResponse(
                status_code=403,
                content={"reasonCode": "UNDERSTANDING_ADOPTION_ACCESS_DENIED"},
            )

    @app.get(path)
    def read(request: Request, conversation: str, message: str, requestKey: str):
        return invoke(request, conversation, message, requestKey, write=False)

    @app.post(path)
    def apply(request: Request, conversation: str, message: str, body: AdoptionRequest):
        return invoke(request, conversation, message, body.requestKey, write=True)
