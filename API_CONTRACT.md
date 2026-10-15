````markdown
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
    - Permissions are enforced in the backend. The frontend only hides links and disables buttons.
  - **Endpoint and role table (current state):**

| Endpoint | Who can call it | Notes |
|---|---|---|
| `GET /health` | public | health check |
| `POST /auth/signup` | public | creates an organization and its first user (owner) |
| `POST /auth/login` | public | same 401 message for every failure |
| `POST /auth/logout` | any logged-in user | revokes the token |
| `GET /auth/me` | any logged-in user | returns the current user |
| `POST /auth/forgot-password` | public | generic answer, see item 9 |
| `POST /auth/reset-password` | public | needs the token from the email, see item 9 |
| `POST /invites` | owner, admin | admin cannot invite an owner (403); see item 8 |
| `GET /invites` | owner, admin | only invites of the user's own company |
| `GET /invites/{token}` | public | the secret token in the link is the permission; see item 8 |
| `POST /invites/{token}/accept` | public | creates the user with the invited role; see item 8 |
| `POST /tickets` | any logged-in user | `organization_id` and `requester_id` come from the current user, never from the body |
| `GET /tickets` | staff: all tickets in their company. Customer: only their own | other companies' tickets are never returned |
| `GET /tickets/{id}` | staff: any ticket in their company. Customer: only their own | 404 for a ticket in another company or another customer's ticket |
| `PATCH /tickets/{id}` | staff: any ticket in their company. Customer: only their own | customers cannot set `assignee_id` (403); the assignee must be active staff in the same company (400) |
| `GET /audit-logs` | owner, admin | only audit entries of the user's own company; agents and customers get 403; see item 10 |
| `GET /settings/sla` | owner, admin | the company's first-reply SLA in hours; agents and customers get 403; see item 11 |
| `PUT /settings/sla` | owner, admin | sets `first_reply_hours` (1–168) for the user's own company; see item 11 |
| `GET /users` | owner, admin | only users of the user's own company; see item 12 |
| `PATCH /users/{id}` | owner, admin | change `role` or `is_active`; an admin cannot touch an owner; see item 12 |

  - The SLA background job (item 13) has no HTTP endpoint. It runs in its own `worker` service.
  - **Tests:** `backend/tests/test_permissions.py` tests the helpers. `backend/tests/test_tenant_isolation.py` proves that company A cannot read or change company B's tickets, and that customers only see their own tickets. Run them with `docker compose exec backend pytest -v`. Tests use a separate `helpdesk_test` database and replace `get_current_user`, so they need neither Redis nor a real login (fixtures are in `backend/tests/conftest.py`).
- **Status:** Implemented (issue #29)

### 3. Audit log helper function
- **What:** A function that records "who did what" in the `audit_logs` table. Saqeeba's ticket code calls it; it is already called from signup, login, invites, settings, team management and the SLA worker.
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
  - **Action names** are the `AuditAction` enum in `core/audit.py`. An unknown name raises `ValueError`, which catches typos. To add a new action, add one line to the enum **and** the same name to `ACTIONS` in `frontend/src/pages/AuditLog.tsx`.
  - **Current actions:** `user.signup`, `user.login`, `user.password_reset_requested`, `user.password_reset`, `user.role_changed`, `user.deactivated`, `invite.created`, `invite.accepted`, `settings.sla_updated`, `ticket.created`, `ticket.updated`, `ticket.status_changed`, `ticket.sla_breached`.
  - **Already called from:** signup (`user.signup`), login (`user.login`), password reset (`user.password_reset_requested`, `user.password_reset`), creating an invite (`invite.created`), accepting an invite (`invite.accepted`), changing the SLA setting (`settings.sla_updated`), changing a user's role or deactivating a user (`user.role_changed`, `user.deactivated`), and the SLA worker (`ticket.sla_breached`, with no actor).
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
  - `send_email(to, subject, body)` sends a **plain-text** email and returns nothing. It raises `EmailSendError` if sending fails; decide in your code what that means (the invite endpoint rolls back and returns 502, so nothing is saved; the SLA worker logs the error and goes on with the next email).
  - **It is synchronous.** The caller waits until the email is sent (SMTP timeout is 10 seconds). The SLA worker calls it in its own process, so no web request waits for it.
  - **Keep line breaks out of `subject`.** The subject goes into an email header. Put anything the user typed (like a ticket subject) in the body.
  - **Settings** come from `.env` (copy new lines from `.env.example` after pulling):
    - `SMTP_HOST`: if it is **empty**, nothing is sent and the email is only written to the log (`docker compose logs backend`, or `worker` for SLA alerts).
    - `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_USE_TLS` (`true` switches on STARTTLS; login is used only when `SMTP_USER` is set).
    - `FRONTEND_URL`: used to build links inside emails (for example `http://localhost:5173/accept-invite/<token>`).
  - **In development**, Mailpit catches every email. It is a service in `docker-compose.yml`. The inbox is at http://localhost:8025. The containers talk to it on port 1025 (`SMTP_HOST=mailpit`, `SMTP_PORT=1025`); from your own machine the SMTP port is 1127. No real email ever leaves your machine.
  - **In tests**, replace the function where it is **used**, not where it is defined. Examples: `monkeypatch.setattr("routers.invites.send_email", fake)` and `monkeypatch.setattr("core.sla.send_email", fake)`. See `sent_emails` in `backend/tests/test_invites.py` and `backend/tests/test_sla_job.py`.
  - **Never put secrets in logs.** In log-only mode the full body is logged, including links, so do not use an empty `SMTP_HOST` outside development.
- **Status:** Implemented (issue #31)

### 5. Signup endpoint
- **What:** Creates a new organization (company) together with its first user, who becomes the `owner`. Every user and ticket belongs to an organization, so this is where an organization first exists.
- **How:** `POST /auth/signup` (code: `backend/routers/auth.py`, schemas in `backend/schemas/auth.py`). Frontend: the `/signup` page and `signupRequest` in `frontend/src/api/auth.ts`.
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
    - No token is returned. The user logs in with `POST /auth/login` (item 1).
- **Status:** Implemented (issue #4)

### 6. Frontend auth state (token, current user, 401 handling)
- **What:** One shared place on the frontend for the token and the logged-in user, so pages never handle auth themselves.
- **How:**
  - **Token storage:** `localStorage`, key `"token"`. Do not read or write it directly in pages. Use `getToken`, `clearToken` and `TOKEN_KEY` from `frontend/src/api/client.ts`.
  - **Making API calls:** always use `apiFetch<T>(path, options)` from `frontend/src/api/client.ts`. It adds the base URL (`VITE_API_URL`, default `http://localhost:8000`) and the `Authorization: Bearer` header. It throws `ApiError` on non-2xx responses.
  - **`ApiError`:** has `.status` (the HTTP status) and `.detail` (the backend's `detail` text when it is a plain string, otherwise `undefined`; 422 errors send a list, so `.detail` is empty for them). `.message` is still `Request failed: <status>`.
  - **Error messages for pages:** `apiErrorMessage(err, fallback, overrides?)` from `frontend/src/api/errors.ts` turns an `ApiError` into a clear message. 403 and 409 show the backend's own text. Pass `overrides` (for example `{ 403: "..." }`) when a page needs its own text for one status.
  - **Current user in components:** `const { user, loading, login, logout, refresh } = useAuth()` from `frontend/src/auth/useAuth.ts`. `user` is `{ id, email, full_name?, role }` or `null`. `AuthProvider` (in `main.tsx`) calls `GET /auth/me` once when the app loads.
  - **`login(email, password)`:** calls `POST /auth/login`, saves the token, loads `GET /auth/me` and sets `user`. It throws `ApiError` when the login fails, so the login page shows its own message.
  - **`refresh()`:** loads the current user again from `GET /auth/me`.
  - **401 behavior:** if a request that sent a token gets a 401 (expired or revoked), `apiFetch` clears the token and `AuthContext` sets `user` to `null`. The route guard then redirects to `/login`. A 401 on a request with no token (for example a wrong password on login) is NOT treated as an expired session; the caller gets the normal `ApiError`.
  - **Logout:** `logout()` calls `POST /auth/logout`, clears the token, and resets the user, even if the server call fails.
  - **Roles on the frontend:** `frontend/src/auth/roles.ts` has `ROLES`, `assignableRoles(role)` (an owner may assign all four roles, everyone else all except `owner`) and `roleLabel(role)`. The type `Role` is in `frontend/src/auth/types.ts`.
- **Status:** Implemented (issues #7 and the login issue, #54 added `ApiError.detail`, `errors.ts` and `roles.ts`)

### 7. Frontend routes and protection
- **What:** Which pages exist and which need a login.
- **How:**
  - Public (outside the guard): `/login`, `/signup`, `/forgot-password`, `/reset-password/:token` and `/accept-invite/:token`. Unknown URLs show a NotFound page.
  - Protected (redirect to `/login` when there is no valid user; the original location is passed as `state.from`, and the login page sends the user back there): everything inside the shared layout.

| Route | Sidebar visible to | Status |
|---|---|---|
| `/login` | n/a (public) | implemented |
| `/signup` | n/a (public, creates a company and its owner) | implemented |
| `/forgot-password` | n/a (public) | implemented |
| `/reset-password/:token` | n/a (public, opened from the reset email) | implemented |
| `/accept-invite/:token` | n/a (public, opened from the invite email) | implemented (issue #31) |
| `/` | n/a | redirects to `/tickets` |
| `/tickets` | agent, admin, owner | implemented (Saqeeba, issue #13) |
| `/tickets/:id` | n/a (opened from lists) | implemented (Saqeeba, issue #37) |
| `/portal` | customer | placeholder |
| `/settings` | admin, owner | implemented (issue #54, SLA form, see item 11) |
| `/settings/team` | admin, owner | implemented (issue #54, team page, see items 12 and 14) |
| `/audit-log` | admin, owner | implemented (issue #35) |

  - The guard only checks that the user is logged in. It does not check roles; the sidebar only hides links by role (`frontend/src/layout/navConfig.ts`). The backend is what enforces permissions on every endpoint. If an agent opens `/settings` or `/settings/team` by typing the URL, the page loads but the backend answers 403 and the page shows a message.
  - To add a page: add the `<Route>` inside the protected layout block in `App.tsx`, and add one line to `NAV_ITEMS` in `navConfig.ts` if it needs a sidebar link. A public page goes next to `/login`, outside `ProtectedRoute`.
- **Status:** Implemented (issues #6, #7, #31, #35 and #54)

### 8. Invites (invite users to an organization)
- **What:** An owner or admin invites a person by email. The person opens the link, sets a name and password, and gets an account with the invited role in the inviter's company.
- **How:** Code: `backend/routers/invites.py`, schemas in `backend/schemas/invites.py`, model `backend/models/invite.py`. Frontend: `frontend/src/pages/AcceptInvite.tsx` (accept page), `frontend/src/components/InviteSection.tsx` (invite form and pending list on the team page, see item 14) and `frontend/src/api/invites.ts` (`getInvite`, `acceptInvite`, `createInvite`, `listInvites`).
  - `POST /invites` (owner or admin). Body: `{ "email", "role" }` where `role` is `customer`, `agent`, `admin` or `owner`. Returns **201** `{ id, email, role, status, invited_by, expires_at, accepted_at, created_at }`. The token is **never** returned; it exists only in the email link.
    - An **admin** cannot invite an `owner` (403). An owner can invite any role.
    - **409** if a user with this email already exists (in any company, because emails are unique), or if this company already has a pending invite for the email. An expired or used invite does not block a new one.
    - **502** if the email could not be sent. Nothing is saved in that case, so the request can simply be repeated.
    - The email is saved lowercase. Agents and customers get **403**.
  - `GET /invites` (owner or admin). Returns a list of the user's own company invites, newest first, each with `status`: `pending`, `accepted` or `expired`. No pagination yet. The team page shows only the `pending` ones.
  - `GET /invites/{token}` (public). Returns `{ email, role, organization_name, expires_at }` so the accept page can show who is inviting. **404** for an unknown token, **410** if it was already used or has expired.
  - `POST /invites/{token}/accept` (public). Body: `{ "full_name" (1–100), "password" (8–128) }`. Returns **201** with the new user (same shape as signup). Same **404** / **410** errors as above, **409** if the email was registered in the meantime, **422** for bad input. A failed attempt (for example a short password) does not use up the invite.
    - It does **not** log the user in. The user goes to `/login` afterwards.
  - **Token rules:** `secrets.token_urlsafe(32)`, valid for **7 days**, usable **once**. Only the **SHA-256 hash** is stored (`invites.token_hash`, unique). The accept call locks the invite row, so two requests at the same moment cannot both succeed.
  - **Link in the email:** `FRONTEND_URL` + `/accept-invite/<token>`.
  - **Table `invites`:** `id`, `email`, `role` (lowercase string), `organization_id` (FK), `invited_by` (FK to users, `SET NULL`), `token_hash`, `expires_at`, `accepted_at` (NULL while pending), `created_at`.
  - **Audit:** `invite.created` (actor = inviter) and `invite.accepted` (actor = the new user), both with `entity_type="invite"`, `entity_id` = invite id and `metadata={"role": ...}`. No email address or token is logged.
  - **Tests:** `backend/tests/test_invites.py` (success, role rules, duplicates, existing members, failed email, expired, reused, invalid token, audit entries).
- **Status:** Implemented (issue #31). The invite form and pending list on the team page came with issue #54.

### 9. Password Reset (Forgot & Reset Password)
- **What:** Allows users to request a password reset email using their registered email address and complete the reset using a secure token.
- **How:** Code: `backend/routers/auth.py`, schemas in `backend/schemas/auth.py`. Frontend: `frontend/src/pages/ForgotPassword.tsx`, `frontend/src/pages/ResetPassword.tsx`, and `frontend/src/api/auth.ts`.
  - `POST /auth/forgot-password` (public). Body: `{ "email": "user@example.com" }`. Returns **202** with a generic message ("If an account with this email exists, we have sent a link to reset the password.") whether or not the email exists, to prevent user enumeration.
    - Stored lowercase email lookup. Only active users get an email. The email is sent after the response, so the response time is the same for every email.
    - The email contains a link: `FRONTEND_URL` + `/reset-password/<token>` (the token is part of the path, not a query parameter).
    - Audit log: `user.password_reset_requested`.
  - `POST /auth/reset-password` (public). Body: `{ "token": "string", "new_password": "8–128 characters" }`. Returns **200** with a message on success.
    - Errors: **404** unknown token, **410** token already used, expired, or the user is inactive, **422** for bad input.
    - Updates the user password hash (argon2). Any other open reset link of this user stops working too.
    - Audit log: `user.password_reset`.
  - **Security Rules:** The token is `secrets.token_urlsafe(32)`, only its SHA-256 hash is stored, it is valid for **60 minutes** and works **once**. The reset call locks the token row, so two requests at the same moment cannot both use it.
- **Status:** Implemented

### 10. Audit log viewer (read the audit log)
- **What:** Owners and admins can read the audit log of their own company, with filters and pages.
- **How:** Code: `backend/routers/audit_logs.py`, schemas in `backend/schemas/audit_logs.py`. Frontend: `frontend/src/pages/AuditLog.tsx` and `frontend/src/api/auditLogs.ts`.
  - `GET /audit-logs` (owner or admin). Query parameters, all optional:
    - `action`: one of the `AuditAction` names (for example `ticket.created`). An unknown name returns **422**.
    - `date_from`, `date_to`: dates as `YYYY-MM-DD`. They are whole days in **UTC**, and `date_to` includes the whole day. If `date_from` is after `date_to`, the answer is **400**.
    - `page` (default 1) and `page_size` (default 20, maximum 100). Values outside the range return **422**.
  - Returns **200**, newest first:
```json
    {
      "items": [
        {
          "id": 12,
          "action": "ticket.status_changed",
          "actor_user_id": 3,
          "actor_name": "Ali",
          "entity_type": "ticket",
          "entity_id": 7,
          "metadata": { "status": ["new", "open"] },
          "created_at": "2026-10-09T12:00:00Z"
        }
      ],
      "total": 1,
      "page": 1,
      "page_size": 20
    }
```
  - `actor_name` is the user's full name (the email if there is no name). It is `null` when the system did it (for example `ticket.sla_breached`) or the user was deleted. The page shows "System" in that case.
  - **Tenant isolation:** the company filter always comes from the logged-in user, never from the request. Agents and customers get **403**; a missing or revoked token is **401**.
  - **For Saqeeba:** entries written with `log_audit_event` show up in the viewer automatically. When you add a new action to the `AuditAction` enum in `core/audit.py`, also add the same name to the `ACTIONS` list in `frontend/src/pages/AuditLog.tsx`, or it will not appear in the action filter dropdown (the entries themselves still show).
  - **Tests:** `backend/tests/test_audit_logs.py` (another company's entries never appear, also with filters; roles; action and date filters; pagination; actor name).
- **Status:** Implemented (issue #35)

### 11. SLA policy setting (first reply within X hours)
- **What:** One setting per company: "the first reply to a ticket is due within X hours". Owners and admins can read and change it. The SLA background job (item 13) reads the same value to find overdue tickets.
- **How:** Code: `backend/routers/settings.py`, schemas in `backend/schemas/settings.py`. Frontend: `frontend/src/pages/Settings.tsx` and `frontend/src/api/settings.ts` (`getSlaSettings`, `updateSlaSettings`).
  - `GET /settings/sla` (owner or admin). Returns **200**:
```json
    { "first_reply_hours": 4 }
```
  - `PUT /settings/sla` (owner or admin). Body:
```json
    { "first_reply_hours": 8 }
```
    - `first_reply_hours`: whole number from **1 to 168** (one week). Anything else, a missing field or a wrong type returns **422**.
    - Returns **200** with the saved value, same shape as `GET`.
  - Agents and customers get **403**; a missing or revoked token is **401**.
  - **Where it is stored:** the API field is `first_reply_hours`, but the value lives in the existing column `organizations.sla_first_response_hours`. The default is 4. **Code that reads the SLA (for example the background job) must use that column.**
  - **Tenant isolation:** the company always comes from the logged-in user. An `organization_id` in the request body is ignored.
  - **Audit:** `settings.sla_updated` with `entity_type="organization"`, `entity_id` = the company id and `metadata={"first_reply_hours": [old, new]}`. If the new value equals the old value, nothing changes and nothing is logged.
  - **Tests:** `backend/tests/test_sla_settings.py` (roles, limits, company comes from the user, one value per company, audit entries).
  - **Frontend:** the SLA form on `/settings` (see item 14).
- **Status:** Implemented (issue #52, frontend in issue #54)

### 12. Team management (list users, change role, deactivate)
- **What:** Owners and admins can see the users of their own company, change a user's role, and deactivate or reactivate a user.
- **How:** Code: `backend/routers/users.py`, schemas in `backend/schemas/users.py`. Frontend: `frontend/src/pages/Team.tsx` and `frontend/src/api/users.ts` (`listUsers`, `updateUser`).
  - `GET /users` (owner or admin). Returns **200**, a list of the user's own company users, oldest first:
```json
    [
      {
        "id": 3,
        "email": "ali@fastmart.com",
        "full_name": "Ali",
        "role": "agent",
        "is_active": true,
        "organization_id": 1,
        "created_at": "2026-09-29T12:00:00Z"
      }
    ]
```
    - No pagination yet. The password hash is never returned.
  - `PATCH /users/{id}` (owner or admin). Body: at least one of:
```json
    { "role": "admin", "is_active": false }
```
    - `role`: `customer`, `agent`, `admin` or `owner`. `is_active`: `true` or `false`.
    - An empty body, an unknown role or an unknown field (for example `organization_id`) returns **422**.
    - Returns **200** with the updated user, same shape as `GET /users`.
  - **Rules (checked in this order):**
    - **404:** the user does not exist or belongs to another company (same message for both).
    - **403:** an admin cannot change an owner, and cannot make someone an owner. Only an owner can.
    - **403:** nobody can demote or deactivate themselves. Sending your own current role is allowed.
    - **409:** the last active owner of a company can never be demoted or deactivated.
  - Agents and customers get **403**; a missing or revoked token is **401**.
  - **Deactivated users** are rejected on their next request, because `get_current_user` loads the user from the database every time.
  - **Audit:** `user.role_changed` with `metadata={"role": [old, new]}` and `user.deactivated` with `metadata={"is_active": [true, false]}`, both with `entity_type="user"` and `entity_id` = the changed user. A request that changes both writes two entries. No email or name is logged. Reactivating a user (`is_active: true`) is saved but not logged.
  - **Tests:** `backend/tests/test_users_admin.py` (cross-company 404, roles, admin vs owner, self rules, last active owner, audit entries without personal data, bad input).
  - **Frontend:** the team page on `/settings/team` (see item 14).
- **Status:** Implemented (issue #52, frontend in issue #54)

### 13. SLA background job and overdue alerts
- **What:** A background worker checks for tickets whose first reply is overdue, flags each one once, writes an audit entry and emails the owners and admins of that company.
- **How:** Code: `backend/core/sla.py` (the logic), `backend/worker.py` (the loop). Service: `worker` in `docker-compose.yml`. Column: `tickets.sla_breached_at`.
  - **Which tickets are flagged:** all of these must be true:
    - `first_response_at IS NULL` (no public staff reply yet; Saqeeba's comments code sets it)
    - `status` is not `resolved` and not `closed`
    - `sla_breached_at IS NULL` (not flagged before)
    - `created_at + organizations.sla_first_response_hours` hours is in the past (each company uses its own hours, see item 11)
  - **What happens to each ticket:**
    - `sla_breached_at` is set to the time of the run.
    - Audit entry `ticket.sla_breached` with `actor_user_id=None`, `entity_type="ticket"`, `entity_id` = ticket id and `metadata={"first_reply_hours": <hours>}`.
    - One email to every **active owner and admin** of the ticket's company. Subject: `SLA breached: ticket #<id>`. The body has the ticket subject, the creation time (UTC), the SLA hours and a link `FRONTEND_URL/tickets/<id>`.
  - **Only once:** a flagged ticket is never flagged or emailed again, even if it is still without a reply. A ticket that gets its first reply later keeps its `sla_breached_at`, because the SLA was already missed. A ticket that is resolved or closed without a reply is never flagged.
  - **Order and failures:** flags and audit entries are committed first, then the emails are sent. If one email fails (`EmailSendError`), it is logged and the run goes on with the next one. A failed alert is not sent again, but the audit log still shows the breach. If a company has no active owner or admin, a warning is logged and no email is sent.
  - **Function for tests:** `run_sla_check(db, now)` in `core/sla.py` returns the number of tickets flagged. It never reads Redis or the clock itself, so tests can pass any `now`. It does not use `send_email` anywhere else than `core.sla.send_email` (replace that name in tests).
  - **Worker:** `python -u worker.py`, one loop: run the check, wait `SLA_CHECK_INTERVAL_SECONDS`, repeat. A Redis lock (`lock:sla_check`, 5 minutes) stops two workers from running at the same moment, and the database query uses `FOR UPDATE SKIP LOCKED` as a second safety. An error in one run is logged and the worker keeps running. If Redis is down, the run is skipped.
  - **Env vars:** `SLA_CHECK_INTERVAL_SECONDS` (default 300, minimum 10). The worker also needs `DATABASE_URL`, `REDIS_URL` and the `SMTP_*` and `FRONTEND_URL` settings (see `.env.example`).
  - **Run and check:** `docker compose up` starts the worker. See its output with `docker compose logs worker`. Alerts show in Mailpit at http://localhost:8025 and as `ticket.sla_breached` entries on the `/audit-log` page.
  - **First run:** the first run flags every old ticket that is already past its SLA, so a database with old tickets gets several alerts at once.
  - **For Saqeeba:** `sla_breached_at` is written only by the worker. Please do not set it from the ticket endpoints. It is not returned by the API yet. If you want an "Overdue" badge in the inbox, add it to `TicketRead`.
  - **Table change:** `tickets.sla_breached_at`, timestamp with time zone, nullable. Migration `a7c3d9e15b42` (no backfill needed: NULL means "not breached").
  - **Tests:** `backend/tests/test_sla_job.py` (breached ticket flagged and emailed, only owners and admins get the email, audit entry without actor, ticket with a first response ignored, resolved and closed tickets ignored, ticket inside the SLA ignored, no second email on a second run, each company uses its own hours, inactive admin not emailed, one failed email does not stop the run).
- **Status:** Implemented (issue #53)

### 14. Admin settings and team pages (frontend)
- **What:** The screens where an owner or admin changes the SLA, manages the team and invites people. They use the APIs from items 8, 11 and 12.
- **How:** Code:
  - Pages: `frontend/src/pages/Settings.tsx` (route `/settings`) and `frontend/src/pages/Team.tsx` (route `/settings/team`).
  - Components: `frontend/src/components/InviteSection.tsx` (invite form and pending invites) and `frontend/src/components/ConfirmDialog.tsx` (small modal for confirm steps; Escape or a click outside cancels).
  - API files: `frontend/src/api/settings.ts`, `frontend/src/api/users.ts`, `frontend/src/api/invites.ts` and the helper `frontend/src/api/errors.ts`.
  - **`/settings`:** SLA form with a number input (whole number 1–168, checked in the browser and again by the backend), a loading state, "Try again" if loading fails, and success and error messages. The Save button is off while the value is unchanged.
  - **`/settings/team`:**
    - Members table: name, email, role (dropdown), status (Active / Inactive) and actions.
    - The role dropdown shows only the roles the current user may assign (owner: all four; admin: customer, agent, admin). The current role of a row is always shown.
    - **Deactivate** opens a confirm dialog. **Reactivate** needs no confirm.
    - Actions are disabled, with the reason as hover text, for: the user's own row, an owner row when the current user is an admin, and the last active owner.
    - After a 403, 404 or 409 the list is loaded again, because the data on screen may be out of date.
    - Invite form (email + role; an admin does not see "owner") and a table of pending invites (email, role, sent, expires).
  - **Error messages:** 403 and 409 show the backend's own text (for example "Only an owner can change an owner" or "A company must always have at least one active owner"). 404 shows "This item was not found". 422 shows a "values are not valid" message. 502 on invites says the email could not be sent and nothing was saved. 503 says the service is temporarily unavailable.
  - **The UI only hides and disables things.** The backend is the real check, so a changed or old page still gets 403, 404 or 409 from the API.
  - **For Saqeeba:** `apiErrorMessage` in `frontend/src/api/errors.ts` and `ApiError.detail` can be used on any page that needs a clear message for 403, 404 or 409.
- **Status:** Implemented (issue #54)

---

## Saqeeba provides → Ayesha consumes

### 1. Ticket fields: `first_response_at` and `status`
- **What:** Needed by the SLA background job (item 13) to detect overdue tickets.
- **How:** Columns on the `tickets` table (model: `backend/models/ticket.py`):
  - `first_response_at`: timestamp with time zone, nullable. It stays NULL until the first public (not internal) reply from staff. It is set in the same transaction as the comment (see Comments, #38).
  - `status`: string, one of `new`, `open`, `pending`, `resolved`, `closed` (default `new`). The allowed changes are enforced in `routers/tickets.py` (issue #36).
  - `created_at`: timestamp with time zone, set by the database. The SLA deadline is counted from it.
  - `organization_id`: the company of the ticket. The SLA hours come from that company.
- **Status:** Implemented (used by the SLA job, issue #53)

## Comments (#38)

### POST /tickets/{ticket_id}/comments
Create a comment on a ticket. Both staff and customers can post.

Body:
```json
{
  "body": "string (required)",
  "is_internal": false
}
```

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

## Tags (Issue #39)

### POST /tags
Create a new tag (agent+ only)
- Request: `{"name": "urgent", "color": "red"}`
- Response: 201 TagRead
- Error: 403 if customer

### GET /tags
List all tags in user's organization
- Response: 200 list[TagRead]

### DELETE /tags/{tag_id}
Delete a tag (agent+ only)
- Response: 204
- Error: 403 if customer, 404 if not found

### POST /tags/{tag_id}/tickets/{ticket_id}
Add tag to ticket (agent+ only)
- Response: 204
- Error: 403 if customer, 404 if tag/ticket not found

### DELETE /tags/{tag_id}/tickets/{ticket_id}
Remove tag from ticket (agent+ only)
- Response: 204
- Error: 403 if customer, 404 if tag/ticket not found

### Tag validation update (Issue #39 follow-up)
- Tag names are lowercased and trimmed before saving, so "Billing" and "billing" are treated as the same tag within a company (409 on duplicate).
- Tag color must be a hex code matching `^#[0-9a-fA-F]{6}$`, or null. Any other value returns 422.

## Attachments (Issue #40)

### POST /tickets/{ticket_id}/attachments
Upload a file attachment to a ticket (multipart/form-data).
- Field: file (the file to upload)
- Allowed types: images (jpeg, png, gif, webp), pdf, txt - validated against the file's extension AND its declared content type, not just one or the other
- Max size: 5 MB
- Response: 201 AttachmentRead
- Error: 400 if type/size invalid, 404 if ticket not in user's org

### GET /tickets/{ticket_id}/attachments
List attachments on a ticket, oldest first.
- Response: 200 list[AttachmentRead]
- Error: 404 if ticket not in user's org

### GET /attachments/{attachment_id}/download
Download an attachment's file.
- Response: 200 file stream (original filename, correct content type)
- Error: 404 if attachment not in user's org, or if the file is missing on disk

### GET /tickets/{id} now includes tags
TicketRead responses include a tags field:
```json
[{"id": 1, "name": "urgent", "color": "#ff0000", "organization_id": 1, "created_at": "..."}]
```

## Search (Issue #60)

### GET /tickets?search=<term>
Adds case-insensitive, partial-match search over tickets.
- Matches against both subject and description
- Combines with existing filters: status, priority, assignee_id
- Omit the parameter to get all tickets as before (unchanged behavior)
- Example: `GET /tickets?search=order&status=open` returns only open tickets whose subject or description contains "order"
````