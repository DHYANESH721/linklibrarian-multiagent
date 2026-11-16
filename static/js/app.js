/* LinkLibrarian front end */
(function () {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  const addForm    = $("#add-form");
  const urlInput   = $("#url-input");
  const addButton  = $("#add-button");
  const statusEl   = $("#add-status");
  const readerEl   = $("#reader");
  const cardsEl    = $("#cards");
  const modalEl    = $("#edit-modal");
  const editForm   = $("#edit-form");
  const editError  = $("#edit-error");

  /* ---------------------------------------------------------------- api */
  async function api(url, options = {}) {
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    let body = {};
    try { body = await res.json(); } catch (_) {
      throw new Error("Server sent an unreadable response.");
    }
    if (!res.ok || body.success === false) {
      const err = new Error(body.error || `Request failed (${res.status}).`);
      err.status = res.status;
      throw err;
    }
    return body.data;
  }

  /* --------------------------------------------------------------- toast */
  function toast(msg, isError = false) {
    const el = document.createElement("div");
    el.className = "toast" + (isError ? " toast--error" : "");
    el.setAttribute("role", "status");
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3500);
  }

  /* -------------------------------------------------------------- status */
  function setStatus(msg, kind = "") {
    if (!statusEl) return;
    statusEl.textContent = msg;
    statusEl.className = "deposit__status" + (kind ? " is-" + kind : "");
  }

  /* ------------------------------------------------------------ reader */
  let readerTimers = [];

  function startReader() {
    if (!readerEl) return;
    readerEl.removeAttribute("hidden");
    readerEl.setAttribute("aria-hidden", "false");
    const steps = $$("li", readerEl);
    steps.forEach(s => s.className = "");
    if (steps[0]) steps[0].className = "is-active";

    /* move the highlight from one agent to the next while the server works */
    const delays = [1200, 2200, 3600, 4800, 5800];
    readerTimers = delays.map((ms, n) => setTimeout(() => {
      steps.forEach((s, i) => s.className = i <= n ? "is-done" : i === n + 1 ? "is-active" : "");
    }, ms));
  }

  function stopReader() {
    readerTimers.forEach(clearTimeout);
    readerTimers = [];
    if (!readerEl) return;
    readerEl.setAttribute("hidden", "");
    readerEl.setAttribute("aria-hidden", "true");
  }

  /* Summarise which agents worked on the link, e.g.
     "✓ Filed by 6 agents · Quality Checker asked for 1 redo" */
  function agentReport(data) {
    const trace  = data.agents || [];
    const names  = new Set(trace.map(step => step.agent));
    const redos  = trace.filter(step => step.agent === "Quality Checker Agent"
                                     && step.action.startsWith("rejected")).length;
    let msg = `✓ Filed by ${names.size || 6} agents`;
    if (redos) msg += ` · Quality Checker asked for ${redos} redo${redos > 1 ? "s" : ""}`;
    msg += data.ai_generated ? " · AI summary" : " · offline mode";
    return msg + ". Reloading…";
  }

  /* --------------------------------------------------------------- add */
  if (addForm) {
    addForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const url = urlInput.value.trim();
      if (!url) { setStatus("Enter a URL to save.", "error"); return; }

      addButton.disabled = true;
      addButton.textContent = "Filing…";
      setStatus("The agent team is working on it — this takes a few seconds…");
      startReader();

      try {
        const data = await api("/api/links", {
          method: "POST",
          body: JSON.stringify({ url }),
        });
        stopReader();
        urlInput.value = "";
        setStatus(agentReport(data), "good");
        setTimeout(() => window.location.reload(), 1800);
      } catch (err) {
        stopReader();
        setStatus(err.message, "error");
        addButton.disabled = false;
        addButton.textContent = "File it";
      }
    });
  }

  /* --------------------------------------------------------- card actions */
  if (cardsEl) {
    cardsEl.addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-action]");
      if (!btn) return;

      const card = btn.closest(".card");
      const id   = card ? card.dataset.id : null;
      if (!id) return;

      /* DELETE */
      if (btn.dataset.action === "delete") {
        if (!confirm("Delete this card? This cannot be undone.")) return;
        btn.disabled = true;
        try {
          await api(`/api/links/${id}`, { method: "DELETE" });
          card.style.transition = "opacity .25s, transform .25s";
          card.style.opacity = "0";
          card.style.transform = "translateY(-8px)";
          setTimeout(() => { card.remove(); toast("Card deleted."); }, 250);
        } catch (err) {
          btn.disabled = false;
          toast(err.message, true);
        }
        return;
      }

      /* REFRESH */
      if (btn.dataset.action === "refresh") {
        btn.disabled = true;
        btn.textContent = "Reading…";
        try {
          await api(`/api/links/${id}/refresh`, { method: "POST" });
          toast("Re-read complete. Reloading…");
          setTimeout(() => window.location.reload(), 600);
        } catch (err) {
          btn.disabled = false;
          btn.textContent = "Re-read";
          toast(err.message, true);
        }
        return;
      }

      /* EDIT */
      if (btn.dataset.action === "edit") {
        openEditor(card, btn.dataset);
      }
    });
  }

  /* -------------------------------------------------------------- editor */
  function openEditor(card, data) {
    if (!modalEl) return;
    $("#edit-id").value            = card.dataset.id;
    $("#edit-url").value           = card.dataset.url;
    $("#edit-title-input").value   = data.title    || "";
    $("#edit-summary").value       = data.summary  || "";
    $("#edit-category").value      = data.category || "";
    /* tags come in as "python,flask,api" — show as "python, flask, api" */
    const rawTags = (data.tags || "").split(",").map(t => t.trim()).filter(Boolean);
    $("#edit-tags").value = rawTags.join(", ");
    if (editError) editError.textContent = "";
    modalEl.removeAttribute("hidden");
    const titleInput = $("#edit-title-input");
    if (titleInput) titleInput.focus();
  }

  function closeEditor() {
    if (modalEl) modalEl.setAttribute("hidden", "");
  }

  if (modalEl) {
    modalEl.addEventListener("click", (e) => {
      if (e.target.hasAttribute("data-close") || e.target === modalEl) closeEditor();
    });
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modalEl && !modalEl.hasAttribute("hidden")) closeEditor();
  });

  if (editForm) {
    editForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const id = $("#edit-id").value;
      if (editError) editError.textContent = "";

      try {
        await api(`/api/links/${id}`, {
          method: "PUT",
          body: JSON.stringify({
            url:      $("#edit-url").value.trim(),
            title:    $("#edit-title-input").value.trim(),
            summary:  $("#edit-summary").value.trim(),
            category: $("#edit-category").value.trim(),
            tags:     $("#edit-tags").value.trim(),
          }),
        });
        closeEditor();
        toast("Changes saved. Reloading…");
        setTimeout(() => window.location.reload(), 600);
      } catch (err) {
        if (editError) editError.textContent = err.message;
      }
    });
  }

  /* -------------------------------------------------- live search debounce */
  const searchInput = $("#search-input");
  if (searchInput) {
    let timer;
    searchInput.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(() => searchInput.closest("form").submit(), 600);
    });
  }

})();
