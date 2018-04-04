#
# Utils
#
def log(verbosity, msg):
    if args.verbosity >= verbosity:
        print(msg)

def indent(level):
    return "    " * level

def indent_from_scope(fq_name):
    if not fq_name:
        return ""
    level = fq_name.count('.')
    return indent(level)

def writeln(file, line, indent = 0):
    file.write("  " * indent + line + "\n")

def write_blank_if(file, collection):
    if len(collection) > 0:
        writeln(file, "")
