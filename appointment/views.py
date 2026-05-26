import logging
from django.shortcuts import render, redirect, get_object_or_404
from datetime import datetime, time
from django.contrib import messages
from dateutil.parser import parse

from django.contrib.auth.decorators import login_required # login required
from django.db import IntegrityError
from django.db.models import Sum, Q
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from .models import UserInfo, Doctor, Reminder
from django.contrib.auth import login, logout, authenticate
from .models import Patient, zoom_appointment, Message, Prescription, MedicalRecord

from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from datetime import timedelta
from django.utils import timezone
import random, string

# Use smtplib and MIMEText for direct SMTP to Mailpit
import smtplib
from email.mime.text import MIMEText
from .utils import send_verification_email, send_welcome_email
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.contrib.auth.tokens import default_token_generator
import uuid
from django.urls import reverse
from django.core.mail import send_mail, EmailMultiAlternatives
from django.utils.encoding import force_bytes
from django.utils.html import strip_tags

# Zoom settings

from .zoom_utils import create_zoom_meeting
from django.utils import timezone


# Create your views here.
def homepage(request):
    # Fetch available doctors (staff users with doctor profiles)
    available_doctors = User.objects.filter(
        is_staff=True, 
        is_active=True,
        is_superuser=False
    ).select_related('userinfo', 'doctor').filter(doctor__isnull=False)
    return render(request, 'index.html', {'available_doctors': available_doctors})
 
def servicespage(request):
    return render(request, 'services.html')

def doctorspage(request):
    # Show all staff users as doctors who have complete doctor profiles. Include related UserInfo for fewer queries.
    doctors = User.objects.filter(is_staff=True).select_related('userinfo', 'doctor').filter(doctor__isnull=False)
    return render(request, 'doctors.html', {'doctors': doctors})

def aboutpage(request):
    return render(request, 'about.html')

def contactpage(request):
    return render(request, 'contact.html')



def registerpage(request):
    if request.method == "POST":
        print("=== REGISTRATION POST RECEIVED ===")
        firstName = request.POST.get('firstName')
        lastName = request.POST.get('lastName')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        password_confirmation = request.POST.get('password_confirmation')
        userType = request.POST.get('userType')
        next_url = request.POST.get('next', request.GET.get('next', ''))
        print(f"Data: firstName={firstName}, lastName={lastName}, email={email}, phone={phone}, userType={userType}")

        userInput = {
            'firstName': firstName,
            'lastName': lastName,
            'email': email,
            'phone' : phone
        }

        try:
            if firstName == "" or lastName == "" or email == "" or phone == "" or password == "":
                error = "Please Fill all Fields"
                return render(request, 'register.html', {'error': error, 'userInput': userInput, 'next': next_url})

            try:
                validate_email(email)
            except ValidationError:
                error = "Invalid Email Address"
                return render(request, 'register.html', {'error': error, 'userInput': userInput, 'next': next_url})

            if password_confirmation != password:
                error = "Password Do Not Match"
                return render(request, 'register.html', {'error': error, 'userInput': userInput, 'next': next_url})

            if User.objects.filter(email=email).exists():
                error = "Email already exist!"
                return render(request, 'register.html', {'error': error, 'userInput': userInput, 'next': next_url})

            if userType == "doctor":
                staff = 1
            else:
                staff = 0

            randomNumber = random.randint(100000, 999999)
            print(f"Creating user: username={lastName}-{randomNumber}")

            user = User.objects.create_user(
                first_name=firstName,
                last_name=lastName,
                username=f'{lastName}-{randomNumber}',
                email=email,
                password=password,
                is_staff=staff
            )
            print(f"User created: {user.id}")

            # Create or update UserInfo to avoid duplicate OneToOne entries (handles race/duplicate registration)
            try:
                userinfo, created = UserInfo.objects.get_or_create(
                    user=user,
                    defaults={
                        'phone_number': phone
                    }
                )
                if not created:
                    # If the record already exists, update phone number when provided
                    if phone and getattr(userinfo, 'phone_number', '') != phone:
                        userinfo.phone_number = phone
                        userinfo.save()
            except IntegrityError:
                # As a fallback, try to update any existing record (defensive)
                existing = UserInfo.objects.filter(user=user).first()
                if existing and phone:
                    existing.phone_number = phone
                    existing.save()
                userinfo = existing

            if user.is_staff:
                Doctor.objects.create(user=user, speciality="General")
            else:
                Patient.objects.create(user=user)
            print("UserInfo and Patient/Doctor created")

            # Keep the account inactive until the user verifies their email.
            user.is_active = False
            user.save()

            # Ensure userinfo exists and is marked unverified.
            if not userinfo:
                userinfo = UserInfo.objects.filter(user=user).first()
            if userinfo:
                userinfo.email_verified = False
                userinfo.email_token_expiry = None
                userinfo.save()
            print("User deactivated and userinfo updated")

            send_verification_email(request, user)
            print("Verification email sent")

            messages.success(request, 'Registration successful! Please check your email to verify your account.')
            # Store next_url in session for redirect after email verification
            if next_url:
                request.session['next_after_verification'] = next_url
            return redirect('verify_email')
        except Exception as e:
            # If there's an error (e.g., email sending fails), show error
            import traceback
            error_message = f'Registration failed: {str(e)}'
            print(f"ERROR: {error_message}")
            print(traceback.format_exc())
            return render(request, 'register.html', {'error': error_message, 'userInput': userInput, 'next': next_url})

    # Get the 'next' parameter from GET request
    next_url = request.GET.get('next', '')
    return render(request, 'register.html', {'next': next_url})

def checkAdmin(user):
    if user.is_superuser:
        return True
    else:
        if user.is_staff:
            return redirect('doctors_dashboard')
        else:
            return redirect('user_dashboard')
        
 
def loginpage(request):
    if request.method == 'POST':
        email = request.POST.get('email').strip()
        password = request.POST.get('password').strip()
        next_url = request.POST.get('next', request.GET.get('next', ''))

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            error = 'No account found with that email.'
            return render(request, 'login.html', {'error': error, 'email': email, 'next': next_url})

        user_auth = authenticate(username=user.username, password=password)
        if user_auth is not None:
            # check if verified (skip for superusers)
            if not user.is_superuser and not user.userinfo.email_verified:
                error = 'Please verify your email before logging in.'
                return render(request, 'login.html', {'error': error, 'email': email, 'next': next_url})
            login(request, user_auth)
            messages.success(request, f'Welcome back, {user.username}!')
            
            # Redirect to booking page if user was trying to book
            if next_url:
                return redirect(next_url)
            
            if user.is_superuser and user.is_staff is True:
                return redirect('admin_dashboard')
            elif user.is_staff and user.is_superuser is False:
                return redirect('doctors_dashboard')
            else:
                return redirect('user_dashboard')
        else:
            error = 'Incorrect password.'
            return render(request, 'login.html', {'error': error, 'email': email, 'next': next_url})

    # Get the 'next' parameter from GET request
    next_url = request.GET.get('next', '')
    return render(request, 'login.html', {'next': next_url})


def resend_verification(request):
    if request.method == 'POST':
        email = request.POST.get('email')

        try:
            user = User.objects.get(email=email)
            user_info = user.userinfo
        except User.DoesNotExist:
            messages.error(request, "User not found.")
            return redirect('register')

        # Already verified
        if user_info.email_verified:
            messages.info(request, "Your email is already verified.")
            return redirect('home')

        # Prevent spam or repeated requests
        if (
            user_info.email_token_expiry and 
            user_info.email_token_expiry > timezone.now()
        ):
            messages.warning(request, "You just requested a link. Please wait a bit.")
            return redirect('verify_email')

        # 🩵 Just reuse our helper instead of duplicating code
        send_verification_email(request, user)

        message = "Verification link resent successfully! Please check your email."
        redirect_url = reverse('verify_email')
        return redirect(f"{reverse('success_page')}?message={message}&redirect_url={redirect_url}")

    return redirect('home')


def verify_email(request):
    return render(request, 'verify_email.html')

def verify_email_view(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if user.userinfo.email_token_expiry and timezone.now() > user.userinfo.email_token_expiry:
            return render(request, 'verification_expired.html', {'email': user.email})

        user.userinfo.email_verified = True
        user.is_active = True
        user.userinfo.email_token_expiry = None
        user.save()
        user.userinfo.save()

        # Send welcome email
        try:
            is_doctor = user.is_staff
            send_welcome_email(user, is_doctor=is_doctor)
        except Exception as e:
            # Log error but don't fail the verification
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send welcome email: {e}")

        # Check if there's a pending redirect (e.g., booking page)
        next_url = request.session.pop('next_after_verification', None)
        if next_url:
            messages.success(request, 'Email verified successfully! Please login to continue.')
            return redirect(f'{reverse("login")}?next={next_url}')

        messages.success(request, 'Email verified successfully! You can now login.')
        return redirect('login')

    return render(request, 'verification_failed.html')



@login_required
def logoutpage(request):
    logout(request)
    return redirect('/login')

@login_required
def book_appointmentpage(request):
    return render(request, 'book_appointment.html')


def initiate_booking(request):

    if request.user.is_authenticated:
        # User is logged in, redirect to booking page
        if request.user.is_staff:
            messages.warning(request, 'Doctors cannot book appointments.')
            return redirect('doctors_dashboard')
        return redirect('book_appointment')
    else:
        # User is not logged in, redirect to login page with next parameter
        messages.info(request, 'Please login or register to book an appointment.')
        return redirect('login')

@login_required
def user_dashboardpage(request):
    # Fetch available doctors (staff users with doctor profiles)
    user = request.user
    available_doctors = User.objects.filter(is_staff=True, is_active=True, is_superuser=False).select_related('userinfo', 'doctor').filter(doctor__isnull=False)[:6]
    userinfo = getattr(user, 'userinfo', None)
    
    # Get patient profile
    try:
        patient = user.patient
    except:
        patient = None
    
    # Fetch appointments stats and upcoming appointments
    from django.utils import timezone
    now = timezone.now()
    
    if patient:
        # Get all appointments for this patient
        all_appointments = zoom_appointment.objects.filter(
            patient=patient
        ).select_related('doctor', 'doctor__userinfo').order_by('-date')
        
        # Upcoming appointments (future or today)
        upcoming_appointments = all_appointments.filter(
            date__gte=now,
            status__in=['pending', 'approved']
        ).order_by('date')[:5]  # Limit to 5
        
        # Stats
        upcoming_count = all_appointments.filter(date__gte=now).count()
        completed_count = all_appointments.filter(status='completed').count()
        pending_count = all_appointments.filter(status='pending').count()
        
        # Get prescriptions count
        from appointment.models import Prescription
        prescriptions_count = Prescription.objects.filter(patient=patient).count()
    else:
        upcoming_appointments = []
        upcoming_count = 0
        completed_count = 0
        pending_count = 0
        prescriptions_count = 0
    
    return render(request, 'user_dashboard.html', {
        'available_doctors': available_doctors,
        'userinfo': userinfo,
        'upcoming_appointments': upcoming_appointments,
        'stat_upcoming': upcoming_count,
        'stat_completed': completed_count,
        'stat_pending': pending_count,
        'stat_prescriptions': prescriptions_count,
    })

@login_required
def user_profilepage(request):
    user = request.user
    userinfo = getattr(user, 'userinfo', None)
    
    # Get patient profile and appointments
    try:
        patient = user.patient
        now = timezone.now()
        appointments = zoom_appointment.objects.filter(
            patient=patient
        ).select_related('doctor', 'doctor__userinfo').order_by('-date')[:10]
    except:
        appointments = []
    
    return render(request, 'user_profile.html', {
        'userinfo': userinfo,
        'appointments': appointments,
    })

@login_required
def doctors_profilepage(request):
    user = request.user
    userinfo = getattr(user, 'userinfo', None)
    doctor = Doctor.objects.filter(user=user).first()
    
    # Fetch appointments for this doctor
    from django.utils import timezone
    now = timezone.now()
    appointments = zoom_appointment.objects.filter(
        doctor=user
    ).select_related('patient', 'patient__user', 'patient__user__userinfo').order_by('-date')[:10]
    
    # Build appointments data for the template
    appointments_data = []
    for appt in appointments:
        appointments_data.append({
            'id': appt.id,
            'patient_name': appt.patient.user.get_full_name() or appt.patient.user.username,
            'patient_id': appt.patient.id,
            'date': appt.date.strftime('%Y-%m-%d'),
            'time': appt.date.strftime('%H:%M'),
            'status': appt.get_status_display(),
            'datetime': appt.date.isoformat(),
        })
    
    return render(request, 'doctors_profile.html', {
        'userinfo': userinfo,
        'doctor': doctor,
        'appointments': appointments_data,
    })


@login_required
def doctor_editprofilepage(request):
    if not request.user.is_staff:
        return redirect('home')
    
    user = request.user
    
    if request.method == 'POST':
        # Update User fields
        first_name = request.POST.get('firstName', '').strip()
        last_name = request.POST.get('lastName', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        dob = request.POST.get('dob', '').strip()
        gender = request.POST.get('gender', '').strip()
        location = request.POST.get('location', '').strip()
        speciality = request.POST.get('speciality', '').strip()
        profile_photo = request.FILES.get('profile_photo', None)
        yearsOfExperience = request.POST.get('yearsOfExperience', '').strip()
        bio = request.POST.get('bio', '').strip()
        education = request.POST.get('education', '').strip()
        certifications = request.POST.get('certifications', '').strip()

        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name

        # Email uniqueness check
        if email and email != user.email:
            if User.objects.filter(email=email).exclude(pk=user.pk).exists():
                messages.error(request, 'Email address is already used by another account.')
            else:
                user.email = email

        user.save()

        # Update UserInfo fields
        userinfo, _ = UserInfo.objects.get_or_create(user=user)

        if phone:
            userinfo.phone_number = phone

        if dob:
            userinfo.dob = dob

        if gender:
            userinfo.gender = gender

        if location:
            userinfo.location = location

        yearsOfExperience = request.POST.get('yearsOfExperience', '').strip()
        if yearsOfExperience:
            userinfo.yearsOfExperience = yearsOfExperience

        # Handle profile picture
        if request.FILES.get('profile_photo'):
            userinfo.profile_picture = request.FILES.get('profile_photo')

        # Update bio, education, and certifications (allow empty strings)
        userinfo.bio = bio
        userinfo.education = education
        userinfo.certifications = certifications

        userinfo.save()

        speciality = request.POST.get('speciality', '').strip()
        if speciality:
            userinfo.speciality = speciality

        # Update Doctor speciality
        # if speciality:  
        #     doctor_obj, created = Doctor.objects.get_or_create(user=user)
        #     doctor_obj.speciality = speciality
        #     doctor_obj.save()
        
        message = 'Profile updated successfully!'
        redirect_url = reverse('doctors_profile')
        return redirect(f"{reverse('success_page')}?message={message}&redirect_url={redirect_url}")
    
    # GET request
    userinfo = getattr(user, 'userinfo', None)
    doctor = Doctor.objects.filter(user=user).first()
    speciality = doctor.speciality if doctor else ''
    
    return render(request, 'doctor_editprofile.html', {
        'doctor': user,
        'userinfo': userinfo,
        'speciality': speciality,
    })

def edit_userprofilepage(request, id=None):
    """Edit profile page for regular users."""
    from datetime import datetime
    
    # If id provided and user is superuser, allow editing that user.
    # Otherwise, edit own profile.
    if id and request.user.is_superuser:
        try:
            user = User.objects.get(pk=id)
        except User.DoesNotExist:
            messages.error(request, 'User not found.')
            return redirect('user_dashboard')
    else:
        user = request.user

    if request.method == 'POST':
        # Update User fields
        first_name = request.POST.get('firstName', '').strip()
        last_name = request.POST.get('lastName', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        gender = request.POST.get('gender', '').strip()
        location = request.POST.get('location', '').strip()
        bloodgroup = request.POST.get('bloodgroup', '').strip()


        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        
        # Email uniqueness check
        if email and email != user.email:
            if User.objects.filter(email=email).exclude(pk=user.pk).exists():
                messages.error(request, 'Email address is already used by another account.')
            else:
                user.email = email

        user.save()

        # Update UserInfo fields
        userinfo, _ = UserInfo.objects.get_or_create(user=user)
        
        # phone = request.POST.get('phone', '').strip()
        if phone:
            userinfo.phone_number = phone
            
        dob = request.POST.get('dob')
        if dob:
            try:
                dob_date = datetime.strptime(dob, '%Y-%m-%d').date()
                userinfo.dob = dob_date
            except ValueError:
                # Handle invalid date format
                messages.error(request, 'Invalid date format for Date of Birth.')
            
        gender = request.POST.get('gender')
        if gender:
            userinfo.gender = gender
            
        location = request.POST.get('location', '').strip() # Template uses 'address'
        if location:
            userinfo.location = location

        bloodgroup = request.POST.get('bloodgroup', '').strip()
        if bloodgroup:
            userinfo.bloodgroup = bloodgroup    
 
            
        # Handle profile picture
        if request.FILES.get('profile_photo'):
            userinfo.profile_picture = request.FILES.get('profile_photo')

        userinfo.save()
        
        message = 'Profile updated successfully!'
        redirect_url = reverse('user_profile')
        return redirect(f"{reverse('success_page')}?message={message}&redirect_url={redirect_url}")

    # GET request
    userinfo = getattr(user, 'userinfo', None)
    return render(request, 'edit_userprofile.html',{
        'patients': user,
        'userinfo': userinfo,
        'target': user  # Pass target for template compatibility
    })

@login_required
def doctors_dashboardpage(request):
    userinfo = getattr(request.user, 'userinfo', None)

    # Fetch all appointments for this doctor
    appointments = zoom_appointment.objects.filter(
        doctor=request.user
    ).select_related('patient', 'patient__user', 'patient__user__userinfo').order_by('-date')

    # Build patient list from appointments (unique patients)
    patient_ids = appointments.values_list('patient_id', flat=True).distinct()
    patients = Patient.objects.filter(
        id__in=patient_ids
    ).select_related('user', 'user__userinfo').order_by('-id')

    # Calculate stats
    now = timezone.now()
    week_ago = now - timedelta(days=7)

    appointments_this_week = appointments.filter(date__gte=week_ago, date__lte=now).count()
    completed = appointments.filter(status='completed').count()
    upcoming = appointments.filter(date__gt=now).count()
    missed = appointments.filter(
        Q(status='cancelled') | Q(date__lt=now, status__in=['pending', 'approved'])
    ).count()

    return render(request, 'doctors_dashboard.html', {
        'userinfo': userinfo,
        'patients': patients,
        'appointments': appointments,
        'stat_weekly': appointments_this_week,
        'stat_completed': completed,
        'stat_upcoming': upcoming,
        'stat_missed': missed,
        'now': timezone.now(),
        'user': request.user,
    })


@login_required
def reminderspage(request):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    
    userinfo = getattr(request.user, 'userinfo', None)
    
    # Get all upcoming appointments for this doctor
    from django.utils import timezone
    now = timezone.now()
    appointments = zoom_appointment.objects.filter(
        doctor=request.user,
        status__in=['pending', 'approved'],
        date__gte=now
    ).select_related('patient', 'patient__user').order_by('date')[:20]

    # Get all patients this doctor has seen
    patient_ids = zoom_appointment.objects.filter(
        doctor=request.user
    ).values_list('patient_id', flat=True).distinct()
    patients = Patient.objects.filter(
        id__in=patient_ids
    ).select_related('user').order_by('user__first_name')
    
    return render(request, 'reminders.html', {
        'userinfo': userinfo,
        'appointments': appointments,
        'patients': patients,
    })

@login_required
def user_reminderspage(request):
    if request.user.is_staff:
        return redirect('doctors_dashboard')

    try:
        patient = Patient.objects.get(user=request.user)
    except Patient.DoesNotExist:
        messages.error(request, 'Patient profile not found.')
        return redirect('user_dashboard')

    # Get all appointments for this patient
    from django.utils import timezone
    now = timezone.now()
    appointments = zoom_appointment.objects.filter(
        patient=patient
    ).select_related('doctor', 'doctor__userinfo').order_by('date')

    # Separate upcoming and past
    upcoming_appointments = appointments.filter(date__gte=now, status__in=['pending', 'approved'])
    past_appointments = appointments.filter(Q(date__lt=now) | Q(status__in=['completed', 'cancelled']))

    # Get all doctors this patient has appointments with
    doctor_ids = appointments.values_list('doctor_id', flat=True).distinct()
    doctors = User.objects.filter(
        id__in=doctor_ids,
        is_staff=True
    ).select_related('userinfo', 'doctor')

    return render(request, 'user_reminders.html', {
        'appointments': appointments,
        'upcoming_appointments': upcoming_appointments,
        'past_appointments': past_appointments,
        'doctors': doctors,
    })


@login_required
def send_reminder_to_doctor(request):
    if request.user.is_staff:
        return redirect('doctors_dashboard')

    try:
        patient = Patient.objects.get(user=request.user)
    except Patient.DoesNotExist:
        messages.error(request, 'Patient profile not found.')
        return redirect('user_reminders')

    if request.method == 'POST':
        doctor_id = request.POST.get('doctor_id')
        subject = request.POST.get('subject', 'Appointment Reminder').strip()
        message_text = request.POST.get('message', '').strip()
        appointment_id = request.POST.get('appointment_id')

        if not doctor_id or not message_text:
            messages.error(request, 'Please select a doctor and enter a message.')
            return redirect('user_reminders')

        try:
            doctor = User.objects.get(pk=doctor_id, is_staff=True)
            appointment = None
            if appointment_id:
                appointment = zoom_appointment.objects.get(
                    pk=appointment_id,
                    patient=patient
                )

            # Create internal message
            Message.objects.create(
                sender_type='patient',
                sender=request.user,
                recipient=doctor,
                subject=subject,
                message=message_text,
                appointment=appointment
            )

            # Send email to doctor
            patient_name = request.user.get_full_name() or request.user.username
            appointment_details = ""
            if appointment:
                appt_date = appointment.date.strftime("%B %d, %Y at %I:%M %p")
                appointment_details = f"""
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="color: #0070a0; margin-top: 0;">Appointment Details</h3>
                    <p><strong>Patient:</strong> {patient_name}</p>
                    <p><strong>Date & Time:</strong> {appt_date}</p>
                    <p><strong>Reason:</strong> {appointment.reason or 'Not specified'}</p>
                </div>
                """
            
            email_subject = f"Patient Reminder: {subject}"
            
            html_message = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #0070a0;">New Patient Reminder</h2>
                    <p>Dear Dr. {doctor.last_name},</p>
                    <p>You have received a new reminder from your patient:</p>
                    
                    <div style="background-color: #e8f4fd; padding: 15px; border-left: 4px solid #0070a0; margin: 20px 0;">
                        <p style="font-style: italic; margin: 0;">"{message_text}"</p>
                    </div>
                    
                    {appointment_details}
                    
                    <p style="color: #6c757d; font-size: 14px;">
                        Please respond to your patient at their earliest convenience.
                    </p>
                    <p>Best regards,<br>MediCare Clinic Team</p>
                </div>
            </body>
            </html>
            """
            
            appt_info_plain = ""
            if appointment:
                appt_date = appointment.date.strftime("%B %d, %Y at %I:%M %p")
                appt_info_plain = f"""
Appointment Date: {appt_date}
Reason: {appointment.reason or 'Not specified'}
"""
            
            plain_message = f"""
Dear Dr. {doctor.last_name},

You have received a new reminder from your patient {patient_name}.

Message:
"{message_text}"

{appt_info_plain}
Please respond to your patient at their earliest convenience.

Best regards,
MediCare Clinic Team
"""

            try:
                from django.core.mail import send_mail
                send_mail(
                    subject=email_subject,
                    message=plain_message,
                    from_email='appointments@medicare.com',
                    recipient_list=[doctor.email],
                    html_message=html_message,
                    fail_silently=False,
                )
                messages.success(request, 'Reminder sent to doctor successfully! An email has been sent.')
            except Exception as e:
                messages.warning(request, f'Reminder saved but email failed: {str(e)}')
            
            return redirect('user_reminders')
        except User.DoesNotExist:
            messages.error(request, 'Doctor not found.')
        except Exception as e:
            messages.error(request, f'Error sending reminder: {str(e)}')

    return redirect('user_reminders')


@login_required
def create_reminder(request):
    if request.user.is_staff:
        return redirect('doctors_dashboard')

    try:
        patient = Patient.objects.get(user=request.user)
    except Patient.DoesNotExist:
        messages.error(request, 'Patient profile not found.')
        return redirect('user_dashboard')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        reminder_type = request.POST.get('reminder_type', 'task')
        date_time_str = request.POST.get('date_time')
        frequency = request.POST.get('frequency', 'once')
        location = request.POST.get('location', '').strip()

        if not title or not date_time_str:
            messages.error(request, 'Title and date/time are required.')
        else:
            try:
                date_time = timezone.make_aware(
                    datetime.strptime(date_time_str, "%Y-%m-%dT%H:%M")
                )

                Reminder.objects.create(
                    patient=patient,
                    title=title,
                    description=description,
                    reminder_type=reminder_type,
                    date_time=date_time,
                    frequency=frequency,
                    location=location
                )

                messages.success(request, 'Reminder created successfully!')
                return redirect('user_reminders')
            except Exception as e:
                messages.error(request, f'Error creating reminder: {str(e)}')

    return redirect('user_reminders')


@login_required
def update_reminder(request, reminder_id):
    if request.user.is_staff:
        return redirect('doctors_dashboard')

    try:
        patient = Patient.objects.get(user=request.user)
        reminder = Reminder.objects.get(pk=reminder_id, patient=patient)
    except (Patient.DoesNotExist, Reminder.DoesNotExist):
        messages.error(request, 'Reminder not found.')
        return redirect('user_reminders')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        reminder_type = request.POST.get('reminder_type', 'task')
        date_time_str = request.POST.get('date_time')
        frequency = request.POST.get('frequency', 'once')
        location = request.POST.get('location', '').strip()
        is_completed = request.POST.get('is_completed', False)

        if not title or not date_time_str:
            messages.error(request, 'Title and date/time are required.')
        else:
            try:
                date_time = timezone.make_aware(
                    datetime.strptime(date_time_str, "%Y-%m-%dT%H:%M")
                )

                reminder.title = title
                reminder.description = description
                reminder.reminder_type = reminder_type
                reminder.date_time = date_time
                reminder.frequency = frequency
                reminder.location = location
                reminder.is_completed = is_completed == 'on' or is_completed == True
                reminder.save()

                messages.success(request, 'Reminder updated successfully!')
                return redirect('user_reminders')
            except Exception as e:
                messages.error(request, f'Error updating reminder: {str(e)}')

    return redirect('user_reminders')


@login_required
def delete_reminder(request, reminder_id):
    if request.user.is_staff:
        return redirect('doctors_dashboard')

    try:
        patient = Patient.objects.get(user=request.user)
        reminder = Reminder.objects.get(pk=reminder_id, patient=patient)
    except (Patient.DoesNotExist, Reminder.DoesNotExist):
        messages.error(request, 'Reminder not found.')
        return redirect('user_reminders')

    reminder.delete()
    messages.success(request, 'Reminder deleted successfully!')
    return redirect('user_reminders')


@login_required
def mark_reminder_completed(request, reminder_id):
    """Mark a reminder as completed or not completed."""
    if request.user.is_staff:
        return redirect('doctors_dashboard')

    try:
        patient = Patient.objects.get(user=request.user)
        reminder = Reminder.objects.get(pk=reminder_id, patient=patient)
    except (Patient.DoesNotExist, Reminder.DoesNotExist):
        messages.error(request, 'Reminder not found.')
        return redirect('user_reminders')

    reminder.is_completed = not reminder.is_completed
    reminder.save()

    status = 'completed' if reminder.is_completed else 'active'
    messages.success(request, f'Reminder marked as {status}.')
    return redirect('user_reminders')

def prescriptions_page(request):
    # Check if user is a doctor or patient and render appropriate template
    if hasattr(request.user, 'doctor'):
        # User is a doctor - show prescriptions they can create and view
        userinfo = getattr(request.user, 'userinfo', None)

        # Get all patients in the system (doctors can prescribe to any patient)
        patients = Patient.objects.all().select_related('user', 'user__userinfo').order_by('user__first_name')

        # Get all prescriptions by this doctor
        prescriptions = Prescription.objects.filter(
            doctor=request.user
        ).select_related('patient', 'patient__user', 'appointment').order_by('-created_at')

        return render(request, 'prescriptions.html', {
            'userinfo': userinfo,
            'patients': patients,
            'prescriptions': prescriptions,
        })
    else:
        # User is a patient - show their prescriptions
        userinfo = getattr(request.user, 'userinfo', None)
        try:
            patient = request.user.patient
            prescriptions = Prescription.objects.filter(
                patient=patient
            ).select_related('doctor', 'doctor__userinfo').order_by('-created_at')
        except:
            prescriptions = []
        return render(request, 'user_prescriptions.html', {'userinfo': userinfo, 'prescriptions': prescriptions})


@login_required
def create_prescription(request):
    """Allow doctors to create a new prescription for a patient."""
    if not hasattr(request.user, 'doctor'):
        messages.error(request, 'Access denied. Doctors only.')
        return redirect('home')

    # Get patient_id from query params if provided (for pre-selection)
    selected_patient_id = request.GET.get('patient_id')

    # Get all patients in the system (doctors can prescribe to any patient)
    patients = Patient.objects.all().select_related('user', 'user__userinfo').order_by('user__first_name')

    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        drug_name = request.POST.get('drug_name', '').strip()
        dosage = request.POST.get('dosage', '').strip()
        frequency = request.POST.get('frequency', '').strip()
        duration = request.POST.get('duration', '').strip()
        instructions = request.POST.get('instructions', '').strip()
        notes = request.POST.get('notes', '').strip()
        start_date = request.POST.get('start_date', '').strip()
        end_date = request.POST.get('end_date', '').strip()

        # Validation
        if not patient_id or not drug_name or not dosage or not frequency or not duration:
            messages.error(request, 'Please fill in all required fields.')
            return redirect(request.META.get('HTTP_REFERER', 'prescriptions'))

        try:
            patient = Patient.objects.get(id=patient_id)
        except Patient.DoesNotExist:
            messages.error(request, 'Patient not found.')
            return redirect(request.META.get('HTTP_REFERER', 'prescriptions'))

        # Parse dates
        start_date_obj = None
        end_date_obj = None
        if start_date:
            try:
                from datetime import datetime
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            except ValueError:
                start_date_obj = timezone.now().date()
        else:
            start_date_obj = timezone.now().date()

        if end_date:
            try:
                from datetime import datetime
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                pass

        # Create prescription
        Prescription.objects.create(
            doctor=request.user,
            patient=patient,
            drug_name=drug_name,
            dosage=dosage,
            frequency=frequency,
            duration=duration,
            instructions=instructions,
            notes=notes,
            start_date=start_date_obj,
            end_date=end_date_obj,
        )

        messages.success(request, 'Prescription created successfully!')
        return redirect('prescriptions')

    return render(request, 'prescriptions.html', {
        'userinfo': getattr(request.user, 'userinfo', None),
        'patients': patients,
        'prescriptions': Prescription.objects.filter(doctor=request.user).select_related('patient', 'patient__user').order_by('-created_at'),
        'selected_patient_id': selected_patient_id,
    })

@login_required
def update_prescription_status(request, prescription_id):
    """Allow doctors to update the status of a prescription."""
    if not hasattr(request.user, 'doctor'):
        messages.error(request, 'Access denied. Doctors only.')
        return redirect('home')

    try:
        prescription = Prescription.objects.get(id=prescription_id, doctor=request.user)
    except Prescription.DoesNotExist:
        messages.error(request, 'Prescription not found.')
        return redirect('prescriptions')

    if request.method == 'POST':
        status = request.POST.get('status')
        if status in ['active', 'completed', 'expired', 'cancelled']:
            prescription.status = status
            prescription.save()
            messages.success(request, 'Prescription status updated successfully!')
        else:
            messages.error(request, 'Invalid status.')

    return redirect('prescriptions')


@login_required
def toggle_prescription_status(request, prescription_id):
    """Allow doctors to toggle prescription between active and completed."""
    if not hasattr(request.user, 'doctor'):
        messages.error(request, 'Access denied. Doctors only.')
        return redirect('home')

    try:
        prescription = Prescription.objects.get(id=prescription_id, doctor=request.user)
    except Prescription.DoesNotExist:
        messages.error(request, 'Prescription not found.')
        return redirect('prescriptions')

    if request.method == 'POST':
        # Toggle between active and completed
        if prescription.status == 'active':
            prescription.status = 'completed'
            messages.success(request, 'Prescription marked as completed.')
        else:
            prescription.status = 'active'
            messages.success(request, 'Prescription marked as active.')
        
        prescription.save()

    return redirect('prescriptions')


@login_required
def delete_prescription(request, prescription_id):
    """Allow doctors to delete a prescription."""
    if not hasattr(request.user, 'doctor'):
        messages.error(request, 'Access denied. Doctors only.')
        return redirect('home')

    try:
        prescription = Prescription.objects.get(id=prescription_id, doctor=request.user)
        prescription.delete()
        messages.success(request, 'Prescription deleted successfully!')
    except Prescription.DoesNotExist:
        messages.error(request, 'Prescription not found.')

    return redirect('prescriptions')

@login_required
def appoinment_historypage(request):
    """Patient's appointment history page showing upcoming and past appointments."""
    if request.user.is_staff:
        return redirect('doctors_dashboard')

    try:
        patient = Patient.objects.get(user=request.user)
    except Patient.DoesNotExist:
        messages.error(request, 'Patient profile not found.')
        return redirect('user_dashboard')

    now = timezone.now()

    # Get all appointments for this patient
    all_appointments = zoom_appointment.objects.filter(
        patient=patient
    ).select_related('doctor', 'doctor__userinfo', 'doctor__doctor').order_by('-date')

    # Separate into upcoming and past
    upcoming_appointments = all_appointments.filter(
        date__gte=now,
        status__in=['pending', 'approved']
    ).order_by('date')

    past_appointments = all_appointments.filter(
        Q(date__lt=now) | Q(status__in=['completed', 'cancelled'])
    ).order_by('-date')

    return render(request, 'appoinment_history.html', {
        'upcoming_appointments': upcoming_appointments,
        'past_appointments': past_appointments,
    })

def doctors_messagepage(request):
    # Ensure user is a doctor
    if not hasattr(request.user, 'doctor'):
        messages.error(request, 'Access denied. Doctors only.')
        return redirect('home')

    # Get all messages where the doctor is the recipient
    messages_list = Message.objects.filter(recipient=request.user).select_related('sender', 'sender__userinfo')

    # Get all patients in the system (doctors can message any patient)
    patients = Patient.objects.all().select_related('user', 'user__userinfo').order_by('user__first_name')

    # Get unread message count
    unread_count = messages_list.filter(is_read=False).count()

    userinfo = getattr(request.user, 'userinfo', None)

    return render(request, 'doctors_message.html', {
        'messages': messages_list,
        'patients': patients,
        'unread_count': unread_count,
        'userinfo': userinfo
    })

def user_messagepage(request):
    # Ensure user is not a doctor (patients only)
    if hasattr(request.user, 'doctor'):
        messages.error(request, 'Access denied. Patients only.')
        return redirect('home')
    
    # Get all messages where the user is the recipient
    messages_list = Message.objects.filter(recipient=request.user).select_related('sender', 'sender__userinfo')
    
    # Get unique senders (doctors who messaged this user)
    unique_senders = messages_list.values('sender').distinct()
    # doctors = User.objects.filter(id__in=unique_senders).select_related('userinfo', 'doctor')
    doctors = User.objects.filter(is_staff=True, is_active=True).select_related('userinfo', 'doctor').filter(doctor__isnull=False)

    # Get unread message count
    unread_count = messages_list.filter(is_read=False).count()

    userinfo = getattr(request.user, 'userinfo', None)

    return render(request, 'user_message.html', {
        'messages': messages_list,
        'doctors': doctors,
        'unread_count': unread_count,
        'userinfo': userinfo
    })

def send_message(request):
    if request.method == 'POST':
        recipient_id = request.POST.get('recipient_id')
        subject = request.POST.get('subject', '')
        message_text = request.POST.get('message')
        parent_message_id = request.POST.get('parent_message_id')

        if not recipient_id or not message_text:
            messages.error(request, 'Recipient and message are required.')
            return redirect(request.META.get('HTTP_REFERER', 'home'))

        try:
            recipient = User.objects.get(id=recipient_id)
        except User.DoesNotExist:
            messages.error(request, 'Recipient not found.')
            return redirect(request.META.get('HTTP_REFERER', 'home'))

        # Determine sender type based on current user
        sender_type = 'doctor' if hasattr(request.user, 'doctor') else 'patient'

        # Get parent message if this is a reply
        parent_message = None
        if parent_message_id:
            try:
                parent_message = Message.objects.get(id=parent_message_id)
            except Message.DoesNotExist:
                pass

        # Create the message
        Message.objects.create(
            sender_type=sender_type,
            sender=request.user,
            recipient=recipient,
            subject=subject,
            message=message_text,
            parent_message=parent_message
        )

        messages.success(request, 'Message sent successfully!')
        return redirect(request.META.get('HTTP_REFERER', 'home'))

    return redirect('home')


@login_required
def send_reminder(request):
    """Allow doctors to send appointment reminders to patients via email and internal messaging."""
    if not request.user.is_staff:
        messages.error(request, 'Access denied. Doctors only.')
        return redirect('home')

    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        appointment_date = request.POST.get('appointment_date')
        appointment_time = request.POST.get('appointment_time')
        message_text = request.POST.get('message', '')
        appointment_id = request.POST.get('appointment_id')

        if not patient_id or not appointment_date:
            messages.error(request, 'Patient and appointment date are required.')
            return redirect('reminders')

        try:
            patient = Patient.objects.get(id=patient_id)
            patient_email = patient.user.email
            patient_name = patient.user.get_full_name() or patient.user.username
        except Patient.DoesNotExist:
            messages.error(request, 'Patient not found.')
            return redirect('reminders')

        # Find the appointment if appointment_id provided or try to match by date/time
        appointment = None
        try:
            if appointment_id:
                appointment = zoom_appointment.objects.get(pk=appointment_id, patient=patient)
            else:
                # Try to find matching appointment
                from datetime import datetime
                appt_datetime = datetime.strptime(f"{appointment_date} {appointment_time}", "%Y-%m-%d %H:%M")
                appt_datetime = timezone.make_aware(appt_datetime)
                appointment = zoom_appointment.objects.filter(
                    patient=patient,
                    doctor=request.user
                ).filter(
                    date__year=appt_datetime.year,
                    date__month=appt_datetime.month,
                    date__day=appt_datetime.day,
                    date__hour=appt_datetime.hour,
                    date__minute=appt_datetime.minute
                ).first()
        except:
            pass

        # Format the appointment datetime
        try:
            from datetime import datetime
            appt_datetime = datetime.strptime(f"{appointment_date} {appointment_time}", "%Y-%m-%d %H:%M")
            formatted_date = appt_datetime.strftime("%B %d, %Y at %I:%M %p")
        except ValueError:
            formatted_date = f"{appointment_date} at {appointment_time}"

        # Prepare email subject and body
        subject = f'Appointment Reminder - Dr. {request.user.last_name}'

        html_message = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #0070a0;">Appointment Reminder</h2>
                <p>Dear {patient_name},</p>
                <p>{message_text}</p>
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="color: #0070a0; margin-top: 0;">Appointment Details</h3>
                    <p><strong>Doctor:</strong> Dr. {request.user.get_full_name()}</p>
                    <p><strong>Date & Time:</strong> {formatted_date}</p>
                    <p><strong>Clinic:</strong> MediCare Clinic</p>
                </div>
                <p style="color: #6c757d; font-size: 14px;">
                    If you need to reschedule or cancel, please contact us at least 24 hours in advance.
                </p>
                <p>Best regards,<br>MediCare Clinic Team</p>
            </div>
        </body>
        </html>
        """

        plain_message = f"""
Dear {patient_name},

{message_text}

Appointment Details:
- Doctor: Dr. {request.user.get_full_name()}
- Date & Time: {formatted_date}
- Clinic: MediCare Clinic

If you need to reschedule or cancel, please contact us at least 24 hours in advance.

Best regards,
MediCare Clinic Team
"""

        # Create internal message record
        try:
            Message.objects.create(
                sender_type='doctor',
                sender=request.user,
                recipient=patient.user,
                subject=subject,
                message=message_text,
                appointment=appointment
            )
        except Exception as e:
            pass  # Continue even if message creation fails

        try:
            # Send email using Django's send_mail
            send_mail(
                subject=subject,
                message=plain_message,
                from_email='appointments@medicare.com',
                recipient_list=[patient_email],
                html_message=html_message,
                fail_silently=False,
            )

            messages.success(request, f'Reminder sent successfully to {patient_name} via email!')
        except Exception as e:
            messages.error(request, f'Failed to send email reminder: {str(e)}')

        return redirect('reminders')

    return redirect('reminders')


def mark_message_as_read(request, message_id):
    try:
        message = Message.objects.get(id=message_id, recipient=request.user)
        message.is_read = True
        message.save()
    except Message.DoesNotExist:
        messages.error(request, 'Message not found.')
    
    return redirect(request.META.get('HTTP_REFERER', 'home'))

def doctors_patientspage(request):
    # Get all patients who have appointments with this doctor
    patient_ids = zoom_appointment.objects.filter(
        doctor=request.user
    ).values_list('patient_id', flat=True).distinct()

    patients = Patient.objects.filter(
        id__in=patient_ids
    ).select_related('user', 'user__userinfo').prefetch_related(
        'appointments',
        'prescriptions',
        'records'
    ).order_by('user__first_name')

    return render(request, 'doctors_patients.html', {
        'patients': patients,
        'userinfo': getattr(request.user, 'userinfo', None),
    })


@login_required
def patient_detail(request, patient_id):
    """Detailed view of a patient's medical records, appointments, and prescriptions."""
    if not hasattr(request.user, 'doctor'):
        messages.error(request, 'Access denied. Doctors only.')
        return redirect('home')

    try:
        patient = Patient.objects.select_related('user', 'user__userinfo').get(id=patient_id)
    except Patient.DoesNotExist:
        messages.error(request, 'Patient not found.')
        return redirect('doctors_patients')

    # Verify this patient belongs to this doctor (has appointments)
    has_appointment = zoom_appointment.objects.filter(
        doctor=request.user,
        patient=patient
    ).exists()

    if not has_appointment:
        messages.error(request, 'You do not have access to this patient.')
        return redirect('doctors_patients')

    # Get patient's appointments with this doctor
    appointments = zoom_appointment.objects.filter(
        doctor=request.user,
        patient=patient
    ).order_by('-date')

    # Get patient's prescriptions from this doctor
    prescriptions = Prescription.objects.filter(
        doctor=request.user,
        patient=patient
    ).order_by('-created_at')

    # Get patient's medical records
    medical_records = MedicalRecord.objects.filter(
        patient=patient
    ).order_by('-date')

    # Get active prescriptions count
    active_prescriptions = prescriptions.filter(status='active').count()

    # Get upcoming appointments
    from django.utils import timezone
    upcoming_appointments = appointments.filter(date__gt=timezone.now()).order_by('date')

    if request.method == 'POST':
        # Handle adding medical record
        action = request.POST.get('action')

        if action == 'add_record':
            diagnosis = request.POST.get('diagnosis', '').strip()
            treatment = request.POST.get('treatment', '').strip()
            notes = request.POST.get('record_notes', '').strip()
            record_date = request.POST.get('record_date', '').strip()

            if diagnosis and treatment:
                from datetime import datetime
                record_date_obj = None
                if record_date:
                    try:
                        record_date_obj = datetime.strptime(record_date, '%Y-%m-%d').date()
                    except ValueError:
                        record_date_obj = timezone.now().date()
                else:
                    record_date_obj = timezone.now().date()

                MedicalRecord.objects.create(
                    patient=patient,
                    date=record_date_obj,
                    diagnosis=diagnosis,
                    treatment=treatment,
                    notes=notes
                )
                messages.success(request, 'Medical record added successfully!')
                return redirect('patient_detail', patient_id=patient.id)
            else:
                messages.error(request, 'Diagnosis and treatment are required.')

        elif action == 'add_prescription':
            # Redirect to prescription creation with patient pre-selected
            return redirect(f'{reverse("create_prescription")}?patient_id={patient.id}')

    return render(request, 'patient_detail.html', {
        'patient': patient,
        'appointments': appointments,
        'prescriptions': prescriptions,
        'medical_records': medical_records,
        'active_prescriptions_count': active_prescriptions,
        'upcoming_appointments': upcoming_appointments,
        'userinfo': getattr(request.user, 'userinfo', None),
    })


@login_required
def meetingpage(request):
    """Patient meeting page - shows upcoming appointment with meeting details from doctor."""
    if request.user.is_staff:
        return redirect('doctors_meeting')
    
    try:
        patient = request.user.patient
    except:
        messages.error(request, 'Patient profile not found.')
        return redirect('user_dashboard')
    
    # Get the next upcoming appointment with meeting details OR Zoom link
    from django.utils import timezone
    now = timezone.now()
    
    # First try: upcoming appointment with meeting details posted by doctor
    appointment = zoom_appointment.objects.filter(
        patient=patient,
        status__in=['approved', 'completed'],
        date__gte=now,
    ).exclude(
        zoom_meeting_id__isnull=True
    ).order_by('date').first()
    
    # Second try: upcoming appointment with Zoom link
    if not appointment:
        appointment = zoom_appointment.objects.filter(
            patient=patient,
            status__in=['approved', 'completed'],
            date__gte=now,
            zoom_join_url__isnull=False
        ).exclude(zoom_join_url='').order_by('date').first()
    
    # Third try: most recent appointment with meeting details
    if not appointment:
        appointment = zoom_appointment.objects.filter(
            patient=patient,
            status__in=['approved', 'completed'],
        ).exclude(
            zoom_meeting_id__isnull=True
        ).order_by('-date').first()
    
    # Fourth try: most recent past appointment with Zoom
    if not appointment:
        appointment = zoom_appointment.objects.filter(
            patient=patient,
            status__in=['approved', 'completed'],
            zoom_join_url__isnull=False
        ).exclude(zoom_join_url='').order_by('-date').first()
    
    return render(request, 'meeting.html', {
        'appointment': appointment,
    })


@login_required
def doctors_meetingpage(request):
    """Doctor meeting page - post meeting details for appointments."""
    if not request.user.is_staff:
        return redirect('home')
    
    from django.utils import timezone
    now = timezone.now()
    
    # Get ALL doctor's appointments (for any patient) with Zoom links
    all_appointments = zoom_appointment.objects.filter(
        doctor=request.user,
        status__in=['approved', 'completed', 'pending']
    ).order_by('-date')[:50]
    
    # Get recent appointments with meeting details posted
    recent_appointments = zoom_appointment.objects.filter(
        doctor=request.user,
        meeting_details__isnull=False
    ).exclude(meeting_details='').order_by('-meeting_details_updated_at')[:5]
    
    if request.method == 'POST':
        appointment_id = request.POST.get('appointment_id')
        zoom_meeting_id = request.POST.get('zoom_meeting_id')
        zoom_join_url = request.POST.get('zoom_join_url')
        meeting_details = request.POST.get('meeting_details')
        
        if not appointment_id or not zoom_meeting_id:
            messages.error(request, 'Please select an appointment and enter Meeting ID.')
        else:
            try:
                appointment = zoom_appointment.objects.get(
                    id=appointment_id,
                    doctor=request.user
                )
                # Update meeting details
                appointment.zoom_meeting_id = zoom_meeting_id
                if zoom_join_url:
                    appointment.zoom_join_url = zoom_join_url
                if meeting_details:
                    appointment.meeting_details = meeting_details
                    appointment.meeting_details_updated_at = timezone.now()
                appointment.save()
                messages.success(request, f'Meeting details saved for {appointment.patient.user.get_full_name()}.')
            except zoom_appointment.DoesNotExist:
                messages.error(request, 'Appointment not found.')
        
        return redirect('doctors_meeting')
    
    return render(request, 'doctors_meeting.html', {
        'all_appointments': all_appointments,
        'recent_appointments': recent_appointments,
    })


def termspage(request):
    return render(request, 'terms.html')


@login_required
def doctors_appointmenthistorypage(request):

    # Only staff users (doctors) may view this page
    if not request.user.is_staff:
        return redirect('home')

    # Import here to avoid circular imports in some environments
    from .models import zoom_appointment

    # Show all appointments for this doctor
    appointments = zoom_appointment.objects.filter(
        doctor=request.user
    ).select_related('patient__user').order_by('-date')
    return render(request, 'doctors_appointmenthistory.html', {
        'appointments': appointments,
        'now': timezone.now(),
    })

@login_required
def admin_dashboardpage(request):

    user = request.user

    # Superusers see the admin dashboard
    if user.is_superuser and user.is_staff is True:
        # Fetch doctors (staff users with doctor profiles)
        from django.db.models import Count
        doctors = User.objects.filter(
            is_staff=True
        ).select_related('userinfo', 'doctor').filter(
            doctor__isnull=False
        ).annotate(
            appointment_count=Count('doctor_appointments')
        ).order_by('-appointment_count')

        # Fetch patients (regular users)
        patients = User.objects.filter(is_staff=False, is_superuser=False).select_related('userinfo')

        # Count appointments
        try:
            from .models import zoom_appointment
            total_appointments = zoom_appointment.objects.count()
        except Exception:
            total_appointments = 0

        return render(request, 'admin_dashboard.html', {
            'doctors': doctors,
            'patients': patients,
            'total_doctors': doctors.count(),
            'total_patients': patients.count(),
            'total_appointments': total_appointments,
        })

    # Staff users (doctors) should go to their dashboard
    if user.is_staff and user.is_superuser is False:
        return redirect('doctors_dashboard')

    # All other users go to the normal user dashboard
    return redirect('user_dashboard')

def zoom_appointmentpage(request):
    if request.method == "POST":
        # You can get appointment details from the form
        patient_name = request.POST.get("patient_name")
        doctor_name = request.POST.get("doctor_name")
        date = request.POST.get("date")  # e.g. 2025-11-15 14:00
        start_time = datetime.strptime(date, "%Y-%m-%d %H:%M")

        # Create meeting
        topic = f"Consultation with Dr. {doctor_name}"
        meeting = create_zoom_meeting(topic, start_time, duration=45)

        if meeting:
            join_url = meeting["join_url"]
            start_url = meeting["start_url"]

            # Save to your Appointment model (if you have one)
            # Appointment.objects.create(..., zoom_link=join_url)

            message = f"Meeting created! Link: {join_url}"
            redirect_url = reverse('user_dashboard')
            return redirect(f"{reverse('success_page')}?message={message}&redirect_url={redirect_url}")
        else:
            messages.error(request, "Failed to create Zoom meeting.")

        return redirect("user_dashboard")

    return render(request, "book.html")

def admin_doctorspage(request):
    return render(request, 'admin_doctors.html')

def admin_patientspage(request):
    return render(request, 'admin_patients.html')


def reset_passwordpage(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        if not email:
            messages.error(request, 'Please enter your email address.')
            return render(request, 'forgot_password.html')
        
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, 'Please enter a valid email address.')
            return render(request, 'forgot_password.html')
        
        try:
            user = User.objects.get(email=email)
            
            # Create password reset token
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            reset_link = f"http://{request.get_host()}/reset-password-confirm/{uid}/{token}/"
            
            subject = "Reset your password"
            context = {
                "user": user,
                "reset_link": reset_link,
            }
            
            # Create password reset email template
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; background-color: #f5f5f5; margin: 0; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                    <h2 style="color: #0d6efd; margin-bottom: 20px;">Password Reset Request</h2>
                    <p>Hello {user.first_name or user.username},</p>
                    <p>We received a request to reset your password for your MediCare account. Click the button below to reset your password:</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{reset_link}" style="background-color: #0d6efd; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">Reset Password</a>
                    </div>
                    <p style="color: #666; font-size: 14px;">This link will expire in 24 hours. If you didn't request this password reset, you can safely ignore this email.</p>
                    <p style="color: #666; font-size: 14px;">If the button doesn't work, copy and paste this link into your browser:</p>
                    <p style="word-break: break-all; color: #666; font-size: 14px;"><a href="{reset_link}" style="color: #0d6efd;">{reset_link}</a></p>
                </div>
            </body>
            </html>
            """
            
            text_content = strip_tags(html_content)
            
            # Build the email
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email="noreply@yourapp.com",
                to=[user.email],
            )
            email.attach_alternative(html_content, "text/html")
            email.send()
            
            message = 'Password reset link has been sent to your email. Please check your inbox.'
            redirect_url = reverse('login')
            return redirect(f"{reverse('success_page')}?message={message}&redirect_url={redirect_url}")
            
        except User.DoesNotExist:
            # Don't reveal that user doesn't exist
            message = 'Password reset link has been sent to your email. Please check your inbox.'
            redirect_url = reverse('login')
            return redirect(f"{reverse('success_page')}?message={message}&redirect_url={redirect_url}")
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
            return render(request, 'forgot_password.html')
    return render(request, 'forgot_password.html')


def reset_password_confirm(request, uidb64, token):
    """Handle password reset confirmation"""
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        messages.error(request, 'The password reset link is invalid.')
        return redirect('login')
    
    # Check if token is valid
    if not default_token_generator.check_token(user, token):
        messages.error(request, 'The password reset link is invalid or has expired.')
        return redirect('login')
    
    if request.method == 'POST':
        new_password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        if not new_password or not confirm_password:
            messages.error(request, 'Please fill in all fields.')
            return render(request, 'reset_password_confirm.html', {'valid_link': True})
        
        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'reset_password_confirm.html', {'valid_link': True})
        
        if len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return render(request, 'reset_password_confirm.html', {'valid_link': True})
        
        # Set new password
        user.set_password(new_password)
        user.save()
        
        message = 'Your password has been reset successfully. You can now log in.'
        redirect_url = reverse('login')
        return redirect(f"{reverse('success_page')}?message={message}&redirect_url={redirect_url}")
    
    return render(request, 'reset_password_confirm.html', {'valid_link': True})


@login_required
# def edit_doctorsprofilepage(request):
#     # Only staff (doctors/admins) may access this page
#     if not request.user.is_staff:
#         return redirect('home')

#     # Determine which user we're editing.
#     # If a `user_id` is supplied, only allow superusers to edit other accounts.
#     user_id = request.POST.get('user_id') or request.GET.get('user_id')
#     if user_id and request.user.is_superuser:
#         try:
#             target = User.objects.get(pk=int(user_id))
#         except (ValueError, User.DoesNotExist):
#             messages.error(request, 'Requested doctor not found.')
#             return redirect('doctors_profile')
#     else:
#         target = request.user

#     if request.method == 'POST':
#         # Basic user fields
#         first_name = request.POST.get('firstName', '').strip()
#         last_name = request.POST.get('lastName', '').strip()
#         email = request.POST.get('email', '').strip()

#         if first_name:
#             target.first_name = first_name
#         if last_name:
#             target.last_name = last_name

#         # Validate email uniqueness before assigning
#         if email:
#             if User.objects.filter(email=email).exclude(pk=target.pk).exists():
#                 messages.error(request, 'Email address is already used by another account.')
#                 return redirect(request.path)
#             target.email = email

#         target.save()

#         # UserInfo data
#         userinfo, _ = UserInfo.objects.get_or_create(user=target)
#         phone = request.POST.get('phone', '').strip()
#         if phone:
#             userinfo.phone_number = phone

#         bio = request.POST.get('bio', '').strip()
#         if bio and hasattr(userinfo, 'bio'):
#             userinfo.bio = bio

#         # Optional extra fields
#         experience = request.POST.get('experience', '').strip()
#         if experience.isnumeric() and hasattr(userinfo, 'experience_years'):
#             userinfo.experience_years = int(experience)

#         # Handle optional passport/profile image upload
#         if request.FILES.get('passport'):
#             try:
#                 userinfo.passport = request.FILES.get('passport')
#             except Exception:
#                 # ignore file save errors; can add logging
#                 pass

#         # Location/Gender/DOB fields if present in model
#         dob = request.POST.get('dob')
#         if dob and hasattr(userinfo, 'dob'):
#             try:
#                 # store as YYYY-MM-DD (forms send date type)
#                 userinfo.dob = dob
#             except Exception:
#                 pass

#         gender = request.POST.get('gender')
#         if gender and hasattr(userinfo, 'gender'):
#             userinfo.gender = gender

#         if request.POST.get('location') and hasattr(userinfo, 'location'):
#             userinfo.location = request.POST.get('location').strip()

#         userinfo.save()

#         # Doctor model (speciality)
#         speciality = request.POST.get('speciality', '').strip()
#         if speciality:
#             doctor_obj, created = Doctor.objects.get_or_create(user=target)
#             doctor_obj.speciality = speciality
#             doctor_obj.save()

#         messages.success(request, "Profile updated successfully!")
#         return redirect('doctors_profile')

#     # GET request — pre-fill form
#     doctor_obj = Doctor.objects.filter(user=target).first()
#     userinfo = getattr(target, 'userinfo', None)

#     return render(request, 'doctor_editprofile.html', {
#         'target': target,
#         'userinfo': userinfo,
#         'doctor': doctor_obj,
#     })


# Dedicated Admin Pages for Doctors and Patients Management

def success_page(request):
    message = request.GET.get('message', 'Success!')
    redirect_url = request.GET.get('redirect_url', '/')
    return render(request, 'success.html', {'message': message, 'redirect_url': redirect_url})

@login_required
def admin_doctors_management(request):

    if not request.user.is_superuser:
        return redirect('home')
    
    # Get search and filter parameters
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', 'all')  # 'all', 'active', 'blocked'
    
    # Fetch doctors (staff users with doctor profiles)
    doctors = User.objects.filter(is_staff=True, is_superuser=False).select_related('userinfo', 'doctor').filter(doctor__isnull=False)

    # Apply search filter
    if search_query:
        doctors = doctors.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(userinfo__phone_number__icontains=search_query)
        )
    
    # Apply status filter
    if status_filter == 'active':
        doctors = doctors.filter(is_active=True)
    elif status_filter == 'blocked':
        doctors = doctors.filter(is_active=False)
    
    return render(request, 'admin_doctors_list.html', {
        'doctors': doctors,
        'search_query': search_query,
        'status_filter': status_filter,
    })


@login_required
def admin_patients_management(request):

    if not request.user.is_superuser:
        return redirect('home')
    
    # Get search and filter parameters
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', 'all')  # 'all', 'active', 'blocked'
    
    # Fetch patients (regular users)
    patients = User.objects.filter(is_staff=False, is_superuser=False).select_related('userinfo')
    
    # Apply search filter
    if search_query:
        patients = patients.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(userinfo__phone_number__icontains=search_query)
        )
    
    # Apply status filter
    if status_filter == 'active':
        patients = patients.filter(is_active=True)
    elif status_filter == 'blocked':
        patients = patients.filter(is_active=False)
    
    return render(request, 'admin_patients_list.html', {
        'patients': patients,
        'search_query': search_query,
        'status_filter': status_filter,
    })



# Admin API endpoints for user management
@login_required
def admin_block_user(request, user_id):

    if not request.user.is_superuser:
        return redirect('home')
    
    try:
        target_user = User.objects.get(pk=user_id)
        target_user.is_active = False
        target_user.save()
        message = f'{target_user.get_full_name() or target_user.username} has been blocked.'
        redirect_url = reverse('admin_dashboard')
        return redirect(f"{reverse('success_page')}?message={message}&redirect_url={redirect_url}")
    except User.DoesNotExist:
        messages.error(request, 'User not found.')
    
    return redirect('admin_dashboard')


@login_required
def admin_unblock_user(request, user_id):
    
    if not request.user.is_superuser:
        return redirect('home')
    
    try:
        target_user = User.objects.get(pk=user_id)
        target_user.is_active = True
        target_user.save()
        message = f'{target_user.get_full_name() or target_user.username} has been unblocked.'
        redirect_url = reverse('admin_dashboard')
        return redirect(f"{reverse('success_page')}?message={message}&redirect_url={redirect_url}")
    except User.DoesNotExist:
        messages.error(request, 'User not found.')
    
    return redirect('admin_dashboard')


@login_required
def admin_delete_user(request, user_id):
    
    if not request.user.is_superuser:
        return redirect('home')
    
    try:
        target_user = User.objects.get(pk=user_id)
        user_display = target_user.get_full_name() or target_user.username
        target_user.delete()
        message = f'{user_display} has been deleted.'
        redirect_url = reverse('admin_dashboard')
        return redirect(f"{reverse('success_page')}?message={message}&redirect_url={redirect_url}")
    except User.DoesNotExist:
        messages.error(request, 'User not found.')
    
    return redirect('admin_dashboard')


# ==================== APPOINTMENT MANAGEMENT VIEWS ====================

# UTILITY FUNCTIONS

def check_appointment_overlap(doctor, start_datetime, duration, exclude_appointment_id=None):

    end_datetime = start_datetime + timedelta(minutes=duration)
    
    # Get all approved appointments for the doctor
    query = zoom_appointment.objects.filter(
        doctor=doctor,
        status__in=['pending', 'approved'],
        date__lt=end_datetime,
        date__gte=start_datetime - timedelta(hours=24)  # Look ahead a day
    )
    
    if exclude_appointment_id:
        query = query.exclude(id=exclude_appointment_id)
    
    for appointment in query:
        appointment_end = appointment.date + timedelta(minutes=appointment.duration)
        # Check if times overlap
        if not (end_datetime <= appointment.date or start_datetime >= appointment_end):
            return True
    
    return False


def get_doctor_availability(doctor, date):
    """Get available time slots for a doctor on a specific date."""
    from .models import DoctorAvailability
    
    date_obj = datetime.strptime(date, '%Y-%m-%d').date()
    day_name = date_obj.strftime('%A')  # e.g., 'Monday'
    available_times = []

    # Get doctor's availability for this day of week
    availabilities = DoctorAvailability.objects.filter(
        doctor=doctor,
        day_of_week=day_name,
        is_active=True
    ).order_by('start_time')

    # If no specific availability set, use default working hours (9 AM - 5 PM)
    if not availabilities.exists():
        start_hour = 9
        end_hour = 17
        time_ranges = [(time(start_hour, 0), time(end_hour, 0))]
    else:
        time_ranges = [(avail.start_time, avail.end_time) for avail in availabilities]

    slot_duration = 30  # minutes

    for start_time, end_time in time_ranges:
        # Generate 30-minute slots within this time range
        current_time = start_time
        while current_time < end_time:
            slot_datetime = datetime.combine(date_obj, current_time)
            slot_time = timezone.make_aware(slot_datetime) if timezone.is_naive(slot_datetime) else slot_datetime

            # Skip past times
            if slot_time <= timezone.now():
                current_time = (datetime.combine(date_obj, current_time) + timedelta(minutes=slot_duration)).time()
                continue

            # Check if slot is already booked
            if not check_appointment_overlap(doctor, slot_time, slot_duration):
                available_times.append(current_time.strftime('%H:%M'))

            # Move to next slot
            current_time = (datetime.combine(date_obj, current_time) + timedelta(minutes=slot_duration)).time()

    return available_times


# PATIENT VIEWS

@login_required
def doctorbook_appointment(request):

    if request.user.is_staff:
        messages.warning(request, 'Doctors cannot book appointments.')
        return redirect('doctors_dashboard')

    # Get patient profile
    try:
        patient = Patient.objects.get(user=request.user)
    except Patient.DoesNotExist:
        messages.error(request, 'Patient profile not found. Please contact support.')
        return redirect('user_dashboard')

    # Get all available doctors - only those who are staff, active, and have a doctor profile
    doctors = User.objects.filter(is_staff=True, is_active=True, is_superuser=False).select_related('userinfo', 'doctor').filter(doctor__isnull=False)

    if request.method == 'POST':
        doctor_id = request.POST.get('doctor')
        appointment_date = request.POST.get('appointment_date')
        appointment_time = request.POST.get('appointment_time')
        reason = request.POST.get('reason', '').strip()

        # Validation
        if not all([doctor_id, appointment_date, appointment_time, reason]):
            messages.error(request, 'Please fill all required fields.')
            return render(request, 'book_appointment.html', {'doctors': doctors})

        try:
            doctor = User.objects.get(pk=doctor_id, is_staff=True, is_active=True, is_superuser=False, doctor__isnull=False)
        except User.DoesNotExist:
            messages.error(request, 'Selected doctor not found.')
            return render(request, 'book_appointment.html', {'doctors': doctors})

        # Parse datetime
        try:
            appointment_datetime = timezone.make_aware(
                datetime.strptime(f"{appointment_date} {appointment_time}", "%Y-%m-%d %H:%M")
            )
        except ValueError:
            messages.error(request, 'Invalid date or time format.')
            return render(request, 'book_appointment.html', {'doctors': doctors})

        # Validation: Future appointment only
        if appointment_datetime <= timezone.now():
            messages.error(request, 'Appointment must be in the future.')
            return render(request, 'book_appointment.html', {'doctors': doctors})

        # Check for overlaps
        if check_appointment_overlap(doctor, appointment_datetime, 30):
            messages.error(request, 'This time slot is not available. Please choose another.')
            return render(request, 'book_appointment.html', {'doctors': doctors})

        # Create appointment
        try:
            from .models import Notification
            
            appointment = zoom_appointment.objects.create(
                doctor=doctor,
                patient=patient,
                date=appointment_datetime,
                reason=reason,
                duration=30,
                status='pending'  # Pending doctor approval
            )
            
            # Create notification for doctor
            patient_name = request.user.get_full_name() or request.user.username
            Notification.objects.create(
                user=doctor,
                notification_type='appointment_booked',
                message=f'New appointment request from {patient_name} on {appointment_datetime.strftime("%B %d, %Y at %I:%M %p")}',
                appointment=appointment
            )
            
            message = f'Appointment booked successfully with Dr. {doctor.get_full_name()}. Status: Pending doctor approval.'
            redirect_url = reverse('patient_appointments')
            return redirect(f"{reverse('success_page')}?message={message}&redirect_url={redirect_url}")
        except Exception as e:
            messages.error(request, f'Error booking appointment: {str(e)}')
            return render(request, 'book_appointment.html', {'doctors': doctors})

    return render(request, 'book_appointment.html', {'doctors': doctors})


@login_required
def patient_appointments(request):

    if request.user.is_staff:
        return redirect('doctors_dashboard')

    try:
        patient = Patient.objects.get(user=request.user)
    except Patient.DoesNotExist:
        messages.error(request, 'Patient profile not found.')
        return redirect('user_dashboard')

    # Get appointments
    appointments = zoom_appointment.objects.filter(patient=patient).select_related('doctor', 'doctor__userinfo')

    # Search filter
    search_query = request.GET.get('search', '').strip()
    if search_query:
        appointments = appointments.filter(
            Q(doctor__first_name__icontains=search_query) |
            Q(doctor__last_name__icontains=search_query) |
            Q(reason__icontains=search_query)
        )

    # Status filter
    status_filter = request.GET.get('status', '')
    if status_filter and status_filter != 'all':
        appointments = appointments.filter(status=status_filter)

    # Admin status filter
    admin_status_filter = request.GET.get('admin_status', '')
    if admin_status_filter and admin_status_filter != 'all':
        appointments = appointments.filter(admin_status=admin_status_filter)

    # Type filter: upcoming vs past
    app_type = request.GET.get('type', 'upcoming')
    now = timezone.now()

    if app_type == 'upcoming':
        appointments = appointments.filter(date__gte=now, status__in=['pending', 'approved'])
    elif app_type == 'past':
        appointments = appointments.filter(Q(date__lt=now) | Q(status__in=['completed', 'cancelled']))

    appointments = appointments.order_by('-date')

    return render(request, 'patient_appointments.html', {
        'appointments': appointments,
        'search_query': search_query,
        'status_filter': status_filter,
        'admin_status_filter': admin_status_filter,
        'app_type': app_type,
    })


@login_required
def reschedule_appointment(request, appointment_id):

    if request.user.is_staff:
        return redirect('doctors_dashboard')
    
    try:
        patient = Patient.objects.get(user=request.user)
        appointment = zoom_appointment.objects.get(pk=appointment_id, patient=patient)
    except (Patient.DoesNotExist, zoom_appointment.DoesNotExist):
        messages.error(request, 'Appointment not found.')
        return redirect('patient_appointments')
    
    # Can only reschedule pending or approved appointments
    if appointment.status not in ['pending', 'approved']:
        messages.warning(request, 'You cannot reschedule this appointment.')
        return redirect('patient_appointments')
    
    if request.method == 'POST':
        new_date = request.POST.get('appointment_date')
        new_time = request.POST.get('appointment_time')
        reschedule_reason = request.POST.get('reschedule_reason', '').strip()
        
        if not all([new_date, new_time]):
            messages.error(request, 'Please select a new date and time.')
        else:
            try:
                new_datetime = timezone.make_aware(
                    datetime.strptime(f"{new_date} {new_time}", "%Y-%m-%d %H:%M")
                )
                 
                # Validation
                if new_datetime <= timezone.now():
                    messages.error(request, 'New appointment must be in the future.')
                elif check_appointment_overlap(appointment.doctor, new_datetime, appointment.duration, exclude_appointment_id=appointment.id):
                    messages.error(request, 'This time slot is not available.')
                else:
                    # Create new appointment with link to original
                    new_appointment = zoom_appointment.objects.create(
                        doctor=appointment.doctor,
                        patient=appointment.patient,
                        date=new_datetime,
                        reason=appointment.reason,
                        duration=appointment.duration,
                        status='pending',
                        admin_status=appointment.admin_status,  # Maintain admin approval status
                        original_appointment=appointment,
                        reschedule_reason=reschedule_reason
                    )
                    
                    # Cancel old appointment
                    appointment.status = 'cancelled'
                    appointment.save()
                    
                    message = 'Appointment rescheduled successfully.'
                    redirect_url = reverse('patient_appointments')
                    return redirect(f"{reverse('success_page')}?message={message}&redirect_url={redirect_url}")
            except ValueError:
                messages.error(request, 'Invalid date or time format.')
    
    return render(request, 'reschedule_appointment.html', {'appointment': appointment})


@login_required
def cancel_appointment(request, appointment_id):
    from .models import Notification

    if request.user.is_staff:
        return redirect('doctors_dashboard')

    try:
        patient = Patient.objects.get(user=request.user)
        appointment = zoom_appointment.objects.get(pk=appointment_id, patient=patient)
    except (Patient.DoesNotExist, zoom_appointment.DoesNotExist):
        messages.error(request, 'Appointment not found.')
        return redirect('patient_appointments')

    if appointment.status in ['completed', 'cancelled']:
        messages.warning(request, 'Cannot cancel this appointment.')
        return redirect('patient_appointments')

    if request.method == 'POST':
        appointment.status = 'cancelled'
        appointment.save()
        
        # Create notification for doctor
        patient_name = request.user.get_full_name() or request.user.username
        Notification.objects.create(
            user=appointment.doctor,
            notification_type='appointment_cancelled',
            message=f'{patient_name} has cancelled their appointment on {appointment.date.strftime("%B %d, %Y at %I:%M %p")}',
            appointment=appointment
        )
        
        message = 'Appointment cancelled successfully.'
        redirect_url = reverse('patient_appointments')
        return redirect(f"{reverse('success_page')}?message={message}&redirect_url={redirect_url}")

    # GET: Show confirmation page
    return render(request, 'confirm_cancel_appointment.html', {'appointment': appointment})


# DOCTOR VIEWS

@login_required
def doctor_appointments(request):

    if not request.user.is_staff:
        return redirect('user_dashboard')

    # Get appointments for this doctor
    appointments = zoom_appointment.objects.filter(
        doctor=request.user
    ).select_related('patient', 'patient__user', 'patient__user__userinfo')

    # Search filter
    search_query = request.GET.get('search', '').strip()
    if search_query:
        appointments = appointments.filter(
            Q(patient__user__first_name__icontains=search_query) |
            Q(patient__user__last_name__icontains=search_query) |
            Q(patient__user__email__icontains=search_query) |
            Q(reason__icontains=search_query)
        )

    # Status filter
    status_filter = request.GET.get('status', '')
    if status_filter and status_filter != 'all':
        appointments = appointments.filter(status=status_filter)

    # Type filter
    app_type = request.GET.get('type', 'pending')
    now = timezone.now()

    if app_type == 'pending':
        appointments = appointments.filter(status='pending')
    elif app_type == 'upcoming':
        appointments = appointments.filter(status='approved', date__gte=now)
    elif app_type == 'past':
        appointments = appointments.filter(status__in=['completed', 'cancelled'], date__lt=now)

    appointments = appointments.order_by('-date')

    return render(request, 'doctor_appointments.html', {
        'appointments': appointments,
        'search_query': search_query,
        'status_filter': status_filter,
        'app_type': app_type,
    })


@login_required
def approve_appointment(request, appointment_id):
    from .models import Notification

    if not request.user.is_staff:
        return redirect('user_dashboard')

    try:
        appointment = zoom_appointment.objects.get(
            pk=appointment_id,
            doctor=request.user,
            status='pending'
        )
        appointment.status = 'approved'

        # Create Zoom meeting if not already created
        if not appointment.zoom_join_url:
            topic = f"Consultation - {appointment.patient.user.get_full_name()}"
            start_time = appointment.date
            meeting = create_zoom_meeting(topic, start_time, duration=appointment.duration or 30)
            if meeting:
                appointment.zoom_meeting_id = meeting.get('id', '')
                appointment.zoom_join_url = meeting.get('join_url', '')
                appointment.zoom_start_url = meeting.get('start_url', '')

        appointment.save()
        
        # Create notification for patient
        doctor_name = appointment.doctor.get_full_name() or appointment.doctor.username
        Notification.objects.create(
            user=appointment.patient.user,
            notification_type='appointment_approved',
            message=f'Dr. {doctor_name} has approved your appointment on {appointment.date.strftime("%B %d, %Y at %I:%M %p")}',
            appointment=appointment
        )
        
        message = f'Appointment with {appointment.patient.user.get_full_name()} approved.'
        redirect_url = reverse('doctor_appointments')
        return redirect(f"{reverse('success_page')}?message={message}&redirect_url={redirect_url}")
    except zoom_appointment.DoesNotExist:
        messages.error(request, 'Appointment not found or already processed.')

    return redirect('doctor_appointments')


@login_required
def decline_appointment(request, appointment_id):
    from .models import Notification

    if not request.user.is_staff:
        return redirect('user_dashboard')

    if request.method == 'POST':
        decline_reason = request.POST.get('decline_reason', '').strip()

        try:
            appointment = zoom_appointment.objects.get(
                pk=appointment_id,
                doctor=request.user,
                status='pending'
            )
            appointment.status = 'cancelled'
            appointment.reschedule_reason = decline_reason  # Store reason
            appointment.save()
            
            # Create notification for patient
            doctor_name = appointment.doctor.get_full_name() or appointment.doctor.username
            Notification.objects.create(
                user=appointment.patient.user,
                notification_type='appointment_declined',
                message=f'Dr. {doctor_name} has declined your appointment on {appointment.date.strftime("%B %d, %Y at %I:%M %p")}. Reason: {decline_reason or "Not specified"}',
                appointment=appointment
            )
            
            message = 'Appointment declined.'
            redirect_url = reverse('doctor_appointments')
            return redirect(f"{reverse('success_page')}?message={message}&redirect_url={redirect_url}")
        except zoom_appointment.DoesNotExist:
            messages.error(request, 'Appointment not found or already processed.')

        return redirect('doctor_appointments')

    # GET: Show decline reason form
    try:
        appointment = zoom_appointment.objects.get(
            pk=appointment_id,
            doctor=request.user,
            status='pending'
        )
    except zoom_appointment.DoesNotExist:
        messages.error(request, 'Appointment not found or already processed.')
        return redirect('doctor_appointments')

    return render(request, 'decline_appointment.html', {'appointment': appointment})


@login_required
def request_reschedule(request, appointment_id):

    if not request.user.is_staff:
        return redirect('user_dashboard')

    if request.method == 'POST':
        reschedule_reason = request.POST.get('reschedule_reason', '').strip()

        try:
            appointment = zoom_appointment.objects.get(
                pk=appointment_id,
                doctor=request.user,
                status__in=['pending', 'approved']
            )
            appointment.status = 'reschedule_requested'
            appointment.reschedule_reason = reschedule_reason
            appointment.save()
            message = 'Reschedule request sent to patient.'
            redirect_url = reverse('doctor_appointments')
            return redirect(f"{reverse('success_page')}?message={message}&redirect_url={redirect_url}")
        except zoom_appointment.DoesNotExist:
            messages.error(request, 'Appointment not found or already processed.')

        return redirect('doctor_appointments')

    # GET: Show reschedule reason form
    try:
        appointment = zoom_appointment.objects.get(
            pk=appointment_id,
            doctor=request.user,
            status__in=['pending', 'approved']
        )
    except zoom_appointment.DoesNotExist:
        messages.error(request, 'Appointment not found or already processed.')
        return redirect('doctor_appointments')

    return render(request, 'request_reschedule.html', {'appointment': appointment})


@login_required
def complete_appointment(request, appointment_id):

    if not request.user.is_staff:
        return redirect('user_dashboard')

    try:
        appointment = zoom_appointment.objects.get(
            pk=appointment_id,
            doctor=request.user,
            status='approved'
        )
    except zoom_appointment.DoesNotExist:
        messages.error(request, 'Appointment not found or not approved yet.')
        return redirect('doctor_appointments')

    if request.method == 'POST':
        from .models import Notification
        
        notes = request.POST.get('notes', '').strip()
        appointment.status = 'completed'
        appointment.notes = notes
        appointment.save()
        
        # Create notification for patient
        doctor_name = appointment.doctor.get_full_name() or appointment.doctor.username
        Notification.objects.create(
            user=appointment.patient.user,
            notification_type='appointment_completed',
            message=f'Your appointment with Dr. {doctor_name} on {appointment.date.strftime("%B %d, %Y at %I:%M %p")} has been completed',
            appointment=appointment
        )
        
        message = 'Appointment marked as completed.'
        redirect_url = reverse('doctor_appointments')
        return redirect(f"{reverse('success_page')}?message={message}&redirect_url={redirect_url}")

    return render(request, 'complete_appointment.html', {'appointment': appointment})


# API/AJAX ENDPOINTS

@login_required
def get_available_times(request):

    doctor_id = request.GET.get('doctor_id')
    date = request.GET.get('date')

    if not all([doctor_id, date]):
        return JsonResponse({'error': 'Missing parameters'}, status=400)

    try:
        doctor = User.objects.get(pk=doctor_id, is_staff=True, is_active=True, doctor__isnull=False)
    except User.DoesNotExist:
        return JsonResponse({'error': 'Doctor not found'}, status=404)

    available_times = get_doctor_availability(doctor, date)
    return JsonResponse({'times': available_times})


@login_required
def add_doctor_availability(request):
   
    if not hasattr(request.user, 'doctor'):
        return JsonResponse({'error': 'Access denied'}, status=403)

    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        day_of_week = data.get('day_of_week')
        start_time = data.get('start_time')
        end_time = data.get('end_time')

        if not all([day_of_week, start_time, end_time]):
            return JsonResponse({'error': 'Missing parameters'}, status=400)

        try:
            from .models import DoctorAvailability
            availability = DoctorAvailability.objects.create(
                doctor=request.user,
                day_of_week=day_of_week,
                start_time=start_time,
                end_time=end_time
            )
            return JsonResponse({'success': True, 'id': availability.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid method'}, status=405)


@login_required
def delete_doctor_availability(request, availability_id):
    """Delete availability slot for doctor."""
    if not hasattr(request.user, 'doctor'):
        return JsonResponse({'error': 'Access denied'}, status=403)

    try:
        from .models import DoctorAvailability
        availability = DoctorAvailability.objects.get(
            pk=availability_id,
            doctor=request.user
        )
        availability.delete()
        return JsonResponse({'success': True})
    except DoctorAvailability.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@login_required
def get_doctor_availability_schedule(request):
   
    if not hasattr(request.user, 'doctor'):
        return JsonResponse({'error': 'Access denied'}, status=403)

    try:
        from .models import DoctorAvailability
        availabilities = DoctorAvailability.objects.filter(
            doctor=request.user,
            is_active=True
        ).order_by('start_time')

        schedule = {}
        for avail in availabilities:
            if avail.day_of_week not in schedule:
                schedule[avail.day_of_week] = []
            schedule[avail.day_of_week].append({
                'id': avail.id,
                'start_time': avail.start_time.strftime('%H:%M'),
                'end_time': avail.end_time.strftime('%H:%M')
            })

        return JsonResponse({'schedule': schedule})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# Admin appointment management
@login_required
def admin_appointments(request):

    if not request.user.is_superuser:
        return redirect('admin_dashboard')

    # Search and filter
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '')
    admin_status_filter = request.GET.get('admin_status', '')

    appointments = zoom_appointment.objects.select_related(
        'doctor', 'patient', 'patient__user', 'doctor__userinfo'
    ).all().order_by('-date')

    if search_query:
        appointments = appointments.filter(
            Q(doctor__first_name__icontains=search_query) |
            Q(doctor__last_name__icontains=search_query) |
            Q(patient__user__first_name__icontains=search_query) |
            Q(patient__user__last_name__icontains=search_query) |
            Q(reason__icontains=search_query)
        )

    if status_filter:
        appointments = appointments.filter(status=status_filter)

    if admin_status_filter:
        appointments = appointments.filter(admin_status=admin_status_filter)

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(appointments, 25)
    page = request.GET.get('page')
    appointments_page = paginator.get_page(page)

    return render(request, 'admin_appointments.html', {
        'appointments': appointments_page,
        'search_query': search_query,
        'status_filter': status_filter,
        'admin_status_filter': admin_status_filter,
    })


@login_required
def admin_approve_appointment(request, appointment_id):

    if not request.user.is_superuser:
        return redirect('admin_dashboard')

    try:
        appointment = zoom_appointment.objects.get(pk=appointment_id)

        # Only allow approving appointments that are still pending admin review
        if appointment.admin_status == 'pending':
            appointment.admin_status = 'approved'
            appointment.save()

            message = f'Appointment for {appointment.patient.user.get_full_name()} approved successfully.'
            redirect_url = reverse('admin_appointments_list')
            return redirect(f"{reverse('success_page')}?message={message}&redirect_url={redirect_url}")
        else:
            messages.error(request, 'Appointment has already been processed.')
    except zoom_appointment.DoesNotExist:
        messages.error(request, 'Appointment not found.')

    return redirect('admin_appointments_list')


@login_required
def admin_reject_appointment(request, appointment_id):

    if not request.user.is_superuser:
        return redirect('admin_dashboard')

    try:
        appointment = zoom_appointment.objects.get(pk=appointment_id)

        # Only allow rejecting appointments that are still pending admin review
        if appointment.admin_status == 'pending':
            if request.method == 'POST':
                rejection_reason = request.POST.get('rejection_reason', '').strip()
                appointment.admin_status = 'rejected'
                appointment.status = 'cancelled'  # Also cancel the appointment
                if rejection_reason:
                    # Append rejection reason to existing reschedule_reason field
                    if appointment.reschedule_reason:
                        appointment.reschedule_reason = f"{appointment.reschedule_reason} | Admin Rejection: {rejection_reason}"
                    else:
                        appointment.reschedule_reason = f"Admin Rejection: {rejection_reason}"
                appointment.save()

                message = f'Appointment for {appointment.patient.user.get_full_name()} rejected.'
                redirect_url = reverse('admin_appointments_list')
                return redirect(f"{reverse('success_page')}?message={message}&redirect_url={redirect_url}")
            else:
                # Show confirmation page for GET request
                return render(request, 'admin_reject_appointment.html', {'appointment': appointment})
        else:
            messages.error(request, 'Appointment has already been processed.')
    except zoom_appointment.DoesNotExist:
        messages.error(request, 'Appointment not found.')

    return redirect('admin_appointments_list')


@login_required
def admin_edit_appointment(request, appointment_id):

    if not request.user.is_superuser:
        return redirect('admin_dashboard')

    try:
        appointment = zoom_appointment.objects.select_related('doctor', 'patient', 'patient__user').get(pk=appointment_id)
    except zoom_appointment.DoesNotExist:
        messages.error(request, 'Appointment not found.')
        return redirect('admin_appointments_list')

    doctors = User.objects.filter(is_staff=True, is_active=True).select_related('userinfo', 'doctor').filter(doctor__isnull=False)
    patients = Patient.objects.select_related('user').all()

    if request.method == 'POST':
        doctor_id = request.POST.get('doctor')
        patient_id = request.POST.get('patient')
        date_str = request.POST.get('appointment_date')
        time_str = request.POST.get('appointment_time')
        status = request.POST.get('status')
        reason = request.POST.get('reason', '').strip()
        notes = request.POST.get('notes', '').strip()
        duration = int(request.POST.get('duration', appointment.duration or 30))

        # Validate doctor and patient
        try:
            new_doctor = User.objects.get(pk=doctor_id, is_staff=True, doctor__isnull=False)
        except User.DoesNotExist:
            messages.error(request, 'Selected doctor not found.')
            return render(request, 'admin_edit_appointment.html', {'appointment': appointment, 'doctors': doctors, 'patients': patients})

        try:
            new_patient = Patient.objects.get(pk=patient_id)
        except Patient.DoesNotExist:
            messages.error(request, 'Selected patient not found.')
            return render(request, 'admin_edit_appointment.html', {'appointment': appointment, 'doctors': doctors, 'patients': patients})

        # Parse datetime
        try:
            new_datetime = timezone.make_aware(datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M"))
        except Exception:
            messages.error(request, 'Invalid date or time format.')
            return render(request, 'admin_edit_appointment.html', {'appointment': appointment, 'doctors': doctors, 'patients': patients})

        # Prevent overlaps for doctor
        if check_appointment_overlap(new_doctor, new_datetime, duration, exclude_appointment_id=appointment.id):
            messages.error(request, 'Selected time overlaps with another appointment for that doctor.')
            return render(request, 'admin_edit_appointment.html', {'appointment': appointment, 'doctors': doctors, 'patients': patients})

        # Update fields
        appointment.doctor = new_doctor
        appointment.patient = new_patient
        appointment.date = new_datetime
        appointment.status = status or appointment.status
        appointment.admin_status = request.POST.get('admin_status', appointment.admin_status) or appointment.admin_status
        appointment.reason = reason or appointment.reason
        appointment.notes = notes
        appointment.duration = duration
        appointment.save()

        message = 'Appointment updated successfully.'
        redirect_url = reverse('admin_appointments_list')
        return redirect(f"{reverse('success_page')}?message={message}&redirect_url={redirect_url}")

    # Pre-fill time and date strings for form
    appointment_date = appointment.date.astimezone(timezone.get_current_timezone()).strftime('%Y-%m-%d')
    appointment_time = appointment.date.astimezone(timezone.get_current_timezone()).strftime('%H:%M')

    return render(request, 'admin_edit_appointment.html', {
        'appointment': appointment,
        'doctors': doctors,
        'patients': patients,
        'appointment_date': appointment_date,
        'appointment_time': appointment_time,
    })


@login_required
def get_patient_appointments_api(request):
    if request.user.is_staff:
        return JsonResponse({'error': 'Access denied'}, status=403)

    try:
        patient = Patient.objects.get(user=request.user)
    except Patient.DoesNotExist:
        return JsonResponse({'error': 'Patient profile not found'}, status=404)

    # Get all appointments for this patient
    appointments = zoom_appointment.objects.filter(patient=patient).select_related(
        'doctor', 'doctor__userinfo', 'doctor__doctor'
    ).order_by('-date')

    now = timezone.now()
    data = {
        'upcoming': [],
        'past': [],
        'stats': {
            'upcoming_count': 0,
            'completed_count': 0,
            'pending_count': 0,
            'cancelled_count': 0,
        }
    }

    for appt in appointments:
        appt_data = {
            'id': appt.id,
            'doctor_name': f"Dr. {appt.doctor.get_full_name()}",
            'doctor_speciality': appt.doctor.doctor.speciality if hasattr(appt.doctor, 'doctor') else 'General',
            'date': appt.date.strftime('%Y-%m-%d'),
            'time': appt.date.strftime('%H:%M'),
            'datetime': appt.date.isoformat(),
            'status': appt.status,
            'status_display': appt.get_status_display(),
            'admin_status': appt.admin_status,
            'admin_status_display': appt.get_admin_status_display(),
            'reason': appt.reason or '',
            'notes': appt.notes or '',
            'reschedule_reason': appt.reschedule_reason or '',
            'duration': appt.duration,
            'has_zoom': bool(appt.zoom_join_url),
            'zoom_join_url': appt.zoom_join_url or '',
            'doctor_avatar': appt.doctor.userinfo.profile_picture.url if hasattr(appt.doctor, 'userinfo') and appt.doctor.userinfo.profile_picture else None,
        }

        # Categorize as upcoming or past
        if appt.date >= now and appt.status in ['pending', 'approved']:
            data['upcoming'].append(appt_data)
            data['stats']['upcoming_count'] += 1
        else:
            data['past'].append(appt_data)

        # Update stats
        if appt.status == 'completed':
            data['stats']['completed_count'] += 1
        elif appt.status == 'pending':
            data['stats']['pending_count'] += 1
        elif appt.status == 'cancelled':
            data['stats']['cancelled_count'] += 1

    return JsonResponse(data)


@login_required
def get_appointment_notifications_api(request):
    from .models import Notification
    
    # Get unread notifications
    unread_notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).select_related('appointment').order_by('-created_at')[:15]
    
    # Get read notifications (recent ones)
    read_notifications = Notification.objects.filter(
        user=request.user,
        is_read=True
    ).select_related('appointment').order_by('-created_at')[:5]
    
    notifications = []
    
    # Icon mapping
    icon_map = {
        'appointment_booked': 'fa-calendar-plus',
        'appointment_approved': 'fa-check-circle',
        'appointment_declined': 'fa-times-circle',
        'appointment_cancelled': 'fa-ban',
        'appointment_completed': 'fa-check-double',
        'appointment_reschedule_requested': 'fa-clock',
        'message_received': 'fa-envelope',
    }
    
    # Type mapping for styling
    type_map = {
        'appointment_booked': 'warning',
        'appointment_approved': 'success',
        'appointment_declined': 'danger',
        'appointment_cancelled': 'secondary',
        'appointment_completed': 'info',
        'appointment_reschedule_requested': 'warning',
        'message_received': 'primary',
    }
    
    for notif in unread_notifications:
        notifications.append({
            'id': notif.id,
            'icon': icon_map.get(notif.notification_type, 'fa-bell'),
            'text': notif.message,
            'type': type_map.get(notif.notification_type, 'secondary'),
            'appointment_id': notif.appointment.id if notif.appointment else None,
            'is_read': False,
            'created_at': notif.created_at.isoformat(),
        })
    
    for notif in read_notifications:
        notifications.append({
            'id': notif.id,
            'icon': icon_map.get(notif.notification_type, 'fa-bell'),
            'text': notif.message,
            'type': type_map.get(notif.notification_type, 'secondary'),
            'appointment_id': notif.appointment.id if notif.appointment else None,
            'is_read': True,
            'created_at': notif.created_at.isoformat(),
        })
    
    return JsonResponse({
        'notifications': notifications,
        'count': len(unread_notifications)
    })


@login_required
def mark_notification_read(request, notification_id):
    from .models import Notification
    
    if request.method == 'POST':
        try:
            notification = Notification.objects.get(
                id=notification_id,
                user=request.user
            )
            notification.is_read = True
            notification.save()
            return JsonResponse({'success': True})
        except Notification.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Notification not found'}, status=404)
    
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)


@login_required
def mark_all_notifications_read(request):
    from .models import Notification
    
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
