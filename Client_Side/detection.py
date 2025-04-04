from PyQt5.QtWidgets import QMainWindow
from PyQt5.uic import loadUi
from PyQt5.QtCore import QThread, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QImage, QPixmap
import cv2
import numpy as np
import time
import requests
import serial.tools.list_ports

# Handles the YOLOv4 detection algorithm, saves detected frames and sends alert to the server-side application
class Detection(QThread):

    def __init__(self, token, location, receiver):
        super(Detection, self).__init__()    

        self.token = token
        self.location = location
        self.receiver = receiver
    
    changePixmap = pyqtSignal(QImage)
    def select_com_port(self):
        ports = serial.tools.list_ports.comports()
        portsList = []

        for one in ports:
            portsList.append(str(one))
            print(str(one))

        # Default COM port is 10
        com = 3

        for i in range(len(portsList)):
            if portsList[i].startswith("COM" + str(com)):
                return "COM" + str(com)

        return None

    # Runs the detection model, evaluates detections and draws boxes around detected objects
    def run(self):
        com_port = "COM3"
        if com_port is None:
            print("Invalid COM port selected.")
            return

        serialInst = serial.Serial()
        serialInst.baudrate = 9600
        serialInst.port = com_port
        serialInst.open()

        serialInst.write("OFF".encode('utf-8'))       
        # Loads Yolov4
        net = cv2.dnn.readNet("weights/yolov4.weights", "cfg/yolov4.cfg")
        classes = []

        # Loads object names
        with open("obj.names", "r") as f:
            classes = [line.strip() for line in f.readlines()]
        
        layer_names = net.getLayerNames()

        # Obtén las capas de salida no conectadas
        unconnected_out_layers = net.getUnconnectedOutLayers()
        
        # Verifica si es una lista de enteros
        output_layers = [layer_names[i - 1] for i in unconnected_out_layers]
        
        colors = np.random.uniform(0, 255, size=(len(classes), 3))

        font = cv2.FONT_HERSHEY_PLAIN
        starting_time = time.time() - 11

        self.running = True

        # Starts camera
        cap = cv2.VideoCapture(0)
        
        # Detection while loop
        while self.running:
            ret, frame = cap.read()
            if ret:

                height, width, channels = frame.shape

                # Running the detection model
                blob = cv2.dnn.blobFromImage(frame, 0.00392, (416, 416), (0, 0, 0), True, crop=False)
                net.setInput(blob)
                outs = net.forward(output_layers)

                # Evaluating detections
                class_ids = []
                confidences = []    
                boxes = []
                for out in outs:
                    for detection in out:
                        scores = detection[5:]
                        class_id = np.argmax(scores)
                        confidence = scores[class_id]

                        # If detection confidance is above 98% a weapon was detected
                        if confidence > 0.98:

                            # Calculating coordinates
                            center_x = int(detection[0] * width)
                            center_y = int(detection[1] * height)
                            w = int(detection[2] * width)
                            h = int(detection[3] * height)

                            # Rectangle coordinates
                            x = int(center_x - w / 2)
                            y = int(center_y - h / 2)

                            boxes.append([x, y, w, h])
                            confidences.append(float(confidence))
                            class_ids.append(class_id)

                            serialInst.write("ON".encode('utf-8'))
                    serialInst.write("OFF".encode('utf-8'))
                indexes = cv2.dnn.NMSBoxes(boxes, confidences, 0.8, 0.3)

                #Draw boxes around detected objects
                for i in range(len(boxes)):
                    serialInst.write("ON".encode('utf-8'))
                    if i in indexes:
                        x, y, w, h = boxes[i]
                        label = str(classes[class_ids[i]])
                        confidence = confidences[i]
                        color = (256, 0, 0)
                        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                        cv2.putText(frame, label + " {0:.1%}".format(confidence), (x, y - 20), font, 3, color, 3)

                        elapsed_time = starting_time - time.time()

                        #Save detected frame every 10 seconds
                        if elapsed_time <= -10:
                            starting_time = time.time()
                            self.save_detection(frame, boxes[i])
                
                # Showing final result
                serialInst.write("ON".encode('utf-8'))
                rgbImage = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                bytesPerLine = channels * width
                convertToQtFormat = QImage(rgbImage.data, width, height, bytesPerLine, QImage.Format_RGB888)
                p = convertToQtFormat.scaled(1180, 720, Qt.KeepAspectRatio)
                self.changePixmap.emit(p)

    # Saves detected frame as a .jpg within the saved_alert folder
    def save_detection(self, frame, box):
        x, y, w, h = box
        mask = np.zeros_like(frame)
        mask[y:y + h, x:x + w] = frame[y:y + h, x:x + w]
        blurred_frame = cv2.GaussianBlur(frame, (21, 21), 0)
        combined = np.where(mask != 0, frame, blurred_frame)
        cv2.imwrite("saved_frame/frame.jpg", combined)
        print('Imagen Guardada')
        

        self.post_detection()

    # Sends alert to the server
    def post_detection(self):
        try:
            url = 'https://server-side-deployment.onrender.com/api/images/'
            headers = {'Authorization': 'Token ' + self.token}
            files = {'image': open('saved_frame/frame.jpg', 'rb')}
            data = {'user_ID': self.token, 'location': self.location, 'alert_receiver': self.receiver}
            response = requests.post(url, files=files, headers=headers, data=data)

            # HTTP 200
            if response.ok:
                print('Alerta enviada al servidor')
            # Bad response
            else:
                print('No se puede enviar alerta al servidor')
                print(f'Código de respuesta: {response.status_code}')
        except FileNotFoundError as e:
            print('Archivo no encontrado:')
        except requests.exceptions.ConnectionError as e:
            print('Error de conexión:')
        except requests.exceptions.Timeout as e:
            print('La solicitud ha expirado:')
        except requests.exceptions.RequestException as e:
            print('Error en la solicitud:')
        except Exception as e:
            print('No se puede acceder al servidor:')
