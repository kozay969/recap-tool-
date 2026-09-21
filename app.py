import streamlit as st
import edge_tts
import asyncio
import tempfile
import os
import json
import shutil
from faster_whisper import WhisperModel

# App configuration
st.set_page_config(page_title="Video Auto Dubbing & Localizer Pro", page_icon="🎬", layout="wide")
st.title("🎬 Video Auto Dubbing & Localizer Pro")

# Helper for Safe Async Execution inside Streamlit
def run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)

# Load Whisper Model (Cached for performance)
@st.cache_resource
def load_whisper_model(model_size="base"):
    return WhisperModel(model_size, device="cpu", compute_type="int8")

whisper_model = load_whisper_model("base")

tab1, tab2, tab3 = st.tabs(["📹 1. Upload & Transcribe", "📝 2. Rewrite & Translate", "🎙️ 3. Dubbing & Video Merge"])

if 'video_path' not in st.session_state: st.session_state.video_path = None
if 'transcript_data' not in st.session_state: st.session_state.transcript_data = []
if 'full_text' not in st.session_state: st.session_state.full_text = ""
if 'final_dub_audio' not in st.session_state: st.session_state.final_dub_audio = None

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

        if st.button("🎙️ Transcribe စတင်ထုတ်မည်", type="primary", use_container_width=True):
            if not shutil.which("ffmpeg"):
                st.error("❌ FFmpeg System Path တွင် မရှိပါ။")
            else:
                with st.spinner("Video မှ စကားပြောများကို ဖတ်ယူနေပါသည်..."):
                    segments, info = whisper_model.transcribe(st.session_state.video_path, beam_size=5)
                    parsed_segments = []
                    full_text_list = []

                    for seg in segments:
                        parsed_segments.append({
                            "start": round(seg.start, 2),
                            "end": round(seg.end, 2),
                            "text": seg.text.strip()
                        })
                        full_text_list.append(seg.text.strip())

                    st.session_state.transcript_data = parsed_segments
                    st.session_state.full_text = "\n".join(full_text_list)
                    st.success("✅ Transcribe ပြုလုပ်ပြီးပါပြီ! TAB 2 သို့ သွား၍ ပြင်ဆင်ပါ။")

# ================= TAB 2 : JSON Format & Rewrite =================
with tab2:
    st.markdown("### 📝 Text Rewrite & JSON Structure")
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**မူရင်း ထုတ်ယူထားသော စာသားများ (Raw Transcripts)**")
        st.text_area("Original Text", st.session_state.full_text, height=300, key="raw_text")

    with col_b:
        st.markdown("**JSON / Subtitle Translations ထည့်သွင်းရန်**")
        # Pre-fill JSON structure
        default_json = {
            "translations": [item["text"] for item in st.session_state.transcript_data] if st.session_state.transcript_data else []
        }
        json_input = st.text_area("JSON Input", json.dumps(default_json, ensure_ascii=False, indent=2), height=300, key="json_editor")

    st.info("💡 ဘာသာပြန်ထားသော စာသား သို့မဟုတ် Rewrite လုပ်ထားသော JSON စာကြောင်းများကို အထက်ပါ JSON Editor တွင် ပြင်ဆင်ပါ။")

# ================= TAB 3 : TTS & Video Merge =================
with tab3:
    st.markdown("### 🎙️ Edge TTS & Video Audio Replacement")

    def parse_style_prompt(prompt, speed_multiplier=1.0, echo_level=0):
        prompt = prompt.lower()
        filters = []
        effects = []
        pitch_rate = 1.0

        if any(w in prompt for w in ['ထူထူ', 'ထူ', 'နိမ့်', 'အဖိုးကြီး']):
            pitch_rate = 0.75
            filters.append("asetrate=44100*0.75,aresample=44100")
            effects.append("အသံထူထူ")
        elif any(w in prompt for w in ['စူးစူး', 'စူး', 'မြင့်', 'ကလေး']):
            pitch_rate = 1.3
            filters.append("asetrate=44100*1.3,aresample=44100")
            effects.append("အသံစူးစူး")

        final_speed = speed_multiplier
        if any(w in prompt for w in ['နှေး', 'နှေးနှေး']): final_speed *= 0.7
        elif any(w in prompt for w in ['မြန်', 'မြန်မြန်']): final_speed *= 1.4

        if pitch_rate != 1.0:
            tempo_fix = final_speed / pitch_rate
            filters.append(f"atempo={tempo_fix}")
        else:
            filters.append(f"atempo={final_speed}")

        if echo_level > 0:
            decay = echo_level / 100.0
            delay = int(250 + (echo_level * 10))
            filters.append(f"aecho=0.8:0.88:{delay}:{decay}")

        filter_str = ",".join(filters) if filters else "anull"
        return filter_str, " + ".join(effects)

    async def generate_tts(text, voice, filter_str):
        communicate = edge_tts.Communicate(text, voice)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            await communicate.save(tmp.name)
            raw_voice = tmp.name

        processed_voice = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
        os.system(f'ffmpeg -i "{raw_voice}" -af "{filter_str}" -y "{processed_voice}"')
        if os.path.exists(raw_voice): os.remove(raw_voice)
        return processed_voice

    col1, col2 = st.columns([2, 1])
    with col1:
        base_voice = st.selectbox(
            "🎭 အခြေခံအသံ",
            ["my-MM-ThihaNeural", "my-MM-NilarNeural"],
            format_func=lambda x: "Thiha - ယောက်ျားလေး" if "Thiha" in x else "Nilar - မိန်းကလေး"
        )
        style_prompt = st.text_area("✍️ အသံပုံစံ Prompt (Optional)", placeholder="ဥပမာ: အသံထူထူ၊ နှေးနှေး", height=60)

    with col2:
        speed = st.slider("⚡ အသံအမြန်နှုန်း", 0.5, 2.0, 1.0, 0.1)
        echo = st.slider("🔊 ပဲ့တင်သံ Level", 0, 100, 0, 5)
        orig_vol = st.slider("🔇 မူရင်း Video အသံပမာဏ (%)", 0, 100, 10, 5, help="0 ထားပါက မူရင်းအသံ လုံးဝပိတ်ပါမည်")

    if st.button("🚀 Video ကို အသံသစ်ဖြင့် Dubbing ထုတ်မည်", type="primary", use_container_width=True):
        # Extract text from JSON editor
        text_to_speak = ""
        try:
            parsed_json = json.loads(json_input)
            arr = parsed_json.get("translations", [])
            if isinstance(arr, list) and len(arr) > 0:
                text_to_speak = "\n".join(arr)
            else:
                text_to_speak = json_input
        except:
            text_to_speak = json_input

        if not text_to_speak.strip():
            st.warning("⚠️ ဖတ်ရန် စာသားမရှိပါ။ TAB 2 တွင် JSON/Text စစ်ဆေးပါ။")
        elif not st.session_state.video_path:
            st.warning("⚠️ Video Upload မတင်ရသေးပါ။ TAB 1 တွင် Upload တင်ပါ။")
        else:
            with st.spinner("အသံသစ် ထုတ်လုပ်ပြီး Video နှင့် ပေါင်းစပ်နေပါသည်..."):
                filter_str, _ = parse_style_prompt(style_prompt, speed, echo)
                dub_audio_path = run_async(generate_tts(text_to_speak, base_voice, filter_str))

                output_video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
                orig_v_vol = orig_vol / 100.0

                # FFmpeg Command to replace/mix video audio with new TTS
                if orig_vol == 0:
                    # Mute original audio completely
                    cmd = f'ffmpeg -i "{st.session_state.video_path}" -i "{dub_audio_path}" -c:v copy -map 0:v:0 -map 1:a:0 -shortest -y "{output_video_path}"'
                else:
                    # Mix original audio (reduced) with new TTS audio
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
