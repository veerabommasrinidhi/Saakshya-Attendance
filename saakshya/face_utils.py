import cv2
import numpy as np
import base64
import json
import os
import logging

logger = logging.getLogger(__name__)

class FaceRecognitionService:
    """Professional face recognition service using OpenCV"""
    
    def __init__(self):
        # Load OpenCV's face detector
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        # For face recognition, we'll use LBPH face recognizer
        self.face_recognizer = cv2.face.LBPHFaceRecognizer_create()
        self.face_data = {}
        self.face_labels = {}
        self.current_label = 0
        
    def encode_face(self, image_data):
        """Encode face from image data for storage"""
        try:
            # Convert image data to numpy array
            if isinstance(image_data, str):
                if image_data.startswith('data:image'):
                    image_data = image_data.split(',')[1]
                image_bytes = base64.b64decode(image_data)
                nparr = np.frombuffer(image_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            elif isinstance(image_data, bytes):
                nparr = np.frombuffer(image_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            else:
                img = image_data
            
            if img is None:
                return None, "Invalid image format", None
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Detect face
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(100, 100))
            
            if len(faces) == 0:
                return None, "No face detected in the image", None
            
            # Get the largest face
            largest_face = max(faces, key=lambda x: x[2] * x[3])
            x, y, w, h = largest_face
            
            # Extract face ROI
            face_roi = gray[y:y+h, x:x+w]
            
            # Resize to standard size
            face_roi = cv2.resize(face_roi, (200, 200))
            
            # Convert to base64 string for storage
            _, buffer = cv2.imencode('.jpg', face_roi)
            face_encoding = base64.b64encode(buffer).decode('utf-8')
            
            face_data = {
                'encoding': face_encoding,
                'box': [int(x), int(y), int(w), int(h)],
                'size': face_roi.shape
            }
            
            return json.dumps(face_data), "Face encoded successfully", face_data
            
        except Exception as e:
            logger.error(f"Face encoding error: {str(e)}")
            return None, f"Error encoding face: {str(e)}", None
    
    def compare_faces(self, known_encoding_json, frame):
        """Compare captured face with known encoding"""
        try:
            # Load known face data
            known_data = json.loads(known_encoding_json)
            known_face_base64 = known_data['encoding']
            
            # Decode known face
            known_face_bytes = base64.b64decode(known_face_base64)
            nparr = np.frombuffer(known_face_bytes, np.uint8)
            known_face = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
            
            # Convert frame to grayscale
            if isinstance(frame, np.ndarray):
                gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                return False, None, 0
            
            # Detect faces in current frame
            faces = self.face_cascade.detectMultiScale(gray_frame, 1.1, 5, minSize=(100, 100))
            
            if len(faces) == 0:
                return False, None, 0
            
            # Get the largest face
            largest_face = max(faces, key=lambda x: x[2] * x[3])
            x, y, w, h = largest_face
            
            # Extract face ROI
            current_face = gray_frame[y:y+h, x:x+w]
            current_face = cv2.resize(current_face, (200, 200))
            
            # Compare using histogram comparison
            # Calculate histogram similarity
            hist1 = cv2.calcHist([known_face], [0], None, [256], [0, 256])
            hist2 = cv2.calcHist([current_face], [0], None, [256], [0, 256])
            
            # Calculate correlation
            correlation = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
            
            # Convert to percentage (0-100)
            confidence = max(0, min(100, correlation * 100))
            
            # Threshold for face matching
            threshold = 70  # 70% confidence threshold
            is_match = confidence >= threshold
            
            return is_match, (x, y, w, h), round(confidence, 2)
            
        except Exception as e:
            logger.error(f"Face comparison error: {str(e)}")
            return False, None, 0
    
    def detect_faces(self, frame):
        """Detect all faces in frame"""
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(100, 100))
            return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]
        except Exception as e:
            logger.error(f"Face detection error: {str(e)}")
            return []
    
    def draw_face_box(self, frame, face, color=(0, 255, 0), confidence=None):
        """Draw rectangle around face with confidence"""
        try:
            x, y, w, h = face
            # Draw rectangle
            cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
            
            # Draw confidence if provided
            if confidence:
                label = f"{confidence:.1f}%"
                # Draw background for text
                font = cv2.FONT_HERSHEY_SIMPLEX
                (label_w, label_h), _ = cv2.getTextSize(label, font, 0.6, 2)
                cv2.rectangle(frame, (x, y - label_h - 5), (x + label_w, y), color, -1)
                cv2.putText(frame, label, (x, y - 5), font, 0.6, (0, 0, 0), 2)
            
            return frame
        except Exception as e:
            logger.error(f"Drawing error: {str(e)}")
            return frame
    
    def extract_face_histogram(self, face_roi):
        """Extract histogram features from face"""
        try:
            # Convert to grayscale
            if len(face_roi.shape) == 3:
                gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
            else:
                gray = face_roi
            
            # Resize to standard size
            gray = cv2.resize(gray, (200, 200))
            
            # Calculate histogram
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
            
            # Normalize histogram
            cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
            
            return hist.flatten()
            
        except Exception as e:
            logger.error(f"Histogram extraction error: {str(e)}")
            return None