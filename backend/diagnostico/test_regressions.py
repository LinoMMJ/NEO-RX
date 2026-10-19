import numpy as np
import pytest
import torch
from torch import nn
from torchvision.models import resnet18
from unittest.mock import patch

from diagnostico.gradcam import GeneradorGradCAM


def test_fast_gradcam_matches_autograd_and_reuses_features():
    """GAP + Linear optimization must preserve the actual Grad-CAM map."""
    torch.set_num_threads(1)
    torch.manual_seed(7)

    class Wrapper(nn.Module):
        def __init__(self):
            super().__init__()
            self.model = resnet18(weights=None, num_classes=3).eval()
            with torch.no_grad():
                self.model.fc.weight.abs_()

        def forward(self, tensor):
            return self.model(tensor)

    model = Wrapper().eval()
    tensor = torch.randn(1, 3, 64, 64)
    captured = {}
    hook = model.model.layer4.register_forward_hook(lambda m, i, o: captured.update(features=o))
    logits = model(tensor)
    features = captured['features']
    gradient = torch.autograd.grad(logits[0, 0], features)[0]
    expected = GeneradorGradCAM._normalizar((gradient.mean((2, 3), keepdim=True) * features).sum(1, keepdim=True))
    hook.remove()
    with torch.inference_mode():
        GeneradorGradCAM.forward(model, tensor)
    with patch.object(model, 'forward', side_effect=AssertionError('CNN should not run twice')):
        actual = GeneradorGradCAM.calcular(model, tensor, 0)
        assert np.allclose(actual, expected, atol=2e-6)
        assert np.isfinite(GeneradorGradCAM.calcular(model, tensor, 1)).all()
    assert not model.model.layer4._forward_hooks


@pytest.mark.django_db
def test_report_keeps_original_raster_after_new_image(auth_medico, imagen_con_resultado):
    from estudios.models import ImagenDICOM
    image = imagen_con_resultado
    image.archivo_dicom = 'dicom/original.jpg'
    image.save()
    response = auth_medico.post('/api/informes/generar/', {'estudio_id': image.estudio_id})
    assert response.status_code == 200
    report_id = response.data['id']
    assert response.data['imagen_png_url'].endswith('/media/dicom/original.jpg')
    assert response.data['imagen_origen'] == image.pk
    ImagenDICOM.objects.create(estudio=image.estudio, archivo_dicom='dicom/newer.png')
    detail = auth_medico.get(f'/api/informes/{report_id}/')
    assert detail.data['imagen_origen'] == image.pk
    assert detail.data['imagen_png_url'].endswith('/media/dicom/original.jpg')
    assert detail.data['probabilidades']['Neumonía'] == 0.85


@pytest.mark.django_db
def test_template_cannot_be_signed_without_completion(auth_medico, imagen_con_resultado):
    response = auth_medico.post('/api/informes/generar/', {'estudio_id': imagen_con_resultado.estudio_id})
    url = f"/api/informes/{response.data['id']}/"
    assert auth_medico.patch(url, {'estado': 'revisado'}).status_code == 200
    assert auth_medico.patch(url, {'estado': 'firmado'}).status_code == 400


@pytest.mark.django_db
def test_result_retains_validation_thresholds(auth_medico, imagen_con_resultado):
    result = imagen_con_resultado.resultado_cnn
    result.patologias = {
        'hallazgos': [{'etiqueta': 'Neumonía', 'etiqueta_en': 'Pneumonia',
                       'probabilidad_estimada': 0.42, 'threshold_usado': 0.4, 'detectado': True}],
        'thresholds': {'Pneumonia': 0.4}, 'resolucion_entrada': 512,
        'modelo': 'resnet50_finetuned_nih', 'es_fine_tuned': True,
    }
    result.save()
    data = auth_medico.get(f'/api/diagnostico/resultado/{imagen_con_resultado.pk}/').data
    assert data['hallazgos'][0]['detectado'] is True
    assert data['thresholds'] == {'Pneumonia': 0.4}
    assert data['resolucion_entrada'] == 512


@pytest.mark.django_db
def test_gradcam_rejects_result_from_another_resolution(auth_medico, imagen_con_resultado):
    result = imagen_con_resultado.resultado_cnn
    result.patologias = {'resolucion_entrada': 224, 'Neumonía': 0.85}
    result.save()
    with patch('diagnostico.views.DetectorTorax._finetuned_input_size', return_value=512), patch('diagnostico.views.DetectorTorax.cargar') as load:
        response = auth_medico.get('/api/diagnostico/gradcam/', {'imagen_id': imagen_con_resultado.pk, 'pathology': 'Pneumonia'})
    assert response.status_code == 409
    load.assert_not_called()


@pytest.mark.django_db
def test_gradcam_requires_completed_result(auth_medico, imagen_con_resultado):
    imagen_con_resultado.resultado_cnn.delete()
    with patch('diagnostico.views.DetectorTorax.cargar') as load:
        response = auth_medico.get('/api/diagnostico/gradcam/', {'imagen_id': imagen_con_resultado.pk, 'pathology': 'Pneumonia'})
    assert response.status_code == 409
    load.assert_not_called()


def test_signed_dicom_window_and_inversion_are_consistent():
    from pydicom.dataset import Dataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian
    from estudios.utils import dicom_display_pixels
    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.Rows, ds.Columns = 2, 2
    ds.BitsAllocated = ds.BitsStored = 16
    ds.HighBit, ds.PixelRepresentation, ds.SamplesPerPixel = 15, 1, 1
    ds.PhotometricInterpretation = 'MONOCHROME2'
    ds.PixelData = np.array([[-1000, -500], [500, 1000]], dtype=np.int16).tobytes()
    ds.WindowCenter, ds.WindowWidth = 0, 1000
    image = dicom_display_pixels(ds)
    assert image.dtype == np.uint8 and image.min() == 0 and image.max() == 255
    ds.PhotometricInterpretation = 'MONOCHROME1'
    np.testing.assert_array_equal(dicom_display_pixels(ds), 255 - image)
