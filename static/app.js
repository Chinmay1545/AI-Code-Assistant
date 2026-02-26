(function () {
  "use strict";

  const uploadZone = document.getElementById("uploadZone");
  const fileInput = document.getElementById("fileInput");
  const browseBtn = document.getElementById("browseBtn");
  const uploadStatus = document.getElementById("uploadStatus");
  const instruction = document.getElementById("instruction");
  const runBtn = document.getElementById("runBtn");
  const fileList = document.getElementById("fileList");
  const previewContent = document.getElementById("previewContent");
  const outputContent = document.getElementById("outputContent");
  const loading = document.getElementById("loading");
  const outputActions = document.getElementById("outputActions");
  const downloadPatchBtn = document.getElementById("downloadPatchBtn");

  let uploadedFiles = [];
  let fileContents = {};
  let lastResultRaw = "";

  function escapeHtml(s) {
    var div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function setOutput(text, isDiff) {
    lastResultRaw = text || "";
    if (isDiff) {
      outputContent.innerHTML = "<pre class=\"output-diff\">" + escapeHtml(text) + "</pre>";
    } else if (typeof marked !== "undefined" && text) {
      marked.setOptions({ gfm: true, breaks: true });
      outputContent.innerHTML = marked.parse(text);
    } else {
      outputContent.textContent = text || "";
    }
  }

  function setStatus(msg, isError) {
    uploadStatus.textContent = msg;
    uploadStatus.className = "upload-status " + (isError ? "error" : "success");
  }

  function clearStatus() {
    uploadStatus.textContent = "";
    uploadStatus.className = "upload-status";
  }

  uploadZone.addEventListener("click", function () {
    fileInput.click();
  });

  browseBtn.addEventListener("click", function (e) {
    e.stopPropagation();
    fileInput.click();
  });

  uploadZone.addEventListener("dragover", function (e) {
    e.preventDefault();
    uploadZone.classList.add("dragover");
  });

  uploadZone.addEventListener("dragleave", function () {
    uploadZone.classList.remove("dragover");
  });

  uploadZone.addEventListener("drop", function (e) {
    e.preventDefault();
    uploadZone.classList.remove("dragover");
    const files = Array.from(e.dataTransfer.files);
    if (files.length) doUpload(files);
  });

  fileInput.addEventListener("change", function () {
    const files = Array.from(fileInput.files);
    if (files.length) doUpload(files);
    fileInput.value = "";
  });

  function doUpload(files) {
    clearStatus();
    setStatus("Uploading and indexing…", false);

    const formData = new FormData();
    const allowedExt = [".py", ".js", ".ts", ".java", ".c", ".cpp", ".go", ".rs", ".md", ".txt"];
    const maxSize = 2 * 1024 * 1024;

    for (const f of files) {
      const ext = "." + (f.name.split(".").pop() || "").toLowerCase();
      if (!allowedExt.includes(ext)) continue;
      if (f.size > maxSize) {
        setStatus("File too large (max 2 MB): " + f.name, true);
        return;
      }
      formData.append("files", f);
    }

    if (formData.getAll("files").length === 0) {
      setStatus("No valid files. Allowed: py, js, ts, java, c, cpp, go, rs, md, txt. Max 2 MB each.", true);
      return;
    }

    fetch("/upload", {
      method: "POST",
      body: formData,
    })
      .then(function (res) {
        if (!res.ok) {
          return res.json().then(function (d) {
            var msg = d.detail;
            if (Array.isArray(msg)) msg = msg.map(function (x) { return x.msg || x.loc?.join(" "); }).join("; ");
            throw new Error(msg || res.statusText);
          }).catch(function () { throw new Error(res.statusText); });
        }
        return res.json();
      })
      .then(function (data) {
        uploadedFiles = data.files || [];
        fileContents = {};
        setStatus(data.message || "Indexed " + uploadedFiles.length + " file(s).", false);
        renderFileList();
        runBtn.disabled = uploadedFiles.length === 0;
      })
      .catch(function (err) {
        setStatus(err.message || "Upload failed.", true);
      });
  }

  function renderFileList() {
    fileList.innerHTML = "";
    uploadedFiles.forEach(function (name) {
      const li = document.createElement("li");
      li.textContent = name;
      li.dataset.name = name;
      li.addEventListener("click", function () {
        fileList.querySelectorAll("li").forEach(function (el) { el.classList.remove("selected"); });
        li.classList.add("selected");
        loadPreview(name);
      });
      fileList.appendChild(li);
    });
    previewContent.innerHTML = "<span class=\"muted\">Select a file or upload files to see preview.</span>";
  }

  function loadPreview(name) {
    if (fileContents[name] !== undefined) {
      previewContent.textContent = fileContents[name];
      return;
    }
    previewContent.innerHTML = "<span class=\"muted\">Loading…</span>";
    fetch("/preview?name=" + encodeURIComponent(name))
      .then(function (res) {
        if (!res.ok) throw new Error("Preview not available");
        return res.json();
      })
      .then(function (data) {
        fileContents[name] = data.content;
        previewContent.textContent = data.content;
      })
      .catch(function () {
        previewContent.innerHTML = "<span class=\"muted\">Preview not available.</span>";
      });
  }

  runBtn.addEventListener("click", function () {
    const inst = instruction.value.trim();
    if (!inst) return;
    if (!uploadedFiles.length) return;

    loading.style.display = "flex";
    outputContent.innerHTML = "";
    outputActions.classList.remove("visible");
    outputActions.style.display = "none";
    lastResultRaw = "";

    fetch("/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ instruction: inst }),
    })
      .then(function (res) {
        if (!res.ok) {
          return res.json().then(function (d) {
            var msg = d.detail;
            if (Array.isArray(msg)) msg = msg.map(function (x) { return x.msg || (x.loc && x.loc.join(" ")); }).join("; ");
            throw new Error(msg || res.statusText);
          }).catch(function () { throw new Error(res.statusText); });
        }
        return res.json();
      })
      .then(function (data) {
        loading.style.display = "none";
        setOutput(data.result_text || "", false);
        outputActions.style.display = (data.result_text || "").trim() ? "flex" : "none";
      })
      .catch(function (err) {
        loading.style.display = "none";
        setOutput("Error: " + (err.message || "Request failed."), false);
        outputActions.style.display = "none";
      });
  });

  downloadPatchBtn.addEventListener("click", function () {
    const text = lastResultRaw;
    if (!text) return;
    const blob = new Blob([text], { type: "text/x-diff" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "patch.diff";
    a.click();
    URL.revokeObjectURL(a.href);
  });
})();
