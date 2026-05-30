# ai-automation-projects
AI workflows built with n8n, Make.com and Claude API

A collection of AI-powered workflows built during my 30-day AI skill building journey.

## Project 1: n8n Webhook to Google Sheets
- Tool: n8n
- What it does: Captures form data via webhook and automatically appends it to Google Sheets
- Skills: Webhook triggers, node connections, Google Sheets API, JSON data mapping

## Project 2: Claude AI Agent (n8n + Claude API)
- Tools: n8n, Anthropic Claude API
- What it does: Receives any question via webhook, sends to Claude AI, 
  saves question + AI reply to Google Sheets automatically
- Skills: REST API calls, JSON parsing, Claude API integration, 
  prompt engineering, multi-node workflow design

## Project 2b: Claude AI Agent (Make.com version)
- Tools: Make.com, Anthropic Claude API, Google Sheets
- What it does: Same as n8n version — receives question via webhook,
  sends to Claude, saves Q&A to Google Sheets
- Key learning: Make.com uses {{module_number.field}} syntax vs 
  n8n's $('NodeName').item.json.body.field syntax
- Skills: Make.com scenario design, HTTP modules, 
  webhook handling, Google Sheets integration
