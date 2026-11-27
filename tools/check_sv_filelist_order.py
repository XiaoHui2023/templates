"""Require generated project types before their first cross-file use."""

from check_sv_declaration_ownership import TOKEN


def check_type_order(files, paths):
    """Check one flat, ordered compilation unit without forward declarations."""
    paths = tuple(paths)
    declared = {}
    references = {}
    for path in paths:
        tokens = [match.group() for match in TOKEN.finditer(files[path]) if match.lastgroup == "value"]
        references[path] = dict.fromkeys(tokens)
        for index, token in enumerate(tokens[:-1]):
            previous = tokens[index - 1] if index else None
            is_class = token == "class" and previous != "typedef"
            is_interface = token == "interface" and previous != "virtual" and tokens[index + 1] != "class"
            if not (is_class or is_interface):
                continue
            name = tokens[index + 1]
            if name in declared:
                raise ValueError(f"duplicate project type {name}: {declared[name]} and {path}")
            declared[name] = path

    compiled = set()
    for path in paths:
        for name in references[path]:
            owner = declared.get(name)
            if owner is not None and owner != path and owner not in compiled:
                raise ValueError(f"{path}: {name} used before {owner} in all.f")
        compiled.add(path)


def self_test():
    files = {
        "provider.sv": "virtual class sequencer; int value; endclass",
        "consumer.sv": "class request_item; `uvm_declare_p_sequencer(sequencer) endclass",
    }
    check_type_order(files, files)
    try:
        check_type_order(files, reversed(files))
    except ValueError as error:
        if "used before" in str(error):
            return
        raise
    raise AssertionError("declaration order accepted an actual macro consumer before its provider")
