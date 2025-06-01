# audio_transcriber_flask_whisper/app.py
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
import os
import secrets
from werkzeug.utils import secure_filename
import whisper

# Importaciones de nuestros módulos
import audio_processor
import transcriber
import file_handler

app = Flask(__name__)

app.secret_key = secrets.token_hex(16) 

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(APP_ROOT, 'uploads')
TRANSCRIPTION_OUTPUT_FOLDER_DOCX = os.path.join(APP_ROOT, 'transcriptions_docx')
TEMP_WAV_OUTPUT_FOLDER = UPLOAD_FOLDER

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['TRANSCRIPTION_OUTPUT_FOLDER_DOCX'] = TRANSCRIPTION_OUTPUT_FOLDER_DOCX
app.config['TEMP_WAV_OUTPUT_FOLDER'] = TEMP_WAV_OUTPUT_FOLDER # Carpeta para WAVs temporales

ALLOWED_EXTENSIONS = {'wav', 'mp3', 'ogg', 'm4a', 'flac'} 

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TRANSCRIPTION_OUTPUT_FOLDER_DOCX, exist_ok=True)
os.makedirs(os.path.join(TEMP_WAV_OUTPUT_FOLDER, "temp_wav"), exist_ok=True)

WHISPER_MODEL_NAME = "base" 
try:
    whisper_transcriber = transcriber.WhisperTranscriber(model_name=WHISPER_MODEL_NAME)
except Exception as e:
    print(f"FALLO CRÍTICO: No se pudo inicializar WhisperTranscriber: {e}")
    whisper_transcriber = None 

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_time_to_ms(time_str):
    """Convierte una cadena HH:MM:SS a milisegundos. Retorna None si está vacía, 'invalid_format' si el formato es incorrecto."""
    if not time_str or not time_str.strip():
        return None
    try:
        parts = list(map(int, time_str.split(':')))
        if len(parts) != 3:
            raise ValueError("El formato debe ser HH:MM:SS")
        h, m, s = parts
        if not (0 <= h < 100 and 0 <= m < 60 and 0 <= s < 60): # H puede ser > 23 para duraciones
             raise ValueError("Valores de tiempo fuera de rango (H < 100, M < 60, S < 60).")
        return (h * 3600 + m * 60 + s) * 1000
    except ValueError as e:
        print(f"Error al parsear tiempo '{time_str}': {e}")
        return "invalid_format"

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if not whisper_transcriber:
            flash('Error: El servicio de transcripción no está disponible. Revisa la consola del servidor.', 'danger')
            return redirect(request.url)

        if 'audio_file' not in request.files:
            flash('No se seleccionó ningún archivo.', 'warning')
            return redirect(request.url)
        
        file = request.files['audio_file']
        
        if file.filename == '':
            flash('No se seleccionó ningún archivo.', 'warning')
            return redirect(request.url)
        
        uploaded_audio_path = None # Para asegurar la limpieza
        temp_wav_path_processed = None # Para el archivo WAV procesado

        if file and allowed_file(file.filename):
            original_filename = secure_filename(file.filename)
            random_hex = secrets.token_hex(8)
            _, f_ext = os.path.splitext(original_filename)
            secure_input_filename = random_hex + f_ext
            
            uploaded_audio_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_input_filename)
            file.save(uploaded_audio_path)
            
            flash(f"Archivo '{original_filename}' subido. Validando tiempos...", 'info')

            # Obtener y parsear tiempos de recorte
            start_time_str = request.form.get('start_time', '').strip()
            end_time_str = request.form.get('end_time', '').strip()

            start_ms = parse_time_to_ms(start_time_str)
            end_ms = parse_time_to_ms(end_time_str)

            error_messages = []
            if start_ms == "invalid_format":
                error_messages.append('Formato de tiempo de inicio inválido. Use HH:MM:SS.')
            if end_ms == "invalid_format":
                error_messages.append('Formato de tiempo de fin inválido. Use HH:MM:SS.')
            
            if start_ms is not None and start_ms != "invalid_format" and \
               end_ms is not None and end_ms != "invalid_format":
                if start_ms >= end_ms:
                    error_messages.append('El tiempo de inicio debe ser anterior al tiempo de fin.')

            if error_messages:
                for msg in error_messages:
                    flash(msg, 'danger')
                file_handler.cleanup_temp_file(uploaded_audio_path) # Limpiar el archivo subido si hay error de validación
                return redirect(request.url)

            flash("Tiempos validados. Procesando audio...", 'info')
            print(f"Archivo subido: {uploaded_audio_path}")
            print(f"Tiempos solicitados: Inicio MS: {start_ms}, Fin MS: {end_ms}")

            # Usar la nueva función que recorta y convierte
            # audio_processor.load_slice_and_export_to_wav retorna una ruta o un string de error
            processing_result = audio_processor.load_slice_and_export_to_wav(
                uploaded_audio_path,
                app.config['TEMP_WAV_OUTPUT_FOLDER'],
                start_ms=start_ms if isinstance(start_ms, int) else None, # Pasar None si es 'invalid_format' o vacío
                end_ms=end_ms if isinstance(end_ms, int) else None
            )
            
            # Verificar el resultado del procesamiento de audio
            if isinstance(processing_result, str) and not processing_result.endswith(".wav"):
                # Es un código de error de audio_processor
                error_map = {
                    "invalid_start_time": "Tiempo de inicio proporcionado es inválido.",
                    "start_time_out_of_bounds": "El tiempo de inicio está fuera de los límites del audio.",
                    "invalid_end_time": "Tiempo de fin proporcionado es inválido.",
                    "end_time_before_start_time": "El tiempo de fin es anterior o igual al tiempo de inicio.",
                    "invalid_interval": "El intervalo de tiempo para el recorte es inválido.",
                    "zero_length_slice": "El recorte resultó en un audio de duración cero. Verifica los tiempos.",
                    "decode_error": "No se pudo decodificar el archivo de audio. ¿Formato corrupto o no soportado?",
                    "file_not_found": "Archivo de audio no encontrado durante el procesamiento (inesperado).",
                    "processing_error": "Error inesperado durante el procesamiento del audio."
                }
                flash(error_map.get(processing_result, "Error desconocido al procesar el audio."), 'danger')
                file_handler.cleanup_temp_file(uploaded_audio_path)
                # temp_wav_path_processed podría no haberse creado o estar vacío, la limpieza general lo tomará.
                return redirect(request.url)
            else:
                temp_wav_path_processed = processing_result # Es una ruta válida a un WAV


            transcription_text = None
            if temp_wav_path_processed and os.path.exists(temp_wav_path_processed):
                print(f"Transcribiendo archivo WAV procesado: {temp_wav_path_processed}")
                transcription_text = whisper_transcriber.transcribe(temp_wav_path_processed, language="es")
            else:
                flash('Error: No se generó el archivo WAV para transcribir después del procesamiento.', 'danger')
            
            # Limpieza
            file_handler.cleanup_temp_file(uploaded_audio_path) # Siempre eliminar el archivo original subido
            if temp_wav_path_processed: # Eliminar el WAV temporal (recortado o completo)
                 file_handler.cleanup_temp_file(temp_wav_path_processed)
            
            temp_wav_folder_path = os.path.join(app.config['TEMP_WAV_OUTPUT_FOLDER'], "temp_wav")
            if os.path.exists(temp_wav_folder_path) and not os.listdir(temp_wav_folder_path):
                 file_handler.cleanup_temp_folder(temp_wav_folder_path)

            if transcription_text:
                flash('Transcripción completada!', 'success')
                rit_identifier = os.path.splitext(original_filename)[0]
                docx_filename = f"{rit_identifier}_transcripcion.docx"
                docx_output_path = os.path.join(app.config['TRANSCRIPTION_OUTPUT_FOLDER_DOCX'], docx_filename)
                
                file_handler.save_to_docx(transcription_text, docx_output_path)
                
                return render_template('result.html', 
                                       transcription=transcription_text, 
                                       docx_filename=docx_filename,
                                       original_filename=original_filename)
            else:
                # Si la transcripción es None pero no hubo error antes, es un error de Whisper
                if temp_wav_path_processed: # Solo si el WAV se procesó
                    flash('No se pudo transcribir el audio. El modelo Whisper pudo haber fallado.', 'danger')
                # Si temp_wav_path_processed fue None, el error ya se mostró.
                return redirect(request.url)
        else:
            flash('Tipo de archivo no permitido.', 'danger')
            return redirect(request.url)
            
    return render_template('index.html')

@app.route('/download_docx/<filename>')
def download_docx(filename):
    try:
        return send_from_directory(app.config['TRANSCRIPTION_OUTPUT_FOLDER_DOCX'], 
                                   filename, 
                                   as_attachment=True)
    except FileNotFoundError:
        flash('Archivo DOCX no encontrado.', 'danger')
        return redirect(url_for('index'))

if __name__ == '__main__':
    # audio_processor.ensure_ffmpeg_is_available() # Llamar una vez al inicio
    print("FFmpeg/Libav check will be performed by audio_processor module upon first conversion.")
    print(f"Modelos Whisper disponibles (ejemplos): {whisper.available_models()}")
    print("Aplicación Flask iniciándose. Accede en http://127.0.0.1:5000")
    app.run(debug=True) # debug=True es para desarrollo. Cambiar para producción.