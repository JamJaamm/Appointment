# Doctors Appointment System - Complete Documentation

## 📋 Table of Contents

1. [Overview](#overview)
2. [Project Structure](#project-structure)
3. [Technology Stack](#technology-stack)
4. [Database Schema](#database-schema)
5. [User Roles & Authentication](#user-roles--authentication)
6. [Core Features](#core-features)
7. [API Endpoints & URL Routing](#api-endpoints--url-routing)
8. [Templates & Frontend](#templates--frontend)
9. [Email System](#email-system)
10. [Zoom Integration](#zoom-integration)
11. [Setup & Installation](#setup--installation)
12. [Configuration](#configuration)
13. [Development Guidelines](#development-guidelines)

---

## 🏥 Overview

The **Doctors Appointment System** is a comprehensive web application built with Django that facilitates appointment booking, management, and patient-doctor communication. The system supports three distinct user roles with role-based access control.

### Key Capabilities

- **Patient Portal**: Book appointments, view history, manage prescriptions, send reminders
- **Doctor Portal**: Manage appointments, view patient records, send prescriptions
- **Admin Portal**: Oversee all users, appointments, and system management
- **Video Consultations**: Integrated Zoom meeting creation
- **Email Notifications**: Automated verification, reminders, and notifications
- **Messaging System**: Internal messaging between patients and doctors

---

## 📁 Project Structure

```
doctors-appointment/
├── doctors_appointment/          # Main Django project configuration
│   ├── __init__.py
│   ├── settings.py               # Django settings (DB, Email, Zoom API)
│   ├── urls.py                   # Main URL routing
│   ├── asgi.py                   # ASGI configuration
│   └── wsgi.py                   # WSGI configuration
│
├── appointment/                  # Main application module
│   ├── __init__.py
│   ├── models.py                 # Database models (7 models)
│   ├── views.py                  # View functions (80+ endpoints)
│   ├── urls.py                   # (Included in main urls.py)
│   ├── admin.py                  # Django admin configuration
│   ├── utils.py                  # Email utility functions
│   ├── zoom_utils.py             # Zoom API integration
│   ├── manager.py                # Custom model managers
│   ├── tests.py                  # Test cases
│   │
│   ├── templates/                # HTML templates (60 files)
│   │   ├── index.html            # Homepage
│   │   ├── register.html         # User registration
│   │   ├── login.html            # User login
│   │   ├── user_header_footer.html    # Patient layout
│   │   ├── doctor_header_footer.html  # Doctor layout
│   │   ├── admin_header_footer.html   # Admin layout
│   │   ├── user_dashboard.html   # Patient dashboard
│   │   ├── doctors_dashboard.html# Doctor dashboard
│   │   ├── admin_dashboard.html  # Admin dashboard
│   │   ├── book_appointment.html # Booking form
│   │   ├── prescriptions.html    # Prescriptions management
│   │   ├── reminders.html        # Reminders management
│   │   └── ... (48 more templates)
│   │
│   ├── static/                   # Static assets
│   │   ├── css/
│   │   │   └── index.css         # Main stylesheet
│   │   ├── cdn/                  # CDN libraries (Bootstrap, jQuery, FontAwesome)
│   │   ├── aos/                  # Animation on scroll library
│   │   └── images/               # Image assets
│   │
│   └── migrations/               # Database migrations (25 migrations)
│
├── media/                        # User-uploaded files (profile pics, passports)
├── manage.py                     # Django management script
├── requirements.txt              # Python dependencies (21 packages)
├── SETUP_GUIDE.md               # Setup instructions
├── repro_counts.py              # Data reproduction utility
└── verify_fix.py                # Verification script
```

---

## 🛠 Technology Stack

### Backend
- **Framework**: Django 4.2.27
- **Language**: Python 3.x
- **Database**: MySQL 8.0 (via mysql-connector-python 9.5.0)
- **Authentication**: Django Auth System with email verification

### Frontend
- **CSS Framework**: Bootstrap 5.3.0
- **Icons**: FontAwesome 6.4.0, Bootstrap Icons 1.11.0
- **JavaScript**: jQuery 3.1.1, jQuery UI
- **Fonts**: Fraunces (headings), Inter (body)
- **Animations**: Animate.css 4.1.1, AOS (Animate On Scroll)

### External Integrations
- **Video Conferencing**: Zoom API (Server-to-Server OAuth)
- **Email**: SMTP via Mailpit (development) / Production SMTP
- **Image Processing**: django-resized, Pillow 12.0.0

### Development Tools
- **Form Handling**: django-crispy-forms 2.5, crispy-bootstrap5 2025.6
- **Environment**: python-decouple 3.8
- **HTTP Client**: requests 2.32.5

---

## 🗄 Database Schema

### Core Models

#### 1. **User** (Django Built-in)
```python
# Django's default User model
- username
- first_name
- last_name
- email
- password (hashed)
- is_staff
- is_superuser
- is_active
```

#### 2. **UserInfo** (Profile Extension)
```python
class UserInfo:
    user: OneToOneField(User)
    profile_picture: ImageField (resized to 320x300)
    phone_number: CharField (max 20)
    dob: DateField (nullable)
    location: CharField (max 500, nullable)
    gender: CharField (max 500, nullable)
    passport: ResizedImageField (320x300, nullable)
    email_token_expiry: DateTimeField (nullable)
    email_verified: BooleanField (default=False)
    yearsOfExperience: PositiveIntegerField (nullable)
    bloodgroup: CharField (max 10, nullable)
    speciality: CharField (max 100, nullable)
```

#### 3. **Doctor**
```python
class Doctor:
    user: OneToOneField(User)
    speciality: CharField (max 100)
```

#### 4. **Patient**
```python
class Patient:
    user: OneToOneField(User, related_name='patient')
    doctor: ForeignKey(User, nullable)
    age: PositiveIntegerField (nullable)
    avatar: URLField (nullable)
    bloodgroup: CharField (max 10, nullable)
```

#### 5. **zoom_appointment** (Core Appointment Model)
```python
class zoom_appointment:
    STATUS_CHOICES = ['pending', 'approved', 'completed', 'cancelled', 'reschedule_requested']
    ADMIN_STATUS_CHOICES = ['pending', 'approved', 'rejected']
    
    doctor: ForeignKey(User, related_name='doctor_appointments')
    patient: ForeignKey(Patient, related_name='appointments')
    date: DateTimeField
    duration: PositiveIntegerField (default=30 minutes)
    status: CharField (choices=STATUS_CHOICES, default='pending')
    admin_status: CharField (choices=ADMIN_STATUS_CHOICES, default='pending')
    reason: TextField (nullable)
    reschedule_reason: TextField (nullable)
    notes: TextField (nullable)
    original_appointment: OneToOneField('self', nullable, related_name='rescheduled_to')
    
    # Zoom Integration
    zoom_meeting_id: CharField (max 100, nullable)
    zoom_join_url: URLField (nullable)
    zoom_start_url: URLField (nullable)
    
    created_at: DateTimeField (auto)
```

#### 6. **Message** (Internal Messaging)
```python
class Message:
    SENDER_TYPES = ['patient', 'doctor']
    
    sender_type: CharField (choices=SENDER_TYPES)
    sender: ForeignKey(User, related_name='sent_messages')
    recipient: ForeignKey(User, related_name='received_messages')
    subject: CharField (max 200, blank)
    message: TextField
    timestamp: DateTimeField (auto)
    is_read: BooleanField (default=False)
    appointment: ForeignKey(zoom_appointment, nullable, related_name='messages')
    parent_message: ForeignKey('self', nullable, related_name='replies')
```

#### 7. **Prescription**
```python
class Prescription:
    STATUS_CHOICES = ['active', 'completed', 'expired', 'cancelled']
    
    doctor: ForeignKey(User, related_name='prescriptions')
    patient: ForeignKey(Patient, related_name='prescriptions')
    drug_name: CharField (max 200)
    dosage: CharField (max 100)
    frequency: CharField (max 100)
    duration: CharField (max 100)
    instructions: TextField (blank)
    notes: TextField (blank)
    status: CharField (choices=STATUS_CHOICES, default='active')
    created_at: DateTimeField (auto)
    start_date: DateField (default=now)
    end_date: DateField (nullable)
    appointment: ForeignKey(zoom_appointment, nullable, related_name='prescriptions')
```

#### 8. **Reminder**
```python
class Reminder:
    REMINDER_TYPES = ['medication', 'appointment', 'task', 'checkup']
    FREQUENCY_CHOICES = ['once', 'daily', 'weekly', 'monthly']
    
    patient: ForeignKey(Patient, related_name='reminders')
    title: CharField (max 200)
    description: TextField (blank)
    reminder_type: CharField (choices=REMINDER_TYPES, default='task')
    date_time: DateTimeField
    frequency: CharField (choices=FREQUENCY_CHOICES, default='once')
    location: CharField (max 300, blank)
    is_completed: BooleanField (default=False)
    created_at: DateTimeField (auto)
    appointment: ForeignKey(zoom_appointment, nullable, related_name='reminders')
```

#### 9. **MedicalRecord**
```python
class MedicalRecord:
    patient: ForeignKey(Patient, related_name='records')
    date: DateField
    diagnosis: CharField (max 255)
    treatment: TextField
    notes: TextField (blank)
```

### Entity Relationship Diagram

```
User (1) ──┬── (1) UserInfo
           ├── (1) Doctor
           ├── (1) Patient ── (M) MedicalRecord
           │                      ├── (M) Prescription
           │                      ├── (M) Reminder
           │                      └── (M) zoom_appointment
           │
           ├── (M) Message (sent/received)
           └── (M) zoom_appointment (as doctor)
                    │
                    ├── (M) Message
                    ├── (M) Prescription
                    └── (M) Reminder
```

---

## 👥 User Roles & Authentication

### Role Types

#### 1. **Patient (Regular User)**
- `is_staff = False`, `is_superuser = False`
- **Dashboard**: `/user_dashboard`
- **Capabilities**:
  - Book appointments with doctors
  - View appointment history
  - Manage prescriptions
  - Create reminders
  - Send messages to doctors
  - Join Zoom meetings

#### 2. **Doctor (Staff User)**
- `is_staff = True`, `is_superuser = False`
- **Dashboard**: `/doctors_dashboard`
- **Capabilities**:
  - View/manage appointments
  - Approve/decline appointment requests
  - View patient lists and records
  - Create prescriptions
  - Send reminders to patients
  - Host Zoom meetings
  - Manage profile and speciality

#### 3. **Admin (Superuser)**
- `is_staff = True`, `is_superuser = True`
- **Dashboard**: `/admin_dashboard`
- **Capabilities**:
  - View all doctors, patients, appointments
  - Approve/reject appointments
  - Block/unblock users
  - Delete user accounts
  - System-wide oversight

### Authentication Flow

#### Registration Process
```
1. User fills registration form (register.html)
2. System validates:
   - All fields filled
   - Valid email format
   - Password confirmation matches
   - Email not already registered
3. User account created with:
   - Random username: {lastName}-{randomNumber}
   - is_active = False (pending verification)
   - email_verified = False
4. Verification email sent with token
5. User clicks verification link
6. Account activated (is_active = True, email_verified = True)
7. Redirect to login
```

#### Login Process
```
1. User enters email and password
2. System retrieves user by email
3. Authenticates with username/password
4. Checks email_verified status
5. Redirects based on role:
   - Admin → /admin_dashboard
   - Doctor → /doctors_dashboard
   - Patient → /user_dashboard
```

#### Email Verification
- **Token Generator**: Django's `default_token_generator`
- **UID Encoding**: `urlsafe_base64_encode`
- **Expiry**: 30 minutes (configurable)
- **URL Format**: `/verify-email/{uidb64}/{token}/`

---

## ⚙️ Core Features

### 1. Appointment Management

#### Patient Workflow
```
1. Browse doctors (homepage or /doctors)
2. Click "Book Appointment"
3. Select doctor, date, time, duration
4. Enter reason for visit
5. Submit → Status: "pending"
6. Wait for doctor approval
7. Receive notification when approved
8. Join Zoom meeting at scheduled time
```

#### Doctor Workflow
```
1. View pending appointments on dashboard
2. Review patient details and reason
3. Approve or decline request
4. If approved:
   - Zoom meeting created automatically
   - Patient notified via email
5. After consultation:
   - Mark appointment as "completed"
   - Create prescription if needed
```

#### Admin Oversight
```
1. View all appointments system-wide
2. Approve/reject appointments (admin_status)
3. Edit appointment details
4. Monitor appointment statistics
```

### 2. Zoom Video Integration

#### Meeting Creation Flow
```python
# Automatic when appointment is approved
1. Doctor approves appointment
2. System calls create_zoom_meeting()
3. Attempts real Zoom API first
4. Falls back to mock meeting if API fails
5. Stores meeting URLs in database:
   - zoom_join_url (for patient)
   - zoom_start_url (for doctor)
   - zoom_meeting_id
```

#### Mock Meeting System
- **Purpose**: Development/testing without valid Zoom credentials
- **Generates**:
  - UUID-based meeting ID
  - Mock join/start URLs
  - Realistic meeting data structure
- **Flag**: `mock: True` in meeting data

### 3. Messaging System

#### Features
- **Internal Messaging**: Send messages between patients and doctors
- **Threaded Replies**: parent_message ForeignKey for threading
- **Appointment Context**: Messages linked to specific appointments
- **Read Status**: is_read flag with read/unread indicators
- **Email Notifications**: Optional email copy sent

#### Usage
```python
# Send message
Message.objects.create(
    sender_type='patient',
    sender=request.user,
    recipient=doctor,
    subject='Follow-up Question',
    message='Question content...',
    appointment=appointment  # Optional context
)
```

### 4. Prescription Management

#### Doctor Creates Prescription
```
1. Navigate to completed appointment
2. Click "Create Prescription"
3. Enter:
   - Drug name
   - Dosage
   - Frequency (e.g., "Twice daily")
   - Duration (e.g., "7 days")
   - Instructions
4. Submit → Patient notified
```

#### Patient Views Prescriptions
- Active prescriptions dashboard
- Filter by status (active, completed, expired)
- View dosage instructions
- Track prescription history

### 5. Reminder System

#### Patient Reminders
- **Types**: Medication, Appointment, Task, Check-up
- **Frequency**: Once, Daily, Weekly, Monthly
- **Features**:
  - Set date/time
  - Add location
  - Mark as completed
  - Link to appointments

#### Doctor Reminders
- Send appointment reminders to patients
- Automated email notifications
- Custom messages with appointment details

---

## 🔗 API Endpoints & URL Routing

### Public Routes (No Authentication Required)

| URL | View | Template | Description |
|-----|------|----------|-------------|
| `/` | homepage | index.html | Homepage with hero, doctors, services |
| `/services` | servicespage | services.html | Services offered |
| `/doctors` | doctorspage | doctors.html | List of all doctors |
| `/about` | aboutpage | about.html | About page |
| `/contact` | contactpage | contact.html | Contact form |
| `/register` | registerpage | register.html | User registration |
| `/login` | loginpage | login.html | User login |
| `/verify-email/<uidb64>/<token>/` | verify_email_view | - | Email verification |
| `/resend-verification/` | resend_verification | - | Resend verification email |

### Patient Routes (Authentication Required)

| URL | View | Template | Description |
|-----|------|----------|-------------|
| `/user_dashboard` | user_dashboardpage | user_dashboard.html | Patient dashboard |
| `/user_profile` | user_profilepage | user_profile.html | Patient profile |
| `/edit_userprofilepage` | edit_userprofilepage | edit_userprofile.html | Edit profile |
| `/book_appointment` | doctorbook_appointment | book_appointment.html | Book appointment |
| `/initiate_booking` | initiate_booking | - | Start booking flow |
| `/appoinment_history` | appoinment_historypage | appoinment_history.html | Appointment history |
| `/user_message` | user_messagepage | user_message.html | Patient messages |
| `/user_reminders` | user_reminderspage | user_reminders.html | Patient reminders |
| `/prescriptions` | prescriptions_page | user_prescriptions.html | View prescriptions |
| `/meeting` | meetingpage | meeting.html | Join meeting |
| `/patient_appointments` | patient_appointments | patient_appointments.html | Manage appointments |
| `/reschedule_appointment/<id>/` | reschedule_appointment | reschedule_appointment.html | Reschedule |
| `/cancel_appointment/<id>/` | cancel_appointment | confirm_cancel_appointment.html | Cancel |
| `/send-reminder-to-doctor/` | send_reminder_to_doctor | - | Send reminder |

### Doctor Routes (Staff Authentication Required)

| URL | View | Template | Description |
|-----|------|----------|-------------|
| `/doctors_dashboard` | doctors_dashboardpage | doctors_dashboard.html | Doctor dashboard |
| `/doctors_profile` | doctors_profilepage | doctors_profile.html | Doctor profile |
| `/doctor_editprofile` | doctor_editprofilepage | doctor_editprofile.html | Edit profile |
| `/doctor_appointments` | doctor_appointments | doctor_appointments.html | Manage appointments |
| `/approve_appointment/<id>/` | approve_appointment | - | Approve appointment |
| `/decline_appointment/<id>/` | decline_appointment | - | Decline appointment |
| `/complete_appointment/<id>/` | complete_appointment | complete_appointment.html | Complete |
| `/request_reschedule/<id>/` | request_reschedule | request_reschedule.html | Request reschedule |
| `/doctors_patients` | doctors_patientspage | doctors_patients.html | Patient list |
| `/doctors_patients/<id>/detail/` | patient_detail | patient_detail.html | Patient details |
| `/doctors_message` | doctors_messagepage | doctors_message.html | Doctor messages |
| `/reminders` | reminderspage | reminders.html | Send reminders |
| `/prescriptions` | prescriptions_page | prescriptions.html | Manage prescriptions |
| `/prescriptions/create/` | create_prescription | - | Create prescription |
| `/prescriptions/<id>/update-status/` | update_prescription_status | - | Update status |
| `/prescriptions/<id>/delete/` | delete_prescription | - | Delete prescription |
| `/doctors_meeting` | doctors_meetingpage | doctors_meeting.html | Host meeting |
| `/doctors_appointment_history` | doctors_appointmenthistorypage | doctors_appointmenthistory.html | History |

### Admin Routes (Superuser Required)

| URL | View | Template | Description |
|-----|------|----------|-------------|
| `/admin_dashboard` | admin_dashboardpage | admin_dashboard.html | Admin dashboard |
| `/admin/doctors/` | admin_doctors_management | admin_doctors_list.html | Manage doctors |
| `/admin/patients/` | admin_patients_management | admin_patients_list.html | Manage patients |
| `/admin/appointments/` | admin_appointments | admin_appointments.html | All appointments |
| `/admin/appointments/<id>/edit/` | admin_edit_appointment | admin_edit_appointment.html | Edit appointment |
| `/admin/appointments/<id>/approve/` | admin_approve_appointment | - | Approve |
| `/admin/appointments/<id>/reject/` | admin_reject_appointment | admin_reject_appointment.html | Reject |
| `/admin/user/<id>/block/` | admin_block_user | - | Block user |
| `/admin/user/<id>/unblock/` | admin_unblock_user | - | Unblock user |
| `/admin/user/<id>/delete/` | admin_delete_user | - | Delete user |

### AJAX/API Endpoints

| URL | View | Method | Description |
|-----|------|--------|-------------|
| `/get_available_times/` | get_available_times | GET | Get doctor's available slots |
| `/send_reminder/` | send_reminder | POST | Send reminder email |
| `/api/patient-appointments/` | get_patient_appointments_api | GET | JSON API for appointments |
| `/api/appointment-notifications/` | get_appointment_notifications_api | GET | JSON notifications |
| `/mark_message_as_read/<id>/` | mark_message_as_read | POST | Mark message read |
| `/reminders/<id>/update/` | update_reminder | POST | Update reminder |
| `/reminders/<id>/delete/` | delete_reminder | POST | Delete reminder |
| `/reminders/<id>/toggle-complete/` | mark_reminder_completed | POST | Toggle complete |

### Authentication Routes

| URL | View | Description |
|-----|------|-------------|
| `/logout` | logoutpage | Logout user |
| `/reset_password` | reset_passwordpage | Forgot password |
| `/reset-password-confirm/<uidb64>/<token>/` | reset_password_confirm | Reset password |

---

## 🎨 Templates & Frontend

### Template Inheritance Structure

```
Base Layouts:
├── header_footer.html          # Public pages (index, about, services)
├── login_header.html           # Login/Register pages
├── user_header_footer.html     # Patient dashboard pages
├── doctor_header_footer.html   # Doctor dashboard pages
└── admin_header_footer.html    # Admin dashboard pages
```

### Key Template Features

#### Responsive Design
- **Desktop (>991px)**: Full sidebar navigation (260px)
- **Tablet (768-991px)**: Collapsed sidebar (70px, icons only)
- **Mobile (≤767px)**: Hidden sidebar with toggle button

#### Mobile Sidebar (Recently Added)
```html
<!-- Toggle Button -->
<button class="sidebar-toggle-btn" id="sidebarToggle">
    <i class="fas fa-bars"></i>
</button>

<!-- Overlay -->
<div class="sidebar-overlay" id="sidebarOverlay"></div>
```

**Features**:
- Hamburger menu icon (transforms to X when open)
- Dark overlay backdrop
- Auto-close on navigation click
- Auto-close on window resize
- Touch-friendly (44px tap target)

### CSS Architecture

#### CSS Variables (Theming)
```css
:root {
  /* Colors */
  --primary-blue: #0070a0;
  --primary-blue-dark: #00577c;
  --bg-primary: #ffffff;
  --text-primary: #1f1f1f;
  
  /* Typography */
  --font-heading: 'Fraunces', serif;
  --font-body: 'Inter', sans-serif;
  
  /* Shadows */
  --shadow-sm: 0 2px 8px rgba(0,0,0,0.04);
  --shadow-lg: 0 8px 20px rgba(0,0,0,0.08);
  
  /* Transitions */
  --transition-fast: 0.2s ease;
}

[data-theme="dark"] {
  /* Dark mode overrides */
}
```

#### Component Classes
- `.card`: Standard card with hover effects
- `.stat-card`: Statistics display cards
- `.appointment-card`: Appointment-specific styling
- `.quick-action-btn`: Quick action buttons
- `.notification-bell`: Notification icon
- `.sidebar`: Fixed navigation sidebar

### JavaScript Functionality

#### Sidebar Toggle (Mobile)
```javascript
document.addEventListener('DOMContentLoaded', function() {
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    const sidebar = document.querySelector('.sidebar');
    
    // Toggle sidebar
    sidebarToggle.addEventListener('click', function() {
        sidebar.classList.toggle('mobile-open');
        sidebarOverlay.classList.toggle('active');
        // Icon switch: bars ↔ times
    });
    
    // Close on overlay click
    sidebarOverlay.addEventListener('click', function() {
        sidebar.classList.remove('mobile-open');
    });
    
    // Close on nav link click (mobile)
    // Auto-close on resize
});
```

#### Dynamic Features
- **Loading Spinner**: Full-screen overlay during AJAX
- **Notification Dropdown**: Real-time appointment notifications
- **Form Validation**: Client-side validation
- **Date/Time Pickers**: jQuery UI datepicker
- **Available Times**: AJAX fetch based on selected date

---

## 📧 Email System

### Configuration

#### Development (Mailpit)
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = '127.0.0.1'
EMAIL_PORT = 1025
EMAIL_USE_TLS = False
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
DEFAULT_FROM_EMAIL = 'noreply@doctors-appointment.com'
```

#### Production (SMTP)
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'  # Or your provider
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your@email.com'
EMAIL_HOST_PASSWORD = 'your-password'
```

#### Console Backend (Debug)
```python
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
# Emails printed to terminal
```

### Email Templates

#### 1. Verification Email (`emails/verify_emails.html`)
```html
Subject: Verify your email address
Content:
- Welcome message
- Verification button/link
- Expiry notice (30 minutes)
- Support contact
```

#### 2. Appointment Confirmation
```html
Subject: Appointment Confirmed - Dr. {Name}
Content:
- Patient name
- Doctor name
- Date & time
- Zoom join link
- Instructions
```

#### 3. Reminder Emails
```html
Subject: Patient Reminder: {Subject}
Content:
- Patient name
- Appointment details
- Custom message
- Reply instructions
```

### Email Functions

#### `send_verification_email(request, user, expiry_minutes=30)`
```python
# Located in: appointment/utils.py
- Generates token
- Creates verification link
- Saves expiry to UserInfo
- Sends HTML email
- Logs success/failure
```

#### Manual Email Sending
```python
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

html_content = render_to_string("template.html", context)
email = EmailMultiAlternatives(
    subject="Subject",
    body=text_content,
    from_email="noreply@doctors-appointment.com",
    to=["user@example.com"]
)
email.attach_alternative(html_content, "text/html")
email.send()
```

---

## 📹 Zoom Integration

### Configuration

```python
# settings.py
ZOOM_ACCOUNT_ID = "your_account_id"
ZOOM_CLIENT_ID = "your_client_id"
ZOOM_CLIENT_SECRET = "your_client_secret"
ZOOM_BASE_URL = "https://api.zoom.us/v2/"
```

### Meeting Creation Flow

#### `create_zoom_meeting(topic, start_time, duration=30)`
```python
# Located in: appointment/zoom_utils.py

1. Get access token (Server-to-Server OAuth)
2. POST to Zoom API: /users/me/meetings
3. If successful → Return real meeting data
4. If failed → Return mock meeting data
```

#### Access Token Generation
```python
def get_zoom_access_token():
    url = "https://zoom.us/oauth/token"
    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    params = {
        "grant_type": "account_credentials",
        "account_id": ACCOUNT_ID
    }
    
    response = requests.post(url, headers=headers, params=params)
    return response.json().get("access_token")
```

### Mock Meeting System

**When Zoom API Fails**:
```python
mock_meeting = {
    "id": str(uuid.uuid4())[:11],
    "topic": topic,
    "start_time": start_time.isoformat(),
    "duration": duration,
    "join_url": f"https://zoom.us/j/{meeting_id}?pwd={uuid}",
    "start_url": f"https://zoom.us/s/{meeting_id}?pwd={uuid}",
    "mock": True
}
```

**Benefits**:
- Development without valid credentials
- Testing appointment workflow
- No API rate limits
- Predictable behavior

### Meeting URLs in Database

```python
# zoom_appointment model
appointment.zoom_join_url    # Patient uses this
appointment.zoom_start_url   # Doctor uses this
appointment.zoom_meeting_id  # Reference ID
```

---

## 🚀 Setup & Installation

### Prerequisites

- **Python**: 3.8 or higher
- **MySQL**: 8.0 or higher
- **pip**: Python package manager
- **Git**: Version control

### Step-by-Step Installation

#### 1. Clone Repository
```bash
git clone <repository-url>
cd doctors-appointment
```

#### 2. Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

#### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 4. Configure MySQL Database
```sql
CREATE DATABASE appointment CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'doctor_user'@'localhost' IDENTIFIED BY 'secure_password';
GRANT ALL PRIVILEGES ON appointment.* TO 'doctor_user'@'localhost';
FLUSH PRIVILEGES;
```

#### 5. Update settings.py
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'appointment',
        'HOST': 'localhost',
        'USER': 'root',
        'PASSWORD': '',  # Your MySQL password
        'PORT': '3306',
    }
}

SECRET_KEY = 'your-secret-key-here'
DEBUG = False  # True for development
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'yourdomain.com']
```

#### 6. Run Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

#### 7. Create Superuser (Admin)
```bash
python manage.py createsuperuser
# Email: admin@doctors-appointment.com
# Password: ********
```

#### 8. Create Sample Doctors
```bash
python manage.py shell
>>> from django.contrib.auth.models import User
>>> from appointment.models import Doctor, UserInfo
>>> 
>>> # Create doctor user
>>> user = User.objects.create_user(
...     username='dr-smith',
...     email='dr.smith@hospital.com',
...     password='password123',
...     first_name='John',
...     last_name='Smith',
...     is_staff=True
... )
>>> 
>>> # Create doctor profile
>>> Doctor.objects.create(user=user, speciality='Cardiology')
>>> 
>>> # Update UserInfo
>>> userinfo = UserInfo.objects.get(user=user)
>>> userinfo.phone_number = '+1234567890'
>>> userinfo.email_verified = True
>>> userinfo.save()
>>> 
>>> # Activate user
>>> user.is_active = True
>>> user.save()
```

#### 9. Configure Email (Mailpit)

**Download Mailpit**:
```bash
# Visit: https://github.com/axllent/mailpit/releases
# Download for your OS
# Extract and run
./mailpit
```

**Access Mailpit**:
- Web Interface: http://localhost:8025
- SMTP Server: 127.0.0.1:1025

#### 10. Run Development Server
```bash
python manage.py runserver
```

**Access Application**:
- Homepage: http://localhost:8000/
- Admin Panel: http://localhost:8000/admin/
- Register: http://localhost:8000/register/

---

## ⚙️ Configuration

### Environment Variables (Recommended)

Create `.env` file:
```env
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_NAME=appointment
DB_USER=root
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=3306

# Email
EMAIL_HOST=127.0.0.1
EMAIL_PORT=1025
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=noreply@doctors-appointment.com

# Zoom API
ZOOM_ACCOUNT_ID=your_account_id
ZOOM_CLIENT_ID=your_client_id
ZOOM_CLIENT_SECRET=your_client_secret
```

**Load in settings.py**:
```python
from decouple import config

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=True, cast=bool)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT'),
    }
}
```

### Media Files Configuration

```python
# settings.py
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# urls.py (development)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

**Upload Directories**:
```
media/
├── profile_pics/      # User profile pictures
└── passport/          # Passport photos (resized)
```

---

## 📝 Development Guidelines

### Code Style

#### Python (PEP 8)
```python
# Function naming
def user_dashboardpage(request):
    """Docstring describing function."""
    pass

# Model naming
class zoom_appointment(models.Model):
    """Appointment model with Zoom integration."""
    pass

# Imports order
from django.shortcuts import render, redirect  # Django first
import requests  # Third-party
from .models import Patient  # Local imports
```

#### Template Conventions
```django
{% load static %}
{% load humanize %}

{% extends "base.html" %}

{% block title %}Page Title{% endblock title %}

{% block content %}
    <!-- Content here -->
{% endblock content %}
```

### Testing

#### Run Tests
```bash
python manage.py test appointment
```

#### Example Test Case
```python
from django.test import TestCase
from django.contrib.auth.models import User
from appointment.models import Patient, zoom_appointment

class AppointmentTest(TestCase):
    def test_appointment_creation(self):
        patient = Patient.objects.create(user=user)
        appointment = zoom_appointment.objects.create(
            doctor=doctor,
            patient=patient,
            reason="Checkup"
        )
        self.assertEqual(appointment.status, 'pending')
```

### Security Best Practices

#### 1. Password Security
```python
# Always use Django's password hashing
from django.contrib.auth.hashers import make_password
hashed = make_password('plain_password')
```

#### 2. CSRF Protection
```django
<!-- In all forms -->
<form method="POST">
    {% csrf_token %}
    <!-- Form fields -->
</form>
```

#### 3. Login Required
```python
from django.contrib.auth.decorators import login_required

@login_required
def user_dashboardpage(request):
    pass
```

#### 4. Input Validation
```python
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

try:
    validate_email(email)
except ValidationError:
    # Handle invalid email
    pass
```

### Performance Optimization

#### 1. Database Queries
```python
# Use select_related for ForeignKey
appointments = zoom_appointment.objects.select_related(
    'doctor', 'patient', 'patient__user'
).all()

# Use prefetch_related for ManyToMany
doctors = User.objects.prefetch_related('doctor_appointments').all()
```

#### 2. Template Caching
```django
{% load cache %}

{% cache 500 sidebar request.user.id %}
    <!-- Sidebar content -->
{% endcache %}
```

#### 3. Static Files
```python
# settings.py
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'
```

### Debugging Tools

#### Django Debug Toolbar
```bash
pip install django-debug-toolbar
```

```python
# settings.py
INSTALLED_APPS += ['debug_toolbar']
MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
```

#### Logging
```python
# settings.py
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'appointment': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

---

## 📊 System Status & Monitoring

### Current Database State

**Users**:
- Total Users: 7
- Superuser (Admin): 1
- Doctors: 2
- Patients: 4

**Appointments**:
- Total Appointments: 1 (test data)
- Status Distribution: Trackable via dashboard

### Health Checks

#### Database Connection
```bash
python manage.py dbshell
# Should open MySQL shell if connected
```

#### Email System
```bash
# Send test email
python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test', 'Body', 'from@example.com', ['to@example.com'])
```

#### Zoom Integration
```bash
python manage.py shell
>>> from appointment.zoom_utils import create_zoom_meeting
>>> from datetime import datetime
>>> meeting = create_zoom_meeting('Test', datetime.now())
>>> print(meeting)
```

---

## 🎯 Future Enhancements

### Planned Features
1. **Real-time Notifications**: WebSocket integration
2. **Payment Gateway**: Paystack integration for consultation fees
3. **Calendar Sync**: Google Calendar, Outlook integration
4. **SMS Notifications**: Twilio integration
5. **Multi-language Support**: i18n implementation
6. **Mobile App**: React Native/Flutter app
7. **Telemedicine Features**: File sharing, screen sharing
8. **Analytics Dashboard**: Advanced reporting for admins

### Performance Improvements
1. **Redis Caching**: Session and query caching
2. **CDN Integration**: Static file delivery
3. **Database Optimization**: Indexing, query optimization
4. **Load Balancing**: Multi-server deployment

---

## 📞 Support & Contact

### Documentation Resources
- **Django Docs**: https://docs.djangoproject.com/
- **Bootstrap Docs**: https://getbootstrap.com/docs/
- **Zoom API**: https://marketplace.zoom.us/docs/

### Project Contacts
- **Primary Developer**: [Your Contact]
- **Email**: [Your Email]
- **Issue Tracker**: [GitHub Issues]

---

## 📄 License

[Add your license information here]

---

**Last Updated**: March 18, 2026  
**Version**: 1.0.0  
**Django Version**: 4.2.27  
**Python Version**: 3.x
