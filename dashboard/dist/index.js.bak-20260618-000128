(function () {
  "use strict";
  var SDK = window.__HERMES_PLUGIN_SDK__;
  var PLUGINS = window.__HERMES_PLUGINS__;

  if (!SDK || !PLUGINS) {
    console.error("[identity] SDK not available");
    return;
  }

  var React = SDK.React;
  var useState = SDK.hooks.useState;
  var useEffect = SDK.hooks.useEffect;
  var useCallback = SDK.hooks.useCallback;
  var useMemo = SDK.hooks.useMemo;
  var cn = SDK.utils.cn;

  var Card = SDK.components.Card;
  var CardHeader = SDK.components.CardHeader;
  var CardTitle = SDK.components.CardTitle;
  var CardContent = SDK.components.CardContent;
  var Badge = SDK.components.Badge;
  var Button = SDK.components.Button;
  var Input = SDK.components.Input;
  var Label = SDK.components.Label;
  var Select = SDK.components.Select;
  var SelectOption = SDK.components.SelectOption;
  var Separator = SDK.components.Separator;
  var Spinner = SDK.components.Spinner;

  // ── Color helpers ──────────────────────────────────────────────────────────

  var COLOR_MAP = {
    green: { bg: "#059669", text: "#fff", label: "green" },
    yellow: { bg: "#d97706", text: "#fff", label: "yellow" },
    orange: { bg: "#ea580c", text: "#fff", label: "orange" },
    red: { bg: "#dc2626", text: "#fff", label: "red" },
  };

  var TONE_MAP = {
    green: "success",
    yellow: "warning",
    orange: "warning",
    danger: "danger",
  };

  function colorBadge(color) {
    var c = COLOR_MAP[color] || COLOR_MAP.red;
    return React.createElement(
      "span",
      {
        style: {
          display: "inline-block",
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: c.bg,
          marginRight: 6,
          flexShrink: 0,
        },
      }
    );
  }

  // ── File Editor Modal ───────────────────────────────────────────────────────

  function EditModal({ file, profile, onClose, onSave }) {
    var content = file.content || "";
    var lines = content.split("\n");

    var _a = useState("replace_line");
    var mode = _a[0], setMode = _a[1];
    var _b = useState("");
    var editContent = _b[0], setEditContent = _b[1];
    var _c = useState(1);
    var lineNum = _c[0], setLineNum = _c[1];
    var _d = useState("");
    var sectionName = _d[0], setSectionName = _d[1];
    var _e = useState(false);
    var saving = _e[0], setSaving = _e[1];
    var _f = useState(null);
    var resultMsg = _f[0], setResultMsg = _f[1];

    var handleSave = useCallback(function () {
      setSaving(true);
      setResultMsg(null);
      var body = { filename: file.filename, profile: profile, mode: mode, content: editContent };
      if (mode === "replace_line") body.line_num = lineNum;
      if (mode === "replace_section") body.section = sectionName;

      SDK.fetchJSON("/api/plugins/identity/edit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
        .then(function (data) {
          setSaving(false);
          setResultMsg({ ok: true, text: mode + " saved successfully" });
          if (onSave) onSave();
        })
        .catch(function (err) {
          setSaving(false);
          setResultMsg({ ok: false, text: err.message || "Save failed" });
        });
    }, [file.filename, profile, mode, editContent, lineNum, sectionName, onSave]);

    return React.createElement(
      "div",
      {
        style: {
          position: "fixed",
          inset: 0,
          zIndex: 50,
          background: "rgba(0,0,0,0.5)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: 24,
        },
        onClick: function (e) { if (e.target === e.currentTarget) onClose(); },
      },
      React.createElement(
        Card,
        { style: { width: "100%", maxWidth: 720, maxHeight: "90vh", display: "flex", flexDirection: "column" } },
        React.createElement(
          CardHeader,
          null,
          React.createElement(CardTitle, null, "Edit ", React.createElement("code", null, file.filename))
        ),
        React.createElement(
          CardContent,
          { style: { display: "flex", flexDirection: "column", gap: 12, overflow: "auto" } },

          // Mode selector
          React.createElement(
            "div",
            { style: { display: "flex", gap: 8, flexWrap: "wrap" } },
            ["replace_line"].map(function (m) {
              return React.createElement(
                Button,
                {
                  key: m,
                  variant: mode === m ? "default" : "outline",
                  size: "sm",
                  onClick: function () { setMode(m); setResultMsg(null); },
                },
                m === "replace_line" ? "Replace Line" : m
              );
            })
          ),

          // Line preview
          React.createElement(
            "div",
            {
              style: {
                maxHeight: 200,
                overflow: "auto",
                border: "1px solid var(--color-border)",
                borderRadius: 6,
                fontSize: 12,
                lineHeight: "1.6",
                fontFamily: "monospace",
              },
            },
            lines.map(function (l, i) {
              return React.createElement(
                "div",
                {
                  key: i,
                  style: {
                    padding: "1px 8px",
                    background: i === lineNum - 1 ? "var(--color-ring)" : "transparent",
                    color: i === lineNum - 1 ? "#000" : "inherit",
                    cursor: "pointer",
                  },
                  onClick: function () { setLineNum(i + 1); },
                },
                React.createElement("span", { style: { opacity: 0.4, marginRight: 8, display: "inline-block", width: 30, textAlign: "right" } }, i + 1),
                l || "(blank)"
              );
            })
          ),

          // Line number for replace_line
          mode === "replace_line" &&
            React.createElement(
              "div",
              null,
              React.createElement(Label, null, "Line Number"),
              React.createElement(Input, {
                type: "number",
                min: 1,
                max: lines.length,
                value: lineNum,
                onChange: function (e) { setLineNum(parseInt(e.target.value, 10) || 1); },
                style: { width: 100 } })
            ),

          // Section name for replace_section
          mode === "replace_section" &&
            React.createElement(
              "div",
              null,
              React.createElement(Label, null, "Section Heading"),
              React.createElement(Input, {
                value: sectionName,
                onChange: function (e) { setSectionName(e.target.value); },
                placeholder: "e.g. Ethos",
              })
            ),

          // Content
          React.createElement(
            "div",
            null,
            React.createElement(Label, null, "New Content"),
            React.createElement("textarea", {
              value: editContent,
              onChange: function (e) { setEditContent(e.target.value); },
              style: {
                width: "100%",
                minHeight: 80,
                fontFamily: "monospace",
                fontSize: 13,
                padding: 8,
                border: "1px solid var(--color-border)",
                borderRadius: 6,
                background: "var(--color-card)",
                color: "var(--color-card-foreground)",
                resize: "vertical",
              },
            })
          ),

          // Result message
          resultMsg &&
            React.createElement(
              "div",
              {
                style: {
                  padding: "8px 12px",
                  borderRadius: 6,
                  background: resultMsg.ok ? "rgba(5,150,105,0.1)" : "rgba(220,38,38,0.1)",
                  color: resultMsg.ok ? "#059669" : "#dc2626",
                  fontSize: 13,
                },
                role: "alert",
              },
              resultMsg.text
            ),

          // Actions
          React.createElement(
            "div",
            { style: { display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 8 } },
            React.createElement(Button, { variant: "outline", onClick: onClose }, "Cancel"),
            React.createElement(
              Button,
              { onClick: handleSave, disabled: saving },
              saving ? "Saving…" : "Save"
            )
          )
        )
      )
    );
  }

  // ── File Viewer ─────────────────────────────────────────────────────────────

  function FileViewer({ fileData, profile, onEdit }) {
    var _a = useState(true);
    var showAll = _a[0], setShowAll = _a[1];
    var lines = fileData.lines || [];
    var referencedOnly = useMemo(function () {
      if (showAll) return lines;
      return lines.filter(function (l) { return l.utilized_at != null; });
    }, [lines, showAll]);

    return React.createElement(
      Card,
      null,
      React.createElement(
        CardHeader,
        { style: { paddingBottom: 8 } },
        React.createElement(
          "div",
          { style: { display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" } },
          React.createElement(
            CardTitle,
            { style: { fontSize: 16 } },
            fileData.filename,
            " ",
            React.createElement(
              "span",
              { style: { fontWeight: 400, opacity: 0.6, fontSize: 13 } },
              "(",
              fileData.referenced_lines,
              "/",
              fileData.total_lines,
              " referenced)"
            )
          ),
          React.createElement(
            "div",
            { style: { display: "flex", gap: 8 } },
            React.createElement(
              Button,
              { variant: "ghost", size: "sm", onClick: function () { setShowAll(!showAll); } },
              showAll ? "Referenced Only" : "Show All"
            ),
            React.createElement(
              Button,
              { variant: "outline", size: "sm", onClick: function () { onEdit(fileData); } },
              "Edit"
            )
          )
        )
      ),
      React.createElement(
        CardContent,
        { style: { paddingTop: 0 } },
        React.createElement(
          "div",
          {
            style: {
              maxHeight: 400,
              overflow: "auto",
              border: "1px solid var(--color-border)",
              borderRadius: 6,
              fontSize: 12,
              lineHeight: "1.7",
              fontFamily: "monospace",
            },
          },
          referencedOnly.length === 0
            ? React.createElement("div", { style: { padding: 16, opacity: 0.5 } }, showAll ? "(empty file)" : "(no references tracked yet)")
            : referencedOnly.map(function (line) {
                return React.createElement(
                  "div",
                  {
                    key: line.line_num,
                    style: {
                      padding: "1px 8px",
                      borderBottom: "1px solid var(--color-border)",
                      borderLeft: "3px solid " + (COLOR_MAP[line.color] ? COLOR_MAP[line.color].bg : "#dc2626"),
                      background: line.utilized_at ? "transparent" : "rgba(220,38,38,0.03)",
                    },
                  },
                  React.createElement(
                    "span",
                    { style: { opacity: 0.35, marginRight: 8, display: "inline-block", width: 30, textAlign: "right", fontSize: 11 } },
                    line.line_num
                  ),
                  React.createElement(
                    Badge,
                    { tone: TONE_MAP[line.color] || "outline", style: { marginRight: 8, fontSize: 10, padding: "1px 6px" } },
                    line.relative
                  ),
                  React.createElement("span", null, line.content || "(blank)")
                );
              })
        )
      )
    );
  }

  // ── Main Page ───────────────────────────────────────────────────────────────

  function IdentityPage() {
    var _a = useState(null);
    var data = _a[0], setData = _a[1];
    var _b = useState(true);
    var loading = _b[0], setLoading = _b[1];
    var _c = useState(null);
    var error = _c[0], setError = _c[1];
    var _d = useState(null);
    var profiles = _d[0], setProfiles = _d[1];
    var _e = useState(null);
    var selectedProfile = _e[0], setSelectedProfile = _e[1];
    var _f = useState(null);
    var editingFile = _f[0], setEditingFile = _f[1];
    var _g = useState(0);
    var refreshKey = _g[0], setRefreshKey = _g[1];

    var fetchData = useCallback(function () {
      setLoading(true);
      setError(null);
      var profile = selectedProfile;
      var url = "/api/plugins/identity/dashboard" + (profile ? "?profile=" + encodeURIComponent(profile) : "");
      var profilesUrl = "/api/plugins/identity/profiles";

      Promise.all([
        SDK.fetchJSON(url),
        SDK.fetchJSON(profilesUrl),
      ])
        .then(function (results) {
          var dashData = results[0];
          var profData = results[1];
          setData(dashData);
          setProfiles(profData);
          if (!selectedProfile) setSelectedProfile(dashData.profile);
          setLoading(false);
        })
        .catch(function (err) {
          setError(err.message || "Failed to load");
          setLoading(false);
        });
    }, [selectedProfile]);

    useEffect(function () { fetchData(); }, [fetchData, refreshKey]);

    var handleProfileSwitch = useCallback(function (newProfile) {
      SDK.fetchJSON("/api/plugins/identity/switch-profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile: newProfile }),
      })
        .then(function () {
          setSelectedProfile(newProfile);
          setData(null);
          setRefreshKey(function (k) { return k + 1; });
        })
        .catch(function (err) { setError(err.message || "Switch failed"); });
    }, []);

    var handleResetUsage = useCallback(function () {
      if (!window.confirm("Clear all utilization tracking data?")) return;
      SDK.fetchJSON("/api/plugins/identity/reset-usage", { method: "POST" })
        .then(function () { setRefreshKey(function (k) { return k + 1; }); })
        .catch(function (err) { setError(err.message || "Reset failed"); });
    }, []);

    var handleFetchFileForEdit = useCallback(function (fileSummary) {
      var profile = selectedProfile;
      var url = "/api/plugins/identity/view?filename=" + encodeURIComponent(fileSummary.name) + "&profile=" + encodeURIComponent(profile || "");
      SDK.fetchJSON(url)
        .then(function (fileData) {
          var content = (fileData.lines || []).map(function (l) { return l.content; }).join("\n");
          setEditingFile({
            filename: fileData.filename,
            profile: fileData.profile,
            content: content,
          });
        })
        .catch(function (err) { setError(err.message || "Failed to load file"); });
    }, [selectedProfile]);

    if (loading && !data) {
      return React.createElement(
        "div",
        { style: { display: "flex", alignItems: "center", justifyContent: "center", padding: 48 } },
        React.createElement(Spinner, null)
      );
    }

    if (error) {
      return React.createElement(
        Card,
        null,
        React.createElement(
          CardContent,
          { style: { padding: 24 } },
          React.createElement("p", { style: { color: "#dc2626" }, role: "alert" }, "Error: ", error),
          React.createElement(Button, { onClick: fetchData, style: { marginTop: 12 } }, "Retry")
        )
      );
    }

    var files = (data && data.files) || [];
    var totalLines = (data && data.total_lines) || 0;
    var totalRefd = (data && data.referenced_lines) || 0;
    var profList = (profiles && profiles.profiles) || [];

    return React.createElement(
      "div",
      { style: { padding: 16, maxWidth: 1200, margin: "0 auto" } },

      // Header controls
      React.createElement(
        "div",
        { style: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 } },
        React.createElement(
          "div",
          null,
          React.createElement("h2", { style: { fontSize: 20, fontWeight: 700, margin: 0 } }, "Identity"),
          React.createElement("p", { style: { fontSize: 13, opacity: 0.6, margin: "4px 0 0" } },
            totalRefd,
            "/",
            totalLines,
            " lines referenced"
          )
        ),
        React.createElement(
          "div",
          { style: { display: "flex", gap: 8, alignItems: "center" } },

          // Profile selector
          React.createElement(
            Select,
            {
              value: selectedProfile || "",
              onValueChange: handleProfileSwitch,
              style: { width: 180 },
            },
            profList.map(function (p) {
              return React.createElement(
                SelectOption,
                { key: p.name, value: p.name },
                p.name,
                " (",
                (p.identity_files || []).length,
                " files)"
              );
            })
          ),

          React.createElement(
            Button,
            { variant: "ghost", size: "sm", onClick: fetchData, title: "Refresh" },
            "↻"
          ),
          React.createElement(
            Button,
            { variant: "ghost", size: "sm", onClick: handleResetUsage, title: "Reset utilization" },
"Reset"
          )
        )
      ),

      // Color legend
      React.createElement(
        "div",
        { style: { display: "flex", gap: 16, marginBottom: 16, fontSize: 12 } },
        Object.keys(COLOR_MAP).map(function (color) {
          var c = COLOR_MAP[color];
          return React.createElement(
            "div",
            { key: color, style: { display: "flex", alignItems: "center" } },
            colorBadge(color),
            React.createElement("span", { style: { textTransform: "capitalize" } }, color)
          );
        }),
        React.createElement("span", { style: { opacity: 0.4 } }, "= utilization frequency")
      ),

      React.createElement(Separator, { style: { marginBottom: 16 } } ),

      // File cards
      React.createElement(
        "div",
        { style: { display: "flex", flexDirection: "column", gap: 16 } },
        files.map(function (f) {
          if (!f.exists) {
            return React.createElement(
              Card,
              { key: f.name },
              React.createElement(
                CardContent,
                { style: { padding: 16, opacity: 0.5 } },
                f.name, " — not found"
              )
            );
          }
          return React.createElement(FileViewer, {
            key: f.name,
            fileData: f,
            profile: selectedProfile,
            onEdit: handleFetchFileForEdit,
          });
        })
      ),

      // Edit modal
      editingFile
        ? React.createElement(EditModal, {
            file: editingFile,
            profile: selectedProfile,
            onClose: function () { setEditingFile(null); },
            onSave: function () {
              setEditingFile(null);
              setRefreshKey(function (k) { return k + 1; });
            },
          })
        : null
    );
  }

  PLUGINS.register("identity", IdentityPage);
})();
