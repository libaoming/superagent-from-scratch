"""skills 技能系统（SPEC #skills）——第四类扩展：注入知识，不占任何缝。

工具/subagent 给能力（缝③）、middleware 给横切行为（缝①），skills 走 messages 内容
本身给知识（怎么做的说明书）。发现与激活都在 loop 外，run() 零改动（C4）。

token 经济学（核心）：**元数据常驻、正文按需**——
- 发现：启动扫 SKILL.md，只把 name+description（便宜）拼进 system prompt；
- 激活：用户消息以 `/名字 ` 开头，才把该 SKILL.md 全文（贵）注入当轮 user 消息前缀块。
注入点 Q3=A：进 user 前缀块而非 system——进 history 可被 Summarization 压缩、可测。
"""

from pathlib import Path

import yaml


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """拆 `---\\nYAML\\n---\\n正文`；无 frontmatter 则元数据为空、全文为正文。"""
    if text.startswith("---"):
        _, fm, body = text.split("---", 2)
        return yaml.safe_load(fm) or {}, body.strip()
    return {}, text


def discover_skills(skills_dir) -> tuple[dict, str]:
    """递归扫 skills_dir 下所有 SKILL.md，返回 (registry, system_block)。

    registry: {name: {"description": str, "path": Path}}——path 留给激活时读全文，不进 system。
    system_block: 只含每个 skill 的 name+description（常驻系统提示的便宜部分）。
    """
    registry: dict = {}
    # 教学版不设防畸形 SKILL.md：未闭合 `---` 或 YAML 语法错会让 _parse_frontmatter 抛异常、
    # 穿透本循环中止整个发现（一个坏文件全灭）。生产版应 try/except 逐个跳过坏文件。
    for skill_md in sorted(Path(skills_dir).rglob("SKILL.md")):
        meta, _body = _parse_frontmatter(skill_md.read_text())
        name, desc = meta.get("name"), meta.get("description")
        if name and desc:  # 两个必填字段齐才注册
            # 重名 skill：sorted 路径序在后者静默胜出，教学版不告警
            registry[name] = {"description": desc, "path": skill_md}
    if not registry:
        return registry, ""
    lines = [f"/{n}：{s['description']}" for n, s in registry.items()]
    return registry, "可用技能（斜杠激活）：\n" + "\n".join(lines)


def activate(user_text: str, registry: dict) -> str:
    """用户消息以 `/名字 ` 开头且名字已注册 → 全文作前缀块注入；否则原样放行。"""
    if not user_text.startswith("/"):
        return user_text
    name, _, rest = user_text[1:].partition(" ")
    skill = registry.get(name)
    if skill is None:
        return user_text  # 未注册的斜杠名当普通文本，教学版不报错
    # 读整个文件（含 frontmatter），即 SPEC「全文」的字面——description 会在 system_block
    # 与此处 user 前缀块各注一次，教学版有意为之（保持「全文」简单）；生产版可只注 body。
    full = Path(skill["path"]).read_text().strip()
    return f"{full}\n\n{rest}" if rest else full
