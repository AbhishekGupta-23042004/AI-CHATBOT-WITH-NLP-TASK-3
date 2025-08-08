import threading
import time
from datetime import datetime
from googlesearch import search
import wikipedia
import nltk
from nltk.stem import WordNetLemmatizer
import speech_recognition as sr
import comtypes.client
from tkinter import *
from tkinter import scrolledtext
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Download necessary NLTK data once (only first run)
nltk.download('punkt')
nltk.download('wordnet')

lemmatizer = WordNetLemmatizer()
speaker = comtypes.client.CreateObject("SAPI.SpVoice")

# Initialize sentiment analyzer
analyzer = SentimentIntensityAnalyzer()

# In-memory caches
query_cache = {}
more_info_cache = {}

def timestamp():
    return datetime.now().strftime("%H:%M:%S")

def speak(text, rate_offset=0):
    """
    Speak text via SAPI5. Optionally adjust rate for emotion.
    """
    try:
        speaker.Rate = rate_offset  # Rate: -10 slow, +10 fast; default 0
        speaker.Speak(text)
        speaker.Rate = 0  # Reset to normal after speaking
    except Exception as e:
        print("Speech synth error:", e)

def listen():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        audio = recognizer.listen(source)
    try:
        query = recognizer.recognize_google(audio)
        print(f"User said: {query}")
        return query
    except Exception as e:
        print("Speech recognition failed:", e)
        return ""

def get_wikipedia_answer(query):
    try:
        summary = wikipedia.summary(query, sentences=2)
        return summary
    except wikipedia.exceptions.DisambiguationError:
        return "Your query may refer to multiple things, please be more specific."
    except wikipedia.exceptions.PageError:
        return None
    except Exception as e:
        print("Wikipedia error:", e)
        return None

def get_google_topics(query):
    try:
        urls = list(search(query, num_results=3))
        if urls:
            topics = []
            for url in urls:
                parts = url.split('/')
                snippet = parts[2]
                if len(parts) > 3:
                    snippet += " - " + parts[3].replace('_', ' ').replace('-', ' ')
                topics.append(snippet)
            return topics
        else:
            return []
    except Exception as e:
        print("Google search error:", e)
        return []

def query_knowledge_base(query):
    if query.lower() in query_cache:
        return query_cache[query.lower()]
    
    result_container = {}

    def wiki_thread():
        result_container['wiki'] = get_wikipedia_answer(query)

    def google_thread():
        result_container['google'] = get_google_topics(query)

    t1 = threading.Thread(target=wiki_thread)
    t2 = threading.Thread(target=google_thread)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    if result_container.get('wiki'):
        ans = result_container['wiki']
    elif result_container.get('google'):
        topics = result_container['google']
        if topics:
            ans = "I couldn't find a Wikipedia summary, but here are some related topics:\n"
            for i, tpc in enumerate(topics, 1):
                ans += f"{i}. About {tpc}\n"
            ans += "\nYou can ask me to 'Tell me more about item X' to get details."
            more_info_cache[query.lower()] = topics
        else:
            ans = "Sorry, I couldn't find relevant information."
    else:
        ans = "Sorry, I couldn't find relevant information."

    query_cache[query.lower()] = ans
    return ans

def handle_more_info_request(user_msg):
    words = user_msg.lower().split()
    idx = None
    for i, w in enumerate(words):
        if w == "item" and i+1 < len(words):
            try:
                idx = int(words[i+1])
                break
            except ValueError:
                pass
    if idx is None:
        return None

    if not more_info_cache:
        return "Sorry, I don't have any topics to give more info about."
    
    last_query = list(more_info_cache.keys())[-1]
    topics = more_info_cache[last_query]
    if 1 <= idx <= len(topics):
        topic_name = topics[idx-1]
        wiki_summary = get_wikipedia_answer(topic_name)
        if wiki_summary:
            return wiki_summary
        else:
            return f"Sorry, I couldn't find detailed info for '{topic_name}'."
    else:
        return f"Invalid item number {idx}. Please choose between 1 and {len(topics)}."

def check_basic_phrases(user_msg):
    msg = user_msg.lower()
    greetings = ["hi", "hello", "hey", "good morning", "good evening"]
    thanks = ["thank you", "thanks", "thx"]
    bye = ["bye", "goodbye", "see you"]

    for greet in greetings:
        if greet in msg:
            return "Hello! How can I help you today?"
    for t in thanks:
        if t in msg:
            return "You're welcome! Feel free to ask me anything."
    for b in bye:
        if b in msg:
            return "Goodbye! Have a great day!"
    return None

def detect_user_emotion(text):
    vs = analyzer.polarity_scores(text)
    compound = vs['compound']
    if compound >= 0.5:
        return 'positive'
    elif compound <= -0.5:
        return 'negative'
    else:
        return 'neutral'

def get_emotional_response(user_msg, base_response):
    emotion = detect_user_emotion(user_msg)
    # Append some empathetic phrases based on emotion
    if emotion == 'positive':
        extra = "😊 I'm glad you feel good! Let me help you."
        rate = 2  # Slightly faster speech
    elif emotion == 'negative':
        extra = "🙏 I'm sorry to hear that. I'll do my best to assist you."
        rate = -2  # Slightly slower/sympathetic speech
    else:
        extra = ""
        rate = 0
    return base_response + extra, rate

def get_response(user_msg):
    # Check polite phrases
    phrase_reply = check_basic_phrases(user_msg)
    if phrase_reply:
        return phrase_reply, 0
    
    # Check for follow-up "Tell me more about item X"
    if "tell me more about item" in user_msg.lower():
        more_info = handle_more_info_request(user_msg)
        return more_info, 0

    base_reply = query_knowledge_base(user_msg)
    emotional_reply, rate = get_emotional_response(user_msg, base_reply)
    return emotional_reply, rate

# GUI and threading

def threaded_search(user_msg):
    def run():
        chat_log.config(state=NORMAL)
        chat_log.insert(END, f"Astra is typing...\n")
        chat_log.see(END)
        chat_log.config(state=DISABLED)

        response, rate = get_response(user_msg)
        time.sleep(0.7)  # Simulate thinking delay

        chat_log.config(state=NORMAL)
        chat_log.delete("end-2l", "end-1l")
        chat_log.insert(END, f"Astra [{timestamp()}]: {response}\n\n")
        chat_log.config(state=DISABLED)
        chat_log.see(END)
        speak(response, rate)
    threading.Thread(target=run, daemon=True).start()

def send_message(event=None):
    user_msg = chat_box.get("1.0", END).strip()
    if not user_msg or user_msg == "Type your message here...":
        return
    chat_log.config(state=NORMAL)
    chat_log.insert(END, f"You [{timestamp()}]: {user_msg}\n")
    chat_log.config(state=DISABLED)
    chat_log.see(END)
    chat_box.delete("1.0", END)
    threaded_search(user_msg)

def voice_input():
    query = listen()
    if query:
        chat_box.delete("1.0", END)
        chat_box.insert(END, query)
        send_message()

# GUI setup
root = Tk()
root.title("Astra - AI Chatbot with Emotion & Voice")
root.geometry("700x550")
root.minsize(600, 450)
root.configure(bg="#2c3e50")

chat_log = scrolledtext.ScrolledText(
    root,
    bg="#34495e",
    fg="#ecf0f1",
    font=("Segoe UI", 12),
    wrap=WORD,
    state=DISABLED,
)
chat_log.pack(padx=15, pady=10, fill=BOTH, expand=True)

chat_box_label = Label(
    root,
    text="Enter your message:",
    bg="#2c3e50",
    fg="#ecf0f1",
    font=("Segoe UI", 10, "italic")
)
chat_box_label.pack(anchor='w', padx=15)

chat_box = Text(
    root,
    height=3,
    bg="#34495e",
    fg="#ecf0f1",
    font=("Segoe UI", 12),
    wrap=WORD,
    insertbackground="#ecf0f1",
    relief="sunken",
    bd=2
)
chat_box.pack(padx=15, pady=(0, 10), fill=X)
chat_box.focus_set()

def add_placeholder(event):
    if chat_box.get("1.0", END).strip() == "":
        chat_box.insert("1.0", "Type your message here...")

def clear_placeholder(event):
    if chat_box.get("1.0", END).strip() == "Type your message here...":
        chat_box.delete("1.0", END)

chat_box.insert("1.0", "Type your message here...")
chat_box.bind("<FocusIn>", clear_placeholder)
chat_box.bind("<FocusOut>", add_placeholder)

btn_frame = Frame(root, bg="#2c3e50")
btn_frame.pack(padx=15, pady=(0, 15), fill=X)

send_btn = Button(
    btn_frame,
    text="Send",
    bg="#27ae60",
    fg="white",
    font=("Segoe UI", 11),
    command=send_message,
    relief=FLAT,
    width=10,
    cursor="hand2"
)
send_btn.pack(side=LEFT, padx=(0, 10))

voice_btn = Button(
    btn_frame,
    text="Speak",
    bg="#2980b9",
    fg="white",
    font=("Segoe UI", 11),
    command=voice_input,
    relief=FLAT,
    width=10,
    cursor="hand2"
)
voice_btn.pack(side=LEFT)

def enter_pressed(event):
    if event.state & 0x0001:  # Shift pressed?
        return
    else:
        send_message()
        return "break"

chat_box.bind("<Return>", enter_pressed)

chat_log.config(state=NORMAL)
chat_log.insert(END, f"Astra [{timestamp()}]: Hello! I am your AI assistant Astra. Ask me anything.\n\n")
chat_log.config(state=DISABLED)

root.mainloop()
