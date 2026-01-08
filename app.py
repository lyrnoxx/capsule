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
    temp_dir_path = os.path.normpath(os.path.abspath(temp_dir_path))
    command = [
        '/usr/bin/docker', 'run', '--rm',
        '-v', f'{temp_dir_path}:/data',
        'map2dfusion', 'DataPath=/data',
        'Win3D.Enable=0', 'ShouldStop=1',
        'Map.File2Save=/data/output.png'
    ]

    print(f"INFO: Executing Docker Command: {' '.join(command)}")

    try:
        print(f"Contents of {temp_dir_path}:", os.listdir(temp_dir_path))
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=180)
        print("Docker STDOUT:\n", result.stdout)
        print("Docker STDERR:\n", result.stderr)
        return True, "Docker processing completed."

    except subprocess.CalledProcessError as e:
        print(f"ERROR: Docker failed!\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}")
        return False, f"Docker failed: {e.stderr}"
    except Exception as e:
        print(f"UNEXPECTED ERROR: {e}")
        return False, str(e)

@app.route('/drone/stitch', methods=['GET', 'POST'])
def drone_stitch():
    if request.method == 'POST':

        base_temp = '/var/www/tmp'
        os.makedirs(base_temp, exist_ok=True)
        temp_dir = tempfile.mkdtemp(dir=base_temp)
        os.chmod(temp_dir, 0o777)
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
                final_image_url = url_for('static', filename=f"outputs/{final_map_filename}", _external=True)
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

        # except Exception as e:
        #     print(f"PROCESSING ERROR: {e}")
        #     # Differentiate error types
        #     status_code = 400 if isinstance(e, ValueError) else 500
        #     return jsonify({'success': False, 'error': str(e)}), status_code
        
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print("FULL TRACEBACK:\n", error_trace)
            status_code = 400 if isinstance(e, ValueError) else 500
            return jsonify({'success': False, 'error': str(e), 'trace': error_trace}), status_code

            
        finally:
            cleanup_temp_dir(temp_dir)
            
    
    return render_template('project_drone-stitch.html')


@app.route('/drone/recent-works')
def recentworks():
    return render_template('awd.html')

@app.route('/talks')
def talks():
    return render_template('project_talks.html')

@app.route('/vision')
def vision():
    return render_template('project_vision.html')

@app.route('/graphics')
def graphics():
    return render_template('graphics.html')


@app.route('/nlp')
def nlp():
    return render_template('project_nlp.html')

# @app.route('/detect', methods=['POST'])
# def detect():
#     if 'file' not in request.files:
#         return jsonify({'error': 'No file uploaded'}), 400

#     file = request.files['file']
#     if file.filename == '':
#         return jsonify({'error': 'No selected file'}), 400

#     # Save uploaded file temporarily
#     with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
#         file.save(tmp.name)
#         image_path = tmp.name

#     try:
#         # Get absolute paths
#         project_root = os.path.dirname(os.path.abspath(__file__))
#         dino_script = os.path.join(project_root, "p2p", "dino_inference.py")

#         if not os.path.exists(dino_script):
#             return jsonify({'result': f"Error: dino_inference.py not found at {dino_script}"}), 500

#         # Run inference using conda environment
#         command = f'conda run -n dino_env python "{dino_script}" "{image_path}"'

#         result = subprocess.run(
#             command,
#             shell=True,
#             capture_output=True,
#             text=True
#         )

#         if result.returncode != 0:
#             output_text = f"Error: {result.stderr.strip()}"
#         else:
#             output_text = result.stdout.strip()

#     except Exception as e:
#         output_text = f"Exception: {str(e)}"

#     finally:
#         if os.path.exists(image_path):
#             os.remove(image_path)

#     return jsonify({'result': output_text})


if __name__=='__main__':
    app.run(debug=True)