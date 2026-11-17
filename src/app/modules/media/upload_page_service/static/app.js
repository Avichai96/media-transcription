(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const form = $("upload-form");
  const input = $("file");
  const dropzone = $("dropzone");
  const chip = $("file-chip");
  const submit = $("submit");
  const alertBox = $("alert");
  const progress = $("progress");
  const fill = $("bar-fill");
  const progressText = $("progress-text");
  const result = $("result");
  const maxBytes = Number(document.querySelector("[data-max-bytes]").dataset.maxBytes);
  const maxMib = document.querySelector("[data-max-mib]").dataset.maxMib;

  const formatSize = (bytes) =>
    bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MiB` : `${Math.max(1, Math.round(bytes / 1024))} KiB`;

  function showError(message, title = "Couldn't transcribe this file") {
    $("alert-title").textContent = title;
    $("alert-message").textContent = message;
    alertBox.hidden = false;
  }
  function clearError() {
    alertBox.hidden = true;
    $("alert-message").textContent = "";
  }
  $("alert-close").addEventListener("click", clearError);

  function syncFile() {
    clearError();
    const file = input.files[0];
    chip.hidden = !file;
    submit.disabled = !file;
    if (!file) return;
    $("file-name").textContent = file.name;
    $("file-size").textContent = formatSize(file.size);
    if (file.size > maxBytes) {
      submit.disabled = true;
      showError(`This file is ${formatSize(file.size)}. The limit is ${maxMib} MiB.`, "File too large");
    }
  }

  input.addEventListener("change", syncFile);
  $("clear-file").addEventListener("click", () => {
    input.value = "";
    syncFile();
  });

  ["dragenter", "dragover"].forEach((name) =>
    dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      dropzone.classList.add("dragover");
    }));
  ["dragleave", "drop"].forEach((name) =>
    dropzone.addEventListener(name, () => dropzone.classList.remove("dragover")));
  dropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    if (event.dataTransfer.files.length) {
      input.files = event.dataTransfer.files;
      syncFile();
    }
  });

  function setProgress(visible) {
    progress.hidden = !visible;
    fill.classList.remove("indeterminate");
    fill.style.width = "0";
    progressText.textContent = "Uploading…";
  }

  form.addEventListener("htmx:beforeRequest", () => {
    clearError();
    result.replaceChildren();
    setProgress(true);
    submit.querySelector(".btn-label").textContent = "Working…";
  });

  // Upload progress; once every byte is sent the server is running the model.
  form.addEventListener("htmx:xhr:progress", (event) => {
    const { loaded, total, lengthComputable } = event.detail;
    if (!lengthComputable) return;
    if (loaded >= total) {
      fill.style.width = "";
      fill.classList.add("indeterminate");
      progressText.textContent = "Transcribing… this can take a little while.";
    } else {
      fill.style.width = `${Math.round((loaded / total) * 100)}%`;
    }
  });

  // The API reports errors as JSON; show its message instead of raw JSON.
  // htmx fires this on the swap target, which is outside the form, so listen higher.
  document.body.addEventListener("htmx:beforeSwap", (event) => {
    const xhr = event.detail.xhr;
    if (!(xhr.getResponseHeader("content-type") || "").includes("json")) return;
    let message = "Something went wrong. Please try again.";
    try {
      const { detail } = JSON.parse(xhr.responseText);
      if (typeof detail === "string") message = detail;
      else if (Array.isArray(detail)) message = detail.map((item) => item.msg).join("; ");
    } catch { /* keep the generic message */ }
    const titles = {
      400: "This file can't be read", 413: "File too large", 422: "Check your upload",
      429: "The server is busy", 503: "Transcription failed",
    };
    if (xhr.status === 429) message += " Please try again in a moment.";
    showError(message, titles[xhr.status]);
    event.detail.shouldSwap = false;
  });

  form.addEventListener("htmx:sendError", () =>
    showError("Check that the server is running and try again.", "Could not reach the server"));
  form.addEventListener("htmx:timeout", () =>
    showError("The request took too long. Try a shorter file.", "Request timed out"));

  form.addEventListener("htmx:afterRequest", () => {
    setProgress(false);
    submit.querySelector(".btn-label").textContent = "Transcribe";
    syncSubmitState();
  });
  function syncSubmitState() {
    submit.disabled = !input.files[0] || input.files[0].size > maxBytes;
  }

  result.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-action]");
    const transcript = $("transcript");
    if (!button || !transcript) return;
    const text = transcript.textContent;
    if (button.dataset.action === "copy") {
      try {
        await navigator.clipboard.writeText(text);
        button.textContent = "Copied ✓";
      } catch {
        button.textContent = "Copy failed";
      }
      setTimeout(() => { button.textContent = "Copy text"; }, 1800);
    } else {
      const name = (button.dataset.filename || "transcript").replace(/\.[^.]+$/, "");
      const link = document.createElement("a");
      link.href = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
      link.download = `${name}.txt`;
      link.click();
      URL.revokeObjectURL(link.href);
    }
  });
})();
