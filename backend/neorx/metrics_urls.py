from django.urls import path
from .views_metrics import MetricasOperacionalesView

urlpatterns = [
    path("operacionales/", MetricasOperacionalesView.as_view(), name="metricas-operacionales"),
]