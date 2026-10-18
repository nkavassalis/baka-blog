/* Rewrites [data-date] elements to relative dates ("today", "yesterday",
 * "N days ago") for posts under 30 days old. Servers render the absolute
 * MM/DD/YYYY text in the markup, so if this file never runs (JS disabled,
 * fetch blocked, crawler) the absolute date simply remains. */
(function () {
  var now = Date.now();
  var items = document.querySelectorAll("[data-date]");
  for (var i = 0; i < items.length; i++) {
    var el = items[i];
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(el.getAttribute("data-date") || "");
    if (!m) continue;
    var d = new Date(+m[1], +m[2] - 1, +m[3]);
    if (isNaN(d.getTime())) continue;
    var days = Math.floor((now - d.getTime()) / 86400000);
    if (days < 0 || days >= 30) continue; // keep absolute
    el.textContent = days === 0 ? "today" : days === 1 ? "yesterday" : days + " days ago";
    el.setAttribute("title", el.getAttribute("data-date"));
  }
})();
