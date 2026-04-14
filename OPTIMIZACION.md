# 🎯 Plan de Optimización - OmniBook Studio

> **Fecha de creación:** 13 de abril de 2026
> **Versión actual:** v1.0
> **Objetivo:** Hoja de ruta para potenciar el proyecto antes de publicación en GitHub

---

## 📊 Matriz de Priorización

| Prioridad | Criterio |
|-----------|----------|
| 🔴 **Alta** | Alto impacto + Bajo/Medio esfuerzo → Hacer primero |
| 🟡 **Media** | Medio impacto + Medio esfuerzo → Hacer segundo |
| 🟢 **Baja** | Alto impacto + Alto esfuerzo → Planificar a futuro |

---

## 📋 Lista de Mejoras (Ordenadas por Prioridad)

### 🔴 PRIORIDAD ALTA — Esta Semana

| # | Mejora | Categoría | Impacto | Esfuerzo | Estado | Notas |
|---|--------|-----------|---------|----------|--------|-------|
| 1 | **Screenshot/GIF en el README** | Documentación | ⭐⭐⭐⭐⭐ | ⭐ | ⬜ | Captura de la app o GIF del flujo completo. Aumenta engagement 40%+ |
| 2 | **Más ejemplos de texto en `input/`** | Contenido | ⭐⭐⭐⭐⭐ | ⭐ | ⬜ | 3-5 textos variados: cuento, poema, artículo técnico, diálogo |
| 3 | **`.env.example` con `HF_TOKEN`** | DevEx | ⭐⭐⭐⭐ | ⭐ | ⬜ | Documenta token de HuggingFace para descargas más rápidas |
| 4 | **Badges profesionales en README** | Presentación | ⭐⭐⭐⭐ | ⭐ | ⬜ | License, Python, PyTorch, Stars, Issues, Downloads |
| 5 | **Makefile / justfile** | DevEx | ⭐⭐⭐ | ⭐ | ⬜ | Comandos: `make run`, `make install`, `make lint` |

### 🟡 PRIORIDAD MEDIA — Semana 2-3

| # | Mejora | Categoría | Impacto | Esfuerzo | Estado | Notas |
|---|--------|-----------|---------|----------|--------|-------|
| 6 | **Tests unitarios con `pytest`** | Calidad | ⭐⭐⭐⭐ | ⭐⭐ | ⬜ | Pruebas de funciones auxiliares, parsing de texto, DB de voces |
| 7 | **Dockerfile + docker-compose** | Infraestructura | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⬜ | Un solo comando para ejecutar en cualquier sistema sin instalar nada |
| 8 | **CHANGELOG.md** | Documentación | ⭐⭐⭐⭐ | ⭐ | ⬜ | Historial de versiones y cambios. Esencial para proyectos serios |
| 9 | **Templates de Issues y PRs** | Comunidad | ⭐⭐⭐⭐ | ⭐ | ⬜ | `.github/ISSUE_TEMPLATE/` y `pull_request_template.md` |
| 10 | **API REST con FastAPI** | Backend | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⬜ | Endpoint `/generate` para integración externa (apps, bots, web) |

### 🟢 PRIORIDAD BAJA — Mes 1-3

| # | Mejora | Categoría | Impacto | Esfuerzo | Estado | Notas |
|---|--------|-----------|---------|----------|--------|-------|
| 11 | **Exportación M4B con capítulos** | Feature | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⬜ | Formato audiolibro profesional con marcadores. Diferenciador clave |
| 12 | **Cola de trabajos (Redis + Celery)** | Backend | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⬜ | Múltiples audiolibros en paralelo sin bloquear UI |
| 13 | **Fine-tuning personalizado** | ML | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⬜ | Docs para adaptar modelo a voces o estilos específicos |
| 14 | **Plataforma SaaS con Stripe** | Negocio | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⬜ | Monetización como servicio cloud. Modelo freemium |
| 15 | **Integración con Calibre/Sigil** | Feature | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⬜ | Generar audiolibros directamente desde EPUBs |

### 🛡️ CALIDAD DEL PROYECTO — Continuo

| # | Mejora | Categoría | Impacto | Esfuerzo | Estado | Notas |
|---|--------|-----------|---------|----------|--------|-------|
| 16 | **GitHub Actions CI/CD** | DevOps | ⭐⭐⭐⭐ | ⭐⭐ | ⬜ | Tests automáticos en cada PR. Garantiza estabilidad |
| 17 | **Linting (ruff, mypy)** | Calidad | ⭐⭐⭐ | ⭐ | ⬜ | Código limpio y sin errores de tipo |
| 18 | **Guía de Contribución** | Comunidad | ⭐⭐⭐⭐ | ⭐ | ⬜ | `CONTRIBUTING.md` — cómo hacer PRs, reportar bugs, añadir voces |
| 19 | **Licencias de terceros** | Legal | ⭐⭐⭐ | ⭐ | ⬜ | Lista de dependencias y sus licencias. Buenas prácticas open source |
| 20 | **Documentación en inglés** | Alcance | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⬜ | Traducir README y docs para audiencia global |

---

## 📅 Plan de Acción — Esta Semana

### Lunes (HOY)
- [ ] **#1 Screenshot/GIF** — Capturar la app en acción
- [ ] **#2 Ejemplos de texto** — Crear 3-5 archivos `.txt` en `input/`
- [ ] **#3 `.env.example`** — Crear template con `HF_TOKEN`

### Martes
- [ ] **#4 Badges** — Agregar badges profesionales al README
- [ ] **#5 Makefile** — Comandos básicos de desarrollo
- [ ] **#18 Guía de Contribución** — Escribir `CONTRIBUTING.md`

### Miércoles
- [ ] **#6 Tests unitarios** — Primeros tests con pytest
- [ ] **#8 CHANGELOG.md** — Historial de cambios
- [ ] **#17 Linting** — Configurar ruff + mypy

### Jueves
- [ ] **#9 Templates Issues/PRs** — GitHub templates
- [ ] **#16 GitHub Actions** — CI/CD básico
- [ ] Revisión general del proyecto

### Viernes
- [ ] **#7 Dockerfile** — Primer draft
- [ ] **#10 API REST** — Diseño de endpoints
- [ ] Publicación en GitHub

---

## 📈 Métricas de Éxito

| Métrica | Actual | Objetivo |
|---------|--------|----------|
| **Ejemplos en `input/`** | 1 archivo | 5 archivos |
| **Tests automatizados** | 0 | 10+ tests |
| **Badges en README** | 3 badges | 6+ badges |
| **Documentación en inglés** | Solo español | README bilingüe |
| **Docker** | No disponible | `docker compose up` funciona |
| **CI/CD** | No configurado | Tests en cada PR |

---

## 🔗 Recursos Útiles

| Recurso | URL |
|---------|-----|
| **Shields.io (badges)** | https://shields.io/ |
| **GitHub Actions** | https://github.com/features/actions |
| **Docker + CUDA** | https://hub.docker.com/r/nvidia/cuda |
| **FastAPI** | https://fastapi.tiangolo.com/ |
| **pytest** | https://docs.pytest.org/ |
| **ruff** | https://github.com/astral-sh/ruff |
| **Celery** | https://docs.celeryq.dev/ |
| **Gradio** | https://www.gradio.app/docs |

---

## 📝 Notas de Progreso

> Aquí se registrarán avances y decisiones durante el desarrollo.

### Semana del 13 de abril de 2026
- [ ] Iniciar con mejoras #1, #2, #3

---

<p align="center">
  <strong>OmniBook Studio</strong> • Plan de Optimización v1.0
</p>
