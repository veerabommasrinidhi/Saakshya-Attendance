from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from datetime import datetime
import cv2
import numpy as np
import base64
import sqlite3
import logging
import socket
from functools import wraps

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'
app.config['SESSION_TYPE'] = 'filesystem'

# Initialize extensions
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize face detector
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')

# Database class
class Database:
    def __init__(self, db_path='attendance.db'):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                face_encoding TEXT,
                department TEXT DEFAULT 'General',
                semester INTEGER DEFAULT 1,
                registered_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                date DATE NOT NULL,
                time_in TIME NOT NULL,
                status TEXT DEFAULT 'present',
                confidence REAL,
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                UNIQUE(student_id, date)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT,
                full_name TEXT
            )
        ''')
        
        cursor.execute("SELECT * FROM admin WHERE username = 'admin'")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO admin (username, password, email, full_name) VALUES (?, ?, ?, ?)",
                         ('admin', 'admin123', 'admin@school.com', 'System Administrator'))
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    
    def register_student(self, student_id, name, email, password, face_encoding, department='General', semester=1):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO students (student_id, name, email, password, face_encoding, department, semester)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, name, email, password, face_encoding, department, semester))
            conn.commit()
            return True, "Student registered successfully"
        except sqlite3.IntegrityError as e:
            return False, f"Registration failed: {str(e)}"
        finally:
            conn.close()
    
    def authenticate_student(self, student_id, password):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students WHERE student_id = ? AND password = ?", 
                      (student_id, password))
        student = cursor.fetchone()
        conn.close()
        return dict(student) if student else None
    
    def authenticate_admin(self, username, password):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admin WHERE username = ? AND password = ?", 
                      (username, password))
        admin = cursor.fetchone()
        conn.close()
        return dict(admin) if admin else None
    
    def mark_attendance(self, student_id, confidence=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        current_time = datetime.now().strftime('%H:%M:%S')
        
        try:
            cursor.execute('''
                INSERT INTO attendance (student_id, date, time_in, status, confidence)
                VALUES (?, ?, ?, ?, ?)
            ''', (student_id, today, current_time, 'present', confidence))
            conn.commit()
            return True, "Attendance marked successfully"
        except sqlite3.IntegrityError:
            return False, "Attendance already marked for today"
        finally:
            conn.close()
    
    def get_student_attendance(self, student_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) as total_classes, 
                   SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present
            FROM attendance
            WHERE student_id = ?
        ''', (student_id,))
        result = cursor.fetchone()
        
        cursor.execute('''
            SELECT date, time_in, status, confidence
            FROM attendance
            WHERE student_id = ?
            ORDER BY date DESC, time_in DESC
            LIMIT 10
        ''', (student_id,))
        recent = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        total_classes = result['total_classes'] if result['total_classes'] else 0
        present = result['present'] if result['present'] else 0
        percentage = (present / total_classes * 100) if total_classes > 0 else 0
        
        return {
            'total_classes': total_classes,
            'present': present,
            'absent': total_classes - present,
            'percentage': round(percentage, 2),
            'recent': recent
        }
    
    def get_all_attendance(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT s.student_id, s.name, s.department, s.semester,
                   COUNT(a.id) as total_classes,
                   SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) as present
            FROM students s
            LEFT JOIN attendance a ON s.student_id = a.student_id
            GROUP BY s.student_id, s.name, s.department, s.semester
            ORDER BY s.student_id
        ''')
        
        attendance_data = []
        for row in cursor.fetchall():
            total = row['total_classes'] if row['total_classes'] else 0
            present = row['present'] if row['present'] else 0
            percentage = (present / total * 100) if total > 0 else 0
            attendance_data.append({
                'student_id': row['student_id'],
                'name': row['name'],
                'department': row['department'],
                'semester': row['semester'],
                'total_classes': total,
                'present': present,
                'absent': total - present,
                'percentage': round(percentage, 2)
            })
        
        conn.close()
        return attendance_data
    
    def get_todays_attendance(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT s.student_id, s.name, s.department, 
                   a.time_in, a.status
            FROM students s
            LEFT JOIN attendance a ON s.student_id = a.student_id AND a.date = ?
            ORDER BY a.time_in DESC NULLS LAST, s.name
        ''', (today,))
        
        attendance = []
        for row in cursor.fetchall():
            attendance.append({
                'student_id': row['student_id'],
                'name': row['name'],
                'department': row['department'],
                'time': row['time_in'] if row['time_in'] else '-',
                'status': row['status'] if row['status'] else 'absent'
            })
        
        conn.close()
        return attendance
    
    def get_all_students(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT student_id, name, email, department, semester, face_encoding FROM students')
        students = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return students
    
    def get_attendance_summary(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as total FROM students")
        total_students = cursor.fetchone()['total']
        
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("SELECT COUNT(*) as present FROM attendance WHERE date = ? AND status = 'present'", (today,))
        today_present = cursor.fetchone()['present']
        
        cursor.execute('''
            SELECT AVG(CASE WHEN status = 'present' THEN 1 ELSE 0 END) * 100 as avg_attendance
            FROM attendance
            WHERE date >= date('now', '-30 days')
        ''')
        avg_attendance = cursor.fetchone()['avg_attendance'] or 0
        
        conn.close()
        
        return {
            'total_students': total_students,
            'present_today': today_present,
            'absent_today': total_students - today_present,
            'attendance_rate': round(today_present / total_students * 100, 2) if total_students > 0 else 0,
            'avg_attendance_30d': round(avg_attendance, 2)
        }

db = Database()

# Face recognition functions
def encode_face_from_image(image_bytes):
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(100, 100))
        
        if len(faces) == 0:
            return None, "No face detected in the image"
        
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        face_roi = gray[y:y+h, x:x+w]
        face_roi = cv2.resize(face_roi, (200, 200))
        
        _, buffer = cv2.imencode('.jpg', face_roi)
        face_encoding = base64.b64encode(buffer).decode('utf-8')
        
        return face_encoding, "Face encoded successfully"
    except Exception as e:
        return None, f"Error encoding face: {str(e)}"

def compare_faces(known_encoding, frame):
    try:
        known_face_bytes = base64.b64decode(known_encoding)
        nparr = np.frombuffer(known_face_bytes, np.uint8)
        known_face = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray_frame, 1.1, 5, minSize=(100, 100))
        
        if len(faces) == 0:
            return False, None, 0
        
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        current_face = gray_frame[y:y+h, x:x+w]
        current_face = cv2.resize(current_face, (200, 200))
        
        hist1 = cv2.calcHist([known_face], [0], None, [256], [0, 256])
        hist2 = cv2.calcHist([current_face], [0], None, [256], [0, 256])
        correlation = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
        confidence = max(0, min(100, correlation * 100))
        
        return confidence > 60, (x, y, w, h), round(confidence, 2)
    except Exception as e:
        return False, None, 0

def detect_liveness(frame):
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(100, 100))
        
        if len(faces) == 0:
            return False, "No face detected", 0
        
        x, y, w, h = faces[0]
        face_roi = frame[y:y+h, x:x+w]
        
        gray_roi = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        eyes = eye_cascade.detectMultiScale(gray_roi, 1.1, 5)
        
        if len(eyes) >= 2:
            return True, "Liveness detected", 80
        else:
            return False, "No eyes detected", 40
    except Exception as e:
        return False, f"Error: {str(e)}", 0

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin' not in session:
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/register')
def register_page():
    return render_template('register.html')

@app.route('/student_dashboard')
def student_dashboard():
    if 'student_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('student_dashboard.html')

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin' not in session:
        return redirect(url_for('login_page'))
    return render_template('admin_dashboard.html')

@app.route('/take_attendance')
def take_attendance():
    if 'admin' not in session:
        return redirect(url_for('login_page'))
    return render_template('take_attendance.html')

# API Routes (same as before - keeping them short here)
@app.route('/api/login', methods=['POST'])
def api_login():
    try:
        data = request.json
        user_type = data.get('type')
        
        if user_type == 'student':
            student = db.authenticate_student(data.get('student_id'), data.get('password'))
            if student:
                session['student_id'] = student['student_id']
                session['student_name'] = student['name']
                return jsonify({'success': True, 'redirect': '/student_dashboard', 'user': student})
        
        elif user_type == 'admin':
            admin = db.authenticate_admin(data.get('username'), data.get('password'))
            if admin:
                session['admin'] = admin['username']
                return jsonify({'success': True, 'redirect': '/admin_dashboard'})
        
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

@app.route('/api/register', methods=['POST'])
def api_register():
    try:
        student_id = request.form.get('student_id')
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        department = request.form.get('department', 'General')
        semester = request.form.get('semester', 1)
        face_image = request.files.get('face_image')
        
        if not all([student_id, name, email, password, face_image]):
            return jsonify({'success': False, 'message': 'All fields are required'})
        
        face_bytes = face_image.read()
        encoding, message = encode_face_from_image(face_bytes)
        
        if not encoding:
            return jsonify({'success': False, 'message': message})
        
        success, msg = db.register_student(student_id, name, email, password, encoding, department, semester)
        
        if success:
            socketio.emit('new_student_registered', {'student_id': student_id, 'name': name})
            return jsonify({'success': True, 'message': msg})
        else:
            return jsonify({'success': False, 'message': msg})
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

@app.route('/api/recognize_face', methods=['POST'])
@admin_required
def api_recognize_face():
    try:
        data = request.json
        image_data = data.get('image')
        
        if not image_data:
            return jsonify({'success': False, 'message': 'No image provided'})
        
        if image_data.startswith('data:image'):
            image_data = image_data.split(',')[1]
        
        image_bytes = base64.b64decode(image_data)
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return jsonify({'success': False, 'message': 'Invalid image format'})
        
        is_live, liveness_msg, liveness_score = detect_liveness(frame)
        
        if not is_live:
            return jsonify({'success': False, 'message': f"Liveness check failed: {liveness_msg}", 'liveness_score': liveness_score})
        
        students = db.get_all_students()
        recognized_student = None
        best_match_score = 0
        
        for student in students:
            if student.get('face_encoding'):
                match, face_location, confidence = compare_faces(student['face_encoding'], frame)
                if match and confidence > best_match_score:
                    best_match_score = confidence
                    recognized_student = student
        
        if recognized_student and best_match_score > 60:
            success, message = db.mark_attendance(recognized_student['student_id'], confidence=best_match_score)
            
            if success:
                socketio.emit('attendance_marked', {
                    'student_id': recognized_student['student_id'],
                    'student_name': recognized_student['name'],
                    'confidence': best_match_score
                })
                
                return jsonify({
                    'success': True,
                    'student': {
                        'student_id': recognized_student['student_id'],
                        'name': recognized_student['name'],
                        'department': recognized_student.get('department', 'N/A')
                    },
                    'confidence': best_match_score,
                    'message': f"Welcome {recognized_student['name']}! Attendance marked with {best_match_score:.1f}% confidence",
                    'liveness_score': liveness_score
                })
            else:
                return jsonify({'success': False, 'message': f"Face recognized but {message}"})
        
        return jsonify({'success': False, 'message': f'Face not recognized (best match: {best_match_score:.1f}%)'})
    except Exception as e:
        logger.error(f"Face recognition error: {str(e)}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

@app.route('/api/student_attendance', methods=['GET'])
def api_student_attendance():
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    try:
        stats = db.get_student_attendance(session['student_id'])
        return jsonify({'success': True, 'data': stats, 'recent': stats.get('recent', [])})
    except Exception as e:
        logger.error(f"Error getting student attendance: {str(e)}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

@app.route('/api/all_attendance', methods=['GET'])
@admin_required
def api_all_attendance():
    try:
        attendance_data = db.get_all_attendance()
        return jsonify({'success': True, 'data': attendance_data})
    except Exception as e:
        logger.error(f"Error getting all attendance: {str(e)}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

@app.route('/api/todays_attendance', methods=['GET'])
@admin_required
def api_todays_attendance():
    try:
        attendance = db.get_todays_attendance()
        return jsonify({'success': True, 'data': attendance})
    except Exception as e:
        logger.error(f"Error getting today's attendance: {str(e)}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

@app.route('/api/students', methods=['GET'])
@admin_required
def api_students():
    try:
        students = db.get_all_students()
        return jsonify({'success': True, 'data': students})
    except Exception as e:
        logger.error(f"Error getting students: {str(e)}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

@app.route('/api/attendance_summary', methods=['GET'])
@admin_required
def api_attendance_summary():
    try:
        summary = db.get_attendance_summary()
        return jsonify({'success': True, 'data': summary})
    except Exception as e:
        logger.error(f"Error getting summary: {str(e)}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'success': True})

# WebSocket events
@socketio.on('connect')
def handle_connect():
    emit('connected', {'message': 'Connected to server'})

def find_free_port():
    """Find a free port to run the server"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        s.listen(1)
        port = s.getsockname()[1]
        return port

if __name__ == '__main__':
    try:
        # Try port 5000 first
        port = 5000
        print(f"\n{'='*50}")
        print(f"🚀 Starting Saakshya Attendance System...")
        print(f"{'='*50}\n")
        print(f"📡 Server running at: http://127.0.0.1:{port}")
        print(f"🔐 Admin Login: username='admin', password='admin123'")
        print(f"📝 Press CTRL+C to stop the server\n")
        print(f"{'='*50}\n")
        
        socketio.run(app, debug=True, host='127.0.0.1', port=port)
        
    except OSError as e:
        if "10048" in str(e) or "address already in use" in str(e).lower():
            print(f"\n⚠️ Port 5000 is already in use!")
            print(f"\n🔧 Solutions:")
            print(f"   1. Close any other application using port 5000")
            print(f"   2. Or use a different port by changing the last line in app.py")
            print(f"\n💡 To find and kill the process using port 5000:")
            print(f"   Run in Command Prompt as Administrator:")
            print(f"   netstat -ano | findstr :5000")
            print(f"   taskkill /PID <PID> /F")
            print(f"\n🔄 Or try port 8080 instead:")
            print(f"   Change 'port=5000' to 'port=8080' in the last line\n")
        else:
            raise