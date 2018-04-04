from collections import namedtuple
from utils import indent_from_scope

import os

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

def cpp_arg_type(proto_type):
    if proto_type == "string":
        return "const std::string&"
    elif proto_type[-2:] == "32" or proto_type[-2:] == "64":
        return proto_type + "_t"
    else:
        return proto_type.replace(".", "::")

def cpp_impl_type(proto_type):
    if proto_type == "string":
        return "std::string"
    elif proto_type[-2:] == "32" or proto_type[-2:] == "64":
        return proto_type + "_t"
    else:
        return proto_type.replace(".", "::")

def writeln(file, line, indent = 0):
    file.write("  " * indent + line + "\n")

def write_blank_if(file, collection):
    if len(collection) > 0:
        writeln(file, "")

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


class Message(Node):
    def __init__(self, fq_name, parent):
        Node.__init__(self)
        self.parent = parent        # the parent Message or None

        self.ns = ""
        self.fq_name = fq_name
        self.impl_cpp_type = ""

        self.fields = {}
        self.enums = {}
        self.messages = {}

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

        s = indent_from_scope(namespace) + "Message: " + self.print_name() + \
            " // " + self.impl_cpp_type + "\n"

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

    def generate_header(self, file, ns, indent = 0):
        # Forward declarations for sub-messages.
        for _, sub_msg in self.messages.items():
            writeln(file, "class " + sub_msg.impl_cpp_type + ";")
        write_blank_if(file, self.messages)

        # Start the C++ class.
        writeln(file, "class " + self.impl_cpp_type + " {", indent)
        writeln(file, " public:", indent)

        # Construction and assignment
        writeln(file, "// Construction and assignment", indent + 1)
        writeln(file, self.impl_cpp_type + "();", indent + 1)
        writeln(file, self.impl_cpp_type + "(const " + self.impl_cpp_type + "&);",
                indent + 1)
        writeln(file, self.impl_cpp_type + "(" + self.impl_cpp_type + "&&);",
                indent + 1)
        writeln(file, self.impl_cpp_type + "& " + "operator=(const " + \
            self.impl_cpp_type + "&);",
            indent + 1)
        writeln(file, self.impl_cpp_type + "& " + "operator=(" + \
            self.impl_cpp_type + "&&);",
            indent + 1)
        writeln(file, "~" + self.impl_cpp_type + "();", indent + 1)
        writeln(file, "")

        # Generally accessible, common API
        writeln(file,
                "static const " + self.impl_cpp_type + "& " + "default_instance();",
                indent + 1)
        writeln(file, "void Clear() { *this = default_instance(); }", indent + 1)
        writeln(file, "")

        # Aliases for sub-messages
        for _, sub_msg in self.messages.items():
            writeln(file,
                    "using " + sub_msg.name() + " = " + sub_msg.impl_cpp_type + ";",
                    1)
        write_blank_if(file, self.messages)

        # Enums
        if len(self.enums.keys()) > 0:
            writeln(file, "// Enums", indent + 1)
        for _, enum in self.enums.items():
            enum.generate_header(file, indent + 1)
        write_blank_if(file, self.enums)

        # Fields
        for id, field in self.fields.items():
            field.generate_accessor_declarations(file, indent + 1)

        # Implementation
        writeln(file, " private:", indent)
        writeln(file, "struct Representation;", indent + 1)
        writeln(file, "std::unique_ptr<Representation> rep_;", indent + 1)

        writeln(file, "};\n", indent)

        # Sub-messages
        #
        # The header cannot be generated in the normal/native DFS style as C++ does not
        # allow forward declarations Outer::Inner. So, just pre-order DFS to flatten out
        # the tree.
        for _, sub_msg in self.messages.items():
            sub_msg.generate_header(file, ns)

    def set_cpp_type_names(self, ns, prefix):
        self.ns = ns
        self.impl_cpp_type = prefix + self.name()

        for _, enum in self.enums.items():
            enum.ns = ns
            enum.impl_cpp_type = prefix + self.name() + "::" + enum.name()

        for _, sub_msg in self.messages.items():
            sub_msg.set_cpp_type_names(ns, prefix + self.name() + "_")

    def generate_forward_declarations(self, file):
        assert(self.impl_cpp_type)
        writeln(file, "class " + self.impl_cpp_type.split("::")[-1] + ";")

        # (Sub)Messages
        for _, sub_msg in self.messages.items():
            sub_msg.generate_forward_declarations(file)

    def generate_source(self, file, ns):
        # Implementation
        writeln(file, "//")
        writeln(file, "// " + self.fq_name)
        writeln(file, "//")
        writeln(file, "struct " + self.impl_cpp_type + "::Representation {")
        for id, field in self.fields.items():
            field.generate_implementation_definition(file)
        writeln(file, "")
        writeln(file,
                "std::bitset<" + str(list(self.fields.keys())[-1] + 1) + "> _Presence;",
                1)
        writeln(file, "};\n")

        # Construction, copying and assigment
        writeln(file, self.impl_cpp_type + "::" + self.impl_cpp_type +
                "() : rep_(std::make_unique<Representation>()) {}")
        writeln(file,
                self.impl_cpp_type + "::" + self.impl_cpp_type +
                    "(const " + self.impl_cpp_type + "& arg) : rep_(new Representation(*arg.rep_)) {}")
        writeln(file, self.impl_cpp_type + "::" + self.impl_cpp_type +
                "(" + self.impl_cpp_type + "&&) = default;")
        writeln(file,
                self.impl_cpp_type + "& " + self.impl_cpp_type + "::operator=(" +
                    "const " + self.impl_cpp_type + "& arg) { ")
        writeln(file, "if (this != &arg) *rep_ = *arg.rep_;", 1)
        writeln(file, "return *this;", 1)
        writeln(file, "}")
        writeln(file, self.impl_cpp_type + "& " + self.impl_cpp_type + "::operator=(" +
                self.impl_cpp_type + "&&) = default;")
        writeln(file, self.impl_cpp_type + "::~" + self.impl_cpp_type + "() = default;")
        writeln(file, "")

        writeln(file, " const " + self.impl_cpp_type + "& " + self.impl_cpp_type + "::default_instance() {")
        writeln(file, "static " + self.impl_cpp_type + " obj;", 1)
        writeln(file, "return obj;", 1)
        writeln(file, "}")
        writeln(file, "")

        # Field accessors for the given message
        for id, field in self.fields.items():
            field.generate_accessor_definitions(file)

        # Sub-messages
        #
        # The header cannot be generated in the normal/native DFS style as C++ does not
        # allow forward declarations Outer::Inner. So, just pre-order DFS to flatten out
        # the tree.
        for _, sub_msg in self.messages.items():
            sub_msg.generate_source(file, ns)

class Enum(Node):
    def __init__(self, fq_name):
        Node.__init__(self)

        self.ns = ""
        self.fq_name = fq_name
        self.impl_cpp_type = ""

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

    def generate_header(self, file, indent):
        writeln(file, "enum " + self.name() + " {", indent)

        for id, value in self.values.items():
            writeln(file, value + " = " + str(id) + ",", indent + 1)

        writeln(file, "};", indent)


class Field(Node):
    def __init__(self, name, id, raw_type, resolved_type, specifier):
        Node.__init__(self)
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

    # Returns the full type of the field's accessor respecting the "repeated" tag's presence.
    def cpp_type_ref(self):
        def repeated(type):
            if self.is_repeated:
                return "std::vector<" + type + ">"
            return type
        return repeated(self.base_cpp_type_ref())

    # Returns the C++ type of the field disregarding the "repeated" tag's presence.
    def base_cpp_type_ref(self):
        if self.is_builtin:
            assert(not self.resolved_type)
            return cpp_impl_type(self.raw_type)

        assert(self.resolved_type)
        if self.is_fq_ref:
            return self.resolved_type.fq_cpp_ref()
        else:
            return self.resolved_type.impl_cpp_type

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

    def generate_accessor_declarations(self, file, indent):
        writeln(file, "// [" + str(self.id) + "] " + self.name, indent)
        if self.is_builtin and not self.is_repeated:
            # These accessors take built-in args by value.
            writeln(file,
                    self.cpp_type_ref() + " " + self.name + "() const;",
                    indent)
            writeln(file,
                    "void set_" + self.name + "(" + self.cpp_type_ref() + ");",
                    indent)
        elif self.is_enum and not self.is_repeated:
            # This one must deal with scopes, but the accessors work as built-ins.
            writeln(file,
                    self.cpp_type_ref() + " " + self.name + "() const;",
                    indent)
            writeln(file,
                    "void set_" + self.name + "(" + self.cpp_type_ref() + ");",
                    indent)
        else:
            # These are sub-messages/containers and, thus, have reference-based accessors.
            writeln(file,
                    "const " + self.cpp_type_ref() + "& " + self.name + "() const;",
                    indent)
            writeln(file,
                    self.cpp_type_ref() + "& " + self.name + "();",
                    indent)
            writeln(file,
                    "/* deprecated */ auto mutable_" + self.name + "() { " + \
                        " return &" + self.name + "(); }",
                    indent)

        if not self.is_repeated:
            writeln(file, "void clear_" + self.name + "();", indent)

        if self.is_repeated:
            writeln(file,
                    "/* deprecated */ " + "void clear_" + self.name + "() { " + \
                        self.name + "().clear(); }",
                    indent)
            if self.is_builtin or self.is_enum:
                writeln(file,
                        "/* deprecated */ " + \
                            "void add_" + self.name + "(" + self.base_cpp_type_ref() + ");",
                        indent)
                writeln(file,
                    "/* deprecated */ " + \
                        self.base_cpp_type_ref() + " " + self.name + "(int idx) const;",
                    indent)
            else:
                writeln(file,
                        "/* deprecated */ " + \
                            self.base_cpp_type_ref() + "* add_" + self.name + "();",
                        indent)
                writeln(file,
                    "/* deprecated */ " + \
                        self.base_cpp_type_ref() + "* mutable_" + self.name + "(int idx);",
                    indent)
                writeln(file,
                    "/* deprecated */ " + \
                        "const " + self.base_cpp_type_ref() + "& " + self.name + "(int idx) const;",
                    indent)
        writeln(file, "", indent)

    def generate_accessor_definitions(self, file):
        writeln(file, "// [" + str(self.id) + "] " + self.name)
        if self.is_builtin and not self.is_repeated:
            writeln(file,
                    self.cpp_type_ref() + " " \
                        + self.parent.impl_cpp_type + "::" + self.name + "() const {")
            writeln(file, "return rep_->" + self.name + ";", 1)
            writeln(file, "}")
            writeln(file,
                    "void " + self.parent.impl_cpp_type + "::set_" + self.name + \
                        "(" + self.cpp_type_ref() + " val) {")
            writeln(file, "rep_->" + self.name + " = val;", 1)
            writeln(file, "rep_->_Presence.set(" + str(self.id) + ");", 1)
            writeln(file, "}")
        elif self.is_enum and not self.is_repeated:
            writeln(file,
                    self.cpp_type_ref() + " " \
                        + self.parent.impl_cpp_type + "::" + self.name + "() const {")
            writeln(file, "return rep_->" + self.name + ";", 1)
            writeln(file, "}")
            writeln(file,
                    "void " + self.parent.impl_cpp_type + "::set_" + self.name + \
                        "(" + self.cpp_type_ref() + " val) {")
            writeln(file, "rep_->" + self.name + " = val;", 1)
            writeln(file, "rep_->_Presence.set(" + str(self.id) + ");", 1)
            writeln(file, "}")
        else:
            writeln(file,
                    "const " + self.cpp_type_ref() + "& " + \
                        self.parent.impl_cpp_type + "::" + self.name + "() const {")
            writeln(file, "return rep_->" + self.name + ";", 1)
            writeln(file, "}")
            writeln(file,
                    self.cpp_type_ref() + "& " + \
                        self.parent.impl_cpp_type + "::" + self.name + "() {")
            writeln(file, "rep_->_Presence.set(" + str(self.id) + ");", 1)
            writeln(file, "return rep_->" + self.name + ";", 1)
            writeln(file, "}")

        if not self.is_repeated:
            writeln(file,
                    "void " + self.parent.impl_cpp_type + "::clear_" + self.name + "() {")

            if self.is_algebraic:
                writeln(file, "rep_->" + self.name + " = 0;", 1)
            elif self.is_builtin:
                writeln(file, "rep_->" + self.name + ".clear();", 1)
            elif self.is_enum:
                writeln(file, "rep_->" + self.name + " = " + self.initializer() + ";", 1)
            else:
                writeln(file, "rep_->" + self.name + ".Clear();", 1)
            writeln(file, "rep_->_Presence.reset(" + str(self.id) + ");", 1)
            writeln(file, "}")

        if self.is_repeated:
            if self.is_builtin or self.is_enum:
                writeln(file,
                        "/* deprecated */ void " + self.parent.impl_cpp_type + "::add_" + self.name + "(" + \
                            self.base_cpp_type_ref() + " value) {")
                writeln(file, self.name + "().push_back(std::move(value));", 1)
                writeln(file, "}")
                writeln(file,
                    "/* deprecated */ " + \
                        self.base_cpp_type_ref() + " " + self.parent.impl_cpp_type + "::" + \
                        self.name + "(int idx) const {")
                writeln(file, "return " + self.name + "().at(idx);", 1)
                writeln(file, "}")
            else:
                writeln(file,
                        "/* deprecated */ " + self.base_cpp_type_ref() + "* " + \
                            self.parent.impl_cpp_type + "::add_" + self.name + "() {")
                writeln(file, self.name + "().push_back({});", 1)
                writeln(file, "return &" + self.name + "().back();", 1)
                writeln(file, "}")
                writeln(file,
                    "/* deprecated */ " + \
                        "const " + self.base_cpp_type_ref() + "& " + \
                        self.parent.impl_cpp_type + "::" + self.name + "(int idx) const {")
                writeln(file, "return " + self.name + "().at(idx);", 1)
                writeln(file, "}")
                writeln(file,
                    "/* deprecated */ " + \
                        self.base_cpp_type_ref() + "* " + \
                        self.parent.impl_cpp_type + "::mutable_" + self.name + "(int idx) {")
                writeln(file, "return &" + self.name + "().at(idx);", 1)
                writeln(file, "}")
        writeln(file, "")

    def generate_implementation_definition(self, file):
        if self.is_algebraic and not self.is_repeated:
            writeln(file, cpp_impl_type(self.raw_type) + " " + self.name + " = 0;", 1)
        elif self.is_builtin and not self.is_repeated:
            writeln(file, cpp_impl_type(self.raw_type) + " " + self.name + ";", 1)
        elif self.is_enum and not self.is_repeated:
            writeln(file, self.cpp_type_ref() + " " + self.name + " = " + \
                self.initializer() + ";", 1)
        else:
            writeln(file, self.cpp_type_ref() + " " + self.name + ";", 1)

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
