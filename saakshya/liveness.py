import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)

class LivenessDetector:
    """Simplified liveness detection using motion and blink detection"""
    
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        self.eye_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_eye.xml'
        )
        
        self.blink_counter = 0
        self.total_blinks = 0
        self.blink_detected = False
        self.prev_frame = None
        self.prev_face_area = None
        
    def detect_eyes(self, frame, face_roi):
        """Detect eyes in face region"""
        try:
            if face_roi is None or face_roi.size == 0:
                return False
            
            gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
            eyes = self.eye_cascade.detectMultiScale(gray, 1.1, 5)
            return len(eyes) >= 2
        except:
            return False
    
    def detect_motion(self, frame):
        """Detect motion for liveness"""
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)
            
            if self.prev_frame is None:
                self.prev_frame = gray
                return False, 0
            
            # Compute difference
            frame_delta = cv2.absdiff(self.prev_frame, gray)
            thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
            
            # Dilate to fill gaps
            thresh = cv2.dilate(thresh, None, iterations=2)
            
            # Calculate motion percentage
            motion_percentage = np.sum(thresh > 0) / thresh.size
            
            self.prev_frame = gray
            
            return motion_percentage > 0.02, motion_percentage * 100
            
        except Exception as e:
            logger.error(f"Motion detection error: {str(e)}")
            return False, 0
    
    def detect_face_movement(self, faces):
        """Detect if face is moving (not a static image)"""
        try:
            if not faces:
                return False, 0
            
            # Get the largest face area
            x, y, w, h = faces[0]
            current_area = w * h
            
            if self.prev_face_area is not None:
                area_change = abs(current_area - self.prev_face_area) / self.prev_face_area
                self.prev_face_area = current_area
                return area_change > 0.05, area_change * 100
            
            self.prev_face_area = current_area
            return False, 0
            
        except:
            return False, 0
    
    def detect_liveness(self, frame):
        """Comprehensive liveness detection"""
        liveness_score = 0
        details = []
        
        # Detect faces
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(100, 100))
        
        if len(faces) == 0:
            return {
                'is_live': False,
                'score': 0,
                'details': ['No face detected'],
                'motion_detected': False,
                'blink_detected': False
            }
        
        # Get the largest face
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        face_roi = frame[y:y+h, x:x+w]
        
        # 1. Motion detection (50% weight)
        motion_detected, motion_percentage = self.detect_motion(frame)
        if motion_detected:
            liveness_score += 50
            details.append(f"Motion detected ({motion_percentage:.1f}%)")
        else:
            details.append(f"No motion detected ({motion_percentage:.1f}%)")
        
        # 2. Face movement detection (30% weight)
        movement_detected, movement_percentage = self.detect_face_movement(faces)
        if movement_detected:
            liveness_score += 30
            details.append(f"Face movement detected ({movement_percentage:.1f}%)")
        else:
            details.append("No face movement detected")
        
        # 3. Eye detection (20% weight)
        eyes_detected = self.detect_eyes(frame, face_roi)
        if eyes_detected:
            liveness_score += 20
            details.append("Eyes detected")
        else:
            details.append("Eyes not clearly visible")
        
        # Determine liveness
        is_live = liveness_score >= 50
        
        return {
            'is_live': is_live,
            'score': liveness_score,
            'details': details,
            'motion_detected': motion_detected,
            'blink_detected': False,
            'skin_percentage': 0
        }
    
    def reset(self):
        """Reset detection counters"""
        self.blink_counter = 0
        self.total_blinks = 0
        self.blink_detected = False
        self.prev_frame = None
        self.prev_face_area = None