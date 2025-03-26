import json
import cv2
import numpy as np
import os
import time
from channels.generic.websocket import AsyncWebsocketConsumer
from cvzone.HandTrackingModule import HandDetector

class VideoConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.presentation_path = ""
        self.current_slide_index = 0
        self.slide = None
        self.detector = HandDetector(detectionCon=0.8, maxHands=1)
        self.annotations = []  # Stores multiple drawings as separate lists
        self.last_gesture_time = time.time()
        self.gesture_cooldown = 1.0
        self.last_pointer_position = (640, 360)
        self.frame_width = 640
        self.frame_height = 480
        self.slide_width = 1280
        self.slide_height = 720
        self.pointer_active = False
        self.drawing_active = False
        self.text_visible = False 
        # Toggle text visibility

        # Green line position (y-coordinate)
        self.green_line_y = int(self.frame_height * 0.75)  # 75% from the top

        # Default gesture mappings
        self.default_gestures = {
            "next": [0, 0, 0, 0, 1],
            "previous": [1, 0, 0, 0, 0],
            "point": [0, 1, 0, 0, 0],
            "draw": [1, 1, 0, 0, 0],
            "undo": [0, 1, 1, 1, 0],
            "toggle_text": [0, 1, 1, 0, 1],
            "checkbox_values" :[1,1,0,0,0]
        }

    async def connect(self):
        session = self.scope.get("session", {})
        self.presentation_path = session.get("presentation_file", "")

        gesture_config = session.get("gesture_config", {})
        self.next_gesture = gesture_config.get("next", self.default_gestures["next"])
        self.previous_gesture = gesture_config.get("previous", self.default_gestures["previous"])
        self.point_gesture = gesture_config.get("point", self.default_gestures["point"])
        self.draw_gesture = gesture_config.get("draw", self.default_gestures["draw"])
        self.undo_gesture = gesture_config.get("undo", self.default_gestures["undo"])
        self.toggle_text_gesture = gesture_config.get("toggle_text", self.default_gestures["toggle_text"])
        self.camera = gesture_config.get("checkbox_values", self.default_gestures["checkbox_values"])

        await self.accept()
        print("WebSocket connected. Presentation Path:", self.presentation_path)
        await self.send_current_slide()

    async def disconnect(self, close_code):
        print("WebSocket disconnected.")

    async def receive(self, text_data=None, bytes_data=None):
        if bytes_data:
            np_data = np.frombuffer(bytes_data, dtype=np.uint8)
            if np_data.size == 0:
                return

            frame = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
            if frame is None:
                return

            frame = cv2.flip(frame, 1)

            # Draw the green line
            cv2.line(frame, (0, self.green_line_y), (self.frame_width, self.green_line_y), (0, 255, 0), 2)

            hands, frame = self.detector.findHands(frame, draw=True)

            if hands:
                # Check if the hand is above the green line
                hand_landmark = hands[0]['lmList'][0]  # Palm base landmark
                if hand_landmark[1] > self.green_line_y:
                    print("Hand detected below the green line. Ignoring gesture.")
                    return

                fingers = self.detector.fingersUp(hands[0])
                current_time = time.time()

                if current_time - self.last_gesture_time > self.gesture_cooldown:
                    if fingers == self.point_gesture:  # Move pointer
                        self.pointer_active = True
                        self.drawing_active = False

                    elif fingers == self.draw_gesture:  # Start new drawing
                        if not self.drawing_active:
                            self.drawing_active = True
                            self.annotations.append([])  # New drawing list

                    elif self.drawing_active:  # If drawing stops
                        self.drawing_active = False

                    elif fingers == self.undo_gesture:  # Undo last drawing
                        if self.annotations:
                            self.annotations.pop()
                            print("Undo last drawing")

                    elif fingers == self.toggle_text_gesture:  # Toggle text visibility
                        self.text_visible = not self.text_visible
                        print("Toggled text display")

                    else:
                        self.pointer_active = False

                    if fingers == self.next_gesture:  # Next slide
                        await self.next_slide()

                    elif fingers == self.previous_gesture:  # Previous slide
                        await self.previous_slide()

                    self.last_gesture_time = current_time

                lm = hands[0]['lmList'][8]  # Index fingertip

                # Calculate z-distance (depth) for dynamic scaling
                z_distance = abs(hands[0]['lmList'][0][2] - hands[0]['lmList'][8][2])  # Palm base to index tip

                # Adjust scaling factor to cover the entire slide
                scaling_factor_x = 3
                scaling_factor_y = 2

                # Map hand position to slide coordinates
                scaled_x = int(lm[0] * scaling_factor_x)
                scaled_y = int(lm[1] * scaling_factor_y)

                # Ensure the pointer stays within slide boundaries
                scaled_x = min(max(scaled_x, 0), self.slide_width - 1)
                scaled_y = min(max(scaled_y, 0), self.slide_height - 1)

                if self.drawing_active:
                    if not self.annotations[-1]:
                        self.annotations.append([])

                    current_drawing = self.annotations[-1]

                    if current_drawing:
                        cv2.line(self.slide, current_drawing[-1], (scaled_x, scaled_y), (0, 0, 255), 3)

                    current_drawing.append((scaled_x, scaled_y))

                self.last_pointer_position = (scaled_x, scaled_y)

            await self.send_current_slide(frame)

    async def send_current_slide(self, frame=None):
        slide_path = os.path.join(self.presentation_path, f"slide_{self.current_slide_index + 1}.png")
        if os.path.exists(slide_path):
            self.slide = cv2.imread(slide_path)
            
            self.slide = cv2.resize(self.slide, (self.slide_width, self.slide_height))

            if frame is not None and self.camera[0] == 1:
                frame_resized = cv2.resize(frame, (200, 150))
                camera_height, camera_width = frame_resized.shape[:2]
                # Positioning based on camera list values
                if self.camera[1] == 1:  # Top-left
                    self.slide[10:160, 10:210] = frame_resized
                elif self.camera[2] == 1:  # Top-right
                    self.slide[10:160, self.slide_width - 210:self.slide_width - 10] = frame_resized
                elif self.camera[3] == 1:  # Bottom-left
                    self.slide[self.slide_height - 160:self.slide_height - 10, 10:210] = frame_resized
                elif self.camera[4] == 1:  # Bottom-right (Fixed alignment here)
                    self.slide[self.slide_height - 10 - camera_height:self.slide_height - 10,
                            self.slide_width - 10 - camera_width:self.slide_width - 10] = frame_resized

            for drawing in self.annotations:
                for i in range(1, len(drawing)):
                    cv2.line(self.slide, drawing[i - 1], drawing[i], (0, 0, 255), 5)

            if self.pointer_active:
                cv2.circle(self.slide, self.last_pointer_position, 10, (0, 255, 0), -1)

            if self.text_visible:
                cv2.putText(self.slide, "NAMASKARAM", (self.slide_width // 2 - 100, self.slide_height // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 5, (0, 0, 255), 12, cv2.LINE_AA)

            _, encoded_slide = cv2.imencode('.png', self.slide)
            await self.send(bytes_data=encoded_slide.tobytes())

    async def next_slide(self):
        if self.current_slide_index + 1 < self.get_slide_count():
            self.current_slide_index += 1
            self.annotations.clear()
            await self.send_current_slide()

    async def previous_slide(self):
        if self.current_slide_index > 0:
            self.current_slide_index -= 1
            self.annotations.clear()
            await self.send_current_slide()

    def get_slide_count(self):
        return len([f for f in os.listdir(self.presentation_path) if f.endswith('.png')])