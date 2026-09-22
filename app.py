import asyncio
import json
import os
import shutil
import subprocess
import tempfile

import assemblyai as aai
import edge_tts
import streamlit as st
from google import genai
from google.genai import types

st.set_page_config(page_title="Video Auto Dubbing & Localizer Pro", page_icon="🎬", layout="wide")
st.title("🎬 Video Auto Dubbing & Localizer Pro")

BATCH_SIZE = 40  # Gemini ကို တစ်ကြိမ်ပို့မယ့် စာကြောင်းအရေအတွက်


# ---------------------------------------------------------------- helpers
def get_secret(name: str) -> str:
    try:
        return st.secrets[name]
    except Exception:
        return ""


def run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

