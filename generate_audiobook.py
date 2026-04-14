#!/usr/bin/env python3
"""
generate_audiobook.py - Script optimizado para generar audiolibros con OmniVoice
en hardware limitado (RTX 4050, 16GB RAM)
"""

import argparse
import os
import sys
import time
import gc
import torch
import torchaudio
from pathlib import Path

# Agregar el directorio del proyecto al path
sys.path.insert(0, str(Path(__file__).parent))

from omnivoice import OmniVoice


def limpiar_memoria():
    """Liberar memoria VRAM y RAM"""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    gc.collect()


def dividir_texto_en_fragmentos(texto, max_caracteres=150):
    """
    Dividir texto en fragmentos manejables para evitar agotamiento de memoria.
    Intenta mantener oraciones completas y evitar pausas largas.
    """
    fragmentos = []
    
    # Dividir por párrafos primero
    parrafos = texto.split('\n\n')
    
    for parrafo in parrafos:
        parrafo = parrafo.strip()
        if not parrafo:
            continue
        
        # Dividir por oraciones (punto + espacio o salto de línea)
        oraciones = []
        actual = []
        actual_len = 0
        
        # Dividir por punto y espacio
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


def generar_audiolibro(
    texto,
    ref_audio,
    ref_text,
    output_path,
    num_step=8,
    device="cuda",
    language_id=None,
    speed=1.0,
    duration=None,
    verbose=True
):
    """
    Generar audiolibro completo a partir de texto.
    """
    
    if verbose:
        print("="*60)
        print("📚 OmniBook - Generador de Audiolibros")
        print("="*60)
    
    # Verificar que existe el audio de referencia
    if not os.path.exists(ref_audio):
        print(f"❌ Error: No se encontró el audio de referencia: {ref_audio}")
        return False
    
    # Determinar dispositivo
    if device == "cuda" and not torch.cuda.is_available():
        print("⚠️  CUDA no disponible, usando CPU (será más lento)")
        device = "cpu"
    
    if verbose:
        print(f"\n📊 Configuración:")
        print(f"   Dispositivo: {device}")
        print(f"   Pasos de difusión: {num_step}")
        print(f"   Velocidad: {speed}x")
        if duration:
            print(f"   Duración fija: {duration}s")
        print(f"   Audio de referencia: {ref_audio}")
        print()
    
    # Cargar modelo
    if verbose:
        print("🔄 Cargando modelo OmniVoice...")
        print("   (Esto puede tomar unos segundos)")
    
    try:
        model = OmniVoice.from_pretrained(
            "k2-fsa/OmniVoice",
            device_map=device,
            dtype=torch.float16 if device == "cuda" else torch.float32
        )
        if verbose:
            print("✅ Modelo cargado exitosamente\n")
    except Exception as e:
        print(f"❌ Error al cargar el modelo: {e}")
        return False
    
    # Dividir texto en fragmentos
    fragmentos = dividir_texto_en_fragmentos(texto)
    
    if verbose:
        print(f"📝 Texto dividido en {len(fragmentos)} fragmentos\n")
    
    # Generar audio para cada fragmento
    audios = []
    tiempos = []
    
    for i, fragmento in enumerate(fragmentos):
        if verbose:
            print(f"🎙️  Fragmento {i+1}/{len(fragmentos)}...")
        
        start_time = time.time()
        
        try:
            # Generar audio
            kwargs = {
                "text": fragmento,
                "ref_audio": ref_audio,
                "ref_text": ref_text,
                "num_step": num_step,
            }
            
            if language_id:
                kwargs["language_id"] = language_id
            if speed != 1.0:
                kwargs["speed"] = speed
            if duration:
                kwargs["duration"] = duration
            
            audio = model.generate(**kwargs)
            audios.append(audio[0])
            
            elapsed = time.time() - start_time
            tiempos.append(elapsed)
            
            if verbose:
                vram = torch.cuda.memory_allocated() / 1e9 if device == "cuda" else 0
                print(f"   ✅ Completado en {elapsed:.1f}s")
                if device == "cuda":
                    print(f"   💾 VRAM usada: {vram:.2f} GB\n")
                else:
                    print()
            
            # Liberar memoria después de cada fragmento
            limpiar_memoria()
            
        except Exception as e:
            print(f"❌ Error en fragmento {i+1}: {e}")
            print(f"   Texto: {fragmento[:100]}...")
            # Continuar con el siguiente fragmento
            continue
    
    if not audios:
        print("❌ No se pudo generar ningún audio")
        return False
    
    # Unir todos los fragmentos
    if verbose:
        print("\n🔗 Uniendo fragmentos...")
    
    try:
        audio_final = torch.cat(audios, dim=1)
        
        # Crear directorio de salida si no existe
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # Guardar audio
        torchaudio.save(output_path, audio_final, 24000)
        
        if verbose:
            duracion_total = audio_final.shape[1] / 24000
            tiempo_total = sum(tiempos)
            
            print("\n" + "="*60)
            print("✅ ¡Audiolibro generado exitosamente!")
            print("="*60)
            print(f"📁 Archivo: {output_path}")
            print(f"⏱️  Duración: {duracion_total:.1f} segundos")
            print(f"⏰ Tiempo de generación: {tiempo_total:.1f} segundos")
            print(f"📊 RTF (Real Time Factor): {tiempo_total/duracion_total:.2f}x")
            print(f"🎵 Fragmentos: {len(audios)}")
            print(f"🔊 Sample rate: 24000 Hz")
            print("="*60)
        
        return True
        
    except Exception as e:
        print(f"❌ Error al unir/guardar audio: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Generar audiolibros con OmniVoice optimizado para hardware limitado"
    )
    
    parser.add_argument(
        "--text", "-t",
        type=str,
        required=True,
        help="Texto del audiolibro (archivo .txt o texto directo)"
    )
    parser.add_argument(
        "--ref_audio", "-r",
        type=str,
        required=True,
        help="Ruta al audio de referencia para clonación"
    )
    parser.add_argument(
        "--ref_text",
        type=str,
        default=None,
        help="Transcripción del audio de referencia (opcional, Whisper lo auto-transcribirá)"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="output/audiolibro.wav",
        help="Ruta de salida del archivo de audio"
    )
    parser.add_argument(
        "--num_step", "-n",
        type=int,
        default=8,
        choices=[4, 8, 16, 32],
        help="Número de pasos de difusión (default: 8). Menos=rápido, Más=calidad"
    )
    parser.add_argument(
        "--device", "-d",
        type=str,
        default="cuda",
        choices=["cuda", "cpu"],
        help="Dispositivo a usar (default: cuda)"
    )
    parser.add_argument(
        "--language_id", "-l",
        type=str,
        default=None,
        help="ID del idioma (ej: 'es' para español, 'en' para inglés)"
    )
    parser.add_argument(
        "--speed", "-s",
        type=float,
        default=1.0,
        help="Factor de velocidad (default: 1.0)"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Duración fija en segundos (ignora speed)"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Modo silencioso (sin salida detallada)"
    )
    
    args = parser.parse_args()
    
    # Leer texto desde archivo o usar directamente
    if os.path.exists(args.text):
        with open(args.text, 'r', encoding='utf-8') as f:
            texto = f.read()
    else:
        texto = args.text
    
    if not texto.strip():
        print("❌ Error: El texto está vacío")
        sys.exit(1)
    
    # Generar audiolibro
    exito = generar_audiolibro(
        texto=texto,
        ref_audio=args.ref_audio,
        ref_text=args.ref_text,
        output_path=args.output,
        num_step=args.num_step,
        device=args.device,
        language_id=args.language_id,
        speed=args.speed,
        duration=args.duration,
        verbose=not args.quiet
    )
    
    sys.exit(0 if exito else 1)


if __name__ == "__main__":
    main()
