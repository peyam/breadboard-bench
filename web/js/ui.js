// Small dialogs that keep the page's look (instead of the browser's prompt boxes).
import { h } from "./util.js";

export function askText(title, value = "", { hint = "", ok = "OK", pattern = null } = {}) {
  return new Promise((resolve) => {
    const input = h("input", { class: "input mono", value, spellcheck: "false", "aria-label": title, style: { width: "100%" } });
    const err = h("div", { class: "hint", style: { color: "var(--danger)", minHeight: "1.2em", fontSize: "12px" } });
    const dlg = h("dialog", { class: "dlg" },
      h("form", { method: "dialog" },
        h("h4", { text: title }),
        hint ? h("p", { class: "hint", text: hint }) : null,
        input, err,
        h("div", { class: "row" },
          h("button", { class: "btn", value: "cancel", type: "button", onclick: () => dlg.close("cancel") }, "Cancel"),
          h("button", { class: "btn primary", value: "ok", type: "submit" }, ok))));
    dlg.querySelector("form").addEventListener("submit", (e) => {
      if (pattern && !pattern.test(input.value.trim())) { e.preventDefault(); err.textContent = "Use letters, digits and _ only."; }
    });
    dlg.addEventListener("close", () => { const v = dlg.returnValue === "ok" ? input.value.trim() : null; dlg.remove(); resolve(v || null); });
    document.body.append(dlg);
    dlg.showModal();
    input.select();
  });
}
