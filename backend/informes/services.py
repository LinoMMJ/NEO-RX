"""Servicios de persistencia de informes preliminares."""

from .models import InformePreliminar


def create_ai_draft_report(estudio, imagen, resultado_cnn, medico=None):
    """Crea una sola vez el borrador ligado a un estudio toracico analizado."""
    if not imagen.apta_para_cnn:
        raise ValueError("Solo una radiografia de torax analizada puede generar informe.")

    from .views import (
        generar_impresion,
        generar_correlacion_clinica,
        generar_recomendaciones,
        generar_texto_hallazgos,
    )

    informe, created = InformePreliminar.objects.get_or_create(estudio=estudio, defaults={"imagen_origen": imagen})
    if created:
        proyeccion = imagen.tipo_proyeccion or "PA"
        calidad = "adecuada" if imagen.es_nitida else "limitada por borrosidad"
        informe.tecnica = (
            f"Radiografia de Torax {proyeccion}. Tecnica digital con detector "
            f"de panel plano. Calidad tecnica {calidad}."
        )
        informe.hallazgos = generar_texto_hallazgos(resultado_cnn, proyeccion)
        informe.correlacion_clinica = generar_correlacion_clinica()
        informe.impresion = generar_impresion(resultado_cnn)
        informe.recomendaciones = generar_recomendaciones(resultado_cnn)
    if medico is not None and getattr(medico, "rol", None) == "medico" and informe.medico_id is None:
        informe.medico = medico
    if created or informe.medico_id:
        informe.save()
    return informe, created
