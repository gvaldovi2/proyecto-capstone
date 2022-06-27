import torch
import cv2
import numpy as np

# Leemos el modelo ya entrenado
model = torch.hub.load('ultralytics/yolov5', 'custom',
                       path='./model/carros.pt')

# Realizar la Videocaptura con la cámara 0
cap = cv2.VideoCapture(1)

# Empezamos
while True:
    # Realizamos lectura de frames
    ret, frame = cap.read()

    # Podemos hacer corrección de color
    #frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Se realiza las detecciones sobre cada frame
    detect = model(frame)

    info = detect.pandas().xyxy[0]  # im1 predictions
    #info = detect.pandas().xyxy[0].to_json(orient="records")  # JSON img1 predictions
    print(info)
    print(len(info))

    # Mostramos FPS
    cv2.imshow('Detector de Carros', np.squeeze(detect.render()))    

    # Leemos el teclado
    t = cv2.waitKey(5)
    if t == 27:
        break

cap.release()
cv2.destroyAllWindows()

