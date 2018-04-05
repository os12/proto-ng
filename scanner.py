from enum import Enum
from utils import log

import sys

class Token:
    class Type(Enum):
        EoF = 1
        Whitespace = 2
        DataType = 3
        Specifier = 4
        Identifier = 5

        Keyword = 7
        Number = 8
        Boolean = 17

        Equals = 9
        Semi = 10
        String = 11
        ParenOpen = 12
        ParenClose = 13
        ScopeOpen = 14
        ScopeClose = 15
        Dot = 16
        SquareOpen = 18
        SquareClose = 19
        Coma = 20

    def __init__(self, type):
        self.type = type
        self.value = ""
        self.line_num = self.pos = 0

    def __str__(self):
        rv = "Token(" + str(self.type)
        if self.value:
            rv += ', "' + self.value + '"'
        return rv + ")"

class Scanner:
    def __init__(self, file_path, flags = 0):
        import collections, re

        self.__reached_eof = False
        self.__queue = []
        self.file_path = file_path
        self.line_num = 0
        self.non_terminals = [
            Token.Type.Identifier, Token.Type.Specifier,
            Token.Type.Keyword, Token.Type.DataType, Token.Type.Number, Token.Type.String]

        self.__keywords = {'package', 'syntax', 'import', 'option',
                           'message', 'enum', 'extend',
                           'reserved', 'extensions'}
        tokens = [
            ("Whitespace", r'[ \t\r\n]+|//.*$|/\*.*\*/'),

            ("DataType", r'int32|uint32|int64|uint64|double|float|string|bool|bytes'),
            ("Specifier", r'repeated|optional|required'),

            ("Equals", r'='),
            ("Number", r'-?\d+'),
            ("ParenOpen", r'\('),
            ("ParenClose", r'\)'),
            ("SquareOpen", r'\['),
            ("SquareClose", r'\]'),
            ("ScopeOpen", r'{'),
            ("ScopeClose", r'}'),
            ("Semi", r';'),
            ("Dot", r'\.'),
            ("Coma", r','),

            ("Boolean", r'true|false'),
            ("Identifier", r'[A-Za-z][A-Za-z0-9_]*'),
            ("String", r'"[^"]*"|\'[^\']*\''),
        ]

        tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in tokens)
        self.__run_regex = re.compile(tok_regex).match

        log(1, "Opening file: " + file_path)
        self.__file = open(file_path, "r")

    def get(self, idx = 0):
        while idx >= len(self.__queue):
            # Consume the current logical block of input. Usually it's just one line, yet
            # it gets longer when multi-line comments are present.
            for token in self.__scan(lambda self : self.__file.readline()):
                log(3, "[scanner] got token: " + str(token))
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

    def __scan(self, read_fn):
        pos = 0
        input = ""

        while True:
            line = read_fn(self)
            if not line:
                if pos != len(input):
                    # We've read the entire file yet failing to get the next token. Die.
                    raise ValueError('Unexpected character %r in %r on line %d' %
                        (input[pos], self.file_path, self.line_num))
                self.__reached_eof = True
                yield Token(Token.Type.EoF)
                if self.__reached_eof: return
            log(3, "[scanner] read line: \"" + line[0:-1] + "\"")

            # Exclude the trailing \n as "re" does not work properly in MULTILINE mode.
            input += line[0:-1]
            self.line_num += 1

            match = self.__run_regex(input, pos)
            if not match: continue

            while match:
                ttype = Token.Type[match.lastgroup]
                if ttype != Token.Type.Whitespace:
                    val = match.group(match.lastgroup)
                    if ttype == Token.Type.Identifier and val in self.__keywords:
                        ttype = Token.Type.Keyword
                    tok = Token(ttype)
                    tok.line = self.line_num
                    tok.pos = match.start()
                    if ttype in self.non_terminals:
                        tok.value = val
                    yield tok
                pos = match.end()
                match = self.__run_regex(input, pos)
            if pos != len(input):
                # Continue pulling data in as we may be dealing with a mutli-line thing.
                continue

            # We are done with this logical block. Generally it's just one line, except for
            # multi-line comments.
            break

class Context:
    def __init__(self, scanner):
        self.scanner = scanner

    def consume(self):
        return self.scanner.pop()

    def throw(self, rule, trailer = ""):
        sys.exit("Unexpected token while parsing the '" + rule.__name__ + "' rule: '" +
                 str(self.scanner.get()) + " " + self.scanner.file_path + " on line " + \
                    str(self.scanner.line_num) + "'." + trailer)

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
        assert(tok.value[0] == "\"" or tok.value[0] == "'")
        tok.value = tok.value[1:-1]
        return tok

    def consume_number(self, rule):
        if self.scanner.next() != Token.Type.Number:
            self.throw(rule, " Expected a number.")
        return self.consume()

    def consume_boolean(self, rule):
        if self.scanner.next() != Token.Type.Boolean:
            self.throw(rule, " Expected a boolean value.")
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

    def consume_square_close(self, rule):
        if self.scanner.next() != Token.Type.SquareClose:
            self.throw(rule, " Expected ']'.")
        return self.consume()
