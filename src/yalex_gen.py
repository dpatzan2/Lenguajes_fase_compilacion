import re


def read_yal(path: str) -> str:
    """Lee y devuelve el contenido completo de un archivo .yal."""
    return open(path, "r", encoding="utf-8").read()


def split_yal(text):
    header = ""
    trailer = ""
    lets = {}
    rules_block = ""
    text_stripped = text.lstrip()
    if text_stripped.startswith("{"):
        start = text.find("{")
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    header = text[start+1:i].strip()
                    text = text[:start] + text[i+1:]
                    break
    last_open = text.rfind("{")
    last_close = text.rfind("}")
    if last_open != -1 and last_close > last_open:
        trailer_candidate = text[last_open+1:last_close].strip()
        if 'rule' in text[last_open-200:last_open+10] or text.strip().endswith("}"):
            trailer = trailer_candidate
            text = text[:last_open] + text[last_close+1:]
    lets_re = re.compile(r'let\s+([A-Za-z_]\w*)\s*=\s*(.+?)(?=\n(?:let|rule|\Z))', re.S)
    for m in lets_re.finditer(text):
        name = m.group(1)
        val = m.group(2).strip()
        lets[name] = val
    rule_re = re.compile(r'rule\s+([A-Za-z_]\w*)\s*(?:\[.*?\]\s*)?=\s*(.+)', re.S)
    m = rule_re.search(text)
    if not m:
        raise ValueError("No 'rule ... =' block found in YALex file.")
    entrypoint = m.group(1)
    block_start = m.start(2)
    rules_block = text[block_start:].strip()
    return header, lets, entrypoint, rules_block, trailer


def remove_hash_comments(s):
    out = []
    in_dquote = False
    in_squote = False
    in_class = False
    brace_depth = 0
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        # toggle states
        if c == '"' and not in_squote and not in_class and brace_depth == 0:
            in_dquote = not in_dquote
            out.append(c); i += 1; continue
        if c == "'" and not in_dquote and not in_class and brace_depth == 0:
            in_squote = not in_squote
            out.append(c); i += 1; continue
        if c == '[' and not in_dquote and not in_squote and brace_depth == 0:
            in_class = True
            out.append(c); i += 1; continue
        if c == ']' and in_class:
            in_class = False
            out.append(c); i += 1; continue
        if c == '{' and not in_dquote and not in_squote:
            brace_depth += 1
            out.append(c); i += 1; continue
        if c == '}' and brace_depth > 0 and not in_dquote and not in_squote:
            brace_depth -= 1
            out.append(c); i += 1; continue
        if c == '#' and not in_dquote and not in_squote and not in_class and brace_depth == 0:
            i += 1
            while i < n and s[i] != '\n':
                i += 1
            continue
        out.append(c)
        i += 1
    return ''.join(out)

def split_rule_alternatives(rules_block):
    alternatives = []
    i = 0
    n = len(rules_block)
    while i < n:
        while i < n and rules_block[i].isspace():
            i += 1
        if i < n and rules_block[i] == '|':
            i += 1
            while i < n and rules_block[i].isspace():
                i += 1
        start = i
        in_sq = False
        in_dq = False
        in_sqquote = False
        in_squote = False
        escaped = False
        while i < n:
            c = rules_block[i]
            if escaped:
                escaped = False
                i += 1
                continue
            if c == "\\":
                escaped = True
                i += 1
                continue
            if c == '"' and not in_squote and not in_sq:
                in_dq = not in_dq
                i += 1
                continue
            if c == "'" and not in_dq and not in_sq:
                in_squote = not in_squote
                i += 1
                continue
            if c == '[' and not in_dq and not in_squote:
                in_sq = True
                i += 1
                continue
            if c == ']' and in_sq:
                in_sq = False
                i += 1
                continue
            if c == '{' and not in_sq and not in_dq and not in_squote:
                break
            i += 1
        regexp = rules_block[start:i].strip()
        if i >= n or rules_block[i] != '{':
            break
        brace_start = i
        depth = 0
        while i < n:
            if rules_block[i] == '{':
                depth += 1
            elif rules_block[i] == '}':
                depth -= 1
                if depth == 0:
                    action = rules_block[brace_start+1:i].strip()
                    i += 1
                    break
            i += 1
        alternatives.append((regexp, action))
    return alternatives