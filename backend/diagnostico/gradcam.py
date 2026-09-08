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

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image


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
        activaciones = {}
        gradientes = {}
        capa = cls._capa_objetivo(modelo)

        h1 = capa.register_forward_hook(lambda m, i, o: activaciones.update({"f": o}))
        # register_full_backward_hook: go[0] son los gradientes del loss respecto
        # a la SALIDA de la capa (los feature maps), que es lo que necesita Grad-CAM
        h2 = capa.register_full_backward_hook(lambda m, gi, go: gradientes.update({"g": go[0]}))

        try:
            modelo.eval()
            tensor_grad = tensor.clone().float().requires_grad_(True)
            salida = modelo(tensor_grad)          # [1, 18] probabilidades
            modelo.zero_grad()
            salida[0, indice_clase].backward()    # gradientes para la clase objetivo

            # Pesos = promedio global de los gradientes por canal (Eq. 1 del paper)
            pesos = gradientes["g"].mean(dim=[2, 3], keepdim=True)  # [1, 2048, 1, 1]
            # Mapa de calor = ReLU de la combinación lineal ponderada (Eq. 2)
            cam = F.relu((pesos * activaciones["f"]).sum(1, keepdim=True))  # [1,1,H,W]
            cam = F.interpolate(cam, size=(512, 512), mode="bilinear", align_corners=False)
            cam_np = cam.squeeze().detach().cpu().numpy()
            cam_np = (cam_np - cam_np.min()) / (cam_np.max() - cam_np.min() + 1e-8)
            return cam_np
        finally:
            h1.remove()
            h2.remove()

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
