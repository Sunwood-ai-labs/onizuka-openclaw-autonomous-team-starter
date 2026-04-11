---
layout: home

hero:
  name: onizuka-openclaw-autonomous-team-starter
  text: Starter kit for autonomous OpenClaw teams
  tagline: One ONIZUKA-series project for building autonomous OpenClaw teams with isolated runtimes, role scaffolds, and a local Mattermost lab.
  image:
    src: /header.svg
    alt: Header artwork for the ONIZUKA-series autonomous OpenClaw team starter
  actions:
    - theme: brand
      text: Quick Start
      link: /guide/quickstart
    - theme: alt
      text: Autonomous Team Guide
      link: /guide/agent-teams
    - theme: alt
      text: Validation
      link: /guide/validation

features:
  - title: Autonomous teammates, isolated state
    details: Each agent gets its own Podman runtime, config, workspace, and ports so the team can act independently without collapsing into one shared state bucket.
  - title: Managed persona scaffolds
    details: Seeded `SOUL.md`, `IDENTITY.md`, `USER.md`, `HEARTBEAT.md`, `TOOLS.md`, and `BOOTSTRAP.md` files turn fresh pods into actual teammates.
  - title: Mattermost communication lab
    details: Run a local Mattermost pod, seed bot accounts, smoke-test replies, and enable heartbeat-driven autonomous chatter.
---

## What You Get

- A Windows-first OpenClaw starter managed by `uv` and PowerShell
- Generated `pod.yaml` manifests for single-agent and multi-agent runs
- Per-agent workspace scaffolds for roles, personality, and heartbeat behavior
- A local communication surface for human mentions and agent-to-agent chatter
- Validation notes for working local-model paths

## ONIZUKA Series

This repository is positioned as one ONIZUKA-series project focused on autonomous-agent and AGI-oriented development workflows.

- [ONIZUKA AGI Co. introduction repository](https://github.com/onizuka-agi-co/onizuka-agi-co)

## Read Next

- [Autonomous Team Guide](/guide/agent-teams)
- [Quick Start](/guide/quickstart)
- [Configuration](/guide/configuration)
- [Validation](/guide/validation)
