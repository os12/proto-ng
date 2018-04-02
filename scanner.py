from enum import Enum
from utils import log

class Token:
    class Type(Enum):
        EoF = 1
        Whitespace = 2
        DataType = 3
        Specifier = 4
        Identifier = 5

        Keyword = 7
        Number = 8

        Equals = 9
        Semi = 10
        String = 11
        ParenOpen = 12
        ParenClose = 13
        ScopeOpen = 14
        ScopeClose = 15
        Dot = 16

    def __init__(self, type):
        self.type = type
        self.value = ""
        self.line = self.pos = 0

    def __str__(self):
        rv = "Token(" + str(self.type)
        if self.value:
            rv += ', "' + self.value + '"'
        return rv + ")"

class Scanner:
    def __init__(self, fname, flags = 0):
        import collections, re

        log(1, "Opening file: " + fname)
        self.__file = open(fname, "r")
        self.__queue = []
        self.filename = fname.split('/')[-1]
        self.line = 0
        self.non_terminals = [
            Token.Type.Identifier, Token.Type.Specifier,
            Token.Type.Keyword, Token.Type.DataType, Token.Type.Number, Token.Type.String]

        self.__keywords = {'package', 'import', 'option', 'message', 'enum'}
        tokens = [
            ("Whitespace", r'[ \t\r\n]+|//.*$'),

            ("DataType", r'int32|uint32|int64|uint64|double|float|string|bool'),
            ("Specifier", r'repeated|optional'),

            ("Identifier", r'[A-Za-z][A-Za-z0-9_]*'),

            ("Equals", r'='),
            ("Number", r'\d+'),
            ("ParenOpen", r'\('),
            ("ParenClose", r'\)'),
            ("ScopeOpen", r'{'),
            ("ScopeClose", r'}'),
            ("Semi", r';'),
            ("Dot", r'\.'),
            ("String", r'"[^"]*"'),
        ]

        tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in tokens)
        self.__get_token = re.compile(tok_regex).match

    def get(self, idx = 0):
        while idx >= len(self.__queue):
            for token in self.__scan(self.__file.readline()):
                log(3, "Got token: " + str(token))
                self.__queue.append(token)
        return self.__queue[idx]

    def next(self):
        return self.get().type

    def pop(self):
        assert(not self.reached_eof())
        assert(len(self.__queue) > 0)
        return self.__queue.pop(0)

    def reached_eof(self):
        return self.get().type == Token.Type.EoF

    def __scan(self, line):
        if not line:
            yield Token(Token.Type.EoF)

        self.line += 1
        pos = line_start = 0

        mo = self.__get_token(line)
        while mo:
            ttype = Token.Type[mo.lastgroup]
            if ttype != Token.Type.Whitespace:
                val = mo.group(mo.lastgroup)
                if ttype == Token.Type.Identifier and val in self.__keywords:
                    ttype = Token.Type.Keyword
                tok = Token(ttype)
                tok.line = self.line
                tok.pos = mo.start() - line_start
                if ttype in self.non_terminals:
                    tok.value = val
                yield tok
            pos = mo.end()
            mo = self.__get_token(line, pos)
        if pos != len(line):
            raise ValueError('Unexpected character %r on line %d' %
                (line[pos], self.line))

class Context:
    def __init__(self, scanner):
        self.scanner = scanner

    def consume(self):
        return self.scanner.pop()

    def throw(self, rule, trailer = ""):
        raise ValueError("Unexpected token while parsing the '" + rule + "' rule: '" +
                str(scanner.get()) + " on line " + str(self.scanner.line) +
                "'." + trailer)

    def consume_keyword(self, rule):
        if self.scanner.next() != Token.Type.Keyword:
            self.throw(rule, " Expected a keyword.")
        return self.consume()

    def consume_identifier(self, rule):
        if self.scanner.next() != Token.Type.Identifier:
            self.throw(rule, " Expected an identifier.")
        return self.consume()

    def consume_string(self, rule):
        if self.scanner.next() != Token.Type.String:
            self.throw(rule, " Expected a string.")
        tok = self.consume()
        assert(tok.value[0] == "\"" and tok.value[-1] == "\"")
        tok.value = tok.value[1:-1]
        return tok

    def consume_number(self, rule):
        if self.scanner.next() != Token.Type.Number:
            self.throw(rule, " Expected a number.")
        return self.consume()

    def consume_semi(self, rule):
        if self.scanner.next() != Token.Type.Semi:
            self.throw(rule, " Expected ';'.")
        return self.consume()

    def consume_equals(self, rule):
        if self.scanner.next() != Token.Type.Equals:
            self.throw(rule, " Expected '='.")
        return self.consume()

    def consume_scope_open(self, rule):
        if self.scanner.next() != Token.Type.ScopeOpen:
            self.throw(rule, " Expected '{'.")
        return self.consume()

    def consume_scope_close(self, rule):
        if self.scanner.next() != Token.Type.ScopeClose:
            self.throw(rule, " Expected '}'.")
        return self.consume()
