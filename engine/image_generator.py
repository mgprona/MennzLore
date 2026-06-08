#!/usr/bin/env python3
"""
MennzLore Image Generator
=========================
Generates storyboard images for a project's production scenes using OpenRouter.
Requires OPENROUTER_API_KEY environment variable.
"""
import os
import sys
import json
import base64
import requests

# OpenRouter text-to-image models
MODELS = [
    {
        "id": "google/gemini-2.5-flash-image",
        "name": "Google: Gemini 2.5 Flash Image (Very Cheap)",
        "pricing": "Prompt: $0.30/M tokens | Completion: $2.50/M tokens"
    },
    {
        "id": "google/gemini-3.1-flash-image-preview",
        "name": "Google: Gemini 3.1 Flash Image Preview (Cheap)",
        "pricing": "Prompt: $0.50/M tokens | Completion: $3.00/M tokens"
    },
    {
        "id": "openai/gpt-5-image-mini",
        "name": "OpenAI: GPT-5 Image Mini (Medium)",
        "pricing": "Prompt: $2.50/M tokens | Completion: $2.00/M tokens"
    },
    {
        "id": "google/gemini-3-pro-image-preview",
        "name": "Google: Gemini 3 Pro Image Preview (High Quality)",
        "pricing": "Prompt: $2.00/M tokens | Completion: $12.00/M tokens"
    },
    {
        "id": "openai/gpt-5-image",
        "name": "OpenAI: GPT-5 Image (High Quality / DALL-E 3)",
        "pricing": "Prompt: $10.00/M tokens | Completion: $10.00/M tokens"
    },
    {
        "id": "openai/gpt-5.4-image-2",
        "name": "OpenAI: GPT-5.4 Image 2 (Premium)",
        "pricing": "Prompt: $8.00/M tokens | Completion: $15.00/M tokens"
    }
]

def generate_image_openrouter(api_key, model_id, prompt_text):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    body = {
        "model": model_id,
        "messages": [
            {
                "role": "user",
                "content": f"Generate a cinematic, high-quality, atmospheric storyboard illustration for the following scene: {prompt_text}"
            }
        ],
        "modalities": ["image", "text"]
    }
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=body,
            timeout=60
        )
        if response.status_code != 200:
            return {"status": "error", "message": f"API Error {response.status_code}: {response.text}"}
            
        res_json = response.json()
        choices = res_json.get("choices", [])
        if not choices:
            return {"status": "error", "message": f"No choices in response: {json.dumps(res_json)}"}
            
        message = choices[0].get("message", {})
        images = message.get("images", [])
        if not images:
            content = message.get("content", "")
            return {"status": "error", "message": f"No image returned. Content: {content}"}
            
        img_url = images[0].get("image_url", {}).get("url", "")
        if not img_url:
            return {"status": "error", "message": "Image URL is empty."}
            
        return {"status": "ok", "url": img_url}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def save_image(img_data_or_url, dest_path):
    try:
        if img_data_or_url.startswith("data:image/"):
            header, base64_str = img_data_or_url.split(",", 1)
            img_bytes = base64.b64decode(base64_str)
            with open(dest_path, "wb") as f:
                f.write(img_bytes)
            return True
        else:
            img_res = requests.get(img_data_or_url, timeout=30)
            if img_res.status_code == 200:
                with open(dest_path, "wb") as f:
                    f.write(img_res.content)
                return True
            return False
    except Exception as e:
        print(f"Error saving image: {e}")
        return False

def generate_storyboard(project_dir, prefix, approved_scenes=None, model_id="google/gemini-2.5-flash-image"):
    """API entry point for headless execution (MCP)."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return {"status": "error", "message": "OPENROUTER_API_KEY environment variable not set."}
        
    prompts_path = os.path.join(project_dir, "output", "production", "scene_image_prompts.json")
    if not os.path.exists(prompts_path):
        return {"status": "error", "message": "scene_image_prompts.json not found. Run production render first."}
        
    with open(prompts_path, "r", encoding="utf-8") as f:
        prompts_list = json.load(f)
        
    if approved_scenes is None:
        approved_scenes = []
        
    storyboard_dir = os.path.join(project_dir, "output", "production", "storyboard")
    os.makedirs(storyboard_dir, exist_ok=True)
    
    results = []
    generated = 0
    skipped = 0
    
    for prompt_item in prompts_list:
        scene_id = prompt_item.get("scene_id")
        image_prompt = prompt_item.get("image_prompt", "")
        
        dest_filename = f"{prefix}_{scene_id}.png"
        dest_path = os.path.join(storyboard_dir, dest_filename)
        
        if os.path.exists(dest_path):
            results.append({"scene_id": scene_id, "status": "exists", "path": dest_filename})
            skipped += 1
            continue
            
        if scene_id not in approved_scenes:
            results.append({"scene_id": scene_id, "status": "skipped_not_approved", "path": None})
            skipped += 1
            continue
            
        # Call API
        res = generate_image_openrouter(api_key, model_id, image_prompt)
        if res["status"] == "ok":
            if save_image(res["url"], dest_path):
                results.append({"scene_id": scene_id, "status": "generated", "path": dest_filename})
                generated += 1
            else:
                results.append({"scene_id": scene_id, "status": "failed_save", "path": None})
        else:
            results.append({"scene_id": scene_id, "status": "failed_api", "message": res["message"]})
            
    return {
        "status": "ok",
        "generated_count": generated,
        "skipped_count": skipped,
        "results": results
    }

def main():
    if len(sys.argv) < 3:
        print("Usage: python image_generator.py <project_dir> <prefix>")
        sys.exit(1)
        
    project_dir = sys.argv[1]
    prefix = sys.argv[2]
    
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("[ERROR] OPENROUTER_API_KEY environment variable not found.")
        sys.exit(1)
        
    prompts_path = os.path.join(project_dir, "output", "production", "scene_image_prompts.json")
    if not os.path.exists(prompts_path):
        print(f"[ERROR] scene_image_prompts.json not found at: {prompts_path}")
        sys.exit(1)
        
    with open(prompts_path, "r", encoding="utf-8") as f:
        prompts_list = json.load(f)
        
    print(f"\nLoaded {len(prompts_list)} scene image prompts.")
    
    # Model selection menu
    print("\nSelect an OpenRouter image model to use:")
    for idx, m in enumerate(MODELS):
        print(f"  [{idx + 1}] {m['name']} ({m['pricing']})")
        
    choice = input("\nEnter choice [1-6, default 1]: ").strip()
    selected_idx = 0
    if choice.isdigit() and 1 <= int(choice) <= len(MODELS):
        selected_idx = int(choice) - 1
        
    model = MODELS[selected_idx]
    print(f"\nUsing model: {model['name']}")
    
    # Run interactively by building approved list
    approved = []
    for idx, prompt_item in enumerate(prompts_list):
        scene_id = prompt_item.get("scene_id")
        location = prompt_item.get("location")
        description = prompt_item.get("description", "")
        
        # Check if file already exists
        dest_filename = f"{prefix}_{scene_id}.png"
        dest_path = os.path.join(project_dir, "output", "production", "storyboard", dest_filename)
        if os.path.exists(dest_path):
            continue
            
        print(f"\nPrompt {idx+1}/{len(prompts_list)}: {scene_id} ({location})")
        print(f"Description : {description}")
        
        user_input = input("Generate this image? [y/N/q to quit]: ").strip().lower()
        if user_input == "q":
            break
        elif user_input == "y":
            approved.append(scene_id)
            
    if approved:
        print(f"\nStarting generation for approved scenes: {approved}")
        res = generate_storyboard(project_dir, prefix, approved, model["id"])
        print(f"Completed: {res['generated_count']} generated, {res['skipped_count']} skipped.")
    else:
        print("\nNo scenes approved for generation.")

if __name__ == "__main__":
    main()
