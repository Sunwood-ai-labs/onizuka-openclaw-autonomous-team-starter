(function () {
  const PLUGIN_ID = "jp.sunwood.rokuseki-brand";
  const TEAM_SLUG = "openclaw";
  const CHANNEL_SLUG = "triad-lab";
  const PANEL_ID = "rokuseki-channel-brand-panel";
  const STYLE_ID = "rokuseki-channel-brand-style";
  const BUTTON_TITLE = "六席印";

  const TARGET_PATH = `/${TEAM_SLUG}/channels/${CHANNEL_SLUG}`;

  function createCrestSvg() {
    return `
      <svg viewBox="0 0 120 120" aria-hidden="true" focusable="false">
        <defs>
          <linearGradient id="rokuseki-bg" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="#15284f"></stop>
            <stop offset="100%" stop-color="#5da4e8"></stop>
          </linearGradient>
          <linearGradient id="rokuseki-ring" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="#f5fbff"></stop>
            <stop offset="100%" stop-color="#91d8ff"></stop>
          </linearGradient>
        </defs>
        <rect width="120" height="120" rx="28" fill="url(#rokuseki-bg)"></rect>
        <circle cx="60" cy="60" r="40" fill="none" stroke="rgba(255,255,255,0.28)" stroke-width="4"></circle>
        <circle cx="60" cy="60" r="52" fill="none" stroke="rgba(255,255,255,0.14)" stroke-width="6"></circle>
        <path d="M60 18 L70 48 L102 60 L70 72 L60 102 L50 72 L18 60 L50 48 Z" fill="url(#rokuseki-ring)"></path>
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
      #${PANEL_ID} {
        position: fixed;
        top: 72px;
        right: 24px;
        z-index: 60;
        width: 332px;
        border-radius: 22px;
        overflow: hidden;
        background:
          radial-gradient(circle at top left, rgba(255,255,255,0.22), transparent 42%),
          linear-gradient(135deg, #0f1730, #25406f 48%, #6faee5 100%);
        color: #f7fbff;
        box-shadow: 0 18px 44px rgba(8, 12, 26, 0.24);
        border: 1px solid rgba(255,255,255,0.14);
        font-family: "Segoe UI", "Yu Gothic UI", sans-serif;
      }

      #${PANEL_ID} * {
        box-sizing: border-box;
      }

      #${PANEL_ID} .rokuseki-card {
        padding: 16px 16px 14px;
      }

      #${PANEL_ID} .rokuseki-top {
        display: flex;
        align-items: center;
        gap: 12px;
      }

      #${PANEL_ID} .rokuseki-crest {
        width: 56px;
        height: 56px;
        flex: 0 0 56px;
      }

      #${PANEL_ID} .rokuseki-label {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: rgba(255,255,255,0.76);
      }

      #${PANEL_ID} .rokuseki-title {
        margin-top: 4px;
        font-size: 22px;
        line-height: 1.15;
        font-weight: 800;
      }

      #${PANEL_ID} .rokuseki-copy {
        margin-top: 12px;
        font-size: 13px;
        line-height: 1.55;
        color: rgba(255,255,255,0.86);
      }

      #${PANEL_ID} .rokuseki-roster {
        margin-top: 12px;
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
      }

      #${PANEL_ID} .rokuseki-chip {
        padding: 8px 10px;
        border-radius: 14px;
        background: rgba(255,255,255,0.12);
        border: 1px solid rgba(255,255,255,0.12);
        min-height: 52px;
      }

      #${PANEL_ID} .rokuseki-chip-name {
        font-size: 12px;
        font-weight: 700;
      }

      #${PANEL_ID} .rokuseki-chip-role {
        margin-top: 2px;
        font-size: 11px;
        line-height: 1.35;
        color: rgba(255,255,255,0.82);
      }

      #${PANEL_ID} .rokuseki-chip-model {
        margin-top: 4px;
        font-size: 10px;
        line-height: 1.25;
        color: rgba(210, 235, 255, 0.92);
      }

      @media (max-width: 1200px) {
        #${PANEL_ID} {
          width: 296px;
          top: 64px;
          right: 12px;
        }
      }

      @media (max-width: 900px) {
        #${PANEL_ID} {
          display: none;
        }
      }
    `;

    document.head.appendChild(style);
  }

  function panelMarkup() {
    return `
      <div class="rokuseki-card">
        <div class="rokuseki-top">
          <div class="rokuseki-crest">${createCrestSvg()}</div>
          <div>
            <div class="rokuseki-label">Channel Crest</div>
            <div class="rokuseki-title">ろくせき談話室</div>
          </div>
        </div>
        <div class="rokuseki-copy">
          GLM三席とGemini三席が同居する談話室です。標準のチャンネルアイコンの代わりに、
          このクレストをチャンネル専用のブランドマークとして表示します。
        </div>
        <div class="rokuseki-roster">
          <div class="rokuseki-chip"><div class="rokuseki-chip-name">いおり</div><div class="rokuseki-chip-role">星図航路士</div><div class="rokuseki-chip-model">glm-5.1</div></div>
          <div class="rokuseki-chip"><div class="rokuseki-chip-name">つむぎ</div><div class="rokuseki-chip-role">夢写本師</div><div class="rokuseki-chip-model">glm-5-turbo</div></div>
          <div class="rokuseki-chip"><div class="rokuseki-chip-name">さく</div><div class="rokuseki-chip-role">痕跡鑑識官</div><div class="rokuseki-chip-model">glm-5</div></div>
          <div class="rokuseki-chip"><div class="rokuseki-chip-name">るり</div><div class="rokuseki-chip-role">信号地図師</div><div class="rokuseki-chip-model">gemma-4-31b-it</div></div>
          <div class="rokuseki-chip"><div class="rokuseki-chip-name">ひびき</div><div class="rokuseki-chip-role">拍子調律師</div><div class="rokuseki-chip-model">gemma-3-27b-it</div></div>
          <div class="rokuseki-chip"><div class="rokuseki-chip-name">かなえ</div><div class="rokuseki-chip-role">検証編み手</div><div class="rokuseki-chip-model">gemma-4-26b-a4b-it</div></div>
        </div>
      </div>
    `;
  }

  function ensurePanel() {
    if (document.getElementById(PANEL_ID)) {
      return;
    }

    const panel = document.createElement("aside");
    panel.id = PANEL_ID;
    panel.setAttribute("aria-label", "ろくせき談話室 brand panel");
    panel.innerHTML = panelMarkup();
    document.body.appendChild(panel);
  }

  function removePanel() {
    document.getElementById(PANEL_ID)?.remove();
  }

  function isTargetChannel() {
    const path = window.location.pathname || "";
    const hash = window.location.hash || "";
    return path.includes(TARGET_PATH) || hash.includes(TARGET_PATH);
  }

  function syncPanel() {
    if (!document.body) {
      return;
    }

    if (isTargetChannel()) {
      ensureStyle();
      ensurePanel();
      return;
    }

    removePanel();
  }

  class RokusekiBrandPlugin {
    initialize(registry) {
      this.interval = window.setInterval(syncPanel, 1200);
      this.observer = new MutationObserver(syncPanel);
      this.observer.observe(document.documentElement, {
        childList: true,
        subtree: true,
      });

      window.addEventListener("hashchange", syncPanel);
      window.addEventListener("popstate", syncPanel);

      if (window.React) {
        const icon = window.React.createElement(
          "span",
          {
            style: {
              display: "inline-flex",
              width: "18px",
              height: "18px",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "16px",
            },
          },
          "✦"
        );

        registry.registerChannelHeaderButtonAction(
          icon,
          () => {
            syncPanel();
            const panel = document.getElementById(PANEL_ID);
            if (panel) {
              panel.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
              panel.animate(
                [
                  { transform: "translateY(0)", boxShadow: "0 18px 44px rgba(8, 12, 26, 0.24)" },
                  { transform: "translateY(-4px)", boxShadow: "0 24px 60px rgba(8, 12, 26, 0.34)" },
                  { transform: "translateY(0)", boxShadow: "0 18px 44px rgba(8, 12, 26, 0.24)" },
                ],
                { duration: 460, easing: "ease-out" }
              );
            }
          },
          BUTTON_TITLE
        );
      }

      syncPanel();
    }

    uninitialize() {
      if (this.interval) {
        window.clearInterval(this.interval);
      }
      if (this.observer) {
        this.observer.disconnect();
      }
      removePanel();
      window.removeEventListener("hashchange", syncPanel);
      window.removeEventListener("popstate", syncPanel);
    }
  }

  window.registerPlugin(PLUGIN_ID, new RokusekiBrandPlugin());
})();
