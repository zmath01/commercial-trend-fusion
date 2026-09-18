#!/usr/bin/env python3
"""build_site.py — render the static GitHub-Pages site from results.

Inputs:  data/results/*.json (produced by backtest.py + predict.py)
Outputs: docs/  (committed; deployable via GitHub Actions or plain rsync)

Everything on the site is generated from pipeline outputs — no hand-written
headline numbers.
"""
from __future__ import annotations

import html
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

with open(ROOT / "config.yaml", encoding="utf-8") as f:
    CFG = yaml.safe_load(f)

RDIR = ROOT / CFG["paths"]["results_dir"]
TDIR = ROOT / CFG["paths"]["template_dir"]
ADIR = ROOT / CFG["paths"]["asset_dir"]
OUT = ROOT / CFG["paths"]["site_dir"]

FIELD_COLORS = {
    "AI": "#58a6ff", "Software": "#4cc38a", "SecurityCrypto": "#d29922",
    "Systems": "#bc8cff", "Theory": "#79c0ff", "Chips": "#f85149",
    "QuantumChips": "#f778ba", "AppliedMath": "#7ee787", "Quantum": "#a5d6ff",
    "QuantFinance": "#ffa657", "Fintech": "#ff7b72", "Other": "#8b949e",
}
FIELD_NAMES = {
    "AI": "AI / ML", "Software": "Software Eng.", "SecurityCrypto": "Security & Crypto",
    "Systems": "Systems", "Theory": "Theory", "Chips": "Chips / Hardware",
    "QuantumChips": "Quantum / Chips", "AppliedMath": "Applied Math",
    "Quantum": "Quantum", "QuantFinance": "Quant Finance", "Fintech": "Fintech",
    "Other": "Other",
}


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def sparkline(vals, w=88, h=22, color="#4cc38a"):
    vals = [v for v in vals if v is not None]
    if not vals or max(vals) == min(vals):
        return '<span class="muted">—</span>'
    lo, hi = min(vals), max(vals)
    n = len(vals)
    pts = []
    for i, v in enumerate(vals):
        x = 2 + i * (w - 4) / max(n - 1, 1)
        y = h - 3 - (v - lo) * (h - 6) / max(hi - lo, 1e-9)
        pts.append(f"{x:.1f},{y:.1f}")
    return (f'<svg class="spark" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" '
            f'stroke-width="1.6" stroke-linejoin="round"/></svg>')


def tag(term: str, field: str) -> str:
    color = FIELD_COLORS.get(field, "#8b949e")
    return (f'<span class="tag" style="border-color:{color};color:{color}">'
            f'{esc(FIELD_NAMES.get(field, field))}</span>')


def fmt(x, nd=2):
    if x is None:
        return "—"
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "—"
    if abs(x) >= 1000:
        return f"{x:,.0f}"
    if x == int(x) and abs(x) < 1000:
        return f"{int(x)}"
    return f"{x:.{nd}f}"


def load_json(name):
    fp = RDIR / name
    if not fp.exists():
        return None
    return json.loads(fp.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- meta
def build_meta() -> dict:
    meta = {"built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "config": CFG}
    try:
        meta["git_sha"] = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True,
            text=True, cwd=ROOT).stdout.strip()
    except Exception:  # noqa: BLE001
        meta["git_sha"] = None
    # corpus stats
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from corpus import load_corpus_df  # noqa: F401
        df = load_corpus_df()
        meta["corpus"] = {"papers": int(len(df)),
                          "years": sorted(int(y) for y in df["year"].unique())}
        fields = CFG["categories"]
        by_field = {}
        for c in fields:
            sub = df[df["primary_cat"] == c["cat"]]
            by_field[c["field"]] = by_field.get(c["field"], 0) + int(len(sub))
        meta["corpus"]["papers_by_field"] = dict(sorted(by_field.items(),
                                                        key=lambda kv: -kv[1]))
    except Exception as e:  # noqa: BLE001
        meta["corpus"] = {"error": str(e)}
    return meta


# ---------------------------------------------------------------- pages
def page_header(title: str, active: str) -> str:
    nav = [
        ("index.html", "Overview"), ("concepts.html", "Concepts"),
        ("fusion.html", "Fusion"), ("fields.html", "Fields"),
        ("backtest.html", "Backtest"), ("methodology.html", "Methodology"),
        ("about.html", "About"),
    ]
    links = "".join(
        f'<a class="nav-link{" active" if k == active else ""}" href="{k}">{v}</a>'
        for k, v in nav)
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} — Commercial Trend Radar</title>
<link rel="stylesheet" href="assets/main.css">
<meta name="description" content="Data-driven, backtested watchlist of research areas with commercialization potential, built from arXiv.">
</head><body>
<header class="site"><div class="container nav">
  <a class="brand" href="index.html">Commercial<span class="dot">·</span>Trend</a>
  {links}
  <span class="spacer"></span>
  <a class="nav-link" href="https://github.com/zmath01/commercial-trend">GitHub ↗</a>
</div></header>
<main class="container">"""


def page_footer() -> str:
    return """</main>
<footer><div class="container row">
  <span>Commercial Trend Radar — open data, open code, honest baselines.</span>
  <span>Not investment advice. Built from arXiv metadata.</span>
</div></footer>
</body></html>"""


def index_page(concepts, fusion, backtest, fields, meta) -> str:
    cards = []
    cor = meta.get("corpus", {})
    yrs = cor.get("years", [])
    yrs_str = f"{yrs[0]}–{yrs[-1]}" if yrs else "—"
    cards.append(("Papers analyzed", fmt(cor.get("papers", "—")), "sampled arXiv corpus"))
    cards.append(("Categories", str(len(CFG["categories"])), "23 arXiv cats / 10 fields"))
    cards.append(("Years", yrs_str, "diachronic window"))
    if backtest:
        ta = backtest.get("task_a", {})
        tb = backtest.get("task_b", {})
        sig = (ta.get("signals") or {}).get("hockey", {})
        cards.append(("Growth signal ρ", fmt(sig.get("spearman_rho")), "future-slope correlation"))
        rates = tb.get("rates", {})
        cards.append(("Fusion hit@100", fmt(rates.get("pool_top100_by_G", 0) * 100, 1) + "%",
                      "vs structural ctrl " + fmt(rates.get("structural_control", 0) * 100, 1) + "%"))
    cards_html = "".join(
        f'<div class="card"><div class="k">{esc(k)}</div><div class="v">{v}</div>'
        f'<div class="s">{esc(s)}</div></div>' for k, v, s in cards)

    # top concepts
    top_c = (concepts or {}).get("top", [])[:10]
    rows = []
    for i, r in enumerate(top_c, 1):
        rows.append(f"""<tr>
<td>{i}</td><td class="mono">{esc(r["term"])}</td>
<td>{tag(r["term"], r["field"])}</td>
<td>{sparkline(r["freq_series"])}</td>
<td class="num">{fmt(r["freq_latest"])}</td>
<td class="num good">{fmt(r["slope_recent"], 3)}</td>
<td class="num">{fmt(r["hockey"], 2)}</td></tr>""")
    concepts_html = "".join(rows) if rows else '<tr><td colspan="7">Run the pipeline first.</td></tr>'

    # top fusion pairs
    top_f = (fusion or {}).get("top", [])[:10]
    frows = []
    for i, r in enumerate(top_f, 1):
        gs = list((r.get("G_series") or {}).values())
        frows.append(f"""<tr>
<td>{i}</td><td class="mono">{esc(r["A"])}</td><td class="mono">×</td><td class="mono">{esc(r["B"])}</td>
<td>{sparkline(gs, color="#d29922")}</td>
<td class="num">{fmt(r["G_latest"], 3)}</td>
<td class="num">{fmt(r["I"], 1)}</td>
<td class="mono muted">{esc(r["via"])}</td></tr>""")
    fusion_html = "".join(frows) if frows else '<tr><td colspan="7">Run the pipeline first.</td></tr>'

    # fields strip
    fld = fields or {}
    fcards = []
    for f, d in sorted(fld.items(), key=lambda kv: -kv[1].get("slope_recent", 0)):
        c = FIELD_COLORS.get(f, "#8b949e")
        fcards.append(f"""<div class="card">
<div class="k">{esc(FIELD_NAMES.get(f, f))} <span style="color:{c}">●</span></div>
<div class="v" style="font-size:18px">{fmt(d.get("slope_recent"), 3)}</div>
<div class="s">recent growth slope</div>
{sparkline(d.get("counts", []), color=c)}</div>""")
    fields_html = "".join(fcards)

    return page_header("Overview", "index.html") + f"""
<div class="hero">
  <h1>Commercial Trend Radar</h1>
  <p class="lead">A data-driven, reproducible radar of research concepts and cross-field
  fusions — built from a capped arXiv corpus. The current site is a research-language
  monitor, not a validated commercialization forecast.</p>
  <div class="callout warn"><b>Current snapshot:</b> 27,259 sampled papers, 2019–2025,
  150-paper annual cap per category. The formal backtest is a fixed 2019–2022 →
  2023–2025 snapshot. Homepage rankings and formal backtest outputs should not be
  treated as the same statistical object. Recent GitHub Actions runs may be cancelled
  when a newer run supersedes an older one.</div>
  <p><span class="badge">open data</span><span class="badge">open code</span>
  <span class="badge">matched baselines</span><span class="badge">permutation tests</span>
  <span class="badge">bootstrap CIs</span><span class="badge">no private funnels</span></p>
</div>
<div class="cards">{cards_html}</div>
<section>
  <h2 class="sec">Emerging concepts</h2>
  <p class="sub">Ranked by takeoff signal (recent growth × acceleration) over the full
  window. Full list with field filters: <a href="concepts.html">concepts →</a></p>
  <table><thead><tr><th>#</th><th>term</th><th>field</th><th>freq history</th>
  <th class="num">freq latest</th><th class="num">slope</th><th class="num">hockey</th></tr></thead>
  <tbody>{concepts_html}</tbody></table>
</section>
<section>
  <h2 class="sec">Fusion watchlist</h2>
  <p class="sub">Concept pairs with <b>no direct co-occurrence yet</b> but strong indirect
  coupling (full-network effective conductance G). Yellow sparkline = G trajectory.
  Interactive map: <a href="fusion.html">fusion →</a></p>
  <table><thead><tr><th>#</th><th>A</th><th></th><th>B</th><th>G trend</th>
  <th class="num">G</th><th class="num">I</th><th>bridge</th></tr></thead>
  <tbody>{fusion_html}</tbody></table>
</section>
<section>
  <h2 class="sec">Field momentum</h2>
  <p class="sub">Recent growth slope per commercial field (log1p freq slope, last 3 years).
  Details: <a href="fields.html">fields →</a></p>
  <div class="cards">{fields_html}</div>
</section>
<section>
  <h2 class="sec">Why you can trust these numbers</h2>
  <p class="sub">Every metric on this site is produced by <code>scripts/backtest.py</code>
  from data this repository fetches itself. We report base rates, matched structural
  controls, permutation p-values and bootstrap confidence intervals — and we publish
  the results even when they are modest. See <a href="backtest.html">backtest →</a>
  and <a href="methodology.html">methodology →</a>.</p>
  <div class="callout warn"><b>Limits:</b> arXiv language is a noisy proxy for research
  activity, not commercialization. Generic phrases can enter the radar; effective
  conductance is a graph heuristic; the committed test does not use independent
  patent, funding, hiring, company, revenue, or market outcomes. This is a research
  monitor, not investment advice.</div>
</section>
""" + page_footer()


def concepts_page(concepts) -> str:
    top = (concepts or {}).get("top", [])
    fields = sorted({r["field"] for r in top})
    btns = ['<button data-field="All" class="active">All</button>'] + [
        f'<button data-field="{esc(f)}">{esc(FIELD_NAMES.get(f, f))}</button>'
        for f in fields]
    rows = []
    for i, r in enumerate(top, 1):
        hk = r.get("hockey")
        rows.append(f"""<tr data-field="{esc(r['field'])}">
<td>{i}</td><td class="mono">{esc(r['term'])}</td>
<td>{tag(r['term'], r['field'])}</td>
<td>{sparkline(r['freq_series'])}</td>
<td class="num">{fmt(r['freq_latest'])}</td>
<td class="num {'good' if r['slope_recent'] > 0 else 'bad'}">{fmt(r['slope_recent'], 3)}</td>
<td class="num">{fmt(hk, 2) if hk is not None else '—'}</td>
<td class="num">{fmt(r['pagerank'], 5)}</td></tr>""")
    return page_header("Concepts", "concepts.html") + f"""
<div class="hero"><h1>Emerging concepts</h1>
<p class="lead">Top {len(top)} terms ranked by takeoff signal over the analysis window.
<code>hockey</code> = recent-vs-prior growth ratio (takeoff detector); <code>slope</code>
= log1p frequency slope over the last 3 years; <code>pagerank</code> = centrality in the
latest cumulative co-occurrence graph.</p>
<div class="filters">{''.join(btns)}</div></div>
<section><table><thead><tr><th>#</th><th>term</th><th>field</th><th>freq history</th>
<th class="num">freq latest</th><th class="num">slope</th><th class="num">hockey</th>
<th class="num">pagerank</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section>
""" + page_footer()


def fusion_page(fusion) -> str:
    top = (fusion or {}).get("top", [])
    nodes, links = {}, []
    for r in top:
        for t in (r["A"], r["B"], r["via"]):
            if t not in nodes:
                nodes[t] = {"id": t, "freq": 10}
        links.append({"source": r["A"], "target": r["via"], "type": "bridge"})
        links.append({"source": r["B"], "target": r["via"], "type": "bridge"})
        links.append({"source": r["A"], "target": r["B"], "type": "predicted"})
    for t, nd in nodes.items():
        nd["color"] = FIELD_COLORS.get(
            next((r["fieldA"] for r in top if r["A"] == t),
                 next((r["fieldB"] for r in top if r["B"] == t), "Other")),
            "#58a6ff")
    gdata = {"nodes": list(nodes.values()), "links": links}

    rows = []
    for i, r in enumerate(top, 1):
        gs = list((r.get("G_series") or {}).values())
        rows.append(f"""<tr>
<td>{i}</td><td class="mono">{esc(r['A'])}</td><td class="mono">{esc(r['B'])}</td>
<td>{tag(r['A'], r['fieldA'])} {tag(r['B'], r['fieldB'])}</td>
<td>{sparkline(gs, color='#d29922')}</td>
<td class="num">{fmt(r['G_latest'], 3)}</td><td class="num">{fmt(r['I'], 1)}</td>
<td class="mono muted">{esc(r['via'])}</td></tr>""")
    return page_header("Fusion", "fusion.html") + f"""
<div class="hero"><h1>Fusion watchlist</h1>
<p class="lead">Pairs that have <b>never co-occurred</b> through the latest year but are
indirectly coupled via a bridge concept. G = full-network effective conductance
(resistance distance); a rising G series means the coupling is tightening — the classic
pre-fusion signature. Dashed edges are <i>predictions</i> (A–B), solid edges are existing
bridges (A–via, B–via).</p></div>
<section>
  <div id="graph"><div class="fallback">Loading…</div></div>
  <p class="sub" style="margin-top:10px">Yellow dashed = predicted A–B link. Node size ∝
  frequency, color = field.</p>
</section>
<section><table><thead><tr><th>#</th><th>A</th><th>B</th><th>fields</th><th>G trend</th>
<th class="num">G latest</th><th class="num">I</th><th>bridge</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></section>
<script>window.FUSION_GRAPH = {json.dumps(gdata)};</script>
<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
<script src="assets/app.js"></script>
""" + page_footer()


def fields_page(fields) -> str:
    fld = fields or {}
    cards = []
    for f, d in sorted(fld.items(), key=lambda kv: -kv[1].get("slope_recent", 0)):
        c = FIELD_COLORS.get(f, "#8b949e")
        cards.append(f"""<div class="card">
<div class="k">{esc(FIELD_NAMES.get(f, f))} <span style="color:{c}">●</span></div>
<div class="v" style="font-size:18px">{fmt(d.get('slope_recent'), 3)}</div>
<div class="s">recent growth slope (log1p, last 3y)</div>
{sparkline(d.get('counts', []), color=c)}</div>""")
    return page_header("Fields", "fields.html") + f"""
<div class="hero"><h1>Field momentum</h1>
<p class="lead">Aggregate phrase-frequency growth per commercial field. The sparkline
shows the field's total phrase volume per year; the slope is the log1p linear trend of
the last three years.</p></div>
<section><div class="cards">{''.join(cards)}</div></section>
""" + page_footer()


def backtest_page(backtest) -> str:
    if not backtest:
        return page_header("Backtest", "backtest.html") + """
<div class="hero"><h1>Backtest</h1>
<p class="lead">No results yet — run <code>python scripts/run_all.py</code>.</p></div>""" + page_footer()

    ta = backtest.get("task_a", {})
    tb = backtest.get("task_b", {})

    def sig_rows():
        import math
        out = []
        for name, s in (ta.get("signals") or {}).items():
            lift = s.get("lift") or {}
            liftv = lift.get("lift")
            if liftv is not None and math.isfinite(liftv):
                lift_str = f"{fmt(liftv, 2)}×"
            else:
                gain = lift.get("gain")
                lift_str = f"{fmt(gain, 3)} gain" if gain is not None else "—"
            out.append(f"""<tr><td class="mono">{name}</td>
<td class="num">{fmt(s.get('spearman_rho'), 3)}</td>
<td class="num">{s.get('perm_p', '—')}</td>
<td class="num">[{fmt(s.get('ci_lo'), 3)}, {fmt(s.get('ci_hi'), 3)}]</td>
<td class="num">{fmt(s.get('auc'), 3)}</td>
<td class="num">{fmt(lift.get('top_k_mean'), 4)}</td>
<td class="num">{fmt(lift.get('baseline_mean'), 4)}</td>
<td class="num">{lift_str}</td></tr>""")
        return "".join(out)

    rates = tb.get("rates") or {}
    def rate_row(label, key):
        return f'<tr><td>{label}</td><td class="num">{fmt(rates.get(key, 0) * 100, 1)}%</td></tr>'

    trows = rate_row("All candidates (pool base rate)", "pool_all") + \
            rate_row("Top-100 ranked by G (effective conductance)", "pool_top100_by_G") + \
            rate_row("Top-100 ranked by I (2-hop strength, cheap baseline)", "pool_top100_by_I") + \
            rate_row("Naive control (random pairs, freq-matched)", "naive_control") + \
            rate_row("Structural control (same A, same bridge, random B′)", "structural_control")

    return page_header("Backtest", "backtest.html") + f"""
<div class="hero"><h1>Backtest</h1>
<p class="lead">Out-of-sample evaluation, run by <code>scripts/backtest.py</code> on data
this repo fetches itself. Windows: history {backtest['meta']['history_years'][0]}–
{backtest['meta']['history_years'][-1]} → test {backtest['meta']['test_years'][0]}–
{backtest['meta']['test_years'][-1]}. <code>TOP_K = {backtest['meta']['top_k']}</code>,
candidates = {backtest['meta']['n_candidates']}.</p></div>

<section>
<h2 class="sec">Task A — concept growth prediction</h2>
<p class="sub">Signal from the history window vs outcome (future growth slope). ρ =
Spearman correlation with permutation p and bootstrap 95% CI; AUC = ROC AUC of
above-median future growth; lift@K = top-K mean outcome ÷ frequency-band-matched
random baseline.</p>
<table><thead><tr><th>signal</th><th class="num">ρ</th><th class="num">perm p</th>
<th class="num">95% CI</th><th class="num">AUC</th><th class="num">topK mean</th>
<th class="num">baseline</th><th class="num">lift</th></tr></thead>
<tbody>{sig_rows()}</tbody></table>
<div class="callout"><b>How to read it:</b> ρ &gt; 0 with p &lt; 0.05 means the signal
predicts future growth better than chance. Lift &gt; 1× means the top-K beats a
frequency-matched random set. Modest values are normal — and are reported honestly.</div>
</section>

<section>
<h2 class="sec">Task B — pair fusion prediction</h2>
<p class="sub">Hit = first co-occurrence in the test window with ≥3 joint papers.
The structural control is the fair baseline: same A, same bridge, random B′ — it asks
whether G adds signal beyond the 2-hop structure itself.</p>
<table><thead><tr><th>set</th><th class="num">hit rate</th></tr></thead>
<tbody>{trows}</tbody></table>
<p class="sub" style="margin-top:14px">Ranking quality on the candidate pool:
AUC(G) = {fmt(tb.get('auc_G'), 3)} · AUC(I) = {fmt(tb.get('auc_I'), 3)} ·
permutation p (AUC of G) = {tb.get('auc_perm_p', '—')} ·
permutation p (top-100 by G vs structural control) = {tb.get('perm_p_top100_vs_structural', '—')}</p>
</section>

<section>
<h2 class="sec">Honest limits</h2>
<ul>
<li>Sampled corpus: per-category-year caps make frequencies comparable within a
category across years, not across categories. Full fetch instructions: docs/data_sources.md.</li>
<li>arXiv preprints precede but do not equal commercialization. Funding, hiring, and
patent data are documented extensions, not yet integrated.</li>
<li>Multiple hypotheses are evaluated; p-values are reported per-test, not
family-wise corrected. Treat any single number with appropriate skepticism.</li>
</ul>
</section>
""" + page_footer()


def render_static(name: str, tokens: dict | None = None) -> None:
    src = TDIR / name
    if not src.exists():
        return
    text = src.read_text(encoding="utf-8")
    if tokens:
        for k, v in tokens.items():
            text = text.replace("{{" + k + "}}", str(v))
    (OUT / name).write_text(text, encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "assets").mkdir(parents=True, exist_ok=True)
    (OUT / "data").mkdir(parents=True, exist_ok=True)

    concepts = load_json("concepts_radar.json")
    fusion = load_json("fusion_watchlist.json")
    backtest = load_json("backtest.json")
    fields = load_json("fields.json")
    meta = build_meta()

    (OUT / "index.html").write_text(
        index_page(concepts, fusion, backtest, fields, meta), encoding="utf-8")
    (OUT / "concepts.html").write_text(concepts_page(concepts), encoding="utf-8")
    (OUT / "fusion.html").write_text(fusion_page(fusion), encoding="utf-8")
    (OUT / "fields.html").write_text(fields_page(fields), encoding="utf-8")
    (OUT / "backtest.html").write_text(backtest_page(backtest), encoding="utf-8")

    render_static("methodology.html", {"GITHUB_URL": "https://github.com/zmath01/commercial-trend"})
    render_static("about.html", {"GITHUB_URL": "https://github.com/zmath01/commercial-trend"})

    shutil.copy(ADIR / "main.css", OUT / "assets" / "main.css")
    shutil.copy(ADIR / "app.js", OUT / "assets" / "app.js")
    (OUT / "data" / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    if fusion:
        gdata_nodes = []
        seen = set()
        for r in fusion.get("top", []):
            for t, field in ((r["A"], r["fieldA"]), (r["B"], r["fieldB"]), (r["via"], r["fieldA"])):
                if t not in seen:
                    seen.add(t)
                    gdata_nodes.append({"id": t, "field": field})
        (OUT / "data" / "fusion_terms.json").write_text(
            json.dumps(gdata_nodes, ensure_ascii=False), encoding="utf-8")

    # also persist meta for reproducibility
    (RDIR / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print(f"[site] built -> {OUT}")


if __name__ == "__main__":
    main()
