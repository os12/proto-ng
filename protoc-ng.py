#!/usr/bin/python3

import nodes, scanner, sys
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
    file_ast.set_cpp_type_names()
    return file_ast

# Grammar:
#  <input>         ::= <statement> [ <statement> ] EOF
def file(ctx):
    if ctx.scanner.reached_eof():
        raise ValueError("Reached EoF while parsing the 'file' rule")

    file = nodes.File(ctx.scanner.file_path)
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
        log(2, "Parsed an imported file: " + file.filename())

        file_node.imports[file.path] = file
    elif keyword.type == Token.Type.Keyword and keyword.value == "option":
        file_node.options.append(option(ctx))
        log(2, "Parsed an 'option' statement: " + file_node.options[-1].name)
    elif keyword.type == Token.Type.Keyword and keyword.value == "message":
        message(ctx, file_node, file_node.namespace + ".")
    elif keyword.type == Token.Type.Keyword and keyword.value == "enum":
        enum_decl(ctx, file_node, file_node.namespace + ".")
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
    return nodes.Package(name.value)

# Grammar:
#  <import>     ::= IMPORT string SEMI
def imports(ctx):
    fname = ctx.consume_string(imports.__name__)
    ctx.consume_semi(imports.__name__)
    return nodes.Import(fname.value)

# Grammar:
#  <option>     ::= OPTION identifier EQUALS string SEMI
def option(ctx):
    name = ctx.consume_identifier(option.__name__)
    ctx.consume_equals(option.__name__)
    value = ctx.consume_string(option.__name__)
    ctx.consume_semi(option.__name__)
    return nodes.Option(name.value, value.value)

# Grammar:
#  <message>     ::= SCOPE_OPEN decl_list SCOPE_CLOSE
def message(ctx, parent, scope):
    fq_name = ctx.consume_identifier(message.__name__).value
    if scope:
        fq_name = scope + fq_name

    msg = nodes.Message(fq_name, parent)
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
#  <decl>     ::= <builtin-field-decl> | <message-field-decl> | <enum-decl>
def decl(ctx, parent, scope):
    spec = None
    if ctx.scanner.next() == Token.Type.Specifier:
        spec = ctx.consume()

    if ctx.scanner.next() == Token.Type.DataType:
        builtin_field_decl(ctx, parent, spec, scope)
    elif ctx.scanner.next() == Token.Type.Identifier:
        message_field_decl(ctx, parent, spec, scope)
    elif ctx.scanner.next() == Token.Type.Keyword and ctx.scanner.get().value == "enum":
        ctx.consume_keyword(decl.__name__)
        enum_decl(ctx, parent, scope)
    else:
        ctx.throw(decl.__name__)


# Grammar:
#  <builtin-field-decl> ::= [ SPECIFIER ] BUILTIN-TYPE identifier EQUALS number
#                           [ OPEN_SQUARE DEFAULT EQUALS builtin-value CLOSE_SQUARE ]
#                           SEMI

#               | identifier [ DOT identifier ] identifier EQALS number SEMI
#               | <enum>
def builtin_field_decl(ctx, parent, spec, scope):
    ftype = ctx.consume().value
    fname = ctx.consume_identifier(decl.__name__)
    ctx.consume_equals(decl.__name__)
    fid = ctx.consume_number(decl.__name__)

    field_ast = nodes.Field(fname.value,
                            int(fid.value),
                            ftype, None,
                            spec)
    field_ast.parent = parent

    ctx.consume_semi(decl.__name__)

    parent.fields[int(fid.value)] = field_ast
    log(2, indent_from_scope(scope) + "Parsed a built-in 'field' declaration: " + fname.value)


# Grammar:
#  <message-field-decl> ::= identifier [ DOT identifier ] identifier EQALS number SEMI
def message_field_decl(ctx, parent, spec, scope):
    # 1. take the type name, possible fully qualified.
    ftype = ctx.consume_identifier(decl.__name__).value
    while ctx.scanner.next() == Token.Type.Dot:
        ctx.consume()
        trailer = ctx.consume_identifier(decl.__name__)
        ftype += "." + trailer.value

    # 2. take the field name
    fname = ctx.consume_identifier(decl.__name__)

    # 3. take the rest
    ctx.consume_equals(decl.__name__)
    fid = ctx.consume_number(decl.__name__)
    ctx.consume_semi(decl.__name__)

    # 4. verify the reference
    if ftype.count(".") == 0:
        # This is a local type that's subject to the plain visibility rules.
        resolved_type = nodes.find_type(parent, ftype)
        if not resolved_type:
            sys.exit("Failed to resolve message type: \"" + ftype +
                "\" on line " + str(ctx.scanner.line) + "\n\n\n" +
                nodes.find_top_parent(parent).as_string())
        assert(resolved_type.name() == ftype)

        field_ast = nodes.Field(fname.value, int(fid.value), ftype, resolved_type, spec)
        field_ast.is_fq_ref = False
    else:
        # This is a fully-qualified type.
        resolved_type = nodes.find_top_parent(parent).resolve_type(ftype)
        if not resolved_type:
            sys.exit("Failed to resolve an FQ message type: \"" + ftype +
                "\" on line " + str(ctx.scanner.line) + "\n\n\n" +
                nodes.find_top_parent(parent).as_string())
        assert(resolved_type.fq_name == ftype)

        field_ast = nodes.Field(fname.value, int(fid.value), ftype, resolved_type, spec)
        field_ast.is_fq_ref = True

    field_ast.parent = parent
    if type(resolved_type) is nodes.Enum:
        field_ast.is_enum = True

    parent.fields[int(fid.value)] = field_ast
    log(2, indent_from_scope(scope) + "Parsed a message 'field' declaration: " + fname.value)


# Grammar:
#  <enum-decl>     ::= ENUM identifier SCOPE_OPEN <evalue-list> SCOPE_CLOSE
def enum_decl(ctx, parent, scope):
    name = ctx.consume_identifier(enum_decl.__name__).value
    fq_name = name
    ctx.consume_scope_open(enum_decl.__name__)
    if scope:
        assert(scope[-1] == '.')
        fq_name = scope + name
    enum_ast = nodes.Enum(fq_name)
    enum_ast.parent = parent

    parent.enums[name] = enum_ast
    log(2, indent_from_scope(fq_name) + "Parsed an 'enum' statement: " + fq_name)

    evalue_list(ctx, enum_ast, scope)
    ctx.consume_scope_close(enum_decl.__name__)

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

group = parser.add_argument_group('Mandatory arguments')
group.add_argument('-I', '--include', help='Include (search) directory', action='append')
group.add_argument('--cpp_out', help='Output directory')
group.add_argument('filename', metavar='filename', help='Input file name')

group = parser.add_argument_group('Code generation options')
group.add_argument('--file-extension', help='File extension for the generated C++ files. ' +
                   'Defaults to "pbng" (which yields <fname>.pbng.h).',
                   default="pbng")
group.add_argument('--omit-deprecated', help='Omit the deprectated old-school accessors.',
                   action='store_true')

group = parser.add_argument_group('Diagnostic options')
group.add_argument("-v", "--verbosity", help="increase output verbosity",
                   action="count", default=0)
group.add_argument("--fq", help="print fully-qualified message and enum types in AST",
                   action='store_true')
group.add_argument("--with-verbose-imports", help="print AST for imported files",
                   action='store_true')

args = parser.parse_args()
utils.args = args
nodes.args = args

assert(args.filename)
if not args.cpp_out:
    sys.exit("Missing the \"--cpp_out\" argument - please provide the output directory.")

file = parse_file(args.filename)
log(1, file.as_string())

file.generate(args.cpp_out)
