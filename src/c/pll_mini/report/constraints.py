from __future__ import annotations

import json
import time
from dataclasses import asdict

from load.tools import run_consolver_solve


def diagnose_constraints(
    builder, result: dict, *, timeout_ms: int | None = None
) -> dict:
    """缩减已经证实无解的断言集合，保留预算与不确定结果。

    Args:
        builder: 原始图的符号及断言。
        result: 正式求解返回的状态。
        timeout_ms: 正式求解预算，诊断不会扩大单次调用预算。

    Returns:
        含消息、冲突集合、缩减状态和失败记录的诊断数据。
    """
    status = result["status"]
    reason = result.get("reason") or "solver did not provide a reason"
    report = {
        "status": status,
        "reason": reason,
        "checks": 0,
        "minimal": False,
        "reduction_complete": False,
        "diagnostic_errors": [],
    }
    if status != "unsat":
        report["message"] = (
            f"[solve/{status}] 未能判定约束是否可满足；reason={reason}；timeout_ms={timeout_ms or 'unlimited'}"
        )
        return report

    core = list(builder.constraints)
    deadline = time.monotonic() + 8.0
    max_checks = 24
    # Every retained set is UNSAT: discard assertions only after an UNSAT check.
    granularity = 2
    while (
        len(core) > 1 and report["checks"] < max_checks and time.monotonic() < deadline
    ):
        chunk_size = (len(core) + granularity - 1) // granularity
        removed = False
        for start in range(0, len(core), chunk_size):
            remaining_ms = int((deadline - time.monotonic()) * 1000)
            if remaining_ms <= 0 or report["checks"] >= max_checks:
                break
            candidate = core[:start] + core[start + chunk_size :]
            report["checks"] += 1
            try:
                check = json.loads(
                    run_consolver_solve(
                        builder.render(candidate),
                        timeout_ms=min(timeout_ms or 1000, 1000, remaining_ms),
                    )
                )
                if not isinstance(check, dict):
                    raise ValueError(f"invalid diagnostic solver output: {check!r}")
                if check.get("status") == "unsat":
                    core = candidate
                    granularity = max(2, granularity - 1)
                    removed = True
                    break
                if check.get("status") != "sat":
                    report["diagnostic_errors"].append(
                        f"check {report['checks']}: {check}"
                    )
            except (ValueError, RuntimeError, OSError) as exc:
                report["diagnostic_errors"].append(str(exc))
                break
        if removed:
            continue
        if chunk_size == 1:
            report["reduction_complete"] = (
                report["checks"] < max_checks and time.monotonic() < deadline
            )
            report["minimal"] = (
                report["reduction_complete"] and not report["diagnostic_errors"]
            )
            break
        granularity = min(len(core), granularity * 2)

    report["conflicts"] = [asdict(item) for item in core]
    names = {item.node for item in core}
    report["involved_nodes"] = sorted(names)
    from collections import Counter

    counts = Counter(item["symbol"] for item in builder.controls)
    report["shared_fields"] = [
        item
        for item in builder.controls
        if item["node"] in names and counts[item["symbol"]] > 1
    ]
    lines = [
        f"[solve/unsat] 频率约束无解；冲突集合 {len(core)}/{len(builder.constraints)} 条；minimal={report['minimal']}"
    ]
    if not report["reduction_complete"]:
        lines.append("诊断缩减达到预算或未完成；下面集合仍已证实无解，不保证最小。")
    for name in sorted(names):
        node = builder.tree.nodes[name]
        rules = [item for item in core if item.node == name]
        paths = sorted({path for item in rules for path in item.paths})
        lines.append(
            f"nodes[{name!r}] kind={node.kind}, inputs={node.input_refs()}, freq={node.freq}, constraints={len(rules)}; fields={', '.join(paths)}"
        )
    if len(core) <= 24:
        for item in core:
            lines.append(f"- {item.name} {item.rule}: {item.expr}")
    else:
        lines.append("完整断言、原始表达式和节点配置保存在诊断 JSON 中。")
    for item in report["shared_fields"]:
        lines.append(
            f"共享字段 {item['node']}.{item['role']}: {item['path']} -> {item['symbol']} = {item['encoding']}"
        )
    if report["diagnostic_errors"]:
        lines.append("诊断附加错误: " + "; ".join(report["diagnostic_errors"]))
    report["message"] = "\n".join(lines)
    return report
