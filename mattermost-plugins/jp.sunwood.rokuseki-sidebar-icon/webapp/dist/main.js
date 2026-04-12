(function () {
  const PLUGIN_ID = "jp.sunwood.rokuseki-sidebar-icon";
  const TEAM_SLUG = "openclaw";
  const CHANNEL_SLUG = "triad-lab";
  const SIDEBAR_CREST_CLASS = "rokuseki-sidebar-crest";
  const SIDEBAR_ICON_HIDDEN_CLASS = "rokuseki-sidebar-icon-hidden";
  const STYLE_ID = "rokuseki-sidebar-icon-style";
  const TARGET_PATH = `/${TEAM_SLUG}/channels/${CHANNEL_SLUG}`;
  const TARGET_LABEL = "ろくせき談話室";

  function createCrestSvg() {
    return `
      <svg viewBox="0 0 120 120" aria-hidden="true" focusable="false">
        <defs>
          <linearGradient id="rokuseki-sidebar-bg" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="#15284f"></stop>
            <stop offset="100%" stop-color="#5da4e8"></stop>
          </linearGradient>
          <linearGradient id="rokuseki-sidebar-ring" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="#f5fbff"></stop>
            <stop offset="100%" stop-color="#91d8ff"></stop>
          </linearGradient>
        </defs>
        <rect width="120" height="120" rx="28" fill="url(#rokuseki-sidebar-bg)"></rect>
        <circle cx="60" cy="60" r="40" fill="none" stroke="rgba(255,255,255,0.28)" stroke-width="4"></circle>
        <circle cx="60" cy="60" r="52" fill="none" stroke="rgba(255,255,255,0.14)" stroke-width="6"></circle>
        <path d="M60 18 L70 48 L102 60 L70 72 L60 102 L50 72 L18 60 L50 48 Z" fill="url(#rokuseki-sidebar-ring)"></path>
        <circle cx="60" cy="60" r="11" fill="#ffffff"></circle>
        <circle cx="60" cy="60" r="4.5" fill="#5da4e8"></circle>
      </svg>
    `;
  }

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) {
      return;
    }

    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      .${SIDEBAR_CREST_CLASS} {
        display: inline-flex;
        width: 18px;
        height: 18px;
        margin-right: 8px;
        margin-left: -1px;
        border-radius: 6px;
        overflow: hidden;
        flex: 0 0 18px;
      }

      .${SIDEBAR_CREST_CLASS} svg {
        width: 18px;
        height: 18px;
      }

      .${SIDEBAR_ICON_HIDDEN_CLASS} {
        display: none !important;
      }
    `;

    document.head.appendChild(style);
  }

  function findSidebarLabelNodes() {
    return [...document.querySelectorAll("span, strong, div, a, button")]
      .filter((el) => (el.textContent || "").trim() === TARGET_LABEL);
  }

  function ensureSidebarCrest() {
    for (const label of findSidebarLabelNodes()) {
      const row =
        label.closest('a, button, li, [class*="SidebarChannel"], [class*="SidebarLink"], [class*="SidebarItem"]') ||
        label.parentElement;

      if (!row) {
        continue;
      }

      if (!row.querySelector(`.${SIDEBAR_CREST_CLASS}`)) {
        const crest = document.createElement("span");
        crest.className = SIDEBAR_CREST_CLASS;
        crest.setAttribute("aria-hidden", "true");
        crest.innerHTML = createCrestSvg();
        label.parentElement?.insertBefore(crest, label);
      }

      const icon = row.querySelector('svg, i[class*="icon"], span[class*="icon"]');
      if (icon) {
        icon.classList.add(SIDEBAR_ICON_HIDDEN_CLASS);
      }
    }
  }

  function removeSidebarCrests() {
    document.querySelectorAll(`.${SIDEBAR_CREST_CLASS}`).forEach((el) => el.remove());
    document.querySelectorAll(`.${SIDEBAR_ICON_HIDDEN_CLASS}`).forEach((el) => el.classList.remove(SIDEBAR_ICON_HIDDEN_CLASS));
  }

  function isTargetChannel() {
    const path = window.location.pathname || "";
    const hash = window.location.hash || "";
    return path.includes(TARGET_PATH) || hash.includes(TARGET_PATH);
  }

  function syncSidebarIcon() {
    if (!document.body) {
      return;
    }

    if (isTargetChannel()) {
      ensureStyle();
      ensureSidebarCrest();
      return;
    }

    removeSidebarCrests();
  }

  class RokusekiSidebarIconPlugin {
    initialize() {
      this.interval = window.setInterval(syncSidebarIcon, 1500);
      this.observer = new MutationObserver(syncSidebarIcon);
      this.observer.observe(document.documentElement, {
        childList: true,
        subtree: true
      });

      window.addEventListener("hashchange", syncSidebarIcon);
      window.addEventListener("popstate", syncSidebarIcon);
      syncSidebarIcon();
    }

    uninitialize() {
      if (this.interval) {
        window.clearInterval(this.interval);
      }
      if (this.observer) {
        this.observer.disconnect();
      }
      removeSidebarCrests();
      window.removeEventListener("hashchange", syncSidebarIcon);
      window.removeEventListener("popstate", syncSidebarIcon);
    }
  }

  window.registerPlugin(PLUGIN_ID, new RokusekiSidebarIconPlugin());
})();
