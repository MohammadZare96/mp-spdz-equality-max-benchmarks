"use client";

import { useState } from "react";
import { benchmarkData, type ChartDatum, type RangeValue } from "./benchmark-data";

const SERIES = [
  { key: "equality" as const, label: "Equality", color: "#63e6d2" },
  { key: "max" as const, label: "Max", color: "#c8f36b" },
];
type Scale = "linear" | "log";

function fmt(value: number, unit: "s" | "MB") {
  if (unit === "s") {
    if (value < 1) return `${(value * 1000).toFixed(value < 0.01 ? 2 : 1)} ms`;
    return `${value.toFixed(value < 10 ? 2 : 1)} s`;
  }
  if (value < 1) return `${(value * 1000).toFixed(0)} KB`;
  if (value >= 1000) return `${(value / 1000).toFixed(2)} GB`;
  return `${value.toFixed(value < 10 ? 2 : 1)} MB`;
}

function Chart({ title, kicker, note, data, xLabel, unit, scale }: {
  title: string; kicker: string; note: string; data: ChartDatum[];
  xLabel: string; unit: "s" | "MB"; scale: Scale;
}) {
  const [active, setActive] = useState<{ i: number; key: "equality" | "max" } | null>(null);
  const W = 720, H = 360, m = { t: 28, r: 24, b: 48, l: 72 };
  const pw = W - m.l - m.r, ph = H - m.t - m.b;
  const ranges = data.flatMap((d) => [d.equality, d.max]);
  const low = Math.min(...ranges.map((d) => d.p25));
  const high = Math.max(...ranges.map((d) => d.p75));
  const y0 = scale === "log" ? low * 0.68 : 0;
  const y1 = scale === "log" ? high * 1.45 : high * 1.12;
  const x = (i: number) => m.l + i * pw / (data.length - 1);
  const y = (v: number) => scale === "log"
    ? m.t + ph - (Math.log(v / y0) / Math.log(y1 / y0)) * ph
    : m.t + ph - (v / y1) * ph;
  const ticks = Array.from({ length: 5 }, (_, i) => scale === "log"
    ? y0 * Math.pow(y1 / y0, i / 4) : y1 * i / 4);
  const line = (key: "equality" | "max", field: keyof RangeValue) => data
    .map((d, i) => `${i ? "L" : "M"}${x(i)},${y(d[key][field])}`).join(" ");
  const band = (key: "equality" | "max") => `${line(key, "p75")} ${[...data].reverse()
    .map((d, ri) => `L${x(data.length - ri - 1)},${y(d[key].p25)}`).join(" ")} Z`;
  const selected = active ? data[active.i][active.key] : null;

  return <article className="chart-card">
    <header><div><p className="kicker">{kicker}</p><h2>{title}</h2><p>{note}</p></div><b>{scale}</b></header>
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title}>
      <defs>{SERIES.map(s => <linearGradient key={s.key} id={`g-${s.key}-${title.replace(/\W/g, "")}`} x1="0" x2="0" y1="0" y2="1"><stop stopColor={s.color} stopOpacity=".24"/><stop offset="1" stopColor={s.color} stopOpacity=".02"/></linearGradient>)}</defs>
      {ticks.map(t => <g key={t}><line className="gridline" x1={m.l} x2={W-m.r} y1={y(t)} y2={y(t)}/><text className="tick" x={m.l-12} y={y(t)+4} textAnchor="end">{fmt(t, unit)}</text></g>)}
      {data.map((d, i) => <text className="tick" key={d.x} x={x(i)} y={H-18} textAnchor="middle">{d.x}</text>)}
      <text className="axislabel" x={m.l+pw/2} y={H-2} textAnchor="middle">{xLabel}</text>
      {SERIES.map(s => <g key={s.key}>
        <path d={band(s.key)} fill={`url(#g-${s.key}-${title.replace(/\W/g, "")})`}/>
        <path className="seriesline" d={line(s.key, "median")} stroke={s.color}/>
        {data.map((d,i) => <circle key={`${s.key}-${d.x}`} className="point" cx={x(i)} cy={y(d[s.key].median)} r={active?.i===i && active.key===s.key ? 7 : 4.5} fill={s.color} tabIndex={0} onMouseEnter={()=>setActive({i,key:s.key})} onMouseLeave={()=>setActive(null)} onFocus={()=>setActive({i,key:s.key})} onBlur={()=>setActive(null)}/>) }
      </g>)}
    </svg>
    <footer><div className="legend">{SERIES.map(s => <span key={s.key}><i style={{background:s.color}}/>{s.label}</span>)}</div><p>{active && selected ? <><strong>{active.key === "equality" ? "Equality" : "Max"} · {data[active.i].x}</strong> {fmt(selected.median, unit)} <small>IQR {fmt(selected.p25, unit)}–{fmt(selected.p75, unit)}</small></> : "Hover or focus a point for exact median and IQR"}</p></footer>
  </article>;
}

export default function Home() {
  const [scale, setScale] = useState<Scale>("log");
  const last = benchmarkData.varyKN.runtime.at(-1)!;
  const lastL = benchmarkData.varyL.communication.at(-1)!;
  return <main>
    <nav><a className="brand" href="#top"><span>MP</span><b>/</b>SPDZ</a><div><a href="https://github.com/MohammadZare96/mp-spdz-equality-max-benchmarks" target="_blank" rel="noreferrer">GitHub ↗</a><span className="verified"><i/>120 verified runs</span></div></nav>
    <section className="hero" id="top">
      <div><p className="eyebrow"><span>01</span> PAPER IMPLEMENTATION BENCHMARK</p><h1>Equality is cheap.<br/><em>Max compounds.</em></h1><p className="lede">Measured runtime and communication for the paper&apos;s Fermat equality test and partition/0-coded Max construction, executed end-to-end in MP-SPDZ.</p><div className="actions"><a href="#results">Explore measurements →</a><a href="/data/raw.csv" download>Download raw CSV</a></div></div>
      <aside><div className="terminal"><header><i/><i/><i/><span>experiment.conf</span></header><pre><code><b>protocol</b>  = semi{"\n"}<b>security</b>  = semi-honest{"\n"}<b>transport</b> = loopback{"\n"}<b>batch</b>     = 500{"\n"}<b>repeats</b>   = 5{"\n"}<b>aggregate</b> = median + IQR{"\n"}<b>status</b>    = <em>verified</em></code></pre></div><p>Captured August 5, 2026 · MP-SPDZ <code>9d809599</code></p></aside>
    </section>
    <section className="stats"><article><span>Configurations</span><strong>24</strong><p>across two sweeps</p></article><article><span>Largest cohort</span><strong>50</strong><p>local MPC parties</p></article><article><span>Max runtime penalty</span><strong>{(last.max.median/last.equality.median).toFixed(1)}×</strong><p>at L=32, K=N=50</p></article><article><span>Max communication penalty</span><strong>{(lastL.max.median/lastL.equality.median).toFixed(1)}×</strong><p>at K=N=8, L=64</p></article></section>
    <section className="results" id="results"><div className="sectionhead"><div><p className="eyebrow"><span>02</span> MEASURED RESULTS</p><h2>Two sweeps. Four views.</h2><p>Lines show the median of five verified runs. Shaded regions show the interquartile range.</p></div><div className="toggle"><button className={scale==="linear"?"active":""} onClick={()=>setScale("linear")}>Linear</button><button className={scale==="log"?"active":""} onClick={()=>setScale("log")}>Log</button></div></div>
      <div className="charts"><Chart kicker="RUNTIME · FIXED COHORT" title="Runtime vs bit length" note="K=N=8 · L ∈ {8, 16, 32, 64}" data={benchmarkData.varyL.runtime} xLabel="Bit length L" unit="s" scale={scale}/><Chart kicker="COMMUNICATION · FIXED COHORT" title="Communication vs bit length" note="Global data sent across all eight parties" data={benchmarkData.varyL.communication} xLabel="Bit length L" unit="MB" scale={scale}/><Chart kicker="RUNTIME · FIXED FIELD" title="Runtime vs K=N" note="L=32 · K=N ∈ {2, 4, 8, 10, 20, 30, 40, 50}" data={benchmarkData.varyKN.runtime} xLabel="Inputs and parties K=N" unit="s" scale={scale}/><Chart kicker="COMMUNICATION · FIXED FIELD" title="Communication vs K=N" note="L=32 · global data sent across all parties" data={benchmarkData.varyKN.communication} xLabel="Inputs and parties K=N" unit="MB" scale={scale}/></div>
    </section>
    <section className="method"><div className="sectionhead"><div><p className="eyebrow"><span>03</span> REPRODUCIBILITY</p><h2>What exactly was measured?</h2></div><a href="/data/summary.csv" download>Summary CSV ↓</a></div><div className="methodgrid"><article><b>01</b><h3>Faithful primitives</h3><p>Equality uses <code>(a-b)^(q-1)</code>. Max uses partition vectors, 0-coded vectors, Fermat&apos;s zero indicator, and a balanced SCG tree.</p></article><article><b>02</b><h3>One backend</h3><p>Every point uses MP-SPDZ <code>semi</code>, including N=2. This keeps the sweep comparable while providing semi-honest computational security.</p></article><article><b>03</b><h3>Measured boundary</h3><p>Runtime is the slowest party&apos;s reported time. Communication is global data sent, including live preprocessing.</p></article><article><b>04</b><h3>Correctness gate</h3><p>Every repetition checks the revealed result against the expected equality bit or plaintext maximum before admission.</p></article></div></section>
    <footer className="pagefoot"><span className="brand"><span>MP</span><b>/</b>SPDZ</span><p>Reproducible measurements for secure Equality and Max.</p><div><a href="/data/raw.csv">Raw data</a><a href="/data/summary.csv">Summary</a><a href="https://github.com/MohammadZare96/mp-spdz-equality-max-benchmarks">GitHub</a></div></footer>
  </main>;
}
