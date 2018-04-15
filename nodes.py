import sys

import gen, utils
from utils import indent_from_scope, writeln, log

#
# AST nodes
#

class Node:
    def __init__(self):
        self.parent = None
        self.fq_name = None

class File(Node, gen.File):
    def __init__(self, full_fs_path, include, parent):
        Node.__init__(self)
        gen.File.__init__(self)

        self.parent = parent
        self.path = full_fs_path
        self.include = include
        self.namespace = ""
        self.syntax = None

        # AST that lives within this file
        self.statements = []
        self.options = []
        self.messages = {}
        self.extends = {}
        self.enums = {}

        # AST for imported files as well as the flat set of all of the imported types
        self.imports = {}
        self.imported_type_names = set()

        # A cache of FQ typenames that live within this file
        self.typenames = {}

        assert(self.path)
        assert(self.path.count('\\') == 0), "Got a Windows path: " + self.path

    def filename(self):
        return self.path.split("/")[-1]

    def cpp_include_path(self):
        assert(self.path[-6:] == ".proto")

        # Drop the "include" path from the full path as the C++ environment must have -I options
        # configured in a way compatible to that of protobuf.
        path = self.path
        inc_pos = path.find(self.include)
        if inc_pos != -1:
            assert(inc_pos == 0), "pos: " + str(inc_pos)
            path = path[len(self.include):]

        global args
        return path[0:-5] + args.file_extension + ".h"

    def store_external_typename_ref(self, fq_type_name):
        # Ideally, this typename should be stored against the import, but I don't know
        # how to deal with transitive imports... so, let's just maintain a flat set.
        self.imported_type_names.add(fq_type_name)

    def as_string(self):
        s = ""

        global args
        if args.with_verbose_imports:
            for file_name, ast in self.imports.items():
                s += ast.as_string()

        s += "\nAST for " + self.filename() + ", namespace=" + \
            (self.namespace or "") + "\n\n"

        # Enums
        for name, enum in self.enums.items():
            s += enum.as_string(self.namespace) + "\n"

        # Messages/extends
        for name, msg in self.messages.items():
            s += msg.as_string(self.namespace)
        for name, msg in self.extends.items():
            s += msg.as_string(self.namespace)

        return s

    # Looks for the given fully-qualified field type 'ftype' in a top->down fashion by
    # resolving every segment of the type's string.
    def resolve_type(self, source_ns, typename):
        assert(typename)

        def search_file(ast, source_ns, typename):
            if typename in ast.typenames:
                return ast.typenames[typename]

            # 1. see whether this typename is known (it would be a FQ typename)
            for file_name, file_ast in ast.imports.items():
                if typename in file_ast.typenames:
                    return file_ast.typenames[typename]

            # 2. then take the common namespace prefix off and see whether the remainder is known
            for file_name, file_ast in ast.imports.items():
                src_parts = source_ns.split(".")
                dst_parts = file_ast.namespace.split(".")
                prefix_parts = []
                while len(src_parts) > 0 and len(dst_parts) > 0:
                    if src_parts[0] != dst_parts[0]:
                        break
                    prefix_parts.append(src_parts.pop(0))
                    dst_parts.pop(0)
                if len(prefix_parts) > 0:
                    guess = ".".join(prefix_parts) + "." + typename
                    if guess in file_ast.typenames:
                        return file_ast.typenames[guess]

            return None

        # 1. See whether this is a partial qualification "d.e" that is made from "a.b.c.d.e.f.g"
        if typename.count(".") > 0:
            front = typename.split(".")[0]
            hacked_ns_parts = source_ns.split(".")
            if front != hacked_ns_parts[0] and front in hacked_ns_parts:
                while hacked_ns_parts[-1] != front:
                    hacked_ns_parts.pop(-1)
                assert(len(hacked_ns_parts) > 1)
                assert(hacked_ns_parts[-1] == front)
                hacked_ns_parts.pop(-1)
                return search_file(self, ".".join(hacked_ns_parts), typename)

        # 2. Search for the typename as is.
        return search_file(self, source_ns, typename)

    def set_cpp_type_names(self):
        assert(self.namespace)

        for _, enum in self.enums.items():
            enum.ns = "::".join(self.namespace.split("."))
            enum.impl_cpp_type = enum.name()

        for _, msg in self.messages.items():
            msg.set_cpp_type_names("::".join(self.namespace.split(".")), "")

    def verify_type_references(self):
        for _, msg in self.messages.items():
            msg.verify_type_references(self)

    def build_typename_cache(self):
        for _, enum in self.enums.items():
            enum.build_typename_cache(self.typenames)

        for _, msg in self.messages.items():
            msg.build_typename_cache(self.typenames)


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
        self.extends = {}
        self.min_extension_id = None    # set when extensions are enabled for is message

        self.impl_cpp_type = None
        self.is_extend = False

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

    def cpp_extend_namespace(self):
        assert(self.is_extend)
        return "::".join(self.fq_name.split(".")[0:-1])

    def is_file_scope(self):
        assert(self.parent)
        return type(self.parent) == File

    def build_typename_cache(self, cache):
        assert(self.fq_name not in cache)
        cache[self.fq_name] = self

        for _, enum in self.enums.items():
            enum.build_typename_cache(cache)

        for _, msg in self.messages.items():
            msg.build_typename_cache(cache)

    def as_string(self, namespace):
        assert(namespace)
        assert(namespace[-1] != '.')

        if not self.is_extend:
            assert(namespace + "." + self.name() == self.fq_name), \
                "namespace=" + namespace + ", fq_name=" + self.fq_name

        s = indent_from_scope(namespace)
        if self.is_extend:
            s += "Extend: " + self.print_name()
        else:
            s += "Message: " + self.print_name()
        if self.is_extend:
            s += " (extend)"
        if self.impl_cpp_type:
            s+= " // " + self.impl_cpp_type
        s += "\n"

        # Fields
        for _, field in self.fields.items():
            s += field.as_string(namespace + "." + self.name()) + "\n"

        # Enums
        for _, enum in self.enums.items():
            s += enum.as_string(namespace + "." + self.name()) + "\n"

        # Sub-messages
        for _, msg in self.messages.items():
            s += msg.as_string(namespace + "." + self.name())

        # Extensions
        for _, msg in self.extends.items():
            s += msg.as_string(namespace + "." + self.name())

        return s

    # Looks for the given fully-qualified field type 'ftype' in a top->down fashion by
    # resolving every segment of the type's string.
    def resolve_type(self, source_ns, fq_type):
        assert(fq_type)

        parts = fq_type.split('.')
        assert(len(parts) > 0)
        front = parts.pop(0)
        assert(front)
        assert(front == self.name())

        if len(parts) == 0: return self

        if len(parts) == 1 and parts[0] in self.enums:
            return self.enums[parts[0]]

        if parts[0] in self.messages:
            return self.messages[parts[0]].resolve_type(source_ns, ".".join(parts))

        return None

    def set_cpp_type_names(self, ns, prefix):
        self.ns = ns
        self.impl_cpp_type = prefix + self.name()

        for _, enum in self.enums.items():
            enum.ns = ns
            enum.impl_cpp_type = prefix + self.name() + "_" + enum.name()

        for _, sub_msg in self.messages.items():
            sub_msg.set_cpp_type_names(ns, prefix + self.name() + "_")

    def verify_type_references(self, file):
        # Verify each field
        for _, field in self.fields.items():
            field.verify_type_references(file)

        # Descend into every sub-message
        for _, sub_msg in self.messages.items():
            sub_msg.verify_type_references(file)

class Enum(Node, gen.Enum):
    def __init__(self, fq_name, is_package_global):
        Node.__init__(self)
        gen.Enum.__init__(self)

        self.ns = ""
        self.fq_name = fq_name
        self.values = {}
        self.options = []
        self.impl_cpp_type = None
        self.is_package_global = is_package_global

    def name(self):
        assert(self.fq_name)
        return self.fq_name.split('.')[-1]

    def fq_cpp_ref(self):
        return self.ns + "::" + self.impl_cpp_type

    def print_name(self):
        global args
        if args.fq:
            return self.fq_name
        else:
            return self.name()

    def build_typename_cache(self, cache):
        assert(self.fq_name not in cache)
        cache[self.fq_name] = self

    def as_string(self, namespace):
        assert(namespace)
        assert(namespace[-1] != '.')
        assert(namespace + "." + self.name() == self.fq_name)

        rv = indent_from_scope(namespace) + "Enum: " + self.print_name() + \
            "(" + ", ".join(self.values.values()) + ")"
        if self.impl_cpp_type:
            rv += " // " + self.impl_cpp_type
        return rv


class Field(Node, gen.Field):
    algebraic_types = ['int32', 'uint32', 'int64', 'uint64', 'double', 'float', 'bool']
    string_types = ['string', 'bytes']

    def __init__(self, name, id, raw_type, resolved_type, specifier, mapped_type = None):
        Node.__init__(self)
        gen.Field.__init__(self)

        self.name = name
        self.id = id
        self.options = {}

        self.raw_type = raw_type
        self.resolved_type = resolved_type

        self.is_forward_decl = False
        self.is_map = False
        self.is_repeated = False

        self.is_enum = False
        if self.raw_type in Field.algebraic_types:
            self.is_builtin = True
            self.is_algebraic = True
        elif self.raw_type in Field.string_types:
            self.is_builtin = True
            self.is_algebraic = False
        else:
            self.is_builtin = False
            self.is_algebraic = False
        self.is_repeated = False
        self.is_fq_ref = False
        if specifier == "repeated":
            self.is_repeated = True
        elif specifier == "map":
            self.is_map = True
            assert(mapped_type)
            self.mapped_type = mapped_type
            self.is_builtin = False

    def is_container(self):
        return self.is_repeated or self.is_map

    def as_string(self, namespace):
        global args

        assert(namespace)
        assert(namespace[-1] != '.')

        rv = indent_from_scope(namespace) + \
            "[" + str(self.id) + "] " + self.name + " : "

        if self.is_map:
            rv += "<" + self.raw_type + ", "
            if self.resolved_type:
                if args.fq:
                    rv += self.resolved_type.print_name()
                else:
                    rv += self.mapped_type
            else:
                rv += self.mapped_type
            rv += ">"
        else:
            if self.resolved_type:
                if args.fq:
                    rv += self.resolved_type.print_name()
                else:
                    rv += self.raw_type
            else:
                rv += self.raw_type

        return rv + (" (enum)" if self.is_enum else "") + \
                (" (repeated)" if self.is_repeated else "") + \
                (" (map)" if self.is_map else "")

    def verify_type_references(self, file_node):
        if self.is_builtin: return
        if self.resolved_type: return

        assert(file_node)
        assert(type(file_node) is File)
        assert(file_node.namespace)

        if self.is_map:
            assert(self.resolved_type or
                   self.mapped_type in Field.algebraic_types + Field.string_types)
            return

        resolved_type = find_type(self.parent, self.raw_type)
        if not resolved_type:
            resolved_type = file_node.resolve_type(file_node.namespace, self.raw_type)
            if not resolved_type:
                this_file_node = find_file_parent(self.parent)
                resolved_type = this_file_node.resolve_type(this_file_node.namespace,
                                                            self.raw_type)
        if not resolved_type:
            sys.exit('Error: failed to resolve type: "' + self.raw_type + '" in ' +
                     file_node.path + ' for the following field: "' + self.name + '"')

        assert(utils.is_suffix(resolved_type.fq_name, self.raw_type))

        file_node.store_external_typename_ref(resolved_type.fq_name)

        assert(resolved_type.fq_name[-len(self.raw_type):] == self.raw_type)
        self.resolved_type = resolved_type
        log(2, "[parser] resolved a forward-declared field: " + self.name + " to " +
            resolved_type.fq_name)


# Looks for the given field type 'typname' in the ever-widening message scopes (from inside
# out) in the current translation unit.
#
# This function finds anything that can be used as a field:
#   - message
#   - enum
def find_type(ast, typename):
    if not ast:
        return None

    assert(typename.count("::") == 0)
    parts = typename.split(".")
    assert(len(parts) >= 1)
    front = parts.pop(0)

    if front in ast.messages:
        msg = ast.messages[front]
        if len(parts) == 0:
            return msg
        return msg.resolve_type("[foobar-unused]", msg.name() + "." + ".".join(parts))

    if front in ast.enums:
        if len(parts) == 0:
            return ast.enums[front]
        return None

    return find_type(ast.parent, typename)

def find_top_parent(ast):
    assert(ast)
    if not ast.parent:
        return ast
    return find_top_parent(ast.parent)

def find_file_parent(ast):
    assert(ast)
    if type(ast) == File:
        return ast
    return find_file_parent(ast.parent)
