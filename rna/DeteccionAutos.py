import torch
import cv2
import numpy as np
import time
import os

#Para MQTT
import paho.mqtt.client as mqtt
import time

# Leemos el modelo ya entrenado
model = torch.hub.load('ultralytics/yolov5', 'custom',
                       path='./model/carros.pt')



#mqttBroker = "mqtt.eclipseprojects.io"
client = mqtt.Client("Camaras Semaforo")
#client.connect(mqttBroker)
#client.connect(host='mqtt.eclipseprojects.io', port=1883)
client.connect(host='192.168.0.33', port=1883)


# Realizar la Videocaptura con la cámara 0
cam1 = cv2.VideoCapture(0)
cam2 = cv2.VideoCapture(2)

# Empezamos
while True:

    os.system('cls')
    # Realizamos lectura de frames
    ret1, frame1 = cam1.read()
    ret2, frame2 = cam2.read()

    # Podemos hacer corrección de color
    #frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Se realiza las detecciones sobre cada frame
    detect1 = model(frame1)
    detect2 = model(frame2)

    info1 = detect1.pandas().xyxy[0]  # im1 predictions
    # info = detect.pandas().xyxy[0].to_json(orient="records")  # JSON img1 predictions

    info2 = detect2.pandas().xyxy[0]  # im1 predictions

    #print(info1)
    #print(len(info1['confidence']))
    #print(info1['confidence'][0])
    #autosCam1 = str(len(info1))
    autosCam1 = 0
    for i in range(0,len(info1['confidence'])):
        if(info1['confidence'][i]>0.65):
            autosCam1 += 1

    #autosCam2 = str(len(info2))
    autosCam2 = 0
    for i in range(0,len(info2['confidence'])):
        if(info2['confidence'][i]>0.65):
            autosCam2 += 1
    
    print('Hay ' + str(autosCam1)+' Autos de la Camara 1')
    print('Hay ' + str(autosCam2)+' Autos de la Camara 2')

    #msg = (b'{0},{1}'.format(autosCam1, autosCam2))
    msg = '{0},{1}'.format(autosCam1, autosCam2)
    msg = msg.encode()    
    client.publish("codigoIoT/ProyectoCapstone/Cams", msg)  
    #client.publish("codigoIoT/ProyectoCapstone/Cam2", autosCam2)  
    print("Publicó " + str(autosCam1) + " al Topic codigoIoT/ProyectoCapstone/Cam1")
    print("Publicó " + str(autosCam2) + " al Topic codigoIoT/ProyectoCapstone/Cam2")

    # Mostramos FPS
    cv2.imshow('Detector de Carros Cámara 1', np.squeeze(detect1.render()))
    cv2.imshow('Detector de Carros Cámara 2', np.squeeze(detect2.render()))

    # Leemos el tecladocd
    t = cv2.waitKey(5)
    if t == 27:
        break
    #time.sleep(1)

cam1.release()
cam2.release()
cv2.destroyAllWindows()
