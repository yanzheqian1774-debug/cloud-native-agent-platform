# ruff: noqa: RUF001
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


def login_document(nonce, destination, *, error=False, accounts=False, request_id=None):
    from pathlib import Path

    template = Path(__file__).with_suffix(".html").read_text()
    template = template.replace(
        "{{error}}",
        '<p role="alert">登录未完成。请检查凭据是否有效。或联系管理员恢复身份。</p>'
        if error
        else "",
    )
    if accounts:
        start = template.index('<label for="credential">')
        end = template.index('<button type="submit">', start)
        template = (
            template[:start]
            + (
                '<label for="username">账号</label><input '
                'id="username" name="username" '
                'autocomplete="username" maxlength="64" required '
                'placeholder="输入测试账号">'
                '<label for="password">密码</label><input '
                'id="password" type="password" name="password" '
                'autocomplete="current-password" maxlength="256" '
                'required placeholder="输入本机领取的密码">'
                '<label class="show-password"><input '
                'id="show-password" type="checkbox">显示密码</label>'
                '<script src="/api/workbench/v1/login-script" defer></script>'
            )
            + template[end:]
        )
        template = template.replace(
            "当前入口：可信问题工作台", "当前入口：本地隔离测试环境"
        )
        template = template.replace("使用现有可信身份机制", "使用独立测试账号登录")
        template = template.replace(
            "请使用管理员通过正式渠道提供的有效凭据。凭据过期时联系管理员恢复身份。",
            "请从本机安全领取文件获取账号密码。账号与登录会话分别管理；权限仍须独立审批。忘记密码或账号停用请联系管理员。",
        )
        template = template.replace(
            "登录未完成。请检查凭据是否有效。或联系管理员恢复身份。",
            "登录未完成，请核对账号密码后重试；表单停留过久请刷新。多次失败请稍后再试或联系管理员。",
        )
        template = template.replace("使用正式有效凭据", "使用本机测试账号")
    if error and request_id:
        template = template.replace(
            '</p><p class="entry-note">',
            "<br>诊断编号：" + html.escape(request_id) + '</p><p class="entry-note">',
            1,
        )
    if urlsplit(safe_return(destination)).path == "/authorization-admin":
        template = template.replace(
            "当前入口：本地隔离测试环境" if accounts else "当前入口：可信问题工作台",
            "当前入口：独立授权审批 · 保留原对象链接",
        ).replace("登录并返回工作台", "登录并返回原审批对象")
    return template.replace("{{nonce}}", html.escape(nonce, quote=True)).replace(
        "{{return}}", html.escape(safe_return(destination), quote=True)
    )
