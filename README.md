---
title: Ramco PO Chatbot
emoji: 🛒
colorFrom: yellow
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
short_description: Deterministic journey-driven chatbot for Ramco's PO module
---

# Ramco PO Chatbot · v9

Interactive test environment for the Ramco Purchase Order chatbot.
Bot v9 · 77.6% eval pass (45/58) · journey-driven, deterministic decisions, LLM only for NL understanding.

v9 closes a structural gap from v1–v8: when the user walks a sub-screen
(Terms, TCD, PR-Cov, SO-Cov, Quality, Notes, Schedule), the sub-screen's own
TRANS task now fires alongside the main commit — writing the orphan child
tables (`po_paytm_doclevel_detail`, `po_potcd_doclevel_detail`,
`po_poqly_quality_detail`, …) that were previously never touched.
All 8 new sub-screen-commit eval cases pass; zero regressions vs v8.

Set the `GEMINI_API_KEY` secret in this Space for the bot to function.

Source: https://github.com/VizuaraAI/ramco-journey-model
