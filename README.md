# Distributed Campus Resource Sharing System

A beginner-friendly mini project based on the uploaded report. Built with Python Flask and SQLite. It demonstrates a client-server application, role-based access, shared file storage, search, audit logging, and a health endpoint.

## Requirements
- Python 3.10 or newer
- pip

## Run on Windows (VS Code terminal / PowerShell)
1. Extract the ZIP.
2. Open the extracted `Distributed_Campus_Resource_Sharing_System` folder in VS Code.
3. Create a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

4. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

5. Start the application:

   ```powershell
   python app.py
   ```

6. Open `http://127.0.0.1:5000` in your browser.

## Demo logins
- Student: `student` / `student123` (search and download)
- Staff: `staff` / `staff123` (search, download, upload)
- Admin: `admin` / `admin123` (all demo functions, including delete)

Change these demo passwords and the `SECRET_KEY` before any real deployment. This demo is for local academic use, not production use.

## Features
- Login with password hashing
- Roles: student, staff, admin
- Upload allowed document types (up to 15 MB)
- Search by title, category, or description
- Download available resources
- Admin delete function
- SQLite metadata database and separate upload folder
- Audit log records for key actions
- `/health` endpoint for basic service/database health

## Architecture mapping to the report
- Client: browser
- Application server: Flask
- Database service: SQLite database (`storage/campus_resources.db`)
- File storage: `storage/uploads/`
- Monitoring: `/health` plus `audit_logs` table

## Important project-report note
This is a working mini-project implementation of the report's core ideas. The database and application run on one computer in this version. Separate physical servers, load balancing, replication, distributed caching, and automatic failover are proposed future extensions, not implemented features.
