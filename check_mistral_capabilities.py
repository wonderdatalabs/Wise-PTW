import requests
import json
from app import MISTRAL_API_KEY

def check_mistral_vision_capabilities():
    """Check if Mistral has vision or document processing capabilities."""
    
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Get available models
    models_endpoint = "https://api.mistral.ai/v1/models"
    models_response = requests.get(models_endpoint, headers=headers)
    
    if models_response.status_code == 200:
        models = models_response.json()
        vision_models = []
        
        # Check if any models have vision capabilities
        if "data" in models:
            for model in models["data"]:
                if "capabilities" in model and "vision" in model["capabilities"]:
                    if model["capabilities"]["vision"]:
                        vision_models.append(model["id"])
        
        print(f"Models with vision capabilities: {vision_models}")
        
        # If vision models are found, try to use them
        if vision_models:
            model_to_test = vision_models[0]
            print(f"\nTesting vision capabilities with model: {model_to_test}")
            
            # Send a chat completion request with vision instructions
            chat_endpoint = "https://api.mistral.ai/v1/chat/completions"
            data = {
                "model": model_to_test,
                "messages": [
                    {
                        "role": "user", 
                        "content": "How do I use the vision or document processing features of the Mistral API? Please provide detailed examples."
                    }
                ]
            }
            
            chat_response = requests.post(chat_endpoint, headers=headers, json=data)
            
            if chat_response.status_code == 200:
                result = chat_response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    vision_info = result["choices"][0].get("message", {}).get("content", "No content found")
                    print("\nInformation about vision capabilities:")
                    print(vision_info)
            else:
                print(f"Error: {chat_response.status_code} - {chat_response.text}")
        else:
            print("\nNo models with vision capabilities found. Testing with mistral-large-latest.")
            
            # Try asking the most capable model about vision capabilities
            chat_endpoint = "https://api.mistral.ai/v1/chat/completions"
            data = {
                "model": "mistral-large-latest",
                "messages": [
                    {
                        "role": "user", 
                        "content": "Does the Mistral API support OCR or document processing? If so, what is the exact API endpoint I should use for OCR or document processing? Please provide detailed examples."
                    }
                ],
                "temperature": 0
            }
            
            chat_response = requests.post(chat_endpoint, headers=headers, json=data)
            
            if chat_response.status_code == 200:
                result = chat_response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    vision_info = result["choices"][0].get("message", {}).get("content", "No content found")
                    print("\nInformation about OCR/document capabilities:")
                    print(vision_info)
            else:
                print(f"Error: {chat_response.status_code} - {chat_response.text}")
    else:
        print(f"Error fetching models: {models_response.status_code} - {models_response.text}")

if __name__ == "__main__":
    check_mistral_vision_capabilities()