# Boolean Expression Simplifier

**Digital Circuit Design - Minor Project**

A Streamlit dashboard that simplifies Boolean expressions using the
Quine-McCluskey (tabular) method.

## Features
- Textbook input: `AB + A'B'`, `(A+B)(A+C)`, `(AB)' + C`
- Also accepts `&`, `|`, `~` and `^` (XOR)
- Minimal SOP and POS results
- Truth table
- Step-by-step Quine-McCluskey tables (prime implicants, essential primes)
- Automatic verification against the truth table
- Cross-check with the sympy library

## Input notation
| Operation | Symbol |
|-----------|--------|
| AND | `AB`, `A*B`, `A&B` |
| OR | `A+B`, `A|B` |
| NOT | `A'`, `!A`, `~A` |
| XOR | `A^B` |

Variables are single letters (case-sensitive). Maximum 6 variables.

## Run locally
```
pip install -r requirements.txt
python -m streamlit run app.py
```

## Example
Input: `ab+ab'` gives `a`

## Tech
Python, Streamlit, SymPy, pandas
