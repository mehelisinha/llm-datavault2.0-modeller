# Microsoft Entra ID sign-in for DWA — setup guide

This document walks you through registering the two app registrations Entra
needs, wiring them into `.env`, and running the app with real sign-in.

The implementation is **opt-in**: while the variables in this guide are
unset, the API stays in dev mode (accepts an `X-Actor` header) and the UI
shows a "development mode" sign-in screen. Nothing in the workflow breaks
during the transition.

---

## 1. What you are creating

Two **Microsoft Entra ID** app registrations:

| App registration | Purpose                                                  | Tokens it issues  |
| ---------------- | -------------------------------------------------------- | ----------------- |
| **DWA API**      | Represents the FastAPI backend; defines the `Admin` role | (none, it is the audience) |
| **DWA UI**       | Represents the React SPA the browser loads               | Access token for the API |

You also assign the **Admin** app role to the colleagues who should see
*all users' history* (everyone else only sees their own).

---

## 2. Register the API app

1. Go to <https://entra.microsoft.com> → **Identity → Applications → App registrations → New registration**.
2. Name: `DWA Metadata API` (anything you like).
3. Supported account types: **Accounts in this organizational directory only (ExampleCorp only — single tenant)**.
4. Redirect URI: leave empty.
5. Click **Register**.
6. On the overview page, copy the **Application (client) ID** — this will become `DWA_API_AAD_API_CLIENT_ID`.
7. Copy the **Directory (tenant) ID** — this will become `DWA_API_AAD_TENANT_ID` (and `VITE_MSAL_TENANT_ID`).

### 2a. Expose a scope so the SPA can request a token

1. Left nav → **Expose an API → Add a scope**.
2. Accept the default Application ID URI (`api://<api-client-id>`) → **Save and continue**.
3. Scope name: `access_as_user`
4. Who can consent: **Admins and users**
5. Display name + description: e.g. `Access DWA on behalf of the signed-in user`.
6. State: **Enabled** → **Add scope**.
7. The full scope identifier is now `api://<api-client-id>/access_as_user`. Copy it — it will become `VITE_MSAL_API_SCOPE`.

### 2b. Define the Admin app role

1. Left nav → **App roles → Create app role**.
2. Display name: `Admin`
3. Allowed member types: **Users/Groups**
4. Value: `Admin` *(must match `DWA_API_AAD_ADMIN_APP_ROLE` — default is `Admin`)*
5. Description: `Can view all users' DWA history.`
6. Enable: ✅ → **Apply**.

---

## 3. Register the UI (SPA) app

1. **App registrations → New registration**.
2. Name: `DWA Metadata UI`.
3. Supported account types: single-tenant (same as the API).
4. **Redirect URI**: platform = **Single-page application (SPA)**; URI = `http://localhost:5173` for local dev (add more later for staging/production).
5. **Register**.
6. Copy the **Application (client) ID** — this will become `VITE_MSAL_CLIENT_ID`.

### 3a. Grant the SPA permission to call the API

1. Left nav → **API permissions → Add a permission → My APIs → DWA Metadata API**.
2. **Delegated permissions** → tick `access_as_user` → **Add permissions**.
3. Click **Grant admin consent for ExampleCorp** (you or a tenant admin).

### 3b. Add production redirect URIs later

When you deploy the UI to a real URL, add it under **Authentication → Single-page application → Redirect URIs**.

---

## 4. Assign the Admin role to your admins

1. Go to **Enterprise applications → DWA Metadata API → Users and groups → Add user/group**.
2. Pick the colleagues (or a security group) and select the **Admin** role.

> **Don't have admin rights to assign roles right now?** Use the email
> allowlist instead: set `DWA_API_ADMIN_EMAILS=alice@example.com,bob@example.com`
> in `.env`. Any user whose UPN matches the list is treated as an admin
> until you finish the role assignment.

---

## 5. Fill in `.env`

In `dwa/.env` (copy from `dwa/.env.template` if missing):

```dotenv
# Backend
DWA_API_AAD_TENANT_ID=<tenant guid>
DWA_API_AAD_API_CLIENT_ID=<API app client id>
DWA_API_AAD_ADMIN_APP_ROLE=Admin
# Optional fallback while you wait for role assignments
DWA_API_ADMIN_EMAILS=

# CORS only needed when UI runs on a different origin than the API.
# Vite dev server proxies /api → :8000 so this can stay empty in dev.
DWA_API_CORS_ALLOWED_ORIGINS=
```

In `dwa/ui/.env` (create the file — Vite loads it automatically):

```dotenv
VITE_MSAL_CLIENT_ID=<UI app client id>
VITE_MSAL_TENANT_ID=<tenant guid>
VITE_MSAL_API_SCOPE=api://<API app client id>/access_as_user

# Optional — sensible defaults are derived from VITE_MSAL_TENANT_ID and
# window.location.origin respectively.
# VITE_MSAL_AUTHORITY=
# VITE_MSAL_REDIRECT_URI=

# Branding shown on the login screen
VITE_APP_NAME=DWA Metadata Generator
VITE_APP_TENANT_NAME=ExampleCorp
```

---

## 6. Run it

```powershell
# In one terminal — backend
cd dwa
.\.venv\Scripts\Activate.ps1
uvicorn dbt_builder.api:app --reload

# In another terminal — UI
cd dwa\ui
pnpm install
pnpm dev
```

Open <http://localhost:5173>. You will be redirected to `/login`, sign in
with your ExampleCorp account, and land on the Discovery page. The header shows
your email and a **Sign out** button. The History page shows only your
records; admins additionally see a **My history / All users** toggle.

---

## 7. How the pieces map at runtime

```
Browser ──login──► Entra ID
   │                  │
   │ ◄── access token ┘
   ▼
Browser sends every API request with:
   Authorization: Bearer <token>
   X-Actor: <email>           ← fallback for dev mode

FastAPI:
   if DWA_API_AAD_TENANT_ID + DWA_API_AAD_API_CLIENT_ID are set
      → validate the bearer token against Entra JWKS
      → use the email/UPN claim as the actor
      → use the `roles` claim (or DWA_API_ADMIN_EMAILS) to decide admin
   else
      → fall back to the X-Actor header (development mode)
```

Approvals (`approve`, `reject`, `submit-for-review`, `request-changes`)
are persisted via `ApprovalRecord` with `actor`, `timestamp`, `status`
and `comment` — exactly what the History page displays.
