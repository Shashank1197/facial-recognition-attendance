import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import cv2
import numpy as np
import os
import sqlite3
import face_recognition
from datetime import datetime
import pickle
import shutil

class AttendanceSystem:
    def __init__(self, root):
        self.root = root
        self.root.title("Facial Recognition Attendance System")
        self.root.geometry("800x600")
        self.root.configure(bg='#f0f0f0')
        
        self.current_user = None
        self.is_admin = False
        self.camera = None
        
        # Initialize database
        self.init_database()
        
        # Create directories
        self.create_directories()
        
        # Handle window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Show login screen
        self.show_login_screen()
    
    def on_closing(self):
        """Handle application closing"""
        if self.camera is not None:
            self.camera.release()
        if hasattr(self, 'conn'):
            self.conn.close()
        self.root.destroy()
    
    def init_database(self):
        """Initialize SQLite database for users, students, and attendance"""
        # Connect with timeout to handle locks
        self.conn = sqlite3.connect('attendance.db', timeout=10.0)
        # Enable WAL mode for better concurrency
        self.conn.execute('PRAGMA journal_mode=WAL')
        # Set busy timeout
        self.conn.execute('PRAGMA busy_timeout=10000')
        self.cursor = self.conn.cursor()
        
        # Create users table (for login/register)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0
            )
        ''')
        
        # Create students table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create attendance table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_username TEXT NOT NULL,
                date DATE NOT NULL,
                time_in TIME,
                time_out TIME,
                status TEXT,
                FOREIGN KEY (student_username) REFERENCES students(username)
            )
        ''')
        
        # Create default admin user if not exists
        try:
            self.cursor.execute('SELECT COUNT(*) FROM users WHERE username = ?', ('admin',))
            admin_exists = self.cursor.fetchone()[0] > 0
            
            if not admin_exists:
                self.cursor.execute('''
                    INSERT INTO users (username, password, is_admin)
                    VALUES (?, ?, ?)
                ''', ('admin', 'admin123', 1))
                self.conn.commit()
            else:
                # Ensure admin password and status are correct
                self.cursor.execute('UPDATE users SET password = ?, is_admin = 1 WHERE username = ?', 
                                  ('admin123', 'admin'))
                self.conn.commit()
        except Exception as e:
            print(f"Warning: Could not create/update admin user: {e}")
            # Try to continue anyway
    
    def execute_db(self, query, params=None, fetch=False):
        """Execute database query with proper error handling"""
        max_retries = 3
        is_select = query.strip().upper().startswith('SELECT')
        
        for attempt in range(max_retries):
            try:
                if params:
                    self.cursor.execute(query, params)
                else:
                    self.cursor.execute(query)
                
                # Only commit for non-SELECT queries
                if not is_select:
                    self.conn.commit()
                
                if fetch:
                    return self.cursor.fetchall()
                elif fetch == 'one':
                    return self.cursor.fetchone()
                return True
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    import time
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    raise
            except Exception as e:
                raise
    
    def create_directories(self):
        """Create necessary directories for storing photos and encodings"""
        directories = ['photos', 'encodings', 'trained_models']
        for directory in directories:
            if not os.path.exists(directory):
                os.makedirs(directory)
    
    def show_login_screen(self):
        """Display login/register screen"""
        self.clear_window()
        
        # Title
        title_label = tk.Label(self.root, text="Facial Recognition Attendance System", 
                              font=('Arial', 20, 'bold'), bg='#f0f0f0')
        title_label.pack(pady=30)
        
        # Login Frame
        login_frame = tk.Frame(self.root, bg='#f0f0f0')
        login_frame.pack(pady=20)
        
        tk.Label(login_frame, text="Username:", font=('Arial', 12), bg='#f0f0f0').grid(row=0, column=0, padx=10, pady=10, sticky='e')
        self.login_username = tk.Entry(login_frame, font=('Arial', 12), width=20)
        self.login_username.grid(row=0, column=1, padx=10, pady=10)
        
        tk.Label(login_frame, text="Password:", font=('Arial', 12), bg='#f0f0f0').grid(row=1, column=0, padx=10, pady=10, sticky='e')
        self.login_password = tk.Entry(login_frame, font=('Arial', 12), width=20, show='*')
        self.login_password.grid(row=1, column=1, padx=10, pady=10)
        
        # Buttons
        button_frame = tk.Frame(self.root, bg='#f0f0f0')
        button_frame.pack(pady=20)
        
        login_btn = tk.Button(button_frame, text="Login", font=('Arial', 12, 'bold'),
                             bg='#4CAF50', fg='white', width=15, height=2,
                             command=self.login)
        login_btn.pack(side=tk.LEFT, padx=10)
        
        register_btn = tk.Button(button_frame, text="Register", font=('Arial', 12, 'bold'),
                                bg='#2196F3', fg='white', width=15, height=2,
                                command=self.show_register_dialog)
        register_btn.pack(side=tk.LEFT, padx=10)
    
    def login(self):
        """Handle user login"""
        username = self.login_username.get().strip()
        password = self.login_password.get().strip()
        
        if not username or not password:
            messagebox.showerror("Error", "Please enter both username and password")
            return
        
        try:
            # Use direct cursor for SELECT to avoid commit issues
            self.cursor.execute('SELECT password, is_admin FROM users WHERE username = ?', (username,))
            result = self.cursor.fetchone()
            
            if result:
                stored_password = result[0]
                is_admin = result[1] == 1
                
                if stored_password == password:
                    self.current_user = username
                    self.is_admin = is_admin
                    self.show_main_screen()
                else:
                    messagebox.showerror("Error", "Invalid username or password")
            else:
                messagebox.showerror("Error", "Invalid username or password")
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower():
                messagebox.showerror("Error", "Database is busy. Please try again in a moment.")
            else:
                messagebox.showerror("Error", f"Login failed: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Login failed: {str(e)}")
    
    def show_register_dialog(self):
        """Show registration dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Register New User")
        dialog.geometry("400x250")
        dialog.configure(bg='#f0f0f0')
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (400 // 2)
        y = (dialog.winfo_screenheight() // 2) - (250 // 2)
        dialog.geometry(f"400x250+{x}+{y}")
        
        tk.Label(dialog, text="Username:", font=('Arial', 12), bg='#f0f0f0').pack(pady=10)
        reg_username = tk.Entry(dialog, font=('Arial', 12), width=25)
        reg_username.pack(pady=5)
        reg_username.focus()
        
        tk.Label(dialog, text="Password:", font=('Arial', 12), bg='#f0f0f0').pack(pady=10)
        reg_password = tk.Entry(dialog, font=('Arial', 12), width=25, show='*')
        reg_password.pack(pady=5)
        
        status_label = tk.Label(dialog, text="", font=('Arial', 10), bg='#f0f0f0', fg='red')
        status_label.pack(pady=5)
        
        def register():
            username = reg_username.get().strip()
            password = reg_password.get().strip()
            
            status_label.config(text="")
            
            if not username or not password:
                status_label.config(text="Please enter both username and password", fg='red')
                messagebox.showerror("Error", "Please enter both username and password")
                return
            
            if len(username) < 3:
                status_label.config(text="Username must be at least 3 characters", fg='red')
                messagebox.showerror("Error", "Username must be at least 3 characters")
                return
            
            if len(password) < 3:
                status_label.config(text="Password must be at least 3 characters", fg='red')
                messagebox.showerror("Error", "Password must be at least 3 characters")
                return
            
            try:
                self.execute_db('INSERT INTO users (username, password) VALUES (?, ?)', 
                               (username, password))
                status_label.config(text="Registration successful!", fg='green')
                messagebox.showinfo("Success", "Registration successful! Please login.")
                dialog.destroy()
            except sqlite3.IntegrityError:
                status_label.config(text="Username already exists", fg='red')
                messagebox.showerror("Error", "Username already exists")
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower():
                    status_label.config(text="Database is busy. Please try again.", fg='red')
                    messagebox.showerror("Error", "Database is busy. Please try again in a moment.")
                else:
                    status_label.config(text=f"Error: {str(e)}", fg='red')
                    messagebox.showerror("Error", f"Registration failed: {str(e)}")
            except Exception as e:
                status_label.config(text=f"Error: {str(e)}", fg='red')
                messagebox.showerror("Error", f"Registration failed: {str(e)}")
        
        def on_enter(event):
            register()
        
        # Bind Enter key to register
        reg_password.bind('<Return>', on_enter)
        
        button_frame = tk.Frame(dialog, bg='#f0f0f0')
        button_frame.pack(pady=20, padx=20)
        
        register_btn = tk.Button(button_frame, text="Register", font=('Arial', 12, 'bold'),
                 bg='#2196F3', fg='white', width=15, height=2, command=register, cursor='hand2')
        register_btn.pack(side=tk.LEFT, padx=10, expand=True, fill=tk.X)
        
        cancel_btn = tk.Button(button_frame, text="Cancel", font=('Arial', 12, 'bold'),
                 bg='#757575', fg='white', width=15, height=2, command=dialog.destroy, cursor='hand2')
        cancel_btn.pack(side=tk.LEFT, padx=10, expand=True, fill=tk.X)
    
    def show_main_screen(self):
        """Display main screen after login"""
        self.clear_window()
        
        # Welcome label
        welcome_text = f"Welcome, {self.current_user}!"
        if self.is_admin:
            welcome_text += " (Admin)"
        
        welcome_label = tk.Label(self.root, text=welcome_text, 
                                font=('Arial', 16, 'bold'), bg='#f0f0f0')
        welcome_label.pack(pady=20)
        
        # Buttons Frame
        button_frame = tk.Frame(self.root, bg='#f0f0f0')
        button_frame.pack(pady=20)
        
        # Attendance In Button
        attendance_in_btn = tk.Button(button_frame, text="Attendance In", 
                                      font=('Arial', 12, 'bold'),
                                      bg='#4CAF50', fg='white', width=20, height=3,
                                      command=self.mark_attendance_in)
        attendance_in_btn.grid(row=0, column=0, padx=10, pady=10)
        
        # Attendance Out Button
        attendance_out_btn = tk.Button(button_frame, text="Attendance Out", 
                                       font=('Arial', 12, 'bold'),
                                       bg='#FF9800', fg='white', width=20, height=3,
                                       command=self.mark_attendance_out)
        attendance_out_btn.grid(row=0, column=1, padx=10, pady=10)
        
        # Add Photo Button (Admin only)
        if self.is_admin:
            add_photo_btn = tk.Button(button_frame, text="Add Photo", 
                                     font=('Arial', 12, 'bold'),
                                     bg='#2196F3', fg='white', width=20, height=3,
                                     command=self.add_photo)
            add_photo_btn.grid(row=1, column=0, padx=10, pady=10)
            
            # Register New Student Button
            register_student_btn = tk.Button(button_frame, text="Register New Student", 
                                            font=('Arial', 12, 'bold'),
                                            bg='#9C27B0', fg='white', width=20, height=3,
                                            command=self.register_new_student)
            register_student_btn.grid(row=1, column=1, padx=10, pady=10)
            
            # Training Dataset Button
            training_btn = tk.Button(button_frame, text="Training Dataset", 
                                     font=('Arial', 12, 'bold'),
                                     bg='#F44336', fg='white', width=20, height=3,
                                     command=self.train_dataset)
            training_btn.grid(row=2, column=0, padx=10, pady=10)
            
            # Attendance Report Button
            report_btn = tk.Button(button_frame, text="Attendance Report", 
                                  font=('Arial', 12, 'bold'),
                                  bg='#607D8B', fg='white', width=20, height=3,
                                  command=self.show_attendance_report)
            report_btn.grid(row=2, column=1, padx=10, pady=10)
            
            # Admin Profile Button
            admin_profile_btn = tk.Button(button_frame, text="Admin Profile", 
                                         font=('Arial', 12, 'bold'),
                                         bg='#E91E63', fg='white', width=20, height=3,
                                         command=self.show_admin_profile)
            admin_profile_btn.grid(row=3, column=0, columnspan=2, padx=10, pady=10)
        
        # Logout Button
        logout_btn = tk.Button(self.root, text="Logout", font=('Arial', 10),
                               bg='#757575', fg='white', width=15,
                               command=self.logout)
        logout_btn.pack(pady=20)
    
    def add_photo(self):
        """Capture photos for a student"""
        username = simpledialog.askstring("Add Photo", "Enter student username:")
        if not username:
            return
        
        username = username.strip()
        if not username:
            messagebox.showerror("Error", "Please enter a valid username.")
            return
        
        # IMPORTANT: Check if student is registered in the database before allowing photo capture
        try:
            # Check if student exists in students table
            result = self.execute_db('SELECT username FROM students WHERE username = ?', 
                                    (username,), fetch='one')
            if result is None:
                messagebox.showerror("Error", 
                                    f"Student '{username}' is not registered in the database.\n\n"
                                    "Please register the student first using 'Register New Student' option.")
                return
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower():
                messagebox.showerror("Error", "Database is busy. Please try again in a moment.")
            else:
                messagebox.showerror("Error", f"Error checking student registration: {str(e)}")
            return
        except Exception as e:
            messagebox.showerror("Error", f"Error checking student registration: {str(e)}")
            return
        
        # Create directory for student photos
        student_photo_dir = os.path.join('photos', username)
        if not os.path.exists(student_photo_dir):
            os.makedirs(student_photo_dir)
        
        # Initialize camera
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            messagebox.showerror("Error", "Could not open camera")
            return
        
        count = 0
        total_photos = 50
        
        messagebox.showinfo("Photo Capture", 
                           f"Starting photo capture for {username}.\n"
                           f"Press SPACE to capture photos.\n"
                           f"Press ESC to finish.\n"
                           f"Target: {total_photos} photos")
        
        while count < total_photos:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Display count on frame
            cv2.putText(frame, f"Photos captured: {count}/{total_photos}", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(frame, "Press SPACE to capture, ESC to finish", 
                       (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            cv2.imshow('Capture Photos', frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord(' '):  # Space to capture
                photo_path = os.path.join(student_photo_dir, f"{username}_{count+1}.jpg")
                cv2.imwrite(photo_path, frame)
                count += 1
                print(f"Captured photo {count}/{total_photos}")
            elif key == 27:  # ESC to exit
                break
        
        cap.release()
        cv2.destroyAllWindows()
        
        messagebox.showinfo("Success", f"Successfully captured {count} photos for {username}")
    
    def register_new_student(self):
        """Register a new student (Admin only)"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Register New Student")
        dialog.geometry("400x200")
        dialog.configure(bg='#f0f0f0')
        
        tk.Label(dialog, text="Student Username:", font=('Arial', 12), bg='#f0f0f0').pack(pady=10)
        student_username = tk.Entry(dialog, font=('Arial', 12), width=25)
        student_username.pack(pady=5)
        
        tk.Label(dialog, text="Password:", font=('Arial', 12), bg='#f0f0f0').pack(pady=10)
        student_password = tk.Entry(dialog, font=('Arial', 12), width=25, show='*')
        student_password.pack(pady=5)
        
        def register_student():
            username = student_username.get()
            password = student_password.get()
            
            if not username or not password:
                messagebox.showerror("Error", "Please enter both username and password")
                return
            
            try:
                self.execute_db('INSERT INTO students (username, password) VALUES (?, ?)', 
                               (username, password))
                messagebox.showinfo("Success", f"Student {username} registered successfully!")
                dialog.destroy()
            except sqlite3.IntegrityError:
                messagebox.showerror("Error", "Student username already exists")
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower():
                    messagebox.showerror("Error", "Database is busy. Please try again in a moment.")
                else:
                    messagebox.showerror("Error", f"Registration failed: {str(e)}")
        
        tk.Button(dialog, text="Register Student", font=('Arial', 12, 'bold'),
                 bg='#9C27B0', fg='white', width=15, command=register_student).pack(pady=20)
    
    def train_dataset(self):
        """Train the face recognition model"""
        messagebox.showinfo("Training", "Starting dataset training... This may take a few minutes.")
        
        known_encodings = []
        known_names = []
        
        # Load all student photos and create encodings
        photos_dir = 'photos'
        if not os.path.exists(photos_dir):
            messagebox.showerror("Error", "No photos directory found")
            return
        
        student_dirs = [d for d in os.listdir(photos_dir) if os.path.isdir(os.path.join(photos_dir, d))]
        
        if not student_dirs:
            messagebox.showerror("Error", "No student photos found. Please add photos first.")
            return
        
        total_photos = 0
        for student_dir in student_dirs:
            student_path = os.path.join(photos_dir, student_dir)
            photos = [f for f in os.listdir(student_path) if f.endswith('.jpg')]
            
            for photo in photos:
                photo_path = os.path.join(student_path, photo)
                try:
                    # Load image
                    image = face_recognition.load_image_file(photo_path)
                    # Find face encodings
                    encodings = face_recognition.face_encodings(image)
                    
                    if len(encodings) > 0:
                        known_encodings.append(encodings[0])
                        known_names.append(student_dir)
                        total_photos += 1
                except Exception as e:
                    print(f"Error processing {photo_path}: {e}")
                    continue
        
        if len(known_encodings) == 0:
            messagebox.showerror("Error", "No faces found in photos. Please check your photos.")
            return
        
        # Save encodings
        encoding_data = {
            'encodings': known_encodings,
            'names': known_names
        }
        
        encoding_file = os.path.join('trained_models', 'face_encodings.pkl')
        with open(encoding_file, 'wb') as f:
            pickle.dump(encoding_data, f)
        
        messagebox.showinfo("Success", 
                           f"Training completed!\n"
                           f"Processed {total_photos} photos\n"
                           f"Trained {len(set(known_names))} students")
    
    def mark_attendance_in(self):
        """Mark attendance in using face recognition"""
        self.mark_attendance('in')
    
    def mark_attendance_out(self):
        """Mark attendance out using face recognition"""
        self.mark_attendance('out')
    
    def mark_attendance(self, attendance_type):
        """Mark attendance using face recognition"""
        # Load trained encodings
        encoding_file = os.path.join('trained_models', 'face_encodings.pkl')
        if not os.path.exists(encoding_file):
            messagebox.showerror("Error", "Model not trained. Please train the dataset first.")
            return
        
        try:
            with open(encoding_file, 'rb') as f:
                encoding_data = pickle.load(f)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load trained model: {str(e)}")
            return
        
        known_encodings = encoding_data['encodings']
        known_names = encoding_data['names']
        
        if len(known_encodings) == 0:
            messagebox.showerror("Error", "No trained faces found. Please train the dataset first.")
            return
        
        # Close any existing OpenCV windows
        cv2.destroyAllWindows()
        
        # Initialize camera
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            messagebox.showerror("Error", "Could not open camera")
            return
        
        # Set camera resolution for better face detection
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        # Use consistent window name
        window_name = 'Face Recognition - Attendance ' + attendance_type.upper()
        
        recognized = False
        recognition_count = 0
        required_matches = 3  # Require 3 consecutive matches for reliability
        last_recognized_name = None
        frame_count = 0
        
        while not recognized:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            
            # Flip frame horizontally for mirror effect
            frame = cv2.flip(frame, 1)
            
            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Resize frame for faster processing (optional)
            small_frame = cv2.resize(rgb_frame, (0, 0), fx=0.25, fy=0.25)
            small_rgb_frame = small_frame
            
            # Find faces and encodings
            face_locations = face_recognition.face_locations(small_rgb_frame, model='hog')
            face_encodings = face_recognition.face_encodings(small_rgb_frame, face_locations)
            
            # Scale back up face locations since the frame we detected in was scaled to 1/4 size
            face_locations = [(top*4, right*4, bottom*4, left*4) for (top, right, bottom, left) in face_locations]
            
            name_display = "Looking for face..."
            color = (255, 255, 255)
            
            if len(face_locations) == 0:
                name_display = "No face detected. Please look at the camera."
                color = (0, 165, 255)  # Orange
            else:
                for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                    # Compare with known faces - use more lenient tolerance
                    matches = face_recognition.compare_faces(known_encodings, face_encoding, tolerance=0.55)
                    face_distances = face_recognition.face_distance(known_encodings, face_encoding)
                    
                    if len(face_distances) > 0:
                        best_match_index = np.argmin(face_distances)
                        best_distance = face_distances[best_match_index]
                        
                        # Check if match is good enough (distance < 0.6)
                        if matches[best_match_index] and best_distance < 0.6:
                            current_name = known_names[best_match_index]
                            
                            # Require consecutive matches for reliability
                            if current_name == last_recognized_name:
                                recognition_count += 1
                            else:
                                recognition_count = 1
                                last_recognized_name = current_name
                            
                            # Draw rectangle and name
                            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                            cv2.putText(frame, current_name, (left, top - 10), 
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                            cv2.putText(frame, f"Match: {recognition_count}/{required_matches}", 
                                       (left, bottom + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                            
                            name_display = f"Recognized: {current_name} ({recognition_count}/{required_matches})"
                            color = (0, 255, 0)
                            
                            # If we have enough consecutive matches, mark attendance
                            if recognition_count >= required_matches:
                                name = current_name
                                recognized = True
                                
                                # Show recognition on screen for a moment
                                cv2.putText(frame, f"ATTENDANCE MARKED: {name}", 
                                           (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
                                cv2.imshow(window_name, frame)
                                cv2.waitKey(1000)  # Show for 1 second
                                
                                # Save attendance - convert date/time to strings for SQLite
                                today = datetime.now().date().isoformat()  # Convert to string
                                current_time = datetime.now().time().strftime('%H:%M:%S')  # Convert to string
                                
                                if attendance_type == 'in':
                                    # Check if already marked in today
                                    try:
                                        result = self.execute_db('''
                                            SELECT id FROM attendance 
                                            WHERE student_username = ? AND date = ? AND time_in IS NOT NULL
                                        ''', (name, today), fetch='one')
                                        if result:
                                            messagebox.showwarning("Warning", 
                                                                  f"{name} has already marked attendance IN today")
                                        else:
                                            self.execute_db('''
                                                INSERT INTO attendance (student_username, date, time_in, status)
                                                VALUES (?, ?, ?, ?)
                                            ''', (name, today, current_time, 'Present'))
                                            messagebox.showinfo("Success", 
                                                               f"Attendance IN marked for {name}\n"
                                                               f"Time: {current_time}")
                                    except sqlite3.OperationalError as e:
                                        if "database is locked" in str(e).lower():
                                            messagebox.showerror("Error", "Database is busy. Please try again.")
                                        else:
                                            messagebox.showerror("Error", f"Failed to mark attendance: {str(e)}")
                                    except Exception as e:
                                        messagebox.showerror("Error", f"Failed to mark attendance: {str(e)}")
                                else:  # out
                                    # Check if marked in today
                                    try:
                                        result = self.execute_db('''
                                            SELECT id FROM attendance 
                                            WHERE student_username = ? AND date = ? AND time_in IS NOT NULL
                                        ''', (name, today), fetch='one')
                                        if not result:
                                            messagebox.showwarning("Warning", 
                                                                  f"{name} has not marked attendance IN today")
                                        else:
                                            # Update time_out
                                            self.execute_db('''
                                                UPDATE attendance 
                                                SET time_out = ?, status = 'Completed'
                                                WHERE student_username = ? AND date = ? AND time_out IS NULL
                                            ''', (current_time, name, today))
                                            messagebox.showinfo("Success", 
                                                               f"Attendance OUT marked for {name}\n"
                                                               f"Time: {current_time}")
                                    except sqlite3.OperationalError as e:
                                        if "database is locked" in str(e).lower():
                                            messagebox.showerror("Error", "Database is busy. Please try again.")
                                        else:
                                            messagebox.showerror("Error", f"Failed to mark attendance: {str(e)}")
                                    except Exception as e:
                                        messagebox.showerror("Error", f"Failed to mark attendance: {str(e)}")
                                
                                break
                        else:
                            # Face detected but not recognized
                            cv2.rectangle(frame, (left, top), (right, bottom), (0, 165, 255), 2)
                            cv2.putText(frame, "Unknown", (left, top - 10), 
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 165, 255), 2)
                            name_display = "Face detected but not recognized"
                            color = (0, 165, 255)
                            recognition_count = 0
                            last_recognized_name = None
            
            # Display status text
            cv2.putText(frame, name_display, (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.putText(frame, f"Press ESC to cancel", 
                       (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            cv2.imshow(window_name, frame)
            
            if cv2.waitKey(1) & 0xFF == 27:  # ESC
                break
        
        cap.release()
        cv2.destroyAllWindows()
    
    def show_attendance_report(self):
        """Display attendance report"""
        report_window = tk.Toplevel(self.root)
        report_window.title("Attendance Report")
        report_window.geometry("900x600")
        
        # Create treeview
        tree = ttk.Treeview(report_window, columns=('Student', 'Date', 'Time In', 'Time Out', 'Status'), 
                           show='headings', height=25)
        
        tree.heading('Student', text='Student Username')
        tree.heading('Date', text='Date')
        tree.heading('Time In', text='Time In')
        tree.heading('Time Out', text='Time Out')
        tree.heading('Status', text='Status')
        
        tree.column('Student', width=150)
        tree.column('Date', width=120)
        tree.column('Time In', width=120)
        tree.column('Time Out', width=120)
        tree.column('Status', width=120)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(report_window, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # Fetch attendance data
        try:
            records = self.execute_db('''
                SELECT student_username, date, time_in, time_out, status
                FROM attendance
                ORDER BY date DESC, student_username
            ''', fetch=True)
            
            for record in records:
                tree.insert('', 'end', values=record)
            
            # Get summary statistics
            total_result = self.execute_db('SELECT COUNT(DISTINCT student_username) FROM attendance', 
                                         fetch='one')
            total_students = total_result[0] if total_result else 0
            
            today_result = self.execute_db('SELECT COUNT(*) FROM attendance WHERE date = ?', 
                                         (datetime.now().date().isoformat(),), fetch='one')
            today_attendance = today_result[0] if today_result else 0
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower():
                messagebox.showerror("Error", "Database is busy. Please try again in a moment.")
                report_window.destroy()
                return
            else:
                messagebox.showerror("Error", f"Failed to load report: {str(e)}")
                report_window.destroy()
                return
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Summary frame
        summary_frame = tk.Frame(report_window)
        summary_frame.pack(fill=tk.X, padx=10, pady=10)
        
        summary_label = tk.Label(summary_frame, 
                                text=f"Total Students: {total_students} | Today's Attendance: {today_attendance}",
                                font=('Arial', 12, 'bold'))
        summary_label.pack()
    
    def show_admin_profile(self):
        """Display admin profile window with password management"""
        if not self.is_admin:
            messagebox.showerror("Error", "Access denied. Admin privileges required.")
            return
        
        profile_window = tk.Toplevel(self.root)
        profile_window.title("Admin Profile")
        profile_window.geometry("900x700")
        profile_window.configure(bg='#f0f0f0')
        profile_window.transient(self.root)
        
        # Title
        title_label = tk.Label(profile_window, text="Admin Profile Management", 
                              font=('Arial', 18, 'bold'), bg='#f0f0f0')
        title_label.pack(pady=20)
        
        # Create notebook for tabs
        notebook = ttk.Notebook(profile_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Tab 1: Change Own Password
        change_pass_frame = tk.Frame(notebook, bg='#f0f0f0')
        notebook.add(change_pass_frame, text="Change My Password")
        
        tk.Label(change_pass_frame, text="Change Admin Password", 
                font=('Arial', 14, 'bold'), bg='#f0f0f0').pack(pady=20)
        
        pass_frame = tk.Frame(change_pass_frame, bg='#f0f0f0')
        pass_frame.pack(pady=30)
        
        tk.Label(pass_frame, text="Current Password:", font=('Arial', 12), bg='#f0f0f0').grid(row=0, column=0, padx=10, pady=10, sticky='e')
        current_pass_entry = tk.Entry(pass_frame, font=('Arial', 12), width=25, show='*')
        current_pass_entry.grid(row=0, column=1, padx=10, pady=10)
        
        tk.Label(pass_frame, text="New Password:", font=('Arial', 12), bg='#f0f0f0').grid(row=1, column=0, padx=10, pady=10, sticky='e')
        new_pass_entry = tk.Entry(pass_frame, font=('Arial', 12), width=25, show='*')
        new_pass_entry.grid(row=1, column=1, padx=10, pady=10)
        
        tk.Label(pass_frame, text="Confirm Password:", font=('Arial', 12), bg='#f0f0f0').grid(row=2, column=0, padx=10, pady=10, sticky='e')
        confirm_pass_entry = tk.Entry(pass_frame, font=('Arial', 12), width=25, show='*')
        confirm_pass_entry.grid(row=2, column=1, padx=10, pady=10)
        
        def change_admin_password():
            current = current_pass_entry.get().strip()
            new = new_pass_entry.get().strip()
            confirm = confirm_pass_entry.get().strip()
            
            if not current or not new or not confirm:
                messagebox.showerror("Error", "Please fill all fields")
                return
            
            # Verify current password
            try:
                result = self.execute_db('SELECT password FROM users WHERE username = ?', 
                                        (self.current_user,), fetch='one')
                if not result or result[0] != current:
                    messagebox.showerror("Error", "Current password is incorrect")
                    return
                
                if new != confirm:
                    messagebox.showerror("Error", "New password and confirm password do not match")
                    return
                
                if len(new) < 3:
                    messagebox.showerror("Error", "Password must be at least 3 characters")
                    return
                
                # Update password
                self.execute_db('UPDATE users SET password = ? WHERE username = ?', 
                              (new, self.current_user))
                messagebox.showinfo("Success", "Password changed successfully!")
                current_pass_entry.delete(0, tk.END)
                new_pass_entry.delete(0, tk.END)
                confirm_pass_entry.delete(0, tk.END)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to change password: {str(e)}")
        
        tk.Button(pass_frame, text="Change Password", font=('Arial', 12, 'bold'),
                 bg='#4CAF50', fg='white', width=20, command=change_admin_password).grid(row=3, column=0, columnspan=2, pady=20)
        
        # Tab 2: View All Students
        view_students_frame = tk.Frame(notebook, bg='#f0f0f0')
        notebook.add(view_students_frame, text="View All Students")
        
        tk.Label(view_students_frame, text="All Students Credentials", 
                font=('Arial', 14, 'bold'), bg='#f0f0f0').pack(pady=10)
        
        # Create treeview for students
        students_tree = ttk.Treeview(view_students_frame, columns=('Username', 'Password'), 
                                    show='headings', height=20)
        students_tree.heading('Username', text='Username')
        students_tree.heading('Password', text='Password')
        students_tree.column('Username', width=200)
        students_tree.column('Password', width=200)
        
        # Scrollbar for students tree
        students_scrollbar = ttk.Scrollbar(view_students_frame, orient=tk.VERTICAL, command=students_tree.yview)
        students_tree.configure(yscrollcommand=students_scrollbar.set)
        
        def load_students():
            # Clear existing items
            for item in students_tree.get_children():
                students_tree.delete(item)
            
            try:
                # Get all students from students table
                records = self.execute_db('SELECT username, password FROM students ORDER BY username', 
                                        fetch=True)
                for record in records:
                    students_tree.insert('', 'end', values=record)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load students: {str(e)}")
        
        load_students()
        
        refresh_btn = tk.Button(view_students_frame, text="Refresh", font=('Arial', 10),
                               bg='#2196F3', fg='white', command=load_students)
        refresh_btn.pack(pady=5)
        
        students_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        students_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)
        
        # Tab 3: Change Student Password
        change_student_frame = tk.Frame(notebook, bg='#f0f0f0')
        notebook.add(change_student_frame, text="Change Student Password")
        
        tk.Label(change_student_frame, text="Change Student Password", 
                font=('Arial', 14, 'bold'), bg='#f0f0f0').pack(pady=20)
        
        student_pass_frame = tk.Frame(change_student_frame, bg='#f0f0f0')
        student_pass_frame.pack(pady=30)
        
        tk.Label(student_pass_frame, text="Student Username:", font=('Arial', 12), bg='#f0f0f0').grid(row=0, column=0, padx=10, pady=10, sticky='e')
        student_username_entry = tk.Entry(student_pass_frame, font=('Arial', 12), width=25)
        student_username_entry.grid(row=0, column=1, padx=10, pady=10)
        
        tk.Label(student_pass_frame, text="New Password:", font=('Arial', 12), bg='#f0f0f0').grid(row=1, column=0, padx=10, pady=10, sticky='e')
        student_new_pass_entry = tk.Entry(student_pass_frame, font=('Arial', 12), width=25, show='*')
        student_new_pass_entry.grid(row=1, column=1, padx=10, pady=10)
        
        tk.Label(student_pass_frame, text="Confirm Password:", font=('Arial', 12), bg='#f0f0f0').grid(row=2, column=0, padx=10, pady=10, sticky='e')
        student_confirm_pass_entry = tk.Entry(student_pass_frame, font=('Arial', 12), width=25, show='*')
        student_confirm_pass_entry.grid(row=2, column=1, padx=10, pady=10)
        
        def change_student_password():
            username = student_username_entry.get().strip()
            new = student_new_pass_entry.get().strip()
            confirm = student_confirm_pass_entry.get().strip()
            
            if not username or not new or not confirm:
                messagebox.showerror("Error", "Please fill all fields")
                return
            
            # Check if student exists
            try:
                result = self.execute_db('SELECT COUNT(*) FROM students WHERE username = ?', 
                                        (username,), fetch='one')
                if not result or result[0] == 0:
                    messagebox.showerror("Error", f"Student '{username}' does not exist")
                    return
                
                if new != confirm:
                    messagebox.showerror("Error", "New password and confirm password do not match")
                    return
                
                if len(new) < 3:
                    messagebox.showerror("Error", "Password must be at least 3 characters")
                    return
                
                # Update password in students table
                self.execute_db('UPDATE students SET password = ? WHERE username = ?', 
                              (new, username))
                
                # Also update in users table if exists
                try:
                    self.execute_db('UPDATE users SET password = ? WHERE username = ?', 
                                  (new, username))
                except:
                    pass  # User might not exist in users table, that's okay
                
                messagebox.showinfo("Success", f"Password changed successfully for {username}!")
                student_username_entry.delete(0, tk.END)
                student_new_pass_entry.delete(0, tk.END)
                student_confirm_pass_entry.delete(0, tk.END)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to change password: {str(e)}")
        
        tk.Button(student_pass_frame, text="Change Student Password", font=('Arial', 12, 'bold'),
                 bg='#F44336', fg='white', width=25, command=change_student_password).grid(row=3, column=0, columnspan=2, pady=20)
    
    def logout(self):
        """Logout and return to login screen"""
        self.current_user = None
        self.is_admin = False
        self.show_login_screen()
    
    def clear_window(self):
        """Clear all widgets from window"""
        for widget in self.root.winfo_children():
            widget.destroy()

def main():
    root = tk.Tk()
    app = AttendanceSystem(root)
    root.mainloop()

if __name__ == "__main__":
    main()

