"""PnL tracker.

Decomposes total PnL into:
- spread PnL: realised from completed round-trips (FIFO matching of fills)
- inventory PnL: mark-to-market of open inventory at the current mid
- fees: cumulative taker fees paid + maker rebates earned
- total = spread + inventory + fees

The MM's "trade" sign convention:
- BID side fill = MM bought = inventory increases by +size, cash decreases
- ASK side fill = MM sold = inventory decreases by -size, cash increases
"""

from __future__ import annotations

from dataclasses import dataclass

from mm_sim.types import FillEvent, Side


@dataclass
class PnLState:
    inventory: float = 0.0
    cash: float = 0.0
    realised_spread_pnl: float = 0.0  # populated by FIFO close-outs
    fees_paid: float = 0.0  # negative = cost
    fills: int = 0
    last_mid: float = 0.0

    # FIFO inventory layers: list of (size, price) tuples; size > 0 long, < 0 short
    _layers: list[tuple[float, float]] | None = None

    def __post_init__(self) -> None:
        self._layers = []

    def on_fill(
        self,
        fill: FillEvent,
        is_mm_maker: bool,
        maker_rebate_bps: float,
        taker_fee_bps: float,
    ) -> None:
        if not is_mm_maker:
            return
        # MM's directional view (maker side as observed in fill.side)
        signed_size = fill.size if fill.side is Side.BID else -fill.size
        self.inventory += signed_size
        self.cash -= signed_size * fill.price  # buy reduces cash, sell increases
        # Maker rebate (positive) on maker fills
        self.fees_paid += fill.size * fill.price * maker_rebate_bps * 1e-4
        # FIFO realisation
        self._update_fifo(signed_size, fill.price)
        self.fills += 1
        self.last_mid = fill.mid_at_fill

    def _update_fifo(self, signed_size: float, price: float) -> None:
        assert self._layers is not None
        remaining = signed_size
        while remaining != 0 and self._layers:
            top_size, top_price = self._layers[0]
            # If top layer is opposite sign, close out
            if (top_size > 0) != (remaining > 0):
                close = min(abs(top_size), abs(remaining))
                pnl = close * (price - top_price) * (1 if top_size > 0 else -1)
                # If we previously bought (top_size>0) and now sell (remaining<0):
                #   realised = close * (sell_price - buy_price) = close * (price - top_price)
                # If we previously sold (top_size<0) and now buy (remaining>0):
                #   realised = close * (sell_price - buy_price) = close * (top_price - price)
                self.realised_spread_pnl += pnl
                # Reduce top layer
                if abs(top_size) > close:
                    new_top = top_size - close * (1 if top_size > 0 else -1)
                    self._layers[0] = (new_top, top_price)
                else:
                    self._layers.pop(0)
                # Reduce remaining
                remaining -= -close * (1 if top_size > 0 else -1)
            else:
                break
        if remaining != 0:
            self._layers.append((remaining, price))

    def mark(self, mid: float) -> None:
        self.last_mid = mid

    @property
    def unrealised_pnl(self) -> float:
        if self.inventory == 0:
            return 0.0
        # Average cost of current open inventory from layers
        if not self._layers:
            return 0.0
        avg_cost = sum(s * p for s, p in self._layers) / sum(s for s, _ in self._layers)
        return self.inventory * (self.last_mid - avg_cost)

    @property
    def total_pnl(self) -> float:
        return self.realised_spread_pnl + self.unrealised_pnl + self.fees_paid
