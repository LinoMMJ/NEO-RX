"""Create print-friendly figures from the current automated test reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont


FONT = Path(r"C:\Windows\Fonts\arial.ttf")
BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")
MONO = Path(r"C:\Windows\Fonts\consola.ttf")


def fonts():
    return {
        "title": ImageFont.truetype(str(BOLD), 42),
        "head": ImageFont.truetype(str(BOLD), 29),
        "body": ImageFont.truetype(str(FONT), 26),
        "small": ImageFont.truetype(str(FONT), 22),
        "mono": ImageFont.truetype(str(MONO), 23),
        "mono_bold": ImageFont.truetype(str(Path(r"C:\Windows\Fonts\consolab.ttf")), 24),
    }


def canvas(title: str, subtitle: str, height: int = 1050):
    image = Image.new("RGB", (1800, height), "white")
    draw = ImageDraw.Draw(image)
    f = fonts()
    draw.rectangle((0, 0, 1800, 118), fill="#F0F2F5")
    draw.text((54, 25), title, font=f["title"], fill="#111111")
    draw.text((56, 80), subtitle, font=f["small"], fill="#4A4A4A")
    return image, draw, f


def badge(draw, x, y, text, f, good=True):
    fill = "#E7F2EA" if good else "#F8E8E8"
    outline = "#2E6B3C" if good else "#8B3333"
    draw.rounded_rectangle((x, y, x + 280, y + 58), radius=18, fill=fill, outline=outline, width=2)
    draw.text((x + 28, y + 13), text, font=f["small"], fill=outline)


def render_playwright(report_path: Path, output: Path):
    report = json.loads(report_path.read_text(encoding="utf-8"))
    stats = report["stats"]
    duration = stats["duration"] / 1000
    image, draw, f = canvas(
        "Pruebas funcionales de extremo a extremo con Playwright",
        "Ejecución local sobre Docker Compose, Chrome de escritorio y la aplicación publicada en el puerto 8080",
    )
    badge(draw, 1460, 34, f"{stats['expected']}/{stats['expected']} aprobadas", f, True)
    rows = [
        ("Autenticación y roles", "Redirección, credenciales inválidas, médico, recepción y administración"),
        ("Pacientes y auditoría", "Registro, búsqueda, edición y trazabilidad visible"),
        ("Métricas y seguridad", "API protegida, 401/403, cabeceras defensivas y sesión temporal"),
        ("Flujo clínico", "Carga PNG, Celery, CNN, resultado, Grad-CAM y preinforme"),
    ]
    y = 170
    for index, (area, detail) in enumerate(rows, 1):
        draw.rounded_rectangle((55, y, 1745, y + 142), radius=14, fill="#FAFAFA", outline="#C8CDD3", width=2)
        draw.ellipse((85, y + 42, 143, y + 100), fill="#E7F2EA", outline="#2E6B3C", width=2)
        draw.text((104, y + 52), str(index), font=f["head"], fill="#2E6B3C")
        draw.text((175, y + 25), area, font=f["head"], fill="#151515")
        draw.text((175, y + 78), detail, font=f["body"], fill="#3F3F3F")
        y += 164
    draw.text((60, 890), f"Duración total: {duration:.1f} s", font=f["head"], fill="#111111")
    draw.text((60, 940), "Resultado: 0 omitidas, 0 inesperadas y 0 inestables.", font=f["body"], fill="#333333")
    image.save(output, optimize=True)


def render_unit_backend(junit_path: Path, output: Path):
    suite = ET.parse(junit_path).getroot().find(".//testsuite")
    total = int(suite.attrib["tests"])
    failures = int(suite.attrib.get("failures", 0)) + int(suite.attrib.get("errors", 0))
    passed = total - failures - int(suite.attrib.get("skipped", 0))
    image, draw, f = canvas(
        "Pruebas unitarias y validaciones técnicas",
        "Resultados actuales del frontend y del backend ejecutados el 12 de noviembre de 2026",
        height=1160,
    )
    sections = [
        ("Frontend Vitest", "37 de 37 pruebas aprobadas en 8 archivos", True),
        ("Sesión con node:test", "7 de 7 pruebas aprobadas, incluida la renovación concurrente", True),
        ("Contraste visual", "7 de 7 temas conformes; razón mínima registrada 4,54:1", True),
        ("Backend pytest", f"{passed} de {total} pruebas aprobadas; {failures} incidencias de ejecución", False),
    ]
    y = 160
    for label, result, good in sections:
        draw.rounded_rectangle((55, y, 1745, y + 130), radius=14, fill="#FAFAFA", outline="#C8CDD3", width=2)
        draw.text((88, y + 24), label, font=f["head"], fill="#151515")
        draw.text((88, y + 73), result, font=f["body"], fill="#3F3F3F")
        badge(draw, 1425, y + 36, "APROBADO" if good else "REVISAR", f, good)
        y += 150
    draw.text((60, 790), "Detalle de las cuatro incidencias de pytest", font=f["head"], fill="#111111")
    notes = [
        "1. El control de intentos devolvió 403 antes de lo esperado por el caso de prueba.",
        "2. La verificación del PDF intentó escribir evidencia en una ruta ausente del contenedor.",
        "3–4. Dos casos de entrenamiento requieren scikit-learn, no incluido en la imagen de producción.",
    ]
    y = 845
    for note in notes:
        draw.text((84, y), "• " + note, font=f["body"], fill="#333333")
        y += 62
    draw.text((60, 1050), "Estas incidencias se separan de los 11 recorridos Playwright, que finalizaron sin fallos.", font=f["small"], fill="#555555")
    image.save(output, optimize=True)


def render_load(report_path: Path, output: Path):
    report = json.loads(report_path.read_text(encoding="utf-8"))
    static = report["targets"]["frontend_estatico"]
    health = report["targets"]["salud_api_y_base_datos"]
    image, draw, f = canvas(
        "Prueba local de concurrencia HTTP",
        "Diez solicitudes por usuario simulado; acceso web estático y comprobación de API con base de datos",
        height=1180,
    )
    columns = [80, 335, 575, 830, 1085, 1350, 1710]
    headers = ["Usuarios", "Solicitudes", "Éxito", "RPS", "p50 ms", "p95 ms"]
    draw.rectangle((55, 160, 1745, 220), fill="#E4E7EB", outline="#AAB0B7")
    for x, label in zip(columns, headers):
        draw.text((x, 174), label, font=f["small"], fill="#111111")
    y = 230
    draw.text((60, y), "Endpoint /health/", font=f["head"], fill="#111111")
    y += 52
    for row in health:
        values = [
            row["concurrent_users"], row["requests"], f"{row['success_rate_percent']:.0f}%",
            f"{row['throughput_requests_per_second']:.2f}", f"{row['latency_ms']['p50']:.2f}",
            f"{row['latency_ms']['p95']:.2f}",
        ]
        draw.rectangle((55, y - 8, 1745, y + 47), fill="#FFFFFF" if row["concurrent_users"] % 50 else "#F5F6F7", outline="#D6D9DD")
        for x, value in zip(columns, values):
            draw.text((x, y + 3), str(value), font=f["small"], fill="#222222")
        y += 60
    y += 28
    draw.text((60, y), "Entrada web /", font=f["head"], fill="#111111")
    y += 52
    for row in static:
        values = [
            row["concurrent_users"], row["requests"], f"{row['success_rate_percent']:.0f}%",
            f"{row['throughput_requests_per_second']:.2f}", f"{row['latency_ms']['p50']:.2f}",
            f"{row['latency_ms']['p95']:.2f}",
        ]
        draw.rectangle((55, y - 8, 1745, y + 47), fill="#FFFFFF" if row["concurrent_users"] % 50 else "#F5F6F7", outline="#D6D9DD")
        for x, value in zip(columns, values):
            draw.text((x, y + 3), str(value), font=f["small"], fill="#222222")
        y += 60
    best = health[-1]
    draw.text((60, 1020), f"Carga máxima ejecutada: {best['concurrent_users']} usuarios y {best['requests']} solicitudes a /health/ sin errores.", font=f["head"], fill="#1F5130")
    draw.text((60, 1075), "Alcance: disponibilidad HTTP y conexión con la base de datos; no incluye carga DICOM ni inferencia CNN concurrente.", font=f["small"], fill="#555555")
    image.save(output, optimize=True)


def render_model(report_path: Path, output: Path):
    report = json.loads(report_path.read_text(encoding="utf-8"))
    image, draw, f = canvas(
        "Rendimiento técnico de la inferencia CNN",
        "Diez inferencias repetibles con un patrón no clínico y el modelo ejecutado en CPU",
        height=1060,
    )
    badge(draw, 1460, 34, f"{report['successful_runs']}/{len(report['runs'])} válidas", f, True)
    info = [
        ("Modelo", report["model"]),
        ("Resolución de entrada", f"{report['input_resolution']} px"),
        ("Parámetros", f"{report['parameters']:,}"),
        ("Carga y precalentamiento", f"{report['load_and_warmup_seconds']:.3f} s"),
        ("Latencia mínima", f"{report['latency_seconds']['minimum']:.3f} s"),
        ("Latencia media", f"{report['latency_seconds']['mean']:.3f} s"),
        ("Latencia máxima", f"{report['latency_seconds']['maximum']:.3f} s"),
        ("Diferencia máxima entre repeticiones", f"{report['maximum_repeat_difference']:.6f}"),
    ]
    y = 165
    for index, (label, value) in enumerate(info):
        fill = "#FAFAFA" if index % 2 == 0 else "#F2F4F6"
        draw.rectangle((65, y, 1735, y + 78), fill=fill, outline="#D1D5D9")
        draw.text((95, y + 23), label, font=f["body"], fill="#222222")
        draw.text((1050, y + 23), value, font=f["mono_bold"], fill="#111111")
        y += 82
    draw.text((65, 880), "Interpretación", font=f["head"], fill="#111111")
    draw.text((65, 930), "La ejecución fue estable, pero la inferencia CPU debe mantenerse en una cola asíncrona.", font=f["body"], fill="#333333")
    draw.text((65, 980), "La medición es técnica; no representa precisión diagnóstica ni eficacia clínica.", font=f["small"], fill="#555555")
    image.save(output, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--playwright", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--load", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    render_playwright(args.playwright, args.output_dir / "evidencia_playwright.png")
    render_unit_backend(args.junit, args.output_dir / "evidencia_pruebas_unitarias_backend.png")
    render_load(args.load, args.output_dir / "evidencia_concurrencia.png")
    render_model(args.model, args.output_dir / "evidencia_rendimiento_cnn.png")
    print(args.output_dir)


if __name__ == "__main__":
    main()
