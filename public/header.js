// Inject OrionBelt logo, app name, and version badge into the Chainlit header
(function injectHeader() {
  var VERSION = "v0.5.0";
  var LOGO_DARK = "/public/logo_w.png";
  var LOGO_LIGHT = "/public/logo.png";
  var APP_NAME = "Chat";

  function insert() {
    if (document.querySelector(".orionbelt-header-brand")) return true;

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

    var headerBar = headerAnchor.parentElement;
    while (headerBar && headerBar.parentElement && headerBar.parentElement.id !== "root") {
      if (headerBar.offsetWidth > window.innerWidth * 0.8) break;
      headerBar = headerBar.parentElement;
    }

    headerBar.style.position = "relative";

    var brand = document.createElement("div");
    brand.className = "orionbelt-header-brand";

    var isDark = document.documentElement.classList.contains("dark") ||
      window.matchMedia("(prefers-color-scheme: dark)").matches;

    var logo = document.createElement("img");
    logo.src = isDark ? LOGO_DARK : LOGO_LIGHT;
    logo.alt = "OrionBelt";
    logo.className = "orionbelt-header-logo";

    // Switch logo when theme changes
    new MutationObserver(function () {
      var dark = document.documentElement.classList.contains("dark");
      logo.src = dark ? LOGO_DARK : LOGO_LIGHT;
    }).observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });

    var appName = document.createElement("span");
    appName.className = "orionbelt-header-name";
    appName.textContent = APP_NAME;

    brand.appendChild(logo);
    brand.appendChild(appName);
    headerBar.appendChild(brand);

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

// Pulse the avatar of the last assistant message while it has no text content
(function thinkingIndicator() {
  new MutationObserver(function () {
    // Find all images that could be assistant avatars
    var avatars = document.querySelectorAll("img");
    avatars.forEach(function (img) {
      // Skip non-avatar images (header logo, etc)
      if (img.classList.contains("orionbelt-header-logo")) return;
      if (img.width > 40 || img.height > 40) return;

      // Check if this avatar's sibling/parent message area has empty content
      var msgContainer = img.closest("[class]");
      if (!msgContainer) return;

      // Walk up a few levels to find the message wrapper
      var wrapper = msgContainer;
      for (var i = 0; i < 5; i++) {
        if (!wrapper.parentElement) break;
        wrapper = wrapper.parentElement;
      }

      // Check if this message block has meaningful text
      var textContent = wrapper.textContent.trim();
      // Remove the avatar alt text from consideration
      var alt = img.alt || "";
      textContent = textContent.replace(alt, "").trim();

      if (textContent === "") {
        img.classList.add("orionbelt-thinking");
      } else {
        img.classList.remove("orionbelt-thinking");
      }
    });
  }).observe(document.body, { childList: true, subtree: true, characterData: true });
})();

// Escape key → click the stop button to cancel generation
(function escapeToStop() {
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    // Find the Chainlit stop button (appears while streaming)
    var stopBtn = document.getElementById("stop-button") ||
      document.querySelector('button[id*="stop"]') ||
      document.querySelector('button svg title')?.closest("button");
    // Fallback: look for a button whose accessible label contains "stop"
    if (!stopBtn) {
      var buttons = document.querySelectorAll("button");
      for (var i = 0; i < buttons.length; i++) {
        var label = (buttons[i].getAttribute("aria-label") || buttons[i].textContent || "").toLowerCase();
        if (label.includes("stop")) { stopBtn = buttons[i]; break; }
      }
    }
    if (stopBtn) {
      stopBtn.click();
    }
  });
})();

// Arrow Up in empty input → recall last user message
(function arrowUpRecall() {
  var lastUserMessage = "";

  // Capture each user message when sent
  new MutationObserver(function () {
    // User messages have data-message-author="user" or similar markers
    var userMsgs = document.querySelectorAll('[class*="userMessage"], [data-message-author="user"]');
    if (userMsgs.length === 0) {
      // Fallback: grab the last message that appears on the right side
      var allMsgs = document.querySelectorAll(".markdown-body, [class*=\"message\"]");
      // Not reliable enough alone, so also track via keydown
    }
    if (userMsgs.length > 0) {
      var last = userMsgs[userMsgs.length - 1];
      var text = (last.textContent || "").trim();
      if (text) lastUserMessage = text;
    }
  }).observe(document.body, { childList: true, subtree: true });

  // Also capture via form submission / Enter key
  document.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      var textarea = document.querySelector("textarea");
      if (textarea && textarea.value.trim()) {
        lastUserMessage = textarea.value.trim();
      }
    }
  }, true);

  // Arrow Up when input is empty → fill with last message
  document.addEventListener("keydown", function (e) {
    if (e.key !== "ArrowUp") return;
    var textarea = document.querySelector("textarea");
    if (!textarea || document.activeElement !== textarea) return;
    // Only recall when the input is empty
    if (textarea.value.trim() !== "") return;
    if (!lastUserMessage) return;
    e.preventDefault();
    // Set value via native input setter to trigger React state update
    var nativeSetter = Object.getOwnPropertyDescriptor(
      window.HTMLTextAreaElement.prototype, "value"
    ).set;
    nativeSetter.call(textarea, lastUserMessage);
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    // Move cursor to end
    textarea.selectionStart = textarea.selectionEnd = lastUserMessage.length;
  });
})();
