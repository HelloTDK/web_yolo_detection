from ultralytics import YOLO

model = YOLO("xueshengxingwei_yolov8n.pt")

print(model.names)

print(model.names[0])