# API Contract — Helpdesk Platform

This document defines what each member needs from the other so both sides can build
independently and integrate smoothly. Update this file whenever an interface changes —
it should always reflect the current, real contract, not the original plan.

## Ayesha provides → Saqeeba consumes

### 1. Current logged-in user + role
- **What:** A way to get the currently authenticated user and their role (Customer / Agent / Admin / Owner)
- **How:** [TBD — e.g. `GET /auth/me` returns `{ id, email, role, organization_id }`, or a dependency/middleware Saqeeba can import]
- **Status:** Not yet implemented

### 2. Permission check helper
- **What:** A reusable function/dependency to check "does this user have permission to do X"
- **How:** [TBD — e.g. `require_role(["agent", "admin", "owner"])` as a FastAPI dependency]
- **Status:** Not yet implemented

### 3. Audit log helper function
- **What:** A function Saqeeba's ticket code can call to record an action (e.g. "ticket created," "ticket updated")
- **How:** [TBD — e.g. `log_audit_event(actor_id, action, entity_type, entity_id, metadata)`]
- **Status:** Not yet implemented

### 4. Email sending helper
- **What:** A reusable function to send emails (used by Saqeeba for ticket-related notifications, and by Ayesha for password reset / SLA alerts)
- **How:** [TBD — e.g. `send_email(to, subject, body)`]
- **Status:** Not yet implemented

### 5. Signup endpoint
- **What:** Creates a new organization (company) together with its first user, who becomes the `owner`. Every user and ticket belongs to an organization, so this is where an organization first exists.
- **How:** `POST /auth/signup` (code: `backend/routers/auth.py`, schemas in `backend/schemas/auth.py`)
  - Request body (JSON):
```json
    {
      "organization_name": "FastMart",
      "full_name": "Owner One",
      "email": "owner@fastmart.com",
      "password": "at-least-8-characters"
    }
```
    - `organization_name`: 2–100 characters
    - `full_name`: 1–100 characters
    - `email`: valid email; stored lowercase, so `A@x.com` and `a@x.com` are the same account
    - `password`: 8–128 characters; stored as an argon2 hash, never returned
  - `201 Created` response:
```json
    {
      "id": 1,
      "email": "owner@fastmart.com",
      "full_name": "Owner One",
      "role": "owner",
      "organization_id": 1,
      "created_at": "2026-09-29T12:00:00Z"
    }
```
  - Errors:
    - `409 Conflict`: an account with this email already exists
    - `422 Unprocessable Entity`: validation failed (bad email, short password, missing field)
  - Notes:
    - The role is not accepted from the client. The first user of a new organization is always `owner`.
    - User roles are stored lowercase: `customer`, `agent`, `admin`, `owner`.
    - No token is returned yet. Login and `GET /auth/me` (item 1) are separate issues.
- **Status:** Implemented (issue #4)

---

## Saqeeba provides → Ayesha consumes

### 1. Ticket fields: `first_response_at` and `status`
- **What:** Needed by the SLA background job to detect overdue tickets
- **How:** Columns on the `tickets` table (model: `backend/models/ticket.py`):
  - `status`: `VARCHAR(20)`, not null, default `new`. Lowercase values: `new`, `open`, `pending`, `resolved`, `closed`. Indexed.
  - `first_response_at`: `TIMESTAMP WITH TIME ZONE`, nullable. NULL means no agent has replied publicly yet.
  - `created_at`: `TIMESTAMP WITH TIME ZONE`, not null, default `now()`. The SLA timer starts from here.
  - `organization_id`: `INTEGER`, not null, indexed. Foreign key to `organizations.id`.
  - `requester_id`: `INTEGER`, not null. Foreign key to `users.id`.
  - `assignee_id`: `INTEGER`, nullable. Foreign key to `users.id`. Can be used to email the assigned agent.
- **Status:** Implemented (tickets table in PR #15, foreign keys in issue #19)

### 2. Ticket events (created, updated)
- **What:** So the audit log can record ticket-related actions automatically
- **How:** [TBD — e.g. Saqeeba calls Ayesha's `log_audit_event()` helper directly from ticket endpoints, or emits an event Ayesha's code listens for]
- **Status:** Not yet implemented

### 3. Ticket list UI
- **What:** So audit log entries can link out to the relevant ticket
- **How:** [TBD — e.g. frontend route pattern like `/tickets/:id`]
- **Status:** Not yet implemented

### 4. Comment-created event
- **What:** So Ayesha's SLA job can mark when the first response happened
- **How:** [TBD — likely tied to #1 above, whatever sets `first_response_at`]
- **Status:** Not yet implemented

---

## Notes
- If the other person's piece isn't ready yet, mock/stub it and replace later — this is normal.
- Update the "Status" and "How" fields as real implementations land, so this file always
  reflects reality, not just the plan.