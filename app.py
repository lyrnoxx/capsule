from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
import os
import torch
import torch.nn as nn
import torchvision.transforms as transforms
from PIL import Image
import uuid
from models.models import DenoisingAutoencoder


app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads'
OUTPUT_FOLDER = 'static/outputs'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

model = DenoisingAutoencoder()
model.load_state_dict(torch.load('models/autoencoder.pth', map_location='cpu'))
model.eval()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/reinforce')
def reinforce():
    return render_template('project_reinforce.html')

@app.route('/autoencoder', methods=['GET', 'POST'])
def autoencoder():
    if request.method == 'POST':
        file = request.files['image']
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            image = Image.open(filepath).convert('L').resize((28,28))
            transform = transforms.ToTensor()
            img_tensor = transform(image).unsqueeze(0)

            with torch.no_grad():
                output = model(img_tensor)
            output_img = transforms.ToPILImage()(output.squeeze(0))

            output_filename = f"{uuid.uuid4()}.png"
            output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
            output_img.save(output_path)

            return render_template('project_autoencoder.html', 
                                input_image='uploads/'+os.path.basename(filepath),
                                output_image='outputs/'+os.path.basename(output_path))
    return render_template('project_autoencoder.html')

if __name__=='__main__':
    app.run(debug=True)