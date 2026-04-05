"""
Management command to add Zoom meetings to existing past appointments.
Run: python manage.py add_zoom_to_past_appointments
"""

from django.core.management.base import BaseCommand
from appointment.models import zoom_appointment
from appointment.zoom_utils import create_zoom_meeting
from django.utils import timezone


class Command(BaseCommand):
    help = 'Add Zoom meetings to past approved appointments without zoom_join_url'

    def handle(self, *args, **kwargs):
        self.stdout.write('Finding past appointments without Zoom links...')
        
        now = timezone.now()
        
        # Get all approved appointments in the past without zoom_join_url
        past_appointments = zoom_appointment.objects.filter(
            date__lt=now,
            status='approved',
        ).filter(
            zoom_join_url__isnull=True
        ) | zoom_appointment.objects.filter(
            date__lt=now,
            status='approved',
            zoom_join_url=''
        )
        
        self.stdout.write(f'Found {past_appointments.count()} appointments')
        
        created_count = 0
        failed_count = 0
        
        for appt in past_appointments:
            try:
                topic = f"Consultation - {appt.patient.user.get_full_name() or appt.patient.user.username}"
                start_time = appt.date
                duration = appt.duration or 30
                
                self.stdout.write(f'Creating Zoom meeting for appointment {appt.id}...')
                meeting = create_zoom_meeting(topic, start_time, duration=duration)
                
                if meeting:
                    appt.zoom_meeting_id = meeting.get('id', '')
                    appt.zoom_join_url = meeting.get('join_url', '')
                    appt.zoom_start_url = meeting.get('start_url', '')
                    appt.save()
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {appt.zoom_join_url}'))
                else:
                    failed_count += 1
                    self.stdout.write(self.style.ERROR('  ✗ Failed to create meeting'))
            except Exception as e:
                failed_count += 1
                self.stdout.write(self.style.ERROR(f'  ✗ Error: {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS(f'\nDone! Created: {created_count}, Failed: {failed_count}'))
