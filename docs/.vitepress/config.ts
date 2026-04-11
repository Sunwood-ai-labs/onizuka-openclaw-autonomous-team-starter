import { defineConfig } from "vitepress";

const repo = "https://github.com/Sunwood-ai-labs/onizuka-openclaw-autonomous-team-starter";

export default defineConfig({
  title: "onizuka-openclaw-autonomous-team-starter",
  description:
    "Windows-first ONIZUKA-series starter for autonomous OpenClaw teams with isolated runtimes, role scaffolds, and a local Mattermost coordination lab.",
  lang: "en-US",
  base: "/onizuka-openclaw-autonomous-team-starter/",
  cleanUrls: true,
  lastUpdated: true,
  head: [["link", { rel: "icon", href: "/header.svg" }]],
  themeConfig: {
    siteTitle: "onizuka-openclaw-autonomous-team-starter",
    logo: "/header.svg",
    socialLinks: [{ icon: "github", link: repo }],
    footer: {
      message: "Released under the MIT License.",
      copyright: "Copyright (c) 2026 Sunwood-ai-labs",
    },
  },
  locales: {
    root: {
      label: "English",
      lang: "en-US",
      themeConfig: {
        nav: [
          { text: "Guide", link: "/guide/quickstart" },
          { text: "Autonomous Team Guide", link: "/guide/agent-teams" },
          { text: "Configuration", link: "/guide/configuration" },
          { text: "Validation", link: "/guide/validation" },
          { text: "GitHub", link: repo },
        ],
        sidebar: [
          {
            text: "Guide",
            items: [
              { text: "Quick Start", link: "/guide/quickstart" },
              { text: "Autonomous Team Guide", link: "/guide/agent-teams" },
              { text: "Configuration", link: "/guide/configuration" },
              { text: "Validation", link: "/guide/validation" },
            ],
          },
        ],
      },
    },
    ja: {
      label: "Japanese",
      lang: "ja-JP",
      themeConfig: {
        nav: [
          { text: "ガイド", link: "/ja/guide/quickstart" },
          { text: "自律チーム導入", link: "/ja/guide/agent-teams" },
          { text: "設定", link: "/ja/guide/configuration" },
          { text: "検証", link: "/ja/guide/validation" },
          { text: "GitHub", link: repo },
        ],
        sidebar: [
          {
            text: "ガイド",
            items: [
              { text: "クイックスタート", link: "/ja/guide/quickstart" },
              { text: "自律チーム導入", link: "/ja/guide/agent-teams" },
              { text: "設定", link: "/ja/guide/configuration" },
              { text: "検証", link: "/ja/guide/validation" },
            ],
          },
        ],
      },
    },
  },
});
