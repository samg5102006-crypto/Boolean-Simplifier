import itertools
import re

import pandas as pd
import streamlit as st
from sympy import Symbol
from sympy.logic.boolalg import And, Not, Or, Xor, false, true, simplify_logic


# ------------------------------------------------------------------
# 1. PARSER: converts text like  AB + A'B'  into a sympy expression
# ------------------------------------------------------------------
class Parser:
    def __init__(self, text):
        text = text.replace("’", "'")
        self.toks = re.findall(r"[A-Za-z01()+*.|&^!~']|\S", text)
        self.i = 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self):
        t = self.peek()
        self.i += 1
        return t

    def parse(self):
        if not self.toks:
            raise ValueError("Please enter an expression")
        e = self.xor()
        if self.peek() is not None:
            raise ValueError(f"Unexpected '{self.peek()}'")
        return e

    def xor(self):
        left = self.or_()
        while self.peek() == "^":
            self.take()
            left = Xor(left, self.or_())
        return left

    def or_(self):
        left = self.and_()
        while self.peek() in ("+", "|"):
            self.take()
            left = Or(left, self.and_())
        return left

    def and_(self):
        left = self.unary()
        while True:
            t = self.peek()
            if t in ("*", ".", "&"):
                self.take()
                left = And(left, self.unary())
            elif t is not None and (t.isalnum() or t in "(!~"):
                left = And(left, self.unary())  # AB means A AND B
            else:
                return left

    def unary(self):
        if self.peek() in ("!", "~"):
            self.take()
            return Not(self.unary())
        e = self.primary()
        while self.peek() == "'":  # A' means NOT A
            self.take()
            e = Not(e)
        return e

    def primary(self):
        t = self.take()
        if t is None:
            raise ValueError("Expression ended unexpectedly")
        if t == "0":
            return false
        if t == "1":
            return true
        if t and t.isalpha():
            return Symbol(t)
        if t == "(":
            e = self.xor()
            if self.take() != ")":
                raise ValueError("Missing closing parenthesis")
            return e
        raise ValueError(f"Unexpected '{t}'")


# ------------------------------------------------------------------
# 2. FORMATTER: converts a sympy expression back to AB + A'B' style
# ------------------------------------------------------------------
def sort_key(x):
    return str(x).lstrip("~")


def fmt(e):
    if e == true:
        return "1"
    if e == false:
        return "0"
    if isinstance(e, Symbol):
        return str(e)
    if isinstance(e, Not):
        a = e.args[0]
        return f"{a}'" if isinstance(a, Symbol) else f"({fmt(a)})'"
    if isinstance(e, And):
        parts = []
        for a in sorted(e.args, key=sort_key):
            s = fmt(a)
            parts.append(f"({s})" if isinstance(a, (Or, Xor)) else s)
        return "".join(parts)
    if isinstance(e, Or):
        return " + ".join(fmt(a) for a in sorted(e.args, key=sort_key))
    if isinstance(e, Xor):
        return " ⊕ ".join(fmt(a) for a in e.args)
    return str(e)


# ------------------------------------------------------------------
# 3. TRUTH TABLE
# ------------------------------------------------------------------
def truth_table(expr):
    syms = sorted(expr.free_symbols, key=str)
    rows = []
    for bits in itertools.product([False, True], repeat=len(syms)):
        sub = {s: (true if b else false) for s, b in zip(syms, bits)}
        rows.append([int(b) for b in bits] + [int(bool(expr.xreplace(sub)))])
    return pd.DataFrame(rows, columns=[str(s) for s in syms] + ["F"])


def minimize(expr, df, form):
    """Simplify; handle constants (A + A' = 1, AA' = 0) explicitly."""
    if df["F"].all():
        return true
    if not df["F"].any():
        return false
    return simplify_logic(expr, form=form)


# ------------------------------------------------------------------
# 5. QUINE-McCLUSKEY (tabular method)
# ------------------------------------------------------------------
def quine_mccluskey(minterms, n):
    """Returns (columns, primes, essential, chosen)."""
    current = {format(m, f"0{n}b"): {m} for m in minterms}
    columns, primes = [], {}

    while current:
        # Step 1: group implicants by number of 1s
        groups = {}
        for imp in current:
            groups.setdefault(imp.count("1"), []).append(imp)
        columns.append({k: sorted(v) for k, v in sorted(groups.items())})

        # Step 2: combine groups that differ in exactly one bit
        nxt, used = {}, set()
        for k in groups:
            for a in groups.get(k + 1, []):
                for b in groups[k]:
                    diff = [i for i in range(n) if a[i] != b[i]]
                    if len(diff) == 1 and "-" not in (a[diff[0]], b[diff[0]]):
                        i = diff[0]
                        nxt[a[:i] + "-" + a[i + 1:]] = current[a] | current[b]
                        used.update([a, b])

        # Step 3: anything that could not combine is a prime implicant
        for imp in current:
            if imp not in used:
                primes[imp] = current[imp]
        current = nxt

    # Step 4: essential prime implicants (only one covering some minterm)
    essential = set()
    for m in minterms:
        covering = [p for p, cov in primes.items() if m in cov]
        if len(covering) == 1:
            essential.add(covering[0])

    # Step 5: cover the rest with the fewest extra primes
    covered = set().union(*[primes[p] for p in essential]) if essential else set()
    left = set(minterms) - covered
    chosen = set(essential)
    if left:
        others = [p for p in primes if p not in essential]
        for r in range(1, len(others) + 1):
            hit = next(
                (c for c in itertools.combinations(others, r)
                 if left <= set().union(*[primes[p] for p in c])),
                None,
            )
            if hit:
                chosen.update(hit)
                break
    return columns, primes, essential, chosen


def implicant_to_term(imp, names):
    term = ""
    for bit, name in zip(imp, names):
        if bit == "1":
            term += name
        elif bit == "0":
            term += name + "'"
    return term or "1"

def show_qm(df):
    names = list(df.columns[:-1])
    n = len(names)
    minterms = [i for i, v in enumerate(df["F"]) if v]
    if n == 0 or not minterms or len(minterms) == 2**n:
        st.write("Constant function (always 0 or always 1): nothing to minimise.")
        return

    columns, primes, essential, chosen = quine_mccluskey(minterms, n)

    st.write("**Minterms:** " + ", ".join(map(str, minterms)))
    for idx, col in enumerate(columns, start=1):
        st.write(f"**Column {idx}** (grouped by number of 1s; - means eliminated variable)")
        rows = [
            {"Group (1s)": k, "Implicants": ", ".join(imps)}
            for k, imps in col.items()
        ]
        st.table(pd.DataFrame(rows))

    st.write("**Prime implicants**")
    rows = [
        {
            "Implicant": p,
            "Term": implicant_to_term(p, names),
            "Covers minterms": ", ".join(map(str, sorted(cov))),
            "Essential": "Yes" if p in essential else "",
        }
        for p, cov in primes.items()
    ]
    st.table(pd.DataFrame(rows))
    st.write(
        "**Result (Quine-McCluskey):**  "
        + " + ".join(sorted(implicant_to_term(p, names) for p in chosen))
    )



def implicant_to_sum(imp, names):
    """Implicant of F' -> sum term of F (De Morgan): 0 -> A, 1 -> A'."""
    parts = [n if b == "0" else n + "'" for b, n in zip(imp, names) if b != "-"]
    if len(parts) == 1:
        return parts[0]
    return "(" + " + ".join(parts) + ")"


def tabular_result(df):
    """Main result using Quine-McCluskey. Returns (sop_text, pos_text)."""
    names = list(df.columns[:-1])
    n = len(names)
    ones = [i for i, v in enumerate(df["F"]) if v]
    zeros = [i for i, v in enumerate(df["F"]) if not v]

    if not ones:
        return "0", "0"
    if not zeros:
        return "1", "1"

    # SOP: group the minterms (F = 1)
    _, _, _, chosen = quine_mccluskey(ones, n)
    sop = " + ".join(sorted(implicant_to_term(p, names) for p in chosen))

    # POS: minimise the zeros (F' = 1), then flip with De Morgan
    _, _, _, chosen0 = quine_mccluskey(zeros, n)
    pos = "".join(sorted(implicant_to_sum(p, names) for p in chosen0))
    return sop, pos


def matches_table(text, df):
    """Check that an expression string gives the same outputs as the truth table."""
    e = Parser(text).parse()
    names = list(df.columns[:-1])
    for row in df.itertuples(index=False):
        sub = {Symbol(nm): (true if b else false) for nm, b in zip(names, row[:-1])}
        if int(bool(e.xreplace(sub))) != row[-1]:
            return False
    return True


# ------------------------------------------------------------------
# 4. STREAMLIT UI
# ------------------------------------------------------------------
st.title("Boolean Expression Simplifier")
st.subheader("Digital Circuit Design - Minor Project")
st.write("Simplify Boolean expressions using the Quine-McCluskey (tabular) method.")

st.caption(
    "Type like AB + A'B'  (AB = AND, + = OR, ' = NOT, ^ = XOR). "
    "You can also use & | ~ symbols."
)

text = st.text_input("Enter Boolean Expression", "ABC + ABC'")

if st.button("Simplify Expression"):
    try:
        expr = Parser(text).parse()

        if len(expr.free_symbols) > 6:
            st.error("Please use at most 6 variables (tabular method grows quickly).")
        else:
            df = truth_table(expr)
            sop, pos = tabular_result(df)

            st.success("Expression simplified successfully!")
            st.latex("F = " + sop)

            st.write("**Minimal SOP:**  " + sop)
            st.write("**Minimal POS:**  " + pos)

            # Verification
            ok = matches_table(sop, df) and matches_table(pos, df)
            if ok:
                st.caption("✅ Verified: both results match the truth table on every input.")
            else:
                st.warning("Result does not match the truth table.")

            sy = minimize(expr, df, "dnf")
            st.caption("Cross-check with sympy library: " + fmt(sy))

            st.subheader("Truth Table")
            st.dataframe(df, hide_index=True)

            with st.expander("Quine-McCluskey (tabular method) steps for SOP"):
                show_qm(df)

    except Exception as e:
        st.error(f"Invalid expression: {e}")