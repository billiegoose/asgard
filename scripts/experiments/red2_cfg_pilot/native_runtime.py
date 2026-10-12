"""Keep long physical-cycle simulations from accumulating scalar type classes."""

import functools


def cache_scalar_types(py):
    original = py._make_ctype
    if getattr(original, "_red2_scalar_cache", False):
        return
    scalar = functools.cache(original)

    def cached(name):
        # Array descriptors carry mutable factory metadata; leave them uncached.
        if (
            name.startswith(("uint", "int"))
            and name.endswith("_t")
            and name.removesuffix("_t")
            .removeprefix("uint")
            .removeprefix("int")
            .isdigit()
        ):
            return scalar(name)
        return original(name)

    cached._red2_scalar_cache = True
    py._make_ctype = cached
