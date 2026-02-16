"""
Delegate Auto 工具 - 自动依赖分析后串并行混合执行。
"""

from __future__ import annotations

import json
import re
from collections import defaultdict, deque
from typing import TYPE_CHECKING, Any

from solopreneur.agent.core.tools.base import Tool

if TYPE_CHECKING:
    from solopreneur.agent.core.subagent import SubagentManager
    from solopreneur.agent.definitions.manager import AgentManager


class DelegateAutoTool(Tool):
    """根据任务依赖自动选择串行或并行委派。"""

    _PATH_RE = re.compile(r"[A-Za-z0-9_./\\-]+\.(?:py|ts|tsx|js|jsx|vue|java|kt|go|rs|sql|md|yaml|yml|json)")

    def __init__(self, manager: "SubagentManager", agent_manager: "AgentManager"):
        self._manager = manager
        self._agent_manager = agent_manager

    @property
    def name(self) -> str:
        return "delegate_auto"

    @property
    def description(self) -> str:
        return (
            "自动分析任务依赖并执行混合调度："
            "独立任务并行，存在依赖的任务串行。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        agent_names = self._agent_manager.get_agent_names()
        return {
            "type": "object",
            "properties": {
                "jobs": {
                    "type": "array",
                    "description": "任务列表。可选 depends_on 指明依赖；不提供时自动推断。",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "可选任务ID"},
                            "agent": {"type": "string", "enum": agent_names, "description": "Agent名称"},
                            "task": {"type": "string", "description": "任务描述"},
                            "context": {"type": "string", "description": "可选上下文"},
                            "project_dir": {"type": "string", "description": "可选项目目录"},
                            "depends_on": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "可选依赖任务ID列表",
                            },
                        },
                        "required": ["agent", "task"],
                    },
                },
                "max_parallel": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 8,
                    "description": "最大并发度，默认3",
                },
            },
            "required": [],
        }

    async def execute(self, jobs: list[dict[str, Any]] | None = None, max_parallel: int = 3, **kwargs: Any) -> str:
        if not isinstance(jobs, list) or not jobs:
            raw = kwargs.get("raw")
            parsed_jobs, parsed_parallel = self._parse_jobs_from_raw(raw)
            if parsed_parallel is not None:
                max_parallel = parsed_parallel
            jobs = parsed_jobs

        if not jobs:
            return (
                "错误: jobs 不能为空。请传入 jobs 数组，"
                "或提供可解析的 raw JSON（含 agent/task 列表）。"
            )

        normalized = self._normalize_jobs(jobs)
        self._apply_auto_dependencies(normalized)
        layers, cycle = self._topo_layers(normalized)

        if cycle:
            # 回退到输入顺序串行，确保可执行
            layers = [[j["id"] for j in normalized]]

        id_to_job = {j["id"]: j for j in normalized}
        id_to_result: dict[str, str] = {}
        id_to_ok: dict[str, bool] = {}

        for layer in layers:
            run_jobs = []
            layer_ids = []
            for job_id in layer:
                job = id_to_job[job_id]
                dep_ctx = []
                for dep_id in job["depends_on"]:
                    if dep_id in id_to_result:
                        dep_ctx.append(f"[依赖 {dep_id}]\n{id_to_result[dep_id]}")
                merged_context = (job.get("context") or "").strip()
                if dep_ctx:
                    merged_context = (merged_context + "\n\n" + "\n\n".join(dep_ctx)).strip()

                run_jobs.append(
                    {
                        "agent": job["agent"],
                        "task": job["task"],
                        "context": merged_context,
                        "project_dir": job.get("project_dir") or "",
                    }
                )
                layer_ids.append(job_id)

            if len(run_jobs) == 1:
                only_id = layer_ids[0]
                only = run_jobs[0]
                agent_def = self._agent_manager.get_agent(only["agent"])
                if not agent_def:
                    id_to_ok[only_id] = False
                    id_to_result[only_id] = f"错误: unknown agent {only['agent']}"
                else:
                    try:
                        out = await self._manager.run_with_agent(
                            agent_def=agent_def,
                            agent_manager=self._agent_manager,
                            task=only["task"],
                            context=only["context"],
                            project_dir=only["project_dir"],
                        )
                        id_to_ok[only_id] = True
                        id_to_result[only_id] = out
                    except Exception as e:
                        id_to_ok[only_id] = False
                        id_to_result[only_id] = f"错误: {e}"
            else:
                outs = await self._manager.run_with_agents_parallel(
                    agent_manager=self._agent_manager,
                    jobs=run_jobs,
                    max_parallel=max_parallel,
                )
                for i, out in enumerate(outs):
                    jid = layer_ids[i]
                    id_to_ok[jid] = bool(out.get("ok"))
                    id_to_result[jid] = out.get("result") if out.get("ok") else f"错误: {out.get('error', 'unknown')}"

        ok_count = sum(1 for jid in id_to_ok if id_to_ok[jid])
        fail_count = len(normalized) - ok_count

        lines = [
            f"自动调度完成：成功 {ok_count} / 失败 {fail_count}",
            f"调度层数: {len(layers)}" + (" (检测到循环依赖，已回退串行)" if cycle else ""),
            "",
            "## 调度计划",
        ]

        for idx, layer in enumerate(layers, 1):
            labels = [f"{jid}({id_to_job[jid]['agent']})" for jid in layer]
            lines.append(f"- 第{idx}层 {'并行' if len(layer) > 1 else '串行'}: " + ", ".join(labels))

        lines.append("")
        lines.append("## 执行结果")
        for job in normalized:
            jid = job["id"]
            status = "✅" if id_to_ok.get(jid) else "❌"
            lines.append(f"### {status} {jid} · {job['agent']}")
            lines.append(id_to_result.get(jid, ""))
            lines.append("")

        return "\n".join(lines)

    def _normalize_jobs(self, jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        used_ids: set[str] = set()
        for i, j in enumerate(jobs, 1):
            jid = str(j.get("id") or f"job_{i}").strip()
            if not jid or jid in used_ids:
                jid = f"job_{i}"
            used_ids.add(jid)

            task = str(j.get("task") or "").strip()
            agent = str(j.get("agent") or "").strip()
            depends = [str(x).strip() for x in (j.get("depends_on") or []) if str(x).strip()]

            normalized.append(
                {
                    "id": jid,
                    "agent": agent,
                    "task": task,
                    "context": str(j.get("context") or ""),
                    "project_dir": str(j.get("project_dir") or ""),
                    "depends_on": depends,
                    "class": self._classify(task),
                    "paths": set(self._extract_paths(task)),
                }
            )
        return normalized

    def _apply_auto_dependencies(self, jobs: list[dict[str, Any]]) -> None:
        # 若已经显式声明依赖则优先使用
        has_explicit = any(j["depends_on"] for j in jobs)
        if has_explicit:
            return

        for i, cur in enumerate(jobs):
            # 审查/测试/发布类默认依赖前序实现任务
            if cur["class"] in {"review", "test", "release", "integration"}:
                cur["depends_on"].extend(j["id"] for j in jobs[:i])
                continue

            # 同文件目标冲突任务串行（后者依赖前者）
            for prev in jobs[:i]:
                if cur["paths"] and prev["paths"] and (cur["paths"] & prev["paths"]):
                    cur["depends_on"].append(prev["id"])

        # 去重保持顺序
        for j in jobs:
            seen: set[str] = set()
            dedup = []
            for dep in j["depends_on"]:
                if dep not in seen:
                    dedup.append(dep)
                    seen.add(dep)
            j["depends_on"] = dedup

    def _topo_layers(self, jobs: list[dict[str, Any]]) -> tuple[list[list[str]], bool]:
        ids = {j["id"] for j in jobs}
        indeg = defaultdict(int)
        edges = defaultdict(list)

        for j in jobs:
            indeg[j["id"]] = indeg[j["id"]]
            for dep in j["depends_on"]:
                if dep not in ids:
                    continue
                edges[dep].append(j["id"])
                indeg[j["id"]] += 1

        q = deque([jid for jid in ids if indeg[jid] == 0])
        layers: list[list[str]] = []
        visited = 0

        while q:
            layer_size = len(q)
            layer: list[str] = []
            for _ in range(layer_size):
                cur = q.popleft()
                visited += 1
                layer.append(cur)
                for nxt in edges[cur]:
                    indeg[nxt] -= 1
                    if indeg[nxt] == 0:
                        q.append(nxt)
            layers.append(layer)

        has_cycle = visited != len(ids)

        # 稳定顺序：按输入顺序重排每层
        input_order = {j["id"]: i for i, j in enumerate(jobs)}
        for layer in layers:
            layer.sort(key=lambda x: input_order.get(x, 0))

        return layers, has_cycle

    def _extract_paths(self, text: str) -> list[str]:
        return [p.replace("\\", "/") for p in self._PATH_RE.findall(text or "")]

    def _parse_jobs_from_raw(self, raw: Any) -> tuple[list[dict[str, Any]], int | None]:
        """从畸形 raw 字符串中尽量恢复 jobs 与 max_parallel。"""
        if not isinstance(raw, str) or not raw.strip():
            return [], None

        text = raw.strip()

        # 去 markdown 包裹
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

        parsed_parallel: int | None = None
        m = re.search(r'"max_parallel"\s*:\s*(\d+)', text)
        if m:
            try:
                parsed_parallel = int(m.group(1))
            except Exception:
                parsed_parallel = None

        # 先尝试标准 JSON
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                jobs = obj.get("jobs")
                if isinstance(jobs, list):
                    if isinstance(obj.get("max_parallel"), int):
                        parsed_parallel = obj["max_parallel"]
                    return jobs, parsed_parallel
                if "agent" in obj and "task" in obj:
                    return [obj], parsed_parallel
            elif isinstance(obj, list):
                return [j for j in obj if isinstance(j, dict)], parsed_parallel
        except Exception:
            pass

        # 回退：抽取多个顶层 { ... } 对象
        jobs: list[dict[str, Any]] = []
        for frag in self._extract_json_objects(text):
            try:
                item = json.loads(frag)
            except Exception:
                continue
            if not isinstance(item, dict):
                continue

            # 兼容第一段错误格式：{"jobs":"architect", "agent":"architect", "task":"..."}
            if "agent" in item and "task" in item:
                if isinstance(item.get("jobs"), str) and not item.get("id"):
                    item["id"] = item["jobs"]
                jobs.append(item)

        return jobs, parsed_parallel

    def _extract_json_objects(self, text: str) -> list[str]:
        """从文本中提取顶层 JSON 对象片段。"""
        parts: list[str] = []
        depth = 0
        start = -1
        in_str = False
        esc = False

        for i, ch in enumerate(text):
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue

            if ch == '"':
                in_str = True
                continue

            if ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}':
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start != -1:
                        parts.append(text[start:i + 1])
                        start = -1

        return parts

    def _classify(self, task: str) -> str:
        t = (task or "").lower()
        if any(k in t for k in ["test", "测试", "单测", "集成测试"]):
            return "test"
        if any(k in t for k in ["review", "审查", "code review", "评审"]):
            return "review"
        if any(k in t for k in ["release", "deploy", "上线", "发布"]):
            return "release"
        if any(k in t for k in ["联调", "integration", "集成"]):
            return "integration"
        return "implementation"
