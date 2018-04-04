from collections import namedtuple
from utils import indent_from_scope, writeln

import gen, os

Filename = namedtuple('Filename', ['cc', 'h'])

# Builds output file paths.
#
# TODO: need to figure out whether this function must merge path
#   - 'proto_name' may have a common prefix with 'out_path'...
def get_cpp_file_paths(proto_name, out_path):
    assert(out_path)
    if out_path[-1] != "/" and out_path[-1] != "\\":
        out_path += "/"
    parts = proto_name.split('.')
    assert(parts[-1] == "proto")
    parts.pop(-1)
    parts.append(args.file_extension)
    return Filename(out_path + ".".join(parts) + ".cc",
                    out_path + ".".join(parts) + ".h")

# Creates a new file in the specified path. The directories are created in the
# "mkdir -p" fashion.
def open_file(path):
    assert(path.count('\\') == 0)

    dir_list = path.split('/')[0:-1]
    dir = "/".join(dir_list)
    if not os.path.exists(dir):
        os.makedirs(dir)
    assert(os.path.exists(dir))

    return open(path, "w")

#
# AST nodes
#

class Node:
    def __init__(self):
        self.parent = None
        self.fq_name = None

class File(Node):
    def __init__(self, fs_path):
        Node.__init__(self)
        self.statements = []
        self.imports = {}
        self.options = []
        self.messages = {}
        self.enums = {}
        self.path = fs_path
        self.namespace = ""
        self.syntax = None

        assert(self.path)
        assert(self.path.count('\\') == 0), "Got a Windows path: " + self.path

    def filename(self):
        return self.path.split("/")[-1]

    def cpp_include_path(self):
        assert(self.path[-6:] == ".proto")

        global args
        return self.path[0:-5] + args.file_extension + ".h"

    def as_string(self):
        assert(self.namespace)

        s = ""

        global args
        if args.with_verbose_imports:
            for file_name, ast in self.imports.items():
                s += ast.as_string()

        s += "\nAST for " + self.filename() + ", namespace=" + self.namespace + "\n\n"

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

    def set_cpp_type_names(self):
        assert(self.namespace)

        for _, enum in self.enums.items():
            enum.ns = self.namespace
            enum.impl_cpp_type = enum.name()

        for _, msg in self.messages.items():
            msg.set_cpp_type_names("::".join(self.namespace.split(".")), "")

    def generate(self, out_path):
        fname = get_cpp_file_paths(self.path, out_path)
        self.generate_header(fname.h)
        self.generate_source(fname.cc)

    def generate_header(self, fname):
        file = open_file(fname)

        writeln(file, "#pragma once\n")
        writeln(file, "#include <cstdint>")
        writeln(file, "#include <memory>")
        writeln(file, "#include <string>")
        writeln(file, "#include <vector>")
        writeln(file, "")

        for _, file_ast in self.imports.items():
            file_ast.generate_forward_declarations(file)

        for ns in self.namespace.split("."):
            writeln(file, "namespace " + ns + " {")

        # Top-level enums.
        for _, enum in self.enums.items():
            enum.generate_header(file, 0)
        if len(self.enums.keys()) > 0:
            writeln(file, "")

        # Messages.
        for _, msg in self.messages.items():
            msg.generate_header(file, self.namespace)

        for ns in self.namespace.split("."):
            writeln(file, "}  // " + ns)

    def generate_source(self, fname):
        file = open_file(fname)

        writeln(file, "#include <bitset>")
        writeln(file, "")

        # Include directives. At this point we need every generated type.
        writeln(file, "#include <" + self.cpp_include_path() + ">")
        for _, file_ast in self.imports.items():
            writeln(file, "#include <" + file_ast.cpp_include_path() + ">")
        writeln(file, "")

        for ns in self.namespace.split("."):
            writeln(file, "namespace " + ns + " {")
        writeln(file, "")

        for _, msg in self.messages.items():
            msg.generate_source(file, self.namespace)

        for ns in self.namespace.split("."):
            writeln(file, "}  // " + ns)

    def generate_forward_declarations(self, file):
        if len(self.messages) == 0:
            return

        writeln(file, "// Forward declarations from " + self.filename())
        for ns in self.namespace.split("."):
            writeln(file, "namespace " + ns + " {")

        '''TODO: how do I deal with enums?'''
        #for _, enum in self.enums.items():
        #    enum.generate_header(file, 0)

        for _, msg in self.messages.items():
            msg.generate_forward_declarations(file)

        for ns in self.namespace.split("."):
            writeln(file, "}  // " + ns)
        writeln(file, "")


class Syntax(Node):
    def __init__(self, syntax_id):
        Node.__init__(self)
        self.syntax_id = syntax_id


class Package(Node):
    def __init__(self, name):
        Node.__init__(self)
        self.name = name


class Import(Node):
    def __init__(self, path):
        Node.__init__(self)
        self.path = path


class Option(Node):
    def __init__(self, name, value):
        Node.__init__(self)
        self.name = name
        self.value = value


class Message(Node, gen.Message):
    def __init__(self, fq_name, parent):
        Node.__init__(self)
        gen.Message.__init__(self)

        self.parent = parent        # the parent Message or None

        self.ns = ""
        self.fq_name = fq_name

        self.fields = {}
        self.enums = {}
        self.messages = {}

        self.impl_cpp_type = None

    def name(self):
        assert(self.fq_name)
        return self.fq_name.split('.')[-1]

    def print_name(self):
        global args
        if args.fq:
            return self.fq_name
        else:
            return self.name()

    def fq_cpp_ref(self):
        return self.ns + "::" + self.impl_cpp_type

    def as_string(self, namespace):
        assert(namespace)
        assert(namespace[-1] != '.')
        assert(namespace + "." + self.name() == self.fq_name)

        s = indent_from_scope(namespace) + "Message: " + self.print_name()
        if self.impl_cpp_type:
            s+= " // " + self.impl_cpp_type
        s += "\n"

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

        if front in self.enums:
            if len(parts) == 0:
                return self.enums[ftype]
            return None

        if front in self.messages:
            msg = self.messages[front]
            if len(parts) == 0:
                return msg
            return msg.resolve_type(".".join(parts))

        return None

    def set_cpp_type_names(self, ns, prefix):
        self.ns = ns
        self.impl_cpp_type = prefix + self.name()

        for _, enum in self.enums.items():
            enum.ns = ns
            enum.impl_cpp_type = prefix + self.name() + "::" + enum.name()

        for _, sub_msg in self.messages.items():
            sub_msg.set_cpp_type_names(ns, prefix + self.name() + "_")


class Enum(Node, gen.Enum):
    def __init__(self, fq_name):
        Node.__init__(self)
        gen.Enum.__init__(self)

        self.ns = ""
        self.fq_name = fq_name
        self.values = {}

    def name(self):
        assert(self.fq_name)
        return self.fq_name.split('.')[-1]

    def initializer(self):
        assert(0 in self.values.keys())
        return self.values[0]

    def print_name(self):
        global args
        if args.fq:
            return self.fq_name
        else:
            return self.name()

    def as_string(self, namespace):
        assert(namespace)
        assert(namespace[-1] != '.')
        assert(namespace + "." + self.name() == self.fq_name)

        return indent_from_scope(namespace) + "Enum: " + self.print_name() + \
            "(" + ", ".join(self.values.values()) + ") // " + self.impl_cpp_type


class Field(Node, gen.Field):
    def __init__(self, name, id, raw_type, resolved_type, specifier):
        Node.__init__(self)
        gen.Field.__init__(self)

        self.name = name
        self.id = id
        self.raw_type = raw_type
        self.resolved_type = resolved_type

        self.is_enum = False
        if self.raw_type in ['int32', 'uint32', 'int64', 'uint64', 'double', 'float', 'bool']:
            self.is_builtin = True
            self.is_algebraic = True
        elif self.raw_type in ['string']:
            self.is_builtin = True
            self.is_algebraic = False
        else:
            self.is_builtin = False
            self.is_algebraic = False
        self.is_repeated = False
        self.is_fq_ref = False
        if specifier and specifier.value == "repeated":
            self.is_repeated = True

    def initializer(self):
        assert(self.is_enum)
        if type(self.resolved_type.parent) is File:
            return self.resolved_type.initializer()

        return self.resolved_type.parent.impl_cpp_type + "::" + \
            self.resolved_type.initializer()

    def as_string(self, namespace):
        assert(namespace)
        assert(namespace[-1] != '.')

        rv = indent_from_scope(namespace) + \
            "[" + str(self.id) + "] " + self.name + " : "
        if self.resolved_type:
            global args
            if args.fq:
                rv += self.resolved_type.print_name()
            else:
                rv += self.raw_type
        else:
            rv += self.raw_type

        return rv + (" (enum)" if self.is_enum else "") + \
                (" (repeated)" if self.is_repeated else "")


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
