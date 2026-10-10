"""Split laboratory SQL scripts without breaking functions or strings."""

from __future__ import annotations


def split_sql(script: str) -> list[str]:
    """Split ``script`` on semicolons that sit outside quotes, comments, and dollar quotes."""
    statements: list[str] = []
    buf: list[str] = []
    dollar_stack: list[str] = []
    in_single = False
    in_line_comment = False
    in_block_comment = False
    i = 0
    length = len(script)

    while i < length:
        if in_line_comment:
            buf.append(script[i])
            if script[i] == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            if script.startswith("*/", i):
                buf.append("*/")
                in_block_comment = False
                i += 2
                continue
            buf.append(script[i])
            i += 1
            continue

        if dollar_stack:
            tag = _dollar_tag(script, i)
            if tag is not None:
                buf.append(tag)
                i += len(tag)
                if tag == dollar_stack[-1]:
                    dollar_stack.pop()
                else:
                    dollar_stack.append(tag)
                continue
            buf.append(script[i])
            i += 1
            continue

        if in_single:
            buf.append(script[i])
            if script[i] == "'":
                if script.startswith("''", i):
                    buf.append("'")
                    i += 2
                    continue
                in_single = False
            i += 1
            continue

        if script.startswith("--", i):
            buf.append("--")
            in_line_comment = True
            i += 2
            continue

        if script.startswith("/*", i):
            buf.append("/*")
            in_block_comment = True
            i += 2
            continue

        if script[i] == "'":
            buf.append("'")
            in_single = True
            i += 1
            continue

        tag = _dollar_tag(script, i)
        if tag is not None:
            dollar_stack.append(tag)
            buf.append(tag)
            i += len(tag)
            continue

        if script[i] == ";":
            statement = "".join(buf).strip()
            if _has_sql(statement):
                statements.append(statement)
            buf = []
            i += 1
            continue

        buf.append(script[i])
        i += 1

    tail = "".join(buf).strip()
    if _has_sql(tail):
        statements.append(tail)
    return statements


def _dollar_tag(script: str, start: int) -> str | None:
    if start >= len(script) or script[start] != "$":
        return None
    end = start + 1
    while end < len(script) and (script[end].isalnum() or script[end] == "_"):
        end += 1
    if end < len(script) and script[end] == "$":
        return script[start : end + 1]
    return None


def _has_sql(statement: str) -> bool:
    return bool(_strip_comments(statement).strip())


def _strip_comments(statement: str) -> str:
    """Remove comments so a comment-only fragment is not executed."""
    kept: list[str] = []
    dollar_stack: list[str] = []
    in_single = False
    in_line_comment = False
    in_block_comment = False
    i = 0
    length = len(statement)

    while i < length:
        if in_line_comment:
            if statement[i] == "\n":
                kept.append("\n")
                in_line_comment = False
            i += 1
            continue
        if in_block_comment:
            if statement.startswith("*/", i):
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue
        if dollar_stack:
            tag = _dollar_tag(statement, i)
            if tag is not None:
                kept.append(tag)
                i += len(tag)
                if tag == dollar_stack[-1]:
                    dollar_stack.pop()
                else:
                    dollar_stack.append(tag)
                continue
            kept.append(statement[i])
            i += 1
            continue
        if in_single:
            kept.append(statement[i])
            if statement[i] == "'" and statement.startswith("''", i):
                kept.append("'")
                i += 2
                continue
            if statement[i] == "'":
                in_single = False
            i += 1
            continue
        if statement.startswith("--", i):
            in_line_comment = True
            i += 2
            continue
        if statement.startswith("/*", i):
            in_block_comment = True
            i += 2
            continue
        if statement[i] == "'":
            kept.append("'")
            in_single = True
            i += 1
            continue
        tag = _dollar_tag(statement, i)
        if tag is not None:
            dollar_stack.append(tag)
            kept.append(tag)
            i += len(tag)
            continue
        kept.append(statement[i])
        i += 1
    return "".join(kept)
