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
            path
            in {
                "/work",
                "/workbench",
                "/authorization-admin",
                "/digital-employees",
                "/skills",
                "/knowledge",
                "/agents",
                "/runtime-profiles",
                "/tasks",
                "/outcomes",
                "/attention",
            }
            or path.startswith("/work/")
        )
    ):
        return "/work"
    return value


def login_document(
    nonce,
    destination,
    *,
    error=False,
    accounts=False,
    request_id=None,
    reason=None,
    username="",
):
    from pathlib import Path

    template = Path(__file__).with_suffix(".html").read_text()
    errors = {
        "ACCOUNT_AUTHENTICATION_FAILED": "账号或密码不匹配，请核对后重试。",
        "LOGIN_NONCE_INVALID": (
            "登录表单已过期，已更新表单。请重新输入密码或凭据后登录。"
        ),
        "ACCOUNT_LOGIN_THROTTLED": "登录尝试过于频繁，请稍后再试。",
        "AUTHORITY_STORAGE_UNAVAILABLE": "登录服务暂不可用，请稍后再试。",
        "AUTHORITY_RECOVERY_REQUIRED": "登录服务正在恢复，请稍后再试。",
    }
    message = errors.get(reason, "本次登录未完成，暂时无法确认原因。请稍后重试。")
    template = template.replace(
        "{{error}}", '<p role="alert">登录未完成：' + message + "</p>" if error else ""
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
                'placeholder="输入测试账号" value="'
                + html.escape(username[:64], quote=True)
                + '">'
                '<label for="password">密码</label><input '
                'id="password" type="password" name="password" '
                'autocomplete="current-password" maxlength="256" '
                'required placeholder="输入本机领取的密码">'
                '<label class="show-password"><input '
                'id="show-password" type="checkbox">显示密码</label>'
            )
            + template[end:]
        )
        template = template.replace(
            "当前入口：可信问题工作台", "当前入口：本地隔离测试环境"
        )
        template = template.replace("使用现有可信身份机制", "使用独立测试账号登录")
        template = template.replace(
            "请使用管理员通过正式渠道提供的有效凭据。凭据过期时联系管理员恢复身份。",
            "请从本机安全领取文件获取账号密码。账号与登录会话分别管理；可见资源与操作范围以当前账号权限为准。忘记密码或账号停用请联系管理员。",
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
        ).replace("登录并继续", "登录并返回原审批对象")
    return template.replace("{{nonce}}", html.escape(nonce, quote=True)).replace(
        "{{return}}", html.escape(safe_return(destination), quote=True)
    )
