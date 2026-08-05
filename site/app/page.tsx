"use client";

import { useState } from "react";
import { benchmarkData, extensionData, type ChartDatum, type ExtensionDatum, type RangeValue } from "./benchmark-data";

const SERIES = [
  { key: "equality" as const, label: "Equality", color: "#63e6d2" },
  { key: "max" as const, label: "Max", color: "#c8f36b" },
];
type Scale = "linear" | "log";

function fmt(value: number, unit: "s" | "MB" | "%") {
  if (unit === "%") return `${value.toFixed(2)}%`;
  if (unit === "s") {
    if (value < 0.001) return `${(value * 1_000_000).toFixed(value < 0.00001 ? 1 : 0)} µs`;
    if (value < 1) return `${(value * 1000).toFixed(value < 0.01 ? 2 : 1)} ms`;
    return `${value.toFixed(value < 10 ? 2 : 1)} s`;
  }
  if (value < 1) return `${(value * 1000).toFixed(0)} KB`;
  if (value >= 1000) return `${(value / 1000).toFixed(2)} GB`;
  return `${value.toFixed(value < 10 ? 2 : 1)} MB`;
}

type ExtraSeries = { key: string; label: string; color: string };

function ExtensionChart({ title, kicker, note, data, series, xLabel, unit, scale = "log" }: {
  title: string; kicker: string; note: string; data: ExtensionDatum[]; series: ExtraSeries[];
  xLabel: string; unit: "s" | "%"; scale?: Scale;
}) {
  const [active, setActive] = useState<{ i: number; key: string } | null>(null);
  const W = 720, H = 360, m = { t: 28, r: 24, b: 48, l: 72 };
  const pw = W - m.l - m.r, ph = H - m.t - m.b;
  const values = data.flatMap(d => series.map(s => d[s.key]));
  const low = Math.min(...values), high = Math.max(...values);
  const y0 = scale === "log" ? low * .65 : Math.max(0, low - (high-low)*.15);
  const y1 = scale === "log" ? high * 1.45 : high + (high-low)*.15;
  const x = (i: number) => m.l + i * pw / (data.length - 1);
  const y = (v: number) => scale === "log"
    ? m.t + ph - Math.log(v/y0) / Math.log(y1/y0) * ph
    : m.t + ph - (v-y0)/(y1-y0) * ph;
  const ticks = Array.from({length: 5}, (_,i) => scale === "log" ? y0*Math.pow(y1/y0,i/4) : y0+(y1-y0)*i/4);
  const path = (key: string) => data.map((d,i) => `${i ? "L" : "M"}${x(i)},${y(d[key])}`).join(" ");
  const selected = active ? data[active.i][active.key] : null;
  return <article className="chart-card extension-card">
    <header><div><p className="kicker">{kicker}</p><h2>{title}</h2><p>{note}</p></div><b>{scale}</b></header>
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title}>
      {ticks.map(t => <g key={t}><line className="gridline" x1={m.l} x2={W-m.r} y1={y(t)} y2={y(t)}/><text className="tick" x={m.l-12} y={y(t)+4} textAnchor="end">{fmt(t,unit)}</text></g>)}
      {data.map((d,i) => <text className="tick" key={d.x} x={x(i)} y={H-18} textAnchor="middle">{d.x.toLocaleString()}</text>)}
      <text className="axislabel" x={m.l+pw/2} y={H-2} textAnchor="middle">{xLabel}</text>
      {series.map(s => <g key={s.key}><path className="seriesline" d={path(s.key)} stroke={s.color}/>{data.map((d,i) => <circle key={`${s.key}-${d.x}`} className="point" cx={x(i)} cy={y(d[s.key])} r={active?.i===i && active.key===s.key ? 7 : 4.5} fill={s.color} tabIndex={0} onMouseEnter={()=>setActive({i,key:s.key})} onMouseLeave={()=>setActive(null)} onFocus={()=>setActive({i,key:s.key})} onBlur={()=>setActive(null)}/>)}</g>)}
    </svg>
    <footer><div className="legend">{series.map(s=><span key={s.key}><i style={{background:s.color}}/>{s.label}</span>)}</div><p>{active && selected !== null ? <><strong>{series.find(s=>s.key===active.key)?.label} · {data[active.i].x.toLocaleString()}</strong> {fmt(selected,unit)}</> : "Hover or focus a point for the exact value"}</p></footer>
  </article>;
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
  return <main>
    <nav><a className="brand" href="#top"><span>MP</span><b>/</b>SPDZ</a><div><a href="https://github.com/MohammadZare96/mp-spdz-equality-max-benchmarks" target="_blank" rel="noreferrer">GitHub ↗</a><span className="verified"><i/>159 measured rows</span></div></nav>
    <section className="hero" id="top">
      <div><p className="eyebrow"><span>01</span> PAPER IMPLEMENTATION BENCHMARK</p><h1>Median preserves the model.<br/><em>It isn&apos;t free.</em></h1><p className="lede">Measured Equality, Max, coordinate-wise Median, Extended SCG, and federated MNIST—plus transparent LAN/WAN sensitivity estimates from MP-SPDZ traces.</p><div className="actions"><a href="#extensions">See new experiments →</a><a href="/data/median-vector-raw.csv" download>Download Median CSV</a></div></div>
      <aside><div className="terminal"><header><i/><i/><i/><span>extension.conf</span></header><pre><code><b>median</b>    = Shamir / 10 clients{"\n"}<b>gradient D</b>= 100 · 1K · 10K{"\n"}<b>extended</b>  = value + secret index{"\n"}<b>network</b>   = LAN + WAN model{"\n"}<b>MNIST</b>     = 3 federated rounds{"\n"}<b>claim</b>     = <em>measure, don&apos;t assume</em></code></pre></div><p>Captured August 5, 2026 · MP-SPDZ <code>9d809599</code></p></aside>
    </section>
    <section className="stats"><article><span>Secure Median</span><strong>31.81s</strong><p>D=10,000 · Shamir</p></article><article><span>Extended SCG</span><strong>48.12s</strong><p>K=N=50 · semi</p></article><article><span>MNIST trajectory</span><strong>Exact</strong><p>same accuracy in both modes</p></article><article><span>WAN estimate</span><strong>57.8m</strong><p>Extended SCG · N=50</p></article></section>
    <section className="results" id="results"><div className="sectionhead"><div><p className="eyebrow"><span>02</span> MEASURED RESULTS</p><h2>Two sweeps. Four views.</h2><p>Lines show the median of five verified runs. Shaded regions show the interquartile range.</p></div><div className="toggle"><button className={scale==="linear"?"active":""} onClick={()=>setScale("linear")}>Linear</button><button className={scale==="log"?"active":""} onClick={()=>setScale("log")}>Log</button></div></div>
      <div className="charts"><Chart kicker="RUNTIME · FIXED COHORT" title="Runtime vs bit length" note="K=N=8 · L ∈ {8, 16, 32, 64}" data={benchmarkData.varyL.runtime} xLabel="Bit length L" unit="s" scale={scale}/><Chart kicker="COMMUNICATION · FIXED COHORT" title="Communication vs bit length" note="Global data sent across all eight parties" data={benchmarkData.varyL.communication} xLabel="Bit length L" unit="MB" scale={scale}/><Chart kicker="RUNTIME · FIXED FIELD" title="Runtime vs K=N" note="L=32 · K=N ∈ {2, 4, 8, 10, 20, 30, 40, 50}" data={benchmarkData.varyKN.runtime} xLabel="Inputs and parties K=N" unit="s" scale={scale}/><Chart kicker="COMMUNICATION · FIXED FIELD" title="Communication vs K=N" note="L=32 · global data sent across all parties" data={benchmarkData.varyKN.communication} xLabel="Inputs and parties K=N" unit="MB" scale={scale}/></div>
    </section>
    <section className="extensions" id="extensions"><div className="sectionhead"><div><p className="eyebrow"><span>03</span> MEDIAN · ESCG · FEDERATED MNIST</p><h2>The extensions, measured.</h2><p>Secure results are real MP-SPDZ runs. LAN/WAN curves are explicitly labeled trace-model estimates.</p></div><div className="downloadrow"><a href="/data/median-vector-summary.csv" download>Median CSV ↓</a><a href="/data/escg-summary.csv" download>ESCG CSV ↓</a></div></div>
      <div className="evidence"><article className="verdict"><p className="kicker">HYPOTHESIS CHECK</p><h3>“No overhead” is not supported.</h3><p>Against vectorized NumPy, secure Median was roughly 59,500–80,600× slower. In MNIST it preserved the accuracy trajectory exactly, but added 2.65–3.07 seconds of MPC runtime and 859.752 MB per round.</p></article><article><p className="kicker">NETWORK MODEL</p><h3>Latency dominates WAN.</h3><p>At N=50, Extended SCG estimates rise from 198.6 s on 1 ms / 1 Gbps LAN to 3465.8 s on 50 ms / 100 Mbps WAN. This is a round-and-byte sensitivity model, not packet-level netem.</p></article></div>
      <div className="charts extensioncharts">
        <ExtensionChart kicker="MEDIAN · MEASURED" title="Median runtime vs vector size" note="10 clients · L=16 · Shamir · median of three runs" data={extensionData.median} series={[{key:"plaintext",label:"Plaintext NumPy",color:"#63e6d2"},{key:"secure",label:"Paper Median",color:"#ff8a65"}]} xLabel="Gradient-vector dimension D" unit="s"/>
        <ExtensionChart kicker="EXTENDED SCG · MEASURED" title="Runtime vs K=N" note="Returns both maximum and secret source index · L=32" data={extensionData.escg} series={[{key:"measured",label:"Measured loopback",color:"#c8f36b"}]} xLabel="Inputs and parties K=N" unit="s"/>
        <ExtensionChart kicker="NETWORK · TRACE MODEL" title="LAN and WAN sensitivity" note="LAN: 1 ms / 1 Gbps · WAN: 50 ms / 100 Mbps" data={extensionData.network} series={[{key:"LAN",label:"LAN estimate",color:"#63e6d2"},{key:"WAN",label:"WAN estimate",color:"#ff6b9d"}]} xLabel="Inputs and parties K=N" unit="s"/>
        <ExtensionChart kicker="FEDERATED MNIST · MEASURED" title="Accuracy over three rounds" note="The plaintext and secure-Median curves overlap exactly" data={extensionData.mnistAccuracy} series={[{key:"secure",label:"Paper Median",color:"#ff8a65"},{key:"plaintext",label:"Plaintext Median",color:"#63e6d2"}]} xLabel="Federated round" unit="%" scale="linear"/>
      </div>
      <div className="mniststrip"><div><span>Round</span><b>1</b><b>2</b><b>3</b></div><div><span>Accuracy · both</span><b>36.85%</b><b>43.65%</b><b>48.60%</b></div><div><span>Secure aggregation wall</span><b>7.664s</b><b>3.420s</b><b>2.969s</b></div><div><span>Communication / round</span><b>859.752 MB</b><b>859.752 MB</b><b>859.752 MB</b></div></div>
    </section>
    <section className="method"><div className="sectionhead"><div><p className="eyebrow"><span>04</span> REPRODUCIBILITY</p><h2>What exactly was measured?</h2></div><a href="/data/escg-network-profiles.csv" download>Network traces ↓</a></div><div className="methodgrid"><article><b>01</b><h3>Faithful primitives</h3><p>Median follows SCI rank selection. Extended SCG selects both encoded maximum and its secret-shared index.</p></article><article><b>02</b><h3>Protocol labels</h3><p>Median and MNIST use honest-majority <code>shamir</code>. ESCG uses <code>semi</code> so N=2 through N=50 stay comparable.</p></article><article><b>03</b><h3>Measured boundary</h3><p>Runtime is the slowest party. Communication is global data sent. Network curves are derived separately from rounds and bytes.</p></article><article><b>04</b><h3>Correctness gate</h3><p>Every Median vector and ESCG value/index is checked against its plaintext result before admission.</p></article></div></section>
    <footer className="pagefoot"><span className="brand"><span>MP</span><b>/</b>SPDZ</span><p>Reproducible measurements for Equality, Max, Median, Extended SCG, and MNIST.</p><div><a href="/data/raw.csv">Core data</a><a href="/data/median-vector-raw.csv">Median</a><a href="/data/escg-raw.csv">ESCG</a><a href="https://github.com/MohammadZare96/mp-spdz-equality-max-benchmarks">GitHub</a></div></footer>
  </main>;
}
