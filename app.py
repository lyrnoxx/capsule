import os
import shutil
import tempfile
import time
import subprocess
import uuid
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from PIL import Image
from werkzeug.exceptions import RequestEntityTooLarge

# --- FLASK SETUP ---
app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads'
OUTPUT_FOLDER = 'static/outputs'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

# FIX FOR 413 ERROR: Increase max upload size to 256 MB (256 * 1024 * 1024 bytes)
app.config['MAX_CONTENT_LENGTH'] = 256 * 1024 * 1024 

# --- ERROR HANDLER ---
# Explicitly handle the 413 Request Entity Too Large error.
@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    # This handler catches the error if Flask's internal limit is exceeded.
    print(f"ERROR: File upload exceeded limit: {e}")
    return jsonify({
        'success': False, 
        'error': f'File size exceeds the configured limit of 256MB in Flask.',
        'hint': 'The 413 error on smaller files (like 17MB) is typically set by the web server proxy upstream, not the Flask app itself.'
    }), 413


# --- UTILITIES ---

OUTPUT_MAP_PATH = '/static/maps/stitched_map.png' 

def cleanup_temp_dir(dir_path):
    """Deletes the temporary directory and all its contents."""
    if os.path.exists(dir_path):
        try:
            shutil.rmtree(dir_path)
            print(f"SUCCESS: Deleted temporary directory: {dir_path}")
        except Exception as e:
            print(f"ERROR: Failed to delete temporary directory {dir_path}: {e}")

def run_docker_command(temp_dir_path):
    """
    Executes the Docker map stitching command and provides detailed failure feedback.
    """
    
    # 0. Pre-check for Docker executable
    try:
        # Check if Docker is available and the service is running
        subprocess.run(['docker', 'info'], capture_output=True, check=True, timeout=5)
    except FileNotFoundError:
        return False, "CRITICAL ERROR: Docker command not found. Please verify that 'docker' is installed and in the system PATH."
    except subprocess.CalledProcessError as e:
        # Docker is found, but service might be down or permissions are wrong (e.g., non-root user issue).
        return False, (
            f"CRITICAL ERROR: Docker service check failed (Exit Code: {e.returncode}). "
            f"Is the Docker daemon running and accessible by the Flask user? "
            f"Check permissions (e.g., user in 'docker' group). Stderr: {e.stderr.strip()}"
        )
    except subprocess.TimeoutExpired:
        return False, "CRITICAL ERROR: Docker pre-check timed out."


    # Use absolute and normalized path for the volume mount host path.
    abs_temp_dir = os.path.normpath(os.path.abspath(temp_dir_path))

    # Reconstructing the full Docker command array
    command = [
        'docker', 'run', '--rm',
        # Volume mount: [HOST_PATH]:[CONTAINER_PATH]
        '-v', f'{abs_temp_dir}:/data',
        'map2dfusion', 'DataPath=/data',
        'Win3D.Enable=0', 'ShouldStop=1',
        'Map.File2Save=/data/output.png'
    ]

    command_str = ' '.join(command)
    print(f"INFO: Executing Docker Command: {command_str}")
    
    try:
        # Execute the command, checking for a zero exit code
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=120)
        print(f"Docker Output (stdout):\n{result.stdout}")
        
        print("SUCCESS: Docker execution finished.")
        return True, "Processing successful."

    except subprocess.CalledProcessError as e:
        # Handles non-zero exit code (failure inside the Docker container or process)
        error_msg = (
            f"DOCKER EXECUTION FAILED: Exit Code: {e.returncode}. "
            f"Check the output below for container errors. "
            f"Command Executed: {command_str}. "
            f"--- Container STDOUT ---\n{e.stdout.strip()}\n"
            f"--- Container STDERR ---\n{e.stderr.strip()}"
        )
        print(f"ERROR: {error_msg}")
        return False, error_msg

    except subprocess.TimeoutExpired:
        print("ERROR: Docker command timed out after 120 seconds.")
        return False, "Docker command timed out after 120 seconds. The process is taking too long."
    except Exception as e:
        # Handles other unexpected errors (e.g., OS errors, permission issues on volume mount)
        print(f"UNEXPECTED ERROR: {e}")
        return False, f"An unexpected error occurred during Docker execution. Error: {e}"

# --- ROUTES ---

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

            # Simplified simulation for autoencoder processing
            image = Image.open(filepath).convert('L').resize((28,28))

            output_filename = f"{uuid.uuid4()}.png"
            output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
            # In a real app, the processed image would be saved here.
            # image.save(output_path) 

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


@app.route('/drone/stitch', methods=['GET', 'POST'])
def drone_stitch():
    if request.method == 'POST':
        # Create a unique temporary directory for this request
        temp_dir = tempfile.mkdtemp()
        rgb_dir = os.path.join(temp_dir, 'rgb')
        os.makedirs(rgb_dir, exist_ok=True)
        
        try:
            # 1. Get files from request
            trajectory_file = request.files.get('trajectory')
            config_file = request.files.get('config') 
            image_files = request.files.getlist('images')

            if not trajectory_file or not image_files or not config_file:
                # This throws a ValueError, which is correctly caught and returned as 400
                raise ValueError("Missing trajectory file, config file, or image folder files.")

            # 2. Save Uploaded Files to Temp Directory Structure
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
            
            # 3. Run Docker Command (Real Execution)
            success, message = run_docker_command(temp_dir)

            if not success:
                # Returns 500 if execution fails
                return jsonify({'success': False, 'error': message}), 500
            
            # 4. Handle Output File and Serve Result
            source_file_name = 'output.png'
            source_path = os.path.join(temp_dir, source_file_name)
            
            # Create a unique filename for the final map
            final_map_filename = f"map_{uuid.uuid4()}.png"
            destination_path = os.path.join(app.config['OUTPUT_FOLDER'], final_map_filename)
            
            # Check if the Docker process successfully created the file
            if os.path.exists(source_path):
                # Move the file to the permanent static output folder
                shutil.move(source_path, destination_path)
                
                # Construct the public URL, relative to the static folder (static/outputs/...)
                final_image_url = f"outputs/{final_map_filename}"
                print(f"SUCCESS: Moved output file to {final_image_url}")
            else:
                # Docker succeeded but didn't produce the expected file
                print("ERROR: Docker command finished successfully but output.png was not found in the volume mount.")
                return jsonify({
                    'success': False, 
                    'error': 'Docker process finished, but the output file (output.png) was not found in the expected location. This often means the internal stitching process failed silently.'
                }), 500
                
            # 5. Return success with the real image URL
            return jsonify({
                'success': True, 
                'imageUrl': final_image_url,
                'message': 'Stitching complete. Map saved.'
            }), 200

        except Exception as e:
            print(f"PROCESSING ERROR: {e}")
            # Differentiate error types
            status_code = 400 if isinstance(e, ValueError) else 500
            # Include the exception message in the response for better debugging
            return jsonify({'success': False, 'error': f'An application error occurred: {str(e)}'}), status_code
            
        finally:
            # CRITICAL STEP: Cleanup the temporary directory regardless of success or failure
            cleanup_temp_dir(temp_dir)
    
    return render_template('project_drone-stitch.html')


if __name__=='__main__':
    # Ensure upload and output directories exist
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    app.run(debug=True)
