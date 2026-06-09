# BIND
### Plataforma modular de gestión de eventos

> *"La productividad no se trata de hacer más cosas, sino de hacer las cosas correctas de manera eficiente."*

BIND es un sistema web diseñado para planear, gestionar y dar seguimiento a eventos de manera eficiente. Su arquitectura modular permite activar únicamente los componentes necesarios, adaptándose a cualquier tipo de evento: académico, corporativo, social o creativo.

---

## Links del proyecto

| Recurso | URL |
|---|---|
| Repositorio GitHub | https://github.com/JuanFelipePerea/Bind |
| Aplicación en producción | https://bind-gexm.onrender.com |

---

## Demo

**URL en producción:** https://bind-gexm.onrender.com

### Cuentas de demostración

| Cuenta | Correo | Contraseña | Rol en evento DEMO |
|---|---|---|---|
| Organizador | *(cuenta principal del equipo)* | — | Owner |
| Editor | SofiaCastillo@gmail.com | `Prueba#0002` | Editor |
| Observador | MartinGonzalez@gmail.com | `Prueba#0007` | Observador |

> El rol **Editor** puede crear y modificar tareas, checklist, presupuesto y más.  
> El rol **Observador** tiene acceso de solo lectura con indicadores visuales diferenciados.

---

## Tecnologías

| Capa | Tecnología |
|---|---|
| Backend | Python 3.13 + Django 6.0.1 |
| Frontend | HTML5 + Tailwind CSS + Flatpickr + FullCalendar |
| Base de datos | PostgreSQL — [Neon](https://neon.tech) (cloud serverless) |
| Almacenamiento | [Cloudinary](https://cloudinary.com) (archivos e imágenes) |
| Despliegue | [Render.com](https://render.com) (autodeploy desde rama `main`) |
| IA | Google Gemini + Groq (asistente Bynix) |
| Autenticación | Django Allauth + Google OAuth 2.0 |
| Email transaccional | Brevo (SMTP) |
| Idioma / Zona horaria | Español Colombia (`es-co` / `America/Bogota`) |
| Control de versiones | Git + GitHub |

---

## Estructura del proyecto

```
Bind/
│
├── bind/                        # Configuración principal del proyecto
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── accounts/                    # Autenticación, perfiles y 2FA
│   ├── models.py
│   ├── views.py
│   └── urls.py
│
├── events/                      # Eventos, plantillas y colaboradores
│   ├── models.py                # Event, EventTemplate, TemplateTask, Momento, …
│   ├── views.py
│   ├── views_collaborator.py
│   └── management/commands/     # seed_demo, seed_templates, fix_encoding, …
│
├── modules/                     # Módulos funcionales por evento
│   ├── models.py                # Task, Attendee, Checklist, Budget, File, …
│   └── views.py
│
├── templates/                   # Templates HTML (Django Template Language)
│   ├── base.html
│   ├── events/
│   └── modules/
│
├── static/                      # CSS compilado, JS, imágenes
├── requirements.txt
└── manage.py
```

---

## Instalación local

### Requisitos previos
- Python 3.11 o superior
- pip

### Pasos

**1. Clonar el repositorio**

```bash
git clone https://github.com/JuanFelipePerea/Bind.git
cd Bind
```

**2. Crear y activar entorno virtual**

Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

Mac / Linux:
```bash
python -m venv venv
source venv/bin/activate
```

**3. Instalar dependencias**
```bash
pip install -r requirements.txt
```

**4. Configurar variables de entorno**

Crear un archivo `.env` en la raíz con las variables necesarias (anexado en la raiz).

**5. Correr el servidor**
```bash
python manage.py runserver
```

**6. Abrir en el navegador**
```
http://127.0.0.1:8000/
```

---

## Módulos del sistema

| Módulo | Descripción |
|---|---|
| **Eventos** | Creación, edición y seguimiento de eventos con plantillas reutilizables |
| **Tareas** | Gestión de tareas por evento con prioridades, estados y orden sugerido por IA |
| **Asistentes** | Control de invitados, confirmaciones y preferencias dietéticas/accesibilidad |
| **Checklist** | Listas de verificación por evento con progreso en tiempo real |
| **Presupuesto** | Control financiero con ítems de gasto/ingreso, moneda y porcentaje de ejecución |
| **Archivos** | Subida y gestión de documentos adjuntos al evento (Cloudinary) |
| **Momentos** | Cronograma visual de hitos del evento integrado con FullCalendar |
| **Bynix** | Asistente IA conversacional por evento (Gemini + Groq) |
| **Colaboradores** | Invitación de usuarios con roles Editor / Observador y modo visual diferenciado |
| **Plantillas** | Plantillas de eventos con tareas, checklist y presupuesto predefinidos |
| **Alertas** | Sistema de alertas automáticas por retrasos, presupuesto y actividad |
| **Reportes** | Exportación de reportes por evento |

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
