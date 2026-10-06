# Banco de Proyectos de Grado — Avance 50 %

Repositorio web donde los **profesores publican temas de grado**, los **estudiantes se postulan** y el sistema **impide que un mismo tema se tome dos veces**. Esta entrega cubre el núcleo funcional; el seguimiento de hitos con el asesor está planeado para la segunda mitad.

**Tecnología:** Python 3.10+ · FastAPI · SQLAlchemy · SQLite (local) / PostgreSQL (producción) · HTML/CSS/JavaScript (sin frameworks)

**Despliegue:** API y base de datos en **Render**, interfaz web en **Vercel** (ver sección 7).

---

## 1. Cómo ejecutarlo

```bash
# 1. Entrar a la carpeta del proyecto
cd banco-proyectos-grado

# 2. (Opcional) crear un entorno virtual
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Levantar el servidor
uvicorn app.main:app --reload
```

Abrir **http://localhost:8000** en el navegador.

- La documentación interactiva de la API (Swagger) queda en **http://localhost:8000/docs**.
- La primera vez se crea `thesis_bank.db` con datos de demostración. Para reiniciar los datos, borra ese archivo y vuelve a iniciar el servidor.

> **Anaconda:** abre *Anaconda Prompt*, ejecuta `pip install -r requirements.txt` y luego `uvicorn app.main:app --reload` desde la carpeta del proyecto.

### Usuarios de prueba

Contraseña para todos: **`demo1234`** (también hay botones de acceso rápido en la pantalla de inicio de sesión).

| Rol | Correo |
|---|---|
| Administrador (coordinación) | `admin@demo.edu.co` |
| Profesora | `laura.benavides@demo.edu.co` |
| Profesor | `andres.munoz@demo.edu.co` |
| Estudiante | `camila.ortiz@demo.edu.co` |
| Estudiante (ya tiene tema asignado) | `juan.erazo@demo.edu.co` |
| Estudiante (con postulación pendiente) | `valentina.chamorro@demo.edu.co` |

### Ejecutar las pruebas automáticas

```bash
pytest -q
```

Son 10 pruebas de punta a punta que validan las reglas de negocio (ver sección 4).

---

## 2. Qué incluye este 50 %

| Módulo | Estado |
|---|---|
| Autenticación con roles (estudiante, profesor, administrador) | ✅ |
| Registro de estudiantes / creación de profesores por la coordinación | ✅ |
| Publicar, editar, cerrar y reabrir temas (profesor) | ✅ |
| **Detección de temas duplicados o similares** (TF-IDF + similitud coseno) | ✅ |
| Verificador "¿Tu idea ya existe?" para estudiantes | ✅ |
| Explorar temas con búsqueda y filtros por estado y línea | ✅ |
| Postulación a temas con motivación | ✅ |
| Revisión de postulaciones: aceptar / rechazar con retroalimentación | ✅ |
| Asignación automática del tema y cierre de postulaciones restantes | ✅ |
| Panel con indicadores y temas por línea de investigación | ✅ |
| Modelo de datos de **hitos** (tabla `milestones`) | ✅ creado |
| Seguimiento de hitos con el asesor (pantallas y endpoints) | ⏳ Fase 2 |

### Pendiente para el otro 50 %

1. **Hitos de avance:** el asesor define entregas con fecha; el estudiante sube avances; el asesor aprueba o pide ajustes.
2. **Notificaciones** por correo cuando cambia el estado de una postulación o vence un hito.
3. **Reportes** para la coordinación (avance por estudiante, temas por profesor, tiempos de asignación) y exportación.
4. **Propuestas propias del estudiante:** que un estudiante proponga su tema y un profesor lo avale como asesor.
5. Adjuntar documentos (anteproyecto, avances) y despliegue en un servidor.

---

## 3. Arquitectura

```
banco-proyectos-grado/
├── app/
│   ├── main.py            # Crea la app, sesiones, rutas y archivos estáticos
│   ├── database.py        # Conexión SQLite (SQLAlchemy)
│   ├── models.py          # User, Topic, Application, Milestone
│   ├── schemas.py         # Validación de datos de entrada/salida (Pydantic)
│   ├── security.py        # Hash de contraseñas (PBKDF2) y control de roles
│   ├── similarity.py      # Motor de detección de duplicados
│   ├── serializers.py     # Conversión de modelos a respuestas JSON
│   ├── seed.py            # Datos de demostración
│   └── routers/
│       ├── auth.py          # /api/auth/*
│       ├── topics.py        # /api/topics/*
│       ├── applications.py  # /api/applications/*
│       └── admin.py         # /api/admin/*
├── frontend/              # Interfaz web (index.html, styles.css, app.js) + vercel.json
├── render.yaml            # Despliegue de la API y la base de datos en Render
├── tests/test_flows.py    # Pruebas automáticas
└── requirements.txt
```

### Modelo de datos

```
users (id, full_name, email, password_hash, role, program)
   │ 1
   ├──< topics (id, title, description, research_line, program, keywords,
   │            max_students, status, professor_id)
   │                │ 1
   └──< applications (id, topic_id, student_id, motivation, status,
                      feedback, reviewed_at)       UNIQUE(topic_id, student_id)
                        │ 1
                        └──< milestones (id, application_id, title, due_date,
                                         status, advisor_feedback)   ← Fase 2
```

Estados de un tema: `available` → `assigned` (cupos llenos) · `closed` (retirado por el profesor).
Estados de una postulación: `pending` → `accepted` | `rejected` | `withdrawn`.

---

## 4. Reglas de negocio implementadas

1. **No hay temas duplicados.** Al publicar o editar un tema se compara con todos los temas activos. Si la similitud es ≥ 75 % se bloquea la publicación; entre 35 % y 75 % se muestra una advertencia con los temas parecidos.
2. **No se puede postular a un tema asignado o cerrado.** Los temas asignados siguen visibles para que nadie proponga lo mismo.
3. **Un estudiante = un tema.** Cuando un profesor acepta a un estudiante, sus demás postulaciones pendientes se retiran automáticamente y ya no puede postularse a otros temas.
4. **Sin sobreasignación.** Cuando se llenan los cupos (1 a 3 por tema), el tema pasa a "asignado" y las postulaciones pendientes se rechazan con el mensaje "Cupos completos".
5. **Máximo 3 postulaciones pendientes** por estudiante, y una sola postulación por tema.
6. **Permisos por rol:** solo profesores/administración publican temas; solo el profesor dueño del tema revisa sus postulaciones; solo la coordinación crea cuentas de profesor.

### ¿Cómo funciona la detección de duplicados?

`app/similarity.py` convierte cada tema (título + palabras clave + descripción) en un vector **TF-IDF** después de normalizar el texto en español (minúsculas, sin tildes, sin palabras vacías y con una reducción simple de plurales). Luego calcula la **similitud coseno** entre la idea nueva y cada tema existente. Está hecho solo con la biblioteca estándar de Python, sin dependencias de machine learning.

---

## 5. Endpoints principales

| Método | Ruta | Quién |
|---|---|---|
| POST | `/api/auth/register` · `/login` · `/logout` | Todos |
| GET | `/api/topics?q=&status=&research_line=` | Autenticados |
| POST | `/api/topics/similarity` | Autenticados |
| POST / PUT | `/api/topics` · `/api/topics/{id}` | Profesor, admin |
| POST | `/api/topics/{id}/close` · `/reopen` | Profesor dueño |
| POST | `/api/applications` | Estudiante |
| GET | `/api/applications/mine` | Estudiante |
| POST | `/api/applications/{id}/withdraw` | Estudiante |
| GET | `/api/applications/received?status=` | Profesor, admin |
| POST | `/api/applications/{id}/review` | Profesor dueño, admin |
| GET | `/api/admin/stats` | Autenticados |
| GET / POST | `/api/admin/users` · `/api/admin/professors` | Admin |

---

## 6. Configuración opcional

| Variable | Uso | Valor por defecto |
|---|---|---|
| `SECRET_KEY` | Firma de la cookie de sesión (cambiar en producción) | `dev-only-change-me` |
| `DATABASE_URL` | Base de datos | `sqlite:///./thesis_bank.db` |
| `SEED_DEMO_DATA` | `0` para iniciar sin datos de demostración | `1` |
| `COOKIE_SECURE` | `1` en producción (cookie de sesión solo por HTTPS) | `0` |

---

## 7. Despliegue: API en Render + interfaz en Vercel

```
Navegador ──► Vercel (frontend/)  ──/api/*──►  Render (FastAPI)  ──►  Render PostgreSQL
              tu-app.vercel.app      proxy       ...onrender.com
```

Vercel sirve la interfaz y **reenvía todas las rutas `/api/*` a Render**. Así el navegador ve un solo dominio, la cookie de sesión funciona sin configurar CORS y la URL de Render queda oculta.

### Paso 1 — Subir el proyecto a GitHub

Crea un repositorio vacío en github.com (por ejemplo `banco-proyectos-grado`, sin README) y luego, desde la carpeta del proyecto:

```bash
git init
git add .
git commit -m "Banco de proyectos de grado - avance 50%"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/banco-proyectos-grado.git
git push -u origin main
```

### Paso 2 — API y base de datos en Render

1. Entra a dashboard.render.com e inicia sesión con GitHub.
2. **New → Blueprint** → elige el repositorio `banco-proyectos-grado`.
3. Render lee `render.yaml` y propone crear dos recursos: el servicio web `banco-proyectos-grado-api` y la base de datos `banco-proyectos-grado-db`. Pulsa **Apply / Deploy Blueprint**.
4. Espera a que el servicio quede en **Live** (unos 3–5 minutos).
5. Copia la URL del servicio (algo como `https://banco-proyectos-grado-api.onrender.com`) y verifica que responda: `https://…onrender.com/api/health` debe mostrar `{"status":"ok"}`.

> Si Render le asignó otra URL (por ejemplo con un sufijo `-x1y2`), abre `frontend/vercel.json`, reemplaza `https://banco-proyectos-grado-api.onrender.com` por tu URL en las tres líneas, y sube el cambio:
> ```bash
> git add frontend/vercel.json
> git commit -m "URL de la API en Render"
> git push
> ```

### Paso 3 — Interfaz en Vercel

1. Entra a vercel.com e inicia sesión con GitHub.
2. **Add New… → Project** → importa `banco-proyectos-grado`.
3. Configura:
   - **Root Directory:** `frontend` ← importante
   - **Framework Preset:** `Other`
   - Build Command / Output Directory: déjalos vacíos.
4. Pulsa **Deploy**. Al terminar tendrás una URL como `https://banco-proyectos-grado.vercel.app`.

### Paso 4 — Probar

Abre la URL de Vercel y entra con una cuenta de prueba (`demo1234`). La documentación de la API también queda disponible en `https://tu-app.vercel.app/docs`.

Cada `git push` a `main` vuelve a desplegar automáticamente en Render y en Vercel.

### Limitaciones del plan gratuito (tenlas en cuenta antes de sustentar)

- **El servidor se duerme** tras 15 minutos sin uso; la siguiente visita tarda cerca de 1 minuto. La interfaz muestra "Despertando el servidor…" mientras tanto. **Consejo:** abre la página unos minutos antes de presentar.
- **La base de datos gratuita de Render vence a los 30 días** de creada (con 14 días de gracia antes de borrarse). Si vence, crea una nueva base desde el Blueprint (o pasa a un plan pago); los datos de demostración se cargan solos cuando la base está vacía.

### Opción rápida: todo en Render

El servicio de Render también sirve la interfaz (`frontend/`), así que la URL `https://…onrender.com` ya funciona como aplicación completa aunque no uses Vercel.
