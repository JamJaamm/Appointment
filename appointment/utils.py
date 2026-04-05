from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

def send_verification_email(request, user, expiry_minutes: int = 30):
    try:
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        verification_link = f"{request.scheme}://{request.get_host()}/verify-email/{uid}/{token}/"

        # Save expiry time
        user.userinfo.email_token_expiry = timezone.now() + timedelta(minutes=expiry_minutes)
        user.userinfo.save()

        subject = "Verify your email address"
        context = {
            "user": user,
            "verification_link": verification_link,
            "expiry_minutes": expiry_minutes,
        }

        # Render HTML from template
        html_content = render_to_string("emails/verify_emails.html", context)
        text_content = strip_tags(html_content)  # Fallback text version

        # Build the email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email="noreply@yourapp.com",
            to=[user.email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        
        logger.info(f"Verification email sent to {user.email}")

    except Exception as e:
        logger.error(f"Failed to send verification email: {e}")
        raise


def send_welcome_email(user, is_doctor: bool = False):
    """
    Send a welcome email to a newly registered user.
    
    Args:
        user: The User instance
        is_doctor: Boolean indicating if the user is a doctor
    """
    try:
        # Determine the appropriate template and dashboard URL
        if is_doctor:
            template_name = "emails/welcome_doctor.html"
            dashboard_url = "/doctors-dashboard/"
        else:
            template_name = "emails/welcome_patient.html"
            dashboard_url = "/user-dashboard/"

        subject = "Welcome to MediCare!"
        context = {
            "user": user,
            "dashboard_url": dashboard_url,
            "now": timezone.now(),
        }

        # Render HTML from template
        html_content = render_to_string(template_name, context)
        text_content = strip_tags(html_content)  # Fallback text version

        # Build the email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email="noreply@doctors-appointment.com",
            to=[user.email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send()

        logger.info(f"Welcome email sent to {user.email} (is_doctor={is_doctor})")

    except Exception as e:
        logger.error(f"Failed to send welcome email: {e}")
        raise