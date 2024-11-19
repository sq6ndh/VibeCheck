import streamlit as st
from utils.connect import intialize_connections
import requests
import time


intialize_connections()

def get_current_pid():
    pid_document = st.session_state.pid_collection.find_one({})
    if pid_document:
        return pid_document["_id"]
    else:
        return

if "current_pid" not in st.session_state:
    st.session_state.current_pid = get_current_pid()

@st.cache_data
def get_spotify_auth_token():
    auth_url = 'https://accounts.spotify.com/api/token'
    auth_response = requests.post(auth_url, {
        'grant_type': 'client_credentials',
        'client_id': st.secrets["SPOTIFY_CLIENT_ID"],
        'client_secret': st.secrets["SPOTIFY_CLIENT_SECRET"],
    })
    auth_response_data = auth_response.json()
    access_token = auth_response_data['access_token']
    return access_token

@st.cache_data
def get_tracks_from_spotify(playlist_id):
    access_token = get_spotify_auth_token()
    headers = {
        'Authorization': f'Bearer {access_token}',
    }
    playlist_url = f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks'
    try:
        response = requests.get(playlist_url, headers=headers)
        response.raise_for_status()
        playlist_tracks = response.json()['items']
        return playlist_tracks
    except requests.exceptions.RequestException:
        return None
    

@st.cache_data
def get_song_description(song_name, artist_name):
    prompt = f"""
        You are an AI agent that helps users determine what songs to play to match
        their setting. Based on the included song name and artist, '{song_name}' by '{artist_name}', write up a description of what
        kind of setting would be appropriate to listen to. Do not make assumptions based purely on the song name, you should
        try to use real information about the song to come up with your setting description.
    """
    response = st.session_state.openai_client.chat.completions.create(
        model="gpt-4o",
        messages=
        [
            {"role": "system", "content": prompt},
        ]
    )
    return response.choices[0].message.content.strip()

def load_tracks_to_astra(new_playlist_id):
    playlist_tracks = get_tracks_from_spotify(new_playlist_id)
    print('playlist_tracks', playlist_tracks)
    if playlist_tracks:
        if new_playlist_id == st.session_state["current_pid"]:
            st.toast("Reloading songs from current playlist - checking for new songs.")
        else:
            clear_playlist()
            st.session_state.pid_collection.insert_one({"_id": new_playlist_id})
        progress_bar = st.progress(0, "Loading tracks to Astra DB...")
        num_tracks = len(playlist_tracks)
        for i in range(num_tracks):
            percentage_complete = i / float(num_tracks)
            st.session_state["current_loading_num"] = i / float(num_tracks)
            item = playlist_tracks[i]
            track = item['track']
            song = track["name"]
            artist = track['artists'][0]['name']
            song_url = track['external_urls']['spotify']
            print(f"Song Name: {song} | Artist Name: {artist} | Song URL: {song_url}")

            existing_document = st.session_state.song_collection.find_one({"Song_URL": song_url})
            if existing_document:
                progress_text = f"Skipping song {i + 1} of {num_tracks}, already loaded: {song} - {artist}"
                progress_bar.progress(percentage_complete, progress_text)
                time.sleep(0.1)
            else:
                progress_text = f"Loading song {i + 1} of {num_tracks}: {song} - {artist}"
                progress_bar.progress(percentage_complete, progress_text)
                description = get_song_description(song, artist)
                print(description)
                document = {
                    "Song_Name": song,
                    "Artist": artist,
                    "Song_URL": song_url,
                    "$vectorize": description
                }
                st.session_state.song_collection.insert_one(document)
        progress_bar.progress(1.0, f"Finished loading {i + 1} of {num_tracks} songs to Astra DB.")
        time.sleep(2)
        progress_bar.empty()
        st.session_state.current_pid = new_playlist_id
    else:
        st.toast("Please submit a valid Spotify playlist ID.")

def clear_playlist():
    print("clear playlist called")
    st.session_state.song_collection.delete_many({})
    st.session_state.pid_collection.delete_many({})
    st.session_state.current_pid = None

def load_playlist():
    new_playlist_id = st.session_state["pid_input"]
    load_tracks_to_astra(new_playlist_id)

def remove_few_songs_from_astra():
    for i in range(2):
        result = st.session_state.song_collection.delete_one({})
        print(result)

### UI ###
st.title("Vibe Check :musical_note:")

with st.container(border=True):
    st.write("**Current Playlist ID:** ", st.session_state.current_pid)
    if st.session_state.current_pid:
        disable_button = False
    else:
        disable_button = True
    st.link_button(
        "Open playlist in Spotify",
        "https://open.spotify.com/user/spotify/playlist/%s" % st.session_state.current_pid,
        disabled=disable_button)
    st.button("Clear full playlist", on_click=clear_playlist, disabled=disable_button)
    st.button("Remove a few songs from Astra DB", on_click=remove_few_songs_from_astra, help="This will remove 2 random songs and their embeddings from the Astra DB vector store - it will retain the rest of the song data.", disabled=disable_button)

with st.form(key="new_playlist_form"):
    st.markdown(
    """
    Copy/paste a Spotify playlist ID into the box below and click "Load to Astra DB". 
    
    This application will:
    1. Retrieve the songs from that playlist using the Spotify API
    1. Generate descriptions of those songs using an LLM
    1. Upload the song information and descriptions to the Astra DB Vector Store
    """
    )
    new_pid = st.text_input(
        "Sample Playlist ID: 3C5CqRlEoisNEusrgg7kEX",
        key="pid_input"
    )
    
    st.form_submit_button("Load full playlist to Astra DB", on_click=load_playlist)
