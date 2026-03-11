# BIND 
### Plataforma modular de gestión de eventos

> *"La productividad no se trata de hacer más cosas, sino de hacer las cosas correctas de manera eficiente."*

BIND es un sistema web diseñado para planear, gestionar y dar seguimiento a eventos de manera eficiente. Su arquitectura modular permite activar únicamente los componentes necesarios, adaptándose a cualquier tipo de evento: académico, corporativo, social o creativo.

---

## Índice

- [Tecnologías](#tecnologías)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Instalación](#instalación)
- [Módulos del sistema](#módulos-del-sistema)
- [Equipo](#equipo)

---

## Tecnologías

| Capa | Tecnología |
|---|---|
| Backend | Python 3.x + Django 6.0 |
| Frontend | HTML5 + TailwindCSS (CDN) + HTMX |
| Base de datos | SQLite3 (desarrollo) |
| Control de versiones | Git + GitHub |
| Idioma / Zona horaria | Español Colombia (`es-co` / `America/Bogota`) |

---

## Estructura del proyecto

```
BindV1/
│
├── BindV1/                  # Configuración principal del proyecto
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── accounts/                # Módulo de autenticación y perfiles
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   └── migrations/
│
├── events/                  # Módulo central de eventos y plantillas
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   └── migrations/
│
├── modules/                 # Módulos funcionales (tareas, asistentes, archivos)
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   └── migrations/
│
├── templates/               # Templates HTML (Django Template Language)
│   ├── accounts/
│   ├── events/
│   └── registration/
│
├── static/                  # Archivos estáticos (CSS, JS, imágenes)
│
├── manage.py
└── db.sqlite3               # No incluido en el repo (.gitignore)
```

---

## Instalación

### Requisitos previos
- Python 3.10 o superior
- pip
- Git

### Pasos

**1. Clonar el repositorio**
```bash
git clone https://github.com/tu-usuario/BindV1.git
cd BindV1
```

**2. Crear y activar el entorno virtual**

En Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

En Mac / Linux:
```bash
python -m venv venv
source venv/bin/activate
```

**3. Instalar dependencias**
```bash
pip install django
```

**4. Aplicar migraciones (crea la base de datos vacía)**
```bash
python manage.py migrate
```

**5. Crear superusuario (opcional, para acceder al admin)**
```bash
python manage.py createsuperuser
```

**6. Correr el servidor**
```bash
python manage.py runserver
```

**7. Abrir en el navegador**
```
http://127.0.0.1:8000/
```

---

## Módulos del sistema

### Núcleo MVP

| Módulo | Descripción | Estado |
|---|---|---|
| **Events** | Creación y gestión de eventos | Activo |
| **Tasks** | Tareas y checklists por evento | Activo |
| **Attendees** | Control de asistentes e invitados | Activo |
| **Files** | Gestión de archivos por evento | Activo |
| **Templates** | Plantillas reutilizables de eventos | Activo |
| **Accounts** | Autenticación, perfiles y roles | Activo |

### Módulos futuros (roadmap)

| Módulo | Derivado de | Estado |
|---|---|---|
| Finances | Events + Tasks | Planeado |
| Reports | Finances + Tasks | Planeado |
| Notifications | Events | Planeado |
| Surveys | Events | Planeado |
| Calendar | Events | Planeado |
| ApiKeys | Finances + Notifications | Planeado |

---

## Equipo

Proyecto desarrollado por estudiantes de **COSFA 11-B** como proyecto productivo académico.

| Nombre | Rol |
|---|---|
| **Sofía Avendaño** | Gerente — Diseñadora conceptual |
| **Alejandra Sánchez** | Diseñadora UX/UI |
| **Samuel Giraldo García** | Técnico — Analista de datos (Backend / BD) |
| **Juan Felipe Perea** | Programador — Gestor técnico (Git) |

**Tutora:** Luisa Fernanda Varela Restrepo

---

<p align="center">
  <sub>© 2025 BIND Project — COSFA 11-B. Todos los derechos reservados.</sub>
</p>