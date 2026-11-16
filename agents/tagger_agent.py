"""tagger_agent.py — TAGGER AGENT

Job: decide which shelf the link belongs on.

    tags      → 3–6 short lowercase keywords, e.g. ["python", "flask", "api"]
    category  → ONE category for the card

How it decides
--------------
  1. The AI (Groq, through llm_client) is shown ~50 built-in categories, each
     with a one-line description, PLUS the categories already used in your
     library, and picks the most specific one that fits.
  2. If truly nothing fits, the AI may CREATE a short new category
     (1–3 words, e.g. "Astrology" or "Robotics"). The agent checks the name is
     clean before accepting it, so any kind of link can be filed automatically.
  3. If the AI is unavailable, weighted keyword scoring picks from the
     built-in list (title words count more than body words).
"""

import re
import time
from collections import Counter

from agents import llm_client
from agents.base_agent import BaseAgent
from utils.helpers import truncate

# ---------------------------------------------------------------------------
# Built-in shelves: category → (what belongs there, offline keywords)
# ---------------------------------------------------------------------------
CATEGORY_GUIDE = {
    # ---------------- technology & computing ----------------
    "AI & Machine Learning": (
        "artificial intelligence, LLMs, chatbots, model training or inference, AI companies and platforms",
        ("artificial intelligence", "machine learning", "deep learning", "neural", "llm", "llms",
         "gpt", "chatgpt", "openai", "anthropic", "gemini", "inference", "open-weight", "model",
         "models", "transformer", "generative", "prompt", "ai", "computer vision", "nlp"),
    ),
    "Programming": (
        "code, programming languages, software development, frameworks, APIs, GitHub repositories",
        ("python", "javascript", "java", "typescript", "github", "repository", "code", "coding",
         "function", "compiler", "api", "framework", "flask", "django", "developer", "sdk",
         "library", "npm", "pip", "debug", "algorithm", "leetcode"),
    ),
    "Web Development": (
        "websites, HTML, CSS, frontend and backend web frameworks, hosting",
        ("html", "css", "frontend", "backend", "react", "next.js", "vue", "angular", "tailwind",
         "website", "web app", "node.js", "hosting", "domain", "wordpress"),
    ),
    "Data Science": (
        "data analysis, statistics, visualisation, SQL, databases, big data",
        ("data science", "data analysis", "analytics", "pandas", "numpy", "sql", "database",
         "statistics", "visualization", "dashboard", "big data", "tableau", "power bi", "excel"),
    ),
    "Cybersecurity": (
        "hacking, security vulnerabilities, privacy, malware, ethical hacking",
        ("cybersecurity", "security", "hacking", "hacker", "vulnerability", "malware",
         "ransomware", "phishing", "encryption", "firewall", "cve", "exploit", "penetration"),
    ),
    "Technology": (
        "gadgets, smartphones, laptops, consumer tech, cloud, internet services, tech industry",
        ("smartphone", "phone", "laptop", "gadget", "cloud", "software", "hardware", "internet",
         "app", "device", "tech", "chip", "processor", "5g", "iphone", "android"),
    ),
    "Engineering": (
        "mechanical, civil, electrical, electronics engineering, IoT, robotics, embedded systems",
        ("engineering", "mechanical", "civil", "electrical", "electronics", "circuit", "iot",
         "robotics", "robot", "embedded", "arduino", "raspberry", "sensor", "cad", "vlsi"),
    ),
    # ---------------- science & knowledge ----------------
    "Science": (
        "physics, chemistry, biology and general scientific research",
        ("physics", "chemistry", "biology", "quantum", "experiment", "hypothesis", "scientists",
         "molecule", "genome", "laboratory", "research"),
    ),
    "Space & Astronomy": (
        "space missions, planets, stars, rockets, NASA, ISRO, astronomy",
        ("space", "nasa", "isro", "spacex", "rocket", "planet", "mars", "moon", "galaxy",
         "telescope", "astronomy", "satellite", "orbit", "astronaut"),
    ),
    "Mathematics": (
        "maths topics, problems, proofs, calculus, algebra, statistics theory",
        ("mathematics", "math", "maths", "calculus", "algebra", "geometry", "theorem",
         "equation", "probability", "matrix", "integral"),
    ),
    "Agriculture": (
        "farming, crops, soil, irrigation, livestock, plant disease, agricultural research",
        ("agriculture", "agricultural", "farming", "farmer", "farmers", "crop", "crops", "soil",
         "irrigation", "harvest", "yield", "livestock", "fertilizer", "pesticide", "plantation",
         "seed", "seeds", "paddy", "wheat", "plant disease", "agronomy", "greenhouse", "dairy"),
    ),
    "Environment": (
        "climate change, pollution, conservation, sustainability, wildlife protection",
        ("climate", "pollution", "environment", "carbon", "wildlife", "conservation",
         "emissions", "sustainability", "forest", "recycling", "global warming"),
    ),
    "Energy": (
        "solar, wind, electricity, oil and gas, batteries, renewable energy",
        ("energy", "solar", "wind power", "renewable", "electricity", "battery", "batteries",
         "oil", "gas", "nuclear", "power plant", "grid", "hydrogen"),
    ),
    "History": (
        "historical events, ancient civilisations, wars, biographies of historical figures",
        ("history", "historical", "ancient", "empire", "war", "dynasty", "medieval", "century",
         "civilization", "freedom struggle", "independence"),
    ),
    # ---------------- health & life ----------------
    "Health & Medicine": (
        "diseases, treatments, medicine, doctors, hospitals, public health",
        ("health", "medical", "medicine", "doctor", "hospital", "disease", "symptom", "symptoms",
         "treatment", "vaccine", "patient", "diagnosis", "cancer", "diabetes", "drug"),
    ),
    "Fitness": (
        "gym, workouts, exercise, bodybuilding, yoga, running",
        ("fitness", "gym", "workout", "exercise", "bodybuilding", "muscle", "yoga", "running",
         "cardio", "training plan", "protein"),
    ),
    "Mental Health": (
        "stress, anxiety, therapy, mindfulness, wellbeing",
        ("mental health", "anxiety", "stress", "depression", "therapy", "mindfulness",
         "meditation", "wellbeing", "burnout"),
    ),
    "Food & Cooking": (
        "recipes, cooking, restaurants, food reviews, nutrition and diet",
        ("recipe", "recipes", "cooking", "cook", "restaurant", "food", "dish", "ingredients",
         "baking", "cuisine", "nutrition", "diet"),
    ),
    "Parenting & Family": (
        "children, parenting, relationships, family life",
        ("parenting", "parents", "baby", "toddler", "children", "kids", "family",
         "relationship", "marriage", "pregnancy"),
    ),
    "Pets & Animals": (
        "pets, dogs, cats, animal care, wildlife facts",
        ("pet", "pets", "dog", "dogs", "cat", "cats", "puppy", "animal", "animals", "vet",
         "bird", "aquarium"),
    ),
    "Home & Garden": (
        "home improvement, DIY, interiors, gardening, cleaning",
        ("diy", "home improvement", "garden", "gardening", "interior", "furniture", "decor",
         "cleaning", "plants", "kitchen", "renovation"),
    ),
    "Fashion & Beauty": (
        "clothing, style, skincare, makeup, haircare",
        ("fashion", "style", "outfit", "clothing", "skincare", "makeup", "beauty", "haircare",
         "dress", "sneakers", "cosmetics"),
    ),
    "Lifestyle": (
        "personal development, habits, minimalism, general life advice",
        ("lifestyle", "self-improvement", "personal development", "habits", "minimalism",
         "motivation", "life advice", "routine"),
    ),
    # ---------------- learning & work ----------------
    "Education": (
        "courses, tutorials, exams, universities, study material, encyclopedias",
        ("course", "courses", "tutorial", "lesson", "syllabus", "exam", "university", "college",
         "student", "students", "learn", "learning", "wikipedia", "lecture", "school", "notes"),
    ),
    "Careers & Jobs": (
        "job openings, interviews, resumes, placements, internships, career advice",
        ("career", "careers", "job", "jobs", "hiring", "interview", "resume", "placement",
         "internship", "recruitment", "salary", "linkedin", "naukri"),
    ),
    "Business": (
        "companies, startups, entrepreneurship, management, industry news",
        ("business", "company", "startup", "entrepreneur", "management", "ceo", "enterprise",
         "customers", "industry", "founder", "b2b"),
    ),
    "Marketing": (
        "digital marketing, SEO, advertising, branding, social media marketing",
        ("marketing", "seo", "advertising", "ads", "branding", "brand", "campaign",
         "content marketing", "growth", "influencer"),
    ),
    "Finance": (
        "money, stocks, investing, banking, personal finance, taxes, economy",
        ("stock", "stocks", "invest", "investing", "investment", "market cap", "revenue",
         "earnings", "bank", "banking", "loan", "tax", "mutual fund", "sensex", "nifty",
         "economy", "inflation", "budget", "ipo"),
    ),
    "Cryptocurrency": (
        "bitcoin, crypto coins, blockchain, NFTs, Web3",
        ("crypto", "cryptocurrency", "bitcoin", "ethereum", "blockchain", "nft", "web3",
         "token", "defi", "wallet"),
    ),
    "Real Estate": (
        "property, housing, rent, home buying",
        ("real estate", "property", "apartment", "housing", "rent", "flat", "plot", "home loan",
         "realty"),
    ),
    "Productivity": (
        "productivity tips, note-taking, workflows, tools for getting work done",
        ("productivity", "workflow", "todo", "calendar", "notion", "focus", "time management",
         "organize", "planner"),
    ),
    # ---------------- society ----------------
    "News": (
        "current events and breaking news (use a more specific category if one fits)",
        ("breaking", "reported", "correspondent", "press release", "headlines", "news"),
    ),
    "Politics & Government": (
        "elections, government policy, schemes, public administration",
        ("election", "elections", "government", "minister", "parliament", "policy", "scheme",
         "president", "prime minister", "vote", "party", "governance"),
    ),
    "Law & Legal": (
        "laws, court cases, legal rights, judgments",
        ("law", "legal", "court", "supreme court", "high court", "judge", "lawsuit", "rights",
         "act", "advocate", "judgment"),
    ),
    "Religion & Spirituality": (
        "religion, temples, festivals, spirituality, scriptures",
        ("religion", "religious", "temple", "church", "mosque", "god", "spiritual",
         "spirituality", "festival", "prayer", "scripture"),
    ),
    "Social Media": (
        "social platforms, creators, trends, viral posts",
        ("social media", "instagram", "twitter", "tiktok", "reels", "influencer", "viral",
         "followers", "creator"),
    ),
    # ---------------- leisure ----------------
    "Sports": (
        "all sports and motorsport: cricket, football, F1 and racing, tennis, matches, highlights",
        ("sport", "sports", "cricket", "football", "soccer", "tennis", "match", "tournament",
         "f1", "formula 1", "grand prix", "race", "racing", "championship", "motogp", "ipl",
         "fifa", "olympics", "goal", "highlights", "lap", "podium", "kabaddi", "badminton"),
    ),
    "Automotive": (
        "cars, bikes, vehicles, EVs, reviews and maintenance (racing belongs in Sports)",
        ("car", "cars", "bike", "bikes", "motorcycle", "vehicle", "ev", "electric vehicle",
         "engine", "mileage", "suv", "sedan", "automobile", "dealership", "test ride"),
    ),
    "Travel": (
        "trips, destinations, hotels, flights, travel guides",
        ("travel", "trip", "hotel", "flight", "tourism", "destination", "itinerary", "visa",
         "beach", "trek", "resort"),
    ),
    "Movies & TV": (
        "films, web series, TV shows, trailers, reviews, OTT",
        ("movie", "movies", "film", "trailer", "series", "netflix", "prime video", "episode",
         "season", "box office", "actor", "actress", "director", "ott"),
    ),
    "Music": (
        "songs, albums, artists, concerts, music production",
        ("music", "song", "songs", "album", "singer", "concert", "lyrics", "spotify", "band",
         "playlist"),
    ),
    "Gaming": (
        "video games, consoles, esports, game reviews",
        ("game", "games", "gaming", "playstation", "xbox", "nintendo", "esports", "steam",
         "gameplay", "gamer", "bgmi"),
    ),
    "Books & Literature": (
        "books, novels, authors, poetry, reading lists",
        ("book", "books", "novel", "author", "poetry", "poem", "literature", "reading",
         "ebook", "kindle"),
    ),
    "Art & Photography": (
        "drawing, painting, photography, cameras, digital art",
        ("art", "artist", "painting", "drawing", "photography", "photo", "camera", "sketch",
         "illustration", "gallery"),
    ),
    "Design": (
        "UI/UX, graphic design, typography, logos, architecture",
        ("design", "typography", "figma", "ux", "ui", "user interface", "graphic", "logo",
         "font", "architecture"),
    ),
    "Entertainment": (
        "comedy, memes, celebrities, vlogs and general fun content",
        ("comedy", "funny", "meme", "memes", "celebrity", "vlog", "prank", "entertainment",
         "show", "standup"),
    ),
    "Shopping & Deals": (
        "products, prices, offers, discounts, buying guides",
        ("buy", "price", "deal", "deals", "discount", "offer", "sale", "coupon",
         "buying guide", "best price", "shop"),
    ),
    "Other": ("only if nothing fits and no sensible new category can be named", ()),
}

CATEGORIES = list(CATEGORY_GUIDE)

# A new category the AI invents must look like this: 1–3 words, letters, & or -.
NEW_CATEGORY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z&\- ]{1,29}$")
BANNED_NEW = {"none", "unknown", "misc", "miscellaneous", "general", "n/a", "na", "website",
              "web page", "webpage", "page", "link", "content", "article", "uncategorized"}

SYSTEM_PROMPT = (
    "You are a careful librarian who files web pages on the most specific correct shelf. "
    "Reply with a single JSON object and nothing else: "
    "{\"tags\": string[], \"category\": string}. "
    "Give 3-6 lowercase single-word or hyphenated tags about the page's real topic "
    "(never generic words like 'his', 'city', 'help', 'contact', 'terms'). "
    "Ignore website navigation, login and account text; judge the page by its real subject.\n\n"
    "Pick the category using these rules, in order:\n"
    "1. If one of the user's EXISTING library categories fits, reuse it exactly.\n"
    "2. Otherwise choose the most specific category from this built-in list:\n"
    + "\n".join(f"- {name}: {desc}" for name, (desc, _) in CATEGORY_GUIDE.items() if name != "Other")
    + "\n3. Only if nothing above fits, create ONE short new category (1-3 words, Title Case, "
    "e.g. 'Astrology', 'Robotics', 'Martial Arts').\n"
    "Use 'Other' only as a last resort."
)

STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "you", "your", "are", "was", "were",
    "have", "has", "had", "not", "but", "all", "can", "will", "how", "what", "when", "why",
    "who", "its", "our", "their", "they", "them", "about", "into", "more", "than", "also",
    "been", "which", "would", "there", "here", "one", "two", "use", "used", "using", "may",
    "get", "new", "out", "his", "her", "him", "she", "very", "just", "over", "after",
    "before", "where", "while", "each", "every", "some", "any", "most", "other", "such",
    "only", "own", "same", "too", "page", "home", "click", "sign", "login", "account",
    "contact", "help", "terms", "privacy", "policy", "cookies", "menu", "search", "username",
    "password", "update", "address", "view", "profile", "support", "worldwide", "canada",
    "need", "free", "now", "watch", "video", "youtube", "com", "www", "http", "https", "html",
    "city", "upon", "through", "untitled", "details", "options", "information", "preferences",
}


class TaggerAgent(BaseAgent):
    name = "Tagger Agent"
    role = "picks the tags and the category"

    def run(self, task: dict) -> dict:
        started = time.perf_counter()
        feedback = task.get("quality_feedback", {}).get("tags")
        existing = task.get("existing_categories") or []
        try:
            reply = llm_client.ask_json(SYSTEM_PROMPT, self._prompt(task, feedback, existing),
                                        max_tokens=200)
            task["tags"] = self.clean_tags(reply.get("tags", []))
            task["category"], is_new = self.choose_category(reply.get("category", "Other"), existing)
            task["ai_tags"] = True
            how = ("created NEW category with AI" if is_new else "chose tags + category with AI")
        except llm_client.LLMError as exc:
            self.say(f"AI unavailable ({exc}) — using keyword fallback")
            task["tags"], task["category"] = self.fallback(task)
            task["ai_tags"] = False
            how = "keyword fallback tags + category"

        self.say(f"{how}: {task['category']} · {', '.join(task['tags'])}")
        self.record(task, how, started)
        return task

    # ------------------------------------------------------------------ #
    @staticmethod
    def clean_tags(raw) -> list[str]:
        if isinstance(raw, str):
            raw = raw.split(",")
        tags = []
        for t in raw or []:
            slug = re.sub(r"[^a-z0-9+#.\-]", "", str(t).strip().lower().replace(" ", "-"))
            if slug and slug not in tags and slug not in STOPWORDS:
                tags.append(slug)
        return tags[:6]

    @staticmethod
    def choose_category(value, existing: list[str] | None = None) -> tuple[str, bool]:
        """Return (category, is_new). Accepts built-in, existing, or a clean new name."""
        raw = re.sub(r"\s+", " ", str(value or "")).strip().strip(".")
        low = raw.lower().replace(" and ", " & ")
        known = CATEGORIES + [c for c in (existing or []) if c not in CATEGORIES]

        exact = next((c for c in known if c.lower() == low), None)
        if exact:
            return exact, False
        # tolerate small differences: "sport" → Sports, "health" → Health & Medicine
        loose = next((c for c in known if len(low) >= 4 and (low in c.lower() or c.lower() in low)), None)
        if loose:
            return loose, False
        # accept a sensible brand-new category the AI invented
        if (NEW_CATEGORY_PATTERN.match(raw) and len(raw.split()) <= 3
                and low not in BANNED_NEW):
            return raw.title().replace(" And ", " & "), True
        return "Other", False

    @staticmethod
    def valid_category(value) -> str:
        """Kept for compatibility: built-in / clean new name, else 'Other'."""
        return TaggerAgent.choose_category(value)[0]

    @staticmethod
    def _prompt(task: dict, feedback: str | None, existing: list[str]) -> str:
        prompt = (
            f"EXISTING library categories: {', '.join(existing) if existing else '(none yet)'}\n\n"
            f"URL: {task['url']}\nTitle: {task.get('title', '')}\n"
            f"Meta description: {task.get('description') or '(none)'}\n"
            f"Summary: {task.get('summary', '')}\n\n"
            f"Page content:\n{truncate(task.get('text') or task.get('description', ''), 4000)}"
        )
        if feedback:
            prompt += f"\n\nYour previous answer was rejected: {feedback}"
        return prompt

    # ------------------------------------------------------------------ #
    # Offline fallback: weighted keyword scoring over the built-in list
    # ------------------------------------------------------------------ #
    @staticmethod
    def fallback(task: dict) -> tuple[list[str], str]:
        title = (task.get("title") or "").lower()
        desc = (task.get("description") or "").lower()
        text = (task.get("text") or "")[:6000].lower()
        url = (task.get("url") or "").lower()

        def hits(source: str, keyword: str) -> int:
            return len(re.findall(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", source))

        scores = {}
        for category, (_, keywords) in CATEGORY_GUIDE.items():
            score = sum(4 * hits(title, k) + 3 * hits(desc, k) + 2 * hits(url, k)
                        + min(hits(text, k), 3) for k in keywords)
            if score:
                scores[category] = score
        category = max(scores, key=scores.get) if scores else "Other"

        words = (re.findall(r"[a-z][a-z0-9+#\-]{2,}", title) * 3
                 + re.findall(r"[a-z][a-z0-9+#\-]{2,}", desc) * 2
                 + re.findall(r"[a-z][a-z0-9+#\-]{2,}", text))
        common = [w for w, _ in Counter(w for w in words if w not in STOPWORDS).most_common(5)]
        return common, category
