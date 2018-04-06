from collections import namedtuple
from utils import writeln, write_blank_if, log
import os

Filename = namedtuple('Filename', ['cc', 'h'])

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

#
# File
#
class File:
    def __init__(self, *args, **kwargs):
        super(File, self).__init__(*args, **kwargs)

    def generate(self, out_path):
        log(0, "Generating C++ code for " + self.path)
        fname = get_cpp_file_paths(self.path, out_path)
        self.generate_header(fname.h)
        self.generate_source(fname.cc)

    def generate_header(self, fname):
        file = open_file(fname)

        writeln(file, "#pragma once\n")
        writeln(file, "#include <cstdint>")
        writeln(file, "#include <map>")
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
        for _, file_ast in self.imports.items():
            writeln(file, "#include <" + file_ast.cpp_include_path() + ">")
        writeln(file, "#include <" + self.cpp_include_path() + ">")
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


#
# Enum
#
class Enum:
    def __init__(self, *args, **kwargs):
        super(Enum, self).__init__(*args, **kwargs)

    def generate_header(self, file, indent):
        writeln(file, "enum " + self.name() + " {", indent)

        for id, value in self.values.items():
            writeln(file, value + " = " + str(id) + ",", indent + 1)

        writeln(file, "};", indent)


#
# Message
#
class Message:
    def __init__(self, *args, **kwargs):
        super(Message, self).__init__(*args, **kwargs)

    def generate_header(self, file, ns, indent = 0):
        # Forward declarations for sub-messages.
        for _, sub_msg in self.messages.items():
            writeln(file, "class " + sub_msg.impl_cpp_type + ";")

        # Forward declarations for the implicitly declared (foward-declared) local messages.
        forwards = False
        for _, field in self.fields.items():
            if field.is_forward_decl:
                writeln(file, "class " + field.raw_type + ";")
                forwards = True
        if len(self.messages) > 0 or forwards:
            writeln(file, "")


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
        if len(self.fields) > 0:
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


#
# Field
#
class Field:
    def __init__(self, *args, **kwargs):
        super(Field, self).__init__(*args, **kwargs)

    # Returns the full type of the field's accessor respecting the "repeated" tag's presence.
    def cpp_type_ref(self):
        def repeated(type):
            if self.is_map:
                return "std::map<" + type + ">"
            elif self.is_repeated:
                return "std::vector<" + type + ">"
            return type
        return repeated(self.base_cpp_type_ref())

    # Returns the C++ type of the field disregarding the "repeated" tag's presence.
    def base_cpp_type_ref(self):
        if self.is_builtin:
            assert(not self.resolved_type)
            return cpp_impl_type(self.raw_type)

        if self.is_map:
            if self.resolved_type:
                return cpp_impl_type(self.raw_type) + ", " + self.mapped_type
            else:
                return cpp_impl_type(self.raw_type) + ", " + cpp_impl_type(self.mapped_type)

        assert(self.resolved_type)
        if self.is_fq_ref:
            return self.resolved_type.fq_cpp_ref()
        else:
            return self.resolved_type.impl_cpp_type

    def generate_accessor_declarations(self, file, indent):
        writeln(file, "// [" + str(self.id) + "] " + self.name, indent)
        if self.is_builtin and not self.is_container():
            # These accessors take built-in args by value.
            writeln(file,
                    self.cpp_type_ref() + " " + self.name + "() const;",
                    indent)
            writeln(file,
                    "void set_" + self.name + "(" + self.cpp_type_ref() + ");",
                    indent)
        elif self.is_enum and not self.is_container():
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
            if not args.omit_deprecated:
                writeln(file,
                        "/* deprecated */ auto mutable_" + self.name + "() { " + \
                            " return &" + self.name + "(); }",
                        indent)

        if not self.is_container():
            writeln(file, "void clear_" + self.name + "();", indent)

        if self.is_container() and not args.omit_deprecated:
            writeln(file,
                    "/* deprecated */ " + "void clear_" + self.name + "() { " + \
                        self.name + "().clear(); }",
                    indent)
        if self.is_repeated and not args.omit_deprecated:
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
        if self.is_builtin and not self.is_container():
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
        elif self.is_enum and not self.is_container():
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

        if not self.is_container():
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

        if self.is_repeated and not args.omit_deprecated:
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
        if self.is_algebraic and not self.is_container():
            writeln(file, cpp_impl_type(self.raw_type) + " " + self.name + " = 0;", 1)
        elif self.is_builtin and not self.is_container():
            writeln(file, cpp_impl_type(self.raw_type) + " " + self.name + ";", 1)
        elif self.is_enum and not self.is_container():
            writeln(file, self.cpp_type_ref() + " " + self.name + " = " + \
                self.initializer() + ";", 1)
        else:
            writeln(file, self.cpp_type_ref() + " " + self.name + ";", 1)