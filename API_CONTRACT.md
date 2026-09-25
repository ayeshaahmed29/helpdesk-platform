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

---

## Saqeeba provides → Ayesha consumes

### 1. Ticket fields: `first_response_at` and `status`
- **What:** Needed by the SLA background job to detect overdue tickets
- **How:** [TBD — exact field names/types on the `tickets` table]
- **Status:** Not yet implemented

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