"""
URL configuration for doctors_appointment project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from appointment import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.homepage, name='home'), 
    path('services', views.servicespage, name='services'), 
    path('doctors', views.doctorspage, name='doctors'),
    path('about', views.aboutpage, name='about'),
    path('contact', views.contactpage, name='contact'),
    path('register', views.registerpage, name='register'),
    path('login', views.loginpage, name='login'),
    path('logout', views.logoutpage, name='logout'),
    path('initiate_booking', views.initiate_booking, name='initiate_booking'),
    path('book_appointment', views.doctorbook_appointment, name='book_appointment'),
    path('user_dashboard', views.user_dashboardpage, name='user_dashboard'),
    path('user_profile', views.user_profilepage, name='user_profile'),
    path('edit_userprofilepage', views.edit_userprofilepage, name='edit_userprofilepage'),
    path('doctor_editprofile', views.doctor_editprofilepage, name='doctor_editprofile'),
    # path('doctors_editprofile', views.edit_doctorsprofilepage, name='doctors_editprofile'),
    path('doctors_dashboard', views.doctors_dashboardpage, name='doctors_dashboard'),
    path('reminders', views.reminderspage, name='reminders'),
    path('user_reminders', views.user_reminderspage, name='user_reminders'),
    path('prescriptions', views.prescriptions_page, name='prescriptions'),
    path('prescriptions/create/', views.create_prescription, name='create_prescription'),
    path('prescriptions/<int:prescription_id>/update-status/', views.update_prescription_status, name='update_prescription_status'),
    path('prescriptions/<int:prescription_id>/delete/', views.delete_prescription, name='delete_prescription'),
    path('appoinment_history', views.appoinment_historypage, name='appoinment_history'),
    path('doctors_message', views.doctors_messagepage,name='doctors_message'),
    path('user_message', views.user_messagepage, name='user_message'),
    path('send_message', views.send_message, name='send_message'),
    path('mark_message_as_read/<int:message_id>/', views.mark_message_as_read, name='mark_message_as_read'),
    path('doctors_patients', views.doctors_patientspage, name='doctors_patients'),
    path('doctors_patients/<int:patient_id>/detail/', views.patient_detail, name='patient_detail'),
    path('doctors_profile', views.doctors_profilepage, name='doctors_profile'),
    path('meeting', views.meetingpage, name='meeting'),
    path('doctors_meeting', views.doctors_meetingpage, name='doctors_meeting'),
    path('terms', views.termspage, name='terms'), 
    path('verify-email/<uidb64>/<token>/', views.verify_email_view, name='verify-email'),
    path('resend-verification/', views.resend_verification, name='resend_verification'),
    path('verify_email/', views.verify_email, name='verify_email'),
    path('doctors_appointment_history', views.doctors_appointmenthistorypage, name='doctors_appointment_history'),
    path('doctorbook_appointment', views.doctorbook_appointment, name='doctorbook_appointment'),
    path('admin_dashboard', views.admin_dashboardpage, name='admin_dashboard'),
    path('zoom_appointment', views.zoom_appointmentpage, name='zoom_appointment'),
    path('admin_doctors', views.admin_doctorspage, name='admin_doctors'),
    path('admin_patients', views.admin_patientspage, name='admin_patients'),
    path('reset_password', views.reset_passwordpage, name='reset_password'),
    path('reset-password-confirm/<uidb64>/<token>/', views.reset_password_confirm, name='reset_password_confirm'),
    path('admin/user/<int:user_id>/block/', views.admin_block_user, name='admin_block_user'),
    path('admin/user/<int:user_id>/unblock/', views.admin_unblock_user, name='admin_unblock_user'),
    path('admin/user/<int:user_id>/delete/', views.admin_delete_user, name='admin_delete_user'),
    path('success/', views.success_page, name='success_page'),
    path('admin/doctors/', views.admin_doctors_management, name='admin_doctors_list'),
    path('admin/patients/', views.admin_patients_management, name='admin_patients_list'),
    path('admin/appointments/', views.admin_appointments, name='admin_appointments_list'),
    path('admin/appointments/<int:appointment_id>/edit/', views.admin_edit_appointment, name='admin_edit_appointment'),
    path('admin/appointments/<int:appointment_id>/approve/', views.admin_approve_appointment, name='admin_approve_appointment'),
    path('admin/appointments/<int:appointment_id>/reject/', views.admin_reject_appointment, name='admin_reject_appointment'),
    # Patient Appointment URLs
    path('patient_appointments', views.patient_appointments, name='patient_appointments'),
    path('reschedule_appointment/<int:appointment_id>/', views.reschedule_appointment, name='reschedule_appointment'),
    path('cancel_appointment/<int:appointment_id>/', views.cancel_appointment, name='cancel_appointment'),

    # Doctor Appointment URLs
    path('doctor_appointments', views.doctor_appointments, name='doctor_appointments'),
    path('approve_appointment/<int:appointment_id>/', views.approve_appointment, name='approve_appointment'),
    path('decline_appointment/<int:appointment_id>/', views.decline_appointment, name='decline_appointment'),
    path('request_reschedule/<int:appointment_id>/', views.request_reschedule, name='request_reschedule'),
    path('complete_appointment/<int:appointment_id>/', views.complete_appointment, name='complete_appointment'),

    # AJAX
    path('get_available_times/', views.get_available_times, name='get_available_times'),
    
    # Reminders
    path('send_reminder/', views.send_reminder, name='send_reminder'),

    # Real-time API endpoints
    path('api/patient-appointments/', views.get_patient_appointments_api, name='api_patient_appointments'),
    path('api/appointment-notifications/', views.get_appointment_notifications_api, name='api_appointment_notifications'),

    # Patient Reminders
    path('user_reminders', views.user_reminderspage, name='user_reminders'),
    path('reminders/create/', views.create_reminder, name='create_reminder'),
    path('reminders/<int:reminder_id>/update/', views.update_reminder, name='update_reminder'),
    path('reminders/<int:reminder_id>/delete/', views.delete_reminder, name='delete_reminder'),
    path('reminders/<int:reminder_id>/toggle-complete/', views.mark_reminder_completed, name='mark_reminder_completed'),
    path('send-reminder-to-doctor/', views.send_reminder_to_doctor, name='send_reminder_to_doctor'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)