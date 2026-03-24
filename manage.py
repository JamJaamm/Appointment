#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import subprocess




# def main():
#     """Run administrative tasks."""
#     if "runserver" in sys.argv:
#         try:
#             subprocess.Popen(["mailpit"])
#             print("🚀 Mailpit started automatically!")
#         except FileNotFoundError:
#             print("⚠️ Mailpit not found. Please make sure it’s installed and in PATH.")
#     from django.core.management import execute_from_command_line
#     execute_from_command_line(sys.argv)

def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'doctors_appointment.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
