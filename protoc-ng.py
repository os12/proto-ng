import sys
from enum import Enum

if len(sys.argv) < 2:
    sys.exit("Need a filename!")

class Token:
    class Type(Enum):
        EoF = 1
        Whitespace = 2
        DataType = 3
        Specifier = 4
        Identifier = 5

        BuiltinType = 6
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

        self.__file = open(fname, "r")
        self.__queue = []
        self.line = 0
        self.non_terminals = [
            Token.Type.Identifier, Token.Type.Specifier,
            Token.Type.Keyword, Token.Type.DataType, Token.Type.Number, Token.Type.String]

        self.__keywords = {'package', 'import', 'option', 'message'}
        tokens = [
            ("Whitespace", r'[ \t\r\n]+|//.*$'),

            ("DataType", r'int32|int64|string|bool'),
            ("Specifier", r'repeated|optional|enum'),

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
                # print("Got token: " + str(token))
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

    def consume_keyword(self, rule):
        if self.scanner.next() != Token.Type.Keyword:
            raise ValueError("Unexpected token while parsing the '" + rule + "' rule: '" +
                str(scanner.get()) + "'. Expected a keyword.")
        return self.consume()

    def consume_identifier(self, rule):
        if self.scanner.next() != Token.Type.Identifier:
            raise ValueError("Unexpected token while parsing the '" + rule + "' rule: '" +
                str(scanner.get()) + "'. Expected an identifier.")
        return self.consume()

    def consume_string(self, rule):
        if self.scanner.next() != Token.Type.String:
            raise ValueError("Unexpected token while parsing the '" + rule + "' rule: '" +
                str(scanner.get()) + "'. Expected a string.")
        return self.consume()

    def consume_number(self, rule):
        if self.scanner.next() != Token.Type.Number:
            raise ValueError("Unexpected token while parsing the '" + rule + "' rule: '" +
                str(scanner.get()) + "'. Expected a number.")
        return self.consume()

    def consume_semi(self, rule):
        if self.scanner.next() != Token.Type.Semi:
            raise ValueError("Unexpected token while parsing the '" + rule + "' rule: '" +
                str(ctx.scanner.get()) + "'. Expected ';'.")
        return self.consume()

    def consume_equals(self, rule):
        if self.scanner.next() != Token.Type.Equals:
            raise ValueError("Unexpected token while parsing the '" + rule + "' rule: '" +
                str(ctx.scanner.get()) + "'. Expected '='.")
        return self.consume()

    def consume_scope_open(self, rule):
        if self.scanner.next() != Token.Type.ScopeOpen:
            raise ValueError("Unexpected token while parsing the '" + rule + "' rule: '" +
                str(ctx.scanner.get()) + "'. Expected '{'.")
        return self.consume()

    def consume_scope_close(self, rule):
        if self.scanner.next() != Token.Type.ScopeClose:
            raise ValueError("Unexpected token while parsing the '" + rule + "' rule: '" +
                str(ctx.scanner.get()) + "'. Expected '}'.")
        return self.consume()

#
# AST nodes
#

class Node:
    def verify(self):
        return "Good!"

class FileNode(Node):
    def __init__(self):
        self.statements = []
        self.imports = []
        self.options = []
        self.messages = []
        self.name = ""

class PackageNode(Node):
    def __init__(self, name):
        self.name = name

class ImportNode(Node):
    def __init__(self, path):
        self.path = path

class OptionNode(Node):
    def __init__(self, name, value):
        self.name = name
        self.value = value

class MessageNode(Node):
    def __init__(self, fq_name):
        self.fq_name = fq_name
        self.fields = {}

class FieldNode(Node):
    def __init__(self, name, id, ftype, is_builtin):
        self.name = name
        self.id = id
        self.ftype = ftype
        self.is_builtin = is_builtin

#
# Utils
#
def log(msg):
    print(msg)

# Grammar:
#  <input>         ::= <statement> [ <statement> ] EOF
def file(ctx):
    if ctx.scanner.reached_eof():
        raise ValueError("Reached EoF while parsing the 'file' rule")

    ast = FileNode()
    while not ctx.scanner.reached_eof():
        statement(ctx, ast)

    return ast

# Grammar:
#  <statement>     ::= <package> | <import> | <option> | <message>
def statement(ctx, file_node):
    keyword = ctx.consume_keyword(statement.__name__)

    if keyword.type == Token.Type.Keyword and keyword.value == "package":
        file_node.name = package(ctx).name
        log("Parsed a 'package' statement")
    elif keyword.type == Token.Type.Keyword and keyword.value == "import":
        file_node.imports.append(imports(ctx))
        log("Parsed an 'import' statement")
    elif keyword.type == Token.Type.Keyword and keyword.value == "option":
        file_node.options.append(option(ctx))
        log("Parsed an 'option' statement: " + file_node.options[-1].name)
    elif keyword.type == Token.Type.Keyword and keyword.value == "message":
        file_node.messages.append(message(ctx, file_node.name))
        log("Parsed a 'message' : " + file_node.messages[-1].fq_name)
    else:
        raise ValueError("Unexpected keyword while parsing the 'statement' rule: '" +
                keyword.value + "'")

# Grammar:
#  <package>     ::= PACKAGE identifier SEMI
def package(ctx):
    name = ctx.consume_identifier(package.__name__)
    ctx.consume_semi(package.__name__)
    return PackageNode(name.value)

# Grammar:
#  <import>     ::= IMPORT string SEMI
def imports(ctx):
    fname = ctx.consume_string(imports.__name__)
    ctx.consume_semi(imports.__name__)
    return ImportNode(fname.value)

# Grammar:
#  <option>     ::= OPTION identifier EQUALS string SEMI
def option(ctx):
    name = ctx.consume_identifier(option.__name__)
    ctx.consume_equals(option.__name__)
    value = ctx.consume_string(option.__name__)
    ctx.consume_semi(option.__name__)
    return OptionNode(name.value, value.value)

# Grammar:
#  <message>     ::= SCOPE_OPEN decl_list SCOPE_CLOSE
def message(ctx, scope):
    fq_name = ctx.consume_identifier(message.__name__).value
    if scope:
        fq_name = scope + "." + fq_name

    ast = MessageNode(fq_name)
    ctx.consume_scope_open(message.__name__)
    decl_list(ctx, ast, fq_name)
    ctx.consume_scope_close(message.__name__)
    return ast

# Grammar:
#  <decl_list>     ::= <decl> | <message> [ <decl> | <message> ]
def decl_list(ctx, parent, scope):
    while ctx.scanner.next() != Token.Type.ScopeClose:
        # Process sub-messages.
        if ctx.scanner.next() == Token.Type.Keyword and ctx.get().value == "message":
            ctx.consume_keyword(decl_list.__name__)
            parent.messages.append(message(ctx, scope))
            continue

        # This must be a normal field declaration.
        decl(ctx, parent, scope)

# Grammar:
#  <decl>     ::= [ SPECIFIER ] BUILTIN-TYPE identifier EQUALS number
#                       [ OPEN_SQUARE DEFAULT EQUALS builtin-value CLOSE_SQUARE ]
#                       SEMI
#               | identifier identifier EQALS number SEMI
def decl(ctx, parent, scope):
    spec = None
    if ctx.scanner.next() == Token.Type.Specifier:
        spec = ctx.consume()

    if ctx.scanner.next() == Token.Type.BuiltinType:
        ftype = ctx.consume()
        fname = ctx.consume_identifier(decl.__name__)
        is_builtin = True
    elif ctx.scanner.next() == Token.Type.Identifier:
        ftype = ctx.consume_identifier(decl.__name__)
        fname = ctx.consume_identifier(decl.__name__)
        is_builtin = False
    else:
        raise ValueError("Unexpected token while parsing the '" + decl.__name__ +
            "' rule: '" + str(ctx.scanner.get()) + "'.")

    ctx.consume_equals(decl.__name__)
    fid = ctx.consume_number(decl.__name__)
    ctx.consume_semi(decl.__name__)
    parent.fields[int(fid.value)] = FieldNode(fname.value,
                                              int(fid.value),
                                              ftype.value,
                                              is_builtin)



#
# the main() part
#
scanner = Scanner(sys.argv[1])
if scanner.reached_eof():
    raise ValueError("Nothing to parse!")

ctx = Context(scanner)
ast = file(ctx)
assert(ctx.scanner.reached_eof())

print(str(ast.verify()))
