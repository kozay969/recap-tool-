import streamlit as st
import edge_tts
import asyncio
import tempfile
import os
import shutil
import json
import wave
import urllib.request
import zipfile
from vosk import Model, KaldiRecognizer

# App configuration
st.set_page_config(page_title="Video Auto Dubbing & Localizer Pro", page_icon="🎬", layout="wide")
st.title("🎬 Video Auto Dubbing & Localizer Pro")

# Offline Chinese Speech Model Downloader & Loader
@st.cache_resource
def load_vosk_model(lang):
    model_dir = "vosk-model-small-cn-0.22"
    zip_path = "vosk-model-small-cn-0.22.zip"
    
    if not os.path.exists(model_dir):
        with st.spinner("အသံဖတ် မော်ဒယ် ဒေါင်းလုဒ်ဆွဲနေပါသည် (ခဏစောင့်ပေးပါ)..."):
            url = "https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip"
            urllib.request.urlretrieve(url, zip_path)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(".")
            if os.path.exists(zip_path):
                os.remove(zip_path)
                
    return Model(model_dir)

# Helper for Safe Async Execution inside Streamlit
def run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)

tab1, tab2, tab3 = st.tabs(["📹 1. Upload & Transcribe", "📝 2. Rewrite & Translate", "🎙️ 3. Dubbing & Video Merge"])

if 'video_path' not in st.session_state: st.session_state.video_path = None
if 'transcript_data' not in st.session_state: st.session_state.transcript_data = []
if 'full_text' not in st.session_state: st.session_state.full_text = ""
if 'final_dub_video' not in st.session_state: st.session_state.final_dub_video = None

# ================= TAB 1 : Video Upload & Transcribe =================
with tab1:
    st.markdown("### 📹 Video သို့မဟုတ် Audio File တင်ပါ")
    uploaded_file = st.file_uploader("Video/Audio Upload (MP4, MKV, MOV, MP3, WAV)", type=['mp4', 'mkv', 'mov', 'mp3', 'wav'])

    if uploaded_file:
        suffix = os.path.splitext(uploaded_file.name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.read())
            st.session_state.video_path = tmp.name

        if suffix in ['.mp4', '.mkv', '.mov']:
            st.video(st.session_state.video_path)
        else:
            st.audio(st.session_state.video_path)

        if st.button("🎙️ စာသား စတင်ထုတ်မည်", type="primary", use_container_width=True):
            if not shutil.which("ffmpeg"):
                st.error("❌ FFmpeg System Path တွင် မရှိပါ။ packages.txt ကို စစ်ဆေးပါ။")
            else:
                with st.spinner("အသံဖိုင်မှ တရုတ်စာသားအဖြစ် ပြောင်းလဲပေးနေပါသည်..."):
                    wav_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
                    # Convert to 16kHz Mono PCM WAV
                    os.system(f'ffmpeg -i "{st.session_state.video_path}" -vn -ac 1 -ar 16000 -acodec pcm_s16le -y "{wav_audio}"')

                    try:
                        model = load_vosk_model("cn")
                        wf = wave.open(wav_audio, "rb")
                        rec = KaldiRecognizer(model, wf.getframerate())
                        rec.SetWords(True)

                        results = []
                        while True:
                            data = wf.readframes(4000)
                            if len(data) == 0:
                                break
                            if rec.AcceptWaveform(data):
                                part = json.loads(rec.Result())
                                if 'text' in part and part['text'].strip():
                                    results.append(part['text'].replace(" ", ""))

                        final_res = json.loads(rec.FinalResult())
                        if 'text' in final_res and final_res['text'].strip():
                            results.append(final_res['text'].replace(" ", ""))

                        extracted_text = "\n".join(results)

                        st.session_state.full_text = extracted_text
                        st.session_state.transcript_data = results

                        if len(results) == 0:
                            st.warning("⚠️ စာသား ထွက်မလာပါ။ မူရင်း Video အသံ ကြည်လင်မှု မရှိခြင်း သို့မဟုတ် အသံတိတ်နေခြင်း ဖြစ်နိုင်ပါတယ်။")
                        else:
                            st.success("✅ စာသား အောင်မြင်စွာ ထွက်လာပါပြီ! TAB 2 (Rewrite & Translate) တွင် စာသားများ တန်းပေါ်နေပါမည်။")

                    except Exception as e:
                        st.error(f"❌ Transcribe Error: {str(e)}")

                    finally:
                        if os.path.exists(wav_audio):
                            os.remove(wav_audio)

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
            placeholder="ဒီမှာ မြန်မာလို ဘာသာပြန်ထည့်ပါ...",
            key="translated_editor"
        )

# ================= TAB 3 : TTS & Video Merge =================
with tab3:
    st.markdown("### 🎙️ Edge TTS & Video Merge")

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
        translations = st.session_state.translated_editor.strip()

        if not translations:
            st.warning("⚠️ ဖတ်ရန် စာသားမရှိပါ။ TAB 2 တွင် မြန်မာဘာသာပြန် ရေးထည့်ပါ။")
        elif not st.session_state.video_path:
            st.warning("⚠️ Video Upload မတင်ရသေးပါ။ TAB 1 တွင် Upload တင်ပါ။")
        else:
            with st.spinner("အသံသစ် ဖန်တီးပြီး Video ထဲ ပေါင်းစပ်နေပါသည်..."):
                dub_audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
                run_async(generate_single_tts(translations, base_voice, dub_audio_path))

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
            
