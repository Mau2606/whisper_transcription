# audio_transcriber_flask_whisper/transcriber.py
import whisper # pip install openai-whisper
import os

class WhisperTranscriber:
    def __init__(self, model_name="base"):
        """
        Inicializa el transcriptor Whisper.
        Args:
            model_name (str): Nombre del modelo Whisper a usar 
                              (e.g., "tiny", "base", "small", "medium", "large").
                              Modelos más grandes son más precisos pero más lentos y consumen más recursos.
        """
        print(f"Cargando modelo Whisper '{model_name}'...")
        try:
            self.model = whisper.load_model(model_name)
            print(f"Modelo Whisper '{model_name}' cargado exitosamente.")
        except Exception as e:
            print(f"Error al cargar el modelo Whisper '{model_name}': {e}")
            print("Asegúrate de tener PyTorch instalado y de que el nombre del modelo sea correcto.")
            print("Modelos disponibles: tiny, base, small, medium, large, o versiones específicas como base.en")
            # Podrías querer re-lanzar la excepción o manejarla de forma que la app no inicie.
            raise  # Re-lanzar para que la aplicación falle si el modelo no carga.

    def transcribe(self, audio_path, language="es"):
        """
        Transcribe el archivo de audio usando Whisper.
        Args:
            audio_path (str): Ruta al archivo de audio (WAV, MP3, etc., Whisper es flexible).
            language (str): Código del idioma para la transcripción (e.g., "es", "en").
                            Whisper puede auto-detectar, pero especificarlo puede mejorar la precisión.
        Returns:
            str: El texto transcrito, o None si ocurre un error.
        """
        if not os.path.exists(audio_path):
            print(f"Error de transcripción: El archivo de audio '{audio_path}' no existe.")
            return None
        
        print(f"Iniciando transcripción para '{audio_path}' con Whisper (idioma: {language})...")
        try:
            # Whisper puede tomar la ruta del archivo directamente.
            # La opción 'fp16=False' puede ser necesaria en CPUs sin soporte para half-precision.
            # Por defecto, Whisper intenta usar fp16 si CUDA está disponible.
            # result = self.model.transcribe(audio_path, language=language, fp16=False)
            result = self.model.transcribe(audio_path, language=language)
            
            transcribed_text = result["text"]
            print("Transcripción completada.")
            # print(f"Texto: {transcribed_text[:200]}...") # Imprime un fragmento
            return transcribed_text
        except Exception as e:
            print(f"Error durante la transcripción con Whisper: {e}")
            return None