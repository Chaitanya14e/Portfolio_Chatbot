# Groq model configuration

The backend uses Groq for chatbot answers, streamed responses, and resume fact
extraction. Set `GROQ_API_KEY` in the private `backend\.env` file.
`GROQ_MODEL` defaults to `openai/gpt-oss-120b`. Never put the key in frontend
environment variables or commit it. Install backend dependencies after
updating `requirements.txt`:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

# GitHub projects

The chatbot can include public GitHub repositories alongside resume projects.
Imported repositories are saved to the `projects` MongoDB collection with
`source_type = github` and `status = pending_review`. Pending and rejected
projects are never included in chatbot context. Review imported details and
deployment links before approving a project.

## MongoDB configuration

Set `MONGODB_URI` in `backend\.env` to your MongoDB connection string. The
database name may be included in the URI; alternatively, set
`MONGODB_DATABASE`. If neither specifies a database, the backend uses
`portfolio_chatbot`. Copy `.env.example` as a template, and keep credentials
private.

For Render deployments, add `MONGODB_URI` under the service's **Environment**
settings; Render does not read your local `backend\.env`. Add `GROQ_API_KEY`
there as well, and optionally set `GROQ_MODEL`. Use the connection string
from MongoDB Atlas, and make sure Atlas Network Access permits
connections from the deployed service. Do not set the hosted URI to
`localhost`: that points back to the Render container, not to Atlas.
Set `FRONTEND_ORIGINS` in Render to
`https://portfolio-chatbot-assistant.vercel.app` if you have configured an
override there; it is included in the application's default allowed origins.

MongoDB creates collections as data is first written. On startup, the backend
creates a unique per-profile GitHub URL index and a unique profile-fact key
index. No SQL migration is needed.

## Import a repository

Start the backend, then use Swagger at `http://127.0.0.1:8000/docs` or send:

```http
POST /api/projects/import-github
Content-Type: application/json
```

```json
{
  "github_url": "https://github.com/owner/repository"
}
```

The URL must point directly to a public repository on `github.com` using HTTPS.
The importer uses GitHub's public REST API, reads metadata and a bounded README
summary, and never downloads or executes repository code. No deployment URL is
inferred from repository metadata.

The response includes the project's MongoDB ID as a string and `import_status` (`imported`
or `already_exists`). New imports remain pending review. Invalid URLs return
422, missing/private repositories return 404, and GitHub rate limiting returns
429. The API does not return tokens or stack traces.

Typical responses:

- `201 Created`: a project was imported and saved as `pending_review`.
- `200 OK`: the repository URL is already imported; the existing project is
  returned without overwriting it.
- `422 Unprocessable Entity`: the URL is not a supported GitHub repository
  URL.
- `404 Not Found`: the repository is private, missing, or unavailable.
- `429 Too Many Requests`: GitHub's unauthenticated API rate limit was reached.
- `504 Gateway Timeout`: GitHub did not respond before the request timeout.

The success response includes the project ID, name, description, technologies,
category, GitHub/deployed URLs, source type, review status, owner, language,
topics, bounded README summary, and import status. A deployment URL remains
null until explicitly entered and approved during review.

## Review projects

Review operations are disabled unless `ADMIN_API_TOKEN` is configured in the
backend environment. Set a long, private token in `backend\.env`; do not commit
it or expose it to the frontend. Use [`.env.example`](./.env.example) as a
template; the example value is a placeholder and must be replaced.

List pending records:

```http
GET /api/projects/review
X-Admin-Token: <admin-token>
```

Approve or reject a pending record. The optional editable fields are applied
before changing its status; `status` must be `verified` or `rejected`.

```http
PATCH /api/projects/{project_id}/review
X-Admin-Token: <admin-token>
Content-Type: application/json
```

```json
{
  "status": "verified",
  "deployed_url": "<your verified deployment URL>"
}
```

Only verified projects are added to chatbot context. The model groups broad
project-list answers into Frontend projects, Full-stack projects, AI projects,
and Other projects. A deployed button appears only for a deployment URL stored
on the exact verified project.

## Run and test

From `backend\`:

```powershell
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests use mocked GitHub API responses and do not import repositories over the
network.
