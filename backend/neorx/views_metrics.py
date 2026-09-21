"""
API de métricas operativas para Dashboard.

GET /api/metrics/operacionales/

Retorna:
- Estudios por día (últimos 30 días)
- Latencia diagnóstico (p50, p95, p99)
- % completados vs pendientes
- Distribución por rol/usuario
- Top patologías detectadas
"""

from datetime import datetime, timedelta, date
from django.utils import timezone
from diagnostico.results import probabilities_es
from django.db.models import Count, Q, F, ExpressionWrapper
from django.db.models.functions import TruncHour
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from estudios.models import Estudio, ImagenDICOM
from diagnostico.models import ResultadoCNN
from accounts.models import CustomUser


class MetricasOperacionalesView(APIView):
    """
    Métricas operativas en tiempo real para dashboard administrativo/clínico.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Rango de fechas (default: últimos 30 días)
        try:
            dias = int(request.query_params.get("dias", 30))
            if not 1 <= dias <= 366:
                raise ValueError
        except (TypeError, ValueError):
            return Response({"error": "dias debe ser un entero entre 1 y 366."}, status=400)
        try:
            fecha_fin = date.fromisoformat(request.query_params.get("fecha_hasta", timezone.localdate().isoformat()))
            fecha_inicio = date.fromisoformat(request.query_params.get("fecha_desde", (fecha_fin - timedelta(days=dias - 1)).isoformat()))
            dias = (fecha_fin - fecha_inicio).days + 1
            if not 1 <= dias <= 366:
                raise ValueError
        except (TypeError, ValueError):
            return Response({"error": "Rango de fechas inválido; máximo 366 días."}, status=400)

        # ──────────────────────────────────────────────────────────────────────
        # 1. Estudios por día
        # Nota: `fecha` es DateField; agrupar directamente evita TruncDate sobre
        # DateField, que falla en SQLite con USE_TZ=True (P4).
        # ──────────────────────────────────────────────────────────────────────
        estudios_por_dia = (
            Estudio.objects
            .filter(fecha__range=(fecha_inicio, fecha_fin))
            .values("fecha")
            .annotate(total=Count("id"))
            .order_by("fecha")
        )
        # Completar días sin datos
        dias_dict = {item["fecha"]: item["total"] for item in estudios_por_dia}
        serie_estudios = []
        for i in range(dias):
            d = fecha_inicio + timedelta(days=i)
            serie_estudios.append({
                "fecha": d.isoformat(),
                "total": dias_dict.get(d, 0),
            })

        # ──────────────────────────────────────────────────────────────────────
        # 2. Latencia diagnóstico (tiempo entre estudio creado y informe firmado)
        # ──────────────────────────────────────────────────────────────────────
        from informes.models import InformePreliminar
        from django.db.models import DurationField

        latencia_qs = (
            InformePreliminar.objects
            .filter(estado="firmado", fecha_firmado__isnull=False, fecha_creacion__date__range=(fecha_inicio, fecha_fin))
            .annotate(
                latencia=ExpressionWrapper(
                    F("fecha_firmado") - F("estudio__created_at"),
                    output_field=DurationField()
                )
            )
            .values_list("latencia", flat=True)
        )

        latencias_horas = [float(l.total_seconds() / 3600) for l in latencia_qs if l]

        def percentil(arr, p):
            if not arr:
                return 0
            arr_sorted = sorted(arr)
            k = int(len(arr_sorted) * p / 100)
            return round(arr_sorted[min(k, len(arr_sorted) - 1)], 2)

        latencia_metrics = {
            "promedio": round(sum(latencias_horas) / len(latencias_horas), 2) if latencias_horas else 0,
            "p50": percentil(latencias_horas, 50),
            "p95": percentil(latencias_horas, 95),
            "p99": percentil(latencias_horas, 99),
            "muestras": len(latencias_horas),
        }

        # ──────────────────────────────────────────────────────────────────────
        # 3. % Completados vs Pendientes
        # ──────────────────────────────────────────────────────────────────────
        total_estudios = Estudio.objects.filter(fecha__range=(fecha_inicio, fecha_fin)).count()
        # Un estudio está "completado" si tiene al menos un informe firmado
        completados = InformePreliminar.objects.filter(
            estudio__fecha__range=(fecha_inicio, fecha_fin), estado="firmado"
        ).values("estudio").distinct().count()
        pendientes = total_estudios - completados

        # ──────────────────────────────────────────────────────────────────────
        # 4. Distribución por rol/usuario (solo admin ve esto)
        # ──────────────────────────────────────────────────────────────────────
        usuarios_por_rol = list(
            CustomUser.objects
            .filter(is_active=True)
            .values("rol")
            .annotate(total=Count("id"))
            .order_by("-total")
        )

        # ──────────────────────────────────────────────────────────────────────
        # 5. Top patologías detectadas (últimos N estudios con informe)
        # ──────────────────────────────────────────────────────────────────────
        from collections import Counter
        patologias_counter = Counter()
        resultados = ResultadoCNN.objects.filter(
            fecha_analisis__date__range=(fecha_inicio, fecha_fin)
        ).values_list("patologias", flat=True)
        for pats in resultados:
            if isinstance(pats, dict):
                for nombre, prob in probabilities_es(pats).items():
                    if prob >= 0.15:  # umbral de mención
                        patologias_counter[nombre] += 1

        top_patologias = [
            {"nombre": k, "conteo": v}
            for k, v in patologias_counter.most_common(10)
        ]

        # ──────────────────────────────────────────────────────────────────────
        # 6. Estudios por hora (heatmap horario)
        # Nota: `fecha` es DateField y no tiene hora; usar `created_at`
        # (DateTimeField) para la distribución horaria (P4).
        # ──────────────────────────────────────────────────────────────────────
        estudios_por_hora = (
            Estudio.objects
            .filter(created_at__date__range=(fecha_inicio, fecha_fin))
            .annotate(hora=TruncHour("created_at"))
            .values("hora")
            .annotate(total=Count("id"))
            .order_by("hora")
        )
        from collections import defaultdict
        hora_dict = defaultdict(int)
        for item in estudios_por_hora:
            if item["hora"]:
                hora_dict[item["hora"].hour] += item["total"]
        heatmap_hora = [{"hora": h, "total": hora_dict.get(h, 0)} for h in range(24)]

        # ──────────────────────────────────────────────────────────────────────
        # RESPUESTA
        # ──────────────────────────────────────────────────────────────────────
        return Response({
            "metricas_cnn": {"estado": "pendiente", "detail": "Resultado pendiente de ejecución experimental."},
            "periodo_dias": dias,
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin": fecha_fin.isoformat(),
            "estudios_por_dia": serie_estudios,
            "latencia_diagnostico": latencia_metrics,
            "completitud": {
                "total": total_estudios,
                "completados": completados,
                "pendientes": pendientes,
                "porcentaje_completados": round(100 * completados / total_estudios, 1) if total_estudios else 0,
            },
            "usuarios_por_rol": usuarios_por_rol,
            "top_patologias": top_patologias,
            "estudios_por_hora": heatmap_hora,
            "timestamp": datetime.now().isoformat(),
        })
