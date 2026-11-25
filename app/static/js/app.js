(function () {
  "use strict";

  // Mobile navigation
  var toggle = document.querySelector("[data-nav-toggle]");
  var nav = document.getElementById("mainNav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.setAttribute("aria-label", open ? "إغلاق القائمة" : "فتح القائمة");
    });
  }

  // Confirm destructive forms
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    var message = form.getAttribute("data-confirm");
    if (message && !window.confirm(message)) {
      event.preventDefault();
    }
  });

  // Print (CV page)
  document.querySelectorAll("[data-print]").forEach(function (btn) {
    btn.addEventListener("click", function () { window.print(); });
  });

  // Copy to clipboard (admin reset link)
  document.querySelectorAll("[data-copy-target]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var input = document.querySelector(btn.getAttribute("data-copy-target"));
      if (!input) return;
      var done = function () {
        var old = btn.textContent;
        btn.textContent = "تم النسخ";
        setTimeout(function () { btn.textContent = old; }, 1600);
      };
      if (navigator.clipboard) {
        navigator.clipboard.writeText(input.value).then(done).catch(function () { input.select(); });
      } else {
        input.select();
        document.execCommand("copy");
        done();
      }
    });
  });

  // Repeatable rows (profile page)
  function renumber(rows) {
    rows.querySelectorAll("[data-row]").forEach(function (row, index) {
      row.querySelectorAll("[name]").forEach(function (input) {
        input.name = input.name.replace(/\[\d+\]/, "[" + index + "]");
      });
    });
  }

  document.querySelectorAll("[data-add-row]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var rows = document.querySelector(btn.getAttribute("data-add-row"));
      var templateId = btn.getAttribute("data-template");
      var template = templateId && document.getElementById(templateId);
      if (!rows || !template) return;
      var html = template.innerHTML.replace(/__INDEX__/g, String(rows.querySelectorAll("[data-row]").length));
      var holder = document.createElement("div");
      holder.innerHTML = html.trim();
      var node = holder.firstElementChild;
      rows.appendChild(node);
      var first = node.querySelector("input, select, textarea");
      if (first) first.focus();
      renumber(rows);
    });
  });

  document.addEventListener("click", function (event) {
    var btn = event.target.closest("[data-remove-row]");
    if (!btn) return;
    var row = btn.closest("[data-row]");
    if (!row) return;
    var rows = row.parentElement;
    row.remove();
    renumber(rows);
  });

  // Password reveal
  document.querySelectorAll("[data-toggle-password]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var input = document.getElementById(btn.getAttribute("data-toggle-password"));
      if (!input) return;
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.textContent = show ? "إخفاء" : "عرض";
    });
  });
})();
