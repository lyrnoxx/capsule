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

app.config['MAX_CONTENT_LENGTH'] = 256 * 1024 * 1024 

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
        '-v', f'{temp_dir_path}:/data',
        'map2dfusion', 'DataPath=/data',
        'Win3D.Enable=0', 'ShouldStop=1',
        'Map.File2Save=/data/output.png'
    ]

    print(f"INFO: Executing Docker Command: {' '.join(command)}")
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=120)
        print(f"Docker Output (stdout):\n{result.stdout}")
        
        print("SUCCESS: Docker execution finished.")
        return True, "Processing successful."

    except subprocess.CalledProcessError as e:
        print(f"ERROR: Docker command failed. Stderr:\n{e.stderr}")
        return False, f"Docker command failed with exit code {e.returncode}. Stderr: {e.stderr}"
    except FileNotFoundError:
        print("ERROR: Docker command not found. Execution environment issue.")
        return False, "Docker command not found. Verify Docker installation and PATH environment variable."
    except subprocess.TimeoutExpired:
        print("ERROR: Docker command timed out after 120 seconds.")
        return False, "The map stitching process timed out after 120 seconds. It may require more resources."
    except Exception as e:
        print(f"UNEXPECTED ERROR: {e}")
        return False, f"An unexpected error occurred during Docker execution. Check volume mount permissions: {e}"

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
            

            source_file_name = 'output.png'
            source_path = os.path.join(temp_dir, source_file_name)
            
            final_map_filename = f"map_{uuid.uuid4()}.png"
            destination_path = os.path.join(app.config['OUTPUT_FOLDER'], final_map_filename)
            
            if os.path.exists(source_path):
                shutil.move(source_path, destination_path)
                
                final_image_url = f"outputs/{final_map_filename}"
                print(f"SUCCESS: Moved output file to {final_image_url}")
            else:
                print("ERROR: Docker command finished successfully but output.png was not found in the volume mount.")
                return jsonify({
                    'success': False, 
                    'error': 'Docker process finished, but the output file (output.png) was not found in the expected location.'
                }), 500

            return jsonify({
                'success': True, 
                'imageUrl': final_image_url,
                'message': 'Stitching complete. Map saved.'
            }), 200

        except Exception as e:
            print(f"PROCESSING ERROR: {e}")
            # Differentiate error types
            status_code = 400 if isinstance(e, ValueError) else 500
            return jsonify({'success': False, 'error': str(e)}), status_code
            
        # finally:
        #     cleanup_temp_dir(temp_dir)
            
    
    return render_template('project_drone-stitch.html')


if __name__=='__main__':
    app.run(debug=True)