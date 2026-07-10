"""S6 / F09_memory：长期记忆（SPEC #memory）。

测试纪律不变：LLM 只从 FakeLLM 接缝进，不 patch 内部；用 background=False + flush() 同步排空队列，
不依赖真实 Timer（测试确定性）。核心断言：①写路径独立于对话循环（run 返回后记忆仍空，flush 才更新）
②读路径记忆走 user 角色注入（M2 权限隔离）③updater 确定性 merge（6 段非空才覆盖 + 门槛/去重/删除/截断）。
"""

from pathlib import Path

from src.llm import FakeLLM
from src.loop import State
from src.memory import (
    MemoryQueue,
    MemoryStore,
    _apply_updates,
    _parse_update,
    empty_memory,
    filter_messages_for_memory,
    run_with_memory,
)

FIX = Path(__file__).parent.parent / "fixtures" / "fake_llm"


# ---------- 写路径：独立于对话循环（核心 aha） ----------


def test_write_path_is_off_the_conversation_loop(tmp_path):
    store = MemoryStore(tmp_path / "mem.json")
    llm = FakeLLM(FIX / "memory_update.json")
    queue = MemoryQueue(llm, store, background=False)  # 不起 Timer，手动 flush
    state = run_with_memory(
        State(messages=[{"role": "user", "content": "我在做 superagent-from-scratch"}]),
        llm,
        tools=[],
        store=store,
        queue=queue,
    )
    # 对话已返回，但记忆还没更新——「写路径独立于对话循环」的实证
    assert store.load() == empty_memory()
    # 空记忆 → 不注入空 <memory> 块，首条仍是原始 user 消息
    assert state.messages[0]["content"] == "我在做 superagent-from-scratch"
    # flush 才触发 updater（消耗 response[1] 的增量指令 JSON）
    queue.flush()
    mem = store.load()
    assert "superagent-from-scratch" in mem["user"]["workContext"]  # 段级填充
    assert "长期记忆" in mem["user"]["topOfMind"]
    assert mem["user"]["personalContext"] == ""  # updater 留空 → 该段不改
    contents = [f["content"] for f in mem["facts"]]
    assert any("零框架依赖" in c for c in contents)  # 0.95 fact 留
    assert any("边学边开源" in c for c in contents)  # 0.85 fact 留
    assert not any("噪声" in c for c in contents)  # 0.5 被 0.7 门槛砍
    assert len(mem["facts"]) == 2


# ---------- 读路径：记忆走 user 角色注入（M2 权限隔离） ----------


def test_read_path_injects_memory_as_user_role(tmp_path):
    store = MemoryStore(tmp_path / "mem.json")
    mem = empty_memory()
    mem["user"]["workContext"] = "用户在做千行级 agent 项目"
    mem["facts"] = [{"content": "偏好教学向", "confidence": 0.9, "category": "preference"}]
    store.save(mem)
    llm = FakeLLM(FIX / "natural_close.json")
    queue = MemoryQueue(llm, store, background=False)
    state = run_with_memory(
        State(messages=[{"role": "user", "content": "继续"}]),
        llm,
        tools=[],
        store=store,
        queue=queue,
    )
    first = state.messages[0]
    assert first["role"] == "user"  # M2：记忆走 user 角色，不给 system 权限
    assert first["content"].startswith("<memory>")
    assert "[工作]" in first["content"]  # 段标签
    assert "千行级 agent 项目" in first["content"] and "偏好教学向" in first["content"]
    assert any(m.get("content") == "继续" for m in state.messages)  # 原始 user 消息还在


# ---------- updater 确定性 merge（6 段 + facts） ----------


def test_apply_updates_sections_threshold_dedup_remove():
    old = {
        "user": {"workContext": "旧工作", "personalContext": "", "topOfMind": ""},
        "history": {"recentMonths": "旧近期记录", "earlierContext": "", "longTermBackground": ""},
        "facts": [
            {"content": "已有事实A", "confidence": 0.8, "category": "context"},
            {"content": "要被删的旧事实", "confidence": 0.9, "category": "knowledge"},
        ],
    }
    upd = {
        "user": {"workContext": "新工作", "personalContext": "", "topOfMind": "新焦点"},
        "history": {},  # 不给 history → recentMonths 不动
        "newFacts": [
            {"content": "新事实B", "confidence": 0.95, "category": "preference"},
            {"content": "低置信噪声", "confidence": 0.4, "category": "knowledge"},
            {"content": "已有事实A", "confidence": 0.99, "category": "context"},  # 重复
            {"content": "已有事实a", "confidence": 0.9, "category": "context"},  # 大小写变体 → casefold 去重
            {"content": "恰好门槛", "confidence": 0.7, "category": "context"},  # =0.7 边界：门槛是 <，恰好过
        ],
        "factsToRemove": ["要被删的旧事实"],
    }
    mem = _apply_updates(old, upd)
    assert mem["user"]["workContext"] == "新工作"  # 非空覆盖
    assert mem["user"]["topOfMind"] == "新焦点"
    assert mem["user"]["personalContext"] == ""  # 空段不改
    assert mem["history"]["recentMonths"] == "旧近期记录"  # 空段不覆盖已有非空段
    contents = [f["content"] for f in mem["facts"]]
    assert "新事实B" in contents  # 0.95 过门槛
    assert "低置信噪声" not in contents  # 0.4 被砍
    assert "要被删的旧事实" not in contents  # factsToRemove
    assert contents.count("已有事实A") == 1  # 去重、不重复加
    assert "已有事实a" not in contents  # casefold：大小写变体也算重复
    assert "恰好门槛" in contents  # confidence 恰好 0.7 → 进（门槛含边界）


def test_apply_updates_caps_at_max_facts():
    upd = {"newFacts": [{"content": f"fact{i}", "confidence": 0.7 + i * 0.01, "category": ""} for i in range(10)]}
    mem = _apply_updates(empty_memory(), upd, max_facts=3)
    assert len(mem["facts"]) == 3  # 容量截断
    assert mem["facts"][0]["confidence"] >= mem["facts"][-1]["confidence"]  # 保 confidence top-N


# ---------- 消息过滤 + JSON 解析 + 队列折叠 ----------


def test_filter_keeps_human_and_final_ai_only():
    messages = [
        {"role": "user", "content": "<memory>\n旧记忆\n</memory>"},  # 注入的记忆 → 丢
        {"role": "user", "content": "帮我数文件"},  # human → 留
        {"role": "assistant", "content": [{"type": "tool_use", "id": "1", "name": "bash", "input": {}}]},  # 工具轮 → 丢
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "1", "content": "3"}]},  # tool_result → 丢
        {"role": "assistant", "content": [{"type": "text", "text": "共 3 个文件"}]},  # 最终 ai → 留
    ]
    kept = filter_messages_for_memory(messages)
    assert [m["content"] if isinstance(m["content"], str) else m["content"][0]["text"] for m in kept] == [
        "帮我数文件", "共 3 个文件",
    ]


def test_parse_update_tolerates_wrapping():
    text = '让我想想...\n```json\n{"user": {}, "history": {}, "newFacts": [], "factsToRemove": []}\n```'
    assert _parse_update(text) == {"user": {}, "history": {}, "newFacts": [], "factsToRemove": []}
    assert _parse_update("no json here") == {}  # 解析不到 → 空 dict（调用方据此不动记忆）


def test_queue_folds_same_key(tmp_path):
    queue = MemoryQueue(None, MemoryStore(tmp_path / "mem.json"), background=False)  # llm=None，不 flush 不调
    queue.add("t1", [{"role": "user", "content": "snap1"}])
    queue.add("t1", [{"role": "user", "content": "snap2"}])  # 同 key 覆盖
    assert len(queue._pending) == 1
    assert queue._pending["t1"][0]["content"] == "snap2"  # 只留最新快照
