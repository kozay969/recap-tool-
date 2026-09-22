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
import subprocess
from vosk import Model, KaldiRecognizer

st.set_page_config(page_title="Video Auto Dubbing & Localizer Pro", page_icon="🎬", layout="wide")
st.title("🎬 Video Auto Dubbing & Localizer Pro")

# ================= Helper Functions =================
@st.cache_resource
def load_vosk_model():
    model_dir = "vosk-model-small-cn-0.22"
    zip_path = f"{model_dir}.zip"
    if not os.path.exists(model_dir):
        with st.spinner("အသံဖတ် မော်ဒယ် ဒေါင်းလုဒ်ဆွဲနေပါသည် (42MB)..."):
            url = "https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip"
            try:
                urllib.request.urlretrieve(url, zip_path)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(".")
            finally:
                if os.path.exists(zip_path):
                    os.remove(zip_path)
    return Model(model_dir)

def run_ffmpeg(cmd_args):
    # Safe execution
    result = subprocess.run(cmd_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode!= 0:
        raise RuntimeError(result.stderr.decode('utf-8', errors='ignore'))
    return result

def run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)

# Session State
if 'video_path' not in st.session_state: st.session_state.video_path = None
if 'full_text' not in st.session_state: st.session_state.full_text = ""
if 'final_dub_video' not in st.session_state: st.session_state.final_dub_video = None

tab1, tab2, tab3 = st.tabs(["📹 1. Upload & Transcribe", "📝 2. Rewrite & Translate", "🎙️ 3. Dubbing & Video Merge"])

# ================= TAB 1 =================
with tab1:
    st.markdown("### 📹 Video သို့မဟုတ် Audio File တင်ပါ")
    uploaded_file = st.file_uploader("MP4, MKV, MOV, MP3, WAV", type=['mp4','mkv','mov','mp3','wav'])

    if uploaded_file:
        suffix = os.path.splitext(uploaded_file.name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.getbuffer())
            st.session_state.video_path = tmp.name

        if suffix in ['.mp4','.mkv','.mov']:
            st.video(st.session_state.video_path)
        else:
            st.audio(st.session_state.video_path)

        if st.button("🎙️ စာသား စတင်ထုတ်မည်", type="primary", use_container_width=True):
            if not shutil.which("ffmpeg"):
                st.error("❌ FFmpeg မရှိပါ။ packages.txt ထဲမှာ ffmpeg ထည့်ပေးပါ။")
            else:
                with st.spinner("တရုတ်စာသားအဖြစ် ပြောင်းလဲနေပါသည်..."):
                    wav_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
                    try:
                        run_ffmpeg(["ffmpeg", "-i", st.session_state.video_path, "-vn", "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le", "-y", wav_audio])

                        model = load_vosk_model()
                        wf = wave.open(wav_audio, "rb")
                        rec = KaldiRecognizer(model, wf.getframerate())

                        results = []
                        while True:
                            data = wf.readframes(8000)
                            if len(data) == 0: break
                            if rec.AcceptWaveform(data):
                                part = json.loads(rec.Result())
                                if part.get('text'):
                                    results.append(part['text'].replace(" ", ""))

                        final_res = json.loads(rec.FinalResult())
                        if final_res.get('text'):
                            results.append(final_res['text'].replace(" ", ""))

                        st.session_state.full_text = "\n".join(results)
                        if not results:
                            st.warning("⚠️ စာသား ထွက်မလာပါ။ အသံကြည်လင်မှု စစ်ပါ။")
                        else:
                            st.success(f"✅ စာသား {len(results)} ကြောင်း ရပါပြီ! TAB 2 မှာ သွားကြည့်ပါ။")
                            st.text(st.session_state.full_text)
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
                    finally:
                        if os.path.exists(wav_audio): os.remove(wav_audio)

# ================= TAB 2 =================
with tab2:
    st.markdown("### 📝 စာသား ပြင်ဆင်/ဘာသာပြန်ရန်")
    if not st.session_state.full_text:
        st.info("TAB 1 မှာ အရင် transcribe လုပ်ပါ။")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**မူရင်း Raw Text**")
        # full_text ကို တိုက်ရိုက်ပြမယ်
        st.text_area("Original", value=st.session_state.full_text, height=400, key="raw_text_display")

    with col_b:
        st.markdown("**မြန်မာဘာသာပြန် (တစ်ကြောင်းချင်းစီ)**")
        translated_input = st.text_area("Translated Burmese", height=400, placeholder="ဒီမှာ မြန်မာလို ရေးပါ...", key="translated_editor")

# ================= TAB 3 =================
with tab3:
    st.markdown("### 🎙️ Edge TTS & Video Merge")

    async def generate_long_tts(text, voice, output_path):
        # စာရှည်ရင် ခွဲပြီး ဆက်မယ်
        chunks = [text[i:i+2000] for i in range(0, len(text), 2000)]
        tmp_files = []
        for i, chunk in enumerate(chunks):
            if not chunk.strip(): continue
            tmp_mp3 = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{i}.mp3").name
            communicate = edge_tts.Communicate(chunk, voice)
            await communicate.save(tmp_mp3)
            tmp_files.append(tmp_mp3)

        # mp3 တွေကို ပေါင်းမယ်
        if len(tmp_files) == 1:
            shutil.move(tmp_files[0], output_path)
        else:
            list_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode='w', encoding='utf-8').name
            with open(list_file, 'w', encoding='utf-8') as f:
                for tf in tmp_files:
                    f.write(f"file '{tf}'\n")
            run_ffmpeg(["ffmpeg", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", "-y", output_path])
            os.remove(list_file)
            for tf in tmp_files:
                if os.path.exists(tf): os.remove(tf)

    col1, col2 = st.columns([2,1])
    with col1:
        base_voice = st.selectbox("🎭 အသံ", ["my-MM-ThihaNeural", "my-MM-NilarNeural"], format_func=lambda x: "Thiha - ယောက်ျားလေး" if "Thiha" in x else "Nilar - မိန်းကလေး")
    with col2:
        orig_vol = st.slider("🔇 မူရင်းအသံ %", 0, 100, 5)

    if st.button("🚀 Dubbing ထုတ်မည်", type="primary", use_container_width=True):
        translations = st.session_state.get("translated_editor", "").strip()
        if not translations:
            st.warning("⚠️ TAB 2 မှာ မြန်မာလို စာသားအရင် ရေးပါ။")
        elif not st.session_state.video_path:
            st.warning("⚠️ Video မတင်ရသေးပါ။")
        else:
            with st.spinner("အသံဖန်တီးပြီး Video ပေါင်းနေပါသည်..."):
                try:
                    dub_audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
                    run_async(generate_long_tts(translations, base_voice, dub_audio_path))

                    output_video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name

                    if orig_vol == 0:
                        cmd = ["ffmpeg", "-i", st.session_state.video_path, "-i", dub_audio_path, "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0", "-shortest", "-y", output_video_path]
                    else:
                        cmd = ["ffmpeg", "-i", st.session_state.video_path, "-i", dub_audio_path, "-filter_complex", f"[0:a]volume={orig_vol/100.0}[orig];[1:a]volume=1.0[dub];[orig][dub]amix=inputs=2:duration=longest", "-c:v", "copy", "-shortest", "-y", output_video_path]

                    run_ffmpeg(cmd)
                    st.session_state.final_dub_video = output_video_path
                    st.success("✅ ပြီးပါပြီ!")
                except Exception as e:
                    st.error(f"❌ Dubbing Error: {e}")
                finally:
                    if 'dub_audio_path' in locals() and os.path.exists(dub_audio_path):
                        os.remove(dub_audio_path)

    if st.session_state.final_dub_video and os.path.exists(st.session_state.final_dub_video):
        st.markdown("---")
        st.video(st.session_state.final_dub_video)
        with open(st.session_state.final_dub_video, 'rb') as f:
            st.download_button("📥 Download Dubbed Video", f.read(), "dubbed_video.mp4", "video/mp4", use_container_width=True)
