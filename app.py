import streamlit as st

st.title("test")
st.write("hello")

try:
    import assemblyai, edge_tts
    from google import genai
    st.success("imports ok")
except Exception as e:
    st.exception(e)

t1, t2 = st.tabs(["a", "b"])
with t1:
    st.write("tab a")
