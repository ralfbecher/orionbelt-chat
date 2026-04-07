// Inject OrionBelt logo, app name, and version badge into the Chainlit header
(function injectHeader() {
  var VERSION = "v0.5.0";
  var LOGO_URL = "/public/logo_w.png";
  var APP_NAME = "Chat";

  function insert() {
    if (document.querySelector(".orionbelt-header-brand")) return true;

    // Find header links ("Readme", "GitHub", "Report Issue")
    var allAnchors = document.querySelectorAll("a");
    var headerAnchor = null;
    for (var i = 0; i < allAnchors.length; i++) {
      var text = allAnchors[i].textContent.trim();
      if (text === "GitHub" || text === "Report Issue" || text === "Readme") {
        headerAnchor = allAnchors[i];
        break;
      }
    }

    if (!headerAnchor) return false;

    // Walk up to find the top-level header bar
    var headerBar = headerAnchor.parentElement;
    while (headerBar && headerBar.parentElement && headerBar.parentElement.id !== "root") {
      if (headerBar.offsetWidth > window.innerWidth * 0.8) break;
      headerBar = headerBar.parentElement;
    }

    // Make header bar a positioning context
    headerBar.style.position = "relative";

    // -- Left side: logo + app name (absolutely positioned) --
    var brand = document.createElement("div");
    brand.className = "orionbelt-header-brand";

    var logo = document.createElement("img");
    logo.src = LOGO_URL;
    logo.alt = "OrionBelt";
    logo.className = "orionbelt-header-logo";

    var appName = document.createElement("span");
    appName.className = "orionbelt-header-name";
    appName.textContent = APP_NAME;

    brand.appendChild(logo);
    brand.appendChild(appName);
    headerBar.appendChild(brand);

    // -- Version badge: insert before the first header link --
    var linksParent = headerAnchor.parentElement;
    var badge = document.createElement("span");
    badge.className = "orionbelt-version";
    badge.textContent = VERSION;
    linksParent.insertBefore(badge, linksParent.firstChild);

    return true;
  }

  if (!insert()) {
    var observer = new MutationObserver(function () {
      if (insert()) observer.disconnect();
    });
    observer.observe(document.body, { childList: true, subtree: true });
    setTimeout(function () { observer.disconnect(); }, 15000);
  }
})();
