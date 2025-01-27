from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('patient-data/step1/', views.step1, name='step1'),
    path('patient-data/step2/', views.step2, name='step2'),
    path('patient-data/step3/', views.step3, name='step3'),
    path('patient-data/step4/', views.step4, name='step4'),
    path('patient-data/summary/', views.summary, name='summary'), 
    path('process-guided-form/', views.process_guided_form, name='process_guided_form'),
    path('patient-data-fast/', views.patient_data_form_fast, name='patient_data_form_fast'),  
    path('success/', views.success_view, name='success'),
    path('download/', views.download_prediction_result, name='download_result'),
    path('predict/', views.predict_view, name='predict'),
    path('history/', views.prediction_history_view, name='history'),

]


