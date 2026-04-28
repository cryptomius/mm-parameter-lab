import { useState } from "react";
import { api } from "../api/rest";
import { CUSTOM_REGIME_KEY } from "../state/regimes";
import { useSessionStore } from "../state/sessionStore";
import { Slider } from "./Slider";

interface ParamMeta {
  key: string;
  label: string;
  description: string;
}

const META: Record<string, ParamMeta> = {
  gamma: {
    key: "gamma",
    label: "γ (inv aversion)",
    description:
      "How aggressively the quoter skews against accumulated inventory. Higher γ = harder skew, but also tighter spreads in our rent-dominated regime (so more turnover and more PnL). Findings recommend γ = 5.",
  },
  k: {
    key: "k",
    label: "k (rent slope)",
    description:
      "AS rent term. Roughly: how much spread the MM demands as compensation for being a passive market maker. Higher k = wider spreads. Default k = 10 puts us in a rent-term-dominated regime; the inv-risk term only takes over at much higher σ.",
  },
  tau: {
    key: "tau",
    label: "τ (lookback s)",
    description:
      "Horizon used in the AS spread/skew. In our infinite-horizon variant, τ scales the inventory-risk term. Longer τ = more emphatic inventory skew.",
  },
  q_target: {
    key: "q_target",
    label: "q_target (inv target)",
    description:
      "Inventory target the quoter biases toward. Set NEGATIVE for known structural buy-side pressure (e.g. token vesting sellers — you expect to accumulate, so pre-skew short). Set POSITIVE for buyback / accumulation campaigns. The reservation formula becomes r = mid − (q − q_target)·γ·σ²·τ. Bounded by ±inventory_limit.",
  },
  bid_widening_factor: {
    key: "bid_widening_factor",
    label: "Bid widening ×",
    description:
      "Multiplier on the bid half-spread. >1 = step OUT on the bid (less likely to be hit by sellers, slows inventory accumulation). <1 = step IN. Use >1 alongside negative q_target for one-sided sell pressure. Applied AFTER the intervention pipeline.",
  },
  ask_widening_factor: {
    key: "ask_widening_factor",
    label: "Ask widening ×",
    description:
      "Multiplier on the ask half-spread. <1 = step IN on the ask (more likely to be lifted, sheds long inventory faster). Pair with bid widening >1 to lean against persistent one-sided pressure. Applied AFTER the intervention pipeline.",
  },
};

export function ParameterPanel() {
  const gamma = useSessionStore((s) => s.state.gamma);
  const k = useSessionStore((s) => s.state.k);
  const tau = useSessionStore((s) => s.state.tau);
  const qTarget = useSessionStore((s) => s.state.q_target);
  const bidF = useSessionStore((s) => s.state.bid_widening_factor);
  const askF = useSessionStore((s) => s.state.ask_widening_factor);
  const invLimit = useSessionStore((s) => s.state.inventory_limit ?? 100);
  const running = useSessionStore((s) => s.state.running);
  const setRegime = useSessionStore((s) => s.setRegime);
  const [hovered, setHovered] = useState<string | null>(null);
  const info = hovered ? META[hovered] : null;

  // Wrap commits so any user edit flips regime to "custom".
  const wrapCommit = (field: string) => async (v: number) => {
    setRegime(CUSTOM_REGIME_KEY);
    await api.patchParams({ [field]: v });
  };

  return (
    <div className="panel p-3">
      <div className="label mb-2">Quoter Parameters</div>
      <Slider
        label={META.gamma.label}
        serverValue={gamma}
        min={0.001}
        max={100}
        scale="log10"
        disabled={!running}
        onCommit={wrapCommit("gamma")}
        onHover={setHovered}
        hoverKey="gamma"
      />
      <Slider
        label={META.k.label}
        serverValue={k}
        min={0.1}
        max={1000}
        scale="log10"
        disabled={!running}
        onCommit={wrapCommit("k")}
        onHover={setHovered}
        hoverKey="k"
      />
      <Slider
        label={META.tau.label}
        serverValue={tau}
        min={10}
        max={3600}
        scale="linear"
        unit="s"
        disabled={!running}
        onCommit={wrapCommit("tau")}
        onHover={setHovered}
        hoverKey="tau"
      />
      <Slider
        label={META.q_target.label}
        serverValue={qTarget}
        min={-invLimit}
        max={invLimit}
        scale="linear"
        disabled={!running}
        onCommit={wrapCommit("q_target")}
        onHover={setHovered}
        hoverKey="q_target"
      />
      <Slider
        label={META.bid_widening_factor.label}
        serverValue={bidF}
        min={0.3}
        max={5.0}
        scale="linear"
        unit="×"
        disabled={!running}
        onCommit={wrapCommit("bid_widening_factor")}
        onHover={setHovered}
        hoverKey="bid_widening_factor"
      />
      <Slider
        label={META.ask_widening_factor.label}
        serverValue={askF}
        min={0.3}
        max={5.0}
        scale="linear"
        unit="×"
        disabled={!running}
        onCommit={wrapCommit("ask_widening_factor")}
        onHover={setHovered}
        hoverKey="ask_widening_factor"
      />
      <div className="mt-2 p-2 bg-bg/60 border border-border rounded text-[10px] text-sub leading-snug min-h-[64px]">
        {info ? (
          <>
            <span className="text-ink font-semibold">{info.label}.</span> {info.description}
          </>
        ) : (
          <span className="italic">Hover a control to see what it does. Press Enter or release the slider to apply.</span>
        )}
      </div>
    </div>
  );
}
