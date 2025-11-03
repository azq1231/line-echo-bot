# LINE Bot 排程管理系統

## Overview

This is a LINE Bot scheduling and user management system built with Flask and SQLite. The application allows administrators to manage authorized LINE users, schedule automated messages, and manage weekly appointment bookings with automated reminder notifications. Users can book appointments directly through LINE using interactive Flex Messages. The system integrates Gemini AI for intelligent scheduling suggestions and provides a web-based admin interface for comprehensive management.

**Key Features:**
- Automatic user registration when users add the bot as a friend or send messages
- Silent message handling: Bot records user information without sending automatic replies
- **User name editing**: Click on any user's name to edit their display name
- Scheduled message delivery with automatic retry mechanism (up to 3 retries)
- **Weekly appointment booking system** with visual schedule management
- **LINE interactive booking**: Users can book appointments directly through LINE Flex Messages
- **Configurable booking window**: Set 2 weeks or 1 month (4 weeks) advance booking period
- **Smart time filtering**: Automatically hide past time slots in LINE booking flow
- **Week navigation**: Browse and manage appointments across multiple weeks
- **Closed day management**: Set clinic closures with automatic appointment cancellation
- **Batch reminder sending**: Send appointment reminders for whole week or single day
- **Cross-page navigation**: Easy navigation between Admin, Schedule, Appointments, and Closed Days pages
- **Secure webhook**: LINE signature verification with HMAC-SHA256
- Web-based management interface for users, schedules, appointments, and closed days
- Real-time status tracking (pending/sent/failed)
- Robust error handling with detailed logging
- Timezone-aware scheduling (Asia/Taipei UTC+8)

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture

**Web Interface Pattern**: The application uses server-side rendering with Flask templates to deliver HTML pages. The frontend consists of multiple views:

- **Admin Dashboard** (`templates/admin.html`): User management interface for adding/removing authorized LINE users, with inline name editing capability
- **Schedule Management** (`templates/schedule.html`): Interface for creating and managing scheduled messages
- **Appointment Management** (`templates/appointments.html`): Weekly appointment booking interface with time slot selection

**User Name Editing**: Uses event delegation pattern with `data-*` attributes to safely handle user name editing. Click events are captured on the user list container and delegated to individual editable name elements, avoiding issues with special characters in onclick attributes.

**Styling Approach**: Custom CSS with gradient backgrounds and modern UI components. The design uses a purple gradient theme (`#667eea` to `#764ba2`) for visual consistency across all pages. Fully responsive design with mobile-optimized layouts (media queries for screens ≤768px).

**Appointment System Design**:
- Compact grid layout showing all 5 days (Tue-Sat) in one row on large screens
- Time slots: 
  - Tue/Thu: 14:00-18:00 (17 slots)
  - Sat: 10:00-18:00 (33 slots) 
  - Wed/Fri: 18:00-21:00 (13 slots)
  - All in 15-minute intervals
- Minimized spacing for better visibility and compact display
- Dropdown selection from registered users for each time slot
- Send reminders for entire week or specific day with one click
- Responsive design: 5 columns on large screens, 3 on medium, 1 on mobile

### Backend Architecture

**Web Framework**: Flask serves as the lightweight web framework handling HTTP requests, routing, and template rendering.

**Authentication Strategy**: The system uses Replit's built-in authentication (`X-Replit-User-*` headers) to identify and authorize admin users accessing the web interface.

**Data Persistence**: SQLite database for robust data management:
- `appointments.db`: Main SQLite database file
- Tables: users, appointments, closed_days, schedules, notification_templates
- Partial unique index on appointments for rebooking cancelled slots
- Support for multi-slot bookings via booking_group_id

**Background Processing**: APScheduler (BackgroundScheduler) runs scheduled jobs to check for pending messages and deliver them at the specified times.

### External Dependencies

**LINE Messaging API**: 
- Primary integration for sending messages to LINE users
- Requires `LINE_CHANNEL_TOKEN` environment variable
- Used for push message delivery to scheduled recipients

**Replit Authentication**:
- Used for admin interface access control
- Integrates via JavaScript library (`repl-auth-v2.js`)
- Provides user identification through request headers

**Python Libraries**:
- `Flask`: Web framework and routing
- `APScheduler`: Background job scheduling
- `requests`: HTTP client for LINE API calls
- `uuid`: Unique identifier generation for schedules

**Data Storage**:
- File system (JSON files) for user and schedule persistence
- No database required - uses simple JSON serialization

**Gemini AI Integration**:
- `gemini_ai.py`: AI-powered appointment scheduling suggestions
- Uses Gemini 2.5 Flash model with JSON output mode
- Analyzes booking patterns and suggests optimal time slots
- Requires `GEMINI_API_KEY` environment variable

**Security**:
- LINE webhook signature verification (HMAC-SHA256)
- Requires `LINE_CHANNEL_SECRET` for webhook security
- Environment-based secret management

**Runtime Environment**:
- Environment variables for sensitive credentials:
  - `LINE_CHANNEL_TOKEN`: LINE Messaging API access token
  - `LINE_CHANNEL_SECRET`: LINE webhook signature verification secret
  - `GEMINI_API_KEY`: Gemini AI API key
- Replit platform for hosting and deployment

## Recent Changes

**2025-10-10: Bug Fixes & Feature Enhancements**
- 🐛 Fixed backend appointments page showing "undefined" for dates
- 🐛 Fixed closed days showing "取消true個預約" text formatting issue
- ⏰ Changed Saturday hours to 10:00-18:00 (was 14:00-18:00)
- 🔍 Added automatic filtering of past time slots in LINE booking flow
- ⚙️ Added configurable booking window (2 weeks or 1 month) in system settings
- 📚 Created comprehensive LINE Rich Menu setup tutorial
- 📚 Created detailed deployment guide for Heroku, PythonAnywhere, AWS/VPS
- ✅ Added config validation to ensure only 2 or 4 weeks can be set

**2025-10-10: Complete System Upgrade**
- ✅ Migrated from JSON to SQLite database
- ✅ Integrated Gemini AI for scheduling suggestions
- ✅ Created LINE Flex Message templates for date/time selection
- ✅ Fixed partial unique index to allow rebooking cancelled slots
- ✅ Added support for multi-slot bookings via booking_group_id
- ✅ Implemented LINE webhook with HMAC-SHA256 signature verification
- ✅ Added complete booking flow: query, book, cancel appointments
- ✅ Created admin interfaces: users, schedules, appointments, closed days
- ✅ Implemented week navigation for appointment management
- ✅ Added closed day management with automatic appointment cancellation
- ✅ Cleaned up legacy JSON files (backed up to json_backup/)

## Project Architecture

### Core Modules

**database.py**: SQLite database layer
- User management (add, update, delete)
- Appointment CRUD operations
- Closed day management with auto-cancellation
- Notification template storage
- Partial unique indexing for slot rebooking

**gemini_ai.py**: AI-powered scheduling assistant
- Analyzes appointment patterns and gaps
- Suggests optimal time slots for users
- JSON-structured output for easy integration

**line_flex_messages.py**: Interactive LINE UI templates
- Date selection card with week navigation
- Time slot selection with availability display
- Booking confirmation card
- Closed day notification card