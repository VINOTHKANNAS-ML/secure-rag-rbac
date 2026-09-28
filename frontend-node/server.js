/**
 * Node.js/Express frontend for the Secure Enterprise RAG (RBAC) project.
 *
 * This server does NOT talk to the vector database or the LLM directly -
 * it's a thin frontend that proxies login/ask requests to the Python
 * FastAPI backend (api_server.py) and keeps the session token server-side
 * so it never has to be exposed to client-side JavaScript.
 *
 * Run:
 *   npm install
 *   npm start
 *
 * Requires the Python backend running separately:
 *   uvicorn api_server:app --reload --port 8000
 */

require("dotenv").config();

const express = require("express");
const session = require("express-session");
const path = require("path");

const PYTHON_API_URL = process.env.PYTHON_API_URL || "http://localhost:8000";
const PORT = process.env.PORT || 3000;
const SESSION_SECRET = process.env.SESSION_SECRET || "dev-secret-change-me";

const app = express();

// Uploads are sent as base64 JSON (2 MB file limit -> ~2.7 MB encoded).
app.use(express.json({ limit: "4mb" }));
app.use(express.static(path.join(__dirname, "public")));
app.use(
  session({
    secret: SESSION_SECRET,
    resave: false,
    saveUninitialized: false,
    cookie: { maxAge: 8 * 60 * 60 * 1000 }, // 8 hours, matches backend TTL
  })
);

function requireLogin(req, res, next) {
  if (!req.session.token) {
    return res.status(401).json({ error: "Not logged in." });
  }
  next();
}

function requireAdmin(req, res, next) {
  if (!req.session.token) {
    return res.status(401).json({ error: "Not logged in." });
  }
  if (!req.session.user || req.session.user.role !== "admin") {
    return res.status(403).json({ error: "Admin access required." });
  }
  next();
}

// ---------------------------------------------------------------------
// Pages
// ---------------------------------------------------------------------
app.get("/", (req, res) => {
  if (req.session.token) {
    return res.redirect("/chat");
  }
  res.sendFile(path.join(__dirname, "public", "login.html"));
});

app.get("/chat", (req, res) => {
  if (!req.session.token) {
    return res.redirect("/");
  }
  res.sendFile(path.join(__dirname, "public", "chat.html"));
});

app.get("/documents", (req, res) => {
  if (!req.session.token) {
    return res.redirect("/");
  }
  res.sendFile(path.join(__dirname, "public", "documents.html"));
});

app.get("/admin", (req, res) => {
  if (!req.session.token) {
    return res.redirect("/");
  }
  if (!req.session.user || req.session.user.role !== "admin") {
    return res.redirect("/chat");
  }
  res.sendFile(path.join(__dirname, "public", "admin.html"));
});

// ---------------------------------------------------------------------
// API proxy routes - the browser talks to these (same-origin, no CORS
// issues), and this server forwards to the Python backend.
// ---------------------------------------------------------------------
app.post("/api/login", async (req, res) => {
  const { username, password } = req.body;

  try {
    const response = await fetch(`${PYTHON_API_URL}/api/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({ error: data.detail || "Login failed." });
    }

    // Keep the backend token server-side only.
    req.session.token = data.token;
    req.session.user = {
      username: data.username,
      full_name: data.full_name,
      department: data.department,
      role: data.role,
      allowed_departments: data.allowed_departments,
      max_confidentiality: data.max_confidentiality,
    };

    res.json({ ok: true, user: req.session.user });
  } catch (err) {
    console.error("Login proxy error:", err);
    res.status(502).json({ error: "Could not reach the backend API. Is it running?" });
  }
});

// ---------------------------------------------------------------------
// Document upload / management proxies (any logged-in user; the Python
// backend enforces what each role may upload, list, and delete).
// ---------------------------------------------------------------------
async function proxyAuthed(method, pythonPath, req, res, body) {
  try {
    const response = await fetch(`${PYTHON_API_URL}${pythonPath}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${req.session.token}`,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) {
      if (response.status === 401) {
        req.session.destroy(() => {});
      }
      return res.status(response.status).json({ error: data.detail || "Request failed." });
    }
    res.json(data);
  } catch (err) {
    console.error(`Proxy ${method} ${pythonPath} error:`, err);
    res.status(502).json({ error: "Could not reach the backend API. Is it running?" });
  }
}

app.get("/api/documents/options", requireLogin, (req, res) =>
  proxyAuthed("GET", "/api/documents/options", req, res));
app.get("/api/documents", requireLogin, (req, res) =>
  proxyAuthed("GET", "/api/documents", req, res));
app.post("/api/documents", requireLogin, (req, res) =>
  proxyAuthed("POST", "/api/documents", req, res, req.body));
app.delete("/api/documents/:docId", requireLogin, (req, res) =>
  proxyAuthed("DELETE", `/api/documents/${encodeURIComponent(req.params.docId)}`, req, res));

app.get("/api/me", requireLogin, (req, res) => {
  res.json({ user: req.session.user });
});

app.post("/api/ask", requireLogin, async (req, res) => {
  const { question } = req.body;

  try {
    const response = await fetch(`${PYTHON_API_URL}/api/ask`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${req.session.token}`,
      },
      body: JSON.stringify({ question }),
    });

    const data = await response.json();

    if (!response.ok) {
      if (response.status === 401) {
        req.session.destroy(() => {});
      }
      return res.status(response.status).json({ error: data.detail || "Request failed." });
    }

    res.json(data);
  } catch (err) {
    console.error("Ask proxy error:", err);
    res.status(502).json({ error: "Could not reach the backend API. Is it running?" });
  }
});

app.post("/api/logout", async (req, res) => {
  const token = req.session.token;

  if (token) {
    try {
      await fetch(`${PYTHON_API_URL}/api/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch (err) {
      console.error("Logout proxy error (continuing anyway):", err);
    }
  }

  req.session.destroy(() => {
    res.json({ ok: true });
  });
});

// ---------------------------------------------------------------------
// Admin proxy routes - all require an admin session (checked here AND
// re-checked by the Python backend, which is the real enforcement point).
// ---------------------------------------------------------------------
async function proxyGet(pythonPath, req, res) {
  try {
    const response = await fetch(`${PYTHON_API_URL}${pythonPath}`, {
      headers: { Authorization: `Bearer ${req.session.token}` },
    });
    const data = await response.json();
    if (!response.ok) {
      return res.status(response.status).json({ error: data.detail || "Request failed." });
    }
    res.json(data);
  } catch (err) {
    console.error(`Proxy GET ${pythonPath} error:`, err);
    res.status(502).json({ error: "Could not reach the backend API. Is it running?" });
  }
}

app.get("/api/admin/roles", requireAdmin, (req, res) => proxyGet("/api/admin/roles", req, res));
app.get("/api/admin/users", requireAdmin, (req, res) => proxyGet("/api/admin/users", req, res));
app.get("/api/admin/login-log", requireAdmin, (req, res) => proxyGet("/api/admin/login-log", req, res));

app.post("/api/admin/users", requireAdmin, async (req, res) => {
  try {
    const response = await fetch(`${PYTHON_API_URL}/api/admin/users`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${req.session.token}`,
      },
      body: JSON.stringify(req.body),
    });
    const data = await response.json();
    if (!response.ok) {
      return res.status(response.status).json({ error: data.detail || "Could not create user." });
    }
    res.json(data);
  } catch (err) {
    console.error("Create user proxy error:", err);
    res.status(502).json({ error: "Could not reach the backend API. Is it running?" });
  }
});

app.delete("/api/admin/users/:username", requireAdmin, async (req, res) => {
  try {
    const response = await fetch(
      `${PYTHON_API_URL}/api/admin/users/${encodeURIComponent(req.params.username)}`,
      {
        method: "DELETE",
        headers: { Authorization: `Bearer ${req.session.token}` },
      }
    );
    const data = await response.json();
    if (!response.ok) {
      return res.status(response.status).json({ error: data.detail || "Could not remove user." });
    }
    res.json(data);
  } catch (err) {
    console.error("Delete user proxy error:", err);
    res.status(502).json({ error: "Could not reach the backend API. Is it running?" });
  }
});

app.get("/api/admin/login-log/csv", requireAdmin, async (req, res) => {
  try {
    const response = await fetch(`${PYTHON_API_URL}/api/admin/login-log/csv`, {
      headers: { Authorization: `Bearer ${req.session.token}` },
    });
    if (!response.ok) {
      return res.status(response.status).json({ error: "Could not generate CSV." });
    }
    res.setHeader("Content-Type", "text/csv");
    res.setHeader(
      "Content-Disposition",
      response.headers.get("content-disposition") || 'attachment; filename="login_log.csv"'
    );
    const csvText = await response.text();
    res.send(csvText);
  } catch (err) {
    console.error("CSV proxy error:", err);
    res.status(502).json({ error: "Could not reach the backend API. Is it running?" });
  }
});

app.listen(PORT, () => {
  console.log(`Node frontend running at http://localhost:${PORT}`);
  console.log(`Proxying to Python backend at ${PYTHON_API_URL}`);
});
