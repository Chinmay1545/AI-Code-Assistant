(function () {
  "use strict";

  const app = document.querySelector(".app");
  const uploadZone = document.getElementById("uploadZone");
  const fileInput = document.getElementById("fileInput");
  const uploadBtn = document.getElementById("uploadBtn");
  const browseBtn = document.getElementById("browseBtn");
  const uploadStatus = document.getElementById("uploadStatus");
  const filesMeta = document.getElementById("filesMeta");
  const fileList = document.getElementById("fileList");
  const preview = document.getElementById("preview");
  const previewName = document.getElementById("previewName");
  const previewMeta = document.getElementById("previewMeta");
  const previewWrap = document.getElementById("previewWrap");
  const previewContent = document.getElementById("previewContent");
  const composer = document.getElementById("composer");
  const instruction = document.getElementById("instruction");
  const runBtn = document.getElementById("runBtn");
  const composerHint = document.getElementById("composerHint");
  const outputWrap = document.getElementById("outputWrap");
  const outputEmpty = document.getElementById("outputEmpty");
  const asked = document.getElementById("asked");
  const askedText = document.getElementById("askedText");
  const outputContent = document.getElementById("outputContent");
  const loading = document.getElementById("loading");
  const outputActions = document.getElementById("outputActions");
  const downloadPatchBtn = document.getElementById("downloadPatchBtn");

  const ALLOWED_EXT = [".py", ".js", ".ts", ".java", ".c", ".cpp", ".go", ".rs", ".md", ".txt"];
  const MAX_SIZE = 2 * 1024 * 1024;

  let uploadedFiles = [];
  let fileContents = {};
  let lastResultRaw = "";
  let running = false;

  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function escapeRegExp(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function lineCount(text) {
    return text ? text.replace(/\n$/, "").split("\n").length : 0;
  }

  function plural(n, word) {
    return n.toLocaleString() + " " + word + (n === 1 ? "" : "s");
  }

  function setStatus(msg, isError) {
    uploadStatus.textContent = msg;
    uploadStatus.className = "upload-status" + (isError ? " error" : "");
  }

  // FastAPI errors come back as {detail: string | [{msg, loc}]}
  function errorFromResponse(res) {
    return res.json().then(
      function (d) {
        let msg = d && d.detail;
        if (Array.isArray(msg)) msg = msg.map(function (x) { return x.msg || (x.loc && x.loc.join(" ")); }).join("; ");
        return new Error(msg || res.statusText);
      },
      function () { return new Error(res.statusText); }
    );
  }

  function canRun() {
    return !running && uploadedFiles.length > 0 && instruction.value.trim() !== "";
  }

  // The button is enabled only when there is something to ask; the hint says what is missing.
  function updateRunState() {
    runBtn.disabled = !canRun();
    composerHint.textContent = uploadedFiles.length ? "Cmd or Ctrl + Enter" : "Upload files first";
  }

  // --- Upload ---

  function openPicker() {
    fileInput.click();
  }

  uploadBtn.addEventListener("click", openPicker);
  uploadZone.addEventListener("click", openPicker);
  browseBtn.addEventListener("click", function (e) {
    e.stopPropagation();
    openPicker();
  });

  // The whole window is a drop target; the files panel shows where it lands.
  let dragDepth = 0;
  window.addEventListener("dragenter", function (e) {
    e.preventDefault();
    dragDepth++;
    app.classList.add("dragover");
  });
  window.addEventListener("dragover", function (e) {
    e.preventDefault();
  });
  window.addEventListener("dragleave", function () {
    dragDepth = Math.max(0, dragDepth - 1);
    if (dragDepth === 0) app.classList.remove("dragover");
  });
  window.addEventListener("drop", function (e) {
    e.preventDefault();
    dragDepth = 0;
    app.classList.remove("dragover");
    const files = Array.from(e.dataTransfer.files);
    if (files.length) doUpload(files);
  });

  fileInput.addEventListener("change", function () {
    const files = Array.from(fileInput.files);
    if (files.length) doUpload(files);
    fileInput.value = "";
  });

  function doUpload(files) {
    const formData = new FormData();
    for (const f of files) {
      const ext = "." + (f.name.split(".").pop() || "").toLowerCase();
      if (!ALLOWED_EXT.includes(ext)) continue;
      if (f.size > MAX_SIZE) {
        setStatus("File too large (max 2 MB): " + f.name, true);
        return;
      }
      formData.append("files", f);
    }

    if (formData.getAll("files").length === 0) {
      setStatus("No supported files. Allowed: py, js, ts, java, c, cpp, go, rs, md, txt.", true);
      return;
    }

    setStatus("Indexing " + plural(formData.getAll("files").length, "file") + "…", false);
    uploadBtn.disabled = true;

    fetch("/upload", { method: "POST", body: formData })
      .then(function (res) {
        if (!res.ok) return errorFromResponse(res).then(function (err) { throw err; });
        return res.json();
      })
      .then(function (data) {
        uploadedFiles = data.files || [];
        fileContents = {};
        return Promise.all(uploadedFiles.map(fetchContent)).then(function () {
          setStatus(data.message || "Indexed " + plural(uploadedFiles.length, "file") + ".", false);
          renderFileList();
          if (uploadedFiles.length) selectFile(uploadedFiles[0]);
          updateRunState();
          instruction.focus();
        });
      })
      .catch(function (err) {
        setStatus(err.message || "Upload failed.", true);
      })
      .finally(function () {
        uploadBtn.disabled = false;
      });
  }

  function fetchContent(name) {
    return fetch("/preview?name=" + encodeURIComponent(name))
      .then(function (res) {
        if (!res.ok) throw new Error("Preview not available");
        return res.json();
      })
      .then(function (data) {
        fileContents[name] = data.content;
      })
      .catch(function () {
        fileContents[name] = null;
      });
  }

  // --- Files and preview ---

  function renderFileList() {
    fileList.innerHTML = "";
    let totalLines = 0;
    uploadedFiles.forEach(function (name) {
      const lines = lineCount(fileContents[name] || "");
      totalLines += lines;

      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.dataset.name = name;
      btn.innerHTML = '<span class="file-name"></span><span class="file-lines num"></span>';
      btn.querySelector(".file-name").textContent = name;
      btn.querySelector(".file-lines").textContent = fileContents[name] == null ? "—" : plural(lines, "line");
      btn.addEventListener("click", function () { selectFile(name); });
      li.appendChild(btn);
      fileList.appendChild(li);
    });

    const hasFiles = uploadedFiles.length > 0;
    uploadZone.hidden = hasFiles;
    fileList.hidden = !hasFiles;
    preview.hidden = !hasFiles;
    filesMeta.textContent = hasFiles ? plural(uploadedFiles.length, "file") + " · " + plural(totalLines, "line") : "";
  }

  // ranges: optional [[start, end], ...] to highlight; the view scrolls to the first.
  function selectFile(name, ranges) {
    ranges = ranges || [];
    fileList.querySelectorAll("button").forEach(function (b) {
      b.setAttribute("aria-current", b.dataset.name === name ? "true" : "false");
    });

    const content = fileContents[name];
    previewName.textContent = name;
    if (content == null) {
      previewMeta.textContent = "";
      previewContent.innerHTML = '<span class="preview-message">Preview not available.</span>';
      return;
    }

    previewMeta.textContent = plural(lineCount(content), "line");
    const lines = content.replace(/\n$/, "").split("\n");
    previewContent.innerHTML = lines
      .map(function (line, i) {
        const n = i + 1;
        const cited = ranges.some(function (r) { return n >= r[0] && n <= r[1]; });
        return '<span class="code-line' + (cited ? " cited" : "") + '">' + escapeHtml(line) + "</span>";
      })
      .join("");

    if (ranges.length) {
      const target = previewContent.children[ranges[0][0] - 1];
      if (target) {
        const top = target.offsetTop - previewWrap.clientHeight / 3;
        previewWrap.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
        if (window.matchMedia("(max-width: 900px)").matches) preview.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    } else {
      previewWrap.scrollTop = 0;
    }
  }

  // --- Run ---

  // One question, one answer: the question moves above the answer area and the field clears for the next one.
  function run() {
    const inst = instruction.value.trim();
    if (!canRun()) {
      instruction.focus();
      return;
    }

    running = true;
    instruction.value = "";
    updateRunState();
    askedText.textContent = inst;
    asked.hidden = false;
    outputEmpty.hidden = true;
    loading.hidden = false;
    outputContent.innerHTML = "";
    outputActions.hidden = true;
    lastResultRaw = "";
    outputWrap.scrollTop = 0;

    fetch("/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ instruction: inst }),
    })
      .then(function (res) {
        if (!res.ok) return errorFromResponse(res).then(function (err) { throw err; });
        return res.json();
      })
      .then(function (data) {
        setOutput(data.result_text || "");
        outputActions.hidden = diffBlocks(lastResultRaw).length === 0;
      })
      .catch(function (err) {
        outputContent.innerHTML = '<p class="error-message"></p>';
        outputContent.firstChild.textContent = "Request failed: " + (err.message || "unknown error") + ". Your question is back in the box below; check the server log, then try again.";
        if (!instruction.value.trim()) instruction.value = inst;
      })
      .finally(function () {
        running = false;
        loading.hidden = true;
        updateRunState();
      });
  }

  composer.addEventListener("submit", function (e) {
    e.preventDefault();
    run();
  });

  instruction.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      run();
    }
  });

  instruction.addEventListener("input", updateRunState);

  document.querySelectorAll(".suggestion").forEach(function (btn) {
    btn.addEventListener("click", function () {
      instruction.value = btn.textContent;
      updateRunState();
      if (canRun()) run();
      else instruction.focus();
    });
  });

  updateRunState();

  // --- Answer rendering ---

  function setOutput(text) {
    lastResultRaw = text;
    if (typeof marked !== "undefined") {
      marked.setOptions({ gfm: true, breaks: true });
      outputContent.innerHTML = marked.parse(text);
    } else {
      outputContent.textContent = text;
    }
    colourDiffs();
    linkCitations();
  }

  function colourDiffs() {
    outputContent.querySelectorAll("pre code.language-diff, pre code.language-patch").forEach(function (code) {
      code.innerHTML = code.textContent
        .split("\n")
        .map(function (line) {
          const cls = /^\+(?!\+\+)/.test(line) ? "diff-add"
            : /^-(?!--)/.test(line) ? "diff-remove"
            : /^@@/.test(line) ? "diff-hunk"
            : "";
          return cls ? '<span class="' + cls + '">' + escapeHtml(line) + "</span>" : escapeHtml(line);
        })
        .join("\n");
    });
  }

  // Turn "main.py:42", "main.py:40-52" or "main.py:52, 365-366" into a button that opens those lines in the preview.
  // A trailing ", N" only counts as another line when no word follows it ("main.py:12, 3 files" links line 12 only).
  function linkCitations() {
    if (!uploadedFiles.length) return;
    const names = uploadedFiles.slice().sort(function (a, b) { return b.length - a.length; }).map(escapeRegExp);
    const range = "\\d+(?:\\s*[-–]\\s*\\d+)?";
    const pattern = new RegExp("(" + names.join("|") + "):(" + range + "(?:\\s*,\\s*" + range + "(?!\\s*[A-Za-z]))*)", "g");

    const walker = document.createTreeWalker(outputContent, NodeFilter.SHOW_TEXT, {
      acceptNode: function (node) {
        return node.parentElement.closest("pre") ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
      },
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);

    nodes.forEach(function (node) {
      const text = node.nodeValue;
      pattern.lastIndex = 0;
      if (!pattern.test(text)) return;
      pattern.lastIndex = 0;

      const frag = document.createDocumentFragment();
      let last = 0;
      let m;
      while ((m = pattern.exec(text))) {
        frag.appendChild(document.createTextNode(text.slice(last, m.index)));
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "cite";
        btn.textContent = m[0];
        const file = m[1];
        const ranges = m[2].split(",").map(function (part) {
          const bounds = part.split(/[-–]/).map(function (x) { return parseInt(x, 10); });
          return [bounds[0], bounds[1] || bounds[0]];
        });
        btn.setAttribute("aria-label", "Show " + file + " lines " + m[2]);
        btn.addEventListener("click", function () { selectFile(file, ranges); });
        frag.appendChild(btn);
        last = m.index + m[0].length;
      }
      frag.appendChild(document.createTextNode(text.slice(last)));
      node.parentNode.replaceChild(frag, node);
    });
  }

  function diffBlocks(text) {
    const blocks = [];
    const re = /```(?:diff|patch)\n([\s\S]*?)```/g;
    let m;
    while ((m = re.exec(text))) blocks.push(m[1].replace(/\n?$/, "\n"));
    return blocks;
  }

  // Shown only when the answer contains a diff; downloads just the diff blocks.
  downloadPatchBtn.addEventListener("click", function () {
    const blocks = diffBlocks(lastResultRaw);
    if (!blocks.length) return;
    const blob = new Blob([blocks.join("\n")], { type: "text/x-diff" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "patch.diff";
    a.click();
    URL.revokeObjectURL(a.href);
  });
})();
