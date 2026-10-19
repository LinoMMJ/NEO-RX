"""
Grad-CAM (Gradient-weighted Class Activation Mapping) para torchxrayvision ResNet-50.

El mapa de calor muestra los gradientes de la clase predicha respecto a los
feature maps de la capa convolucional final (layer4), evidenciando las regiones
anatómicas que determinaron el diagnóstico.

Referencia: Selvaraju et al. (2017), "Grad-CAM: Visual Explanations from
Deep Networks via Gradient-based Localization".
"""

import base64
import io
import hashlib
from collections import OrderedDict
from weakref import WeakKeyDictionary

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torchvision.models.resnet import ResNet


class GeneradorGradCAM:
    """Genera visualizaciones Grad-CAM para modelos ResNet de torchxrayvision."""

    @staticmethod
    def _capa_objetivo(modelo):
        """Retorna layer4 (2048 feature maps, 16×16 para entrada 512×512)."""
        try:
            return modelo.model.layer4
        except AttributeError:
            # Fallback: última nn.Sequential con Conv2d hijos
            ultima = None
            for _, modulo in modelo.named_modules():
                if isinstance(modulo, torch.nn.Sequential):
                    if any(isinstance(c, torch.nn.Conv2d) for c in modulo.modules()):
                        ultima = modulo
            if ultima is None:
                raise RuntimeError("No se encontró capa convolucional objetivo para Grad-CAM.")
            return ultima

    @classmethod
    def calcular(cls, modelo, tensor, indice_clase):
        """
        Calcula el mapa de activación Grad-CAM.

        tensor: [1,1,512,512] preparado por DetectorTorax._preprocesar
        Retorna numpy float32 [512,512] normalizado en [0,1].
        Las zonas de mayor valor (→1) son las más relevantes para la clase.
        """
        if cls._is_linear_resnet(modelo):
            # For ResNet's GAP -> Linear head, d(logit_c)/d(A_kij) is
            # exactly W_ck / (H*W). This is the same Grad-CAM as autograd,
            # without allocating a backward graph or running the CNN again.
            with torch.inference_mode():
                key = cls._tensor_key(tensor)
                entries = cls._features.get(modelo, {})
                features = entries.get(key)
                if features is None:
                    cls.forward(modelo, tensor.float())
                    features = cls._features[modelo][key]
                weights = modelo.model.fc.weight[indice_clase].reshape(1, -1, 1, 1)
                cam = (features * weights).sum(dim=1, keepdim=True)
                cam = cam / (features.shape[-2] * features.shape[-1])
                return cls._normalizar(cam)

        activaciones = {}
        capa = cls._capa_objetivo(modelo)

        h1 = capa.register_forward_hook(lambda m, i, o: activaciones.update({"f": o}))

        try:
            modelo.eval()
            # No se requiere gradiente respecto a la imagen ni a cada peso del
            # modelo. autograd.grad hasta la activación final corta el backward
            # allí: conserva el Grad-CAM correcto y evita recorrer toda ResNet.
            with torch.enable_grad():
                salida = modelo(tensor.float().detach().requires_grad_(True))
                gradientes_salida = torch.autograd.grad(
                    salida[0, indice_clase], activaciones["f"], retain_graph=False
                )[0]

            # Pesos = promedio global de los gradientes por canal (Eq. 1 del paper)
            pesos = gradientes_salida.mean(dim=[2, 3], keepdim=True)  # [1, 2048, 1, 1]
            # Mapa de calor = ReLU de la combinación lineal ponderada (Eq. 2)
            cam = F.relu((pesos * activaciones["f"]).sum(1, keepdim=True))  # [1,1,H,W]
            return cls._normalizar(cam)
        finally:
            h1.remove()

    @classmethod
    def get_centroide(cls, cam_np):
        """Retorna {'x': int, 'y': int} del centroide de mayor activación, o None."""
        cam_u8 = (cam_np * 255).astype(np.uint8)
        _, thresh = cv2.threshold(cam_u8, 200, 255, cv2.THRESH_BINARY)
        contornos, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contornos:
            c = max(contornos, key=cv2.contourArea)
            M = cv2.moments(c)
            if M["m00"] > 0:
                return {"x": int(M["m10"] / M["m00"]), "y": int(M["m01"] / M["m00"])}
        return None

    @classmethod
    def overlay_base64(cls, modelo, tensor, indice_clase, arr_original_2d, cam=None):
        """
        Superpone el mapa de calor JET sobre la radiografía original.

        arr_original_2d: float32 pixel array 2D sin normalizar (valores DICOM crudos)
        cam: cam_np pre-calculado para evitar recalcular (opcional)
        Retorna data:image/png;base64,...
        """
        if cam is None:
            cam = cls.calcular(modelo, tensor, indice_clase)

        img_norm = ((arr_original_2d - arr_original_2d.min()) /
                    (arr_original_2d.max() - arr_original_2d.min() + 1e-8) * 255).astype(np.uint8)
        # Match the center crop used by the model before resizing. Stretching
        # the full rectangular image displaces the heatmap anatomically.
        height, width = img_norm.shape
        side = min(height, width)
        top, left = (height - side) // 2, (width - side) // 2
        img_norm = img_norm[top:top + side, left:left + side]
        orig_rgb = cv2.cvtColor(img_norm, cv2.COLOR_GRAY2RGB)
        orig_rgb_resized = cv2.resize(orig_rgb, (512, 512))

        cam_u8 = (cam * 255).astype(np.uint8)
        heatmap_bgr = cv2.applyColorMap(cam_u8, cv2.COLORMAP_JET)
        heatmap_rgb = cv2.cvtColor(heatmap_bgr, cv2.COLOR_BGR2RGB)

        # Mezcla: 55% radiografía + 45% mapa de calor
        overlay = cv2.addWeighted(orig_rgb_resized, 0.55, heatmap_rgb, 0.45, 0)

        # Dibuja círculo en el centroide de mayor activación
        _, thresh = cv2.threshold(cam_u8, 200, 255, cv2.THRESH_BINARY)
        contornos, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contornos:
            c = max(contornos, key=cv2.contourArea)
            M = cv2.moments(c)
            if M["m00"] > 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                cv2.circle(overlay, (cx, cy), 18, (255, 255, 0), 2)
                cv2.circle(overlay, (cx, cy), 4, (255, 255, 0), -1)

        pil = Image.fromarray(overlay)
        buf = io.BytesIO()
        pil.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    @classmethod
    def overlay_solo_heatmap_base64(cls, modelo, tensor, indice_clase, cam=None):
        """Solo el heatmap JET sin la imagen, para el modo toggle 'solo calor'."""
        if cam is None:
            cam = cls.calcular(modelo, tensor, indice_clase)

        cam_u8 = (cam * 255).astype(np.uint8)
        heatmap_bgr = cv2.applyColorMap(cam_u8, cv2.COLORMAP_JET)
        heatmap_rgb = cv2.cvtColor(heatmap_bgr, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(heatmap_rgb)
        buf = io.BytesIO()
        pil.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    _features = WeakKeyDictionary()

    @staticmethod
    def _is_linear_resnet(modelo):
        return isinstance(getattr(modelo, "model", None), ResNet)

    @staticmethod
    def _tensor_key(tensor):
        array = tensor.detach().float().cpu().contiguous().numpy()
        return (array.shape, hashlib.sha256(array.tobytes()).digest())

    @classmethod
    def forward(cls, modelo, tensor):
        """Capture final features during prediction; bounded to four images/model.

        Call under DetectorTorax's inference lock. No patient identifiers or
        gradients are kept. A cached feature map also serves other classes.
        """
        if not cls._is_linear_resnet(modelo):
            return modelo(tensor)
        key = cls._tensor_key(tensor)
        captured = {}
        handle = modelo.model.layer4.register_forward_hook(
            lambda _m, _i, output: captured.update(features=output.detach())
        )
        try:
            output = modelo(tensor)
        finally:
            handle.remove()
        entries = cls._features.setdefault(modelo, OrderedDict())
        entries[key] = captured["features"]
        entries.move_to_end(key)
        while len(entries) > 4:
            entries.popitem(last=False)
        return output

    @staticmethod
    def _normalizar(cam):
        cam = F.interpolate(F.relu(cam), size=(512, 512), mode="bilinear", align_corners=False)
        array = cam.squeeze().detach().cpu().numpy()
        if not np.isfinite(array).all():
            raise ValueError("El mapa contiene valores no finitos.")
        return (array - array.min()) / (array.max() - array.min() + 1e-8)
