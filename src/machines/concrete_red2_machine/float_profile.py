"""RED2_FLOAT_V1: the bounded binary64 profile shared with Pypeline hardware.

This is intentionally *not* a full IEEE-754 implementation.  It mirrors the
common-case arithmetic shape in PipelineC/Pypeline's ``floating_point.py``:
normal finite binary64 values plus signed zero, truncating mantissa operations,
and no special support for subnormals, infinities, NaNs, or IEEE rounding.

Keeping this reference model bit-oriented is important: Concrete must not gain
an invisible Python-host FPU whose results Synth cannot reproduce.
"""

from __future__ import annotations


RED2_FLOAT_V1 = 1

FLOAT64_EXP_BITS = 11
FLOAT64_MAN_BITS = 52
FLOAT64_SIGN_SHIFT = 63
FLOAT64_EXP_SHIFT = FLOAT64_MAN_BITS
FLOAT64_EXP_MASK = (1 << FLOAT64_EXP_BITS) - 1
FLOAT64_MAN_MASK = (1 << FLOAT64_MAN_BITS) - 1
FLOAT64_HIDDEN = 1 << FLOAT64_MAN_BITS
FLOAT64_BIAS = (1 << (FLOAT64_EXP_BITS - 1)) - 1
FLOAT64_ONE = FLOAT64_BIAS << FLOAT64_EXP_SHIFT
FLOAT64_PAYLOAD_MASK = (1 << 64) - 1


def parts(bits: int) -> tuple[int, int, int]:
    bits &= FLOAT64_PAYLOAD_MASK
    return (
        (bits >> FLOAT64_SIGN_SHIFT) & 1,
        (bits >> FLOAT64_EXP_SHIFT) & FLOAT64_EXP_MASK,
        bits & FLOAT64_MAN_MASK,
    )


def pack(sign: int, exp: int, man: int) -> int:
    return (
        ((sign & 1) << FLOAT64_SIGN_SHIFT)
        | ((exp & FLOAT64_EXP_MASK) << FLOAT64_EXP_SHIFT)
        | (man & FLOAT64_MAN_MASK)
    )


def is_zero(bits: int) -> bool:
    _, exp, man = parts(bits)
    return exp == 0 and man == 0


def is_supported(bits: int) -> bool:
    """Return whether RED2_FLOAT_V1 accepts this encoded operand/result."""

    _, exp, man = parts(bits)
    if exp == FLOAT64_EXP_MASK:  # inf / NaN excluded from the hardware profile
        return False
    if exp == 0 and man != 0:  # subnormal excluded; signed zero is supported
        return False
    return True


def negate(bits: int) -> int:
    return bits ^ (1 << FLOAT64_SIGN_SHIFT)


def absolute(bits: int) -> int:
    return bits & ~(1 << FLOAT64_SIGN_SHIFT)


def int_to_bits(value: int) -> int:
    """Pypeline-style signed integer -> binary64 conversion (truncate, no round)."""

    if value == 0:
        return 0
    sign = int(value < 0)
    magnitude = -value if value < 0 else value
    true_exp = magnitude.bit_length() - 1
    exp = true_exp + FLOAT64_BIAS
    if true_exp <= FLOAT64_MAN_BITS:
        hidden = magnitude << (FLOAT64_MAN_BITS - true_exp)
    else:
        hidden = magnitude >> (true_exp - FLOAT64_MAN_BITS)
    return pack(sign, exp, hidden & FLOAT64_MAN_MASK)


def trunc_to_int(bits: int) -> int:
    """Pypeline-style float -> integer conversion, truncating toward zero."""

    sign, exp, man = parts(bits)
    if exp == 0:
        return 0
    true_exp = exp - FLOAT64_BIAS
    if true_exp < 0:
        magnitude = 0
    else:
        hidden = FLOAT64_HIDDEN | man
        if true_exp >= FLOAT64_MAN_BITS:
            magnitude = hidden << (true_exp - FLOAT64_MAN_BITS)
        else:
            magnitude = hidden >> (FLOAT64_MAN_BITS - true_exp)
    return -magnitude if sign else magnitude


def integral_value(bits: int) -> int | None:
    """Return the exact integer represented by ``bits``, or None if fractional."""

    sign, exp, man = parts(bits)
    if exp == 0:
        return 0
    true_exp = exp - FLOAT64_BIAS
    hidden = FLOAT64_HIDDEN | man
    if true_exp < 0:
        return None
    if true_exp >= FLOAT64_MAN_BITS:
        magnitude = hidden << (true_exp - FLOAT64_MAN_BITS)
    else:
        shift = FLOAT64_MAN_BITS - true_exp
        discarded_mask = (1 << shift) - 1
        if hidden & discarded_mask:
            return None
        magnitude = hidden >> shift
    return -magnitude if sign else magnitude


def floor_to_int(bits: int) -> int:
    sign, exp, man = parts(bits)
    if exp == 0:
        return 0
    true_exp = exp - FLOAT64_BIAS
    hidden = FLOAT64_HIDDEN | man
    if true_exp < 0:
        return -1 if sign else 0
    if true_exp >= FLOAT64_MAN_BITS:
        magnitude = hidden << (true_exp - FLOAT64_MAN_BITS)
        return -magnitude if sign else magnitude
    shift = FLOAT64_MAN_BITS - true_exp
    magnitude = hidden >> shift
    fractional = bool(hidden & ((1 << shift) - 1))
    if sign:
        return -magnitude - int(fractional)
    return magnitude


def ceil_to_int(bits: int) -> int:
    sign, exp, man = parts(bits)
    if exp == 0:
        return 0
    true_exp = exp - FLOAT64_BIAS
    hidden = FLOAT64_HIDDEN | man
    if true_exp < 0:
        return 0 if sign else 1
    if true_exp >= FLOAT64_MAN_BITS:
        magnitude = hidden << (true_exp - FLOAT64_MAN_BITS)
        return -magnitude if sign else magnitude
    shift = FLOAT64_MAN_BITS - true_exp
    magnitude = hidden >> shift
    fractional = bool(hidden & ((1 << shift) - 1))
    if sign:
        return -magnitude
    return magnitude + int(fractional)


def compare(left: int, right: int) -> int:
    """Numeric comparison for supported finite-normal/zero payloads."""

    if is_zero(left) and is_zero(right):
        return 0
    ls, le, lm = parts(left)
    rs, re, rm = parts(right)
    if ls != rs:
        return -1 if ls else 1
    lmag = (le, lm)
    rmag = (re, rm)
    if lmag == rmag:
        return 0
    if ls:
        return -1 if lmag > rmag else 1
    return 1 if lmag > rmag else -1


def add(left: int, right: int) -> int | None:
    """Mirror Pypeline ``make_float_adder`` for binary64 common cases."""

    ls, le, lm = parts(left)
    rs, re, rm = parts(right)
    if re > le:
        xs, xe, xm, ys, ye, ym = rs, re, rm, ls, le, lm
    else:
        xs, xe, xm, ys, ye, ym = ls, le, lm, rs, re, rm

    x_hidden = (FLOAT64_HIDDEN if xe != 0 else 0) | xm
    y_hidden = (FLOAT64_HIDDEN if ye != 0 else 0) | ym
    x_signed = -x_hidden if xs else x_hidden
    y_signed = -y_hidden if ys else y_hidden
    y_aligned = y_signed >> (xe - ye)
    total = x_signed + y_aligned
    total_sign = int(total < 0)
    total_abs = -total if total < 0 else total

    if total_abs == 0:
        result = pack(total_sign, 0, 0)
    elif total_abs & (1 << (FLOAT64_MAN_BITS + 1)):
        result = pack(
            total_sign,
            xe + 1,
            (total_abs >> 1) & FLOAT64_MAN_MASK,
        )
    else:
        width = FLOAT64_MAN_BITS + 1
        leading_zeros = width - total_abs.bit_length()
        result_exp = xe - leading_zeros
        shifted = (total_abs << leading_zeros) & ((1 << width) - 1)
        result = pack(total_sign, result_exp, shifted & FLOAT64_MAN_MASK)
    return result if is_supported(result) else None


def sub(left: int, right: int) -> int | None:
    return add(left, negate(right))


def mul(left: int, right: int) -> int | None:
    """Mirror Pypeline ``make_float_multiplier`` for binary64 common cases."""

    ls, le, lm = parts(left)
    rs, re, rm = parts(right)
    sign = ls ^ rs
    if le == 0 or re == 0:
        return pack(sign, 0, 0)
    l_hidden = FLOAT64_HIDDEN | lm
    r_hidden = FLOAT64_HIDDEN | rm
    product = l_hidden * r_hidden
    combined_exp = le + re - FLOAT64_BIAS
    top_bit = bool(product & (1 << (2 * (FLOAT64_MAN_BITS + 1) - 1)))
    if top_bit:
        result_exp = combined_exp + 1
        result_man = (product >> (FLOAT64_MAN_BITS + 1)) & FLOAT64_MAN_MASK
    else:
        result_exp = combined_exp
        result_man = (product >> FLOAT64_MAN_BITS) & FLOAT64_MAN_MASK
    if not 0 < result_exp < FLOAT64_EXP_MASK:
        return None
    result = pack(sign, result_exp, result_man)
    return result if is_supported(result) else None


def div(left: int, right: int) -> int | None:
    """Mirror Pypeline ``make_float_divider`` for binary64 common cases."""

    ls, le, lm = parts(left)
    rs, re, rm = parts(right)
    sign = ls ^ rs
    if re == 0:
        return None  # RED2 rejects division by zero instead of Pypeline's flush.
    if le == 0:
        return pack(sign, 0, 0)
    l_hidden = FLOAT64_HIDDEN | lm
    r_hidden = FLOAT64_HIDDEN | rm
    quotient = (l_hidden << (FLOAT64_MAN_BITS + 1)) // r_hidden
    biased_exp = le + FLOAT64_BIAS - re
    if biased_exp <= 0:
        return None
    if quotient & (1 << (FLOAT64_MAN_BITS + 1)):
        hidden = (quotient >> 1) & ((1 << (FLOAT64_MAN_BITS + 1)) - 1)
        final_exp = biased_exp
    else:
        hidden = quotient & ((1 << (FLOAT64_MAN_BITS + 1)) - 1)
        final_exp = biased_exp - 1
    if not 0 < final_exp < FLOAT64_EXP_MASK:
        return None
    result = pack(sign, final_exp, hidden & FLOAT64_MAN_MASK)
    return result if is_supported(result) else None


def pow_integral(base: int, exponent: int) -> int | None:
    """Integer-exponent power using only the profile's mul/div operations."""

    if exponent == 0:
        return FLOAT64_ONE
    invert = exponent < 0
    remaining = -exponent if invert else exponent
    result = FLOAT64_ONE
    factor = base
    while remaining:
        if remaining & 1:
            result = mul(result, factor)
            if result is None:
                return None
        remaining >>= 1
        if remaining:
            factor = mul(factor, factor)
            if factor is None:
                return None
    if invert:
        return div(FLOAT64_ONE, result)
    return result
