import os
import io
import joblib
import numpy as np
from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.shortcuts import redirect, render
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet

from .forms import PatientDataForm
from .models import PredictionHistory
from .predict_model import predict_tumor_category


### Funciones Auxiliares ###

def generate_pdf_data(patient_data, prediction_result, prediction_proba):
    """
    Genera un diccionario con los datos ingresados por el usuario y los resultados de la predicción.
    """
    factors = [
        ("Fuma", patient_data.SMOKING),
        ("Dedos amarillos", patient_data.YELLOW_FINGERS),
        ("Ansiedad", patient_data.ANXIETY),
        ("Presión de pares", patient_data.PEER_PRESSURE),
        ("Enfermedad crónica", patient_data.CHRONIC_DISEASE),
        ("Fatiga", patient_data.FATIGUE),
        ("Alergia", patient_data.ALLERGY),
        ("Silbido en el pecho", patient_data.WHEEZING),
        ("Consumo de alcohol", patient_data.ALCOHOL_CONSUMING),
        ("Tos", patient_data.COUGHING),
        ("Dificultad para respirar", patient_data.SHORTNESS_OF_BREATH),
        ("Dificultad para tragar", patient_data.SWALLOWING_DIFFICULTY),
        ("Dolor en el pecho", patient_data.CHEST_PAIN),
    ]
    positive_factors = [name for name, value in factors if value == 1]

    return {
        "AGE": patient_data.AGE,
        "GENDER": "Masculino" if patient_data.GENDER == 1 else "Femenino",
        "positive_factors": positive_factors,
        "prediction_result": (
            "Usted tiene una alta probabilidad de presentar cáncer de pulmón. "
            "Le recomendamos que consulte a un médico." if prediction_result == 1 else
            "Es poco probable que usted tenga cáncer de pulmón. Sin embargo, le recomendamos "
            "que consulte a un médico si tiene alguna preocupación."
        ),
        "prediction_proba": prediction_proba * 100,  # Convertir a porcentaje
    }


### Vistas Principales ###

def patient_data_form_guided(request):
    """
    Vista para manejar el formulario guiado por pasos.
    """
    current_step = int(request.GET.get('step', 1))
    total_steps = 7

    if not request.session.get('patient_data'):
        request.session['patient_data'] = {}
        print("Inicializando datos de sesión para patient_data")

    session_data = request.session['patient_data']
    print(f"Paso actual: {current_step}, Datos en sesión: {session_data}")

    if request.method == 'POST':
        form = PatientDataForm(request.POST)
        if form.is_valid():
            session_data.update(form.cleaned_data)
            request.session['patient_data'] = session_data

            if current_step == total_steps:
                final_form = PatientDataForm(session_data)
                if final_form.is_valid():
                    final_form.save()
                    del request.session['patient_data']
                    return redirect('core:success')
                else:
                    return render(request, 'core/patient_data_form_guided.html', {
                        'form': final_form,
                        'current_step': current_step,
                        'total_steps': total_steps,
                    })

            return redirect(f"{request.path}?step={current_step + 1}")
        else:
            print(f"Errores en el formulario: {form.errors}")
            return render(request, 'core/patient_data_form_guided.html', {
                'form': form,
                'current_step': current_step,
                'total_steps': total_steps,
            })

    initial_data = session_data if current_step > 1 else None
    form = PatientDataForm(initial=initial_data)
    return render(request, 'core/patient_data_form_guided.html', {
        'form': form,
        'current_step': current_step,
        'total_steps': total_steps,
    })


def patient_data_form_fast(request):
    """
    Vista para el formulario rápido de datos del paciente.
    """
    form = PatientDataForm()
    model_path = os.path.join(os.path.dirname(__file__), 'modelo_random_forest.pkl')

    try:
        model = joblib.load(model_path)
    except FileNotFoundError:
        print("Modelo no encontrado.")
        model = None

    if request.method == 'POST':
        form = PatientDataForm(request.POST)
        if form.is_valid() and model:
            patient_data = form.save()

            data = np.array([[  
                patient_data.GENDER, patient_data.AGE, patient_data.SMOKING, patient_data.YELLOW_FINGERS,
                patient_data.ANXIETY, patient_data.PEER_PRESSURE, patient_data.CHRONIC_DISEASE, patient_data.FATIGUE,
                patient_data.ALLERGY, patient_data.WHEEZING, patient_data.ALCOHOL_CONSUMING, patient_data.COUGHING,
                patient_data.SHORTNESS_OF_BREATH, patient_data.SWALLOWING_DIFFICULTY, patient_data.CHEST_PAIN
            ]])

            prediction_result = model.predict(data)[0]
            prediction_proba = model.predict_proba(data)[0][1]
            if prediction_proba == 1:
                prediction_proba = 0.9997
            elif prediction_proba == 0:
                prediction_proba = 0.0001
            

            pdf_data = generate_pdf_data(patient_data, prediction_result, prediction_proba)
            request.session.update(pdf_data)

            return render(request, 'core/prediction_result.html', {
                'form': form,
                'prediction_result': prediction_result,
                'prediction_proba': prediction_proba * 100,
                'positive_factors': pdf_data["positive_factors"],
                'pdf_data': pdf_data,
            })

    return render(request, 'core/patient_data_form_fast.html', {'form': form})


def predict_view(request):
    if request.method == 'POST' and request.FILES.get('image'):
        # Obtener la imagen cargada
        image = request.FILES['image']

        # Convertir la imagen en un objeto BytesIO
        image_bytes = io.BytesIO(image.read())

        # Realizar predicción
        result = predict_tumor_category(image_bytes)

        # Depurar para confirmar la estructura de probabilities
        print("Result probabilities:", result['probabilities'])

        # Multiplicar y redondear las probabilidades por 100
        probabilities = [round(float(p) * 100, 2) for p in result['probabilities'][0]]
        print("Processed probabilities:", probabilities)

        # Guardar predicción automáticamente en la base de datos
        prediction = PredictionHistory.objects.create(
            image=image,
            predicted_class=result['class'],
            probabilities=result['probabilities'],
        )

        # Renderizar resultados
        return render(request, 'core/predict_results.html', {
            'class': result['class'],
            'probabilities': probabilities,  # Asegúrate de pasar esto al template
            'uploaded_image_url': prediction.image.url,
        })

    return render(request, 'core/predict.html')



def download_prediction_result(request):
    # Recuperar datos de la sesión
    age = request.session.get("AGE", "N/A")
    gender = request.session.get("GENDER", "N/A")
    positive_factors = request.session.get("positive_factors", [])
    prediction_result = request.session.get("prediction_result", "N/A")
    prediction_proba = request.session.get("prediction_proba", 0.0)

    # Crear un objeto HttpResponse con contenido PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="resultado_prediccion.pdf"'

    # Crear un PDF con ReportLab
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)

    # Título del informe
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(100, 750, "Informe de Resultados de la Predicción")

    # Datos ingresados
    pdf.setFont("Helvetica", 12)
    pdf.drawString(100, 720, f"Edad: {age}")
    pdf.drawString(100, 700, f"Género: {gender}")
    pdf.drawString(100, 680, "Factores de riesgo positivos:")
    y = 660
    for factor in positive_factors:
        pdf.drawString(120, y, f"- {factor}")
        y -= 20

    # Resultado de la predicción con ajuste de texto
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import getSampleStyleSheet

    styles = getSampleStyleSheet()
    normal_style = styles['Normal']

    prediction_paragraph = Paragraph(f"Resultado de la predicción: {prediction_result}", normal_style)
    probability_paragraph = Paragraph(f"Probabilidad de padecer cáncer de pulmón: {prediction_proba}%", normal_style)

    prediction_paragraph.wrapOn(pdf, 400, 100)
    prediction_paragraph.drawOn(pdf, 100, y - 10)

    probability_paragraph.wrapOn(pdf, 400, 100)
    probability_paragraph.drawOn(pdf, 100, y - 50)

    # Ajustar posición del gráfico
    y_graph = y - 250

    try:
        # Convertir prediction_proba a float y validar
        proba_value = float(prediction_proba)
        if not (0 <= proba_value <= 100):
            raise ValueError(f"El valor de prediction_proba no está en el rango esperado: {proba_value}")

        # Crear el gráfico
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

        fig = Figure(figsize=(4, 4))
        ax = fig.add_subplot(111)
        ax.pie(
            [proba_value, 100 - proba_value],
            labels=["Probabilidad", "Resto"],
            colors=["#007BFF", "#D8D8D8"],
            autopct='%1.1f%%',
        )
        ax.set_title("Probabilidad de Padecer Cáncer")

        # Convertir el gráfico a imagen
        canvas_graph = FigureCanvas(fig)
        img_buffer = io.BytesIO()
        canvas_graph.print_png(img_buffer)
        img_buffer.seek(0)

        # Añadir el gráfico como imagen al PDF
        pdf.drawImage(ImageReader(img_buffer), 100, y_graph, width=200, height=200)

    except ValueError as ve:
        print(f"Error de conversión o rango inválido: {ve}")
        pdf.drawString(100, y_graph, "Gráfico no disponible: Datos inválidos.")
    except Exception as e:
        print(f"Error inesperado al generar el gráfico: {e}")
        pdf.drawString(100, y_graph, "Gráfico no disponible por datos insuficientes.")

    # Finalizar y guardar el PDF
    pdf.showPage()
    pdf.save()

    # Configurar la respuesta
    buffer.seek(0)
    response.write(buffer.getvalue())
    buffer.close()

    return response



def prediction_history_view(request):
    """
    Vista para mostrar el historial de predicciones.
    """
    predictions = PredictionHistory.objects.all().order_by('-created_at')
    return render(request, 'core/history.html', {'predictions': predictions})


def success_view(request):
    """
    Vista de éxito.
    """
    return render(request, 'core/success.html')
