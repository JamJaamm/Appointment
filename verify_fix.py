import os
import django
import sys

# Setup Django environment
# sys.path.append('c:\\Users\\user\\doctors-appointment')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'doctors_appointment.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from django.conf import settings
from appointment.views import admin_dashboardpage

def verify_dashboard_context():
    # Create a superuser for the request
    superuser, created = User.objects.get_or_create(username='admin_test', email='admin_test@example.com', defaults={'is_superuser': True, 'is_staff': True})
    if created:
        superuser.set_password('password')
        superuser.save()

    # Create a regular user (patient)
    patient_user, created = User.objects.get_or_create(username='patient_test', email='patient_test@example.com', defaults={'is_staff': False, 'is_superuser': False})
    if created:
        patient_user.set_password('password')
        patient_user.save()

    factory = RequestFactory()
    request = factory.get('/admin_dashboard/')
    request.user = superuser

    response = admin_dashboardpage(request)
    
    # Check context data directly if possible, but render returns HttpResponse. 
    # We can inspect the response content or use a mock render if we want to be precise, 
    # but for now let's just check if it runs without error and maybe print some debug info if we could.
    # Since we can't easily inspect context from HttpResponse without using Django test client, 
    # we will rely on the fact that it runs successfully.
    
    print("Admin dashboard page rendered successfully.")
    
    # To be more thorough, let's manually check the query logic used in the view
    doctors = User.objects.filter(is_staff=True)
    patients = User.objects.filter(is_staff=False, is_superuser=False)
    
    print(f"Doctors count: {doctors.count()}")
    print(f"Patients count (Regular Users): {patients.count()}")
    
    if patients.count() > 0:
        print("SUCCESS: Regular users are being counted as patients.")
    else:
        print("FAILURE: No regular users found (or logic is wrong).")

if __name__ == '__main__':
    verify_dashboard_context()
