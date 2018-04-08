#!/usr/bin/python3

import gen, nodes, scanner, utils
import sys

from scanner import Token
from utils import indent_from_scope, log

#
# The main parser: builds AST for a single file.
#
def parse_file(path, parent = None):
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

    if path in scanner.Context.global_file_dict.keys():
        return scanner.Context.global_file_dict[path]

    s = scanner.Scanner(path)
    if s.reached_eof():
        raise ValueError("Nothing to parse!")

    ctx = scanner.Context(s)
    file_ast = file(ctx, parent)
    assert(ctx.scanner.reached_eof())
    file_ast.set_cpp_type_names()

    scanner.Context.global_file_dict[path] = file_ast

    return file_ast

# Grammar:
#  <input>         ::= <statement> [ <statement> ] EOF
def file(ctx, parent):
    if ctx.scanner.reached_eof():
        raise ValueError("Reached EoF while parsing the 'file' rule")

    file = nodes.File(ctx.scanner.file_path, parent)
    while not ctx.scanner.reached_eof():
        statement(ctx, file)

    # OK, this file has been parsed, but there may be unresolved (forward) references.
    log(1, "Parsed " + file.path + ", verifying type references...")
    file.verify_type_references()

    return file

# Grammar:
#  <statement>     ::= <package> | <syntax> <import> | <option>
#                    | <message> | <enum>
#                    | <extend>
def statement(ctx, file_node):
    keyword = ctx.consume_keyword(statement)

    if keyword.value == "syntax":
        file_node.syntax = syntax(ctx)
        log(2, "[parser] consumed a 'syntax' statement: " + file_node.syntax.syntax_id)
    elif keyword.value == "package":
        file_node.namespace = package(ctx).name
        log(2, "[parser] consumed a 'package' statement: " + file_node.namespace)
    elif keyword.value == "import":
        statement_ast = imports(ctx)
        log(2, "[parser] consumed an 'import' statement: " + statement_ast.path)

        file = parse_file(statement_ast.path, file_node)
        log(2, "[parser] consumed an imported file: " + file.filename())

        file_node.imports[file.path] = file
    elif keyword.value == "option":
        file_node.options.append(option(ctx))
        log(2, "[parser] consumed an 'option' statement: " + file_node.options[-1].name)
    elif keyword.value == "message":
        msg = message(ctx, file_node, file_node.namespace + ".")
    elif keyword.value == "enum":
        enum_decl(ctx, file_node, file_node.namespace + ".")
    elif keyword.value == "extend":
        extend(ctx, file_node, file_node.namespace + ".")
    else:
        ctx.throw(statement,
                  " Unexpected keyword: " + keyword.value)

# Grammar:
#  <syntax>     ::= SYNTAX = string SEMI
def syntax(ctx):
    ctx.consume_equals(syntax)
    syntax_id = ctx.consume_string(syntax)
    ctx.consume_semi(syntax)
    return nodes.Syntax(syntax_id.value)

# Grammar:
#  <package>     ::= PACKAGE [ DOT identifier ] identifier SEMI
def package(ctx):
    name = ctx.consume_identifier(package)
    while ctx.scanner.next() == Token.Type.Dot:
        ctx.consume()
        trailer = ctx.consume_identifier(package)
        name.value += "." + trailer.value
    ctx.consume_semi(package)
    return nodes.Package(name.value)

# Grammar:
#  <import>     ::= IMPORT string SEMI
def imports(ctx):
    fname = ctx.consume_string(imports)
    ctx.consume_semi(imports)
    return nodes.Import(fname.value)

# Grammar:
#  <option>     ::= OPTION identifier EQUALS (string | number | boolean) SEMI
def option(ctx):
    name = ctx.consume_identifier(option)
    ctx.consume_equals(option)
    if ctx.scanner.next() == Token.Type.String:
        value_tok = ctx.consume_string(option)
    elif ctx.scanner.next() == Token.Type.Number:
        value_tok = ctx.consume_number(option)
    elif ctx.scanner.next() == Token.Type.Boolean:
        value_tok = ctx.consume_boolean(option)
    elif ctx.scanner.next() == Token.Type.Identifier:
        value_tok = ctx.consume_identifier(option)
    else:
        ctx.throw(option)
    ctx.consume_semi(option)
    return nodes.Option(name.value, value_tok.value)

# Grammar:
#  <message>     ::= SCOPE_OPEN decl_list SCOPE_CLOSE
def message(ctx, parent, scope):
    fq_name = ctx.consume_identifier(message).value
    if scope:
        fq_name = scope + fq_name

    msg = nodes.Message(fq_name, parent)
    ctx.consume_scope_open(message)

    # Splice the new Node into the AST right here so that type lookups work.
    parent.messages[msg.name()] = msg
    log(2, "[parser] " + indent_from_scope(fq_name) + "Started a 'message' : " + msg.fq_name)

    decl_list(ctx, msg, fq_name + ".")
    ctx.consume_scope_close(message)

    # protoc is accepts a SEMI here for no apparent reason.
    if ctx.scanner.next() == Token.Type.Semi:
        ctx.consume()

    log(2, "[parser] " + indent_from_scope(fq_name) + "Finished " + msg.fq_name)
    return msg

# Grammar:
#  <decl_list>     ::= ( <decl> | <message> ) [ <decl> | <message> ]
def decl_list(ctx, parent, scope):
    while ctx.scanner.next() != Token.Type.ScopeClose:
        # Process sub-messages.
        if ctx.scanner.next() == Token.Type.Keyword and ctx.scanner.get().value == "message":
            ctx.consume_keyword(decl_list)
            msg = message(ctx, parent, scope)
            continue

        # Process extensions.
        if ctx.scanner.next() == Token.Type.Keyword and ctx.scanner.get().value == "extend":
            ctx.consume_keyword(decl_list)
            extend(ctx, parent, scope)
            continue

        # This must be a normal field declaration.
        decl(ctx, parent, scope)

# Grammar:
#  <decl>     ::= <builtin-field-decl> | <message-field-decl> | <enum-decl>
#               | <reserved-decl> | <extensions-decl> | <map-field-decl>
def decl(ctx, parent, scope):
    spec = None
    if ctx.scanner.next() == Token.Type.Specifier:
        if ctx.scanner.get().value == "map":
            map_field_decl(ctx, parent, scope)
            return
        else:
            spec = ctx.consume().value

    if ctx.scanner.next() == Token.Type.DataType:
        builtin_field_decl(ctx, parent, spec, scope)
    elif ctx.scanner.next() == Token.Type.Identifier:
        message_field_decl(ctx, parent, spec, scope)
    elif ctx.scanner.next() == Token.Type.Keyword and ctx.scanner.get().value == "enum":
        ctx.consume_keyword(decl)
        enum_decl(ctx, parent, scope)
    elif ctx.scanner.next() == Token.Type.Keyword and ctx.scanner.get().value == "reserved":
        ctx.consume_keyword(decl)
        reserved_decl(ctx, parent, scope)
    elif ctx.scanner.next() == Token.Type.Keyword and ctx.scanner.get().value == "extensions":
        # extensions 100 to 199;
        # extensions 100 to max;
        ctx.consume_keyword(decl)
        parent.min_extension_id = int(ctx.consume_number(decl).value)
        tok = ctx.consume_identifier(decl)
        assert(tok.value == 'to')
        if ctx.scanner.next() == Token.Type.Keyword:
            end = ctx.consume_keyword(decl).value
            assert(end == 'max')
        else:
            end = ctx.consume_number(decl)
        ctx.consume_semi(decl)
    else:
        ctx.throw(decl)


# Grammar:
#  <builtin-field-decl> ::= [ SPECIFIER ] BUILTIN-TYPE identifier EQUALS number
#                           [ SQUARE_OPEN DEFAULT EQUALS builtin-value SQUARE_CLOSE ]
#                           SEMI
def builtin_field_decl(ctx, parent, spec, scope):
    ftype = ctx.consume().value
    fname = ctx.consume_identifier(builtin_field_decl)
    ctx.consume_equals(builtin_field_decl)
    fid = ctx.consume_number(builtin_field_decl)

    if ctx.scanner.next() == Token.Type.SquareOpen:
        ctx.consume()
        tok = ctx.consume_identifier(builtin_field_decl)
        if not tok.value in ["default", "deprecated", "packed"]:
            ctx.throw(builtin_field_decl, "Unrecognized keyword: " + tok.value)
        ctx.consume_equals(message_field_decl)
        ctx.consume()
        tok = ctx.consume_square_close(builtin_field_decl)
    ctx.consume_semi(builtin_field_decl)

    field_ast = nodes.Field(fname.value,
                            int(fid.value),
                            ftype, None,
                            spec)
    field_ast.parent = parent

    parent.fields[int(fid.value)] = field_ast
    log(2, "[parser] " + indent_from_scope(scope) + "consumed a built-in 'field' declaration: " + fname.value)


# Grammar:
#  <map-field-decl> ::= MAP ANGLE_OPEN BUILTIN-TYPE COMA identifier ANGLE_CLOSE identifier EQUALS number SEMI
def map_field_decl(ctx, parent, scope):
    spec = ctx.consume_specifier(map_field_decl).value
    assert(spec == "map")

    ctx.consume_angle_open(map_field_decl)
    key_type = ctx.consume_data_type(map_field_decl).value
    ctx.consume_coma(map_field_decl)
    mapped_type = ctx.consume()
    ctx.consume_angle_close(map_field_decl)
    fname = ctx.consume_identifier(map_field_decl)

    if mapped_type.type == Token.Type.DataType:
        resolved_mapped_type = None
    elif mapped_type.type == Token.Type.Identifier:
        resolved_mapped_type = nodes.find_type(parent, mapped_type.value)
        this_file_node = nodes.find_file_parent(parent)
        if not resolved_mapped_type:
            resolved_mapped_type = this_file_node.resolve_type(this_file_node.namespace,
                                                                mapped_type.value)
            if not resolved_mapped_type:
                sys.exit('Error: failed to resolve type: "' + mapped_type.value + '" in ' +
                     this_file_node.path + ' for the following field: "' + fname.value + '"')
    else:
        ctx.throw(builtin_field_decl, "Expected a known data type.")

    ctx.consume_equals(map_field_decl)
    fid = ctx.consume_number(map_field_decl)
    ctx.consume_semi(map_field_decl)

    field_ast = nodes.Field(fname.value,
                            int(fid.value),
                            key_type, None,
                            spec,
                            mapped_type.value)
    field_ast.parent = parent
    assert(field_ast.is_map)
    field_ast.resolved_type = resolved_mapped_type

    parent.fields[int(fid.value)] = field_ast
    log(2, "[parser] " + indent_from_scope(scope) + "consumed a map 'field' declaration: " + fname.value)


# Grammar:
#  <message-field-decl> ::= identifier [ DOT identifier ] identifier EQALS number
#                           [ SQUARE_OPEN <stuff> SQUARE_CLOSE ] SEMI
def message_field_decl(ctx, parent, spec, scope):
    # 1. take the type name, possible fully qualified.
    ftype = ctx.consume_identifier(message_field_decl).value
    while ctx.scanner.next() == Token.Type.Dot:
        ctx.consume()
        trailer = ctx.consume_identifier(message_field_decl)
        ftype += "." + trailer.value

    # 2. take the field name
    fname = ctx.consume_identifier(message_field_decl)

    # 3. take the rest
    ctx.consume_equals(message_field_decl)
    fid = ctx.consume_number(message_field_decl)
    if ctx.scanner.next() == Token.Type.SquareOpen:
        ctx.consume()

        paren = None
        if ctx.scanner.next() == Token.Type.ParenOpen:
            paren = ctx.consume()
        stuff = ctx.consume_identifier(builtin_field_decl)
        if paren:
            ctx.consume_paren_close(builtin_field_decl)

        ctx.consume_equals(message_field_decl)
        value = ctx.consume()
        ctx.consume_square_close(builtin_field_decl)
    ctx.consume_semi(message_field_decl)

    # 4. verify the type reference
    #   a) see whether this is a reference to a type within the current file
    #      which is subject to the C++-style visibility rules.
    resolved_type = nodes.find_type(parent, ftype)
    if resolved_type:
        assert(utils.is_suffix(resolved_type.fq_name, ftype))
        field_ast = nodes.Field(fname.value, int(fid.value), ftype, resolved_type, spec)
        field_ast.is_fq_ref = False
    else:
        file_node = nodes.find_file_parent(parent)
        assert(file_node)
        assert(type(file_node) is nodes.File)
        assert(file_node.namespace)

        # b) see whether the type lives in the same namespace but is being imported. This
        #    type name may be partially or fully qualified.
        resolved_type = file_node.resolve_type(file_node.namespace, ftype)
        if resolved_type:
            assert(resolved_type.fq_name[-len(ftype):] == ftype)
            file_node.store_external_typename_ref(resolved_type.fq_name)
        else:
            log(1, "[parser] " + indent_from_scope(scope) + ftype + " appears to be is a forward declaration")

        field_ast = nodes.Field(fname.value, int(fid.value), ftype, resolved_type, spec)
        field_ast.is_fq_ref = resolved_type != None
        field_ast.is_forward_decl = resolved_type == None

    field_ast.parent = parent
    if type(resolved_type) is nodes.Enum:
        field_ast.is_enum = True

    parent.fields[int(fid.value)] = field_ast
    log(2, "[parser] " + indent_from_scope(scope) + "consumed a message 'field' declaration: " + fname.value)


# Grammar:
#  <enum-decl>     ::= ENUM identifier SCOPE_OPEN <evalue-list> SCOPE_CLOSE
def enum_decl(ctx, parent, scope):
    name = ctx.consume_identifier(enum_decl).value
    fq_name = name
    if scope:
        fq_name = scope + fq_name

    ctx.consume_scope_open(enum_decl)
    enum_ast = nodes.Enum(fq_name, type(parent) == nodes.File)
    enum_ast.parent = parent

    parent.enums[name] = enum_ast
    log(2, '[parser] ' + indent_from_scope(fq_name) + "consumed an 'enum' declaration: " + fq_name)

    evalue_list(ctx, enum_ast, scope)
    ctx.consume_scope_close(enum_decl)

    # protoc is accepts a SEMI here for no apparent reason.
    if ctx.scanner.next() == Token.Type.Semi:
        ctx.consume()

# Grammar:
#  <evalue_list>     ::= <evalue> [ <evalue> ]
def evalue_list(ctx, enum, scope):
    while ctx.scanner.next() != Token.Type.ScopeClose:
        if ctx.scanner.next() == Token.Type.Keyword and ctx.scanner.next_value() == "option":
            ctx.consume_keyword(evalue_list)
            enum.options.append(option(ctx))
            log(2, "[parser] consumed an enum 'option' statement: " + enum.options[-1].name)
            continue
        evalue(ctx, enum, scope + ".")

# Grammar:
#  <evalue>     ::= identifier EQALS number SEMI
def evalue(ctx, enum, scope):
    val = ctx.consume_identifier(evalue)
    ctx.consume_equals(evalue)
    eid = ctx.consume_number(evalue)
    ctx.consume_semi(evalue)
    enum.values[int(eid.value)] = val.value
    log(2, '[parser] ' + indent_from_scope(scope) + "consumed an enum constant: " + val.value)

# Grammar:
#  <reserved-decl>     ::= RESERVED number ( [COMA number ] | [ TO number ] ) SEMI
def reserved_decl(ctx, parent, scope):
    id = int(ctx.consume_number(reserved_decl).value)
    if ctx.scanner.next() == Token.Type.Coma:
        while ctx.scanner.next() == Token.Type.Coma:
            ctx.consume()
            ctx.consume_number(reserved_decl)
    elif ctx.scanner.next() == Token.Type.Identifier:
        to = ctx.consume_identifier(reserved_decl)
        if to.value != "to":
            ctx.throw("Expected \"to\".")
        id2 = int(ctx.consume_number(reserved_decl).value)

    ctx.consume_semi(reserved_decl)
    log(2, '[parser] ' + indent_from_scope(scope) + "consumed an 'reserved' declaration: " + str(id))

# Grammar:
#  <extend>     ::= identifier [ DOT identifier ] SCOPE_OPEN decl_list SCOPE_CLOSE
def extend(ctx, parent, scope):
    base_typename = ctx.consume_identifier(extend).value
    if scope:
        base_typename = scope + base_typename

    while ctx.scanner.next() == Token.Type.Dot:
        ctx.consume()
        trailer = ctx.consume_identifier(package)
        base_typename += "." + trailer.value

    msg = nodes.Message(base_typename, parent)
    msg.is_extend = True
    ctx.consume_scope_open(extend)

    parent.extends[msg.name()] = msg
    log(2, "[parser] consumed an 'extend' : " + msg.fq_name)

    decl_list(ctx, msg, base_typename + ".")
    ctx.consume_scope_close(extend)

    # protoc is accepts a SEMI here for no apparent reason.
    if ctx.scanner.next() == Token.Type.Semi:
        ctx.consume()

    return msg

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
group.add_argument('--omit-deprecated', help='Omit the deprecated old-school accessors.',
                   action='store_true')
group.add_argument('--all', help='Generate C++ code for all imported .proto files.',
                   action='store_true')

group = parser.add_argument_group('Diagnostic options')
group.add_argument("-v", "--verbosity", help="increase output verbosity",
                   action="count", default=0)
group.add_argument("--fq", help="print fully-qualified message and enum types in AST",
                   action='store_true')
group.add_argument("--with-verbose-imports", help="print AST for imported files",
                   action='store_true')
group.add_argument("-w", "--with-warnings", help="print warnings pertaining to the generated code's semantics",
                   action='store_true')

args = parser.parse_args()
utils.args = args
nodes.args = args
gen.args = args

assert(args.filename)
if not args.cpp_out:
    sys.exit("Error: missing the \"--cpp_out\" argument - please provide the output directory.")

file = parse_file(args.filename)
if args.verbosity >= 1:
    log(1, file.as_string())

if args.all:
    for _, file in scanner.Context.global_file_dict.items():
        file.generate(args.cpp_out)
else:
    file.generate(args.cpp_out)
