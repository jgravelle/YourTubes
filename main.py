import streamlit as st
import googleapiclient.discovery
import googleapiclient.errors
import os
import json
from datetime import datetime, timedelta
import requests
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up YouTube API client
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

# Load configuration
def load_config():
    with open('config.json') as config_file:
        return json.load(config_file)

config = load_config()

# Authenticate and create YouTube API client
def get_authenticated_service():
    return googleapiclient.discovery.build(
        API_SERVICE_NAME, API_VERSION, developerKey=os.getenv('YOUTUBE_API_KEY'))

youtube = get_authenticated_service()

# Function to get channel ID from channel URL
def get_channel_id(channel_url):
    response = requests.get(channel_url)
    if response.status_code == 200:
        channel_id = response.text.split('"channelId":"')[1].split('"')[0]
        return channel_id
    return None

# Function to fetch latest videos from a channel
def fetch_latest_videos(channel_id, max_results=10):
    try:
        request = youtube.search().list(
            part="snippet",
            channelId=channel_id,
            order="date",
            type="video",
            maxResults=max_results
        )
        response = request.execute()
        return response['items']
    except googleapiclient.errors.HttpError as e:
        st.error(f"An error occurred: {e}")
        return []

# Function to filter relevant content
def filter_relevant_content(videos, keywords):
    return [video for video in videos if any(keyword.lower() in video['snippet']['title'].lower() or 
                                             keyword.lower() in video['snippet']['description'].lower() 
                                             for keyword in keywords)]

# Cache videos
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_cached_videos(channels, max_results=10, keywords=None):
    all_videos = []
    for channel in channels:
        channel_id = get_channel_id(channel)
        if channel_id:
            videos = fetch_latest_videos(channel_id, max_results)
            if keywords:
                videos = filter_relevant_content(videos, keywords)
            all_videos.extend(videos)
    return sorted(all_videos, key=lambda x: x['snippet']['publishedAt'], reverse=True)

# Streamlit app
def main():
    st.title("YouTube Channel Monitor")

    # Sidebar for configuration
    st.sidebar.header("Configuration")
    channels = st.sidebar.text_area("Enter YouTube channel URLs (one per line)", value="\n".join(config['channels']))
    channels = [channel.strip() for channel in channels.split('\n') if channel.strip()]
    
    keywords = st.sidebar.text_input("Enter keywords for filtering (comma-separated)", value=",".join(config['keywords']))
    keywords = [keyword.strip() for keyword in keywords.split(',') if keyword.strip()]

    max_results = st.sidebar.slider("Max videos per channel", 1, 50, 10)

    if st.sidebar.button("Save Configuration"):
        config['channels'] = channels
        config['keywords'] = keywords
        with open('config.json', 'w') as config_file:
            json.dump(config, config_file)
        st.sidebar.success("Configuration saved!")

    # Main content
    if st.button("Refresh Videos"):
        st.cache_data.clear()
        st.experimental_rerun()

    videos = get_cached_videos(channels, max_results, keywords)

    # Display videos in a grid
    cols = st.columns(3)
    for i, video in enumerate(videos):
        with cols[i % 3]:
            thumbnail_url = video['snippet']['thumbnails']['medium']['url']
            response = requests.get(thumbnail_url)
            img = Image.open(BytesIO(response.content))
            st.image(img, use_column_width=True)
            st.write(f"**{video['snippet']['title']}**")
            st.write(f"Published: {video['snippet']['publishedAt']}")
            st.write(f"[Watch Video](https://www.youtube.com/watch?v={video['id']['videoId']})")

if __name__ == "__main__":
    main()
