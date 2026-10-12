"""Typed packet utilities shared by native experiment checks."""

BASE_REQUEST = [
    "graph_addr",
    "graph_lo",
    "graph_hi",
    "graph_write",
    "control_addr",
    "control_lo",
    "control_hi",
    "control_tag",
    "control_write",
]
BASE_RESPONSE = ["graph_lo", "graph_hi", "control_lo", "control_hi", "control_tag"]


def request_fields(m):
    return BASE_REQUEST + [
        name + "_addr" for name, _ in m.get("publication_reads", {}).get("banks", [])
    ]


def response_fields(m):
    return BASE_RESPONSE + [
        f["name"] for f in m.get("publication_reads", {}).get("responses", [])
    ]


def construct(typ, prefix, values):
    if prefix in values:
        return values[prefix]
    if not hasattr(typ, "_fields"):
        # Fields absent from the extracted interface are neither read nor
        # written; complete the typed source fixture with zero for those leaves.
        return 0
    return typ(
        **{
            field: construct(typ.__annotations__[field], prefix + "." + field, values)
            for field in typ._fields
        }
    )


def sidecars(hw, m, response):
    spec = m.get("publication_reads", {})
    values = {
        f["bank"] + f["suffix"]: value
        for f, value in zip(spec.get("responses", []), response[5:], strict=True)
    }
    return [
        construct(getattr(hw, dtype), name, values)
        for name, dtype in spec.get("banks", [])
    ]
