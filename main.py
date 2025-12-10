import os
import io
import tempfile
from flask import Flask, request, send_file
import pikepdf

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            return 'No file uploaded', 400
        
        file = request.files['file']
        if file.filename == '':
            return 'No file selected', 400
            
        if file and file.filename.lower().endswith('.pdf'):
            # Create a temporary file to save the upload
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_input:
                file.save(temp_input.name)
                temp_input_path = temp_input.name
            
            try:
                # Process the PDF
                pdf = pikepdf.open(temp_input_path, allow_overwriting_input=True)
                
                # Save to memory buffer
                output_buffer = io.BytesIO()
                pdf.save(output_buffer)
                pdf.close()
                
                output_buffer.seek(0)
                
                return send_file(
                    output_buffer, 
                    as_attachment=True, 
                    download_name=f"processed_{file.filename}",
                    mimetype='application/pdf'
                )
            except Exception as e:
                return f"Error processing PDF: {str(e)}", 500
            finally:
                # Clean up the temp file
                if os.path.exists(temp_input_path):
                    os.remove(temp_input_path)
                
    return '''
    <!doctype html>
    <title>PDF Processor</title>
    <h1>Upload a PDF to process</h1>
    <form method=post enctype=multipart/form-data>
      <input type=file name=file accept=".pdf">
      <input type=submit value="Upload and Process">
    </form>
    '''

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
