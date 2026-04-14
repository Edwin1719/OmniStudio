# Changelog - OmniBook Studio

Todos los cambios notables en este proyecto serán documentados en este archivo.

---

## [2.1.0-MVP] - 2026-04-14
### 🎉 Añadido
- **Módulo de Diálogos Multivoz:** Nueva pestaña que permite procesar guiones con múltiples personajes.
- **Micro-silencios Automáticos:** Inserción de 300ms entre intervenciones para naturalidad.
- **Estabilidad de Audio:** Algoritmo de "aire" al final de frases para evitar cortes por el modelo de difusión.
- **Lista de Voces Interactiva:** Panel lateral para copiar nombres de voces con emojis fácilmente.

### 🛠️ Corregido
- **Inferencia:** Optimización de la liberación de caché de GPU tras cada fragmento de diálogo.
- **Puntuación:** Mejor manejo de puntos y comas en el divisor inteligente de texto.

---

## [2.0.0] - 2026-04-13
### 🎉 Añadido
- **Interfaz Gradio:** Rediseño completo por pestañas.
- **Biblioteca de Voces:** Sistema de persistencia JSON para voces clonadas y diseñadas.
- **Soporte Whisper:** Integración de transcripción automática.
- **Clonación Zero-Shot:** Motor OmniVoice integrado.

---

## [1.0.0] - 2026-01-10
### 🎉 Añadido
- **Core Engine:** Implementación básica de síntesis de voz con modelos locales.
- **CLI Tools:** Scripts iniciales para generación de audiolibros simples.
