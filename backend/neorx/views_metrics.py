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

from datetime import datetime, timedelta
from django.db.models import Count, Avg, Q, F, ExpressionWrapper, fields
from django.db.models.functions import TruncDate, TruncHour
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
        dias = int(request.query_params.get("dias", 30))
        fecha_inicio = datetime.now().date() - timedelta(days=dias)

        # ──────────────────────────────────────────────────────────────────────
        # 1. Estudios por día
        # ──────────────────────────────────────────────────────────────────────
        estudios_por_dia = (
            Estudio.objects
            .filter(fecha__gte=fecha_inicio)
            .annotate(dia=TruncDate("fecha"))
            .values("dia")
            .annotate(total=Count("id"))
            .order_by("dia")
        )
        # Completar días sin datos
        dias_dict = {item["dia"]: item["total"] for item in estudios_por_dia}
        serie_estudios = []
        for i in range(dias):
            d = datetime.now().date() - timedelta(days=dias - 1 - i)
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
            .filter(estado="firmado", fecha_firmado__isnull=False, fecha_creacion__gte=fecha_inicio)
            .annotate(
                latencia=ExpressionWrapper(
                    F("fecha_firmado") - F("estudio__fecha"),
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
        total_estudios = Estudio.objects.filter(fecha__gte=fecha_inicio).count()
        # Un estudio está "completado" si tiene al menos un informe firmado
        completados = InformePreliminar.objects.filter(
            estudio__fecha__gte=fecha_inicio, estado="firmado"
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
            fecha_analisis__date__gte=fecha_inicio
        ).values_list("patologias", flat=True)
        for pats in resultados:
            if isinstance(pats, dict):
                for nombre, prob in pats.items():
                    if prob >= 0.15:  # umbral de mención
                        patologias_counter[nombre] += 1

        top_patologias = [
            {"nombre": k, "conteo": v}
            for k, v in patologias_counter.most_common(10)
        ]

        # ──────────────────────────────────────────────────────────────────────
        # 6. Estudios por hora (heatmap horario)
        # ──────────────────────────────────────────────────────────────────────
        estudios_por_hora = (
            Estudio.objects
            .filter(fecha__gte=fecha_inicio)
            .annotate(hora=TruncHour("fecha"))
            .values("hora")
            .annotate(total=Count("id"))
            .order_by("hora")
        )
        hora_dict = {item["hora"].hour: item["total"] for item in estudios_por_hora if item["hora"]}
        heatmap_hora = [{"hora": h, "total": hora_dict.get(h, 0)} for h in range(24)]

        # ──────────────────────────────────────────────────────────────────────
        # RESPUESTA
        # ──────────────────────────────────────────────────────────────────────
        return Response({
            "periodo_dias": dias,
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin": datetime.now().date().isoformat(),
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