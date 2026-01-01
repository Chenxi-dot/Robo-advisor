import os
import requests
import json

# Qwen API config (env overrides)
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "ms-60c5577d-33b4-401f-ac7f-2479fdf4dfd5")
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://api-inference.modelscope.cn/v1/")
QWEN_MODEL = os.getenv("QWEN_MODEL", "Qwen/Qwen2.5-7B-Instruct")

def call_llm(prompt, system_prompt="You are a helpful assistant."):
    """
    Call the Qwen LLM API.
    """
    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": QWEN_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }
    
    try:
        # Adjust URL if needed. The provided base URL ends with /v1/, so we append chat/completions
        url = QWEN_BASE_URL.rstrip('/') + "/chat/completions"
        
        response = requests.post(url, headers=headers, json=data, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            else:
                return f"Error: No choices in response. {result}"
        else:
            return f"Error: API request failed with status code {response.status_code}. {response.text}"
            
    except Exception as e:
        return f"Error calling LLM: {str(e)}"
