"""
brain.py
========
This is your ORIGINAL assistant's intelligence, with every OS-specific
piece surgically removed. Compare this file to your original script as
you read it — notice what's GONE:

  - speak()              -> DELETED. Functions now RETURN text instead
                             of speaking it. The browser decides how to
                             voice it (Web Speech API), not Python.
  - listen()              -> DELETED. The browser's mic feeds text INTO
                             these functions as a parameter; Python never
                             touches a microphone.
  - os.startfile(...)      -> DELETED. A server cannot open an app on a
                             stranger's computer (and shouldn't be able to
                             - imagine if any website could do that).
  - screen_brightness_*    -> DELETED. Can't control a stranger's screen.
  - subprocess volume hack -> DELETED. Can't control a stranger's PC audio.
  - SETTINGS as one global  -> CHANGED. Settings are now passed IN per
    JSON file                 request (per-user), not one shared file.
                             (We wire this to a real per-user DB in the
                             next ring - for now it's passed as a dict.)

Every function below takes plain Python values in, returns plain Python
values out. No side effects on "the machine" - because there IS no single
machine anymore. There's a server, and there's whoever is visiting it.
"""

import os
import re
import json
import math
import datetime
import requests as req

# ============================================================
#   API KEYS  (server-side only - NEVER sent to the browser)
# ============================================================

GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "")
NVIDIA_API_KEY  = os.getenv("NVIDIA_API_KEY", "")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")

GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"


# ============================================================
#   WORD NUMBERS & MATH  (unchanged from your original - pure logic)
# ============================================================

WORD_NUMBERS = {
    "zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,
    "six":6,"seven":7,"eight":8,"nine":9,"ten":10,
    "eleven":11,"twelve":12,"thirteen":13,"fourteen":14,
    "fifteen":15,"sixteen":16,"seventeen":17,"eighteen":18,
    "nineteen":19,"twenty":20,"thirty":30,"forty":40,
    "fifty":50,"sixty":60,"seventy":70,"eighty":80,
    "ninety":90,"hundred":100,"thousand":1000,"million":1000000
}

MATH_WORDS = [
    "plus","minus","times","divided","multiplied","into","power",
    "root","percent","factorial","sine","cosine","tangent","log","pi",
    "sin","cos","tan","sqrt","ln","squared","cubed","half","double",
    "triple","mod","modulo","remainder","raised","negative","subtract",
    "add","multiply","divide","over","+","-","*","/"
]


def extract_number(text):
    text = text or ""
    match = re.search(r'(\d+)', text)
    if match:
        return int(match.group(1))
    for word, value in sorted(WORD_NUMBERS.items(), key=lambda x: len(x[0]), reverse=True):
        if word in text.lower():
            return value
    return None


def convert_word_numbers(text):
    operator_words = ["plus","minus","times","into","multiplied by","divided by","to the power of"]
    tokens = re.split(
        r'(\bplus\b|\bminus\b|\btimes\b|\binto\b|\bmultiplied by\b|\bdivided by\b|\bto the power of\b)',
        text
    )
    result = []
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        if token in operator_words:
            result.append(token)
        else:
            chunk = token
            for word, value in sorted(WORD_NUMBERS.items(), key=lambda x: len(x[0]), reverse=True):
                if word in chunk:
                    chunk = chunk.replace(word, str(value), 1)
            result.append(chunk)
    return " ".join(result)


def clean_ai_text(text):
    text = re.sub(r'\*+',  '', text)
    text = re.sub(r'#+',   '', text)
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def strip_question_prefixes(query):
    q = (query or "").lower().strip()
    prefixes = sorted([
        "who is","who was","who were","who are",
        "what is","what was","what are","what's",
        "what does","what do","where is","where was",
        "when is","when was","when did","how is",
        "how does","how do","how did","how many","how much",
        "why is","why was","why did",
        "tell me about","tell me","define",
        "definition of","look up","find out about",
        "give me info on","can you tell me about",
        "i want to know about","explain to me","explain",
        "full form of","full form","abbreviation of",
        "meaning of","means","stands for",
        "do you know about","search for","find",
    ], key=len, reverse=True)
    for phrase in prefixes:
        if q.startswith(phrase):
            q = q[len(phrase):].strip()
            break
    for article in ["the ", "a ", "an "]:
        if q.startswith(article):
            q = q[len(article):].strip()
    return q if q else query


# ============================================================
#   NLP SYSTEM PROMPT  (trimmed: removed intents that no longer
#   make sense on a server - volume/brightness/open_app/change-of-
#   wake-word, etc. We'll re-add app-relevant ones as we go)
# ============================================================

NLP_SYSTEM_PROMPT = """
You are the brain of a web-based AI voice assistant called Sky.
The user will say something and you must figure out what they want.

Reply ONLY with a valid JSON object - nothing else.
No explanation, no preamble, no markdown. Just raw JSON.

JSON structure:
{
  "intent":     "<intent>",
  "topic":      "<search topic or question, else null>",
  "city":       "<city name if weather, else null>",
  "task":       "<reminder or note content, else null>",
  "time":       "<reminder time e.g. 3 pm, else null>",
  "duration":   "<timer duration e.g. 5 minutes, else null>",
  "expression": "<math expression, else null>",
  "reply":      "<short friendly reply for small talk, else null>"
}

Valid intents:
- greeting
- how_are_you
- name
- time
- date
- time_and_date
- reminder_set
- reminder_show
- timer
- note_take
- note_show
- calculate
- weather
- ask            (general knowledge: who is, what is, explain, define, news)
- joke
- small_talk
- unknown
"""


def understand_command(command):
    """
    Calls Groq first, falls back to NVIDIA, falls back to keyword
    matching. IDENTICAL strategy to your original - this part needed
    almost no changes, because it never touched the OS in the first
    place. This is the proof that your intent-detection logic was
    always portable; it was speak()/listen() that weren't.
    """
    try:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": NLP_SYSTEM_PROMPT},
                {"role": "user", "content": "User said: " + command}
            ],
            "temperature": 0.1,
            "max_tokens": 300
        }
        response = req.post(GROQ_URL, headers=headers, json=payload, timeout=8)
        data = response.json()
        if "error" in data:
            raise Exception(data["error"].get("message", str(data["error"])))
        raw = data["choices"][0]["message"]["content"].strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"Groq failed: {e}")

    try:
        headers = {"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "meta/llama-3.3-70b-instruct",
            "messages": [
                {"role": "system", "content": NLP_SYSTEM_PROMPT},
                {"role": "user", "content": "User said: " + command}
            ],
            "temperature": 0.1,
            "max_tokens": 300
        }
        response = req.post(NVIDIA_URL, headers=headers, json=payload, timeout=8)
        data = response.json()
        if "choices" in data:
            raw = data["choices"][0]["message"]["content"].strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            return json.loads(raw)
    except Exception as e:
        print(f"NVIDIA intent failed: {e}")

    return fallback_understand(command)


def fallback_understand(command):
    """
    NOTE on ordering: specific/deterministic intents (time, date,
    reminders, timers, calculator) are checked BEFORE the generic
    'knowledge question' catch-all. This matters because phrases like
    "what is the time" legitimately start with "what is" - if the
    knowledge check ran first, it would steal every time/date/etc.
    query and send it to the LLM instead of our fast deterministic
    handler. Always order keyword fallbacks from most-specific to
    most-generic.
    """
    c = command.lower()

    if any(w in c for w in ["hello","hi there","hey"]):
        return {"intent": "greeting"}
    elif "how are you" in c:
        return {"intent": "how_are_you"}
    elif "your name" in c:
        return {"intent": "name"}
    elif re.search(r'\btime\b', c) and "date" in c:
        return {"intent": "time_and_date"}
    elif re.search(r'\btime\b', c) and "timer" not in c:
        return {"intent": "time"}
    elif "date" in c:
        return {"intent": "date"}
    elif ("show" in c or "list" in c) and "reminder" in c:
        return {"intent": "reminder_show"}
    elif "reminder" in c or "remind me" in c:
        return {"intent": "reminder_set", "task": None, "time": None}
    elif "timer" in c:
        return {"intent": "timer", "duration": c}
    elif ("show" in c or "read" in c) and "note" in c:
        return {"intent": "note_show"}
    elif any(p in c for p in ["take a note","make a note","note down","save note"]):
        return {"intent": "note_take", "task": c}
    elif "calculate" in c or (any(w in c for w in MATH_WORDS) and any(ch.isdigit() for ch in c)):
        return {"intent": "calculate", "expression": c}
    elif "weather" in c:
        city = c.split("in")[-1].strip() if "in" in c else None
        return {"intent": "weather", "city": city}
    elif "joke" in c:
        return {"intent": "joke"}
    elif any(t in c for t in [
        "who is","who was","what is","what was","what are","what's",
        "where is","when is","when was","how does","how many","how much",
        "why is","tell me about","define","full form","abbreviation",
        "meaning of","stands for","explain","look up","find out",
        "news about","latest news","what is happening","updates on"
    ]):
        return {"intent": "ask", "topic": c}
    else:
        return {"intent": "unknown"}


# ============================================================
#   ASK GROQ / NVIDIA  (returns text instead of speaking it)
# ============================================================

def ask_groq(prompt, system=(
    "You are a helpful voice assistant. "
    "Answer in 2 clear natural spoken sentences. "
    "No markdown, no bullet points, no asterisks, no symbols, no numbering."
)):
    try:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 200
        }
        response = req.post(GROQ_URL, headers=headers, json=payload, timeout=10)
        data = response.json()
        if "choices" not in data:
            return None
        answer = clean_ai_text(data["choices"][0]["message"]["content"])
        return answer if answer and len(answer) > 10 else None
    except Exception as e:
        print(f"GROQ error: {e}")
        return None


def ask_nvidia(prompt):
    try:
        headers = {"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "meta/llama-3.3-70b-instruct",
            "messages": [
                {"role": "system", "content": (
                    "You are a helpful voice assistant. Answer in 2 clear natural "
                    "spoken sentences. No markdown, no bullet points, no symbols."
                )},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 200
        }
        response = req.post(NVIDIA_URL, headers=headers, json=payload, timeout=10)
        data = response.json()
        if "choices" not in data:
            return None
        answer = clean_ai_text(data["choices"][0]["message"]["content"])
        return answer if answer and len(answer) > 10 else None
    except Exception as e:
        print(f"NVIDIA answer error: {e}")
        return None


def answer_question(query):
    """
    CHANGED: original would open Chrome as a last resort
    (subprocess.Popen on the SERVER - useless to a remote user).
    Now we just return a plain failure message; the frontend can
    decide to offer a "search the web" link if it wants.
    """
    q = strip_question_prefixes(query)
    if not q:
        return "What would you like to know about?"
    answer = ask_groq(q)
    if answer:
        return answer
    answer = ask_nvidia(q)
    if answer:
        return answer
    return f"Sorry, I could not find a good answer for {q}."


# ============================================================
#   CALCULATOR  (pure logic, returns string instead of speaking)
# ============================================================

def calculate(expression):
    try:
        for prefix in ["calculate","compute","solve","what's","what is",
                       "how much is","how much","tell me","find","give me"]:
            expression = expression.replace(prefix, "")
        expression = expression.replace(" the ", " ").strip()
        if not expression:
            return "What would you like me to calculate?"

        expression = convert_word_numbers(expression)
        expression = re.sub(r'(\d+)\s*point\s*(\d+)', r'\1.\2', expression)
        e = expression.strip()

        if e in ("pi", "value of pi"):
            return f"Pi is approximately {round(math.pi, 5)}"
        if e in ("e", "value of e", "euler", "eulers number"):
            return f"Euler's number is approximately {round(math.e, 5)}"
        if re.search(r'square root of|square root|sqrt', expression):
            n = float(re.sub(r'square root of|square root|sqrt', '', expression).strip())
            return f"Square root of {n} is {round(math.sqrt(n), 4)}"
        if re.search(r'cube root of|cube root', expression):
            n = float(re.sub(r'cube root of|cube root', '', expression).strip())
            return f"Cube root of {n} is {round(n ** (1/3), 4)}"
        if "squared" in expression:
            n = float(expression.replace("squared", "").strip())
            return f"{n} squared is {round(n**2, 4)}"
        if "cubed" in expression:
            n = float(expression.replace("cubed", "").strip())
            return f"{n} cubed is {round(n**3, 4)}"
        if "factorial" in expression:
            n = int(re.sub(r'factorial of|factorial', '', expression).strip())
            return f"Factorial of {n} is {math.factorial(n)}"
        if "percent of" in expression:
            parts = expression.split("percent of")
            pct, total = float(parts[0].strip()), float(parts[1].strip())
            return f"{pct} percent of {total} is {round((pct/100)*total, 2)}"

        expression = (expression
            .replace("multiplied by", "*").replace("multiply by", "*")
            .replace("divided by", "/").replace("divide by", "/")
            .replace("to the power of", "**").replace("to the power", "**")
            .replace("raised to", "**").replace("power", "**")
            .replace("plus", "+").replace("add", "+")
            .replace("minus", "-").replace("subtract", "-")
            .replace("times", "*").replace("multiply", "*")
            .replace("into", "*").replace("divide", "/")
            .replace("over", "/")
        )
        expression = re.sub(r'\bx\b', '*', expression)
        expression = re.sub(r'\bby\b', '/', expression)
        expression = re.sub(r'\band\b', '+', expression)
        expression = re.sub(r'\bnegative\b', '-', expression)
        expression = re.sub(r'[^0-9+\-*/.()\s]', '', expression)
        expression = re.sub(r'\s+', ' ', expression).strip()

        if not expression:
            return "Sorry, I could not understand the math expression!"

        result = round(eval(expression), 4)
        if result == int(result):
            result = int(result)
        return f"The answer is {result}"

    except ZeroDivisionError:
        return "Sorry, you cannot divide by zero!"
    except Exception as e:
        print(f"Calc error: {e}")
        return "Sorry, I could not calculate that!"


# ============================================================
#   WEATHER  (pure logic, returns string instead of speaking)
# ============================================================

def get_weather(city, default_city="Thrissur"):
    target = city if city else default_city
    try:
        response = req.get(
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?q={target}&appid={WEATHER_API_KEY}&units=metric",
            timeout=5
        )
        data = response.json()
        if data.get("cod") != 200:
            return f"Sorry, I could not find weather data for {target}."

        temp = round(data["main"]["temp"])
        feels_like = round(data["main"]["feels_like"])
        condition = data["weather"][0]["description"]
        main_weather = data["weather"][0]["main"].lower()
        humidity = data["main"]["humidity"]
        wind_speed = round(data.get("wind", {}).get("speed", 0) * 3.6)

        feels_part = f", though it feels more like {feels_like}" if abs(feels_like - temp) >= 2 else ""

        if wind_speed < 5: wind_part = "Winds are calm."
        elif wind_speed < 20: wind_part = f"A light breeze at {wind_speed} kilometres per hour."
        elif wind_speed < 40: wind_part = f"It is a bit windy at {wind_speed} kilometres per hour."
        else: wind_part = f"Strong winds at {wind_speed} kilometres per hour, be careful outside."

        if humidity > 80: humidity_part = f"Humidity is high at {humidity} percent, it might feel sticky."
        elif humidity > 60: humidity_part = f"Humidity is moderate at {humidity} percent."
        elif humidity > 30: humidity_part = f"Humidity is comfortable at {humidity} percent."
        else: humidity_part = f"The air is quite dry at {humidity} percent humidity."

        if "thunderstorm" in main_weather: advice = "There is a thunderstorm, best to stay indoors."
        elif "rain" in main_weather or "drizzle" in main_weather: advice = "You might want to grab an umbrella before heading out."
        elif "snow" in main_weather: advice = "It is snowing! Bundle up warm."
        elif any(w in main_weather for w in ["fog","mist","haze"]): advice = "Visibility is low, drive carefully."
        elif temp >= 38: advice = "It is extremely hot. Stay hydrated!"
        elif temp >= 33: advice = "Quite hot outside, drink plenty of water."
        elif temp >= 28: advice = "Nice and warm, great weather to be outdoors."
        elif temp >= 20: advice = "Pleasant weather, enjoy the day!"
        elif temp >= 10: advice = "A bit cool, a light jacket would be a good idea."
        elif temp >= 0: advice = "It is cold, dress warmly!"
        else: advice = "It is freezing out there, bundle up well!"

        return (f"It is currently {temp} degrees{feels_part}, with {condition}. "
                f"{wind_part} {humidity_part} {advice}")

    except Exception as e:
        print(f"Weather error: {e}")
        return "Sorry, I could not get the weather right now!"


# ============================================================
#   TIME / DATE / JOKES  (trivial pure functions)
# ============================================================

import random

JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs!",
    "Why did the computer go to the doctor? Because it had a virus!",
    "What do you call a computer that sings? A Dell!",
    "Why do Java developers wear glasses? Because they don't C sharp!",
    "How many programmers does it take to change a light bulb? None, that is a hardware problem!",
    "Why was the computer cold? It left its Windows open!",
    "Why did the programmer quit his job? Because he did not get arrays!",
    "What is a computer's favourite snack? Microchips!"
]

def get_time():
    return f"The current time is {datetime.datetime.now().strftime('%I:%M %p')}."

def get_date():
    return f"Today is {datetime.datetime.now().strftime('%B %d %Y')}."

def get_time_and_date():
    now = datetime.datetime.now()
    return f"Today is {now.strftime('%B %d %Y')} and the time is {now.strftime('%I:%M %p')}."

def get_joke():
    return random.choice(JOKES)
