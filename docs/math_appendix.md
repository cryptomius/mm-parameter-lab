# Math Appendix: The Avellaneda-Stoikov Quoter

This appendix lays out the maths the simulator's quoter implements. Every
symbol used in the findings document maps to one defined here. The original
AS framework is from Avellaneda & Stoikov (2008) — we use it with one
principled deviation explained in §A.1.

## A.0 Notation

| Symbol  | Meaning                                          | Units                  |
|---------|--------------------------------------------------|------------------------|
| s       | Mid-market price (best bid + best ask) / 2       | price                  |
| q       | MM's signed inventory (positive = long)          | units                  |
| γ       | Inventory-aversion parameter (operator choice)   | unitless               |
| σ       | Volatility estimate of mid                       | per √second            |
| τ       | Look-ahead horizon                               | seconds                |
| k       | Order-flow elasticity (touch-distance slope)     | 1/price                |
| r       | Reservation price (MM's "fair value")            | price                  |
| δ       | Half-spread                                      | price                  |
| bid, ask| Quote prices                                     | price                  |

## A.1 Why we use the infinite-horizon variant

The original AS paper formulates the problem with a hard terminal time `T`
at which the MM must liquidate. The reservation-price and spread formulas
contain a `(T − t)` term that decays to zero as the session ends. This is
appropriate for the "agent must flatten by 4pm" framing in the paper, but
for a *continuous* market-maker — the case this simulator targets — that
decay is unrealistic. As `t → T`, the spread collapses, the MM tries to
flatten at any cost, and the dynamics become non-stationary.

We replace `(T − t)` with a constant `τ` (default 300s = 5 minutes). This
gives stationary dynamics. Conceptually, `τ` is "how many seconds I plan to
hold this risk before I can hedge or unwind it". The original formulas are
recovered by setting `τ = T − t` and decreasing `τ` to zero.

## A.2 The reservation price

```
r(t) = s(t) − q(t) · γ · σ²(t) · τ
```

The MM's "fair value" is *not* the mid. It is the mid, adjusted by current
inventory:

- If long (`q > 0`), `r < s`. The MM shades quotes downward, encouraging
  the market to lift the offer (and reduce inventory).
- If short (`q < 0`), `r > s`. The MM shades quotes upward.

The strength of shading scales with three things:

- **`γ` (inventory aversion)**: how much the MM dislikes carrying inventory.
  Higher γ produces more aggressive shading. This is the operator's risk
  appetite knob.
- **`σ²` (variance)**: how dangerous inventory is, as a function of the
  underlying volatility. In quiet markets, `q` units of inventory is
  almost free; in fast markets, the same `q` is a real risk.
- **`τ` (horizon)**: how long we expect to hold the position before
  hedging. Longer horizon = more time for `q · σ` damage to accumulate.

## A.3 The optimal half-spread

```
δ(t) = (γ · σ²(t) · τ) / 2  +  (1/γ) · ln(1 + γ/k)
```

Two terms with two intuitions:

### Term 1 — Inventory-risk premium: `(γ · σ² · τ) / 2`

Even if no one is trading adversely, the MM needs this much edge to be
compensated for the variance she carries on every fill. It scales with `γ`,
`σ²`, and `τ` — and is the term that grows in fast markets.

### Term 2 — Monopoly-rent term: `(1/γ) · ln(1 + γ/k)`

This falls out of the assumed exponential intensity of market-order arrivals:

```
λ(δ) = A · exp(−k · δ)
```

That is: the rate at which random takers walk up to depth `δ` decays
exponentially with `δ`. The slope `k` measures *price elasticity of
order flow*:

- **Low `k`** = inelastic flow. Takers will pay to cross a wide spread.
  The MM widens to extract the rent.
- **High `k`** = elastic flow. Takers vanish at any non-trivial depth.
  The MM tightens to stay competitive.

The `(1/γ)` prefactor and the `ln(·)` together encode the MM's risk-aversion
adjustment: a more risk-averse MM (higher `γ`) does not extract the same
rent as a more risk-tolerant one — she trades off less expected revenue
against less variance.

The unit consistency: `δ` is in price units, so `k` is in 1/price (so
`k · δ` is unitless, as required for an exponent).

## A.4 The final quotes

```
bid(t) = r(t) − δ(t)
ask(t) = r(t) + δ(t)
```

Note: the asymmetry the MM displays is entirely encoded in `r(t)`. The
spread itself is symmetric around the reservation price; the reservation
price moves with inventory.

## A.5 What we estimate vs assume

| Symbol | Source in the simulator |
|--------|-------------------------|
| `s(t)` | Observed: mid of the L2 order book at the current sim tick. |
| `σ(t)` | Estimated: EWMA of squared log-returns with configurable half-life (default 60s). Cheat-mode (D4) substitutes the generator's true σ. |
| `γ`    | Operator choice. Findings 1 and 4 sweep this. |
| `k`    | Default fixed at 10.0 (chosen so default spread is a few bps on a $100 mid). Could be fitted from rolling fill data; we leave that as future work to keep one fewer source of variance. |
| `τ`    | Operator choice, default 300s. |
| `q(t)` | Observed: MM's own inventory tracker, updated on every fill. |

## A.6 Why this matters for the Findings

- **Finding 1** sweeps `γ` and shows that both terms move:
  - The inventory-risk term grows linearly in `γ`.
  - The rent term shrinks in `γ` (because the MM accepts less rent in
    exchange for less variance).
  - So the *direction* of the spread change in `γ` depends on which term
    dominates — which depends on `σ`. This is also why Finding 4 shows
    that the optimal `γ` shifts with vol regime.

- **Finding 2** demonstrates a phenomenon AS does not capture: post-fill
  price drift from informed flow. The base AS model assumes symmetric
  noise traders. Our `per_counterparty_penalty` intervention extends AS
  with a per-CP rolling toxicity score that widens quotes against takers
  who recently caused adverse drift.

- **Finding 4** shows that holding `γ` fixed across `σ` regimes is
  suboptimal. This is a direct consequence of the non-linear dependence
  of `δ` on `γ` and `σ`.

## A.7 Numerical example (sanity check)

With `γ=0.1`, `k=10`, `τ=300`, `σ=0.001` per √s, `s=100`, `q=0`:

```
inv_risk_term = 0.1 · (0.001)² · 300 / 2  = 1.5e-5
rent_term     = (1/0.1) · ln(1 + 0.1/10) = 10 · ln(1.01) ≈ 0.0995
half_spread   ≈ 0.0995  →  ~ 9.95 bps on a $100 mid
```

With `q = +5`:

```
reservation = 100 − 5 · 0.1 · 1e-6 · 300 = 100 − 1.5e-4 = 99.99985
```

Tiny shading at low vol, but non-zero — and as `σ` grows, this shading
grows quadratically. That's exactly the intended behaviour.
