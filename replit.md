# LINE Bot 排程管理系統

## Overview

This is a LINE Bot scheduling and user management system built with Flask. The application allows administrators to manage authorized LINE users, schedule automated messages, and manage weekly appointment bookings with automated reminder notifications. The system provides a web-based admin interface for user management, message scheduling, and appointment management, with background job processing to handle scheduled message delivery.

**Key Features:**
- Automatic user registration when users add the bot as a friend or send messages
- Silent message handling: Bot records user information without sending automatic replies
- **User name editing**: Click on any user's name to edit their display name
- Scheduled message delivery with automatic retry mechanism (up to 3 retries)
- **Weekly appointment booking system** with visual schedule management
- **Batch reminder sending** for appointments (whole week or single day)
- **Cross-page navigation**: Easy navigation between Admin, Schedule, and Appointments pages
- Web-based management interface for users, schedules, and appointments
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
- Time slots: Tue/Thu/Sat (14:00-18:00, 17 slots), Wed/Fri (18:00-21:00, 13 slots) in 15-minute intervals
- Minimized spacing for better visibility and compact display
- Dropdown selection from registered users for each time slot
- Send reminders for entire week or specific day with one click
- Responsive design: 5 columns on large screens, 3 on medium, 1 on mobile

### Backend Architecture

**Web Framework**: Flask serves as the lightweight web framework handling HTTP requests, routing, and template rendering.

**Authentication Strategy**: The system uses Replit's built-in authentication (`X-Replit-User-*` headers) to identify and authorize admin users accessing the web interface.

**Data Persistence**: JSON file-based storage is used for simplicity:
- `users.json`: Stores authorized LINE user IDs and names
- `schedules.json`: Stores scheduled message data including status, timestamps, and delivery information
- `appointments.json`: Stores weekly appointment bookings with date, time, user information

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

**Runtime Environment**:
- Environment variables for sensitive credentials (LINE_CHANNEL_TOKEN)
- Replit platform for hosting and deployment