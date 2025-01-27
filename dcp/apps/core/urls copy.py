from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('patient-data/', views.patient_data_form_guided, name='patient_data_form_guided'),  
    path('patient-data-fast/', views.patient_data_form_fast, name='patient_data_form_fast'),  
    path('success/', views.success_view, name='success'),
    path('download/', views.download_prediction_result, name='download_result'),
    path('predict/', views.predict_view, name='predict'),
    path('history/', views.prediction_history_view, name='history'),

]


