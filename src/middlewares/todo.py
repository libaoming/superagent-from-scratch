"""write_todos 工具 + TodoMiddleware（SPEC #long-task · 计划外置）。

长任务最大的敌人之一：计划只活在对话历史里，一旦 Summarization 压缩就可能被压没（S2）。
对策 = **把计划外置到 state.todos**（结构化字段，摘要只碰 messages 不碰它），每轮 before_model
再把当前清单渲染成一条提醒重注入——**计划活在 state、不活在模型脑子里**。

- write_todos（工具，缝③）：全量替换 state.todos（覆盖即真相，教学版不做增量 diff）。
  state 走构造注入（Q1=A 同款：谁需要谁持有），工具协议 name/description/input_schema/run 不变。
- TodoMiddleware（缝①）：before_model 撤旧提醒、按当前 todos 重注一条——只保留一条、不累积。
"""

from src.middleware import Middleware


class WriteTodos:
    name = "write_todos"
    description = (
        "登记/更新任务计划清单（全量覆盖，每次传完整清单）。"
        "把多步计划外置到状态里、不靠记忆——长任务里先列计划再逐条推进时用。"
    )
    input_schema = {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "description": "完整的待办清单（覆盖旧清单，不是追加）",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "一条待办事项"},
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed"],
                        },
                    },
                    "required": ["content", "status"],
                },
            }
        },
        "required": ["todos"],
    }

    def __init__(self, state):
        # 构造注入：工具持有它要写的 state。隐式不变量——依赖 run() 全程「原地 mutate 同一 State 对象」
        # （loop.py 全程 return state、从不 new 一个返回）；哪天 run 改成返回新 State，这里会写到陈旧对象上。
        self._state = state

    def run(self, *, todos: list) -> str:
        self._state.todos = todos  # 全量替换：覆盖即真相
        done = sum(1 for t in todos if t.get("status") == "completed")
        return f"已更新计划：{len(todos)} 项（已完成 {done}）"


class TodoMiddleware(Middleware):
    """每轮 before_model 把 state.todos 渲染成一条提醒重注入——只保留一条、不累积。"""

    MARK = "[当前计划]"

    def before_model(self, state) -> None:
        # 撤上一轮的旧提醒（避免每轮累积），再按当前 todos 重注——提醒始终反映最新 state.todos
        state.messages[:] = [m for m in state.messages if not self._is_reminder(m)]
        if not state.todos:
            return
        lines = "\n".join(f"- [{t['status']}] {t['content']}" for t in state.todos)
        state.messages.append({"role": "user", "content": f"{self.MARK}\n{lines}"})

    def _is_reminder(self, msg) -> bool:
        # 边界：用户自己发的、恰以 MARK 开头的消息会被误删（教学版接受；生产版可用更独特的哨兵串）
        c = msg.get("content")
        return msg.get("role") == "user" and isinstance(c, str) and c.startswith(self.MARK)
