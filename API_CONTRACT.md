# API Contract — Helpdesk Platform

This document defines what each member needs from the other so both sides can build
independently and integrate smoothly. Update this file whenever an interface changes —
it should always reflect the current, real contract, not the original plan.

## Ayesha provides → Saqeeba consumes

### 1. Current logged-in user + role
- **What:** A way to get the currently authenticated user and their role (Customer / Agent / Admin / Owner)
- **How:**
  - **In backend code:** import `get_current_user` from `core.auth` and use it as a dependency:
    `user: Annotated[User, Depends(get_current_user)]`. It returns the `User` model (with `id`, `email`, `role`, `organization_id`, `is_active`), or raises 401. Take `organization_id` and `requester_id` from this user, never from the request body, and filter every query by `user.organization_id`.
  - **Over HTTP:** `GET /auth/me` returns `{ id, email, full_name, role, organization_id, created_at }`.
  - **Auth flow:**
    - `POST /auth/login` with `{ "email", "password" }` returns 200 `{ "access_token", "token_type": "bearer", "expires_in" }`. Bad credentials return 401 with the same message for all failures.
    - Send the token on every request as `Authorization: Bearer <access_token>`.
    - `POST /auth/logout` (needs the token) returns 204 and revokes that token immediately.
  - **Token details:** JWT (HS256), expires after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60). The role is not in the token; the user is loaded from the DB on every request, and inactive users are rejected.
  - **Errors:** 401 for missing, invalid, expired or revoked tokens. 503 if the token denylist (Redis) is unavailable.
  - **Env vars needed:** `JWT_SECRET`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REDIS_URL` (see `.env.example`).
- **Status:** Implemented (replaces the temporary fake `Bearer fake-<user_id>` auth) 

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

### 6. Frontend auth state (token, current user, 401 handling)
- **What:** One shared place on the frontend for the token and the logged-in user, so pages never handle auth themselves.
- **How:**
  - **Token storage:** `localStorage`, key `"token"`. Do not read or write it directly in pages. Use `getToken`, `clearToken` and `TOKEN_KEY` from `frontend/src/api/client.ts`.
  - **Making API calls:** always use `apiFetch<T>(path, options)` from `frontend/src/api/client.ts`. It adds the base URL (`VITE_API_URL`, default `http://localhost:8000`) and the `Authorization: Bearer` header. It throws `ApiError` (with `.status`) on non-2xx responses.
  - **Current user in components:** `const { user, loading, logout } = useAuth()` from `frontend/src/auth/AuthContext.tsx`. `user` is `{ id, email, full_name?, role }` or `null`. `AuthProvider` (in `main.tsx`) calls `GET /auth/me` once when the app loads.
  - **401 behavior:** if a request that sent a token gets a 401 (expired or revoked), `apiFetch` clears the token and `AuthContext` sets `user` to `null`. The route guard then redirects to `/login`. A 401 on a request with no token (for example a wrong password on login) is NOT treated as an expired session; the caller gets the normal `ApiError`.
  - **Logout:** `logout()` calls `POST /auth/logout`, clears the token, and resets the user, even if the server call fails.
- **Status:** Implemented (issue #7). Not yet available: a `login()` or `refresh()` function on `useAuth`, which the real login page (separate issue) will add.

### 7. Frontend routes and protection
- **What:** Which pages exist and which need a login.
- **How:**
  - Public: `/login` (placeholder for now). Unknown URLs show a NotFound page.
  - Protected (redirect to `/login` when there is no valid user; the original location is passed as `state.from`): everything inside the shared layout.

| Route | Sidebar visible to | Status |
|---|---|---|
| `/` | n/a | redirects to `/tickets` |
| `/tickets` | agent, admin, owner | placeholder |
| `/tickets/:id` | n/a (opened from lists) | placeholder |
| `/portal` | customer | placeholder |
| `/settings` | admin, owner | placeholder |
| `/settings/team` | admin, owner | placeholder |
| `/audit-log` | admin, owner | placeholder |

  - The guard only checks that the user is logged in. It does not check roles; the sidebar only hides links by role (`frontend/src/layout/navConfig.ts`). The backend is what enforces permissions on every endpoint.
  - To add a page: add the `<Route>` inside the protected layout block in `App.tsx`, and add one line to `NAV_ITEMS` in `navConfig.ts` if it needs a sidebar link.
- **Status:** Implemented (issues #6 and #7)

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
- **How (planned):** Saqeeba calls Ayesha's `log_audit_event()` helper directly from the ticket endpoints.
  - `action`: `ticket.created`, `ticket.updated`, `ticket.status_changed`
  - `entity_type`: `ticket`
  - `entity_id`: ticket id
  - `metadata`: changed fields, e.g. `{ "status": ["new", "open"] }`
- **Status:** Not yet implemented. Waiting for Ayesha's `log_audit_event()` helper.

### 3. Ticket list UI
- **What:** So audit log entries can link out to the relevant ticket
- **How:** Frontend route pattern `/tickets/:id` for a single ticket and `/tickets` for the list. Both routes exist inside the protected layout (see Ayesha item 7); Saqeeba replaces the placeholder `element` in `App.tsx` with the real pages.
- **Status:** Ticket list page implemented at `/tickets` (issue #13). The detail page at `/tickets/:id` is still a placeholder and comes in Week 2.

### 4. Comment-created event
- **What:** So Ayesha's SLA job can mark when the first response happened
- **How (planned):** No separate event. When an agent, admin or owner posts the first public reply, the comment endpoint sets `first_response_at` to the current time if it is still NULL. Internal notes and customer comments do not count. The SLA job only reads `first_response_at`.
- **Status:** Not yet implemented (comments are a Week 2 task)

### 5. Tickets API
- **What:** Endpoints for creating, listing, reading and updating tickets. All require the Bearer token.
- **How:**
  - `POST /tickets`: body `{ subject, description }`. Priority always starts as `normal`; `organization_id` and `requester_id` come from the current user.
  - `GET /tickets`: optional query params `status`, `priority`, `assignee_id`, plus `page` (default 1) and `page_size` (default 20, max 100). Returns `{ items, total, page, page_size }`.
  - `GET /tickets/{id}`: returns one ticket, or 404 if it does not exist or belongs to another organization.
  - `PATCH /tickets/{id}`: body can include `subject`, `description`, `priority`, `assignee_id`. Assignee must be an active staff user in the same organization (400 otherwise). Customers cannot assign (403).
  - Customers only see tickets they created.
- **Status:** Implemented (CRUD in PR #25, filtering and pagination in #27)

---