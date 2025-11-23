# Facial Recognition Attendance System

A Python-based facial recognition attendance system for college students using OpenCV and face_recognition library.

## Features

- **User Authentication**: Login and Register functionality
- **Student Management**: Register new students (Admin only)
- **Photo Capture**: Capture 50 photos per student for training
- **Face Recognition Training**: Train the model to recognize students
- **Attendance Marking**: Mark attendance IN/OUT using facial recognition
- **Attendance Reports**: View detailed attendance records (Admin only)

## Installation

1. **Install Python** (3.8 or higher)

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

   **Note**: On Windows, if you encounter issues installing `dlib`, you may need to:
   - Install Visual Studio Build Tools
   - Or use a pre-built wheel: `pip install dlib-binary`

3. **Run the application**:
   ```bash
   python attendance_system.py
   ```

## Default Login Credentials

- **Username**: `admin`
- **Password**: `admin123`

## Usage Guide

### 1. Login/Register
- Use the default admin credentials or register a new user
- Admin users have access to all features

### 2. Register New Student (Admin Only)
- Click "Register New Student" button
- Enter student username and password
- This creates a student account in the system

### 3. Add Photos (Admin Only)
- Click "Add Photo" button
- Enter the student username
- The camera will open
- Press **SPACE** to capture photos (50 photos recommended)
- Press **ESC** to finish

### 4. Training Dataset (Admin Only)
- After adding photos for students, click "Training Dataset"
- This will process all photos and create face encodings
- Wait for the training to complete

### 5. Mark Attendance
- Click "Attendance In" or "Attendance Out"
- The camera will open and recognize the student's face
- Attendance will be automatically marked
- Press **ESC** to cancel

### 6. View Attendance Report (Admin Only)
- Click "Attendance Report" button
- View all attendance records with dates, times, and status

## Database

The system uses SQLite database (`attendance.db`) to store:
- User accounts
- Student information
- Attendance records

## Directory Structure

```
.
├── attendance_system.py    # Main application file
├── requirements.txt        # Python dependencies
├── attendance.db          # SQLite database (created automatically)
├── photos/                # Student photos directory
│   └── [username]/        # Individual student photos
├── encodings/             # Face encodings (if needed)
└── trained_models/        # Trained face recognition model
    └── face_encodings.pkl
```

## Requirements

- Python 3.8+
- Webcam/Camera
- Windows/Linux/macOS

## Troubleshooting

1. **Camera not opening**: Make sure no other application is using the camera
2. **Face not recognized**: 
   - Ensure good lighting
   - Make sure student photos are clear
   - Retrain the dataset
3. **Installation issues**: 
   - For dlib on Windows, consider using conda: `conda install -c conda-forge dlib`
   - Or use pre-built wheels

## Notes

- The system requires at least 50 photos per student for better accuracy
- Ensure good lighting conditions when capturing photos and marking attendance
- The face recognition model needs to be trained after adding new student photos

