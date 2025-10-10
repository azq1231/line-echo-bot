# LINE Bot 排程管理系統

## Overview

This is a LINE Bot scheduling and user management system built with Flask. The application allows administrators to manage authorized LINE users and schedule automated messages to be sent to users at specific times. The system provides a web-based admin interface for user management and message scheduling, with background job processing to handle scheduled message delivery.

**Key Features:**
- Automatic user registration when users add the bot as a friend or send messages
- Scheduled message delivery with automatic retry mechanism (up to 3 retries)
- Web-based management interface for users and schedules
- Real-time status tracking (pending/sent/failed)
- Robust error handling with detailed logging

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture

**Web Interface Pattern**: The application uses server-side rendering with Flask templates to deliver HTML pages. The frontend consists of multiple views:

- **Admin Dashboard** (`templates/admin.html`): User management interface for adding/removing authorized LINE users
- **Schedule Management** (`templates/schedule.html`): Interface for creating and managing scheduled messages
- **Authentication Page** (`templates/index.html`): Replit authentication integration for admin access

**Styling Approach**: Custom CSS with gradient backgrounds and modern UI components. The design uses a purple gradient theme (`#667eea` to `#764ba2`) for visual consistency across all pages.

### Backend Architecture

**Web Framework**: Flask serves as the lightweight web framework handling HTTP requests, routing, and template rendering.

**Authentication Strategy**: The system uses Replit's built-in authentication (`X-Replit-User-*` headers) to identify and authorize admin users accessing the web interface.

**Data Persistence**: JSON file-based storage is used for simplicity:
- `users.json`: Stores authorized LINE user IDs and names
- `schedules.json`: Stores scheduled message data including status, timestamps, and delivery information

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