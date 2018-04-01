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

            ("DataType", r'int32|int64|string|bool'),
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

#
# AST nodes
#

class Node:
    def verify(self):
        return "Good!"

class FileNode(Node):
    def __init__(self, fname):
        self.statements = []
        self.imports = {}
        self.options = []
        self.messages = []
        self.enums = {}
        self.name = fname
        self.namespace = ""

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
        self.enums = {}
        self.messages = []

    def as_string(self, prefix = ""):
        s = prefix + "Message: " + self.fq_name + "\n"

        # Fields
        for id, field in self.fields.items():
            s += field.as_string(prefix + "    ") + "\n"

        # Sub-messages
        for sub_msg in self.messages:
            s += sub_msg.as_string(prefix + "    ")

        return s

class EnumNode(Node):
    def __init__(self, fq_name):
        self.fq_name = fq_name
        self.values = {}

class FieldNode(Node):
    def __init__(self, name, id, ftype, is_builtin, specifier):
        self.name = name
        self.id = id
        self.ftype = ftype
        self.is_builtin = is_builtin
        self.is_repeated = False
        if specifier and specifier.value == "repeated":
            self.is_repeated = True

    def as_string(self, prefix = ""):
        return prefix + \
            "[" + str(self.id) + "] " + self.name + " : " + self.ftype +\
                (" (repeated)" if self.is_repeated else "")

#
# The main parser: builds AST for a single file.
#
def parse_file(path):
    import os.path

    # First fine the file. Let's start with the given path and then search
    # the 'includes'.
    if not os.path.isfile(path):
        for inc in __args.include:
            next_path = inc
            assert(next_path)
            if next_path[-1] != '/':
                next_path += '/'
            next_path += path
            if os.path.isfile(next_path):
                path = next_path
                break

    scanner = Scanner(path)
    if scanner.reached_eof():
        raise ValueError("Nothing to parse!")

    ctx = Context(scanner)
    ast = file(ctx)
    assert(ctx.scanner.reached_eof())
    return ast

#
# Utils
#
def log(verbosity, msg):
    if __args.verbosity >= verbosity:
        print(msg)

# Grammar:
#  <input>         ::= <statement> [ <statement> ] EOF
def file(ctx):
    if ctx.scanner.reached_eof():
        raise ValueError("Reached EoF while parsing the 'file' rule")

    ast = FileNode(ctx.scanner.filename)
    while not ctx.scanner.reached_eof():
        statement(ctx, ast)

    return ast

# Grammar:
#  <statement>     ::= <package> | <import> | <option> | <message> | <enum>
def statement(ctx, file_node):
    keyword = ctx.consume_keyword(statement.__name__)

    if keyword.type == Token.Type.Keyword and keyword.value == "package":
        file_node.namespace = package(ctx).name
        log(2, "Parsed a 'package' statement: " + file_node.namespace)
    elif keyword.type == Token.Type.Keyword and keyword.value == "import":
        statement_ast = imports(ctx)
        log(2, "Parsed an 'import' statement: " + statement_ast.path)

        ast = parse_file(statement_ast.path)
        log(2, "Parsed an imported file: " + ast.name)

        file_node.imports[ast.name] = ast
    elif keyword.type == Token.Type.Keyword and keyword.value == "option":
        file_node.options.append(option(ctx))
        log(2, "Parsed an 'option' statement: " + file_node.options[-1].name)
    elif keyword.type == Token.Type.Keyword and keyword.value == "message":
        file_node.messages.append(message(ctx, file_node.namespace))
        log(2, "Parsed a 'message' : " + file_node.messages[-1].fq_name)
    elif keyword.type == Token.Type.Keyword and keyword.value == "enum":
        enum(ctx, file_node)
    else:
        raise ValueError("Unexpected keyword while parsing the 'statement' rule: '" +
                keyword.value + "'")

# Grammar:
#  <package>     ::= PACKAGE [ DOT identifier ] identifier SEMI
def package(ctx):
    name = ctx.consume_identifier(package.__name__)
    while ctx.scanner.next() == Token.Type.Dot:
        ctx.consume()
        trailer = ctx.consume_identifier(package.__name__)
        name.value += "." + trailer.value
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
#  <decl_list>     ::= ( <decl> | <message> ) [ <decl> | <message> ]
def decl_list(ctx, parent, scope):
    while ctx.scanner.next() != Token.Type.ScopeClose:
        # Process sub-messages.
        if ctx.scanner.next() == Token.Type.Keyword and ctx.scanner.get().value == "message":
            ctx.consume_keyword(decl_list.__name__)
            parent.messages.append(message(ctx, scope))
            continue

        # This must be a normal field declaration.
        decl(ctx, parent, scope)

# Grammar:
#  <decl>     ::= [ SPECIFIER ] BUILTIN-TYPE identifier EQUALS number
#                       [ OPEN_SQUARE DEFAULT EQUALS builtin-value CLOSE_SQUARE ]
#                       SEMI
#               | identifier [ DOT identifier ] identifier EQALS number SEMI
#               | <enum>
def decl(ctx, parent, scope):
    spec = None
    if ctx.scanner.next() == Token.Type.Specifier:
        spec = ctx.consume()

    if ctx.scanner.next() == Token.Type.DataType:
        ftype = ctx.consume()
        fname = ctx.consume_identifier(decl.__name__)
        is_builtin = True
    elif ctx.scanner.next() == Token.Type.Identifier:
        # 1. handle the type name, possible fully qualified.
        ftype = ctx.consume_identifier(decl.__name__)
        while ctx.scanner.next() == Token.Type.Dot:
            ctx.consume()
            trailer = ctx.consume_identifier(decl.__name__)
            ftype.value += "." + trailer.value

        # 2. handle the filed name
        fname = ctx.consume_identifier(decl.__name__)
        is_builtin = False
    elif ctx.scanner.next() == Token.Type.Keyword and ctx.scanner.get().value == "enum":
        ctx.consume_keyword(decl.__name__)
        enum(ctx, parent, scope)
        return
    else:
        ctx.throw(decl.__name__)

    ctx.consume_equals(decl.__name__)
    fid = ctx.consume_number(decl.__name__)
    ctx.consume_semi(decl.__name__)
    parent.fields[int(fid.value)] = FieldNode(fname.value,
                                              int(fid.value),
                                              ftype.value,
                                              is_builtin,
                                              spec)
    log(2, "Parsed a 'field' declaration: " + fname.value)

# Grammar:
#  <decl>     ::= ENUM identifier SCOPE_OPEN <evalue-list> SCOPE_CLOSE
def enum(ctx, parent, scope = ""):
    ename = ctx.consume_identifier(enum.__name__)
    ctx.consume_scope_open(enum.__name__)
    ast = EnumNode(scope + ename.value)
    parent.enums[ename.value] = ast
    evalue_list(ctx, ast)
    ctx.consume_scope_close(enum.__name__)
    log(2, "Parsed an 'enum' statement: " + parent.enums[ename.value].fq_name)

# Grammar:
#  <evalue_list>     ::= <evalue> [ <evalue> ]
def evalue_list(ctx, parent):
    while ctx.scanner.next() != Token.Type.ScopeClose:
        evalue(ctx, parent)

# Grammar:
#  <evalue>     ::= identifier EQALS number SEMI
def evalue(ctx, enum):
    fname = ctx.consume_identifier(evalue.__name__)
    ctx.consume_equals(evalue.__name__)
    eid = ctx.consume_number(evalue.__name__)
    ctx.consume_semi(evalue.__name__)
    enum.values[int(eid.value)] = fname.value

#
# Semantic part.
#
def verify(file):
    for msg in file.messages:
        log(1, msg.as_string())
    log(1, "Good!")

#
# the main() part
#
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-I', '--include', help='Include (search) directory',
                    action='append')
parser.add_argument("-v", "--verbosity", help="increase output verbosity",
                    action="count", default=0)
parser.add_argument('filename', metavar='filename',
                    help='Input file name')
__args = parser.parse_args()

ast = parse_file(sys.argv[1])
verify(ast)
