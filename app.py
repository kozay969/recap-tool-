import streamlit as st
import edge_tts
import asyncio
import tempfile
import os
import shutil
import assemblyai as aai

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

# Sidebar for AssemblyAI API Key
st.sidebar.title("⚙️ Settings")
aai_key = st.sidebar.text_input("🔑 AssemblyAI API Key ထည့်ပါ", type="password")
st.sidebar.markdown("[AssemblyAI Dashboard မှ API Key ယူရန်](https://www.assemblyai.com)")

tab1, tab2, tab3 = st.tabs(["📹 1. Upload & Transcribe", "📝 2. Translate Text", "🎙️ 3. Dubbing & Video Merge"])

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
        ["zh (Chinese - တရုတ်)", "en (English - အင်္ဂလိပ်)", "Auto Detect (အလိုအလျောက်ဖတ်ရန်)"]
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

        if st.button("🎙️ Transcribe စတင်ထုတ်မည်", type="primary", use_container_width=True):
            if not aai_key:
                st.error("❌ ဘယ်ဘက် Sidebar တွင် AssemblyAI API Key အရင်ထည့်သွင်းပေးပါ။")
            elif not shutil.which("ffmpeg"):
                st.error("❌ FFmpeg System Path တွင် မရှိပါ။ packages.txt ကို စစ်ဆေးပါ။")
            else:
                with st.spinner("AssemblyAI ဖြင့် အသံမှ စာသားအဖြစ် ပြောင်းလဲနေပါသည်..."):
                    extracted_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
                    os.system(f'ffmpeg -i "{st.session_state.video_path}" -vn -ar 16000 -ac 1 -ab 128k -f mp3 -y "{extracted_audio}"')

                    try:
                        aai.settings.api_key = aai_key

                        lang_code = None
                        if "zh" in lang_choice:
                            lang_code = "zh"
                        elif "en" in lang_choice:
                            lang_code = "en"

                        config = aai.TranscriptionConfig(
                            language_code=lang_code if lang_code else None,
                            language_detection=True if not lang_code else False
                        )

                        transcriber = aai.Transcriber()
                        transcript = transcriber.transcribe(extracted_audio, config=config)

                        parsed_segments = []
                        full_text_list = []

                        if transcript.status == aai.TranscriptStatus.error:
                            st.error(f"❌ Transcribe Error: {transcript.error}")
                        else:
                            sentences = transcript.get_sentences()
                            if sentences:
                                for sent in sentences:
                                    txt = sent.text.strip()
                                    if txt:
                                        parsed_segments.append({
                                            "start": round(sent.start / 1000.0, 2),
                                            "end": round(sent.end / 1000.0, 2),
                                            "text": txt
                                        })
                                        full_text_list.append(txt)

                            st.session_state.transcript_data = parsed_segments
                            st.session_state.full_text = "\n".join(full_text_list)

                            if len(full_text_list) == 0:
                                st.warning("⚠️ စာသား ထွက်မလာပါ။ မူရင်း Video တွင် အသံပါဝင်မှု စစ်ဆေးပါ။")
                            else:
                                st.success(f"✅ စာသား {len(full_text_list)} ကြောင်း အောင်မြင်စွာ ထွက်လာပါပြီ! TAB 2 သို့ သွားပါ။")

                    except Exception as e:
                        st.error(f"❌ AssemblyAI API Error: {str(e)}")

                    finally:
                        if os.path.exists(extracted_audio):
                            os.remove(extracted_audio)

# ================= TAB 2 : Plain Text Translate =================
with tab2:
    st.markdown("### 📝 စကားပြောများ ဘာသာပြန်ဆိုရန်")
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**မူရင်း ထုတ်ယူထားသော စာသားများ (Raw Transcripts)**")
        st.text_area("Original Text", st.session_state.full_text, height=350, key="raw_text")

    with col_b:
        st.markdown("**မြန်မာဘာသာပြန် စာသားများ ထည့်သွင်းရန် (တစ်ကြောင်းစီ ရေးပါ)**")
        translated_input = st.text_area(
            "Translated Burmese Text", 
            value="", 
            height=350, 
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

    if st.button("🚀 Video နှင့် အသံကို Time-Sync လုပ်၍ Dubbing ထုတ်မည်", type="primary", use_container_width=True):
        translations = [line.strip() for line in st.session_state.translated_editor.split('\n') if line.strip()]

        if not translations:
            st.warning("⚠️ ဖတ်ရန် စာသားမရှိပါ။ TAB 2 တွင် မြန်မာဘာသာပြန် ရေးထည့်ပါ။")
        elif not st.session_state.video_path:
            st.warning("⚠️ Video Upload မတင်ရသေးပါ။ TAB 1 တွင် Upload တင်ပါ။")
        elif len(translations) != len(st.session_state.transcript_data):
            st.error(f"❌ စာကြောင်း အရေအတွက် မတူပါ (Original: {len(st.session_state.transcript_data)} ကြောင်း, Translated: {len(translations)} ကြောင်း)။ စာကြောင်းအရေအတွက် ညီအောင် ပြင်ပေးပါ။")
        else:
            with st.spinner("စာကြောင်းတစ်ကြောင်းချင်းစီ၏ Timing ကို တွက်ချက်၍ Video နှင့် အပြိုင်ညှိနေပါသည်..."):
                filter_complex_parts = []
                temp_files = []

                for idx, (seg, text) in enumerate(zip(st.session_state.transcript_data, translations)):
                    start_ms = int(seg['start'] * 1000)

                    tts_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
                    temp_files.append(tts_tmp)

                    run_async(generate_single_tts(text, base_voice, tts_tmp))

                    filter_complex_parts.append(
                        f"[{idx+1}:a]adelay={start_ms}|{start_ms}[a{idx}]"
                    )

                amix_inputs = "".join([f"[a{i}]" for i in range(len(translations))])
                filter_complex_str = ";".join(filter_complex_parts) + f";{amix_inputs}amix=inputs={len(translations)}:dropout_transition=0[dubbed_audio]"

                orig_v_vol = orig_vol / 100.0
                if orig_vol > 0:
                    filter_complex_str += f";[0:a]volume={orig_v_vol}[orig];[orig][dubbed_audio]amix=inputs=2:duration=first[final_audio]"
                    map_audio = "[final_audio]"
                else:
                    map_audio = "[dubbed_audio]"

                inputs_cmd = f'-i "{st.session_state.video_path}" ' + " ".join([f'-i "{f}"' for f in temp_files])
                output_video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name

                cmd = f'ffmpeg {inputs_cmd} -filter_complex "{filter_complex_str}" -map 0:v:0 -map {map_audio} -c:v copy -shortest -y "{output_video_path}"'
                os.system(cmd)

                for f in temp_files:
                    if os.path.exists(f): os.remove(f)

                st.session_state.final_dub_video = output_video_path
                st.success("✅ အသံနှင့် Video ကြာချိန် ကွက်တိ ညှိပြီးပါပြီ!")

    if 'final_dub_video' in st.session_state and st.session_state.final_dub_video and os.path.exists(st.session_state.final_dub_video):
        st.markdown("---")
        st.markdown("### 🎬 Final Synchronized Dubbed Video")
        st.video(st.session_state.final_dub_video)
        with open(st.session_state.final_dub_video, 'rb') as f:
            st.download_button("📥 Dubbed Video Download (MP4)", f.read(), "dubbed_video.mp4", "video/mp4", use_container_width=True)
