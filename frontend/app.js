// Banco de Proyectos de Grado — frontend (vanilla JS, hash router)

const appRoot = document.getElementById("app");
const dialog = document.getElementById("dialog");
const dialogBody = document.getElementById("dialog-body");

const state = { user: null, filters: null };

const ROLE_LABELS = { student: "Estudiante", professor: "Profesor", admin: "Administrador" };
const STATUS_LABELS = {
  available: "Disponible",
  assigned: "Asignado",
  closed: "Cerrado",
  pending: "Pendiente",
  accepted: "Aceptada",
  rejected: "Rechazada",
  withdrawn: "Retirada",
};

const DEMO_ACCOUNTS = [
  { email: "camila.ortiz@demo.edu.co", label: "Camila Ortiz", role: "Estudiante" },
  { email: "laura.benavides@demo.edu.co", label: "Laura Benavides", role: "Profesora" },
  { email: "admin@demo.edu.co", label: "Coordinación", role: "Administrador" },
];

/* ---------- Utilities ---------- */

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[ch]);
}

function formatDate(isoString) {
  if (!isoString) return "";
  return new Date(isoString + "Z").toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" });
}

function debounce(fn, wait = 400) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

function badge(status) {
  return `<span class="badge badge--${status}">${STATUS_LABELS[status] ?? status}</span>`;
}

function showToast(message, isError = false) {
  const toast = document.createElement("div");
  toast.className = `toast${isError ? " toast--error" : ""}`;
  toast.textContent = message;
  document.getElementById("toasts").appendChild(toast);
  setTimeout(() => toast.remove(), 4200);
}

function emptyState(title, text, actionHtml = "") {
  return `<div class="empty"><h3>${title}</h3><p>${text}</p>${actionHtml}</div>`;
}

function skeletons(count = 4) {
  return Array.from({ length: count }, () => '<div class="skeleton" aria-hidden="true"></div>').join("");
}

function formToObject(form) {
  return Object.fromEntries(new FormData(form).entries());
}

/* ---------- API client ---------- */

class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function api(path, { method = "GET", body } = {}) {
  const response = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
    credentials: "same-origin",
  });
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    let message = "Ocurrió un error inesperado.";
    if (typeof detail === "string") message = detail;
    else if (detail?.message) message = detail.message;
    else if (Array.isArray(detail)) message = "Revisa los campos: " + detail.map((d) => d.loc.at(-1)).join(", ");
    if (response.status === 401 && state.user) {
      state.user = null;
      renderLogin();
    }
    throw new ApiError(message, response.status, detail);
  }
  return data;
}

/* ---------- Shell & router ---------- */

function navItems(role) {
  const common = [
    { hash: "#/", label: "Inicio" },
    { hash: "#/temas", label: "Explorar temas" },
    { hash: "#/verificar", label: "Verificar idea" },
  ];
  if (role === "student") {
    return [...common, { hash: "#/postulaciones", label: "Mis postulaciones" }, { hash: "#/hitos", label: "Hitos", soon: true }];
  }
  if (role === "professor") {
    return [
      ...common,
      { hash: "#/mis-temas", label: "Mis temas" },
      { hash: "#/recibidas", label: "Postulaciones" },
      { hash: "#/hitos", label: "Hitos", soon: true },
    ];
  }
  return [...common, { hash: "#/recibidas", label: "Postulaciones" }, { hash: "#/usuarios", label: "Usuarios" }];
}

function renderShell() {
  const current = location.hash || "#/";
  const links = navItems(state.user.role)
    .map(
      (item) => `<li><a href="${item.hash}" ${current === item.hash ? 'aria-current="page"' : ""}>${item.label}${
        item.soon ? ' <span class="soon">Fase 2</span>' : ""
      }</a></li>`
    )
    .join("");

  appRoot.innerHTML = `
    <header class="navbar">
      <nav class="container navbar__inner" aria-label="Principal">
        <a class="brand" href="#/"><span class="brand__mark" aria-hidden="true">BG</span>Banco de Grado</a>
        <button class="btn btn--ghost menu-toggle" aria-expanded="false" aria-controls="nav-links">Menú</button>
        <ul class="nav-links" id="nav-links">${links}</ul>
        <div class="user-chip">
          <div>
            <div class="user-chip__name">${escapeHtml(state.user.full_name)}</div>
            <div class="user-chip__role">${ROLE_LABELS[state.user.role]}</div>
          </div>
          <button class="btn btn--secondary btn--sm" id="logout">Salir</button>
        </div>
      </nav>
    </header>
    <main class="container" id="view"></main>`;

  const toggle = appRoot.querySelector(".menu-toggle");
  const navList = appRoot.querySelector("#nav-links");
  toggle.addEventListener("click", () => {
    const open = navList.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", String(open));
  });
  appRoot.querySelector("#logout").addEventListener("click", async () => {
    await api("/api/auth/logout", { method: "POST" });
    state.user = null;
    location.hash = "";
    renderLogin();
  });
}

const routes = {
  "#/": viewDashboard,
  "#/temas": viewExplore,
  "#/verificar": viewSimilarityChecker,
  "#/postulaciones": viewMyApplications,
  "#/mis-temas": viewMyTopics,
  "#/publicar": viewPublishTopic,
  "#/recibidas": viewReceivedApplications,
  "#/usuarios": viewUsers,
  "#/hitos": viewMilestonesRoadmap,
};

async function router() {
  if (dialog.open) dialog.close();
  if (!state.user) return renderLogin();
  renderShell();
  const view = document.getElementById("view");
  const handler = routes[location.hash || "#/"] ?? viewDashboard;
  try {
    await handler(view);
  } catch (error) {
    view.innerHTML = `<div class="empty"><h3>No pudimos cargar esta sección</h3><p>${escapeHtml(error.message)}</p>
      <button class="btn btn--secondary" onclick="location.reload()">Intentar de nuevo</button></div>`;
  }
  window.scrollTo(0, 0);
}

/* ---------- Auth ---------- */

function renderLogin(mode = "login") {
  appRoot.innerHTML = `
    <div class="auth">
      <section class="auth__intro">
        <p class="eyebrow">Ingeniería de Software · Opciones de grado</p>
        <h1 class="hero-title">Encuentra tu tema de grado sin pisar el de nadie.</h1>
        <p class="page-lead">Los profesores publican temas disponibles, los estudiantes se postulan y el sistema impide que un mismo tema se tome dos veces.</p>
        <ul class="auth__points">
          <li><strong>01</strong> Banco único de temas, con estado en tiempo real.</li>
          <li><strong>02</strong> Detección automática de temas similares o duplicados.</li>
          <li><strong>03</strong> Postulación y aprobación con trazabilidad.</li>
        </ul>
      </section>
      <section class="auth__panel">
        <div class="tabs" role="tablist">
          <button role="tab" aria-selected="${mode === "login"}" data-mode="login">Iniciar sesión</button>
          <button role="tab" aria-selected="${mode === "register"}" data-mode="register">Crear cuenta de estudiante</button>
        </div>
        <div id="auth-error"></div>
        ${mode === "login" ? loginFormHtml() : registerFormHtml()}
      </section>
    </div>`;

  appRoot.querySelectorAll("[data-mode]").forEach((tab) =>
    tab.addEventListener("click", () => renderLogin(tab.dataset.mode))
  );

  const form = appRoot.querySelector("form");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = form.querySelector("[type=submit]");
    submit.disabled = true;
    try {
      const payload = formToObject(form);
      state.user = await api(mode === "login" ? "/api/auth/login" : "/api/auth/register", { method: "POST", body: payload });
      location.hash = "#/";
      router();
    } catch (error) {
      appRoot.querySelector("#auth-error").innerHTML = `<div class="alert alert--error">${escapeHtml(error.message)}</div>`;
      submit.disabled = false;
    }
  });

  appRoot.querySelectorAll("[data-demo]").forEach((button) =>
    button.addEventListener("click", () => {
      form.email.value = button.dataset.demo;
      form.password.value = "demo1234";
      form.requestSubmit();
    })
  );
}

function loginFormHtml() {
  return `
    <form class="form" novalidate>
      <div class="field"><label for="email">Correo institucional</label>
        <input class="input" id="email" name="email" type="email" autocomplete="email" required></div>
      <div class="field"><label for="password">Contraseña</label>
        <input class="input" id="password" name="password" type="password" autocomplete="current-password" required></div>
      <button class="btn btn--primary" type="submit">Entrar →</button>
    </form>
    <div class="demo-accounts">
      <p class="muted" style="font-size:14px">Cuentas de demostración (contraseña <span class="mono">demo1234</span>):</p>
      ${DEMO_ACCOUNTS.map((a) => `<button type="button" data-demo="${a.email}"><span>${a.label}</span><span class="muted">${a.role}</span></button>`).join("")}
    </div>`;
}

function registerFormHtml() {
  return `
    <form class="form" novalidate>
      <div class="field"><label for="full_name">Nombre completo</label>
        <input class="input" id="full_name" name="full_name" required minlength="3"></div>
      <div class="field"><label for="email">Correo institucional</label>
        <input class="input" id="email" name="email" type="email" required></div>
      <div class="field"><label for="program">Programa</label>
        <input class="input" id="program" name="program" value="Ingeniería de Software"></div>
      <div class="field"><label for="password">Contraseña</label>
        <input class="input" id="password" name="password" type="password" minlength="6" required>
        <span class="hint">Mínimo 6 caracteres.</span></div>
      <button class="btn btn--primary" type="submit">Crear cuenta →</button>
    </form>`;
}

/* ---------- Dashboard ---------- */

async function viewDashboard(view) {
  view.innerHTML = skeletons(3);
  const stats = await api("/api/admin/stats");
  const { role, full_name } = state.user;
  const firstName = escapeHtml(full_name.split(" ")[0]);
  const maxLine = Math.max(1, ...stats.topics_by_research_line.map((l) => l.count));

  const headline = {
    student: "Elige un tema que nadie más haya tomado.",
    professor: "Publica temas y elige a tus tesistas.",
    admin: "Panorama del banco de proyectos.",
  }[role];

  const shortcuts = {
    student: [
      ["#/temas", "Explorar temas disponibles", "Filtra por línea de investigación y postúlate."],
      ["#/verificar", "¿Tu idea ya existe?", "Compara tu propuesta con los temas del banco antes de presentarla."],
    ],
    professor: [
      ["#/publicar", "Publicar un tema", "El sistema te avisa si ya hay uno parecido."],
      ["#/recibidas", "Revisar postulaciones", "Acepta o rechaza con retroalimentación."],
    ],
    admin: [
      ["#/usuarios", "Gestionar profesores", "Crea cuentas para los docentes que publican temas."],
      ["#/recibidas", "Ver postulaciones", "Seguimiento de todas las postulaciones del programa."],
    ],
  }[role];

  view.innerHTML = `
    <section>
      <p class="eyebrow">Hola, ${firstName}</p>
      <h1 class="hero-title">${headline}</h1>
    </section>

    <section class="section" aria-label="Indicadores">
      <div class="kpis">
        <div class="kpi"><div class="kpi__value">${stats.topics.available}</div><div class="kpi__label">Temas disponibles</div></div>
        <div class="kpi"><div class="kpi__value">${stats.topics.assigned}</div><div class="kpi__label">Temas asignados</div></div>
        <div class="kpi"><div class="kpi__value">${stats.applications.pending}</div><div class="kpi__label">Postulaciones pendientes</div></div>
        <div class="kpi"><div class="kpi__value">${stats.professors}</div><div class="kpi__label">Profesores publicando</div></div>
      </div>
    </section>

    <section class="section grid-2">
      ${shortcuts.map(([href, title, text]) => `
        <a class="card link-card" href="${href}"><h3>${title}</h3><p class="muted">${text}</p><div class="arrow">Ir →</div></a>`).join("")}
    </section>

    <section class="section">
      <h2 class="section-title">Temas activos por línea de investigación</h2>
      <div class="card bars">
        ${stats.topics_by_research_line.length
          ? stats.topics_by_research_line.map((l) => `
            <div class="bar">
              <span class="bar__label">${escapeHtml(l.research_line)}</span>
              <div class="bar__track" role="img" aria-label="${l.count} temas"><div class="bar__fill" style="width:${(l.count / maxLine) * 100}%"></div></div>
              <span class="bar__value">${l.count}</span>
            </div>`).join("")
          : '<p class="muted">Aún no hay temas publicados.</p>'}
      </div>
    </section>`;
}

/* ---------- Explore topics ---------- */

async function loadFilters() {
  if (!state.filters) state.filters = await api("/api/topics/filters");
  return state.filters;
}

async function viewExplore(view) {
  const filters = await loadFilters();
  view.innerHTML = `
    <div class="page-header">
      <div>
        <p class="eyebrow">Banco de temas</p>
        <h1 class="page-title">Explorar temas</h1>
        <p class="page-lead">Todos los temas publicados por los profesores. Los asignados siguen visibles para que nadie proponga lo mismo.</p>
      </div>
    </div>
    <form class="toolbar" role="search" id="filters">
      <div class="field field--search"><label class="visually-hidden" for="q">Buscar</label>
        <input class="input" id="q" name="q" placeholder="Buscar por título, descripción o palabra clave…"></div>
      <div class="field"><label class="visually-hidden" for="status">Estado</label>
        <select class="select" id="status" name="status">
          <option value="">Todos los estados</option>
          <option value="available" selected>Disponibles</option>
          <option value="assigned">Asignados</option>
          <option value="closed">Cerrados</option>
        </select></div>
      <div class="field"><label class="visually-hidden" for="research_line">Línea</label>
        <select class="select" id="research_line" name="research_line">
          <option value="">Todas las líneas</option>
          ${filters.research_lines.map((l) => `<option>${escapeHtml(l)}</option>`).join("")}
        </select></div>
    </form>
    <div id="results">${skeletons()}</div>`;

  const form = view.querySelector("#filters");
  const results = view.querySelector("#results");

  const load = async () => {
    const params = new URLSearchParams(Object.entries(formToObject(form)).filter(([, v]) => v));
    results.innerHTML = skeletons();
    try {
      const topics = await api(`/api/topics?${params}`);
      results.innerHTML = topics.length
        ? `<p class="muted" style="margin-bottom:12px;font-size:14px">${topics.length} tema(s)</p><div class="topic-list">${topics.map(topicRowHtml).join("")}</div>`
        : emptyState("No hay temas con esos filtros", "Prueba otra palabra clave o cambia el estado.");
      results.querySelectorAll("[data-topic]").forEach((row) => {
        const open = () => openTopicDialog(topics.find((t) => t.id === Number(row.dataset.topic)), load);
        row.addEventListener("click", open);
        row.addEventListener("keydown", (e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), open()));
      });
    } catch (error) {
      results.innerHTML = `<div class="alert alert--error">${escapeHtml(error.message)}</div>`;
    }
  };

  form.addEventListener("input", debounce(load, 300));
  form.addEventListener("submit", (e) => e.preventDefault());
  load();
}

function topicRowHtml(topic) {
  const seats = `${topic.accepted_count}/${topic.max_students} cupos`;
  return `
    <article class="topic-row" data-topic="${topic.id}" tabindex="0" aria-label="${escapeHtml(topic.title)}">
      <div>
        <h3>${escapeHtml(topic.title)}</h3>
        <p>${escapeHtml(topic.description)}</p>
        <div class="meta">
          <span>${escapeHtml(topic.professor_name)}</span>
          <span class="tag">${escapeHtml(topic.research_line)}</span>
          <span>${formatDate(topic.created_at)}</span>
        </div>
      </div>
      <div class="topic-row__side">${badge(topic.status)}<span class="mono">${seats}</span></div>
    </article>`;
}

function openTopicDialog(topic, onChange) {
  const isStudent = state.user.role === "student";
  const canApply = isStudent && topic.status === "available";
  const keywords = topic.keywords
    .split(",").map((k) => k.trim()).filter(Boolean)
    .map((k) => `<span class="tag">${escapeHtml(k)}</span>`).join(" ");

  dialogBody.innerHTML = `
    <div class="dialog__head">
      <div><p class="eyebrow">${escapeHtml(topic.research_line)}</p><h2 id="dialog-title">${escapeHtml(topic.title)}</h2></div>
      <button class="btn btn--ghost" data-close aria-label="Cerrar">✕</button>
    </div>
    <div class="meta" style="margin-top:0">${badge(topic.status)}
      <span>Asesor: <strong>${escapeHtml(topic.professor_name)}</strong></span>
      <span class="mono">${topic.accepted_count}/${topic.max_students} cupos · ${topic.pending_count} pendientes</span></div>
    <p>${escapeHtml(topic.description)}</p>
    ${keywords ? `<div class="meta" style="margin-top:0">${keywords}</div>` : ""}
    ${canApply ? `
      <form class="form" id="apply-form">
        <div class="field"><label for="motivation">¿Por qué quieres este tema?</label>
          <textarea class="textarea" id="motivation" name="motivation" minlength="20" required
            placeholder="Cuéntale al profesor tu interés, experiencia previa y disponibilidad."></textarea>
          <span class="hint">Mínimo 20 caracteres. Puedes tener hasta 3 postulaciones pendientes.</span></div>
        <div id="apply-error"></div>
        <div class="form-actions"><button class="btn btn--primary" type="submit">Postularme →</button></div>
      </form>`
      : isStudent ? `<div class="alert alert--info">Este tema no recibe postulaciones porque está ${STATUS_LABELS[topic.status].toLowerCase()}.</div>` : ""}`;

  dialogBody.querySelector("[data-close]").addEventListener("click", () => dialog.close());
  const form = dialogBody.querySelector("#apply-form");
  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await api("/api/applications", { method: "POST", body: { topic_id: topic.id, motivation: form.motivation.value } });
      dialog.close();
      showToast("Postulación enviada. El profesor la revisará pronto.");
      onChange?.();
    } catch (error) {
      dialogBody.querySelector("#apply-error").innerHTML = `<div class="alert alert--error">${escapeHtml(error.message)}</div>`;
    }
  });
  dialog.showModal();
}

/* ---------- Similarity (duplicate) checker ---------- */

function similarityPanelHtml(matches, { checking = false } = {}) {
  if (checking) return `<div class="similarity"><div class="similarity__head">Comparando con el banco…</div></div>`;
  if (!matches) return "";
  if (!matches.length) {
    return `<div class="similarity similarity--ok"><div class="similarity__head"><span>✓ No encontramos temas similares</span></div>
      <p class="muted" style="font-size:14px">Tu idea parece original frente a los temas activos del banco.</p></div>`;
  }
  const hasDuplicate = matches.some((m) => m.is_duplicate);
  return `
    <div class="similarity ${hasDuplicate ? "similarity--block" : "similarity--warn"}">
      <div class="similarity__head">
        <span>${hasDuplicate ? "⚠ Hay un tema prácticamente igual" : "Hay temas parecidos"}</span>
        <span class="muted mono">${matches.length} coincidencia(s)</span>
      </div>
      ${matches.map((m) => `
        <div class="match ${m.is_duplicate ? "match--dup" : ""}">
          <div><strong>${escapeHtml(m.title)}</strong><div class="meta" style="margin-top:4px">${badge(m.status)}<span>${escapeHtml(m.professor_name)}</span></div></div>
          <div class="match__score"><span>${Math.round(m.score * 100)}% similar</span>
            <div class="bar__track"><div class="bar__fill" style="width:${m.score * 100}%"></div></div></div>
        </div>`).join("")}
    </div>`;
}

async function viewSimilarityChecker(view) {
  view.innerHTML = `
    <div class="page-header"><div>
      <p class="eyebrow">Antes de proponer</p>
      <h1 class="page-title">¿Tu idea ya existe?</h1>
      <p class="page-lead">Escribe tu idea de proyecto. La comparamos con todos los temas activos del banco (disponibles y asignados) usando similitud de texto.</p>
    </div></div>
    <div class="grid-2">
      <form class="form card" id="check-form">
        <div class="field"><label for="title">Título tentativo</label>
          <input class="input" id="title" name="title" required placeholder="Ej.: App móvil para trazabilidad del café"></div>
        <div class="field"><label for="description">Descripción breve</label>
          <textarea class="textarea" id="description" name="description" placeholder="¿Qué problema resuelve y cómo?"></textarea></div>
        <div class="field"><label for="keywords">Palabras clave</label>
          <input class="input" id="keywords" name="keywords" placeholder="Separadas por comas"></div>
        <div class="form-actions"><button class="btn btn--primary" type="submit">Comparar →</button></div>
      </form>
      <div id="similarity-result">${emptyState("Sin comparar todavía", "El resultado aparecerá aquí.")}</div>
    </div>`;

  const form = view.querySelector("#check-form");
  const result = view.querySelector("#similarity-result");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (form.title.value.trim().length < 3) return showToast("Escribe al menos un título tentativo.", true);
    result.innerHTML = similarityPanelHtml(null, { checking: true });
    try {
      const matches = await api("/api/topics/similarity", { method: "POST", body: formToObject(form) });
      result.innerHTML = similarityPanelHtml(matches);
    } catch (error) {
      result.innerHTML = `<div class="alert alert--error">${escapeHtml(error.message)}</div>`;
    }
  });
}

/* ---------- Student: my applications ---------- */

async function viewMyApplications(view) {
  view.innerHTML = `
    <div class="page-header"><div>
      <p class="eyebrow">Seguimiento</p><h1 class="page-title">Mis postulaciones</h1>
      <p class="page-lead">Cuando un profesor te acepta, tus demás postulaciones pendientes se retiran automáticamente.</p>
    </div></div>
    <div id="list">${skeletons()}</div>`;
  const list = view.querySelector("#list");

  const load = async () => {
    const applications = await api("/api/applications/mine");
    if (!applications.length) {
      list.innerHTML = emptyState("Aún no te has postulado", "Explora el banco y elige un tema disponible.", '<a class="btn btn--primary" href="#/temas">Explorar temas →</a>');
      return;
    }
    list.innerHTML = `<div class="app-list">${applications.map((a) => `
      <article class="app-card">
        <div class="app-card__head"><h3>${escapeHtml(a.topic_title)}</h3>${badge(a.status)}</div>
        <p class="quote">${escapeHtml(a.motivation)}</p>
        ${a.feedback ? `<div class="feedback"><strong>Respuesta:</strong> ${escapeHtml(a.feedback)}</div>` : ""}
        <div class="meta" style="margin-top:0"><span>Enviada ${formatDate(a.created_at)}</span>
          ${a.reviewed_at ? `<span>Revisada ${formatDate(a.reviewed_at)}</span>` : ""}</div>
        ${a.status === "pending" ? `<div><button class="btn btn--danger btn--sm" data-withdraw="${a.id}">Retirar postulación</button></div>` : ""}
      </article>`).join("")}</div>`;
    list.querySelectorAll("[data-withdraw]").forEach((button) =>
      button.addEventListener("click", async () => {
        if (!confirm("¿Retirar esta postulación?")) return;
        try {
          await api(`/api/applications/${button.dataset.withdraw}/withdraw`, { method: "POST" });
          showToast("Postulación retirada.");
          load();
        } catch (error) { showToast(error.message, true); }
      })
    );
  };
  await load();
}

/* ---------- Professor: my topics & publish ---------- */

async function viewMyTopics(view) {
  view.innerHTML = `
    <div class="page-header">
      <div><p class="eyebrow">Profesor</p><h1 class="page-title">Mis temas</h1>
        <p class="page-lead">Temas que has publicado en el banco y su estado actual.</p></div>
      <a class="btn btn--primary" href="#/publicar">Publicar tema →</a>
    </div>
    <div id="list">${skeletons()}</div>`;
  const list = view.querySelector("#list");

  const load = async () => {
    const topics = await api("/api/topics/mine");
    if (!topics.length) {
      list.innerHTML = emptyState("No has publicado temas", "Publica tu primer tema para que los estudiantes puedan postularse.", '<a class="btn btn--primary" href="#/publicar">Publicar tema →</a>');
      return;
    }
    list.innerHTML = `<div class="table-wrap"><table>
      <thead><tr><th>Tema</th><th>Línea</th><th>Estado</th><th>Cupos</th><th>Pendientes</th><th><span class="visually-hidden">Acciones</span></th></tr></thead>
      <tbody>${topics.map((t) => `
        <tr>
          <td><strong>${escapeHtml(t.title)}</strong><div class="muted" style="font-size:13px">${formatDate(t.created_at)}</div></td>
          <td>${escapeHtml(t.research_line)}</td>
          <td>${badge(t.status)}</td>
          <td class="mono">${t.accepted_count}/${t.max_students}</td>
          <td class="mono">${t.pending_count}</td>
          <td>${t.status === "available" && t.accepted_count === 0
            ? `<button class="btn btn--ghost btn--sm" data-close-topic="${t.id}">Cerrar</button>`
            : t.status === "closed" ? `<button class="btn btn--ghost btn--sm" data-reopen="${t.id}">Reabrir</button>` : ""}</td>
        </tr>`).join("")}</tbody></table></div>`;

    list.querySelectorAll("[data-close-topic]").forEach((b) => b.addEventListener("click", async () => {
      if (!confirm("Al cerrar el tema se rechazan sus postulaciones pendientes. ¿Continuar?")) return;
      try { await api(`/api/topics/${b.dataset.closeTopic}/close`, { method: "POST" }); showToast("Tema cerrado."); load(); }
      catch (error) { showToast(error.message, true); }
    }));
    list.querySelectorAll("[data-reopen]").forEach((b) => b.addEventListener("click", async () => {
      try { await api(`/api/topics/${b.dataset.reopen}/reopen`, { method: "POST" }); showToast("Tema reabierto."); load(); }
      catch (error) { showToast(error.message, true); }
    }));
  };
  await load();
}

async function viewPublishTopic(view) {
  const filters = await loadFilters();
  view.innerHTML = `
    <div class="page-header"><div>
      <p class="eyebrow">Nuevo tema</p><h1 class="page-title">Publicar un tema</h1>
      <p class="page-lead">Mientras escribes, comparamos tu tema con el banco. Si es prácticamente igual a uno existente, no se podrá publicar.</p>
    </div></div>
    <div class="grid-2" style="align-items:start">
      <form class="form card" id="topic-form">
        <div class="field"><label for="title">Título</label>
          <input class="input" id="title" name="title" required minlength="10" maxlength="200"></div>
        <div class="field"><label for="description">Descripción</label>
          <textarea class="textarea" id="description" name="description" required minlength="30"
            placeholder="Problema, objetivo y alcance esperado."></textarea></div>
        <div class="form-row">
          <div class="field"><label for="research_line">Línea de investigación</label>
            <input class="input" id="research_line" name="research_line" list="lines" required>
            <datalist id="lines">${filters.research_lines.map((l) => `<option value="${escapeHtml(l)}">`).join("")}</datalist></div>
          <div class="field"><label for="max_students">Cupos</label>
            <select class="select" id="max_students" name="max_students">
              <option value="1">1 estudiante</option><option value="2">2 estudiantes</option><option value="3">3 estudiantes</option>
            </select></div>
        </div>
        <div class="field"><label for="program">Programa</label>
          <input class="input" id="program" name="program" value="${escapeHtml(state.user.program)}" required></div>
        <div class="field"><label for="keywords">Palabras clave</label>
          <input class="input" id="keywords" name="keywords" placeholder="Separadas por comas"></div>
        <div id="form-error"></div>
        <div class="form-actions">
          <button class="btn btn--primary" type="submit">Publicar tema →</button>
          <a class="btn btn--secondary" href="#/mis-temas">Cancelar</a>
        </div>
      </form>
      <aside id="live-similarity" aria-live="polite">
        ${emptyState("Verificación de duplicados", "Escribe un título y una descripción para comparar con el banco.")}
      </aside>
    </div>`;

  const form = view.querySelector("#topic-form");
  const panel = view.querySelector("#live-similarity");

  const check = debounce(async () => {
    const { title, description, keywords } = formToObject(form);
    if (title.trim().length < 5) return;
    panel.innerHTML = similarityPanelHtml(null, { checking: true });
    try {
      const matches = await api("/api/topics/similarity", { method: "POST", body: { title, description, keywords } });
      panel.innerHTML = similarityPanelHtml(matches);
    } catch { /* live check is best-effort */ }
  }, 600);
  ["title", "description", "keywords"].forEach((name) => form[name].addEventListener("input", check));

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = formToObject(form);
    payload.max_students = Number(payload.max_students);
    const errorBox = view.querySelector("#form-error");
    errorBox.innerHTML = "";
    try {
      const result = await api("/api/topics", { method: "POST", body: payload });
      state.filters = null;
      showToast(result.similar_topics.length
        ? "Tema publicado. Ten en cuenta que hay temas parecidos en el banco."
        : "Tema publicado en el banco.");
      location.hash = "#/mis-temas";
    } catch (error) {
      errorBox.innerHTML = `<div class="alert alert--error">${escapeHtml(error.message)}</div>`;
      if (error.detail?.similar_topics) panel.innerHTML = similarityPanelHtml(error.detail.similar_topics);
    }
  });
}

/* ---------- Professor/Admin: received applications ---------- */

async function viewReceivedApplications(view) {
  view.innerHTML = `
    <div class="page-header">
      <div><p class="eyebrow">${state.user.role === "admin" ? "Todo el programa" : "Tus temas"}</p>
        <h1 class="page-title">Postulaciones</h1>
        <p class="page-lead">Al aceptar, el tema se marca como asignado cuando se llenan los cupos y las demás postulaciones se cierran solas.</p></div>
      <div class="field" style="min-width:200px"><label class="visually-hidden" for="status-filter">Estado</label>
        <select class="select" id="status-filter">
          <option value="pending">Pendientes</option><option value="accepted">Aceptadas</option>
          <option value="rejected">Rechazadas</option><option value="">Todas</option>
        </select></div>
    </div>
    <div id="list">${skeletons()}</div>`;
  const list = view.querySelector("#list");
  const statusFilter = view.querySelector("#status-filter");

  const load = async () => {
    list.innerHTML = skeletons();
    const query = statusFilter.value ? `?status=${statusFilter.value}` : "";
    const applications = await api(`/api/applications/received${query}`);
    if (!applications.length) {
      list.innerHTML = emptyState("No hay postulaciones aquí", "Cuando un estudiante se postule a tus temas aparecerá en esta lista.");
      return;
    }
    list.innerHTML = `<div class="app-list">${applications.map((a) => `
      <article class="app-card">
        <div class="app-card__head">
          <div><h3>${escapeHtml(a.student_name)}</h3><div class="muted mono">${escapeHtml(a.student_email)}</div></div>
          ${badge(a.status)}
        </div>
        <div class="muted" style="font-size:14px">Tema: <strong style="color:var(--text)">${escapeHtml(a.topic_title)}</strong></div>
        <p class="quote">${escapeHtml(a.motivation)}</p>
        ${a.feedback ? `<div class="feedback"><strong>Retroalimentación:</strong> ${escapeHtml(a.feedback)}</div>` : ""}
        ${a.status === "pending" ? `
          <form class="form" data-review="${a.id}" style="gap:12px">
            <div class="field"><label for="fb-${a.id}">Retroalimentación para el estudiante (opcional)</label>
              <textarea class="textarea" id="fb-${a.id}" name="feedback" style="min-height:70px"></textarea></div>
            <div class="form-actions">
              <button class="btn btn--primary btn--sm" type="submit" value="accepted">Aceptar</button>
              <button class="btn btn--danger btn--sm" type="submit" value="rejected">Rechazar</button>
            </div>
          </form>` : ""}
        <div class="meta" style="margin-top:0"><span>Enviada ${formatDate(a.created_at)}</span></div>
      </article>`).join("")}</div>`;

    list.querySelectorAll("[data-review]").forEach((form) =>
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const decision = event.submitter.value;
        try {
          await api(`/api/applications/${form.dataset.review}/review`, {
            method: "POST", body: { decision, feedback: form.feedback.value },
          });
          showToast(decision === "accepted" ? "Estudiante aceptado. El tema quedó registrado." : "Postulación rechazada.");
          load();
        } catch (error) { showToast(error.message, true); }
      })
    );
  };
  statusFilter.addEventListener("change", load);
  await load();
}

/* ---------- Admin: users ---------- */

async function viewUsers(view) {
  view.innerHTML = `
    <div class="page-header"><div>
      <p class="eyebrow">Administración</p><h1 class="page-title">Usuarios</h1>
      <p class="page-lead">Los estudiantes se registran solos; las cuentas de profesor las crea la coordinación.</p>
    </div></div>
    <div class="grid-2" style="align-items:start">
      <div id="users">${skeletons()}</div>
      <form class="form card" id="professor-form">
        <h3>Crear cuenta de profesor</h3>
        <div class="field"><label for="p-name">Nombre completo</label><input class="input" id="p-name" name="full_name" required></div>
        <div class="field"><label for="p-email">Correo</label><input class="input" id="p-email" name="email" type="email" required></div>
        <div class="field"><label for="p-program">Programa</label><input class="input" id="p-program" name="program" value="Ingeniería de Software"></div>
        <div class="field"><label for="p-pass">Contraseña temporal</label><input class="input" id="p-pass" name="password" type="text" minlength="6" required></div>
        <div id="p-error"></div>
        <div class="form-actions"><button class="btn btn--primary" type="submit">Crear profesor →</button></div>
      </form>
    </div>`;

  const usersBox = view.querySelector("#users");
  const load = async () => {
    const users = await api("/api/admin/users");
    usersBox.innerHTML = `<div class="table-wrap"><table>
      <thead><tr><th>Nombre</th><th>Correo</th><th>Rol</th></tr></thead>
      <tbody>${users.map((u) => `<tr><td>${escapeHtml(u.full_name)}</td><td class="mono">${escapeHtml(u.email)}</td><td>${ROLE_LABELS[u.role]}</td></tr>`).join("")}</tbody>
    </table></div>`;
  };

  const form = view.querySelector("#professor-form");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await api("/api/admin/professors", { method: "POST", body: formToObject(form) });
      form.reset();
      view.querySelector("#p-error").innerHTML = "";
      showToast("Profesor creado.");
      load();
    } catch (error) {
      view.querySelector("#p-error").innerHTML = `<div class="alert alert--error">${escapeHtml(error.message)}</div>`;
    }
  });
  await load();
}

/* ---------- Milestones (phase 2 roadmap) ---------- */

async function viewMilestonesRoadmap(view) {
  view.innerHTML = `
    <div class="page-header"><div>
      <p class="eyebrow">Fase 2 · En construcción</p>
      <h1 class="page-title">Seguimiento de hitos con el asesor</h1>
      <p class="page-lead">El modelo de datos de hitos ya existe. Esta sección se habilitará en la segunda mitad del proyecto.</p>
    </div></div>
    <div class="roadmap">
      <div class="card"><h3>Plan de hitos</h3><p class="muted">El asesor define entregas con fecha (anteproyecto, avance 1, avance 2, documento final).</p></div>
      <div class="card"><h3>Entregas y revisión</h3><p class="muted">El estudiante sube avances; el asesor aprueba o pide ajustes con comentarios.</p></div>
      <div class="card"><h3>Alertas y reportes</h3><p class="muted">Avisos de hitos vencidos y reporte de avance por estudiante para la coordinación.</p></div>
    </div>`;
}

/* ---------- Boot ---------- */

window.addEventListener("hashchange", router);
dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });

// Free hosting plans put the API to sleep when idle; the first request can take ~1 minute.
async function waitForServer(maxAttempts = 12) {
  const slowNotice = setTimeout(() => {
    appRoot.innerHTML = `
      <div class="container" style="min-height:100vh;display:grid;place-items:center;text-align:center">
        <div><p class="eyebrow">Un momento</p>
          <h1 class="page-title">Despertando el servidor…</h1>
          <p class="page-lead" style="margin-inline:auto">El plan gratuito apaga el servidor cuando no se usa. Puede tardar hasta un minuto.</p></div>
      </div>`;
  }, 1500);
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      const response = await fetch("/api/health", { cache: "no-store" });
      if (response.ok) break;
    } catch { /* network error while the server boots */ }
    await new Promise((resolve) => setTimeout(resolve, 5000));
  }
  clearTimeout(slowNotice);
}

(async function boot() {
  await waitForServer();
  try {
    state.user = await api("/api/auth/me");
  } catch {
    state.user = null;
  }
  router();
})();
