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
import base64
import pickle

# Load environment variables
load_dotenv()

# Set up YouTube API client
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

# Load configuration
def load_config():
    default_config = {
        "channels": [],
        "keywords": [],
        "channel_ids": {}  # New field to store channel IDs
    }
    try:
        with open('config.json', 'r') as config_file:
            config = json.load(config_file)
            # Ensure the new field exists
            if 'channel_ids' not in config:
                config['channel_ids'] = {}
            return config
    except FileNotFoundError:
        with open('config.json', 'w') as config_file:
            json.dump(default_config, config_file)
        return default_config

config = load_config()

# Save configuration
def save_config():
    with open('config.json', 'w') as config_file:
        json.dump(config, config_file)

# Authenticate and create YouTube API client
def get_authenticated_service():
    return googleapiclient.discovery.build(
        API_SERVICE_NAME, API_VERSION, developerKey=os.getenv('YOUTUBE_API_KEY'))

youtube = get_authenticated_service()

# Function to get channel ID from channel URL
def get_channel_id(channel_url):
    # Check if we have the channel ID cached
    if channel_url in config['channel_ids']:
        return config['channel_ids'][channel_url]

    try:
        if '/channel/' in channel_url:
            channel_id = channel_url.split('/channel/')[1]
        elif '/user/' in channel_url or '/c/' in channel_url or '@' in channel_url:
            username = channel_url.split('/')[-1]
            if username.startswith('@'):
                username = username[1:]  # Remove '@' if present
            request = youtube.search().list(
                part="snippet",
                type="channel",
                q=username,
                maxResults=1
            )
            response = request.execute()
            if response['items']:
                channel_id = response['items'][0]['snippet']['channelId']
            else:
                st.error(f"Could not get channel ID for URL: {channel_url}")
                return None
        else:
            st.error(f"Invalid channel URL format: {channel_url}")
            return None

        # Cache the channel ID
        config['channel_ids'][channel_url] = channel_id
        save_config()
        return channel_id
    except Exception as e:
        st.error(f"An error occurred while getting channel ID: {e}")
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
@st.cache_data(ttl=86400)  # Cache for 24 hours
def get_cached_videos(channels, max_results=5, keywords=None):
    all_videos = []
    for channel in channels:
        channel_id = get_channel_id(channel)
        if channel_id:
            videos = fetch_latest_videos(channel_id, max_results)
            if keywords:
                videos = filter_relevant_content(videos, keywords)
            all_videos.extend(videos)
        else:
            st.warning(f"Skipping channel: {channel} - Could not get channel ID")
    return sorted(all_videos, key=lambda x: x['snippet']['publishedAt'], reverse=True)

# Streamlit app
def main():
    st.title("YourTubes™")
    st.write(" - Your Personalized YouTube™ Feed")

    # Sidebar for configuration
    st.sidebar.header("Configuration")
    channels = st.sidebar.text_area("Enter YouTube channel URLs (one per line)", value="\n".join(config['channels']))
    channels = [channel.strip() for channel in channels.split('\n') if channel.strip()]
    
    keywords = st.sidebar.text_input("Enter keywords for filtering (comma-separated)", value=",".join(config['keywords']))
    keywords = [keyword.strip() for keyword in keywords.split(',') if keyword.strip()]

    max_results = 1

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

    # Create a placeholder for the video player
    video_placeholder = st.empty()

    # Display videos in a grid
    for i in range(0, len(videos), 3):
        cols = st.columns(3)
        for j in range(3):
            if i + j < len(videos):
                video = videos[i + j]
                with cols[j]:
                    with st.container():
                        thumbnail_url = video['snippet']['thumbnails']['medium']['url']
                        st.image(thumbnail_url, use_column_width=True)
                        title = video['snippet']['title']
                        st.markdown(f"**{title[:50]}{'...' if len(title) > 50 else ''}**")
                        st.write(f"Published: {video['snippet']['publishedAt'][:10]}")
                        if st.button(f"Play Video {i+j+1}"):
                            video_id = video['id']['videoId']
                            video_placeholder.markdown(f'<iframe width="100%" height="315" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allowfullscreen></iframe>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
