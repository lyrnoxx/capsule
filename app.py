from flask import Flask, render_template, request, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
import os
from PIL import Image
import uuid
import tempfile
import shutil
import time
import subprocess


app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads'
OUTPUT_FOLDER = 'static/outputs'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

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

            output_filename = f"{uuid.uuid4()}.png"
            output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)

            return render_template('project_autoencoder.html', 
                                input_image='uploads/'+os.path.basename(filepath),
                                output_image='outputs/'+os.path.basename(output_path))
    return render_template('project_autoencoder.html')

@app.route('/drone')
def drone():
    return render_template('project_drone.html')

@app.route('/drone/system')
def drone_system():
    return render_template('project_drone-system.html')


OUTPUT_MAP_PATH = '/static/maps/stitched_map.png' 

def cleanup_temp_dir(dir_path):
    if os.path.exists(dir_path):
        try:
            shutil.rmtree(dir_path)
            print(f"SUCCESS: Deleted temporary directory: {dir_path}")
        except Exception as e:
            print(f"ERROR: Failed to delete temporary directory {dir_path}: {e}")

def run_docker_command(temp_dir_path):
    command = [
        'docker', 'run', '--rm',
        '-v', f'root/{temp_dir_path}/:/data',
        'map2dfusion', 'DataPath=/data',
        'Win3D.Enable=0', 'ShouldStop=1',
        'Map.File2Save=/data/output.png'
    ]

    
    print(f"INFO: Simulating Docker Command: {' '.join(command)}")
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        print(f"Docker Output:\n{result.stdout}")
        
        output_file_path = os.path.join(temp_dir_path, 'output.png')
            
        print("SUCCESS: Docker execution simulated and output created.")
        return True, "Processing successful."

    except subprocess.CalledProcessError as e:
        return False, f"Docker command failed: {e.stderr}"
    except Exception as e:
        return False, f"An unexpected error occurred during Docker execution: {e}"


@app.route('/drone/stitch', methods=['GET', 'POST'])
def drone_stitch():
    if request.method == 'POST':
        temp_dir = tempfile.mkdtemp()
        rgb_dir = os.path.join(temp_dir, 'rgb')
        os.makedirs(rgb_dir, exist_ok=True)
        
        try:
            # width = request.form.get('width')
            # height = request.form.get('height')

            trajectory_file = request.files.get('trajectory')
            config_file = request.files.get('config')  

            image_files = request.files.getlist('images')

            if not trajectory_file or not image_files or not config_file:
                raise ValueError("Missing trajectory file or config file or image folder files.")

            trajectory_file.save(os.path.join(temp_dir, 'trajectory.txt'))
            print(f"INFO: Saved trajectory.txt to {temp_dir}")

            config_file.save(os.path.join(temp_dir, 'config.cfg'))
            print(f"INFO: Saved config.cfg to {temp_dir}")

            # Save Image Files (must be in 'rgb' subdirectory)
            for file in image_files:
                if file.filename:
                    # Use only the base filename to save into the flat 'rgb' directory
                    base_filename = os.path.basename(file.filename)
                    file.save(os.path.join(rgb_dir, base_filename))
            print(f"INFO: Saved {len(image_files)} image files to {rgb_dir}")
            
            # config_content = f"""
            # WIDTH={width}
            # HEIGHT={height}
            # INPUT_DIR=rgb
            # TRAJECTORY_FILE=trajectory.txt
            # OUTPUT_MAP_NAME=stitched_map.png
            # """
            # with open(os.path.join(temp_dir, 'config.cfg'), 'w') as f:
            #     f.write(config_content)
            # print("INFO: Created config.cfg placeholder file.")

            success, message = run_docker_command(temp_dir)

            if not success:
                return jsonify({'success': False, 'error': message}), 500

            # 6. Serve Result
            # SIMULATION: Assuming the Docker command successfully created the map 
            # named 'stitched_map.png' in the temp_dir. 
            
            # In a real app, you would move this file to a permanent static location 
            # and return the URL to that permanent location. 
            # For simulation, we return a placeholder URL based on the parameters.
            
            #simulated_image_url = f"https://placehold.co/{width}x{height}/10b981/ffffff?text=Map+ID:{os.path.basename(temp_dir)}"
            #result_image_url = 

            return jsonify({
                'success': True, 
                'imageUrl': "nah",
                'message': 'Stitching complete. Files deleted.'
            }), 200

        except Exception as e:
            print(f"PROCESSING ERROR: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
            
        # finally:
        #     cleanup_temp_dir(temp_dir)
    
    return render_template('project_drone-stitch.html')


if __name__=='__main__':
    app.run(debug=True)