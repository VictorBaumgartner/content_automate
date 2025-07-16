import os
import random
import glob
import requests
import schedule
import time
import shutil
from datetime import datetime
from dotenv import load_dotenv
import pocketflow as pf
import ollama

# Load environment variables
load_dotenv()

# Configuration
MD_FOLDER = "./content/md_files"
IMAGE_FOLDER = "./content/images"
HISTORY_FOLDER = "./content/history"
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID")
FACEBOOK_ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN")
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Ensure history folder exists
os.makedirs(HISTORY_FOLDER, exist_ok=True)

# PocketFlow Shared Store
store = pf.Store()

# Node 1: Read Markdown Files
def read_md_files():
    md_files = glob.glob(f"{MD_FOLDER}/*.md")
    if not md_files:
        return None
    md_file = random.choice(md_files)
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    store.set("md_content", content)
    store.set("md_filename", os.path.basename(md_file))
    return content

# Node 2: Select Random Image
def select_image():
    image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.webp']
    image_files = []
    for ext in image_extensions:
        image_files.extend(glob.glob(f"{IMAGE_FOLDER}/{ext}"))
    if not image_files:
        return None
    image = random.choice(image_files)
    store.set("selected_image", image)
    return image

# Node 3: Generate Social Media Post
def generate_post():
    content = store.get("md_content")
    filename = store.get("md_filename")
    if not content:
        return None
    
    # Prompt for Llama3.1 to generate a post with hashtags
    prompt = f"""
    You are a social media manager for a high-end restaurant. Based on the following content from a file named '{filename}', create a vibrant, engaging social media post (max 280 characters) that promotes the restaurant's food, quality, prestige, vibe, and warm atmosphere. Use emojis and a positive tone. Include 3-5 relevant hashtags to target food enthusiasts.

    Content:
    {content}

    Post:
    """
    
    # Use Ollama's Llama3.1 for generation
    response = ollama.generate(
        model="llama3.1:latest",
        prompt=prompt,
        options={"temperature": 0.7, "max_tokens": 100}
    )
    post_text = response['response'].strip()
    # Ensure hashtags are added if not in response
    if "#" not in post_text:
        post_text += " #Foodie #RestaurantVibes #Gourmet #DiningExperience"
    store.set("post_text", post_text)
    return post_text

# Node 4: Post to Facebook
def post_to_facebook():
    post_text = store.get("post_text")
    image_path = store.get("selected_image")
    if not post_text or not image_path:
        return None
    
    url = f"https://graph.facebook.com/v20.0/{FACEBOOK_PAGE_ID}/photos"
    params = {
        "access_token": FACEBOOK_ACCESS_TOKEN,
        "caption": post_text,
        "published": True
    }
    with open(image_path, 'rb') as image:
        files = {"source": image}
        response = requests.post(url, params=params, files=files)
    
    # Move image to history folder if post is successful
    if response.status_code == 200:
        shutil.move(image_path, os.path.join(HISTORY_FOLDER, os.path.basename(image_path)))
    return response.json()

# Node 5: Post to Instagram
def post_to_instagram():
    post_text = store.get("post_text")
    image_path = store.get("selected_image")
    if not post_text or not image_path:
        return None
    
    # Step 1: Upload image to create media object
    url = f"https://graph.facebook.com/v20.0/{INSTAGRAM_ACCOUNT_ID}/media"
    params = {
        "access_token": INSTAGRAM_ACCESS_TOKEN,
        "image_url": f"file://{image_path}",  # Requires public URL in production
        "caption": post_text
    }
    response = requests.post(url, params=params)
    media = response.json()
    
    if "id" not in media:
        return None
    
    # Step 2: Publish the media object
    publish_url = f"https://graph.facebook.com/v20.0/{INSTAGRAM_ACCOUNT_ID}/media_publish"
    publish_params = {
        "access_token": INSTAGRAM_ACCESS_TOKEN,
        "creation_id": media["id"]
    }
    publish_response = requests.post(publish_url, params=publish_params)
    
    # Move image to history folder if post is successful
    if publish_response.status_code == 200:
        shutil.move(image_path, os.path.join(HISTORY_FOLDER, os.path.basename(image_path)))
    return publish_response.json()

# Define PocketFlow Graph
graph = pf.Graph()

# Add Nodes
graph.add_node("read_md", read_md_files)
graph.add_node("select_image", select_image)
graph.add_node("generate_post", generate_post)
graph.add_node("post_facebook", post_to_facebook)
graph.add_node("post_instagram", post_to_instagram)

# Define Actions (Edges)
graph.add_action("read_md", "select_image")
graph.add_action("select_image", "generate_post")
graph.add_action("generate_post", "post_facebook")
graph.add_action("generate_post", "post_instagram")

# Workflow Execution
def run_workflow():
    print(f"Running workflow at {datetime.now()}")
    graph.run()
    fb_result = store.get("post_facebook")
    ig_result = store.get("post_instagram")
    print(f"Facebook post result: {fb_result}")
    print(f"Instagram post result: {ig_result}")

# Scheduling
# For testing: Run every minute
schedule.every(1).minutes.do(run_workflow)
# For production: Run daily at 2 PM
# schedule.every().day.at("14:00").do(run_workflow)

# Main Loop
if __name__ == "__main__":
    print("Starting social media posting automation...")
    while True:
        schedule.run_pending()
        time.sleep(30)  # Check every 30 seconds