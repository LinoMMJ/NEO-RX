"""
Validadores robustos para archivos DICOM y PNG.
Incluye validación de MIME type, tamaño, integridad y contenido.
"""

import os
import pydicom
from PIL import Image
from django.conf import settings
from django.core.exceptions import ValidationError


# Configuración por defecto (sobrescribible via settings)
DEFAULT_MAX_FILE_SIZE = getattr(settings, 'IMAGE_MAX_FILE_SIZE', 50 * 1024 * 1024)  # 50MB
ALLOWED_DICOM_MIME_TYPES = [
    'application/dicom',
    'application/octet-stream',  # Algunos DICOM vienen como octet-stream
]
ALLOWED_IMAGE_MIME_TYPES = [
    'image/png',
    'image/jpeg',
    'image/jpg',
    'image/webp',
]
ALLOWED_EXTENSIONS = ['.dcm', '.dicom', '.png', '.jpg', '.jpeg', '.webp']

# Umbral de borrosidad configurable
BLUR_THRESHOLD = getattr(settings, 'BLUR_THRESHOLD', 100.0)


class FileValidationError(ValidationError):
    """Excepción personalizada para errores de validación de archivos."""
    def __init__(self, message, code='invalid_file'):
        super().__init__(message, code=code)


def validate_file_extension(filename: str) -> None:
    """Valida que la extensión del archivo sea permitida."""
    import os
    ext = os.path.splitext(filename.lower())[1]
    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"Extensión '{ext}' no permitida. Extensiones permitidas: {', '.join(ALLOWED_EXTENSIONS)}",
            code='invalid_extension'
        )


def validate_file_size(file_obj) -> None:
    """Valida que el archivo no exceda el tamaño máximo permitido."""
    if getattr(file_obj, 'size', 0) == 0:
        raise FileValidationError('Archivo vacío.', code='empty_file')
    if hasattr(file_obj, 'size') and file_obj.size > getattr(settings, 'IMAGE_MAX_FILE_SIZE', DEFAULT_MAX_FILE_SIZE):
        max_mb = DEFAULT_MAX_FILE_SIZE / (1024 * 1024)
        actual_mb = file_obj.size / (1024 * 1024)
        raise FileValidationError(
            f"Archivo demasiado grande: {actual_mb:.1f}MB. Máximo permitido: {max_mb}MB",
            code='file_too_large'
        )


def validate_mime_type(file_obj, expected_types: list) -> str:
    """
    Valida el MIME type real del archivo usando firmas binarias portables, con validación posterior del contenido.
    Retorna el MIME type detectado.
    """
    file_obj.seek(0)
    header = file_obj.read(132)
    file_obj.seek(0)
    if header[128:132] == b'DICM':
        mime_type = 'application/dicom'
    elif header.startswith(b'\x89PNG\r\n\x1a\n'):
        mime_type = 'image/png'
    elif header.startswith(b'\xff\xd8\xff'):
        mime_type = 'image/jpeg'
    elif header.startswith(b'RIFF') and header[8:12] == b'WEBP':
        mime_type = 'image/webp'
    elif os.path.splitext(file_obj.name.lower())[1] in ['.dcm', '.dicom']:
        # Headerless DICOM must still pass structural and pixel decoding checks.
        mime_type = 'application/octet-stream'
    else:
        raise FileValidationError('Contenido de archivo no reconocido.', code='invalid_mime_type')
    extension_mimes = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp'}
    ext = os.path.splitext(file_obj.name.lower())[1]
    if ext in extension_mimes and extension_mimes[ext] != mime_type:
        raise FileValidationError('La extensión no corresponde al contenido.', code='invalid_extension')
    if mime_type not in expected_types:
        raise FileValidationError('El contenido no corresponde al tipo de archivo.', code='invalid_mime_type')
    return mime_type


def validate_dicom_integrity(file_obj) -> tuple:
    """
    Valida que el archivo DICOM sea legible y tenga estructura básica.
    Retorna (dataset, error_message) - si hay error, dataset es None.
    """
    file_obj.seek(0)
    try:
        # Usar force=True para leer DICOMs sin meta header
        ds = pydicom.dcmread(file_obj, force=True)
        file_obj.seek(0)

        # Validaciones básicas de estructura DICOM
        required_tags = ['SOPClassUID', 'SOPInstanceUID', 'StudyInstanceUID', 'Modality', 'Rows', 'Columns', 'PixelData']
        missing = [tag for tag in required_tags if not hasattr(ds, tag) or not getattr(ds, tag, None)]
        if missing:
            return None, f"DICOM incompleto: faltan tags requeridos: {', '.join(missing)}"

        # Verificar que es imagen médica
        if getattr(ds, 'Modality', '') not in ['CR', 'DX', 'RF', 'XA', 'XC']:
            # Advertencia pero no error - algunos equipos usan otros códigos
            pass

        pixels = ds.pixel_array
        if pixels.ndim != 2 or pixels.size == 0:
            return None, "Se requiere una imagen DICOM monocromática de un solo cuadro."
        return ds, None
    except pydicom.errors.InvalidDicomError as e:
        return None, f"Archivo DICOM inválido: {str(e)}"
    except Exception as e:
        return None, f"Error al leer DICOM: {str(e)}"


def validate_image_integrity(file_obj, mime_type: str) -> tuple:
    """
    Valida que el archivo de imagen (PNG/JPG/WebP) sea válido y legible.
    Retorna (imagen_pil, error_message).
    """
    file_obj.seek(0)
    try:
        img = Image.open(file_obj)
        img.verify()  # Verifica integridad
        file_obj.seek(0)
        img = Image.open(file_obj)
        img.load()
        file_obj.seek(0)

        # Validar dimensiones mínimas
        if img.width < 50 or img.height < 50:
            return None, "Imagen demasiado pequeña (mínimo 50x50 píxeles)"

        # Validar dimensiones máximas razonables
        if img.width > 10000 or img.height > 10000:
            return None, "Imagen demasiado grande (máximo 10000x10000 píxeles)"

        return img, None
    except Exception as e:
        return None, f"Archivo de imagen inválido o corrupto: {str(e)}"


def validate_file_comprehensive(file_obj, file_type: str = 'auto') -> dict:
    """
    Validación completa de un archivo subido por firma binaria y decodificación.

    Args:
        file_obj: Archivo subido (request.FILES['archivo'])
        file_type: 'dicom', 'image', o 'auto' para detectar automáticamente

    Returns:
        dict con resultado de validación:
        {
            'valid': bool,
            'file_type': 'dicom' | 'image',
            'mime_type': str,
            'dataset': pydicom.Dataset | None,  # solo para DICOM
            'pil_image': PIL.Image | None,      # solo para imágenes
            'errors': list[str],
            'warnings': list[str],
            'metadata': dict  # metadatos extraídos
        }
    """
    result = {
        'valid': True,
        'file_type': None,
        'mime_type': None,
        'dataset': None,
        'pil_image': None,
        'errors': [],
        'warnings': [],
        'metadata': {}
    }

    # 1. Validar extensión
    try:
        validate_file_extension(file_obj.name)
    except FileValidationError as e:
        result['valid'] = False
        result['errors'].append(str(e))
        return result

    # 2. Validar tamaño
    try:
        validate_file_size(file_obj)
    except FileValidationError as e:
        result['valid'] = False
        result['errors'].append(str(e))
        return result

    # 3. Detectar tipo si auto
    if file_type == 'auto':
        ext = os.path.splitext(file_obj.name.lower())[1]
        file_type = 'dicom' if ext in ['.dcm', '.dicom'] else 'image'

    # 4. Validar MIME type según tipo esperado
    expected_mimes = (
        ALLOWED_DICOM_MIME_TYPES if file_type == 'dicom'
        else ALLOWED_IMAGE_MIME_TYPES
    )

    try:
        mime = validate_mime_type(file_obj, expected_mimes)
        result['mime_type'] = mime
        result['file_type'] = file_type
    except FileValidationError as e:
        result['valid'] = False
        result['errors'].append(str(e))
        return result

    # 5. Validación específica por tipo
    if file_type == 'dicom':
        ds, error = validate_dicom_integrity(file_obj)
        if error:
            result['valid'] = False
            result['errors'].append(error)
        else:
            result['dataset'] = ds
            # Extraer metadatos útiles
            result['metadata'] = {
                'PatientName': str(getattr(ds, 'PatientName', '')),
                'PatientID': str(getattr(ds, 'PatientID', '')),
                'StudyDate': str(getattr(ds, 'StudyDate', '')),
                'StudyTime': str(getattr(ds, 'StudyTime', '')),
                'Modality': str(getattr(ds, 'Modality', '')),
                'Rows': getattr(ds, 'Rows', None),
                'Columns': getattr(ds, 'Columns', None),
                'PixelSpacing': str(getattr(ds, 'PixelSpacing', '')),
            }
    else:  # image
        img, error = validate_image_integrity(file_obj, result['mime_type'])
        if error:
            result['valid'] = False
            result['errors'].append(error)
        else:
            result['pil_image'] = img
            result['metadata'] = {
                'width': img.width,
                'height': img.height,
                'mode': img.mode,
                'format': img.format,
            }

    return result


def get_file_info(file_obj) -> dict:
    """Extrae información básica del archivo sin validación completa."""
    import os
    file_obj.seek(0, 2)  # seek al final
    size = file_obj.tell()
    file_obj.seek(0)

    ext = os.path.splitext(file_obj.name.lower())[1]

    return {
        'name': file_obj.name,
        'size': size,
        'size_mb': round(size / (1024 * 1024), 2),
        'extension': ext,
    }
