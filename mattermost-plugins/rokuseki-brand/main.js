(function () {
  const PLUGIN_ID = "jp.sunwood.rokuseki-brand";
  const TEAM_SLUG = "openclaw";
  const CHANNEL_SLUG = "triad-lab";
  const HERO_ID = "rokuseki-channel-brand-hero";
  const HEADER_CREST_ID = "rokuseki-channel-header-crest";
  const STYLE_ID = "rokuseki-channel-brand-style";
  const BUTTON_TITLE = "Crest";

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
      #${HERO_ID} {
        margin: 0 auto 14px;
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
      }

      #${HERO_ID} .rokuseki-hero-crest {
        width: 168px;
        height: 168px;
        margin-bottom: 18px;
        filter: drop-shadow(0 16px 26px rgba(14, 28, 58, 0.18));
      }

      #${HERO_ID} .rokuseki-hero-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 14px;
        border-radius: 999px;
        background: linear-gradient(135deg, #18325e, #578fce);
        color: #f8fbff;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.04em;
        box-shadow: 0 10px 24px rgba(19, 34, 70, 0.16);
      }

      #${HERO_ID} .rokuseki-hero-copy {
        margin-top: 12px;
        max-width: 540px;
        color: rgba(var(--center-channel-color-rgb), 0.8);
        line-height: 1.55;
        font-size: 14px;
      }

      #${HEADER_CREST_ID} {
        display: inline-flex;
        width: 32px;
        height: 32px;
        margin-right: 10px;
        align-items: center;
        justify-content: center;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 8px 18px rgba(18, 32, 62, 0.18);
        flex: 0 0 32px;
      }

      #channel-header .channel-header__top {
        display: flex;
        align-items: center;
      }

      #channelIntro.rokuseki-intro-patched > svg:first-of-type {
        display: none !important;
      }

      #channelIntro.rokuseki-intro-patched .channel-intro__title {
        margin-top: 4px;
      }
    `;

    document.head.appendChild(style);
  }

  function heroMarkup() {
    return `
      <div class="rokuseki-hero-crest">${createCrestSvg()}</div>
      <div class="rokuseki-hero-badge">CHANNEL CREST ・ ろくせき談話室</div>
      <div class="rokuseki-hero-copy">
        Mattermost 標準のチャンネル導入イラストの代わりに、六席チーム専用のクレストを表示します。
      </div>
    `;
  }

  function ensureIntroHero() {
    const intro = document.getElementById("channelIntro");
    if (!intro) {
      return;
    }

    intro.classList.add("rokuseki-intro-patched");

    if (document.getElementById(HERO_ID)) {
      return;
    }

    const title = intro.querySelector(".channel-intro__title");
    if (!title) {
      return;
    }

    const hero = document.createElement("div");
    hero.id = HERO_ID;
    hero.innerHTML = heroMarkup();
    intro.insertBefore(hero, title);
  }

  function ensureHeaderCrest() {
    const top = document.querySelector("#channel-header .channel-header__top");
    if (!top || document.getElementById(HEADER_CREST_ID)) {
      return;
    }

    const crest = document.createElement("span");
    crest.id = HEADER_CREST_ID;
    crest.setAttribute("aria-label", "ろくせき談話室 crest");
    crest.innerHTML = createCrestSvg();
    top.insertBefore(crest, top.firstChild);
  }

  function removeIntroHero() {
    document.getElementById(HERO_ID)?.remove();
    const intro = document.getElementById("channelIntro");
    if (intro) {
      intro.classList.remove("rokuseki-intro-patched");
    }
  }

  function removeHeaderCrest() {
    document.getElementById(HEADER_CREST_ID)?.remove();
  }

  function isTargetChannel() {
    const path = window.location.pathname || "";
    const hash = window.location.hash || "";
    return path.includes(TARGET_PATH) || hash.includes(TARGET_PATH);
  }

  function syncBrand() {
    if (!document.body) {
      return;
    }

    if (isTargetChannel()) {
      ensureStyle();
      ensureIntroHero();
      ensureHeaderCrest();
      return;
    }

    removeIntroHero();
    removeHeaderCrest();
  }

  class RokusekiBrandPlugin {
    initialize(registry) {
      this.interval = window.setInterval(syncBrand, 1200);
      this.observer = new MutationObserver(syncBrand);
      this.observer.observe(document.documentElement, {
        childList: true,
        subtree: true,
      });

      window.addEventListener("hashchange", syncBrand);
      window.addEventListener("popstate", syncBrand);

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
            syncBrand();
            const crest = document.getElementById(HEADER_CREST_ID);
            if (crest) {
              crest.animate(
                [
                  { transform: "scale(1)", boxShadow: "0 8px 18px rgba(18, 32, 62, 0.18)" },
                  { transform: "scale(1.08)", boxShadow: "0 12px 26px rgba(18, 32, 62, 0.28)" },
                  { transform: "scale(1)", boxShadow: "0 8px 18px rgba(18, 32, 62, 0.18)" },
                ],
                { duration: 360, easing: "ease-out" }
              );
            }
          },
          BUTTON_TITLE
        );
      }

      syncBrand();
    }

    uninitialize() {
      if (this.interval) {
        window.clearInterval(this.interval);
      }
      if (this.observer) {
        this.observer.disconnect();
      }
      removeIntroHero();
      removeHeaderCrest();
      window.removeEventListener("hashchange", syncBrand);
      window.removeEventListener("popstate", syncBrand);
    }
  }

  window.registerPlugin(PLUGIN_ID, new RokusekiBrandPlugin());
})();
