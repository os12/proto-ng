from utils import writeln, write_blank_if

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

class Enum:
    def __init__(self, *args, **kwargs):
        super(Enum, self).__init__(*args, **kwargs)

    def generate_header(self, file, indent):
        writeln(file, "enum " + self.name() + " {", indent)

        for id, value in self.values.items():
            writeln(file, value + " = " + str(id) + ",", indent + 1)

        writeln(file, "};", indent)


class Message:
    def __init__(self, *args, **kwargs):
        super(Message, self).__init__(*args, **kwargs)

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


class Field:
    def __init__(self, *args, **kwargs):
        super(Field, self).__init__(*args, **kwargs)

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
            if not args.omit_deprecated:
                writeln(file,
                        "/* deprecated */ auto mutable_" + self.name + "() { " + \
                            " return &" + self.name + "(); }",
                        indent)

        if not self.is_repeated:
            writeln(file, "void clear_" + self.name + "();", indent)

        if self.is_repeated and not args.omit_deprecated:
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
        if self.is_algebraic and not self.is_repeated:
            writeln(file, cpp_impl_type(self.raw_type) + " " + self.name + " = 0;", 1)
        elif self.is_builtin and not self.is_repeated:
            writeln(file, cpp_impl_type(self.raw_type) + " " + self.name + ";", 1)
        elif self.is_enum and not self.is_repeated:
            writeln(file, self.cpp_type_ref() + " " + self.name + " = " + \
                self.initializer() + ";", 1)
        else:
            writeln(file, self.cpp_type_ref() + " " + self.name + ";", 1)