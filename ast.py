from collections import namedtuple
from utils import indent_from_scope

Filename = namedtuple('Filename', ['cc', 'h'])

def get_cpp_name(proto_name):
    parts = proto_name.split('.')
    assert(parts[-1] == "proto")
    parts.pop(-1)
    parts.append("pbng")
    return Filename(".".join(parts) + ".cc", ".".join(parts) + ".h")

def to_cpp_type(proto_type):
    if proto_type == "string":
        return "const std::string&"
    elif proto_type[-2:] == "32" or proto_type[-2:] == "64":
        return proto_type + "_t"
    else:
        return proto_type

def writeln(file, line, indent = 0):
    file.write("  " * indent + line + "\n")

#
# AST nodes
#

class Node:
    def __init__(self):
        self.parent = None

class FileNode(Node):
    def __init__(self, fname):
        Node.__init__(self)
        self.statements = []
        self.imports = {}
        self.options = []
        self.messages = {}
        self.enums = {}
        self.name = fname
        self.namespace = ""

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

    def generate(self):
        fname = get_cpp_name(self.name)
        cc_file = open(fname.cc, "w")
        h_file = open(fname.h, "w")

        writeln(h_file, "#pragma once")
        writeln(h_file, "#include <cstdint>")
        writeln(h_file, "#include <string>")
        for ns in self.namespace.split("."):
            writeln(h_file, "namespace " + ns + " {")

        for _, enum in self.enums.items():
            enum.generate_header(h_file, 0)

        for _, msg in self.messages.items():
            msg.generate_header(h_file, 0)

        for ns in self.namespace.split("."):
            writeln(h_file, "}  // " + ns)


class PackageNode(Node):
    def __init__(self, name):
        Node.__init__(self)
        self.name = name

class ImportNode(Node):
    def __init__(self, path):
        Node.__init__(self)
        self.path = path

class OptionNode(Node):
    def __init__(self, name, value):
        Node.__init__(self)
        self.name = name
        self.value = value

class MessageNode(Node):
    def __init__(self, fq_name, parent):
        Node.__init__(self)
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

    def generate_header(self, file, indent):
        writeln(file, "class " + self.name() + " {", indent)
        writeln(file, " public:", indent)

        # Enums
        if len(self.enums.keys()) > 0:
            writeln(file, "// Enums", indent + 1)
        for _, enum in self.enums.items():
            enum.generate_header(file, indent + 1)
        if len(self.enums.keys()) > 0:
            writeln(file, "", indent)

        # (Sub)Messages
        for name, sub_msg in self.messages.items():
            sub_msg.generate_header(file, indent + 1)

        # Fields
        for id, field in self.fields.items():
            field.generate_accessor_declarations(file, indent + 1)

        writeln(file, "};\n", indent)

class EnumNode(Node):
    def __init__(self, fq_name):
        Node.__init__(self)
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

    def generate_header(self, file, indent):
        writeln(file, "enum " + self.name() + " {", indent)

        for id, value in self.values.items():
            writeln(file, value + " = " + str(id) + ",", indent + 1)

        writeln(file, "};", indent)

class FieldNode(Node):
    def __init__(self, name, id, fq_type, raw_type, specifier):
        Node.__init__(self)
        self.name = name
        self.id = id
        self.fq_type = fq_type
        self.raw_type = raw_type

        self.is_enum = False
        self.is_builtin = False
        self.is_repeated = False
        if specifier and specifier.value == "repeated":
            self.is_repeated = True

    def as_string(self, namespace):
        assert(namespace)
        assert(namespace[-1] != '.')

        return indent_from_scope(namespace) + \
            "[" + str(self.id) + "] " + self.name + " : " + self.fq_type + \
                (" (enum)" if self.is_enum else "") + \
                (" (repeated)" if self.is_repeated else "")

    def generate_accessor_declarations(self, file, indent):
        writeln(file, "// [" + str(self.id) + "] " + self.name, indent)
        if self.is_builtin or self.is_enum:
            writeln(file,
                    to_cpp_type(self.raw_type) + " " + self.name + "() const;",
                    indent)
            writeln(file,
                    "void set_" + self.name + "(" + to_cpp_type(self.raw_type) + ");",
                    indent)
        else:
            writeln(file, "const " + self.raw_type + "& " + self.name + "() const;", indent)
            writeln(file, self.raw_type + "& " + self.name + "();", indent)
        writeln(file, "", indent)

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
