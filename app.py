import streamlit as st
import edge_tts
import asyncio
import tempfile
import os
import shutil
from google import genai
from google.genai import types

# App configuration
st.set_page_config(page_title="Video Auto Dubbing & Localizer Pro", page_icon="🎬", layout="wide")
st.title("🎬 Video Auto Dubbing & Localizer Pro (Gemini Powered)")

# Helper for Safe Async Execution inside Streamlit
def run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)

# Sidebar for Gemini API Key
st.sidebar.title("⚙️ Settings")
gemini_api_key = st.sidebar.text_input("🔑 Gemini API Key ထည့်ပါ", type="password")
st.sidebar.markdown("[Google AI Studio မှ API Key အခမဲ့ယူရန်](https://aistudio.google.com/)")

tab1, tab2, tab3 = st.tabs(["📹 1. Upload & Transcribe", "📝 2. Rewrite & Translate", "🎙️ 3. Dubbing & Video Merge"])

if 'video_path' not in st.session_state: st.session_state.video_path = None
if 'transcript_data' not in st.session_state: st.session_state.transcript_data = []
if 'full_text' not in st.session_state: st.session_state.full_text = ""
if 'final_dub_video' not in st.session_state: st.session_state.final_dub_video = None

# ================= TAB 1 : Video Upload & Transcribe =================
with tab1:
    st.markdown("### 📹 Video သို့မဟုတ် Audio File တင်ပါ")
    uploaded_file = st.file_uploader("Video/Audio Upload (MP4, MKV, MOV, MP3, WAV)", type=['mp4', 'mkv', 'mov', 'mp3', 'wav'])

    lang_choice = st.selectbox(
        "🌐 Video ထဲက စကားပြော ဘာသာစကား ရွေးပါ",
        ["Chinese (တရုတ်)", "English (အင်္ဂလိပ်)", "Auto Detect"]
    )

    if uploaded_file:
        suffix = os.path.splitext(uploaded_file.name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.read())
            st.session_state.video_path = tmp.name

        if suffix in ['.mp4', '.mkv', '.mov']:
            st.video(st.session_state.video_path)
        else:
            st.audio(st.session_state.video_path)

        if st.button("🎙️ Gemini ဖြင့် စာသား စတင်ထုတ်မည်", type="primary", use_container_width=True):
            if not gemini_api_key:
                st.error("❌ ဘယ်ဘက် Sidebar တွင် Gemini API Key အရင်ထည့်သွင်းပေးပါ။")
            elif not shutil.which("ffmpeg"):
                st.error("❌ FFmpeg System Path တွင် မရှိပါ။ packages.txt ကို စစ်ဆေးပါ။")
            else:
                with st.spinner("Gemini API ဖြင့် Audio ဖတ်ရှုပြီး စာသားပြောင်းလဲနေပါသည်..."):
                    extracted_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
                    os.system(f'ffmpeg -i "{st.session_state.video_path}" -vn -ar 16000 -ac 1 -ab 128k -f mp3 -y "{extracted_audio}"')

                    try:
                        client = genai.Client(api_key=gemini_api_key)

                        # Audio File ကို Gemini API ဆီ တင်ခြင်း
                        audio_file = client.files.upload(file=extracted_audio)

                        prompt = f"""
                        Listen to the provided audio file carefully.
                        Transcribe the spoken audio text line by line.
                        Language of spoken audio: {lang_choice}.
                        Rules:
                        1. Provide ONLY the transcribed spoken text.
                        2. Print each spoken sentence on a new line.
                        3. Do NOT include markdown code tags, formatting, sound descriptions, or headers.
                        """

                        response = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=[audio_file, prompt]
                        )

                        transcribed_text = response.text.strip()
                        lines = [line.strip() for line in transcribed_text.split('\n') if line.strip()]

                        # Audio Timing Estimation based on total lines
                        # (Gemini Audio Direct Transcription format mapping)
                        parsed_segments = []
                        for i, line in enumerate(lines):
                            parsed_segments.append({
                                "start": i * 3.0, # Average 3 seconds per line estimate
                                "end": (i + 1) * 3.0,
                                "text": line
                            })

                        st.session_state.transcript_data = parsed_segments
                        st.session_state.full_text = "\n".join(lines)

                        if len(lines) == 0:
                            st.warning("⚠️ စာသား ထွက်မလာပါ။ မူရင်း Video တွင် အသံပါဝင်မှု စစ်ဆေးပါ။")
                        else:
                            st.success(f"✅ စာသား {len(lines)} ကြောင်း အောင်မြင်စွာ ထွက်လာပါပြီ! TAB 2 (Rewrite & Translate) တွင် စာသားများ တန်းပေါ်နေပါမည်။")

                    except Exception as e:
                        st.error(f"❌ Gemini API Error: {str(e)}")

                    finally:
                        if os.path.exists(extracted_audio):
                            os.remove(extracted_audio)

# ================= TAB 2 : Plain Text Rewrite & Translate =================
with tab2:
    st.markdown("### 📝 စကားပြောများ တိုက်ရိုက် ပြင်ဆင်/ဘာသာပြန်ဆိုရန်")
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**မူရင်း ထုတ်ယူထားသော စာသားများ (Raw Transcripts)**")
        st.text_area("Original Text", st.session_state.full_text, height=380, key="raw_text")

    with col_b:
        st.markdown("**မြန်မာဘာသာပြန်/Rewrite စာသားများ ထည့်သွင်းရန် (တစ်ကြောင်းစီ ရေးပါ)**")
        translated_input = st.text_area(
            "Translated / Rewritten Burmese Text", 
            value="", 
            height=380, 
            placeholder="မူရင်း စာကြောင်း အရေအတွက် အတိုင်း မြန်မာလို တစ်ကြောင်းစီ ဘာသာပြန်ထည့်ပါ...",
            key="translated_editor"
        )

    st.info("💡 Original Text ထဲမှ စာကြောင်း အရေအတွက်နှင့် Translated Text ထဲမှ စာကြောင်း အရေအတွက် ညီနေရပါမည်။")

# ================= TAB 3 : TTS & Video Merge =================
with tab3:
    st.markdown("### 🎙️ Edge TTS & Synchronized Video Merge")

    async def generate_single_tts(text, voice, output_path):
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)

    col1, col2 = st.columns([2, 1])
    with col1:
        base_voice = st.selectbox(
            "🎭 အခြေခံအသံ",
            ["my-MM-ThihaNeural", "my-MM-NilarNeural"],
            format_func=lambda x: "Thiha - ယောက်ျားလေး" if "Thiha" in x else "Nilar - မိန်းကလေး"
        )

    with col2:
        orig_vol = st.slider("🔇 မူရင်း Video အသံပမာဏ (%)", 0, 100, 5)

    if st.button("🚀 Video နှင့် အသံကို Dubbing ထုတ်မည်", type="primary", use_container_width=True):
        translations = [line.strip() for line in st.session_state.translated_editor.split('\n') if line.strip()]

        if not translations:
            st.warning("⚠️ ဖတ်ရန် စာသားမရှိပါ။ TAB 2 တွင် မြန်မာဘာသာပြန် ရေးထည့်ပါ။")
        elif not st.session_state.video_path:
            st.warning("⚠️ Video Upload မတင်ရသေးပါ။ TAB 1 တွင် Upload တင်ပါ။")
        else:
            with st.spinner("အသံသစ် ဖန်တီးပြီး Video ထဲ ပေါင်းစပ်နေပါသည်..."):
                combined_text = " ".join(translations)
                dub_audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
                run_async(generate_single_tts(combined_text, base_voice, dub_audio_path))

                output_video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
                orig_v_vol = orig_vol / 100.0

                if orig_vol == 0:
                    cmd = f'ffmpeg -i "{st.session_state.video_path}" -i "{dub_audio_path}" -c:v copy -map 0:v:0 -map 1:a:0 -shortest -y "{output_video_path}"'
                else:
                    cmd = f'ffmpeg -i "{st.session_state.video_path}" -i "{dub_audio_path}" -filter_complex "[0:a]volume={orig_v_vol}[orig];[1:a]volume=1.0[dub];[orig][dub]amix=inputs=2:duration=first" -c:v copy -shortest -y "{output_video_path}"'

                os.system(cmd)

                if os.path.exists(dub_audio_path): os.remove(dub_audio_path)

                st.session_state.final_dub_video = output_video_path
                st.success("✅ Video Dubbing အောင်မြင်စွာ ပြီးဆုံးပါပြီ!")

    if 'final_dub_video' in st.session_state and st.session_state.final_dub_video and os.path.exists(st.session_state.final_dub_video):
        st.markdown("---")
        st.markdown("### 🎬 Final Dubbed Video")
        st.video(st.session_state.final_dub_video)
        with open(st.session_state.final_dub_video, 'rb') as f:
            st.download_button("📥 Dubbed Video Download (MP4)", f.read(), "dubbed_video.mp4", "video/mp4", use_container_width=True)
    
