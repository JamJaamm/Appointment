import os
import django
import sys

# Setup Django environment
sys.path.append('c:\\Users\\user\\doctors-appointment')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'doctors_appointment.settings')
django.setup()

from django.contrib.auth.models import User
from appointment.models import Patient

def check_counts():
    total_users = User.objects.count()
    staff_users = User.objects.filter(is_staff=True).count()
    superuser_users = User.objects.filter(is_superuser=True).count()
    regular_users = User.objects.filter(is_staff=False, is_superuser=False).count()
    
    patient_objects = Patient.objects.count()
    
    print(f"Total Users: {total_users}")
    print(f"Staff Users (Doctors/Admins): {staff_users}")
    print(f"Superusers: {superuser_users}")
    print(f"Regular Users (Potential Patients): {regular_users}")
    print(f"Patient Model Objects: {patient_objects}")

if __name__ == '__main__':
    check_counts()
