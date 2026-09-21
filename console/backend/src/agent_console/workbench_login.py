"""Presentation over the existing nonce/bootstrap boundary; no identity store."""

import html
from urllib.parse import unquote, urlsplit


def safe_return(value):
    try:
        parsed = urlsplit(value)
    except ValueError:
        return "/work"
    path = unquote(parsed.path)
    if (
        parsed.scheme
        or parsed.netloc
        or "\\" in value
        or any(ord(c) < 32 for c in value + path)
        or "\\" in path
        or any(part in {".", ".."} for part in path.split("/"))
        or path.startswith("//")
        or not (
            path in {"/work", "/workbench", "/authorization-admin"}
            or path.startswith("/work/")
        )
    ):
        return "/work"
    return value


def login_document(nonce, destination, *, error=False):
    from pathlib import Path

    template = Path(__file__).with_suffix(".html").read_text()
    template = template.replace(
        "{{error}}",
        '<p role="alert">登录未完成。请检查凭据是否有效。或联系管理员恢复身份。</p>'
        if error
        else "",
    )
    return template.replace("{{nonce}}", html.escape(nonce, quote=True)).replace(
        "{{return}}", html.escape(safe_return(destination), quote=True)
    )
