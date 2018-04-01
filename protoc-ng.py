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
        self.messages = {}
        self.enums = {}
        self.name = fname
        self.namespace = ""
        self.parent = None

    def as_string(self):
        assert(self.namespace)

        s = ""

        global args
        if args.with_imports:
            for file_name, ast in self.imports.items():
                s += ast.as_string()

        s += "\nAST for " + self.name + ", namespace=" + self.namespace + "\n\n"

        # Enums
        for name, enum in self.enums.items():
            s += enum.as_string(self.namespace) + "\n"

        # Messages
        for name, msg in self.messages.items():
            s += msg.as_string(self.namespace)

        return s

    # Looks for the given fully-qualified field type 'ftype' in a top->down fashion by
    # resolving every segment of the type's string.
    def resolve_type(self, fq_type):
        assert(fq_type)
        assert(self.namespace)

        if fq_type[0:len(self.namespace)] == self.namespace:
            fq_type = fq_type[len(self.namespace):]
            parts = fq_type.split('.')
            front = parts.pop(0) # the remaining "."
            assert(not front)
            front = parts.pop(0)
            assert(front)

            if front in self.enums:
                if len(parts) == 0:
                    return ast.enums[front]
                return None

            if front in self.messages:
                msg = self.messages[front]
                if len(parts) == 0:
                    return msg
                return msg.resolve_type(".".join(parts))
        else:
            for file_name, file_ast in self.imports.items():
                # TODO: this step should check the type prefix instead of searching
                #       blindly, but that's tricky due to variable number of segments...
                t = file_ast.resolve_type(fq_type)
                if t:
                    return t
        return None

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
    def __init__(self, fq_name, parent):
        self.parent = parent        # the parent Message or None
        self.fq_name = fq_name
        self.fields = {}
        self.enums = {}
        self.messages = {}

    def name(self):
        assert(self.fq_name)
        return self.fq_name.split('.')[-1]

    def as_string(self, namespace):
        assert(namespace)
        assert(namespace[-1] != '.')
        assert(namespace + "." + self.name() == self.fq_name)

        s = indent_from_scope(namespace) + "Message: "
        global args
        if args.fqdn:
            s += self.fq_name  + "\n"
        else:
            s += self.name() + "\n"

        # Fields
        for id, field in self.fields.items():
            s += field.as_string(namespace + "." + self.name()) + "\n"

        # Enums
        for name, enum in self.enums.items():
            s += enum.as_string(namespace + "." + self.name()) + "\n"

        # Sub-messages
        for name, sub_msg in self.messages.items():
            s += sub_msg.as_string(namespace + "." + self.name())

        return s

    # Looks for the given fully-qualified field type 'ftype' in a top->down fashion by
    # resolving every segment of the type's string.
    def resolve_type(self, fq_type):
        assert(fq_type)

        parts = fq_type.split('.')
        assert(len(parts) > 0)
        front = parts.pop(0)
        assert(front)

        if front in ast.enums:
            if len(parts) == 0:
                return ast.enums[ftype]
            return None

        if front in ast.messages:
            msg = ast.messages[ftype]
            if len(parts) == 0:
                return msg
            return msg.resolve_type(".".join(parts))

        return None

class EnumNode(Node):
    def __init__(self, fq_name):
        self.fq_name = fq_name
        self.values = {}

    def name(self):
        assert(self.fq_name)
        return self.fq_name.split('.')[-1]

    def as_string(self, namespace):
        assert(namespace)
        assert(namespace[-1] != '.')
        assert(namespace + "." + self.name() == self.fq_name)

        s = indent_from_scope(namespace) + "Enum: "

        global args
        if args.fqdn:
            s += self.fq_name
        else:
            s += self.name()

        return s + "(" + ", ".join(self.values.values()) + ")"

class FieldNode(Node):
    def __init__(self, name, id, ftype, is_builtin, specifier):
        self.name = name
        self.id = id
        self.ftype = ftype
        self.is_builtin = is_builtin
        self.is_repeated = False
        if specifier and specifier.value == "repeated":
            self.is_repeated = True

    def as_string(self, namespace):
        assert(namespace)
        assert(namespace[-1] != '.')

        return indent_from_scope(namespace) + \
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
        for inc in args.include:
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
    if args.verbosity >= verbosity:
        print(msg)

# Looks for the given field type 'ftype' in the ever-widening message scopes (from inside
# out).
#
# This function finds anything that can be used as a field:
#   - message
#   - enum
def find_type(ast, ftype):
	if not ast:
		return None

	if ftype in ast.messages:
		return ast.messages[ftype]
	if ftype in ast.enums:
		return ast.enums[ftype]

	return find_type(ast.parent, ftype)

def find_top_parent(ast):
    assert(ast)
    if not ast.parent:
        return ast
    return find_top_parent(ast.parent)

def indent(level):
    return "    " * level

def indent_from_scope(fq_name):
    if not fq_name:
        return ""
    level = fq_name.count('.')
    return indent(level)

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
        message(ctx, file_node, file_node.namespace + ".")
    elif keyword.type == Token.Type.Keyword and keyword.value == "enum":
        enum(ctx, file_node, file_node.namespace + ".")
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
def message(ctx, parent, scope):
    fq_name = ctx.consume_identifier(message.__name__).value
    if scope:
        fq_name = scope + fq_name

    ast = MessageNode(fq_name, parent)
    ctx.consume_scope_open(message.__name__)

    parent.messages[ast.name()] = ast
    log(2, indent_from_scope(fq_name) + "Parsed a 'message' : " + ast.fq_name)

    decl_list(ctx, ast, fq_name + ".")
    ctx.consume_scope_close(message.__name__)
    return ast

# Grammar:
#  <decl_list>     ::= ( <decl> | <message> ) [ <decl> | <message> ]
def decl_list(ctx, parent, scope):
    while ctx.scanner.next() != Token.Type.ScopeClose:
        # Process sub-messages.
        if ctx.scanner.next() == Token.Type.Keyword and ctx.scanner.get().value == "message":
            ctx.consume_keyword(decl_list.__name__)
            message(ctx, parent, scope)
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
        ftype = ctx.consume().value
        fname = ctx.consume_identifier(decl.__name__)
        is_builtin = True
    elif ctx.scanner.next() == Token.Type.Identifier:
        # 1a. take the type name, possible fully qualified.
        ftype = ctx.consume_identifier(decl.__name__).value
        while ctx.scanner.next() == Token.Type.Dot:
            ctx.consume()
            trailer = ctx.consume_identifier(decl.__name__)
            ftype += "." + trailer.value

        # 1b. verify the type:
        #   - unqualified reference is expanded into a fully-qualified name.
        if ftype.count(".") == 0:
            resolved_type = find_type(parent, ftype)
            if not resolved_type:
                sys.exit("Failed to resolve message type: \"" + ftype +
                    "\" on line " + str(ctx.scanner.line) + "\n\n\n" +
                    find_top_parent(parent).as_string())
            assert(resolved_type.name() == ftype)
            ftype = resolved_type.fq_name
        else:
            resolved_type = find_top_parent(parent).resolve_type(ftype)
            if not resolved_type:
                sys.exit("Failed to resolve an FQ message type: \"" + ftype +
                    "\" on line " + str(ctx.scanner.line) + "\n\n\n" +
                    find_top_parent(parent).as_string())
            assert(resolved_type.fq_name == ftype)

        # 2. take the field name
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
                                              ftype,
                                              is_builtin,
                                              spec)
    log(2, indent_from_scope(scope) + "Parsed a 'field' declaration: " + fname.value)

# Grammar:
#  <decl>     ::= ENUM identifier SCOPE_OPEN <evalue-list> SCOPE_CLOSE
def enum(ctx, parent, scope):
    name = ctx.consume_identifier(enum.__name__).value
    fq_name = name
    ctx.consume_scope_open(enum.__name__)
    if scope:
        assert(scope[-1] == '.')
        fq_name = scope + name
    ast = EnumNode(fq_name)

    parent.enums[name] = ast
    log(2, indent_from_scope(fq_name) + "Parsed an 'enum' statement: " + fq_name)

    evalue_list(ctx, ast, scope)
    ctx.consume_scope_close(enum.__name__)

# Grammar:
#  <evalue_list>     ::= <evalue> [ <evalue> ]
def evalue_list(ctx, parent, scope):
    while ctx.scanner.next() != Token.Type.ScopeClose:
        evalue(ctx, parent, scope + ".")

# Grammar:
#  <evalue>     ::= identifier EQALS number SEMI
def evalue(ctx, enum, scope):
    fname = ctx.consume_identifier(evalue.__name__)
    ctx.consume_equals(evalue.__name__)
    eid = ctx.consume_number(evalue.__name__)
    ctx.consume_semi(evalue.__name__)
    enum.values[int(eid.value)] = fname.value
    log(2, indent_from_scope(scope) + "Parsed an enum constant: " + fname.value)

#
# Semantic part.
#
def verify(file):
    log(1, file.as_string())
    log(1, "Good!")

#
# the main() part
#
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-I', '--include', help='Include (search) directory',
                    action='append')
parser.add_argument('filename', metavar='filename',
                    help='Input file name')

parser.add_argument("-v", "--verbosity", help="increase output verbosity",
                    action="count", default=0)
parser.add_argument("--fqdn", help="print fully-qualified message and enum types in AST",
                    action='store_true')
parser.add_argument("--with-imports", help="print AST for imported files",
                    action='store_true')

args = parser.parse_args()

ast = parse_file(sys.argv[1])
verify(ast)
