import streamlit as st
import os
import json
import tempfile
import subprocess
import time
from pathlib import Path
from gtts import gTTS

# Optional edge-tts support if installed
try:
    import asyncio
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

# ==========================================
# PAGE CONFIGURATION & MODERN DARK UI THEME
# ==========================================
st.set_page_config(
    page_title="Video Recap & Burmese Auto-Dubber",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Modern Dark UI (Streamlit Dark Theme)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Padauk:wght@400;700&family=JetBrains+Mono:wght@400;500&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    .burmese-font {
        font-family: 'Padauk', sans-serif !important;
        line-height: 1.8 !important;
    }
    
    .stApp {
        background-color: #09090b;
        color: #f4f4f5;
    }
    
    .main-card {
        background: #18181b;
        border: 1px solid #27272a;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 20px;
    }
    
    .metric-badge {
        display: inline-block;
        background: #27272a;
        color: #fbbf24;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-right: 8px;
    }
    
    .step-indicator {
        display: flex;
        align-items: center;
        margin-bottom: 12px;
        font-weight: 600;
        color: #f59e0b;
    }
    
    .stButton>button {
        background: linear-gradient(135deg, #d97706 0%, #b45309 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 24px;
        font-weight: 600;
        transition: all 0.2s;
    }
    
    .stButton>button:hover {
        background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
        box-shadow: 0 4px 12px rgba(245, 158, 11, 0.3);
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# SESSION STATE INITIALIZATION
# ==========================================
if "current_step" not in st.session_state:
    st.session_state.current_step = 1
if "video_path" not in st.session_state:
    st.session_state.video_path = None
if "audio_path" not in st.session_state:
    st.session_state.audio_path = None
if "transcription_data" not in st.session_state:
    st.session_state.transcription_data = None
if "burmese_segments" not in st.session_state:
    st.session_state.burmese_segments = None
if "burmese_recap" not in st.session_state:
    st.session_state.burmese_recap = None
if "english_recap" not in st.session_state:
    st.session_state.english_recap = None
if "dubbed_video_path" not in st.session_state:
    st.session_state.dubbed_video_path = None
if "srt_burmese" not in st.session_state:
    st.session_state.srt_burmese = None

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def extract_audio_from_video(video_path: str, output_audio_path: str):
    """Extract audio from MP4 using FFmpeg"""
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "libmp3lame", "-q:a", "2",
        output_audio_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return output_audio_path

def format_timestamp_srt(seconds: float) -> str:
    """Convert float seconds to SRT time format: 00:00:00,000"""
    millis = int((seconds % 1) * 1000)
    seconds = int(seconds)
    minutes = seconds // 60
    hours = minutes // 60
    minutes = minutes % 60
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

def generate_srt(segments: list, lang_key: str = "burmeseText") -> str:
    """Generate SRT formatted string from segments"""
    srt_lines = []
    for idx, seg in enumerate(segments, 1):
        start_str = format_timestamp_srt(seg["start"])
        end_str = format_timestamp_srt(seg["end"])
        text = seg.get(lang_key, seg.get("text", ""))
        srt_lines.append(f"{idx}\n{start_str} --> {end_str}\n{text}\n")
    return "\n".join(srt_lines)

def transcribe_and_recap_with_gemini(audio_path: str, api_key: str):
    """Transcribe audio and generate timestamped segments with Gemini"""
    client = genai.Client(api_key=api_key)
    
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    prompt = """
    Analyze this audio carefully. 
    1. Provide an executive summary/recap of what is spoken in the audio.
    2. Transcribe the audio into concise sentence-level or phrase-level segments.
    3. Include accurate start and end timestamps in seconds (e.g., 0.0 to 3.5).
    
    Output strictly valid JSON with this structure:
    {
      "recap": "Concise executive recap of the video/audio content...",
      "segments": [
        {
          "id": 1,
          "start": 0.0,
          "end": 3.4,
          "text": "Exact English transcribed text."
        }
      ]
    }
    """
    
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=[
            types.Part.from_bytes(data=audio_bytes, mime_type="audio/mp3"),
            prompt
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    
    return json.loads(response.text)

def translate_to_burmese_with_gemini(segments_data: dict, api_key: str):
    """Translate timestamps & recap into natural Burmese Unicode"""
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    You are an expert English to Burmese (မြန်မာဘာသာ) audiovisual translator.
    Translate the English recap and each sentence-level segment into natural, idiomatic, spoken Burmese.
    Preserve the exact start and end timestamps. Use standard Myanmar Unicode fonts.
    
    Input data:
    {json.dumps(segments_data)}
    
    Output strictly valid JSON:
    {{
      "englishRecap": "{segments_data.get('recap', '')}",
      "burmeseRecap": "ဗီဒီယို၏ အကျဉ်းချုပ် မြန်မာလို...",
      "segments": [
        {{
          "id": 1,
          "start": 0.0,
          "end": 3.4,
          "originalText": "...",
          "burmeseText": "မြန်မာဘာသာပြန်..."
        }}
      ]
    }}
    """
    
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    
    return json.loads(response.text)

def generate_burmese_tts(text: str, output_path: str, tts_engine: str = "gTTS"):
    """Synthesize Burmese speech into MP3"""
    if tts_engine == "edge-tts" and HAS_EDGE_TTS:
        voice = "my-MM-NilarNeural"
        async def _run():
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_path)
        asyncio.run(_run())
    else:
        # Fallback to gTTS (Burmese language code 'my')
        tts = gTTS(text=text, lang="my", slow=False)
        tts.save(output_path)
    return output_path

def sync_and_dub_video(video_path: str, segments: list, temp_dir: str, output_video_path: str, mix_mode: str = "replace", duck_vol: float = 0.15):
    """Align Burmese audio segments to timestamps and mux with video via FFmpeg"""
    audio_clips = []
    filter_inputs = []
    
    # 1. Synthesize audio for each segment
    for i, seg in enumerate(segments):
        clip_path = os.path.join(temp_dir, f"seg_{i}.mp3")
        generate_burmese_tts(seg["burmeseText"], clip_path)
        
        # Measure duration with ffprobe
        probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", clip_path]
        dur_res = subprocess.run(probe_cmd, stdout=subprocess.PIPE, text=True)
        clip_dur = float(dur_res.stdout.strip() or 1.0)
        
        target_dur = seg["end"] - seg["start"]
        # If TTS audio is slightly longer than window, speed up with atempo
        if clip_dur > target_dur + 0.3 and target_dur > 0.5:
            tempo = min(clip_dur / target_dur, 1.5)
            adjusted_path = os.path.join(temp_dir, f"seg_adj_{i}.mp3")
            subprocess.run([
                "ffmpeg", "-y", "-i", clip_path,
                "-filter:a", f"atempo={tempo}",
                adjusted_path
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            clip_path = adjusted_path
            
        audio_clips.append((clip_path, seg["start"]))

    # 2. Build FFmpeg audio timeline
    # Using adelay and amix
    inputs = []
    filter_parts = []
    
    for i, (clip_file, start_sec) in enumerate(audio_clips):
        inputs.extend(["-i", clip_file])
        delay_ms = int(start_sec * 1000)
        filter_parts.append(f"[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}];")
    
    mix_ins = "".join([f"[a{i}]" for i in range(len(audio_clips))])
    filter_parts.append(f"{mix_ins}amix=inputs={len(audio_clips)}:dropout_transition=0:normalize=0[dubbed_track]")
    
    full_filter = "".join(filter_parts)
    dubbed_audio_track = os.path.join(temp_dir, "dubbed_audio_master.mp3")
    
    subprocess.run(["ffmpeg", "-y"] + inputs + ["-filter_complex", full_filter, "-map", "[dubbed_track]", dubbed_audio_track], check=True)
    
    # 3. Combine with original video
    if mix_mode == "duck":
        # Mix original audio lowered with dubbed track
        final_cmd = [
            "ffmpeg", "-y", "-i", video_path, "-i", dubbed_audio_track,
            "-filter_complex", f"[0:a]volume={duck_vol}[bg];[bg][1:a]amix=inputs=2:dropout_transition=0:normalize=0[final_audio]",
            "-map", "0:v:0", "-map", "[final_audio]", "-c:v", "copy", "-c:a", "aac",
            output_video_path
        ]
    else:
        # Replace original audio completely
        final_cmd = [
            "ffmpeg", "-y", "-i", video_path, "-i", dubbed_audio_track,
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac",
            output_video_path
        ]
        
    subprocess.run(final_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return output_video_path

# ==========================================
# SIDEBAR CONTROLS
# ==========================================
with st.sidebar:
    st.title("🎬 Video Auto-Dubber")
    st.markdown("**All-in-One AI Video Recap & Burmese Dubbing**")
    st.markdown("---")
    
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        api_key = st.text_input("🔑 Gemini API Key", type="password", help="Enter your Google Gemini API key")
    else:
        st.success("✅ Gemini API Key detected")
        
    tts_engine = st.selectbox("🔊 Voice Engine", ["gTTS (Google TTS)", "Edge-TTS (Neural)"], index=0)
    engine_choice = "edge-tts" if "Edge" in tts_engine else "gTTS"
    
    audio_mode = st.selectbox(
        "🎛️ Audio Mixing",
        ["Replace Original Audio", "Duck Original Audio (15% BG)", "Mute Original Audio"],
        index=0
    )
    mix_choice = "duck" if "Duck" in audio_mode else "replace"
    
    st.markdown("---")
    st.markdown("### 📋 Workflow Steps")
    steps = [
        "1. Upload MP4 Video",
        "2. Extract & Transcribe",
        "3. Translate to Burmese",
        "4. Synthesize AI Voice",
        "5. Auto-Sync & Export"
    ]
    for s in steps:
        st.markdown(f"- {s}")

# ==========================================
# MAIN INTERFACE
# ==========================================
st.title("🎥 All-in-One Video Recap & Auto-Dubbing Tool")
st.markdown("Automatically transcribe video, generate dual-language recaps, translate with preserved timestamps, and dub with natural Burmese AI voice.")

# TAB 1: Main Pipeline
tab_pipeline, tab_subtitles, tab_about = st.tabs(["🚀 Auto-Dubbing Pipeline", "📄 Subtitles & SRT", "ℹ️ About & Setup"])

with tab_pipeline:
    col1, col2 = st.columns([1, 1], gap="large")
    
    with col1:
        st.subheader("1. Video Source")
        uploaded_file = st.file_uploader("Upload an MP4 Video File", type=["mp4", "mov", "m4v"])
        
        if uploaded_file is not None:
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            tfile.write(uploaded_file.read())
            st.session_state.video_path = tfile.name
            
            st.video(st.session_state.video_path)
            st.caption(f"📁 Loaded: {uploaded_file.name} ({uploaded_file.size / 1024 / 1024:.1f} MB)")
            
            # Action button
            if st.button("✨ Run Automated Recap & Dubbing", use_container_width=True):
                if not api_key:
                    st.error("Please provide a Gemini API Key in the sidebar.")
                else:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    try:
                        # Step 1: Extract Audio
                        status_text.info("🔊 Step 1/5: Extracting audio from video with FFmpeg...")
                        progress_bar.progress(15)
                        temp_dir = tempfile.mkdtemp()
                        extracted_audio = os.path.join(temp_dir, "extracted.mp3")
                        extract_audio_from_video(st.session_state.video_path, extracted_audio)
                        st.session_state.audio_path = extracted_audio
                        
                        # Step 2: Transcription with Gemini
                        status_text.info("🤖 Step 2/5: Transcribing and generating recap with Gemini AI...")
                        progress_bar.progress(35)
                        trans_data = transcribe_and_recap_with_gemini(extracted_audio, api_key)
                        st.session_state.transcription_data = trans_data
                        st.session_state.english_recap = trans_data.get("recap", "")
                        
                        # Step 3: Burmese Translation
                        status_text.info("🇲🇲 Step 3/5: Translating timestamps into Burmese Unicode...")
                        progress_bar.progress(60)
                        translation_res = translate_to_burmese_with_gemini(trans_data, api_key)
                        st.session_state.burmese_segments = translation_res.get("segments", [])
                        st.session_state.burmese_recap = translation_res.get("burmeseRecap", "")
                        
                        # Generate SRT
                        st.session_state.srt_burmese = generate_srt(st.session_state.burmese_segments, "burmeseText")
                        
                        # Step 4 & 5: Voice Synthesis & Video Muxing
                        status_text.info("🎙️ Step 4 & 5: Generating Burmese voice clips & synchronizing video...")
                        progress_bar.progress(85)
                        output_mp4 = os.path.join(temp_dir, "dubbed_final.mp4")
                        sync_and_dub_video(
                            video_path=st.session_state.video_path,
                            segments=st.session_state.burmese_segments,
                            temp_dir=temp_dir,
                            output_video_path=output_mp4,
                            mix_mode=mix_choice
                        )
                        st.session_state.dubbed_video_path = output_mp4
                        
                        progress_bar.progress(100)
                        status_text.success("🎉 Video Recap & Burmese Auto-Dubbing Complete!")
                        st.balloons()
                        
                    except Exception as e:
                        status_text.error(f"❌ Processing failed: {str(e)}")
                        
    with col2:
        st.subheader("2. Result & Final Dubbed Video")
        if st.session_state.dubbed_video_path and os.path.exists(st.session_state.dubbed_video_path):
            st.video(st.session_state.dubbed_video_path)
            
            with open(st.session_state.dubbed_video_path, "rb") as vf:
                st.download_button(
                    label="⬇️ Download Final Dubbed MP4 Video",
                    data=vf.read(),
                    file_name="burmese_dubbed_video.mp4",
                    mime="video/mp4",
                    use_container_width=True
                )
                
            # Dual Recap Display
            st.markdown("### 📝 Video Executive Recap")
            if st.session_state.burmese_recap:
                st.markdown(f"**🇲🇲 မြန်မာဘာသာ အကျဉ်းချုပ်:**")
                st.info(st.session_state.burmese_recap)
            if st.session_state.english_recap:
                st.markdown(f"**🇬🇧 English Recap:**")
                st.caption(st.session_state.english_recap)
                
        else:
            st.info("Upload a video on the left and click 'Run Automated Recap & Dubbing' to generate the dubbed video.")

with tab_subtitles:
    st.subheader("Timestamped Subtitles & Segments")
    if st.session_state.burmese_segments:
        if st.session_state.srt_burmese:
            st.download_button(
                label="⬇️ Download Burmese Subtitles (.SRT)",
                data=st.session_state.srt_burmese,
                file_name="burmese_subtitles.srt",
                mime="text/plain"
            )
            
        for seg in st.session_state.burmese_segments:
            with st.expander(f"⏱️ {seg['start']:.1f}s - {seg['end']:.1f}s | {seg.get('originalText', '')[:40]}..."):
                st.write(f"**Original:** {seg.get('originalText', '')}")
                st.markdown(f"**Burmese:** {seg.get('burmeseText', '')}")
    else:
        st.info("No transcription segments available yet. Process a video first.")

with tab_about:
    st.markdown("""
    ### About the Burmese Video Recap & Auto-Dubbing Tool
    - **Engine**: Powered by Google Gemini 3.8 Flash & Google GenAI SDK.
    - **Audio Extraction**: FFmpeg with high-fidelity MP3 audio stream extraction.
    - **Translation**: Preserves segment start/end boundary timestamps with natural Burmese phrasing.
    - **Voice Synthesis**: Burmese TTS via gTTS or Edge-TTS Neural.
    - **Video Sync**: Exact milliseconds alignment using FFmpeg `adelay` and `amix`.
    """)
    
