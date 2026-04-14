#!/usr/bin/env python3
"""
generate_chapters.py - Procesar audiolibros capítulo por capítulo
Ideal para archivos largos, permite paralelización y mejor control
"""

import argparse
import os
import sys
import time
import gc
import json
import torch
import torchaudio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from omnivoice import OmniVoice


def cargar_configuracion(config_path=None):
    """Cargar configuración desde archivo JSON"""
    config = {
        "num_step": 8,
        "device": "cuda",
        "speed": 1.0,
        "language_id": "es",
    }
    
    if config_path and os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config.update(json.load(f))
    
    return config


def dividir_texto_en_capitulos(texto, max_capitulo=2000):
    """
    Dividir texto largo en capítulos manejables.
    Intenta respetar límites de párrafo.
    """
    capitulos = []
    
    # Dividir por líneas dobles (párrafos)
    parrafos = texto.split('\n\n')
    
    capitulo_actual = []
    longitud_actual = 0
    
    for parrafo in parrafos:
        parrafo = parrafo.strip()
        if not parrafo:
            continue
        
        if longitud_actual + len(parrafo) <= max_capitulo:
            capitulo_actual.append(parrafo)
            longitud_actual += len(parrafo)
        else:
            if capitulo_actual:
                capitulos.append('\n\n'.join(capitulo_actual))
            capitulo_actual = [parrafo]
            longitud_actual = len(parrafo)
    
    if capitulo_actual:
        capitulos.append('\n\n'.join(capitulo_actual))
    
    return [c for c in capitulos if c.strip()]


def generar_audiolibro_capitulos(
    texto,
    ref_audio,
    ref_text,
    output_dir,
    output_final,
    config,
    verbose=True
):
    """
    Generar audiolibro procesando por capítulos.
    """
    
    if verbose:
        print("="*60)
        print("📚 OmniBook - Procesador por Capítulos")
        print("="*60)
    
    # Verificar audio de referencia
    if not os.path.exists(ref_audio):
        print(f"❌ Error: Audio de referencia no encontrado: {ref_audio}")
        return False
    
    device = config.get("device", "cuda")
    num_step = config.get("num_step", 8)
    
    if device == "cuda" and not torch.cuda.is_available():
        print("⚠️  CUDA no disponible, usando CPU")
        device = "cpu"
    
    # Crear directorios
    os.makedirs(output_dir, exist_ok=True)
    output_dir_path = Path(output_dir)
    
    if verbose:
        print(f"\n📂 Directorio de salida: {output_dir}")
        print(f"🔧 Configuración:")
        print(f"   Dispositivo: {device}")
        print(f"   Pasos de difusión: {num_step}")
        print()
    
    # Dividir texto en capítulos
    capitulos = dividir_texto_en_capitulos(texto)
    
    if verbose:
        print(f"📖 Texto dividido en {len(capitulos)} capítulos\n")
    
    # Cargar modelo
    if verbose:
        print("🔄 Cargando modelo...")
    
    try:
        model = OmniVoice.from_pretrained(
            "k2-fsa/OmniVoice",
            device_map=device,
            dtype=torch.float16 if device == "cuda" else torch.float32
        )
        if verbose:
            print("✅ Modelo cargado\n")
    except Exception as e:
        print(f"❌ Error al cargar modelo: {e}")
        return False
    
    # Procesar cada capítulo
    archivos_generados = []
    tiempos = []
    
    for i, capitulo in enumerate(capitulos):
        capitulo_num = i + 1
        output_file = output_dir_path / f"capitulo_{capitulo_num:03d}.wav"
        
        if verbose:
            print(f"📖 Capítulo {capitulo_num}/{len(capitulos)}")
        
        start_time = time.time()
        
        try:
            kwargs = {
                "text": capitulo,
                "ref_audio": ref_audio,
                "ref_text": ref_text,
                "num_step": num_step,
            }
            
            if config.get("language_id"):
                kwargs["language_id"] = config["language_id"]
            if config.get("speed", 1.0) != 1.0:
                kwargs["speed"] = config["speed"]
            
            audio = model.generate(**kwargs)
            torchaudio.save(str(output_file), audio[0], 24000)
            
            elapsed = time.time() - start_time
            tiempos.append(elapsed)
            archivos_generados.append(str(output_file))
            
            if verbose:
                duracion = audio[0].shape[1] / 24000
                print(f"   ✅ {elapsed:.1f}s (audio: {duracion:.1f}s)")
                if device == "cuda":
                    vram = torch.cuda.memory_allocated() / 1e9
                    print(f"   💾 VRAM: {vram:.2f} GB\n")
                else:
                    print()
            
            # Liberar memoria
            torch.cuda.empty_cache() if device == "cuda" else None
            gc.collect()
            
        except Exception as e:
            print(f"❌ Error en capítulo {capitulo_num}: {e}")
            continue
    
    if not archivos_generados:
        print("❌ No se generó ningún capítulo")
        return False
    
    # Unir todos los capítulos
    if verbose:
        print("\n🔗 Uniendo capítulos...")
    
    try:
        audios = []
        for archivo in archivos_generados:
            audio, sr = torchaudio.load(archivo)
            audios.append(audio)
        
        audio_final = torch.cat(audios, dim=1)
        torchaudio.save(output_final, audio_final, 24000)
        
        if verbose:
            duracion_total = audio_final.shape[1] / 24000
            tiempo_total = sum(tiempos)
            
            print("\n" + "="*60)
            print("✅ ¡Audiolibro completado!")
            print("="*60)
            print(f"📁 Archivo final: {output_final}")
            print(f"📂 Capítulos individuales: {output_dir}/")
            print(f"⏱️  Duración total: {duracion_total:.1f}s ({duracion_total/60:.1f} min)")
            print(f"⏰ Tiempo de generación: {tiempo_total:.1f}s")
            print(f"📊 RTF: {tiempo_total/duracion_total:.2f}x")
            print(f"📖 Capítulos: {len(archivos_generados)}")
            print("="*60)
        
        return True
        
    except Exception as e:
        print(f"❌ Error al unir capítulos: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Procesar audiolibros por capítulos con OmniVoice"
    )
    
    parser.add_argument(
        "--input", "-i",
        type=str,
        required=True,
        help="Archivo de texto o directorio con capítulos"
    )
    parser.add_argument(
        "--ref_audio", "-r",
        type=str,
        required=True,
        help="Audio de referencia para clonación"
    )
    parser.add_argument(
        "--ref_text",
        type=str,
        default=None,
        help="Transcripción del audio de referencia"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output/capitulos",
        help="Directorio para capítulos individuales"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="output/audiolibro_completo.wav",
        help="Archivo final unido"
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="Archivo de configuración JSON"
    )
    parser.add_argument(
        "--num_step", "-n",
        type=int,
        default=8,
        choices=[4, 8, 16, 32],
        help="Pasos de difusión"
    )
    parser.add_argument(
        "--device", "-d",
        type=str,
        default="cuda",
        choices=["cuda", "cpu"],
        help="Dispositivo"
    )
    parser.add_argument(
        "--language_id", "-l",
        type=str,
        default="es",
        help="ID del idioma"
    )
    parser.add_argument(
        "--speed", "-s",
        type=float,
        default=1.0,
        help="Factor de velocidad"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Modo silencioso"
    )
    
    args = parser.parse_args()
    
    # Cargar texto
    if os.path.isfile(args.input):
        with open(args.input, 'r', encoding='utf-8') as f:
            texto = f.read()
    elif os.path.isdir(args.input):
        # Unir todos los archivos .txt del directorio
        archivos = sorted(Path(args.input).glob("*.txt"))
        if not archivos:
            print(f"❌ No se encontraron archivos .txt en {args.input}")
            sys.exit(1)
        
        textos = []
        for archivo in archivos:
            with open(archivo, 'r', encoding='utf-8') as f:
                textos.append(f.read())
        texto = '\n\n'.join(textos)
    else:
        print(f"❌ No se encontró: {args.input}")
        sys.exit(1)
    
    # Cargar configuración
    config = cargar_configuracion(args.config)
    config.update({
        "num_step": args.num_step,
        "device": args.device,
        "language_id": args.language_id,
        "speed": args.speed,
    })
    
    # Generar
    exito = generar_audiolibro_capitulos(
        texto=texto,
        ref_audio=args.ref_audio,
        ref_text=args.ref_text,
        output_dir=args.output_dir,
        output_final=args.output,
        config=config,
        verbose=not args.quiet
    )
    
    sys.exit(0 if exito else 1)


if __name__ == "__main__":
    main()
