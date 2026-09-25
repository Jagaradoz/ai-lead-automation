# LINE Official Account Adapter & Conversational Qualification

## Purpose

The **LINE Official Account (LINE OA) Adapter** connects Southeast Asia's dominant conversational channel (LINE) directly into the AI Lead Automation system.

Unlike static web forms, LINE is inherently conversational. In **Milestone 2.0**, this component acts as a proactive **Conversational Qualification Layer**: engaging prospects in natural dialogue, answering initial FAQs, gathering missing business criteria (budget, timeline, branch count), and minting a Canonical Lead once qualification thresholds are satisfied.

---

## Conversational Qualification Concept

```text
Prospective Customer sends LINE Message
  │
  ▼
LINE Messaging API Webhook (/webhook/leads/line)
  │
  ├──► 1. Verify Request Signature (`X-Line-Signature` HMAC-SHA256)
  │
  ├──► 2. Conversational Qualification Loop
  │        ├── State Check: Do we have enough information?
  │        ├── Missing Information? ──► AI Agent asks friendly, clarifying follow-up question
  │        └── Information Sufficient?
  │                 │
  │                 ▼
  │        3. Compile Conversation Transcript into Canonical Lead
  │                 ├── Extract contact name from LINE User Profile API
  │                 ├── Format synthesis of chat into `message`
  │                 └── Assign `source`: "line", `external_id`: `userId`
  │
  └──► 4. Forward to Core Workflow (Execute Workflow Node)
```

---

## Architectural Advantages

1. **Higher Conversion**: In Thailand and regional markets, businesses lose leads when redirecting users from LINE chat to external web forms. Conversational qualification keeps prospects inside their preferred app.
2. **Dynamic Gap Filling**: If a user says "I want a bot", the conversational agent clarifies: "Glad to help! How many customer inquiries do you typically receive daily, and do you have an expected timeline?"
3. **Canonical Decoupling**: Once enough facts are gathered, the core engine processes the lead using the exact same JSON schema and scoring engine as a web or Facebook lead.

---

## Security & LINE Platform Requirements

- **Signature Verification**: Every incoming webhook payload must be validated against `LINE_CHANNEL_SECRET` using HMAC-SHA256 before processing.
- **Reply Token Expiry**: LINE reply tokens expire after 1 minute; synchronous replies must be fast, while long-running qualification tasks use push messages (`/v2/bot/message/push`).

---

## Implementation Status

- **Status**: [Future - Milestone 2.0]
- **Prerequisites**: Milestones 0.1 through 1.3 completed and tested.
