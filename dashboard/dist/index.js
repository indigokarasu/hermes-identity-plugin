/**
 * Identity Dashboard Plugin — real Hermes dashboard plugin (SDK / React IIFE).
 *
 * Renders live data from:
 *   GET  /api/plugins/identity/dashboard
 *        → { profile, total_lines, referenced_lines,
 *            files:[{ name, exists, total_lines, referenced_lines,
 *                     lines:[{ line_num, content, utilized_at, relative, color }] }] }
 *   GET  /api/plugins/identity/profiles
 *        → { current_profile, profiles:[{ name, identity_files }] }
 *   POST /api/plugins/identity/switch-profile  body {profile}
 *
 * Freshness colors: green(<6h FRESH) yellow(<24h RECENT) orange(<1wk AGING) red(>1wk/never STALE).
 * Theme-native: dashboard tokens (var(--color-*)) + Tailwind classes + SDK components.
 * Real data only — profiles, lines and counts come straight from the endpoints.
 */
(function () {
  "use strict";

  var SDK = window.__HERMES_PLUGIN_SDK__;
  var PLUGINS = window.__HERMES_PLUGINS__;
  if (!SDK || !PLUGINS) { console.error("[identity] Hermes plugin SDK not available."); return; }

  var React = SDK.React;
  var h = React.createElement;
  var useState = SDK.hooks.useState;
  var useEffect = SDK.hooks.useEffect;
  var useCallback = SDK.hooks.useCallback;
  var useMemo = SDK.hooks.useMemo;
  var fetchJSON = SDK.fetchJSON;
  var C = SDK.components;
  var Card = C.Card, CardHeader = C.CardHeader, CardTitle = C.CardTitle, CardContent = C.CardContent;
  var Badge = C.Badge, Button = C.Button;
  var Spinner = C.Spinner || function (p) { return h("span", { className: (p.className || "") + " animate-pulse" }, "…"); };
  var cn = (SDK.utils && SDK.utils.cn) || function () { return Array.prototype.filter.call(arguments, Boolean).join(" "); };

  // --- color → hex (line freshness) + ordered metadata ---
  var HEX = { green: "#4fd6a6", yellow: "#f0b54e", orange: "#d29a5e", red: "#f0706e" };
  var ORDER = ["green", "yellow", "orange", "red"];
  var FRESH_LABEL = { green: "FRESH", yellow: "RECENT", orange: "AGING", red: "STALE" };
  function hex(color) { return HEX[color] || HEX.red; }

  // role labels for the four identity files
  var ROLE = {
    "SOUL.md": "persona core",
    "MEMORY.md": "working memory",
    "USER.md": "about the operator",
    "AGENT.md": "operating rules"
  };

  var STALE_CAP = 12;

  // --- one-time scoped CSS injection (unique prefix idn-) ---
  function injectCSS() {
    if (document.getElementById("idn-css")) return;
    var s = document.createElement("style");
    s.id = "idn-css";
    s.textContent = [
      ".idn{display:flex;flex-direction:column;gap:1rem}",
      ".idn-profile{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap}",
      ".idn-profile-name{font-size:1rem;font-weight:500;display:flex;align-items:center;gap:.45rem}",
      ".idn-switch{display:flex;align-items:center;gap:.4rem;flex-wrap:wrap}",
      // KPI strip — equal columns, label reserves 2 lines so values align
      ".idn-kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.75rem}",
      ".idn-kpi-l{font-size:.7rem;letter-spacing:.06em;text-transform:uppercase;color:var(--color-muted-foreground);min-height:2.4em;line-height:1.3}",
      ".idn-kpi-v{font-size:1.6rem;font-weight:300;line-height:1;margin-top:.35rem}",
      ".idn-kpi-v small{font-size:.9rem;font-weight:400;color:var(--color-muted-foreground);margin-left:.15rem}",
      // freshness card: donut left, legend right
      ".idn-fresh{display:flex;align-items:center;gap:1.5rem;flex-wrap:wrap}",
      ".idn-legend{display:flex;flex-direction:row;flex-wrap:wrap;gap:1rem;flex:1 1 auto;min-width:0}",
      ".idn-leg{display:flex;align-items:center;gap:.45rem;font-size:.8rem;white-space:nowrap}",
      ".idn-leg-name{color:var(--color-muted-foreground);letter-spacing:.04em}",
      ".idn-leg-n{font-weight:500}",
      // dots — vertically centered with text
      ".idn-dot{width:.55rem;height:.55rem;border-radius:9999px;flex:0 0 auto}",
      // per-file viewer
      ".idn-file-hd{display:flex;align-items:center;gap:.6rem;width:100%;text-align:left;flex-wrap:wrap}",
      ".idn-file-name{font-weight:500;font-size:.9rem}",
      ".idn-file-role{font-size:.72rem;color:var(--color-muted-foreground)}",
      ".idn-file-meta{margin-left:auto;display:flex;align-items:center;gap:.6rem;font-size:.75rem;color:var(--color-muted-foreground)}",
      ".idn-caret{display:inline-block;width:1rem;color:var(--color-muted-foreground);transition:transform .12s ease}",
      ".idn-caret.open{transform:rotate(90deg)}",
      ".idn-lines{display:flex;flex-direction:column;border:1px solid var(--color-border);border-radius:6px;margin-top:.5rem;overflow:hidden}",
      ".idn-line{display:flex;align-items:center;gap:.55rem;padding:.18rem .6rem;font-size:.78rem;border-top:1px solid var(--color-border)}",
      ".idn-line:first-child{border-top:none}",
      ".idn-line-num{flex:0 0 auto;width:2.2rem;text-align:right;font-variant-numeric:tabular-nums;color:var(--color-muted-foreground);opacity:.7;font-size:.72rem}",
      ".idn-line-txt{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}",
      ".idn-line-rel{flex:0 0 auto;color:var(--color-muted-foreground);font-size:.72rem;white-space:nowrap}",
      // stale review rows
      ".idn-stale-row{display:flex;align-items:center;gap:.55rem;padding:.2rem 0;font-size:.8rem;border-top:1px solid var(--color-border)}",
      ".idn-stale-row:first-child{border-top:none}",
      ".idn-stale-loc{flex:0 0 auto;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.72rem;color:var(--color-muted-foreground);white-space:nowrap}",
      ".idn-stale-txt{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}",
      ".idn-stale-rel{flex:0 0 auto;color:var(--color-muted-foreground);font-size:.72rem;white-space:nowrap}",
      // donut
      ".idn-donut{position:relative;width:140px;height:140px;flex:none}",
      ".idn-donut::before{content:\"\";position:absolute;inset:0;border-radius:50%;background:var(--g);-webkit-mask:radial-gradient(circle farthest-side,#0000 calc(100% - 20px),#000 calc(100% - 20px));mask:radial-gradient(circle farthest-side,#0000 calc(100% - 20px),#000 calc(100% - 20px))}",
      ".idn-donut .ctr{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}",
      ".idn-donut .ctr .n{font-size:2rem;font-weight:300;line-height:1}",
      ".idn-donut .ctr .t{font-size:.7rem;letter-spacing:.08em;text-transform:uppercase;color:var(--color-muted-foreground);margin-top:.2rem}",
      "@media(max-width:760px){.idn-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}}",
    ].join("");
    document.head.appendChild(s);
  }

  // --- small reusable bits ---
  function dot(color, extra) {
    return h("span", { className: cn("idn-dot", extra), style: { background: hex(color) } });
  }
  function Kpi(label, value, unit) {
    return h("div", { className: "idn-kpi" },
      h("div", { className: "idn-kpi-l" }, label),
      h("div", { className: "idn-kpi-v" }, value, unit ? h("small", null, unit) : null)
    );
  }

  // --- donut (segments green,yellow,orange,red by count) ---
  function Donut(counts) {
    var total = counts.green + counts.yellow + counts.orange + counts.red;
    var pct = function (n) { return total > 0 ? (n / total) * 100 : 0; };
    var g = pct(counts.green);
    var gy = g + pct(counts.yellow);
    var gyo = gy + pct(counts.orange);
    var gradient = total > 0
      ? "conic-gradient(" + HEX.green + " 0 " + g + "%, "
        + HEX.yellow + " " + g + "% " + gy + "%, "
        + HEX.orange + " " + gy + "% " + gyo + "%, "
        + HEX.red + " " + gyo + "% 100%)"
      : "conic-gradient(var(--color-muted) 0 100%)";
    return h("div", { className: "idn-donut", style: { "--g": gradient } },
      h("div", { className: "ctr" },
        h("span", { className: "n", style: { color: counts.red ? HEX.red : "inherit" } }, counts.red),
        h("span", { className: "t" }, "stale")
      )
    );
  }

  // --- per-file expandable viewer ---
  function FileSection(props) {
    var f = props.file;
    var es = useState(props.defaultOpen), open = es[0], setOpen = es[1];
    var lines = f.lines || [];
    var staleN = lines.filter(function (l) { return l.color === "red"; }).length;

    var header = h(Button, {
      variant: "ghost",
      size: "sm",
      className: "w-full justify-start px-2",
      onClick: function () { setOpen(!open); },
      "aria-expanded": open
    },
      h("div", { className: "idn-file-hd" },
        h("span", { className: cn("idn-caret", open ? "open" : null) }, "▶"),
        h("span", { className: "idn-file-name" }, f.name),
        h("span", { className: "idn-file-role" }, ROLE[f.name] || ""),
        h("div", { className: "idn-file-meta" },
          h("span", null, f.referenced_lines + "/" + f.total_lines + " referenced"),
          staleN
            ? h(Badge, { tone: "destructive" }, staleN + " stale")
            : h("span", { style: { color: HEX.green } }, "0 stale")
        )
      )
    );

    if (!f.exists) {
      return h("div", { className: "flex flex-col" },
        h("div", { className: "idn-file-hd px-2 py-1 opacity-60" },
          h("span", { className: "idn-file-name" }, f.name),
          h("span", { className: "idn-file-role" }, ROLE[f.name] || ""),
          h("div", { className: "idn-file-meta" }, h("span", null, "not found"))
        )
      );
    }

    var body = null;
    if (open) {
      // natural line_num order
      var ordered = lines.slice().sort(function (a, b) { return (a.line_num || 0) - (b.line_num || 0); });
      body = h("div", { className: "idn-lines" },
        ordered.length === 0
          ? h("div", { className: "px-2 py-2 text-xs text-muted-foreground" }, "(empty file)")
          : ordered.map(function (l) {
              return h("div", { key: l.line_num, className: "idn-line" },
                h("span", { className: "idn-line-num" }, l.line_num),
                dot(l.color),
                h("span", { className: "idn-line-txt", title: l.content || "" }, l.content || ""),
                h("span", { className: "idn-line-rel" }, l.relative || "")
              );
            })
      );
    }

    return h("div", { className: "flex flex-col" }, header, body);
  }

  function IdentityDashboard() {
    var ds = useState(null), data = ds[0], setData = ds[1];
    var ps = useState(null), prof = ps[0], setProf = ps[1];
    var ls = useState(true), loading = ls[0], setLoading = ls[1];
    var es = useState(null), err = es[0], setErr = es[1];
    var bs = useState(false), busy = bs[0], setBusy = bs[1];

    var load = useCallback(function () {
      Promise.all([
        fetchJSON("/api/plugins/identity/dashboard"),
        fetchJSON("/api/plugins/identity/profiles")
      ])
        .then(function (r) { setData(r[0]); setProf(r[1]); setErr(null); setLoading(false); })
        .catch(function (e) { setErr((e && e.message) || "Failed to load"); setLoading(false); });
    }, []);

    useEffect(function () {
      injectCSS();
      load();
      var iv = setInterval(load, 60000);
      return function () { clearInterval(iv); };
    }, [load]);

    var switchProfile = useCallback(function (name) {
      setBusy(true);
      fetchJSON("/api/plugins/identity/switch-profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile: name })
      })
        .then(function () { return load(); })
        .catch(function (e) { setErr("Switch failed: " + ((e && e.message) || "error")); })
        .finally(function () { setBusy(false); });
    }, [load]);

    // ---- derived counts (must be before any early return for stable hooks) ----
    var derived = useMemo(function () {
      var files = (data && data.files) || [];
      var counts = { green: 0, yellow: 0, orange: 0, red: 0 };
      var staleLines = [];
      files.forEach(function (f) {
        (f.lines || []).forEach(function (l) {
          if (counts[l.color] != null) counts[l.color] += 1;
          if (l.color === "red") {
            staleLines.push({ file: f.name, line_num: l.line_num, content: l.content || "", relative: l.relative || "" });
          }
        });
      });
      var existing = files.filter(function (f) { return f.exists; }).length;
      return { files: files, counts: counts, staleLines: staleLines, existing: existing };
    }, [data]);

    if (loading && !data) {
      return h("div", { className: "flex items-center gap-2 p-8 text-sm text-muted-foreground" },
        h(Spinner, { className: "h-4 w-4" }), "Loading Identity…");
    }
    if (err && !data) {
      return h("div", { className: "p-4 text-sm text-destructive", role: "alert" },
        "Error: " + err,
        h(Button, { size: "sm", variant: "outline", className: "ml-2", onClick: load }, "Retry"));
    }
    if (!data) return null;

    var totalLines = data.total_lines || 0;
    var referenced = data.referenced_lines || 0;
    var counts = derived.counts;
    var staleLines = derived.staleLines;
    var refRate = totalLines > 0 ? Math.round(100 * referenced / totalLines) : 0;

    // ---- profile bar (real profiles only) ----
    var current = (prof && prof.current_profile) || data.profile || "—";
    var profList = (prof && prof.profiles) || [];
    var profileBar;
    if (profList.length > 1) {
      profileBar = h("div", { className: "idn-profile" },
        h("span", { className: "idn-profile-name" }, dot("green"), "Profile · " + current),
        h("div", { className: "idn-switch" },
          profList.map(function (p) {
            var active = p.name === current;
            return h(Button, {
              key: p.name,
              size: "sm",
              variant: active ? "default" : "outline",
              disabled: busy || active,
              onClick: function () { switchProfile(p.name); }
            }, p.name);
          })
        )
      );
    } else {
      profileBar = h("div", { className: "idn-profile" },
        h("span", { className: "idn-profile-name" }, dot("green"), "Profile · " + current)
      );
    }

    // ---- KPI strip (above donut) ----
    var kpis = h("div", { className: "idn-kpis" },
      Kpi("Identity files", derived.existing),
      Kpi("Total lines", totalLines),
      Kpi("Referenced", referenced),
      Kpi("Stale lines", counts.red),
      Kpi("Referenced rate", refRate, "%")
    );

    // ---- freshness card: donut left + one-line legend right ----
    var legend = h("div", { className: "idn-legend" },
      ORDER.map(function (color) {
        return h("div", { key: color, className: "idn-leg" },
          dot(color),
          h("span", { className: "idn-leg-name" }, FRESH_LABEL[color]),
          h("span", { className: "idn-leg-n" }, counts[color])
        );
      })
    );
    var freshCard = h(Card, null,
      h(CardHeader, { className: "pb-2" }, h(CardTitle, { className: "text-sm" }, "Freshness")),
      h(CardContent, null,
        h("div", { className: "idn-fresh" }, Donut(counts), legend)
      )
    );

    // ---- per-file viewer (MEMORY.md open by default) ----
    var filesCard = h(Card, null,
      h(CardHeader, { className: "pb-2" }, h(CardTitle, { className: "text-sm" }, "Identity files")),
      h(CardContent, null,
        h("div", { className: "flex flex-col gap-1" },
          derived.files.map(function (f) {
            return h(FileSection, { key: f.name, file: f, defaultOpen: f.name === "MEMORY.md" });
          })
        )
      )
    );

    // ---- stale review card (cap at STALE_CAP, surface the cap) ----
    var shown = staleLines.slice(0, STALE_CAP);
    var overflow = staleLines.length - shown.length;
    var staleCard = h(Card, null,
      h(CardHeader, { className: "pb-2" }, h(CardTitle, { className: "text-sm" }, "Stale lines · review")),
      h(CardContent, null,
        staleLines.length === 0
          ? h("div", { className: "flex items-center gap-2 text-sm" },
              dot("green"),
              h("span", { className: "text-muted-foreground" }, "No stale lines. Everything referenced within the last week."))
          : h("div", { className: "flex flex-col" },
              h("div", { className: "flex flex-col" },
                shown.map(function (s, i) {
                  return h("div", { key: s.file + ":" + s.line_num + ":" + i, className: "idn-stale-row" },
                    dot("red"),
                    h("span", { className: "idn-stale-loc" }, s.file + ":" + s.line_num),
                    h("span", { className: "idn-stale-txt", title: s.content }, s.content),
                    h("span", { className: "idn-stale-rel" }, s.relative)
                  );
                })
              ),
              overflow > 0
                ? h("div", { className: "text-xs text-muted-foreground pt-2" },
                    "+" + overflow + " more stale line" + (overflow !== 1 ? "s" : "")
                    + " (showing first " + STALE_CAP + " of " + staleLines.length + ").")
                : null
            )
      )
    );

    return h("div", { className: "idn p-4" },
      profileBar,
      kpis,
      freshCard,
      filesCard,
      staleCard
    );
  }

  PLUGINS.register("identity", IdentityDashboard);
})();
