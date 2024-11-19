import streamlit as st
import astrapy
from openai import OpenAI


def intialize_connections():
    if "song_collection" not in st.session_state:
        st.session_state["song_collection"] = get_collection(st.secrets["ASTRA_DB_COLLECTION_NAME"])
    
    if "pid_collection" not in st.session_state:
        st.session_state["pid_collection"] = get_collection(st.secrets["ASTRA_DB_PID_COLLECTION_NAME"])

    if "openai_client" not in st.session_state:
        st.session_state["openai_client"] = load_openai_client()
    
@st.cache_resource
def get_collection(collection_name):
    client = astrapy.DataAPIClient(st.secrets["ASTRA_DB_APPLICATION_TOKEN"])
    database = client.get_database_by_api_endpoint(st.secrets["ASTRA_DB_API_ENDPOINT"])
    collection = database.get_collection(collection_name)
    print("collection:", collection)
    return collection

@st.cache_resource
def load_openai_client():
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    return client
