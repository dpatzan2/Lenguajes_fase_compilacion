import re
from collections import defaultdict

def read_yal(path: str) -> str:
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

class RegexParser:
    def __init__(self, s, lets=None):
        self.s = s
        self.i = 0
        self.n = len(s)
        self.lets = lets or {}

    def peek(self):
        return self.s[self.i] if self.i < self.n else None

    def get(self):
        c = self.peek()
        if c is not None:
            self.i += 1
        return c

    def parse(self):
        if self.lets:
            s = self.s
            for k, v in self.lets.items():
                s = re.sub(r'\{' + re.escape(k) + r'\}', '(' + v + ')', s)
            for k, v in self.lets.items():
                s = re.sub(r'(?<!\w)'+re.escape(k)+r'(?!\w)', '(' + v + ')', s)
            self.s = s
            self.n = len(self.s)
        expr = self.parse_alt()
        return expr

    def parse_alt(self):
        parts = [self.parse_concat()]
        while self.peek() == '|':
            self.get()
            parts.append(self.parse_concat())
        if len(parts) == 1:
            return parts[0]
        else:
            return ('alt', parts)

    def parse_concat(self):
        nodes = []
        while True:
            if self.peek() is None or self.peek() in ')|':
                break
            node = self.parse_repeat()
            if node is None:
                break
            nodes.append(node)
        if not nodes:
            return ('epsilon',)
        if len(nodes) == 1:
            return nodes[0]
        return ('concat', nodes)
    
    def parse_repeat(self):
        node = self.parse_atom()
        if node is None:
            return None
        while True:
            p = self.peek()
            if p == '*':
                self.get()
                node = ('star', node)
            elif p == '+':
                self.get()
                node = ('plus', node)
            elif p == '?':
                self.get()
                node = ('opt', node)
            else:
                break
        return node

    def parse_atom(self):
        c = self.peek()
        if c is None:
            return None
        if c == '(':
            self.get()
            sub = self.parse_alt()
            if self.peek() == ')':
                self.get()
            return sub
        if c == '"':
            return self.parse_string()
        if c == "'":
            return self.parse_string(quote="'")
        if c == '[':
            return self.parse_class()
        if c == '.':
            self.get()
            return ('dot',)
        if c == '\\':
            self.get()
            nxt = self.get()
            if nxt is None:
                return ('char', '')
            return ('char', self.unescape(nxt))
        if c in '*+?)|':
            return None
        self.get()
        return ('char', c)

    def unescape(self, c):
        escapes = {'n':'\n','t':'\t','r':'\r','\\':'\\','"':'"',"'" : "'"}
        return escapes.get(c, c)

    def parse_string(self, quote='"'):
        self.get()
        chars = []
        while True:
            c = self.get()
            if c is None:
                break
            if c == '\\':
                nxt = self.get()
                if nxt is None:
                    break
                chars.append(self.unescape(nxt))
                continue
            if c == quote:
                break
            chars.append(c)
        content = ''.join(chars)
        if len(content) == 0:
            return ('epsilon',)
        if len(content) == 1:
            return ('char', content)
        return ('str', content)

    def parse_class(self):
        self.get()
        neg = False
        if self.peek() == '^':
            neg = True
            self.get()
        items = []
        prev = None
        while True:
            c = self.get()
            if c is None:
                break
            if c == ']':
                break
            if c == '\\':
                c = self.get()
                if c is None:
                    break
                items.append(self.unescape(c))
                prev = items[-1]
                continue
            if c == '-' and prev is not None and self.peek() != ']' and len(items) > 0:
                end = self.get()
                if end == '\\':
                    end = self.get()
                if end is None:
                    break
                for ch in range(ord(prev)+1, ord(end)+1):
                    items.append(chr(ch))
                prev = items[-1]
                continue
            items.append(c)
            prev = c
        return ('class', (neg, set(items)))
    
class NFAState:
    _id_counter = 0
    def __init__(self):
        self.id = NFAState._id_counter
        NFAState._id_counter += 1
        self.eps = []
        self.trans = defaultdict(list)

class NFA:
    def __init__(self, start, accept):
        self.start = start
        self.accept = accept

def ast_to_nfa(ast):
    t = ast[0]
    if t == 'char':
        s = NFAState(); a = NFAState()
        sym = ast[1]
        s.trans[sym].append(a)
        return NFA(s,a)
    if t == 'str':
        seq = ast[1]
        states = []
        for ch in seq:
            s = NFAState(); a = NFAState()
            s.trans[ch].append(a)
            states.append((s,a))
        for i in range(len(states)-1):
            states[i][1].eps.append(states[i+1][0])
        return NFA(states[0][0], states[-1][1])
    if t == 'dot':
        s = NFAState(); a = NFAState()
        s.trans[None].append(a)
        return NFA(s,a)
    if t == 'class':
        neg, items = ast[1]
        s = NFAState(); a = NFAState()
        s.trans[('class', neg, frozenset(items))].append(a)
        return NFA(s,a)
    if t == 'epsilon':
        s = NFAState(); a = NFAState()
        s.eps.append(a)
        return NFA(s,a)
    if t == 'star':
        inner = ast_to_nfa(ast[1])
        s = NFAState(); a = NFAState()
        s.eps.extend([inner.start, a])
        inner.accept.eps.extend([inner.start, a])
        return NFA(s,a)
    if t == 'plus':
        inner = ast_to_nfa(ast[1])
        s = NFAState(); a = NFAState()
        s.eps.append(inner.start)
        inner.accept.eps.extend([inner.start, a])
        return NFA(s,a)
    if t == 'opt':
        inner = ast_to_nfa(ast[1])
        s = NFAState(); a = NFAState()
        s.eps.extend([inner.start, a])
        inner.accept.eps.append(a)
        return NFA(s,a)
    if t == 'concat':
        nodes = ast[1]
        nfa_list = [ast_to_nfa(n) for n in nodes]
        for i in range(len(nfa_list)-1):
            nfa_list[i].accept.eps.append(nfa_list[i+1].start)
        return NFA(nfa_list[0].start, nfa_list[-1].accept)
    if t == 'alt':
        parts = ast[1]
        s = NFAState(); a = NFAState()
        for p in parts:
            np = ast_to_nfa(p)
            s.eps.append(np.start)
            np.accept.eps.append(a)
        return NFA(s,a)
    s = NFAState(); a = NFAState(); s.eps.append(a); return NFA(s,a)

def epsilon_closure(states):
    stack = list(states)
    res = set(states)
    while stack:
        st = stack.pop()
        for nx in st.eps:
            if nx not in res:
                res.add(nx)
                stack.append(nx)
    return res

def nfa_all_symbol_keys(nfa_start):
    visited = set()
    stack = [nfa_start]
    keys = set()
    while stack:
        st = stack.pop()
        if st in visited:
            continue
        visited.add(st)
        for k, vlist in st.trans.items():
            keys.add(k)
            for v2 in vlist:
                stack.append(v2)
        for e in st.eps:
            stack.append(e)
    return keys