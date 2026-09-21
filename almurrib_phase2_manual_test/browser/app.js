/* Station 7 test harness: modes EN / AR / overlay + debug panel.
 * Placeholder handling mirrors Almurrib semantics: {name}/{count} are
 * substituted, [score] is substituted, <b> renders bold. Anything unknown
 * is left visible (never silently dropped). */
(function () {
  "use strict";
  var state = {
    data: null, ar: null, glossary: [],
    mode: "en", nodeId: null, playerName: "Alex",
    flags: {}, score: 100, seen: 0
  };

  function $(id) { return document.getElementById(id); }

  function loadJSON(path) {
    return fetch(path).then(function (r) {
      if (!r.ok) throw new Error("cannot load " + path + " (" + r.status + ")");
      return r.json();
    });
  }

  function substitute(text) {
    return String(text)
      .split("{player_name}").join(state.playerName)
      .split("{count}").join("7")
      .split("[score]").join(String(state.score));
  }

  function renderRich(text) {
    // Escape HTML, then allow the Almurrib-supported <b> only.
    var div = document.createElement("div");
    div.textContent = substitute(text);
    return div.innerHTML.split("&lt;b&gt;").join("<b>")
      .split("&lt;/b&gt;").join("</b>");
  }

  function arLines(nodeId) {
    if (!state.ar || !state.ar.dialogue || !state.ar.dialogue[nodeId]) return null;
    return state.ar.dialogue[nodeId].lines || null;
  }

  function glossaryMatches(text) {
    var hits = [];
    (state.glossary || []).forEach(function (g) {
      var terms = [g.source_term].concat(g.aliases || []);
      terms.forEach(function (term) {
        if (!term || !term.trim()) return;
        var re = new RegExp("(?<!\\w)" + term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "(?!\\w)", "i");
        var m = re.exec(text);
        if (m) hits.push(g.source_term + " -> " + g.target_term + " (saw: " + m[0] + ")");
      });
    });
    return hits;
  }

  function currentText(node, key, sourceText) {
    // key: "text" or "choice:<text>"
    if (state.mode === "en") return { text: sourceText, shown: "English" };
    var lines = arLines(node.id);
    var arText = lines ? lines[key] : null;
    if (state.mode === "ar") {
      return { text: arText !== undefined && arText !== null ? arText : sourceText,
               shown: arText ? "Arabic" : "English (missing translation)" };
    }
    // overlay: base stays English, displayed layer is Arabic (conceptual demo)
    return { text: arText !== undefined && arText !== null ? arText : sourceText,
             shown: arText ? "Arabic" : "English (missing translation)" };
  }

  function speakerShown(node) {
    if (state.mode === "en" || !node.speaker) return node.speaker || "";
    var found = null;
    (state.glossary || []).forEach(function (g) {
      if (g.source_term && g.source_term.toLowerCase() === node.speaker.toLowerCase()) found = g.target_term;
    });
    return found || node.speaker;
  }

  function showNode(id) {
    if (!state.data) return;
    var node = state.data.nodes.find(function (n) { return n.id === id; });
    if (!node) return;
    state.nodeId = id;
    state.seen += 1;
    var t = currentText(node, "text", node.text);
    $("speaker").textContent = speakerShown(node);
    var textEl = $("text");
    textEl.innerHTML = renderRich(t.text);
    var rtl = state.mode !== "en";
    textEl.className = rtl ? "ar" : "";
    $("choices").className = rtl ? "ar" : "";
    $("choices").innerHTML = "";
    (node.choices || []).forEach(function (c) {
      var ct = currentText(node, "choice:" + c.text, c.text);
      var btn = document.createElement("button");
      btn.innerHTML = renderRich(ct.text);
      btn.onclick = function () {
        Object.assign(state.flags, c.set || {});
        if (c.set && c.set.hero) state.score += 10;
        showNode(c.next);
      };
      $("choices").appendChild(btn);
    });
    if (!node.choices || !node.choices.length) {
      if (node.next) {
        var cont = document.createElement("button");
        cont.textContent = state.mode === "en" ? "Continue…" : "تابع…";
        cont.onclick = function () { showNode(node.next); };
        $("choices").appendChild(cont);
      } else {
        var end = document.createElement("div");
        end.textContent = state.mode === "en" ? "— THE END —" : "— النهاية —";
        $("choices").appendChild(end);
      }
    }
    $("progress").textContent = "node " + id + " • seen " + state.seen;
    // debug panel
    $("d-id").textContent = node.id;
    $("d-speaker").textContent = node.speaker || "(narrator)";
    $("d-source").textContent = node.text;
    $("d-display").textContent = t.text;
    var hits = glossaryMatches(node.text);
    $("d-gloss").textContent = hits.length ? hits.join(" | ") : "(none)";
    $("d-base").textContent = "English";
    $("d-shown").textContent = t.shown;
    $("d-overlay").textContent = state.mode === "overlay" ? "ON" : "OFF";
    $("d-flags").textContent = JSON.stringify(state.flags) + " score=" + state.score;
  }

  function setMode(mode) {
    state.mode = mode;
    document.querySelectorAll(".modebtn").forEach(function (b) {
      b.classList.toggle("active", b.dataset.mode === mode);
    });
    $("overlay-badge").hidden = mode !== "overlay";
    if (state.nodeId) showNode(state.nodeId);
  }

  function start() {
    state.playerName = $("player-name").value.trim() || "Alex";
    $("start-screen").hidden = true;
    $("stage").hidden = false;
    showNode(state.data.start);
  }

  document.querySelectorAll(".modebtn").forEach(function (b) {
    b.onclick = function () { setMode(b.dataset.mode); };
  });
  $("start-btn").onclick = start;
  $("restart-btn").onclick = function () {
    state.flags = {}; state.score = 100; state.seen = 0;
    showNode(state.data.start);
  };

  $("start-btn").disabled = true;
  Promise.all([
    loadJSON("../game_data/dialogue.json"),
    loadJSON("../game_data/glossary.json").catch(function () { return { entries: [] }; }),
    loadJSON("../output/dialogue_ar.json").catch(function () { return null; })
  ]).then(function (parts) {
    state.data = parts[0];
    state.glossary = (parts[1] && parts[1].entries) || [];
    state.ar = parts[2];
    $("start-btn").disabled = false;
    if (!state.ar) {
      var note = $("load-note");
      note.hidden = false;
      note.textContent = "Arabic output not generated yet — run the Almurrib workflow (see docs/PHASE2_MANUAL_TEST.md), then reload. English + overlay-fallback work now.";
    }
  }).catch(function (err) {
    document.getElementById("start-screen").innerHTML =
      "<b>Failed to load game data.</b> Serve this folder over HTTP (START_GAME.bat) — " +
      String(err).replace(/</g, "&lt;");
  });
})();
