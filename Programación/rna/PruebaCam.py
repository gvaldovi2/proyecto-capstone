
import cv2
import numpy as np
import time
import os

# Realizar la Videocaptura con la cámara 2
cam1 = cv2.VideoCapture(2)

# Empezamos
while True:

    os.system('cls')
    # Realizamos lectura de frames
    ret1, frame1 = cam1.read()
 # Mostramos FPS
    cv2.imshow('Detector de Carros Cámara 1', frame1)    

    # Leemos el tecladocd
    t = cv2.waitKey(5)
    if t == 27:
        break
    time.sleep(1)

cam1.release()
cv2.destroyAllWindows()
