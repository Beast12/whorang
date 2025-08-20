"""Face recognition module for the doorbell addon."""

import cv2
import face_recognition
import numpy as np
import os
from typing import List, Tuple, Optional, Dict
from datetime import datetime
import threading
import time
from PIL import Image

from .database import db, Person, FaceEncoding
from .config import settings


class FaceRecognitionManager:
    """Manages face recognition operations."""
    
    def __init__(self):
        self.known_face_encodings: List[np.ndarray] = []
        self.known_face_names: List[str] = []
        self.known_face_ids: List[int] = []
        self.face_locations = []
        self.face_encodings = []
        self.face_names = []
        self.process_this_frame = True
        
        # Load known faces from database
        self.load_known_faces()
    
    def load_known_faces(self):
        """Load known face encodings from the database."""
        self.known_face_encodings = []
        self.known_face_names = []
        self.known_face_ids = []
        
        # Get all face encodings from database
        face_encodings = db.get_face_encodings()
        
        for face_encoding in face_encodings:
            person = db.get_person(face_encoding.person_id)
            if person:
                self.known_face_encodings.append(face_encoding.encoding)
                self.known_face_names.append(person.name)
                self.known_face_ids.append(person.id)
        
        print(f"Loaded {len(self.known_face_encodings)} known face encodings")
    
    def detect_faces_in_image(self, image_path: str) -> List[Tuple[str, float, Tuple[int, int, int, int]]]:
        """
        Detect and recognize faces in an image.
        
        Returns:
            List of tuples: (name, confidence, face_location)
        """
        try:
            # Load image
            image = face_recognition.load_image_from_file(image_path)
            
            # Find face locations and encodings
            face_locations = face_recognition.face_locations(image)
            face_encodings = face_recognition.face_encodings(image, face_locations)
            
            results = []
            
            for face_encoding, face_location in zip(face_encodings, face_locations):
                # Check if face matches any known faces
                matches = face_recognition.compare_faces(
                    self.known_face_encodings, 
                    face_encoding,
                    tolerance=1.0 - settings.face_confidence_threshold
                )
                
                name = "Unknown"
                confidence = 0.0
                
                # If a match was found, use the first one
                if True in matches:
                    first_match_index = matches.index(True)
                    name = self.known_face_names[first_match_index]
                    
                    # Calculate confidence based on face distance
                    face_distances = face_recognition.face_distance(
                        [self.known_face_encodings[first_match_index]], 
                        face_encoding
                    )
                    confidence = 1.0 - face_distances[0]
                
                results.append((name, confidence, face_location))
            
            return results
            
        except Exception as e:
            print(f"Error detecting faces in {image_path}: {e}")
            return []
    
    def process_doorbell_image(self, image_path: str) -> Dict:
        """
        Process a doorbell image for face recognition.
        
        Returns:
            Dictionary with detection results
        """
        results = self.detect_faces_in_image(image_path)
        
        detected_faces = []
        known_person_id = None
        max_confidence = 0.0
        
        for name, confidence, location in results:
            face_info = {
                "name": name,
                "confidence": confidence,
                "location": location,
                "is_known": name != "Unknown"
            }
            detected_faces.append(face_info)
            
            # Track the most confident known face
            if name != "Unknown" and confidence > max_confidence:
                max_confidence = confidence
                # Find person ID
                for i, known_name in enumerate(self.known_face_names):
                    if known_name == name:
                        known_person_id = self.known_face_ids[i]
                        break
        
        # Save event to database
        event = db.add_doorbell_event(
            image_path=image_path,
            person_id=known_person_id,
            confidence=max_confidence if known_person_id else None
        )
        
        result = {
            "event_id": event.id,
            "timestamp": event.timestamp,
            "faces_detected": len(detected_faces),
            "known_faces": len([f for f in detected_faces if f["is_known"]]),
            "faces": detected_faces,
            "primary_person_id": known_person_id,
            "primary_confidence": max_confidence
        }
        
        # Notify Home Assistant integration
        try:
            from .ha_integration import ha_integration
            import asyncio
            asyncio.create_task(ha_integration.handle_face_detected(result))
        except Exception as e:
            print(f"Error notifying Home Assistant: {e}")
        
        return result
    
    def add_face_for_person(self, image_path: str, person_name: str, 
                           face_location: Optional[Tuple[int, int, int, int]] = None) -> bool:
        """
        Add a face encoding for a person from an image.
        
        Args:
            image_path: Path to the image file
            person_name: Name of the person
            face_location: Optional specific face location to use
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get or create person
            persons = db.get_all_persons()
            person = None
            for p in persons:
                if p.name == person_name:
                    person = p
                    break
            
            if not person:
                person = db.add_person(person_name)
            
            # Load image and extract face encoding
            image = face_recognition.load_image_from_file(image_path)
            
            if face_location:
                # Use specific face location
                face_encodings = face_recognition.face_encodings(image, [face_location])
            else:
                # Find all faces and use the first one
                face_locations = face_recognition.face_locations(image)
                if not face_locations:
                    print(f"No faces found in {image_path}")
                    return False
                face_encodings = face_recognition.face_encodings(image, face_locations)
            
            if not face_encodings:
                print(f"Could not extract face encoding from {image_path}")
                return False
            
            # Add face encoding to database
            face_encoding = face_encodings[0]
            db.add_face_encoding(person.id, face_encoding)
            
            # Reload known faces
            self.load_known_faces()
            
            print(f"Added face encoding for {person_name}")
            return True
            
        except Exception as e:
            print(f"Error adding face for {person_name}: {e}")
            return False
    
    def create_face_thumbnail(self, image_path: str, face_location: Tuple[int, int, int, int], 
                             output_path: str, size: Tuple[int, int] = (150, 150)) -> bool:
        """
        Create a thumbnail of a detected face.
        
        Args:
            image_path: Path to the original image
            face_location: Face location (top, right, bottom, left)
            output_path: Path to save the thumbnail
            size: Thumbnail size
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Load image with PIL
            image = Image.open(image_path)
            
            # Extract face region
            top, right, bottom, left = face_location
            face_image = image.crop((left, top, right, bottom))
            
            # Resize to thumbnail size
            face_image = face_image.resize(size, Image.Resampling.LANCZOS)
            
            # Save thumbnail
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            face_image.save(output_path)
            
            return True
            
        except Exception as e:
            print(f"Error creating face thumbnail: {e}")
            return False
    
    def get_face_similarity(self, encoding1: np.ndarray, encoding2: np.ndarray) -> float:
        """
        Calculate similarity between two face encodings.
        
        Returns:
            Similarity score (0.0 to 1.0, higher is more similar)
        """
        distance = face_recognition.face_distance([encoding1], encoding2)[0]
        return 1.0 - distance


class CameraManager:
    """Manages camera capture and processing."""
    
    def __init__(self, face_manager: FaceRecognitionManager):
        self.face_manager = face_manager
        self.camera_url = settings.camera_url
        self.is_running = False
        self.capture_thread = None
        self.last_capture_time = 0
        self.capture_interval = 5  # seconds between captures
    
    def start_monitoring(self):
        """Start camera monitoring in a separate thread."""
        if self.is_running:
            return
        
        self.is_running = True
        self.capture_thread = threading.Thread(target=self._monitor_camera)
        self.capture_thread.daemon = True
        self.capture_thread.start()
        print("Camera monitoring started")
    
    def stop_monitoring(self):
        """Stop camera monitoring."""
        self.is_running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=5)
        print("Camera monitoring stopped")
    
    def _monitor_camera(self):
        """Monitor camera feed for motion/doorbell events."""
        cap = None
        
        try:
            # Initialize video capture
            cap = cv2.VideoCapture(self.camera_url)
            if not cap.isOpened():
                print(f"Failed to open camera: {self.camera_url}")
                return
            
            print(f"Connected to camera: {self.camera_url}")
            
            while self.is_running:
                ret, frame = cap.read()
                if not ret:
                    print("Failed to read frame from camera")
                    time.sleep(1)
                    continue
                
                current_time = time.time()
                
                # Capture frame at intervals
                if current_time - self.last_capture_time >= self.capture_interval:
                    self._process_frame(frame)
                    self.last_capture_time = current_time
                
                time.sleep(0.1)  # Small delay to prevent excessive CPU usage
                
        except Exception as e:
            print(f"Camera monitoring error: {e}")
        finally:
            if cap:
                cap.release()
    
    def _process_frame(self, frame):
        """Process a camera frame for face detection."""
        try:
            # Save frame to disk
            timestamp = datetime.now()
            filename = f"doorbell_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
            image_path = os.path.join(settings.images_path, filename)
            
            os.makedirs(settings.images_path, exist_ok=True)
            cv2.imwrite(image_path, frame)
            
            # Process for face recognition
            results = self.face_manager.process_doorbell_image(image_path)
            
            if results["faces_detected"] > 0:
                print(f"Detected {results['faces_detected']} face(s) at {timestamp}")
                
                # Create face thumbnails
                for i, face in enumerate(results["faces"]):
                    thumbnail_filename = f"face_{timestamp.strftime('%Y%m%d_%H%M%S')}_{i}.jpg"
                    thumbnail_path = os.path.join(settings.faces_path, thumbnail_filename)
                    
                    self.face_manager.create_face_thumbnail(
                        image_path, 
                        face["location"], 
                        thumbnail_path
                    )
            
        except Exception as e:
            print(f"Error processing frame: {e}")
    
    def capture_single_frame(self) -> Optional[str]:
        """Capture a single frame from the camera."""
        cap = None
        try:
            cap = cv2.VideoCapture(self.camera_url)
            if not cap.isOpened():
                return None
            
            ret, frame = cap.read()
            if not ret:
                return None
            
            # Save frame
            timestamp = datetime.now()
            filename = f"manual_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
            image_path = os.path.join(settings.images_path, filename)
            
            os.makedirs(settings.images_path, exist_ok=True)
            cv2.imwrite(image_path, frame)
            
            return image_path
            
        except Exception as e:
            print(f"Error capturing frame: {e}")
            return None
        finally:
            if cap:
                cap.release()


# Global instances
face_manager = FaceRecognitionManager()
camera_manager = CameraManager(face_manager)
