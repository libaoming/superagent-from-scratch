"""长期记忆（SPEC #memory · S6）——跨 session 记忆，写路径独立于对话循环。

核心 aha：**记忆的写路径是一条独立于对话循环的旁路**。对话不因「要更新记忆」而变慢/变脏——
`run()` 收口后只把对话快照**入队**（不立即更新），去抖后一个后台线程调 llm 把「旧记忆 + 新对话」
merge 成新记忆落盘；下一轮 `run()` 前把记忆当 `<memory>` 注回。对照 S2 摘要（session 内压缩），
这是**跨 session 记忆**。

挂载点（M1 拍板）：loop 外的 harness 外壳 `run_with_memory()`，与 S4 skills/S5 goal 同构，run() 零改动（C4）。
读注入（M2 拍板）：记忆走 **user 角色**、不给 system 权限——记忆源自用户、可被污染（OWASP LLM01），
框架数据 vs 用户数据的信任边界。

数据模型（沿用 deer-flow 结构）：**6 段结构化摘要**——user×3 按「画像侧面」切、history×3 按「时间远近」切
——+ 带类型 fact 列表。教学版砍掉 per-slot updatedAt / 多租户 / tiktoken / embedding（F09 out_of_scope）。
"""

import json
import threading
from pathlib import Path

from src.loop import run

MEMORY_TAG = "<memory>"  # 注入标记：读路径插它，写路径按它把「注入的记忆」从喂给 updater 的对话里剔掉

# 6 段摘要的两组 slot（沿用 deer-flow 结构）
_USER_SLOTS = ("workContext", "personalContext", "topOfMind")  # 画像侧面：工作职业 / 个人偏好 / 当前并行焦点
_HISTORY_SLOTS = ("recentMonths", "earlierContext", "longTermBackground")  # 时间远近：近1-3月 / 3-12月 / 更早背景
_SLOT_LABELS = {
    "workContext": "工作", "personalContext": "个人", "topOfMind": "当前焦点",
    "recentMonths": "近期", "earlierContext": "更早", "longTermBackground": "背景",
}

MEMORY_UPDATE_PROMPT = """你是长期记忆更新器。给你「已有记忆」和「新对话」，输出一份**增量更新指令**（严格 JSON、无多余文字）。
6 段摘要按语义分工——user：workContext(工作/公司/项目/技术栈,2-3句) / personalContext(语言/沟通偏好/兴趣,1-2句) / topOfMind(当前并行焦点,3-5个,更新最频繁)；history：recentMonths(近1-3月) / earlierContext(3-12月前) / longTermBackground(更早基础背景)。**只在有新信息时填对应段，无更新留空字符串（空=不改）**：
{{"user": {{"workContext": "", "personalContext": "", "topOfMind": ""}}, "history": {{"recentMonths": "", "earlierContext": "", "longTermBackground": ""}}, "newFacts": [{{"content": "一条新事实", "confidence": 0.0-1.0, "category": "preference|context|knowledge|goal|correction"}}], "factsToRemove": ["与新信息矛盾的旧 fact 的 content 原文"]}}

已有记忆：
{old}

新对话：
{conversation}

只输出 JSON。"""


def empty_memory() -> dict:
    """空记忆的 schema：6 段结构化摘要（user×3 侧面 + history×3 时间）+ facts 列表。"""
    return {
        "user": {s: "" for s in _USER_SLOTS},
        "history": {s: "" for s in _HISTORY_SLOTS},
        "facts": [],
    }


class MemoryStore:
    """单文件全局 JSON 记忆（教学版砍多租户 per-user/per-agent 路径分发）。"""

    def __init__(self, path):
        self._path = Path(path)

    def load(self) -> dict:
        if self._path.exists():
            return json.loads(self._path.read_text())
        return empty_memory()

    def save(self, memory: dict) -> None:
        self._path.write_text(json.dumps(memory, ensure_ascii=False, indent=2))


def filter_messages_for_memory(messages: list) -> list:
    """只留 human 输入 + 最终 ai 文本回复——丢工具往返（tool_use/tool_result）与注入的记忆本身。"""
    kept = []
    for m in messages:
        role, content = m.get("role"), m.get("content")
        if role == "user" and isinstance(content, str):
            if content.startswith(MEMORY_TAG):
                continue  # 注入的记忆别喂回 updater（否则自我强化）
            kept.append(m)
        elif role == "assistant" and isinstance(content, list):
            has_tool = any(b.get("type") == "tool_use" for b in content)
            has_text = any(b.get("type") == "text" for b in content)
            if has_text and not has_tool:  # 纯文本的最终回复才留，中间 tool_use 轮丢
                kept.append(m)
    return kept


def _parse_update(text: str) -> dict:
    """从 llm 文本里扫第一个合法 JSON 对象（容忍 thinking/markdown 包裹）。"""
    start = text.find("{")
    if start < 0:
        return {}
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError:
        return {}
    return obj if isinstance(obj, dict) else {}


def _apply_updates(old: dict, upd: dict, *, threshold: float = 0.7, max_facts: int = 100) -> dict:
    """确定性 merge：6 段非空才覆盖 + facts 过 confidence 门槛 + 内容去重 + 容量截断。

    不是全量重写——llm 只出增量指令，代码兜底，防「LLM 手一抖把整个记忆改乱」。
    """
    memory = empty_memory()
    memory["user"].update({s: old.get("user", {}).get(s, "") for s in _USER_SLOTS})
    memory["history"].update({s: old.get("history", {}).get(s, "") for s in _HISTORY_SLOTS})
    memory["facts"] = list(old.get("facts", []))
    # 6 段：非空字符串才覆盖（段级重写，llm 已负责整合新旧；空串=不改）
    for section, slots in (("user", _USER_SLOTS), ("history", _HISTORY_SLOTS)):
        for slot in slots:
            val = upd.get(section, {}).get(slot)
            if isinstance(val, str) and val.strip():
                memory[section][slot] = val
    # facts：删矛盾 + 过门槛 + 去重 + 截断
    remove = {c.casefold() for c in upd.get("factsToRemove", [])}
    memory["facts"] = [f for f in memory["facts"] if f["content"].casefold() not in remove]
    seen = {f["content"].casefold() for f in memory["facts"]}
    for nf in upd.get("newFacts", []):
        content = nf.get("content", "")
        if not content or nf.get("confidence", 0) < threshold or content.casefold() in seen:
            continue  # 低置信度噪声挡门外 / 内容去重
        memory["facts"].append(
            {"content": content, "confidence": nf.get("confidence", 0), "category": nf.get("category", "")}
        )
        seen.add(content.casefold())
    memory["facts"].sort(key=lambda f: f["confidence"], reverse=True)
    memory["facts"] = memory["facts"][:max_facts]  # 容量上限：confidence 降序保 top-N
    return memory


def update_memory(llm, store: MemoryStore, messages: list) -> None:
    """写路径的「重活」：加载旧记忆 → llm 出增量指令 → 确定性 merge → 落盘。由队列在后台/flush 时调。"""
    convo = filter_messages_for_memory(messages)
    if not convo:
        return
    old = store.load()
    # assistant 消息 content 是 block list——抽 text 块，别把 Python repr 喂给 updater
    def _text(c):
        return "".join(b.get("text", "") for b in c if b.get("type") == "text") if isinstance(c, list) else c
    rendered = "\n".join(f"{m['role']}: {_text(m['content'])}" for m in convo)
    resp = llm.complete(
        system="你是长期记忆更新器，只输出 JSON。",
        messages=[{"role": "user", "content": MEMORY_UPDATE_PROMPT.format(
            old=json.dumps(old, ensure_ascii=False), conversation=rendered)}],
        tools=[],
    )
    text = "".join(b.get("text", "") for b in resp["content"] if b.get("type") == "text")
    upd = _parse_update(text)
    if not upd:
        return  # 解析失败：不动记忆（防污染）
    store.save(_apply_updates(old, upd))


class MemoryQueue:
    """把记忆更新甩出对话循环：add() 只入队快照 + 去抖计时，真正的 llm 更新在 Timer/flush 触发。

    这是「写路径独立于对话循环」的物理体现——对话线程只 add()（瞬时），更新在别处。
    同 key 折叠：连续对话只留最新快照。测试用 background=False + flush() 同步排空，不依赖真实 Timer。
    """

    def __init__(self, llm, store: MemoryStore, *, debounce_s: float = 30.0, background: bool = True):
        self._llm = llm
        self._store = store
        self._debounce_s = debounce_s
        self._background = background
        self._pending: dict = {}  # key -> messages 快照（同 key 覆盖）
        self._timer = None

    def add(self, key, messages: list) -> None:
        self._pending[key] = list(messages)  # 同 key 折叠：只留最新
        if self._background:
            self._reset_timer()

    def _reset_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
        self._timer = threading.Timer(self._debounce_s, self.flush)
        self._timer.daemon = True
        self._timer.start()  # 滑动窗口去抖：每次 add 重新计时，静默 debounce_s 后才落盘

    def flush(self) -> None:
        """排空队列、同步更新所有挂起记忆（Timer 到期或调用方主动调）。"""
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        pending, self._pending = self._pending, {}
        for messages in pending.values():
            update_memory(self._llm, self._store, messages)


def format_memory_for_injection(memory: dict, max_chars: int = 2000) -> str:
    """6 段摘要（非空的）+ facts 按 confidence 降序拼成注入串（教学版 len 粗算预算、无 tiktoken/检索）。"""
    parts = []
    for section, slots in (("user", _USER_SLOTS), ("history", _HISTORY_SLOTS)):
        for slot in slots:
            val = memory.get(section, {}).get(slot, "")
            if val:
                parts.append(f"[{_SLOT_LABELS[slot]}] {val}")
    for f in sorted(memory.get("facts", []), key=lambda x: x["confidence"], reverse=True):
        parts.append(f"- [{f.get('category', '')} | {f['confidence']}] {f['content']}")
    return "\n".join(parts)[:max_chars]


def run_with_memory(state, llm, tools, store: MemoryStore, queue: MemoryQueue, *, key="default", **run_kwargs):
    """harness 外壳：run 前注入记忆（读路径）、run 后入队快照（写路径），run() 零改动。

    读路径 M2：记忆作 **user 角色**注入首条 user 前（不给 system 权限——记忆源自用户、可污染）。
    写路径：只 queue.add（瞬时入队），真正的更新在去抖后的后台/flush——对话不被记忆更新拖慢。
    """
    injected = format_memory_for_injection(store.load())
    if injected:
        state.messages.insert(0, {"role": "user", "content": f"{MEMORY_TAG}\n{injected}\n</memory>"})
    state = run(state, llm, tools, **run_kwargs)
    queue.add(key, state.messages)  # 入队即返回，不等更新
    return state
