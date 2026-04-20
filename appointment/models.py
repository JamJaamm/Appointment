# models.py (no changes needed; verification_code and expiry are in UserInfo)
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django_resized import ResizedImageField


class UserInfo(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profile_pics', blank=True, null=True)
    phone_number = models.CharField(max_length=20)
    dob = models.DateField(null=True, blank=True)
    location = models.CharField(max_length=500, null=True, blank=True)
    gender = models.CharField(max_length=500, null=True, blank=True)
    passport = ResizedImageField(size=[320,300], upload_to="passport/", null=True, blank=True)
    email_token_expiry = models.DateTimeField(blank=True, null=True)
    email_verified = models.BooleanField(default=False) 
    yearsOfExperience = models.PositiveIntegerField(null=True, blank=True)
    bloodgroup = models.CharField(max_length=10, blank=True, null=True)
    speciality = models.CharField(max_length=100, blank=True, null=True)
    bio = models.TextField(blank=True, null=True, help_text="Doctor's biography/biography")
    education = models.TextField(blank=True, null=True, help_text="Doctor's education background (one per line)")
    certifications = models.TextField(blank=True, null=True, help_text="Doctor's certifications (one per line)")


    class Meta:
        managed = True
        db_table = 'userinfo'

class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    speciality = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.speciality}"


class DoctorAvailability(models.Model):
    """Doctor's weekly availability schedule."""
    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='availabilities')
    day_of_week = models.CharField(max_length=10, choices=[
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday'),
    ])
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['day_of_week', 'start_time']
        unique_together = ['doctor', 'day_of_week', 'start_time', 'end_time']

    def __str__(self):
        return f"{self.doctor.get_full_name()} - {self.day_of_week} ({self.start_time}-{self.end_time})"


@receiver(post_save, sender=User)
def create_user_info(sender, instance, created, **kwargs):
    if created:
        UserInfo.objects.create(user=instance)


class Patient(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient')
    doctor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='patients')
    age = models.PositiveIntegerField(null=True, blank=True)
    # optional: profile picture
    avatar = models.URLField(blank=True, null=True)
    bloodgroup = models.CharField(max_length=10, blank=True, null=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username

class MedicalRecord(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='records')
    date = models.DateField()
    diagnosis = models.CharField(max_length=255)
    treatment = models.TextField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.patient} – {self.diagnosis} ({self.date})"
    

class Message(models.Model):
    SENDER_TYPES = (
        ('patient', 'Patient'),
        ('doctor', 'Doctor'),
    )

    sender_type = models.CharField(max_length=10, choices=SENDER_TYPES)
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    subject = models.CharField(max_length=200, blank=True)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    appointment = models.ForeignKey('zoom_appointment', on_delete=models.SET_NULL, null=True, blank=True, related_name='messages')
    parent_message = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')

    def __str__(self):
        return f"Message from {self.sender.get_full_name() or self.sender.username} to {self.recipient.get_full_name() or self.recipient.username}"

    class Meta:
        ordering = ['-timestamp']


class zoom_appointment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('reschedule_requested', 'Reschedule Requested'),
    ]

    ADMIN_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='doctor_appointments')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    date = models.DateTimeField(default=timezone.now)
    duration = models.PositiveIntegerField(default=30)  # in minutes
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending') # pending, approved, completed, cancelled, reschedule_requested
    admin_status = models.CharField(max_length=20, choices=ADMIN_STATUS_CHOICES, default='pending') # pending, approved, rejected - for admin approval
    reason = models.TextField(blank=True, null=True)
    reschedule_reason = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    original_appointment = models.OneToOneField('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='rescheduled_to')

    zoom_meeting_id = models.CharField(max_length=100, blank=True, null=True)
    zoom_join_url = models.URLField(blank=True, null=True)
    zoom_start_url = models.URLField(blank=True, null=True)
    meeting_details = models.TextField(blank=True, null=True, help_text="Meeting instructions/details posted by doctor")
    meeting_details_updated_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.patient.user.get_full_name()} with Dr. {self.doctor.last_name} on {self.date.strftime('%Y-%m-%d %H:%M')}"

    def get_status_display(self):
        # Return human-readable status
        status_dict = dict(self.STATUS_CHOICES)
        return status_dict.get(self.status, self.status)

    def get_admin_status_display(self):
        # Return human-readable admin status
        admin_status_dict = dict(self.ADMIN_STATUS_CHOICES)
        return admin_status_dict.get(self.admin_status, self.admin_status)


class Prescription(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]

    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='prescriptions')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='prescriptions')
    drug_name = models.CharField(max_length=200)
    dosage = models.CharField(max_length=100)
    frequency = models.CharField(max_length=100)
    duration = models.CharField(max_length=100)
    instructions = models.TextField(blank=True, help_text="Additional instructions for taking the medication")
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    appointment = models.ForeignKey(zoom_appointment, on_delete=models.SET_NULL, null=True, blank=True, related_name='prescriptions')

    def __str__(self):
        return f"{self.drug_name} - {self.patient.user.get_full_name()}"

    class Meta:
        ordering = ['-created_at']


class Reminder(models.Model):
    """Patient reminders for medications, appointments, or custom tasks."""
    REMINDER_TYPES = [
        ('medication', 'Medication'),
        ('appointment', 'Appointment'),
        ('task', 'Task'),
        ('checkup', 'Check-up'),
    ]

    FREQUENCY_CHOICES = [
        ('once', 'Once'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='reminders')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    reminder_type = models.CharField(max_length=20, choices=REMINDER_TYPES, default='task')
    date_time = models.DateTimeField()
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='once')
    location = models.CharField(max_length=300, blank=True)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    appointment = models.ForeignKey(zoom_appointment, on_delete=models.SET_NULL, null=True, blank=True, related_name='reminders')

    def __str__(self):
        return f"{self.title} - {self.patient.user.get_full_name()}"

    class Meta:
        ordering = ['date_time']


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('appointment_booked', 'Appointment Book'),
        ('appointment_approved', 'Appointment Approved'),
        ('appointment_declined', 'Appointment Declined'),
        ('appointment_cancelled', 'Appointment Cancelled'),
        ('appointment_completed', 'Appointment Completed'),
        ('appointment_reschedule_requested', 'Reschedule Requested'),
        ('message_received', 'New Message'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=32, choices=NOTIFICATION_TYPES)
    message = models.TextField()
    appointment = models.ForeignKey('zoom_appointment', on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.get_full_name() or self.user.username}: {self.message}"
