(function () {
  const PLUGIN_ID = "jp.sunwood.rokuseki-sidebar-icon";
  const STYLE_ID = "rokuseki-sidebar-icon-style";
  const SIDEBAR_ROW_SELECTOR = [
    "#sidebarItem_triad-lab",
    'a.SidebarLink[href="/openclaw/channels/triad-lab"]',
    'a[aria-label="ろくせき談話室 公開チャンネル"]'
  ].join(", ");

  function crestDataUrl() {
    const svg = `
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120">
        <defs>
          <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="#15284f"/>
            <stop offset="100%" stop-color="#5da4e8"/>
          </linearGradient>
          <linearGradient id="ring" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="#f5fbff"/>
            <stop offset="100%" stop-color="#91d8ff"/>
          </linearGradient>
        </defs>
        <rect width="120" height="120" rx="28" fill="url(#bg)"/>
        <circle cx="60" cy="60" r="40" fill="none" stroke="rgba(255,255,255,0.28)" stroke-width="4"/>
        <circle cx="60" cy="60" r="52" fill="none" stroke="rgba(255,255,255,0.14)" stroke-width="6"/>
        <path d="M60 18 L70 48 L102 60 L70 72 L60 102 L50 72 L18 60 L50 48 Z" fill="url(#ring)"/>
        <circle cx="60" cy="60" r="11" fill="#ffffff"/>
        <circle cx="60" cy="60" r="4.5" fill="#5da4e8"/>
      </svg>
    `.replace(/\s+/g, " ").trim();

    return `data:image/svg+xml,${encodeURIComponent(svg)}`;
  }

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) {
      return;
    }

    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      ${SIDEBAR_ROW_SELECTOR} {
        display: flex;
        align-items: center;
      }

      ${SIDEBAR_ROW_SELECTOR} > i.icon-globe,
      ${SIDEBAR_ROW_SELECTOR} > i.icon.icon-globe,
      ${SIDEBAR_ROW_SELECTOR} > [class*="icon-globe"] {
        display: none !important;
      }

      ${SIDEBAR_ROW_SELECTOR}::before {
        content: "";
        width: 18px;
        height: 18px;
        flex: 0 0 18px;
        margin-right: 8px;
        border-radius: 6px;
        background-image: url("${crestDataUrl()}");
        background-size: cover;
        background-repeat: no-repeat;
        background-position: center;
      }
    `;

    document.head.appendChild(style);
  }

  class RokusekiSidebarIconPlugin {
    initialize() {
      ensureStyle();
    }

    uninitialize() {
      document.getElementById(STYLE_ID)?.remove();
    }
  }

  window.registerPlugin(PLUGIN_ID, new RokusekiSidebarIconPlugin());
})();
