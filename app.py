from flask import Flask, request, jsonify, render_template, send_from_directory
import json
import re
import requests  # Import the requests library
from langdetect import detect, LangDetectException
import os

app = Flask(__name__)

# Load the dataset (ensure dataset.json is in the same directory as your app.py)
try:
    with open('dataset.json', 'r', encoding='utf-8') as file:
        dataset = json.load(file)['dataset']  # Access the 'dataset' list directly
except FileNotFoundError:
    print("Error: dataset.json not found.  Make sure it's in the same directory as app.py.")
    exit()  # Exit the application if the dataset isn't found
except json.JSONDecodeError:
    print("Error: Invalid JSON format in dataset.json.")
    exit()

UPLOAD_FOLDER = 'templates'  # Define the upload folder
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx'} # Allowed file types

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True) # Create the uploads directory if it doesn't exist

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/templates', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        filename = file.filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return jsonify({'message': f'File {filename} uploaded successfully'}), 200
    else:
         return jsonify({'error': 'File type not allowed'}), 400

@app.route('/templates/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def detect_language(text):
    try:
        lang = detect(text)
        if lang == 'fr':
             return 'fr'
        elif lang == 'en' :
             return 'en'
        else:
            return 'fr'  # Default to French if detection fails or another language

    except LangDetectException:
        return 'fr'


def ask_ollama(prompt, model="llama3", lang="fr"): # Consistent model name
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,  # Use a consistent model name (llama2 is a good default)
        "prompt": prompt,
        "stream": False
    }
    try:
        response = requests.post(url, json=payload, timeout=60)  # Add a timeout
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        return response.json()["response"]
    except requests.exceptions.RequestException as e:
        print(f"Error communicating with Ollama: {e}") # Print errors for debugging
        return "Error: Could not generate a response from Ollama."  # Return a user-friendly error message



def find_answer(question, lang="fr"):
    question_lower = question.lower()
    best_match = None
    max_score = 0

    for item in dataset:

        question_tokens = set(re.findall(r'\w+', item['question'].lower()))
        user_tokens = set(re.findall(r'\w+', question_lower))
        score = len(question_tokens.intersection(user_tokens))



        if score > max_score:
            max_score = score
            best_match = item

    if best_match:
        if 'file' in best_match:  # Check if a file is associated
             filename = best_match['file'] # Get the filename if it exists
             file_path = f"/uploads/{filename}" # Construct the file URL
             return best_match['answer'] + f"<br><a href='{file_path}' target='_blank'>Télécharger le fichier</a>", best_match.get('link', None) #include file link

        return best_match['answer'], best_match.get('link', None)
    else:
        return None, None


@app.route('/')
def home():
    return render_template('index.html')  # Make sure index.html is in a 'templates' folder


@app.route('/api/chat', methods=['POST'])
def chat():
    user_input = request.json.get('question')

    if not user_input:
        return jsonify({"error": "No question provided"}), 400

    detected_lang = detect_language(user_input)  # Detect language
    print("Detected Language:", detected_lang)


    answer, link = find_answer(user_input, lang=detected_lang) # Use detected language

    if answer:
        response = {"response": answer, "link": link}
    else:
        prompt = f"L'utilisateur a posé la question suivante : {user_input}.  Réponds en {detected_lang}."
        print("Prompt sent to Ollama:", prompt)
        ollama_response = ask_ollama(prompt, lang=detected_lang)
        response = {"response": ollama_response, "link": None}

    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True)