import ast, scanner, sys
import utils

from scanner import Token
from utils import indent_from_scope, log

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

    s = scanner.Scanner(path)
    if s.reached_eof():
        raise ValueError("Nothing to parse!")

    ctx = scanner.Context(s)
    file_ast = file(ctx)
    assert(ctx.scanner.reached_eof())
    return file_ast

# Grammar:
#  <input>         ::= <statement> [ <statement> ] EOF
def file(ctx):
    if ctx.scanner.reached_eof():
        raise ValueError("Reached EoF while parsing the 'file' rule")

    file = ast.File(ctx.scanner.filename)
    while not ctx.scanner.reached_eof():
        statement(ctx, file)

    return file

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

        file = parse_file(statement_ast.path)
        log(2, "Parsed an imported file: " + file.name)
        file.make_forward_decl_names()

        file_node.imports[file.name] = file
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
    return ast.Package(name.value)

# Grammar:
#  <import>     ::= IMPORT string SEMI
def imports(ctx):
    fname = ctx.consume_string(imports.__name__)
    ctx.consume_semi(imports.__name__)
    return ast.Import(fname.value)

# Grammar:
#  <option>     ::= OPTION identifier EQUALS string SEMI
def option(ctx):
    name = ctx.consume_identifier(option.__name__)
    ctx.consume_equals(option.__name__)
    value = ctx.consume_string(option.__name__)
    ctx.consume_semi(option.__name__)
    return ast.Option(name.value, value.value)

# Grammar:
#  <message>     ::= SCOPE_OPEN decl_list SCOPE_CLOSE
def message(ctx, parent, scope):
    fq_name = ctx.consume_identifier(message.__name__).value
    if scope:
        fq_name = scope + fq_name

    msg = ast.Message(fq_name, parent)
    ctx.consume_scope_open(message.__name__)

    parent.messages[msg.name()] = msg
    log(2, indent_from_scope(fq_name) + "Parsed a 'message' : " + msg.fq_name)

    decl_list(ctx, msg, fq_name + ".")
    ctx.consume_scope_close(message.__name__)
    return msg

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
        ctx.consume_equals(decl.__name__)
        fid = ctx.consume_number(decl.__name__)

        field_ast = ast.Field(fname.value,
                              int(fid.value),
                              ftype, ftype,
                              spec)
        field_ast.is_builtin = True
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
            resolved_type = ast.find_type(parent, ftype)
            if not resolved_type:
                sys.exit("Failed to resolve message type: \"" + ftype +
                    "\" on line " + str(ctx.scanner.line) + "\n\n\n" +
                    ast.find_top_parent(parent).as_string())
            assert(resolved_type.name() == ftype)
            resolved_type_name = resolved_type.fq_name
            forward_decl_name = ftype
        else:
            resolved_type = ast.find_top_parent(parent).resolve_type(ftype)
            if not resolved_type:
                sys.exit("Failed to resolve an FQ message type: \"" + ftype +
                    "\" on line " + str(ctx.scanner.line) + "\n\n\n" +
                    ast.find_top_parent(parent).as_string())
            assert(resolved_type.fq_name == ftype)
            resolved_type_name = ftype
            forward_decl_name = resolved_type.forward_decl_name

        # 2. take the field name
        fname = ctx.consume_identifier(decl.__name__)

        # 3. take the rest
        ctx.consume_equals(decl.__name__)
        fid = ctx.consume_number(decl.__name__)

        field_ast = ast.Field(fname.value,
                              int(fid.value),
                              resolved_type_name,
                              ftype,
                              spec)
        if type(resolved_type) is ast.Enum:
            field_ast.is_enum = True
        else:
            field_ast.forward_decl_type = forward_decl_name
    elif ctx.scanner.next() == Token.Type.Keyword and ctx.scanner.get().value == "enum":
        ctx.consume_keyword(decl.__name__)
        enum(ctx, parent, scope)
        return
    else:
        ctx.throw(decl.__name__)

    ctx.consume_semi(decl.__name__)

    parent.fields[int(fid.value)] = field_ast
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
    enum_ast = ast.Enum(fq_name)

    parent.enums[name] = enum_ast
    log(2, indent_from_scope(fq_name) + "Parsed an 'enum' statement: " + fq_name)

    evalue_list(ctx, enum_ast, scope)
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
# the main() part
#
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-I', '--include', help='Include (search) directory',
                    action='append')
parser.add_argument('--cpp_out', help='Output directory')
parser.add_argument('filename', metavar='filename',
                    help='Input file name')

parser.add_argument("-v", "--verbosity", help="increase output verbosity",
                    action="count", default=0)
parser.add_argument("--fqdn", help="print fully-qualified message and enum types in AST",
                    action='store_true')
parser.add_argument("--with-imports", help="print AST for imported files",
                    action='store_true')

args = parser.parse_args()
utils.args = args
ast.args = args

if not args.filename:
    sys.exit("Missing the <filename> argument.")
if not args.cpp_out:
    sys.exit("Missing the --cpp_out argument.")

file = parse_file(args.filename)
log(1, file.as_string())

file.generate()
