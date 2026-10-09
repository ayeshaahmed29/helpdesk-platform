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
- **What:** Reusable checks for "is this role allowed to call this endpoint" and "does this record belong to the user's company".
- **How:** Code: `backend/core/permissions.py`.
  - `require_role(*roles)`: FastAPI dependency. It returns the current user, or raises **403** if the user's role is not in the list. A missing, invalid or revoked token is still **401** (from `get_current_user`, which it uses internally).
  - `ensure_same_org(user, resource_org_id)`: raises **404** if a record belongs to another company. It is 404 and not 403 so that company A cannot find out whether company B's record exists.
  - Role groups: `STAFF_ROLES` = agent, admin, owner. `MANAGER_ROLES` = admin, owner. Roles are the `UserRole` enum from `models.user`.
  - Usage (declare the dependency with `Annotated`, because `Depends(...)` in a default argument fails the ruff `B008` rule):
```python
    from typing import Annotated

    from fastapi import Depends

    from core.permissions import MANAGER_ROLES, STAFF_ROLES, require_role
    from models import User

    StaffUser = Annotated[User, Depends(require_role(*STAFF_ROLES))]
    ManagerUser = Annotated[User, Depends(require_role(*MANAGER_ROLES))]

    @router.get("/something")
    def something(user: StaffUser):
        ...
```
  - **Rules for every endpoint:**
    - Every endpoint must depend on `get_current_user` (directly or through `require_role`), unless it is public on purpose (see table).
    - Every query must filter by `user.organization_id`. In `routers/tickets.py` this is done by `visible_tickets(user)`; use it or an equivalent for any new query.
    - Use `require_role` when an endpoint is limited to some roles (for example invites and the audit log viewer are admin/owner only).
    - Permissions are enforced in the backend. The frontend only hides links.
  - **Endpoint and role table (current state):**

| Endpoint | Who can call it | Notes |
|---|---|---|
| `GET /health` | public | health check |
| `POST /auth/signup` | public | creates an organization and its first user (owner) |
| `POST /auth/login` | public | same 401 message for every failure |
| `POST /auth/logout` | any logged-in user | revokes the token |
| `GET /auth/me` | any logged-in user | returns the current user |
| `POST /invites` | owner, admin | admin cannot invite an owner (403); see item 8 |
| `GET /invites` | owner, admin | only invites of the user's own company |
| `GET /invites/{token}` | public | the secret token in the link is the permission; see item 8 |
| `POST /invites/{token}/accept` | public | creates the user with the invited role; see item 8 |
| `POST /tickets` | any logged-in user | `organization_id` and `requester_id` come from the current user, never from the body |
| `GET /tickets` | staff: all tickets in their company. Customer: only their own | other companies' tickets are never returned |
| `GET /tickets/{id}` | staff: any ticket in their company. Customer: only their own | 404 for a ticket in another company or another customer's ticket |
| `PATCH /tickets/{id}` | staff: any ticket in their company. Customer: only their own | customers cannot set `assignee_id` (403); the assignee must be active staff in the same company (400) |

  - **Tests:** `backend/tests/test_permissions.py` tests the helpers. `backend/tests/test_tenant_isolation.py` proves that company A cannot read or change company B's tickets, and that customers only see their own tickets. Run them with `docker compose exec backend pytest -v`. Tests use a separate `helpdesk_test` database and replace `get_current_user`, so they need neither Redis nor a real login (fixtures are in `backend/tests/conftest.py`).
- **Status:** Implemented (issue #29)

### 3. Audit log helper function
- **What:** A function that records "who did what" in the `audit_logs` table. Saqeeba's ticket code calls it; it is already called from signup, login and invites.
- **How:** Code: `backend/core/audit.py`. Model: `backend/models/audit_log.py`.
```python
    from core.audit import AuditAction, log_audit_event

    log_audit_event(
        db,                                    # the request's DbSession
        organization_id=user.organization_id,  # required
        actor_user_id=user.id,                 # None when the system did it
        action=AuditAction.ticket_created,     # required
        entity_type="ticket",                  # optional
        entity_id=ticket.id,                   # optional
        metadata={"status": ["new", "open"]},  # optional, JSON-serializable dict
    )
```
  - **It does not commit.** Call it before your `db.commit()` so the audit entry and the real change are saved together in one transaction. Do not call it for requests that fail.
  - **Action names** are the `AuditAction` enum in `core/audit.py`. An unknown name raises `ValueError`, which catches typos. To add a new action, add one line to the enum.
  - **Current actions:** `user.signup`, `user.login`, `user.password_reset_requested`, `user.password_reset`, `invite.created`, `invite.accepted`, `ticket.created`, `ticket.updated`, `ticket.status_changed`.
  - **Already called from:** signup (`user.signup`), login (`user.login`), creating an invite (`invite.created`) and accepting an invite (`invite.accepted`).
  - **Ticket events:** `entity_type="ticket"`, `entity_id=ticket.id`, `metadata` holds the changed fields, for example `{"status": ["new", "open"]}`.
  - **Never put secrets in `metadata`:** no passwords, tokens or invite links. Avoid emails and other personal data.
  - **Table columns:** `id`, `organization_id` (required), `actor_user_id` (nullable), `action`, `entity_type`, `entity_id`, `metadata` (JSONB), `created_at`. Index on `(organization_id, created_at)`.
  - **Not logged:** failed logins, because an unknown email has no organization to attach the entry to.
  - **Tests:** `backend/tests/test_audit.py`.
- **Status:** Implemented (issue #30)

### 4. Email sending helper
- **What:** A reusable function to send emails (used by Saqeeba for ticket-related notifications, and by Ayesha for invites, password reset and SLA alerts).
- **How:** Code: `backend/core/email.py`.
```python
    from core.email import EmailSendError, send_email

    try:
        send_email("someone@example.com", "Subject line", "Plain text body")
    except EmailSendError:
        ...  # SMTP server unreachable or it refused the email
```
  - `send_email(to, subject, body)` sends a **plain-text** email and returns nothing. It raises `EmailSendError` if sending fails; decide in your endpoint what that means (the invite endpoint rolls back and returns 502, so nothing is saved).
  - **It is synchronous.** The request waits until the email is sent (SMTP timeout is 10 seconds). Moving it to a background job is a later improvement.
  - **Settings** come from `.env` (copy new lines from `.env.example` after pulling):
    - `SMTP_HOST`: if it is **empty**, nothing is sent and the email is only written to the backend log (`docker compose logs backend`).
    - `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_USE_TLS` (`true` switches on STARTTLS; login is used only when `SMTP_USER` is set).
    - `FRONTEND_URL`: used to build links inside emails (for example `http://localhost:5173/accept-invite/<token>`).
  - **In development**, Mailpit catches every email. It is a service in `docker-compose.yml`. The inbox is at http://localhost:8025 (SMTP on port 1025). No real email ever leaves your machine.
  - **In tests**, replace the function where it is **used**, not where it is defined. Example: `monkeypatch.setattr("routers.invites.send_email", fake)`. See `sent_emails` in `backend/tests/test_invites.py`.
  - **Never put secrets in logs.** In log-only mode the full body is logged, including links, so do not use an empty `SMTP_HOST` outside development.
- **Status:** Implemented (issue #31)

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
  - Public (outside the guard): `/login` (placeholder for now) and `/accept-invite/:token` (real page, issue #31). Unknown URLs show a NotFound page.
  - Protected (redirect to `/login` when there is no valid user; the original location is passed as `state.from`): everything inside the shared layout.

| Route | Sidebar visible to | Status |
|---|---|---|
| `/login` | n/a (public) | placeholder |
| `/accept-invite/:token` | n/a (public, opened from the invite email) | implemented (issue #31) |
| `/` | n/a | redirects to `/tickets` |
| `/tickets` | agent, admin, owner | implemented (Saqeeba, issue #13) |
| `/tickets/:id` | n/a (opened from lists) | implemented (Saqeeba, issue #37) |
| `/portal` | customer | placeholder |
| `/settings` | admin, owner | placeholder |
| `/settings/team` | admin, owner | placeholder |
| `/audit-log` | admin, owner | placeholder |

  - The guard only checks that the user is logged in. It does not check roles; the sidebar only hides links by role (`frontend/src/layout/navConfig.ts`). The backend is what enforces permissions on every endpoint.
  - To add a page: add the `<Route>` inside the protected layout block in `App.tsx`, and add one line to `NAV_ITEMS` in `navConfig.ts` if it needs a sidebar link. A public page goes next to `/login`, outside `ProtectedRoute`.
- **Status:** Implemented (issues #6, #7 and #31)

### 8. Invites (invite users to an organization)
- **What:** An owner or admin invites a person by email. The person opens the link, sets a name and password, and gets an account with the invited role in the inviter's company.
- **How:** Code: `backend/routers/invites.py`, schemas in `backend/schemas/invites.py`, model `backend/models/invite.py`. Frontend: `frontend/src/pages/AcceptInvite.tsx` and `frontend/src/api/invites.ts`.
  - `POST /invites` (owner or admin). Body: `{ "email", "role" }` where `role` is `customer`, `agent`, `admin` or `owner`. Returns **201** `{ id, email, role, status, invited_by, expires_at, accepted_at, created_at }`. The token is **never** returned; it exists only in the email link.
    - An **admin** cannot invite an `owner` (403). An owner can invite any role.
    - **409** if a user with this email already exists (in any company, because emails are unique), or if this company already has a pending invite for the email. An expired or used invite does not block a new one.
    - **502** if the email could not be sent. Nothing is saved in that case, so the request can simply be repeated.
    - The email is saved lowercase. Agents and customers get **403**.
  - `GET /invites` (owner or admin). Returns a list of the user's own company invites, newest first, each with `status`: `pending`, `accepted` or `expired`. No pagination yet.
  - `GET /invites/{token}` (public). Returns `{ email, role, organization_name, expires_at }` so the accept page can show who is inviting. **404** for an unknown token, **410** if it was already used or has expired.
  - `POST /invites/{token}/accept` (public). Body: `{ "full_name" (1–100), "password" (8–128) }`. Returns **201** with the new user (same shape as signup). Same **404** / **410** errors as above, **409** if the email was registered in the meantime, **422** for bad input. A failed attempt (for example a short password) does not use up the invite.
    - It does **not** log the user in. The user goes to `/login` afterwards.
  - **Token rules:** `secrets.token_urlsafe(32)`, valid for **7 days**, usable **once**. Only the **SHA-256 hash** is stored (`invites.token_hash`, unique). The accept call locks the invite row, so two requests at the same moment cannot both succeed.
  - **Link in the email:** `FRONTEND_URL` + `/accept-invite/<token>`.
  - **Table `invites`:** `id`, `email`, `role` (lowercase string), `organization_id` (FK), `invited_by` (FK to users, `SET NULL`), `token_hash`, `expires_at`, `accepted_at` (NULL while pending), `created_at`.
  - **Audit:** `invite.created` (actor = inviter) and `invite.accepted` (actor = the new user), both with `entity_type="invite"`, `entity_id` = invite id and `metadata={"role": ...}`. No email address or token is logged.
  - **Tests:** `backend/tests/test_invites.py` (success, role rules, duplicates, existing members, failed email, expired, reused, invalid token, audit entries).
- **Status:** Implemented (issue #31)

### 9. Password Reset (Forgot & Reset Password)
- **What:** Allows users to request a password reset email using their registered email address and complete the reset using a secure token.
- **How:** Code: `backend/routers/auth.py`, schemas in `backend/schemas/auth.py`. Frontend: `frontend/src/pages/ForgotPasswordPage.tsx`, `frontend/src/pages/ResetPasswordPage.tsx`, and `frontend/src/api/auth.ts`.
  - `POST /auth/forgot-password` (public). Body: `{ "email": "user@example.com" }`. Returns **200** with a generic success message (e.g., instructions sent) to prevent user enumeration.
    - Stored lowercase email lookup.
    - Triggers an email containing a link with the secure token (`FRONTEND_URL` + `/reset-password?token=<token>`).
    - Audit log: `user.password_reset_requested`.
  - `POST /auth/reset-password` (public). Body: `{ "token": "string", "new_password": "at-least-8-characters" }`. Returns **200** on success.
    - Validates token expiration and single-use constraints.
    - Updates the user password hash (argon2).
    - Audit log: `user.password_reset`.
  - **Security Rules:** Tokens are securely hashed, short-lived, and invalidated after successful use.
- **Status:** Implemented

---

## Saqeeba provides → Ayesha consumes

### 1. Ticket fields: `first_response_at` and `status`
- **What:** Needed by the SLA background job to detect overdue tickets
- **How:** Columns on the


## Comments (#38)

### POST /tickets/{ticket_id}/comments
Create a comment on a ticket. Both staff and customers can post.

Body:

{
"body": "string (required)",
"is_internal": false
}


Rules:
- Customers cannot set `is_internal: true` (returns 403).
- Customers never see internal notes in GET.
- First public staff reply (not internal) sets the ticket's `first_response_at`.

Response: 201 with the created comment.

### GET /tickets/{ticket_id}/comments
List comments on a ticket, oldest first.
- Customers see only public comments (never internal).
- Staff see all comments including internal notes.
Response: 200 with a list of comments.