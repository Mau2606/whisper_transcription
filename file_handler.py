# audio_transcriber_flask_whisper/file_handler.py
import os
from docx import Document

def save_to_docx(text_content, output_docx_path):
    """
    Guarda el contenido de texto en un archivo DOCX.
    Reemplaza los saltos de línea con espacios para un texto continuo.
    """
    try:
        # Crear la carpeta de salida si no existe
        os.makedirs(os.path.dirname(output_docx_path), exist_ok=True)
        
        doc = Document()
        # Reemplazar saltos de línea con espacios para un texto continuo en el DOCX
        continuous_text = text_content.replace('\n', ' ').strip()
        doc.add_paragraph(continuous_text)
        doc.save(output_docx_path)
        print(f"Transcripción guardada en formato DOCX en: {output_docx_path}")
        return True
    except Exception as e:
        print(f"Error al guardar el archivo DOCX '{output_docx_path}': {e}")
        return False

def cleanup_temp_file(file_path):
    """Elimina un archivo temporal si existe."""
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"Archivo temporal '{file_path}' eliminado.")
        except Exception as e:
            print(f"Advertencia: No se pudo eliminar el archivo temporal '{file_path}': {e}")

def cleanup_temp_folder(folder_path):
    """Elimina una carpeta temporal y su contenido si existe."""
    if folder_path and os.path.exists(folder_path):
        try:
            # shutil.rmtree para eliminar la carpeta y todo su contenido
            import shutil
            shutil.rmtree(folder_path)
            print(f"Carpeta temporal '{folder_path}' eliminada.")
        except Exception as e:
            print(f"Advertencia: No se pudo eliminar la carpeta temporal '{folder_path}': {e}")

