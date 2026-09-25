# Facebook Lead Ads Adapter Workflow

## Purpose

The **Facebook Lead Ads Adapter** ingests lead submissions originating from Meta ad campaigns (Facebook & Instagram Lead Ads) and Page inbox enquiries.

It handles Meta webhook verification challenges, queries the Meta Graph API to retrieve encrypted leadgen field data, normalizes the response into the Canonical Lead format, and forwards it to the Core Lead Intelligence Workflow.

---

## Data Flow

```text
User Submits Meta Instant Form (Facebook / Instagram)
  │
  ▼
Meta Webhook Event (HTTP POST to /webhook/leads/facebook)
  │
  ├──► 1. Webhook Challenge Handshake (`hub.mode`, `hub.verify_token`)
  │
  ├──► 2. Extract Leadgen ID (`leadgen_id`, `page_id`, `ad_id`)
  │
  ├──► 3. Meta Graph API Query
  │        GET https://graph.facebook.com/v19.0/{leadgen_id}
  │        Headers: Authorization: Bearer {PAGE_ACCESS_TOKEN}
  │
  ├──► 4. Field Normalization Adapter (Code Node)
  │        Transforms `field_data` array into `contact`, `company`, `message`
  │        Stores `ad_id`, `form_id`, and `campaign_id` in `metadata`
  │
  └──► 5. Forward to Core Workflow (Execute Workflow Node)
```

---

## Meta Field Data Normalization

Meta returns lead data as an array of key-value objects:
```json
{
  "field_data": [
    { "name": "full_name", "values": ["Somchai Prasert"] },
    { "name": "email", "values": ["somchai@example.com"] },
    { "name": "phone_number", "values": ["+66812345678"] },
    { "name": "what_challenges_are_you_facing?", "values": ["Need chatbot for branch customer service"] }
  ]
}
```

The adapter maps this structure into the Canonical Lead model:
- `lead_id`: `fb_lead_{leadgen_id}`
- `source`: `"facebook"`
- `external_id`: `leadgen_id`
- `contact.name`: matches `full_name`
- `contact.email`: matches `email`
- `contact.phone`: matches `phone_number`
- `message`: concatenated custom questions and answers

---

## Key Considerations

- **Token Expiry**: Requires Meta System User Page Access Token with long-lived permissions (`leads_retrieval`, `pages_manage_ads`).
- **Graph API Rate Limits**: Implements retry with exponential backoff on transient Meta API errors (HTTP 429 / 5xx).
- **Zero Core Changes**: Notice that no changes to scoring or CRM logic are needed in the core engine; only this intake adapter is added.

---

## Implementation Status

- **Status**: [Planned - Milestone 1.1]
- **Prerequisites**: Core Intelligence Engine (0.1), CRM integration (0.2).
