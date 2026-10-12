"""Equivalent typed import selectors with an optional balanced one-hot bus."""


def emit(fields, onehot=False):
    assert len({slot for slot, _ in fields}) == len(fields)
    if not onehot:
        return "".join(
            f"if cfg_transfer_slot == {slot}:\n    cfg_setup_data = {name}\n"
            for slot, name in fields
        )
    terms, text = [], ""
    for i, (slot, name) in enumerate(fields):
        term = f"cfg_import_term_{i}"
        terms.append(term)
        text += (
            f"{term}: uint64_t = 0\nif cfg_transfer_slot == {slot}:\n"
            f"    {term} = {name}\n"
        )

    def balanced(values):
        if not values:
            return "0"
        if len(values) == 1:
            return values[0]
        mid = len(values) // 2
        return "(" + balanced(values[:mid]) + " | " + balanced(values[mid:]) + ")"

    return text + "cfg_setup_data = " + balanced(terms) + "\n"
