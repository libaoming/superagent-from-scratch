#!/usr/bin/env python3
"""Stop hook · 防造假收口闸（harness 默认）。

把 harness 的核心纪律「完成声明前先回读」在 Stop 边界机器化：
末轮 assistant 文本里出现「已写 / 已落盘 / 创建了 + 文件名」，或交付表里
`path`（N 行）这类落盘声明时，逐一对磁盘 test -f。有声称却不存在的文件，
阻断收口（exit 2），把缺失清单喂回 Claude 强制真核验——把「手打假
File created / 谎报落盘」在出口拦死。与 stop-progress-append.sh 成一对：
一个记录动作、一个校验落盘声明。

设计要点（低误伤 + fail-open）：
- 只在「落盘声明关键词 或 (N 行) 计数」与路径同行时才收候选；
- 带省略号 …/... 或通配 * ? 的路径一律跳过（无法 test 缩写，跳过才不误伤）；
- 只对「声称落盘 且 磁盘不存在」的全拼路径 exit 2；
- stop_hook_active=true（已因本 hook 续过一次）直接放行，最多一次强制复检，不死循环；
- 任何解析异常 / 缺 python3 一律放行（非阻塞），绝不因 hook 自身把会话卡死。

依赖：python3（macOS/多数开发机自带）。无 python3 时 hook 命令执行失败，
Stop hook 非 2 退出码按非阻塞处理，自动降级为 no-op。
"""
import sys, os, json, re


def load_last_assistant_text(transcript_path):
    """返回 transcript 里最后一条 assistant 消息的全部 text block 拼接。"""
    try:
        with open(transcript_path, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return ""
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        msg = row.get("message", {})
        if (msg.get("role") or row.get("type")) != "assistant":
            continue
        content = msg.get("content")
        texts = []
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "text":
                    texts.append(b.get("text", ""))
        if texts:
            return "\n".join(texts)
    return ""


CLAIM = re.compile(
    r"已写|已落盘|已创建|已生成|已保存|落盘|写入了|创建了|新建了?|"
    r"created|written|saved|generated|wrote",
    re.IGNORECASE,
)
PATH = re.compile(r"[`\"']?([A-Za-z0-9_][\w./-]*\.[A-Za-z0-9]{1,6})[`\"']?")
LINECOUNT = re.compile(r"[（(]\s*\d+\s*(?:行|lines?)")


def extract_claimed_paths(text):
    out = set()
    for line in text.splitlines():
        if not (CLAIM.search(line) or LINECOUNT.search(line)):
            continue
        for m in PATH.finditer(line):
            p = m.group(1)
            if any(x in p for x in ("...", "…", "*", "?", "<", ">")):
                continue
            if p.startswith(("http", "//")):
                continue
            out.add(p)
    return out


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        sys.exit(0)

    if data.get("stop_hook_active"):
        sys.exit(0)

    tpath = data.get("transcript_path")
    if not tpath or not os.path.exists(tpath):
        sys.exit(0)

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()

    text = load_last_assistant_text(tpath)
    if not text:
        sys.exit(0)

    candidates = extract_claimed_paths(text)
    if not candidates:
        sys.exit(0)

    missing = []
    for p in sorted(candidates):
        full = p if os.path.isabs(p) else os.path.join(project_dir, p)
        if not os.path.exists(full):
            missing.append(p)

    if not missing:
        sys.exit(0)

    msg = (
        "⛔ 收口闸拦截：你在末轮声称落盘/创建了以下文件，但 test -f 在磁盘上"
        "找不到它们——这正是「手打假 File created / 谎报落盘」的特征。\n"
        + "\n".join(f"  ❌ {p}" for p in missing)
        + "\n\n完成声明前先回读：现在只准跑命令、报字面输出，不准论证。"
        "对每个缺失文件跑一次干净的 Write（不附加任何文字），或用 ls/wc 核实"
        "真实状态后据实修正收口声明。核实通过前不许结束。"
    )
    print(msg, file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
