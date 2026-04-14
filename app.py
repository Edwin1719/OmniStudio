#!/usr/bin/env python3
"""
app.py - OmniBook v2.0 - Plataforma Completa de Audiolibros con IA
Interfaz gráfica web con múltiples pestañas y funcionalidades avanzadas
"""

import gradio as gr
import os
import sys
import time
import gc
import json
import torch
import torchaudio
from pathlib import Path
from pydub import AudioSegment
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from omnivoice import OmniVoice

# ============================================================
# DIRECTORIOS Y CONFIGURACIÓN
# ============================================================

REFERENCE_DIR = Path("reference")
OUTPUT_DIR = Path("output")
VOICES_DB = Path("config/voices_db.json")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
VOICES_DB.parent.mkdir(parents=True, exist_ok=True)

# Crear archivo de base de datos si no existe
if not VOICES_DB.exists():
    with open(VOICES_DB, 'w', encoding='utf-8') as f:
        json.dump({"voices": []}, f, indent=2, ensure_ascii=False)

# Estado global
model_cache = {}


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def cargar_voces_db():
    """Cargar base de datos de voces."""
    try:
        with open(VOICES_DB, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"voices": []}


def guardar_voces_db(db):
    """Guardar base de datos de voces."""
    with open(VOICES_DB, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


def cargar_modelo(device="cuda"):
    """Cargar modelo OmniVoice en caché."""
    if "model" not in model_cache:
        if device == "cuda" and not torch.cuda.is_available():
            device = "cpu"

        dtype = torch.float16 if device == "cuda" else torch.float32

        model_cache["model"] = OmniVoice.from_pretrained(
            "k2-fsa/OmniVoice",
            device_map=device,
            dtype=dtype
        )
        model_cache["device"] = device

    return model_cache["model"], model_cache["device"]


def preparar_audio_referencia(audio_path):
    """Convertir y recortar audio de referencia a 10s, WAV, 16kHz, mono."""
    if audio_path is None:
        return None, "❌ No se proporcionó audio de referencia"

    audio_path = Path(audio_path)

    try:
        if audio_path.suffix.lower() == ".mp3":
            audio = AudioSegment.from_mp3(str(audio_path))
        else:
            audio = AudioSegment.from_file(str(audio_path))
    except Exception as e:
        return None, f"❌ Error al cargar audio: {e}"

    duracion = len(audio) / 1000
    mensaje = f"📊 Audio original: {duracion:.1f}s"

    if duracion > 10:
        audio = audio[:10000]
        mensaje += f" → Recortado a 10s"

    ref_path = REFERENCE_DIR / f"ref_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
    audio = audio.set_frame_rate(16000).set_channels(1)
    audio.export(str(ref_path), format="wav")

    mensaje += f"\n✅ Audio listo: {ref_path.name}"
    return str(ref_path), mensaje


def dividir_texto(texto, max_caracteres=150):
    """Dividir texto en fragmentos manejables."""
    fragmentos = []
    parrafos = texto.split('\n\n')

    for parrafo in parrafos:
        parrafo = parrafo.strip()
        if not parrafo:
            continue

        oraciones = []
        actual = []
        actual_len = 0

        partes = parrafo.replace('. ', '.|').replace('\n', '|').split('|')

        for parte in partes:
            parte = parte.strip()
            if not parte:
                continue

            if actual_len + len(parte) <= max_caracteres:
                actual.append(parte)
                actual_len += len(parte)
            else:
                if actual:
                    oraciones.append(' '.join(actual))
                actual = [parte]
                actual_len = len(parte)

        if actual:
            oraciones.append(' '.join(actual))

        fragmentos.extend(oraciones)

    return [f for f in fragmentos if f.strip()]


# ============================================================
# PESTAÑA 1: GENERAR AUDIOBOOK
# ============================================================

def generar_audiolibro(
    modo_voz,
    audio_ref,
    voz_seleccionada,
    instruct_text,
    archivo_texto,
    texto_directo,
    idioma,
    num_step,
    speed,
    guidance_scale,
    progress=gr.Progress()
):
    """Función principal de generación con múltiples modos de voz."""

    # Validaciones
    if not archivo_texto and not texto_directo:
        yield None, "❌ Debes proporcionar un archivo de texto o escribir texto"
        return

    # Obtener texto
    if archivo_texto:
        with open(archivo_texto, 'r', encoding='utf-8') as f:
            texto = f.read()
    else:
        texto = texto_directo

    if not texto.strip():
        yield None, "❌ El texto está vacío"
        return

    # Preparar modo de voz
    ref_audio = None
    instruct = None

    if modo_voz == "🎙️ Clonar Voz (Audio)":
        if audio_ref is None:
            yield None, "❌ Debes subir un audio de referencia para clonar"
            return
        ref_audio, msg_audio = preparar_audio_referencia(audio_ref)
        if ref_audio is None:
            yield None, msg_audio
            return
    elif modo_voz == "💻 Usar Voz Guardada":
        if not voz_seleccionada or voz_seleccionada == "Ninguna":
            yield None, "❌ Selecciona una voz de la biblioteca"
            return
        db = cargar_voces_db()
        voz = next((v for v in db["voices"] if v["name"] == voz_seleccionada), None)
        if not voz:
            yield None, "❌ Voz no encontrada en la biblioteca"
            return
        if voz["type"] == "clone":
            ref_audio = voz["audio_path"]
        elif voz["type"] == "design":
            instruct = voz["instruct"]
    elif modo_voz == "🎨 Diseño de Voz (Atributos)":
        if not instruct_text:
            yield None, "❌ Debes especificar atributos de voz"
            return
        instruct = instruct_text

    # Dispositivo
    device = "cuda" if torch.cuda.is_available() else "cpu"

    yield None, f"⏳ Cargando modelo en {device.upper()}..."

    try:
        model, device = cargar_modelo(device)
    except Exception as e:
        yield None, f"❌ Error al cargar modelo: {e}"
        return

    # Dividir texto
    fragmentos = dividir_texto(texto)
    total = len(fragmentos)

    log_lines = [f"📝 {total} fragmentos a procesar", f"🌐 Idioma: {idioma}", ""]

    # Generar audio
    audios = []
    tiempos = []

    for i, fragmento in enumerate(fragmentos):
        progreso = (i + 1) / total
        progress(progreso, f"Generando fragmento {i+1}/{total}...")

        start_time = time.time()

        try:
            kwargs = {
                "text": fragmento,
                "num_step": num_step,
            }

            if ref_audio:
                kwargs["ref_audio"] = ref_audio
            if instruct:
                kwargs["instruct"] = instruct
            if idioma and idioma != "Auto-detectar":
                kwargs["language_id"] = idioma
            if speed != 1.0:
                kwargs["speed"] = speed

            audio = model.generate(**kwargs)
            audios.append(audio[0])

            elapsed = time.time() - start_time
            tiempos.append(elapsed)

            duracion_audio = audio[0].shape[1] / 24000 if audio[0].dim() > 1 else 0
            log_lines.append(f"  ✓ {i+1}/{total} - {elapsed:.1f}s (audio: {duracion_audio:.1f}s)")

            if device == "cuda":
                torch.cuda.empty_cache()
            gc.collect()

        except Exception as e:
            log_lines.append(f"  ✗ Error en fragmento {i+1}: {e}")
            continue

    if not audios:
        yield None, "❌ No se pudo generar ningún audio"
        return

    # Unir fragmentos
    log_lines.append(f"\n🔗 Uniendo {len(audios)} fragmentos...")
    yield None, "\n".join(log_lines)

    try:
        audio_final = torch.cat(audios, dim=1)

        output_path = OUTPUT_DIR / f"audiobook_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
        torchaudio.save(str(output_path), audio_final.cpu(), 24000)

        del audios
        del audio_final
        gc.collect()
        if device == "cuda":
            torch.cuda.empty_cache()

        audio_reload, sr = torchaudio.load(str(output_path))

        duracion_total = audio_reload.shape[1] / 24000
        tiempo_total = sum(tiempos)
        rtf = tiempo_total / duracion_total if duracion_total > 0 else 0

        log_lines.append(f"\n{'='*50}")
        log_lines.append(f"✅ ¡Audiolibro generado!")
        log_lines.append(f"📁 {output_path.name}")
        log_lines.append(f"⏱️  Duración: {duracion_total:.1f}s ({duracion_total/60:.1f} min)")
        log_lines.append(f"⏰ Tiempo: {tiempo_total:.1f}s ({tiempo_total/60:.1f} min)")
        log_lines.append(f"📊 RTF: {rtf:.2f}x")
        log_lines.append(f"{'='*50}")

        yield str(output_path), "\n".join(log_lines)

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log_lines.append(f"\n❌ Error al unir audio: {e}")
        log_lines.append(tb)
        yield None, "\n".join(log_lines)


def generar_dialogo_multivoz(
    script_texto,
    mapeo_voces_json,
    idioma,
    num_step,
    speed,
    progress=gr.Progress()
):
    """Generar audio para un diálogo con múltiples personajes."""
    
    if not script_texto.strip():
        yield None, "❌ El guion está vacío"
        return

    # Cargar mapeo de voces
    try:
        mapeo = json.loads(mapeo_voces_json)
    except Exception as e:
        yield None, f"❌ Error en el formato del mapeo (JSON): {e}\nEjemplo:\n{{\"Narrador\": \"Narrador Profesional\", \"Juan\": \"Locutor Épico\"}}"
        return

    db = cargar_voces_db()
    voces_dict = {v["name"]: v for v in db["voices"]}
    
    # Analizar el script
    lineas = script_texto.split('\n')
    tareas = []
    
    for i, linea in enumerate(lineas):
        linea = linea.strip()
        if not linea or ':' not in linea:
            continue
            
        personaje, texto = linea.split(':', 1)
        personaje = personaje.strip()
        texto = texto.strip()
        
        if not texto:
            continue
            
        nombre_voz = mapeo.get(personaje)
        if not nombre_voz:
            yield None, f"❌ No se encontró mapeo para el personaje '{personaje}'"
            return
            
        voz = voces_dict.get(nombre_voz)
        if not voz:
            yield None, f"❌ La voz '{nombre_voz}' no existe en la biblioteca"
            return
            
        tareas.append({
            "linea": i + 1,
            "personaje": personaje,
            "texto": texto,
            "voz": voz
        })

    if not tareas:
        yield None, "❌ No se detectaron líneas válidas con el formato 'Personaje: Texto'"
        return

    # Cargar modelo
    device = "cuda" if torch.cuda.is_available() else "cpu"
    yield None, f"⏳ Cargando modelo en {device.upper()}..."
    try:
        model, device = cargar_modelo(device)
    except Exception as e:
        yield None, f"❌ Error al cargar modelo: {e}"
        return

    log_lines = [f"🎭 Procesando diálogo con {len(tareas)} intervenciones", ""]
    audios = []
    
    # Silencio de 300ms entre intervenciones para naturalidad
    silencio = torch.zeros((1, int(24000 * 0.3)))

    for i, t in enumerate(tareas):
        progreso = (i + 1) / len(tareas)
        progress(progreso, f"Generando voz de {t['personaje']}...")
        
        start_time = time.time()
        
        try:
            # Añadir un espacio extra al final para evitar cortes abruptos del modelo
            texto_procesar = t["texto"] + " "

            kwargs = {
                "text": texto_procesar,
                "num_step": num_step,
                "speed": speed
            }
            
            if t["voz"]["type"] == "clone":
                kwargs["ref_audio"] = t["voz"]["audio_path"]
            elif t["voz"]["type"] == "design":
                kwargs["instruct"] = t["voz"]["instruct"]
                
            if idioma and idioma != "Auto-detectar":
                kwargs["language_id"] = idioma

            audio = model.generate(**kwargs)
            audios.append(audio[0])
            
            # Añadir silencio después de cada intervención (excepto la última si se desea)
            audios.append(silencio)
            
            elapsed = time.time() - start_time
            log_lines.append(f"  ✓ L{t['linea']} [{t['personaje']}]: {elapsed:.1f}s")
            
            if device == "cuda":
                torch.cuda.empty_cache()
            gc.collect()
            
        except Exception as e:
            log_lines.append(f"  ✗ Error en línea {t['linea']}: {e}")
            continue

    if not audios:
        yield None, "❌ Error al generar audios de los personajes"
        return

    # Unir
    log_lines.append(f"\n🔗 Uniendo intervenciones...")
    yield None, "\n".join(log_lines)
    
    try:
        audio_final = torch.cat(audios, dim=1)
        output_path = OUTPUT_DIR / f"dialogo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
        torchaudio.save(str(output_path), audio_final.cpu(), 24000)
        
        log_lines.append(f"\n✅ ¡Diálogo generado exitosamente!")
        log_lines.append(f"📁 {output_path.name}")
        yield str(output_path), "\n".join(log_lines)
        
    except Exception as e:
        yield None, f"❌ Error al unir diálogo: {e}"


def actualizar_voces_dropdown():
    """Actualizar dropdown de voces disponibles."""
    db = cargar_voces_db()
    voces = [v["name"] for v in db["voices"]]
    return gr.Dropdown(choices=["Ninguna"] + voces, value="Ninguna")


# ============================================================
# PESTAÑA 2: DISEÑO DE VOCES
# ============================================================

def generar_muestra_voz(
    texto_muestra,
    genero,
    edad,
    tono,
    estilo,
    acento,
    dialecto,
    num_step,
    progress=gr.Progress()
):
    """Generar muestra de voz diseñada desde atributos."""

    if not texto_muestra.strip():
        return None, "❌ Escribe un texto de muestra"

    # Construir instrucción (convertir booleano de checkbox a string)
    estilo_val = "whisper" if estilo else None

    atributos = []
    if genero:
        atributos.append(genero)
    if edad:
        atributos.append(edad)
    if tono:
        atributos.append(tono)
    if estilo_val:
        atributos.append(estilo_val)
    if acento:
        atributos.append(acento)
    if dialecto:
        atributos.append(dialecto)

    if not atributos:
        return None, "❌ Selecciona al menos un atributo"

    instruct = ", ".join(atributos)

    device = "cuda" if torch.cuda.is_available() else "cpu"

    progress(0.3, f"Generando con: {instruct}")

    try:
        model, device = cargar_modelo(device)
    except Exception as e:
        return None, f"❌ Error al cargar modelo: {e}"

    try:
        kwargs = {
            "text": texto_muestra,
            "instruct": instruct,
            "num_step": num_step,
        }

        audio = model.generate(**kwargs)

        output_path = OUTPUT_DIR / f"voice_sample_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
        torchaudio.save(str(output_path), audio[0], 24000)

        duracion = audio[0].shape[1] / 24000

        log = f"✅ Muestra generada exitosamente\n"
        log += f"🎙️ Voz: {instruct}\n"
        log += f"⏱️  Duración: {duracion:.1f}s\n"
        log += f"📁 {output_path.name}"

        progress(1.0, "Completado")

        return str(output_path), log

    except Exception as e:
        return None, f"❌ Error al generar: {e}"


def guardar_voz_diseñada(
    nombre,
    genero,
    edad,
    tono,
    estilo,
    acento,
    dialecto
):
    """Guardar voz diseñada en la biblioteca."""

    if not nombre.strip():
        return "❌ Escribe un nombre para la voz"

    # Convertir booleano de checkbox a string
    estilo_val = "whisper" if estilo else None

    atributos = []
    if genero:
        atributos.append(genero)
    if edad:
        atributos.append(edad)
    if tono:
        atributos.append(tono)
    if estilo_val:
        atributos.append(estilo_val)
    if acento:
        atributos.append(acento)
    if dialecto:
        atributos.append(dialecto)

    if not atributos:
        return "❌ Selecciona al menos un atributo"

    instruct = ", ".join(atributos)

    db = cargar_voces_db()

    # Verificar nombre duplicado
    if any(v["name"] == nombre for v in db["voices"]):
        return f"❌ Ya existe una voz llamada '{nombre}'"

    nueva_voz = {
        "name": nombre,
        "type": "design",
        "instruct": instruct,
        "atributos": {
            "genero": genero,
            "edad": edad,
            "tono": tono,
            "estilo": estilo_val,
            "acento": acento,
            "dialecto": dialecto,
        },
        "created_at": datetime.now().isoformat(),
    }

    db["voices"].append(nueva_voz)
    guardar_voces_db(db)

    return f"✅ Voz '{nombre}' guardada en la biblioteca!"


def actualizar_preview_instruct(genero, edad, tono, estilo, acento, dialecto):
    """Actualizar preview de la instrucción."""
    estilo_val = "whisper" if estilo else None
    atributos = []
    if genero:
        atributos.append(genero)
    if edad:
        atributos.append(edad)
    if tono:
        atributos.append(tono)
    if estilo_val:
        atributos.append(estilo_val)
    if acento:
        atributos.append(acento)
    if dialecto:
        atributos.append(dialecto)

    return ", ".join(atributos) if atributos else "Selecciona atributos..."


# ============================================================
# PESTAÑA 3: BIBLIOTECA DE VOCES
# ============================================================

def cargar_biblioteca_voces():
    """Cargar y mostrar biblioteca de voces."""
    db = cargar_voces_db()

    if not db["voices"]:
        return "📚 No hay voces guardadas aún.\n\n💡 Clona una voz o diseña una nueva para empezar."

    output = "💾 BIBLIOTECA DE VOCES\n"
    output += "="*50 + "\n\n"

    for i, voz in enumerate(db["voices"], 1):
        tipo = "🎙️ Clonada" if voz["type"] == "clone" else "🎨 Diseñada"
        output += f"{i}. {voz['name']} ({tipo})\n"
        if voz["type"] == "clone":
            output += f"   📁 Audio: {Path(voz['audio_path']).name}\n"
        else:
            output += f"   🎛️ {voz['instruct']}\n"
        output += f"   📅 {voz.get('created_at', 'N/A')[:19]}\n\n"

    return output


def eliminar_voz(nombre):
    """Eliminar voz de la biblioteca."""
    if not nombre or nombre == "Ninguna":
        return "❌ Selecciona una voz para eliminar", actualizar_voces_dropdown()

    db = cargar_voces_db()
    antes = len(db["voices"])
    db["voices"] = [v for v in db["voices"] if v["name"] != nombre]

    if len(db["voices"]) == antes:
        return f"❌ Voz '{nombre}' no encontrada", actualizar_voces_dropdown()

    guardar_voces_db(db)
    return f"✅ Voz '{nombre}' eliminada", actualizar_voces_dropdown()


def clonar_voz_a_biblioteca(audio_path, nombre, transcripcion):
    """Clonar voz y guardar en biblioteca."""
    if audio_path is None:
        return "❌ Sube un audio de referencia"
    if not nombre.strip():
        return "❌ Escribe un nombre para la voz"

    db = cargar_voces_db()

    if any(v["name"] == nombre for v in db["voices"]):
        return f"❌ Ya existe una voz llamada '{nombre}'"

    # Procesar audio
    ref_audio, msg = preparar_audio_referencia(audio_path)
    if ref_audio is None:
        return msg

    nueva_voz = {
        "name": nombre,
        "type": "clone",
        "audio_path": ref_audio,
        "ref_text": transcripcion if transcripcion else None,
        "created_at": datetime.now().isoformat(),
    }

    db["voices"].append(nueva_voz)
    guardar_voces_db(db)

    return f"✅ Voz '{nombre}' clonada y guardada!"


# ============================================================
# PESTAÑA 4: HERRAMIENTAS AVANZADAS
# ============================================================

def auto_transcribir(audio_path):
    """Auto-transcribir audio con Whisper."""
    if audio_path is None:
        return "❌ Sube un audio primero", ""

    device = "cuda" if torch.cuda.is_available() else "cpu"

    try:
        model, device = cargar_modelo(device)
    except Exception as e:
        return f"❌ Error al cargar modelo: {e}", ""

    try:
        # Cargar modelo Whisper
        model.load_asr_model(model_name="openai/whisper-large-v3-turbo")
        transcripcion = model.transcribe(audio_path)

        log = f"✅ Transcripción completada\n📝 Texto: {transcripcion[:200]}..."
        return log, transcripcion

    except Exception as e:
        return f"❌ Error al transcribir: {e}", ""


def convertir_audio(archivo_entrada, formato_salida="mp3"):
    """Convertir audio a diferentes formatos."""
    if archivo_entrada is None:
        return None, "❌ Selecciona un archivo de audio"

    try:
        audio = AudioSegment.from_file(archivo_entrada)
        nombre_base = Path(archivo_entrada).stem
        output_path = OUTPUT_DIR / f"{nombre_base}.{formato_salida}"

        if formato_salida == "mp3":
            audio.export(str(output_path), format="mp3", bitrate="192k")
        elif formato_salida == "ogg":
            audio.export(str(output_path), format="ogg", codec="libvorbis")
        elif formato_salida == "m4a":
            audio.export(str(output_path), format="ipod")
        else:
            audio.export(str(output_path), format=formato_salida)

        return str(output_path), f"✅ Convertido a {formato_salida.upper()}"

    except Exception as e:
        return None, f"❌ Error al convertir: {e}"


# ============================================================
# INTERFAZ GRADIO COMPLETA
# ============================================================

HEADER_HTML = """
<div style="text-align: center; padding: 20px 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; margin-bottom: 20px;">
    <h1 style="font-size: 2.5em; margin: 0; color: white; font-weight: 800;">
        🎙️ OmniBook Studio
    </h1>
    <p style="font-size: 1.2em; color: rgba(255,255,255,0.9); margin: 10px 0 5px 0;">
        Plataforma de Síntesis de Voz y Producción de Audio con IA
    </p>
    <p style="font-size: 0.9em; color: rgba(255,255,255,0.7); margin: 0;">
        Powered by OmniVoice • Clonación • Diseño de Voces • 20+ Voces Pre-diseñadas
    </p>
</div>
"""

FOOTER_HTML = """
<div style="text-align: center; padding: 20px 0; color: #999; font-size: 0.85em; border-top: 1px solid #eee; margin-top: 20px;">
    <p>OmniBook Studio • Basado en OmniVoice (k2-fsa) • Licencia Apache 2.0</p>
</div>
"""

with gr.Blocks(
    title="OmniBook Studio - Síntesis de Voz y Producción de Audio con IA",
) as app:

    gr.HTML(HEADER_HTML)

    # Estado compartido
    voz_seleccionada_state = gr.State(value="Ninguna")

    with gr.Tabs():

        # ============================================================
        # PESTAÑA 1: GENERAR AUDIOBOOK
        # ============================================================
        with gr.Tab("📚 Generar Audiolibro"):

            gr.Markdown("### 📚 Generar Audiolibro con OmniVoice")
            gr.Markdown("Transforma cualquier texto en un audiolibro profesional")

            with gr.Row():
                with gr.Column(scale=1):

                    gr.Markdown("### 🎙️ Paso 1: Selecciona Modo de Voz")
                    modo_voz = gr.Radio(
                        choices=["🎙️ Clonar Voz (Audio)", "💻 Usar Voz Guardada", "🎨 Diseño de Voz (Atributos)"],
                        value="🎙️ Clonar Voz (Audio)",
                        label="Modo de voz",
                    )

                    # Opción A: Clonar voz
                    audio_ref_gen = gr.Audio(
                        type="filepath",
                        label="Audio de referencia (para clonar)",
                        sources=["upload"],
                    )

                    # Opción B: Usar voz guardada
                    voces_dropdown = gr.Dropdown(
                        choices=["Ninguna"],
                        value="Ninguna",
                        label="Voces guardadas",
                        visible=False,
                    )
                    btn_actualizar_voces = gr.Button("🔄 Actualizar lista", size="sm", visible=False)

                    # Opción C: Diseño de voz
                    instruct_gen = gr.Textbox(
                        label="Atributos de voz",
                        placeholder="Ej: female, young adult, high pitch, british accent",
                        lines=2,
                        visible=False,
                    )

                    gr.Markdown("---")
                    gr.Markdown("### 📄 Paso 2: Texto del Libro")

                    archivo_texto_gen = gr.File(
                        label="Archivo de texto (.txt)",
                        file_types=[".txt"],
                        type="filepath",
                    )

                    texto_directo_gen = gr.Textbox(
                        label="O escribe el texto aquí",
                        lines=6,
                        placeholder="Pega o escribe tu texto aquí...",
                    )

                    gr.Markdown("---")
                    gr.Markdown("### ⚙️ Paso 3: Configuración")

                    idioma_gen = gr.Dropdown(
                        choices=["Auto-detectar", "es", "en", "fr", "de", "it", "pt", "zh", "ja", "ko", "ru", "ar", "hi"],
                        value="Auto-detectar",
                        label="Idioma",
                        info="Especificar idioma mejora la calidad",
                    )

                    with gr.Row():
                        num_step_gen = gr.Slider(
                            minimum=4,
                            maximum=32,
                            value=8,
                            step=4,
                            label="Calidad (pasos de difusión)",
                            info="4=Rápido, 8=Balanceado, 16=Alta, 32=Máxima",
                        )

                        speed_gen = gr.Slider(
                            minimum=0.5,
                            maximum=1.5,
                            value=1.0,
                            step=0.1,
                            label="Velocidad de lectura",
                            info="0.5x=lento, 1.0x=normal, 1.5x=rápido",
                        )

                    guidance_scale_gen = gr.Slider(
                        minimum=0.0,
                        maximum=4.0,
                        value=2.0,
                        step=0.5,
                        label="Guidance Scale",
                        info="Más alto = más fiel al texto (0.0-4.0)",
                    )

                    btn_generar = gr.Button(
                        "🎬 Generar Audiolibro",
                        variant="primary",
                        size="lg",
                    )

                with gr.Column(scale=1):
                    gr.Markdown("### 📊 Progreso y Resultados")

                    log_output_gen = gr.Textbox(
                        label="Registro de actividad",
                        lines=15,
                        interactive=False,
                        placeholder="Aquí verás el progreso de la generación...",
                    )

                    audio_output_gen = gr.Audio(
                        label="🎧 Audiolibro generada",
                        type="filepath",
                        interactive=False,
                    )

            # Event handlers
            def actualizar_visibilidad(modo):
                if modo == "🎙️ Clonar Voz (Audio)":
                    return gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)
                elif modo == "💻 Usar Voz Guardada":
                    return gr.update(visible=False), gr.update(visible=True), gr.update(visible=True), gr.update(visible=False)
                else:
                    return gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=True)

            modo_voz.change(
                fn=actualizar_visibilidad,
                inputs=[modo_voz],
                outputs=[
                    audio_ref_gen,
                    voces_dropdown,
                    btn_actualizar_voces,
                    instruct_gen,
                ],
            )

            btn_actualizar_voces.click(
                fn=actualizar_voces_dropdown,
                outputs=[voces_dropdown],
            )

            btn_generar.click(
                fn=generar_audiolibro,
                inputs=[
                    modo_voz,
                    audio_ref_gen,
                    voces_dropdown,
                    instruct_gen,
                    archivo_texto_gen,
                    texto_directo_gen,
                    idioma_gen,
                    num_step_gen,
                    speed_gen,
                    guidance_scale_gen,
                ],
                outputs=[audio_output_gen, log_output_gen],
            )

        # ============================================================
        # PESTAÑA 2: DISEÑO DE VOCES
        # ============================================================
        with gr.Tab("🎨 Diseño de Voces"):

            gr.Markdown("### 🎨 Diseño de Voces desde Atributos")
            gr.Markdown("Crea voces personalizadas sin necesidad de audio de referencia")

            with gr.Row():
                with gr.Column(scale=1):

                    gr.Markdown("### 🎛️ Atributos de Voz")

                    genero = gr.Radio(
                        choices=["male", "female"],
                        label="Género",
                        value=None,
                    )

                    edad = gr.Dropdown(
                        choices=["child", "teenager", "young adult", "middle-aged", "elderly"],
                        label="Edad",
                        value=None,
                        allow_custom_value=False,
                    )

                    tono = gr.Dropdown(
                        choices=["very low pitch", "low pitch", "moderate pitch", "high pitch", "very high pitch"],
                        label="Tono",
                        value=None,
                    )

                    estilo = gr.Checkbox(
                        label="Susurro (whisper)",
                        value=False,
                    )

                    gr.Markdown("---")
                    gr.Markdown("### 🌍 Acentos y Dialectos")

                    acento = gr.Dropdown(
                        choices=[
                            "american accent", "british accent", "australian accent",
                            "canadian accent", "indian accent", "chinese accent",
                            "korean accent", "japanese accent", "portuguese accent",
                            "russian accent"
                        ],
                        label="Acento (inglés)",
                        value=None,
                    )

                    dialecto = gr.Dropdown(
                        choices=[
                            "河南话", "陕西话", "四川话", "贵州话", "云南话",
                            "桂林话", "济南话", "石家庄话", "甘肃话", "宁夏话",
                            "青岛话", "东北话"
                        ],
                        label="Dialecto (chino)",
                        value=None,
                    )

                    gr.Markdown("---")
                    gr.Markdown("### 📝 Vista Previa")

                    instruct_preview = gr.Textbox(
                        label="Instrucción generada",
                        value="Selecciona atributos...",
                        interactive=False,
                        lines=2,
                    )

                with gr.Column(scale=1):

                    gr.Markdown("### 🔊 Generar Muestra")

                    texto_muestra = gr.Textbox(
                        label="Texto de muestra (1-2 oraciones)",
                        placeholder="Hola, soy tu nueva voz diseñada. ¿Qué te parece?",
                        lines=3,
                    )

                    num_step_diseno = gr.Slider(
                        minimum=4,
                        maximum=32,
                        value=8,
                        step=4,
                        label="Calidad",
                    )

                    btn_generar_muestra = gr.Button("🎙️ Generar Muestra", variant="primary")

                    audio_muestra = gr.Audio(
                        label="Muestra de voz",
                        type="filepath",
                        interactive=False,
                    )

                    log_muestra = gr.Textbox(
                        label="Registro",
                        lines=5,
                        interactive=False,
                    )

                    gr.Markdown("---")
                    gr.Markdown("### 💾 Guardar en Biblioteca")

                    nombre_voz_diseno = gr.Textbox(
                        label="Nombre de la voz",
                        placeholder="Ej: Narrador Épico Británico",
                    )

                    btn_guardar_diseno = gr.Button("💾 Guardar Voz", variant="secondary")

                    log_guardado = gr.Textbox(
                        label="Estado",
                        lines=2,
                        interactive=False,
                    )

            # Event handlers - actualizar preview cuando cambian atributos
            def actualizar_preview_wrapper(genero, edad, tono, estilo_check, acento, dialecto):
                estilo_val = "whisper" if estilo_check else None
                return actualizar_preview_instruct(genero, edad, tono, estilo_val, acento, dialecto)

            genero.change(
                fn=actualizar_preview_wrapper,
                inputs=[genero, edad, tono, estilo, acento, dialecto],
                outputs=[instruct_preview],
            )
            edad.change(
                fn=actualizar_preview_wrapper,
                inputs=[genero, edad, tono, estilo, acento, dialecto],
                outputs=[instruct_preview],
            )
            tono.change(
                fn=actualizar_preview_wrapper,
                inputs=[genero, edad, tono, estilo, acento, dialecto],
                outputs=[instruct_preview],
            )
            estilo.change(
                fn=actualizar_preview_wrapper,
                inputs=[genero, edad, tono, estilo, acento, dialecto],
                outputs=[instruct_preview],
            )
            acento.change(
                fn=actualizar_preview_wrapper,
                inputs=[genero, edad, tono, estilo, acento, dialecto],
                outputs=[instruct_preview],
            )
            dialecto.change(
                fn=actualizar_preview_wrapper,
                inputs=[genero, edad, tono, estilo, acento, dialecto],
                outputs=[instruct_preview],
            )

            btn_generar_muestra.click(
                fn=generar_muestra_voz,
                inputs=[
                    texto_muestra,
                    genero,
                    edad,
                    tono,
                    estilo,
                    acento,
                    dialecto,
                    num_step_diseno,
                ],
                outputs=[audio_muestra, log_muestra],
            )

            btn_guardar_diseno.click(
                fn=guardar_voz_diseñada,
                inputs=[nombre_voz_diseno, genero, edad, tono, estilo, acento, dialecto],
                outputs=[log_guardado],
            )

        # ============================================================
        # PESTAÑA 3: BIBLIOTECA DE VOCES
        # ============================================================
        with gr.Tab("💾 Biblioteca"):

            gr.Markdown("### 💾 Biblioteca de Voces Guardadas")
            gr.Markdown("Gestiona tus voces clonadas y diseñadas")

            with gr.Row():
                with gr.Column(scale=1):

                    btn_actualizar_biblioteca = gr.Button("🔄 Actualizar Biblioteca")

                    biblioteca_output = gr.Textbox(
                        label="Voces guardadas",
                        lines=15,
                        interactive=False,
                        value="Haz clic en 'Actualizar Biblioteca' para ver tus voces",
                    )

                with gr.Column(scale=1):

                    gr.Markdown("### 🗑️ Eliminar Voz")

                    nombre_voz_eliminar = gr.Dropdown(
                        choices=["Ninguna"],
                        label="Selecciona voz a eliminar",
                        value="Ninguna",
                    )

                    btn_actualizar_eliminar = gr.Button("🔄 Actualizar lista", size="sm")

                    btn_eliminar = gr.Button("🗑️ Eliminar Voz", variant="stop")

                    log_eliminar = gr.Textbox(
                        label="Estado",
                        lines=2,
                        interactive=False,
                    )

                    gr.Markdown("---")
                    gr.Markdown("### 🎙️ Clonar Nueva Voz")

                    audio_clonar = gr.Audio(
                        type="filepath",
                        label="Audio de referencia",
                        sources=["upload"],
                    )

                    nombre_clonar = gr.Textbox(
                        label="Nombre de la voz",
                        placeholder="Ej: Voz de María",
                    )

                    transcripcion_clonar = gr.Textbox(
                        label="Transcripción (opcional)",
                        placeholder="Texto del audio de referencia...",
                        lines=3,
                    )

                    btn_clonar = gr.Button("🎙️ Clonar y Guardar", variant="primary")

                    log_clonar = gr.Textbox(
                        label="Estado",
                        lines=2,
                        interactive=False,
                    )

            # Event handlers
            btn_actualizar_biblioteca.click(
                fn=cargar_biblioteca_voces,
                outputs=[biblioteca_output],
            )

            def actualizar_dropdown_eliminar():
                db = cargar_voces_db()
                voces = [v["name"] for v in db["voices"]]
                return gr.Dropdown(choices=["Ninguna"] + voces, value="Ninguna")

            btn_actualizar_eliminar.click(
                fn=actualizar_dropdown_eliminar,
                outputs=[nombre_voz_eliminar],
            )

            btn_eliminar.click(
                fn=eliminar_voz,
                inputs=[nombre_voz_eliminar],
                outputs=[log_eliminar, nombre_voz_eliminar],
            )

            btn_clonar.click(
                fn=clonar_voz_a_biblioteca,
                inputs=[audio_clonar, nombre_clonar, transcripcion_clonar],
                outputs=[log_clonar],
            )

        # ============================================================
        # PESTAÑA 4: DIÁLOGOS MULTIVOZ
        # ============================================================
        with gr.Tab("🎭 Diálogos Multivoz"):
            gr.Markdown("### 🎭 Generador de Diálogos Multivoz")
            gr.Markdown("Crea conversaciones entre diferentes personajes usando voces de tu biblioteca.")
            
            with gr.Row():
                with gr.Column(scale=1):
                    # Nueva lista de voces disponibles para facilitar la copia
                    voces_disponibles_box = gr.Textbox(
                        label="📋 Voces Disponibles (Copia y pega el nombre)",
                        lines=15,
                        interactive=False,
                        value="Haz clic en 'Actualizar Lista' para ver tus voces"
                    )
                    btn_refresh_dial_voices = gr.Button("🔄 Actualizar Lista de Voces")

                with gr.Column(scale=2):
                    script_input = gr.Textbox(
                        label="Guion (Script)",
                        placeholder="Narrador: Érase una vez...\nJuan: ¡Hola a todos!\nMaria: ¿Cómo están?",
                        lines=10
                    )
                    
                    mapeo_json = gr.Textbox(
                        label="Mapeo de Voces (JSON)",
                        placeholder='{"Narrador": "📖 Narrador Profesional", "Juan": "🎙️ Locutor Epico"}',
                        lines=5,
                        value='{}'
                    )
                    
                    with gr.Row():
                        idioma_dial = gr.Dropdown(
                            choices=["Auto-detectar", "es", "en", "fr", "de", "it", "pt", "ja", "ko", "zh"],
                            value="es",
                            label="Idioma dominante"
                        )
                        steps_dial = gr.Slider(minimum=4, maximum=32, step=4, value=8, label="Calidad (pasos)")
                        speed_dial = gr.Slider(minimum=0.5, maximum=1.5, step=0.1, value=1.0, label="Velocidad")

                    btn_generar_dial = gr.Button("🎬 Generar Diálogo", variant="primary")

                with gr.Column(scale=1):
                    audio_dial = gr.Audio(label="Audio Final", type="filepath", interactive=False)
                    log_dial = gr.Textbox(label="Registro de Procesamiento", lines=15, interactive=False)

            def listar_voces_para_dialogo():
                db = cargar_voces_db()
                return "\n".join([f"• {v['name']}" for v in db["voices"]])

            btn_refresh_dial_voices.click(
                fn=listar_voces_para_dialogo,
                outputs=[voces_disponibles_box]
            )

            # Ejemplos y Ayuda
            with gr.Accordion("💡 Ver instrucciones y ejemplos", open=False):
                gr.Markdown("""
#### Formato del Guion:
El script debe seguir el formato `Personaje: Texto`. Cada línea representa una intervención.
```text
Narrador: El sol se ocultaba tras las montañas.
Juan: Es hora de partir, amigos.
Maria: Esperadme, ¡no me dejéis atrás!
```

#### Formato del Mapeo (JSON):
Debes asociar cada nombre de personaje con una **Voz Guardada** de tu biblioteca.
```json
{
  "Narrador": "Narrador Profesional",
  "Juan": "Locutor Épico",
  "Maria": "Niña Contadora"
}
```
                """)

            btn_generar_dial.click(
                fn=generar_dialogo_multivoz,
                inputs=[script_input, mapeo_json, idioma_dial, steps_dial, speed_dial],
                outputs=[audio_dial, log_dial],
            )

        # ============================================================
        # PESTAÑA 5: HERRAMIENTAS AVANZADAS
        # ============================================================
        with gr.Tab("⚙️ Avanzado"):

            gr.Markdown("### ⚙️ Herramientas Avanzadas")
            gr.Markdown("Funciones adicionales para potencia tu flujo de trabajo")

            with gr.Tabs():

                # Sub-pestaña: Auto-Transcripción
                with gr.Tab("🎙️ Auto-Transcripción"):

                    gr.Markdown("#### Transcribir audio automáticamente con Whisper")

                    audio_transcribir = gr.Audio(
                        type="filepath",
                        label="Audio para transcribir",
                        sources=["upload"],
                    )

                    btn_transcribir = gr.Button("🎙️ Transcribir", variant="primary")

                    log_trans = gr.Textbox(
                        label="Registro",
                        lines=5,
                        interactive=False,
                    )

                    texto_transcripcion = gr.Textbox(
                        label="Transcripción",
                        lines=5,
                        interactive=True,
                    )

                    btn_transcribir.click(
                        fn=auto_transcribir,
                        inputs=[audio_transcribir],
                        outputs=[log_trans, texto_transcripcion],
                    )

                # Sub-pestaña: Conversor de Audio
                with gr.Tab("🔄 Conversor de Audio"):

                    gr.Markdown("#### Convertir audio a diferentes formatos")

                    audio_convertir = gr.Audio(
                        type="filepath",
                        label="Audio para convertir",
                        sources=["upload"],
                    )

                    formato_salida = gr.Dropdown(
                        choices=["mp3", "ogg", "m4a", "wav", "flac"],
                        value="mp3",
                        label="Formato de salida",
                    )

                    btn_convertir = gr.Button("🔄 Convertir", variant="primary")

                    audio_convertido = gr.Audio(
                        label="Audio convertido",
                        type="filepath",
                        interactive=False,
                    )

                    log_convertir = gr.Textbox(
                        label="Registro",
                        lines=3,
                        interactive=False,
                    )

                    btn_convertir.click(
                        fn=convertir_audio,
                        inputs=[audio_convertir, formato_salida],
                        outputs=[audio_convertido, log_convertir],
                    )

                # Sub-pestaña: Estadísticas
                with gr.Tab("📊 Estadísticas"):

                    gr.Markdown("#### Estadísticas de Uso")

                    def mostrar_estadisticas():
                        db = cargar_voces_db()
                        total_voces = len(db["voices"])
                        voces_clonadas = len([v for v in db["voices"] if v["type"] == "clone"])
                        voces_disenadas = len([v for v in db["voices"] if v["type"] == "design"])

                        # Contar audiolibros generados
                        audiolibros = list(OUTPUT_DIR.glob("audiobook_*.wav"))
                        muestras = list(OUTPUT_DIR.glob("voice_sample_*.wav"))

                        stats = f"📊 ESTADÍSTICAS DE USO\n"
                        stats += "="*50 + "\n\n"
                        stats += f"💾 Voces en biblioteca: {total_voces}\n"
                        stats += f"   🎙️ Clonadas: {voces_clonadas}\n"
                        stats += f"   🎨 Diseñadas: {voces_disenadas}\n\n"
                        stats += f"📚 Audiolibros generados: {len(audiolibros)}\n"
                        stats += f"🎙️ Muestras de voz: {len(muestras)}\n\n"

                        if audiolibros:
                            total_size = sum(f.stat().st_size for f in audiolibros)
                            stats += f"💾 Espacio usado (audiolibros): {total_size / 1024 / 1024:.1f} MB\n"

                        return stats

                    btn_actualizar_stats = gr.Button("🔄 Actualizar Estadísticas")
                    stats_output = gr.Textbox(
                        label="Estadísticas",
                        lines=15,
                        interactive=False,
                        value="Haz clic para ver tus estadísticas",
                    )

                    btn_actualizar_stats.click(
                        fn=mostrar_estadisticas,
                        outputs=[stats_output],
                    )

        # ============================================================
        # PESTAÑA 6: AYUDA
        # ============================================================
        with gr.Tab("❓ Ayuda"):

            gr.Markdown("### ❓ Ayuda y Documentación")

            with gr.Accordion("🚀 Guía Rápida de Inicio", open=True):
                gr.Markdown("""
**1. Generar un Audiolibro:**
- Ve a la pestaña "📚 Generar Audiolibro"
- Sube un audio con la voz que quieres clonar (o usa una voz guardada/diseñada)
- Proporciona el texto (archivo o directo)
- Ajusta calidad y velocidad
- Haz clic en "🎬 Generar Audiolibro"

**2. Diseñar una Voz Personalizada:**
- Ve a "🎨 Diseño de Voces"
- Selecciona atributos (género, edad, tono, acento)
- Genera una muestra para probar
- Guarda en tu biblioteca

**3. Usar la Biblioteca de Voces:**
- Ve a "💾 Biblioteca"
- Clona nuevas voces desde audio
- Elimina voces que ya no necesitas
- Usa voces guardadas al generar audiolibros

**4. Herramientas Avanzadas:**
- Ve a "⚙️ Avanzado"
- Auto-transcribe audio con Whisper
- Convierte audio entre formatos (MP3, OGG, M4A)
- Revisa tus estadísticas de uso
                """)

            with gr.Accordion("⚙️ Explicación de Parámetros", open=False):
                gr.Markdown("""
| Parámetro | Descripción | Valores Recomendados |
|-----------|-------------|---------------------|
| **Calidad (num_step)** | Pasos de difusión | 4=Rápido, 8=Balanceado, 16=Alta, 32=Máxima |
| **Velocidad** | Velocidad de lectura | 0.5x=lento, 1.0x=normal, 1.5x=rápido |
| **Guidance Scale** | Fidelidad al texto | 2.0=default, 3.0=más fiel |
| **Idioma** | Idioma del texto | Auto-detectar o específico |

**Voces Diseñadas (Diseño de Voces):**
- `male/female` - Género
- `child/teenager/young adult/middle-aged/elderly` - Edad
- `very low pitch → very high pitch` - Tono
- `whisper` - Susurro
- `british accent/american accent/...` - Acentos
                """)

            with gr.Accordion("❓ Preguntas Frecuentes", open=False):
                gr.Markdown("""
**¿Por qué tarda tanto la primera vez?**
- La primera vez descarga el modelo (~1-2 GB). Las siguientes veces es más rápido.

**¿Error "CUDA Out of Memory"?**
- Reduce la calidad a 4 pasos o usa CPU.

**¿Puedo usar la app sin GPU?**
- Sí, pero será mucho más lento. Selecciona CPU en la configuración.

**¿Dónde se guardan los audiolibros?**
- En la carpeta `output/` de tu proyecto.

**¿Cuánto dura el audio de referencia?**
- Idealmente 10 segundos. La app lo recorta automáticamente si es más largo.
                """)

            with gr.Accordion("🔗 Enlaces Útiles", open=False):
                gr.Markdown("""
- **Proyecto base:** [OmniVoice en GitHub](https://github.com/k2-fsa/OmniVoice)
- **Modelo:** [k2-fsa/OmniVoice en HuggingFace](https://huggingface.co/k2-fsa/OmniVoice)
- **Documentación:** `docs/` en tu proyecto
- **Licencia:** Apache 2.0
                """)

    gr.HTML(FOOTER_HTML)


if __name__ == "__main__":
    app.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        inbrowser=True,
        theme=gr.themes.Soft(primary_hue="purple", secondary_hue="blue"),
    )
