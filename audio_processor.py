# audio_transcriber_flask_whisper/audio_processor.py
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError
import os
import tempfile
import shutil

# Importar file_handler para usar cleanup_temp_file si es necesario internamente,
# aunque es preferible que el вызывающий (app.py) maneje la limpieza si la función devuelve None.
# from . import file_handler # Si estuvieran en el mismo paquete y quisiéramos usarlo aquí

# Variable global para verificar si se mostró la advertencia de FFmpeg
ffmpeg_warning_shown = False

def ensure_ffmpeg_is_available():
    global ffmpeg_warning_shown
    if ffmpeg_warning_shown:
        return
    if shutil.which("ffmpeg") is None and shutil.which("avconv") is None:
        print("--------------------------------------------------------------------")
        print("ADVERTENCIA: FFmpeg (o Libav) no parece estar instalado o no está en el PATH del sistema.")
        # ... (resto del mensaje de advertencia) ...
        print("--------------------------------------------------------------------")
        ffmpeg_warning_shown = True
    else:
        ffmpeg_warning_shown = True
        # print("FFmpeg (o Libav) detectado. La conversión de audio debería funcionar.")


def load_slice_and_export_to_wav(input_audio_path, output_folder, start_ms=None, end_ms=None):
    """
    Carga un archivo de audio, opcionalmente lo recorta, y lo exporta a formato WAV.
    Guarda el archivo WAV en una subcarpeta 'temp_wav' dentro de output_folder.
    Retorna la ruta al archivo WAV temporal, o None si ocurre un error.
    """
    ensure_ffmpeg_is_available()
    
    filename = os.path.basename(input_audio_path)
    name, _ = os.path.splitext(filename)
    
    temp_wav_dir = os.path.join(output_folder, "temp_wav")
    os.makedirs(temp_wav_dir, exist_ok=True)
    
    temp_wav_file = tempfile.NamedTemporaryFile(
        suffix=".wav", 
        prefix=f"{name}_slice_",
        dir=temp_wav_dir, 
        delete=False 
    )
    temp_wav_path = temp_wav_file.name
    temp_wav_file.close()

    try:
        print(f"Cargando audio desde: '{input_audio_path}'...")
        audio = AudioSegment.from_file(input_audio_path)
        duration_ms = len(audio)
        print(f"Duración original del audio: {duration_ms / 1000.0:.2f} segundos.")

        actual_start_ms = 0
        if start_ms is not None:
            if not isinstance(start_ms, (int, float)) or start_ms < 0:
                print(f"Error: Tiempo de inicio ({start_ms}) inválido. Debe ser un número no negativo.")
                # os.remove(temp_wav_path) # Limpieza temprana
                return "invalid_start_time" 
            if start_ms >= duration_ms:
                print(f"Error: El tiempo de inicio ({start_ms / 1000.0:.2f}s) es mayor o igual a la duración del audio ({duration_ms / 1000.0:.2f}s).")
                # os.remove(temp_wav_path)
                return "start_time_out_of_bounds"
            actual_start_ms = int(start_ms)

        actual_end_ms = duration_ms
        if end_ms is not None:
            if not isinstance(end_ms, (int, float)) or end_ms <= 0:
                print(f"Error: Tiempo de fin ({end_ms}) inválido. Debe ser un número positivo.")
                # os.remove(temp_wav_path)
                return "invalid_end_time"
            if end_ms <= actual_start_ms:
                print(f"Error: El tiempo de fin ({end_ms / 1000.0:.2f}s) debe ser mayor que el tiempo de inicio ({actual_start_ms / 1000.0:.2f}s).")
                # os.remove(temp_wav_path)
                return "end_time_before_start_time"
            # No es un error si end_ms > duration_ms, pydub lo maneja recortando hasta el final.
            # Sin embargo, podemos ajustarlo para mayor claridad o consistencia.
            actual_end_ms = min(int(end_ms), duration_ms)
        
        sliced_audio = audio
        if actual_start_ms > 0 or actual_end_ms < duration_ms : # Solo recorta si es necesario
            if actual_start_ms >= actual_end_ms : # Verificación final por si acaso
                 print(f"Error: Intervalo de tiempo inválido después de los ajustes. Inicio: {actual_start_ms}, Fin: {actual_end_ms}")
                 # os.remove(temp_wav_path)
                 return "invalid_interval"

            print(f"Recortando audio desde {actual_start_ms / 1000.0:.2f}s hasta {actual_end_ms / 1000.0:.2f}s.")
            sliced_audio = audio[actual_start_ms:actual_end_ms]
        else:
            print("No se especificó recorte válido o el recorte cubre el audio completo. Procesando audio completo.")


        if len(sliced_audio) == 0:
            print("Error: El segmento de audio resultante del recorte tiene duración cero.")
            # os.remove(temp_wav_path)
            return "zero_length_slice"

        print(f"Duración del audio a procesar: {len(sliced_audio) / 1000.0:.2f} segundos.")
        sliced_audio.export(temp_wav_path, format="wav")
        print(f"Audio (potencialmente recortado) y convertido a WAV guardado en: {temp_wav_path}")
        return temp_wav_path
        
    except CouldntDecodeError:
        print(f"Error: No se pudo decodificar el archivo de audio '{input_audio_path}'.")
        # os.remove(temp_wav_path) # Asegurarse de que el archivo temporal se borre
        return "decode_error"
    except FileNotFoundError:
        print(f"Error: El archivo de entrada '{input_audio_path}' no fue encontrado.")
        # if os.path.exists(temp_wav_path): os.remove(temp_wav_path)
        return "file_not_found"
    except Exception as e:
        print(f"Error inesperado durante el procesamiento de audio: {e}")
        # if os.path.exists(temp_wav_path): os.remove(temp_wav_path)
        return "processing_error"
    finally:
        # La limpieza del temp_wav_path en caso de error DENTRO de esta función
        # puede ser complicada si la función retorna códigos de error string.
        # Es más robusto que el llamador (app.py) limpie el temp_wav_path si la función
        # no retorna una ruta válida. La función crea el archivo; el llamador gestiona su ciclo de vida.
        pass