# ruff: noqa: RUF001 -- Chinese UI text and explicit Chinese punctuation parsing.
"""Conservative configuration-only schedule preview; not a model or trigger owner."""

import re
from copy import deepcopy


def preview_instruction(instruction, current_trigger=None):
    if (
        not isinstance(instruction, str)
        or not instruction.strip()
        or len(instruction) > 4000
    ):
        raise ValueError("FIXED_WORK_INSTRUCTION_INVALID")
    text = instruction.strip()
    candidate = deepcopy(current_trigger)
    issues = []
    changed = {}
    # Do not turn quoted examples, negated instructions, hypothetical alternatives
    # or unsupported recurrence into an affirmative scheduling instruction.
    if (
        re.search(
            r'["“”「」『』]|不要|不再|不是|取消|暂停|例如|比如|假如|如果|或者|或是',
            text,
        )
        or "'" in text
        or "`" in text
    ):
        issues.append("说明包含否定、引用或条件，请展开字段明确本次安排。")
    if re.search(r"每周|每月|每年|每隔|分钟|小时|节假日", text):
        issues.append("当前配置只支持每天、工作日或明确事件；此处不自动转换其他周期。")
    if re.search(r"不晚于|不迟于|大约|左右|之前|以后|最晚|尽量", text):
        issues.append("说明含时间范围或近似要求，请明确触发时刻。")
    cadence = set()
    if re.search(r"每天|每日|每一天", text):
        cadence.add("DAILY")
    if re.search(r"工作日|每个工作日", text):
        cadence.add("WEEKDAY")
    times = []
    for match in re.finditer(
        r"(?<![\d.])(\d{1,2})\s*(?:[:：]\s*(\d{2})|点\s*(半|\d{1,2}分)?)", text
    ):
        hour = int(match[1])
        minute = (
            int(match[2])
            if match[2]
            else (30 if match[3] == "半" else int(match[3][:-1]) if match[3] else 0)
        )
        period = re.search(
            r"(上午|早上|下午|晚上|中午|凌晨)\s*$", text[: match.start()]
        )
        if period:
            label = period[1]
            if label in {"下午", "晚上"} and 1 <= hour <= 11:
                hour += 12
            elif (
                (label in {"上午", "早上", "凌晨"} and hour >= 12)
                or (
                    label in {"中午", "晚上", "下午"}
                    and hour in {0, 12}
                    and label != "中午"
                )
                or (label == "中午" and hour != 12)
            ):
                issues.append("时段与数字时间有歧义，请明确24小时制时间。")
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            issues.append("时间不在有效范围内，请明确小时和分钟。")
        else:
            times.append(f"{hour:02}:{minute:02}")
    if len(cadence) > 1 or len(set(times)) > 1:
        issues.append("说明中有多个时间或频率，未替你选择其中一项。")
    event = re.search(r"^当([^，。；\n]{1,500}?)时[，,]", text)
    if event and (cadence or times):
        issues.append("说明同时包含事件和定时条件，请明确本次使用哪一种。")
    if not issues:
        if event:
            candidate = {
                "kind": "EVENT",
                "timezone": None,
                "localTime": None,
                "cadence": None,
                "eventDescription": event[1],
            }
            changed = {"kind": "EXPLICIT_TEXT", "eventDescription": "EXPLICIT_TEXT"}
        elif cadence or times:
            if not candidate or candidate.get("kind") != "SCHEDULE":
                candidate = {
                    "kind": "SCHEDULE",
                    "timezone": None,
                    "localTime": None,
                    "cadence": None,
                    "eventDescription": None,
                }
            if cadence:
                candidate["cadence"] = next(iter(cadence))
                changed["cadence"] = "EXPLICIT_TEXT"
            if times:
                candidate["localTime"] = times[0]
                changed["localTime"] = "EXPLICIT_TEXT"
            if "北京时间" in text or "上海时间" in text:
                candidate["timezone"] = "Asia/Shanghai"
                changed["timezone"] = "EXPLICIT_TEXT"
        else:
            issues.append("没有识别到明确时间、频率或事件，请核对展开字段。")
    if candidate and candidate.get("kind") == "SCHEDULE":
        for field, label in (
            ("timezone", "时区"),
            ("localTime", "时间"),
            ("cadence", "频率"),
        ):
            if not candidate.get(field):
                issues.append(f"尚缺{label}，不会自动补入默认值。")
    return {
        "instruction": instruction,
        "previousTrigger": current_trigger,
        "candidateTrigger": candidate,
        "derivedFields": changed,
        "issues": issues,
        "validation": "CONFIGURATION_STRUCTURE_ONLY",
        "modelInvoked": False,
        "executionEnabled": False,
        "authorityGranted": False,
    }
