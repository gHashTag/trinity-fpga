#!/usr/bin/env python3
"""Independent check of the Fibonacci-product / Lucas identity

    F_m * F_n = (L_{m+n} - (-1)^n * L_{m-n}) / 5

cited in research/frontier/CLOSURE_MEASURED_2026-08-10.md (line ~65) as the
reason a Zeckendorf-normalised multiplier would have been a strawman opponent:
the product of two Fibonacci numbers is two Lucas-table lookups, a subtract and
a divide by five.

That document said the identity was "verified over 300 index pairs". No script
for it existed in this repository -- research/verify_lucas_exact.py checks a
DIFFERENT identity (phi^(2n) + phi^(-2n) == L_(2n)). This file is the missing
check.

Method
------
  * Everything is exact Python integer arithmetic. No float, no Decimal, no
    tolerance: the claim is an identity over the integers, so the only honest
    verdict is bit-equality.
  * F and L come from their own recurrences (F_0=0, F_1=1; L_0=2, L_1=1), not
    from Binet, so phi never enters and the check is independent of the
    project's phi code.
  * m - n is negative for half the sweep. The negative index is resolved by the
    standard reflection L_{-k} = (-1)^k * L_k, which is exercised on 32,640 of
    the pairs below rather than avoided by restricting to m >= n.
  * The divide by five is checked as an exact divisibility (divmod remainder
    must be 0), because a hardware path that divides by five only works if the
    numerator is always a multiple of five. A version that got the right
    quotient by truncation would be a different, weaker claim.

Falsifiability
--------------
A check that cannot fail proves nothing, so the same sweep is re-run against
three deliberately broken forms of the identity, each of which must mismatch:

  P1  drop the (-1)^n sign factor          -> (L_{m+n} - L_{m-n})/5
  P2  use the wrong exponent, (-1)^m       -> (L_{m+n} - (-1)^m L_{m-n})/5
  P3  drop the reflection, L_{-k} = +L_k   (true form otherwise)

P1 and P3 are the two errors most likely to be made when transcribing this
identity into RTL; P2 is the near-miss that a sweep restricted to m == n or to
even indices would fail to catch.

Run:  python3 research/verify_lucas_product.py
Exit: 0 if the true identity holds on every pair AND all three perturbations
      are caught; 1 otherwise.
"""
from __future__ import annotations

N_MAX = 255  # sweep m, n over 0..N_MAX inclusive -> (N_MAX+1)^2 ordered pairs


def fib_upto(k_max: int) -> list[int]:
    """Exact F_0..F_k_max."""
    f = [0, 1]
    while len(f) <= k_max:
        f.append(f[-1] + f[-2])
    return f[: k_max + 1]


def lucas_upto(k_max: int) -> list[int]:
    """Exact L_0..L_k_max."""
    ell = [2, 1]
    while len(ell) <= k_max:
        ell.append(ell[-1] + ell[-2])
    return ell[: k_max + 1]


def lucas_signed(ell: list[int], k: int) -> int:
    """L_k for any integer k, using L_{-k} = (-1)^k * L_k."""
    if k >= 0:
        return ell[k]
    k = -k
    return ell[k] if k % 2 == 0 else -ell[k]


def lucas_unsigned(ell: list[int], k: int) -> int:
    """PERTURBATION P3: reflection dropped, L_{-k} treated as +L_k."""
    return ell[abs(k)]


def sweep(fib, ell, *, sign_exponent: str, reflect: bool):
    """Run the full (m, n) sweep for one variant of the identity.

    sign_exponent: 'n' (true), 'm' (P2), or 'none' (P1, factor forced to +1)
    reflect:       True (true rule) or False (P3, L_{-k} = +L_k)

    Returns (checked, mismatches, not_divisible, first_failures).
    """
    look = lucas_signed if reflect else lucas_unsigned
    checked = 0
    mismatches = 0
    not_divisible = 0
    first_failures = []

    for m in range(N_MAX + 1):
        f_m = fib[m]
        for n in range(N_MAX + 1):
            checked += 1
            lhs = f_m * fib[n]

            if sign_exponent == "n":
                sign = -1 if n % 2 else 1
            elif sign_exponent == "m":
                sign = -1 if m % 2 else 1
            else:  # 'none'
                sign = 1

            numerator = look(ell, m + n) - sign * look(ell, m - n)
            quotient, remainder = divmod(numerator, 5)

            bad = False
            if remainder != 0:
                not_divisible += 1
                bad = True
            if quotient != lhs or remainder != 0:
                mismatches += 1
                bad = True
            if bad and len(first_failures) < 5:
                first_failures.append(
                    f"m={m} n={n}: F_m*F_n={lhs} but "
                    f"(numerator={numerator}) /5 -> q={quotient} r={remainder}"
                )

    return checked, mismatches, not_divisible, first_failures


def main() -> int:
    fib = fib_upto(N_MAX)
    ell = lucas_upto(2 * N_MAX)

    total_pairs = (N_MAX + 1) ** 2
    neg_index_pairs = sum(1 for m in range(N_MAX + 1) for n in range(N_MAX + 1) if m - n < 0)

    print("identity : F_m * F_n == (L_{m+n} - (-1)^n * L_{m-n}) / 5")
    print("negative : L_{-k} = (-1)^k * L_k")
    print(f"range    : m, n = 0 .. {N_MAX}  (ordered pairs, both directions)")
    print(f"arithmetic: exact Python integers, no tolerance")
    print()
    print(f"pairs in sweep            : {total_pairs}")
    print(f"  of which m - n < 0      : {neg_index_pairs}   (exercise the reflection rule)")
    print(f"  of which m - n == 0     : {N_MAX + 1}")
    print(f"largest Lucas index used  : L_{2 * N_MAX} ({len(str(ell[2 * N_MAX]))} digits)")
    print()

    # Worked examples, so a reader can check one by hand.
    for m, n in ((5, 3), (3, 5), (8, 8), (7, 0)):
        lhs = fib[m] * fib[n]
        sign = -1 if n % 2 else 1
        num = lucas_signed(ell, m + n) - sign * lucas_signed(ell, m - n)
        print(f"  example m={m} n={n}: F_{m}*F_{n} = {lhs}; "
              f"(L_{m+n} - ({sign})*L_{{{m-n}}}) = {num}; /5 = {num // 5}")
    print()

    checked, mismatches, not_div, failures = sweep(
        fib, ell, sign_exponent="n", reflect=True
    )
    print("== TRUE IDENTITY ==")
    print(f"checked           : {checked}")
    print(f"mismatches        : {mismatches}")
    print(f"numerator not / 5 : {not_div}")
    for line in failures:
        print(f"  FAIL {line}")
    print()

    # --- falsifiability: the same sweep against broken forms -----------------
    perturbations = [
        ("P1 drop (-1)^n           ", dict(sign_exponent="none", reflect=True)),
        ("P2 wrong exponent (-1)^m ", dict(sign_exponent="m", reflect=True)),
        ("P3 drop L_{-k} reflection", dict(sign_exponent="n", reflect=False)),
    ]
    print("== PERTURBATIONS (each MUST mismatch, or this check proves nothing) ==")
    uncaught = []
    for label, kwargs in perturbations:
        p_checked, p_mis, p_nd, p_fail = sweep(fib, ell, **kwargs)
        verdict = "CAUGHT" if p_mis else "NOT CAUGHT"
        pct = 100.0 * p_mis / p_checked
        print(f"{label}: {p_mis}/{p_checked} mismatched ({pct:.1f}%), "
              f"{p_nd} non-divisible  -> {verdict}")
        if p_fail:
            print(f"    first: {p_fail[0]}")
        if not p_mis:
            uncaught.append(label)
    print()

    ok = (mismatches == 0) and (not_div == 0) and not uncaught
    if mismatches or not_div:
        print(f"RESULT: FAIL -- the identity does NOT hold on {mismatches} of "
              f"{checked} pairs.")
    elif uncaught:
        print(f"RESULT: INCONCLUSIVE -- perturbation(s) {uncaught} were not "
              f"caught, so the sweep is not sensitive to that error.")
    else:
        print(f"RESULT: identity holds on all {checked} pairs, exactly, in "
              f"integer arithmetic,")
        print(f"        and all three perturbed forms are detected.")
    print()
    print("SCOPE : this verifies the MATHEMATICAL identity only. It does not")
    print("        exercise any RTL, and it does not establish that a Lucas-table")
    print("        multiplier is cheaper than a Zeckendorf normaliser -- that is a")
    print("        separate, unmeasured claim in CLOSURE_MEASURED_2026-08-10.md.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
