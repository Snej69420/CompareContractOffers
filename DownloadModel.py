from sentence_transformers import SentenceTransformer
import os

# Create a folder called 'models' in your project root
os.makedirs("models", exist_ok=True)

print("Downloading model...")
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

# Save it locally
model.save('./models/paraphrase-multilingual-MiniLM-L12-v2')
print("Model saved locally!")