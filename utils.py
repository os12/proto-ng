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
