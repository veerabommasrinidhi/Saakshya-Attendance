import sqlite3
from datetime import datetime, date
import json
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class Database:
    """Database management class"""
    
    def __init__(self, db_path='attendance.db'):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Students table
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
                enrollment_year INTEGER,
                contact_number TEXT,
                profile_picture TEXT,
                registered_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        # Attendance table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                date DATE NOT NULL,
                time_in TIME NOT NULL,
                time_out TIME,
                status TEXT DEFAULT 'present',
                confidence REAL,
                marked_by TEXT,
                notes TEXT,
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                UNIQUE(student_id, date)
            )
        ''')
        
        # Admin table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT,
                full_name TEXT,
                last_login TIMESTAMP
            )
        ''')
        
        # Attendance logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attendance_id INTEGER,
                action TEXT,
                old_data TEXT,
                new_data TEXT,
                performed_by TEXT,
                ip_address TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert default admin if not exists
        cursor.execute("SELECT * FROM admin WHERE username = 'admin'")
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO admin (username, password, email, full_name)
                VALUES (?, ?, ?, ?)
            ''', ('admin', 'admin123', 'admin@school.com', 'System Administrator'))
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    
    def register_student(self, student_id: str, name: str, email: str, 
                        password: str, face_encoding: str, 
                        department: str = 'General', semester: int = 1) -> Tuple[bool, str]:
        """Register a new student"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO students (student_id, name, email, password, face_encoding, 
                                    department, semester, enrollment_year)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, name, email, password, face_encoding, 
                  department, semester, datetime.now().year))
            conn.commit()
            return True, "Student registered successfully"
        except sqlite3.IntegrityError as e:
            return False, f"Registration failed: {str(e)}"
        finally:
            conn.close()
    
    def authenticate_student(self, student_id: str, password: str) -> Optional[Dict]:
        """Authenticate student login"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM students 
            WHERE student_id = ? AND password = ? AND is_active = 1
        ''', (student_id, password))
        student = cursor.fetchone()
        conn.close()
        return dict(student) if student else None
    
    def authenticate_admin(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate admin login"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM admin WHERE username = ? AND password = ?
        ''', (username, password))
        admin = cursor.fetchone()
        
        if admin:
            # Update last login
            cursor.execute('''
                UPDATE admin SET last_login = CURRENT_TIMESTAMP WHERE username = ?
            ''', (username,))
            conn.commit()
        
        conn.close()
        return dict(admin) if admin else None
    
    def mark_attendance(self, student_id: str, confidence: float = None, 
                       marked_by: str = 'system') -> Tuple[bool, str]:
        """Mark attendance for a student"""
        conn = self.get_connection()
        cursor = conn.cursor()
        today = date.today().isoformat()
        current_time = datetime.now().strftime('%H:%M:%S')
        
        try:
            cursor.execute('''
                INSERT INTO attendance (student_id, date, time_in, status, confidence, marked_by)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (student_id, today, current_time, 'present', confidence, marked_by))
            conn.commit()
            return True, "Attendance marked successfully"
        except sqlite3.IntegrityError:
            return False, "Attendance already marked for today"
        finally:
            conn.close()
    
    def get_student_attendance(self, student_id: str) -> Dict:
        """Get attendance statistics for a student"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get total attendance records
        cursor.execute('''
            SELECT COUNT(*) as total_classes, 
                   SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present
            FROM attendance
            WHERE student_id = ?
        ''', (student_id,))
        result = cursor.fetchone()
        
        # Get monthly breakdown
        cursor.execute('''
            SELECT strftime('%Y-%m', date) as month,
                   COUNT(*) as total,
                   SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present
            FROM attendance
            WHERE student_id = ?
            GROUP BY strftime('%Y-%m', date)
            ORDER BY month DESC
            LIMIT 6
        ''', (student_id,))
        monthly = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        total_classes = result['total_classes'] if result['total_classes'] else 0
        present = result['present'] if result['present'] else 0
        percentage = (present / total_classes * 100) if total_classes > 0 else 0
        
        return {
            'total_classes': total_classes,
            'present': present,
            'absent': total_classes - present,
            'percentage': round(percentage, 2),
            'monthly': monthly
        }
    
    def get_student_recent_attendance(self, student_id: str, limit: int = 10) -> List[Dict]:
        """Get recent attendance records for a student"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT date, time_in, status, confidence
            FROM attendance
            WHERE student_id = ?
            ORDER BY date DESC, time_in DESC
            LIMIT ?
        ''', (student_id, limit))
        records = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return records
    
    def get_all_attendance(self) -> List[Dict]:
        """Get attendance for all students"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT s.student_id, s.name, s.department, s.semester,
                   COUNT(a.id) as total_classes,
                   SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) as present,
                   ROUND(AVG(a.confidence), 2) as avg_confidence
            FROM students s
            LEFT JOIN attendance a ON s.student_id = a.student_id
            WHERE s.is_active = 1
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
                'percentage': round(percentage, 2),
                'avg_confidence': row['avg_confidence'] or 0
            })
        
        conn.close()
        return attendance_data
    
    def get_todays_attendance(self) -> List[Dict]:
        """Get today's attendance records"""
        conn = self.get_connection()
        cursor = conn.cursor()
        today = date.today().isoformat()
        
        cursor.execute('''
            SELECT s.student_id, s.name, s.department, 
                   a.time_in, a.status, a.confidence
            FROM students s
            LEFT JOIN attendance a ON s.student_id = a.student_id AND a.date = ?
            WHERE s.is_active = 1
            ORDER BY a.time_in DESC NULLS LAST, s.name
        ''', (today,))
        
        attendance = []
        for row in cursor.fetchall():
            attendance.append({
                'student_id': row['student_id'],
                'name': row['name'],
                'department': row['department'],
                'time': row['time_in'] if row['time_in'] else '-',
                'status': row['status'] if row['status'] else 'absent',
                'confidence': row['confidence'] if row['confidence'] else 0
            })
        
        conn.close()
        return attendance
    
    def get_all_students(self) -> List[Dict]:
        """Get all registered students"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT student_id, name, email, department, semester, 
                   enrollment_year, registered_date, face_encoding
            FROM students 
            WHERE is_active = 1
            ORDER BY student_id
        ''')
        students = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return students
    
    def get_attendance_summary(self) -> Dict:
        """Get overall attendance summary"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Total students
        cursor.execute("SELECT COUNT(*) as total FROM students WHERE is_active = 1")
        total_students = cursor.fetchone()['total']
        
        # Today's attendance
        today = date.today().isoformat()
        cursor.execute('''
            SELECT COUNT(*) as present 
            FROM attendance WHERE date = ? AND status = 'present'
        ''', (today,))
        today_present = cursor.fetchone()['present']
        
        # Average attendance
        cursor.execute('''
            SELECT AVG(CASE WHEN status = 'present' THEN 1 ELSE 0 END) * 100 as avg_attendance
            FROM attendance
            WHERE date >= date('now', '-30 days')
        ''')
        avg_attendance = cursor.fetchone()['avg_attendance'] or 0
        
        # Weekly trend
        cursor.execute('''
            SELECT date, 
                   COUNT(CASE WHEN status = 'present' THEN 1 END) as present,
                   COUNT(*) as total
            FROM attendance
            WHERE date >= date('now', '-7 days')
            GROUP BY date
            ORDER BY date
        ''')
        weekly_trend = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            'total_students': total_students,
            'present_today': today_present,
            'absent_today': total_students - today_present,
            'attendance_rate': round(today_present / total_students * 100, 2) if total_students > 0 else 0,
            'avg_attendance_30d': round(avg_attendance, 2),
            'weekly_trend': weekly_trend
        }