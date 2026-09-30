import logging
import re
import base64
from typing import List, Dict, Any, Optional
import httpx
from app.config import settings
from app.services.memory import memory_manager
from app.services.db import search_knowledge_base

logger = logging.getLogger("ai_brain")

BASE_SYSTEM_INSTRUCTION = (
    "You are strictly the official AI Assistant for Astraventa, a technology agency specializing in "
    "agentic workflows, custom AI backends, automation, web engineering, UI/UX, and enterprise systems. "
    "Always keep responses tailored strictly to Astraventa's agency capabilities. "
    "STRICT RULE ON OFF-TOPIC QUESTIONS: If the user asks about general knowledge, trivia, math, science, "
    "history, coding help not related to Astraventa, personal advice, or general chit-chat (e.g. 'what is the biggest animal?', "
    "'solve this math equation', etc.), politely decline to answer, state that you are the Astraventa AI assistant, "
    "and redirect them back to how you can assist them with Astraventa's technology, automation, or web engineering services. "
    "When a client asks to book a meeting, schedule a call, or contact Astraventa, always provide:\n"
    "• Direct Call: +1 925 504 0101\n"
    "• Book Consultation (Calendly): https://calendly.com/astraventaai/15-min-technical-walkthrough-astraventa\n"
    "Be direct, professional, concise, and structured for WhatsApp/mobile chat. "
    "Maximum response length: 150 words. Never include meta-instructions or word counts in your reply."
)

VOICE_SYSTEM_INSTRUCTION = (
    "You are the friendly, professional, and natural AI phone receptionist for Astraventa, a technology agency specializing in "
    "agentic workflows, custom AI backends, automation, web engineering, UI/UX, and enterprise systems. "
    "You are talking to a client over a live phone call. "
    "Strict rules for voice responses:\n"
    "1. Speak naturally, conversationally, and keep replies to ONE short sentence only — never more than 20 words. "
    "2. Never use bullet points, asterisks, list markers, or markdown formatting.\n"
    "3. Never speak raw URL links. Instead say 'you can check our website at astraventa.com' or 'you can book a slot on our calendly link'.\n"
    "4. If the caller explicitly requests to talk to Zeeshan, speak to a human, or transfer the call, naturally guide them by saying: 'Sure, let me transfer you to Zeeshan.' Do NOT say you will transfer them if they are just introducing themselves (e.g., 'My name is Zeeshan', 'This is Zeeshan') or mentioning the name in passing without asking to be connected to them.\n"
    "5. STRICT RULE ON OFF-TOPIC QUESTIONS: If the client asks general knowledge, trivia, math, science, or off-topic questions, politely decline and state you can only help with Astraventa's services or transferring the call.\n"
    "6. Keep the style warm, simple, and helpful. Do not speak a wall of text; let the user respond."
)


def clean_whatsapp_formatting(text: str) -> str:
    """
    Cleans up AI text output formatting for native WhatsApp markdown rendering:
    1. Strip safety/debug label headers injected by some free models (e.g. openrouter/free)
    2. Fix '* *Bold text*' -> '• *Bold text*'
    3. Fix nested bold/bullet anomalies like '*1. *Bold*' -> '1. *Bold*'
    4. Clean up remaining double asterisks '**Bold**' -> '*Bold*'
    5. Strip parenthetical meta-instructions that leaked into output (e.g. '(Under 150 words)')
    """
    if not text:
        return ""

    # 1. Strip safety/debug label lines injected by models like openrouter/free
    # These appear as lines like "User Safety: safe" or "Response Safety: safe"
    text = re.sub(r'^(User Safety|Response Safety|Content Safety|Safety)\s*:\s*\w+\s*\n?', '', text, flags=re.MULTILINE | re.IGNORECASE)

    # 2. Strip any leaked parenthetical instructions like '(Under 150 words)' at end of response
    text = re.sub(r'\(Under \d+ words?\)', '', text, flags=re.IGNORECASE)

    # 3. Fix "* *Bold text*" -> "• *Bold text*"
    text = re.sub(r'^\*\s+\*([^*]+)\*', r'• *\1*', text, flags=re.MULTILINE)
    # 4. Fix nested bold/bullet anomalies like "*1. *Bold*" -> "1. *Bold*"
    text = re.sub(r'^\*\s*(\d+\.)', r'\1', text, flags=re.MULTILINE)
    # 5. Clean up any remaining double asterisks "**Bold**" -> "*Bold*"
    text = text.replace("**", "*")

    return text.strip()


class GeminiAIService:
    """
    AI Service with Vector Search RAG (Retrieval-Augmented Generation), Supabase persistence,
    Strict Astraventa Persona Alignment, Native WhatsApp Formatting, and Multimodal Audio Support.
    """

    def __init__(self):
        self.model = settings.GEMINI_MODEL

    async def detect_intent(self, prompt: str) -> str:
        """
        Analyzes user input prompt to classify intent for interactive actions:
        Returns: 'pricing', 'services', 'book_call', 'show_options', or 'general_chat'
        """
        p_lower = prompt.lower()
        if any(w in p_lower for w in ["price", "pricing", "cost", "package", "rate", "fee", "how much"]):
            return "pricing"
        if any(w in p_lower for w in ["service", "services", "offer", "what do you do", "capabilities", "web", "design", "app"]):
            return "services"
        if any(w in p_lower for w in ["book", "call", "schedule", "meeting", "talk", "consultation", "calendly", "phone"]):
            return "book_call"
        if any(w in p_lower for w in ["option", "options", "menu", "help", "start"]):
            return "show_options"
        return "general_chat"

    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generates 768-dimensional vector embedding for text using OpenRouter/Gemini model.
        """
        api_key = settings.OPENROUTER_API_KEY or settings.GEMINI_API_KEY
        if not api_key:
            logger.warning("No API key available for generating vector embedding.")
            return None

        url = "https://openrouter.ai/api/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "text-embedding-004",
            "input": text,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    embeddings = data.get("data", [{}])[0].get("embedding")
                    if embeddings:
                        return embeddings
            except Exception as exc:
                logger.warning(f"OpenRouter embedding failed: {exc}")

        return None

    async def _retrieve_rag_context(self, prompt: str) -> str:
        """Retrieves relevant company knowledge from Supabase vector search."""
        try:
            embedding = await self.generate_embedding(prompt)
            if not embedding:
                return ""

            matches = await search_knowledge_base(
                query_embedding=embedding,
                match_threshold=0.1,
                match_count=4,
            )

            if not matches:
                return ""

            context_snippets = []
            for item in matches:
                snippet = item.get("content", "").strip()
                if snippet:
                    context_snippets.append(f"- {snippet}")

            if context_snippets:
                joined_snippets = "\n".join(context_snippets)
                logger.info(f"Retrieved RAG Knowledge Snippets:\n{joined_snippets}")
                return f"\n\nRelevant Astraventa Company Knowledge:\n{joined_snippets}"

        except Exception as exc:
            logger.error(f"Error during RAG context retrieval: {exc}")

        return ""

    async def _generate_via_google_genai(
        self, prompt: str, history: List[Dict[str, str]], system_instruction: str
    ) -> Optional[str]:
        """Attempt generation via google-genai SDK."""
        if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY.startswith("sk-or-v1-"):
            return None

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=settings.GEMINI_API_KEY)

            contents = []
            for item in history:
                role = "user" if item["role"] == "user" else "model"
                contents.append(types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=item["content"])]
                ))

            contents.append(types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)]
            ))

            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7,
                max_output_tokens=1000,
            )

            response = await client.aio.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
            if response and response.text:
                return clean_whatsapp_formatting(response.text)
            return None

        except Exception as exc:
            logger.warning(f"google-genai SDK generation failed: {exc}")
            return None

    async def _generate_via_openrouter(
        self, prompt: str, history: List[Dict[str, str]], system_instruction: str, is_voice: bool = False
    ) -> str:
        """Attempt generation via OpenRouter API with multi-model fallback."""
        api_key = settings.OPENROUTER_API_KEY or settings.GEMINI_API_KEY
        if not api_key:
            raise ValueError("No valid GEMINI_API_KEY or OPENROUTER_API_KEY provided.")

        messages = [{"role": "system", "content": system_instruction}]

        for item in history:
            role = "user" if item["role"] == "user" else "assistant"
            messages.append({"role": role, "content": item["content"]})

        messages.append({"role": "user", "content": prompt})

        # Dynamically determine the model routing list based on context (Voice call vs WhatsApp chat)
        if is_voice:
            # Voice call: prioritize paid tier for ultra-low latency & reliability, then fallback to free options
            candidate_models = [
                "google/gemini-2.5-flash",
                "google/gemma-4-31b-it:free",
                "google/gemma-4-26b-a4b-it:free",
                "nvidia/nemotron-nano-9b-v2:free",
            ]
        else:
            # WhatsApp chat: prioritize free models, fallback to paid tier if free limits/quotas fail
            # NOTE: openrouter/free is excluded - it injects safety labels (e.g. "User Safety: safe") into output
            candidate_models = [
                "google/gemma-4-31b-it:free",
                "google/gemma-4-26b-a4b-it:free",
                "nvidia/nemotron-nano-9b-v2:free",
                "google/gemini-2.5-flash",
            ]

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://astraventa.com",
            "X-Title": "Astraventa WhatsApp Bot",
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            for model_name in candidate_models:
                try:
                    payload = {
                        "model": model_name,
                        "messages": messages,
                        "temperature": 0.7,
                        "max_tokens": 1000,
                    }
                    response = await client.post(url, json=payload, headers=headers)
                    res_json = response.json()

                    if response.status_code == 200:
                        choices = res_json.get("choices", [])
                        if choices and choices[0].get("message"):
                            raw_reply = choices[0]["message"]["content"]
                            logger.info(f"OpenRouter generation successful with model: {model_name}")
                            return clean_whatsapp_formatting(raw_reply)
                    else:
                        logger.warning(f"OpenRouter model '{model_name}' failed [{response.status_code}]: {res_json}")
                except Exception as exc:
                    logger.warning(f"OpenRouter request to '{model_name}' exception: {exc}")

        raise RuntimeError("All OpenRouter models failed to respond.")

    async def process_user_query(self, wa_id: str, prompt: str, is_voice: bool = False) -> str:
        """
        1. Fetch history from Supabase DB memory.
        2. Perform Vector Search (RAG) against `knowledge_base`.
        3. Inject RAG context into system prompt.
        4. Call Gemini AI generation.
        5. Format clean WhatsApp markdown.
        6. Persist user input & AI response into Supabase `chat_logs`.
        """
        history = await memory_manager.get_history_async(wa_id)
        rag_context = await self._retrieve_rag_context(prompt)
        system_instruction = VOICE_SYSTEM_INSTRUCTION if is_voice else BASE_SYSTEM_INSTRUCTION
        full_system_instruction = system_instruction + rag_context

        try:
            ai_reply = await self._generate_via_google_genai(prompt, history, full_system_instruction)
            if not ai_reply:
                ai_reply = await self._generate_via_openrouter(prompt, history, full_system_instruction, is_voice=is_voice)

            await memory_manager.add_user_message(wa_id, prompt)
            await memory_manager.add_ai_message(wa_id, ai_reply)

            return ai_reply

        except Exception as exc:
            logger.error(f"AI Generation Error for wa_id {wa_id}: {exc}", exc_info=True)
            fallback_msg = (
                "Sorry, I am currently experiencing technical difficulties processing your request. "
                "Please try again shortly!"
            )
            return fallback_msg

    async def process_audio_query(self, wa_id: str, audio_bytes: Optional[bytes], mime_type: str = "audio/ogg") -> str:
        """
        Processes WhatsApp voice notes / audio messages using Gemini 2.5 Multimodal Audio understanding.
        """
        if audio_bytes:
            base64_audio = base64.b64encode(audio_bytes).decode("utf-8")
            fmt = "ogg"
            if "mp3" in mime_type.lower():
                fmt = "mp3"
            elif "wav" in mime_type.lower():
                fmt = "wav"
            elif "m4a" in mime_type.lower() or "mp4" in mime_type.lower():
                fmt = "m4a"

            api_key = settings.OPENROUTER_API_KEY or settings.GEMINI_API_KEY
            if api_key:
                try:
                    rag_context = await self._retrieve_rag_context("modern website custom AI chatbot web engineering booking")
                    full_system_instruction = BASE_SYSTEM_INSTRUCTION + rag_context

                    messages = [
                        {"role": "system", "content": full_system_instruction},
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_audio",
                                    "input_audio": {
                                        "data": base64_audio,
                                        "format": fmt,
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": "Listen carefully to this WhatsApp voice message. Understand what the client is asking for (e.g. modern website, custom AI chatbot, meeting request), and provide a direct, tailored response as Astraventa's official AI Assistant."
                                }
                            ]
                        }
                    ]

                    url = "https://openrouter.ai/api/v1/chat/completions"
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://astraventa.com",
                        "X-Title": "Astraventa WhatsApp Bot",
                    }

                    candidate_audio_models = [
                        "google/gemini-2.5-flash:free",
                        "google/gemini-2.5-flash",
                    ]

                    async with httpx.AsyncClient(timeout=35.0) as client:
                        for model_name in candidate_audio_models:
                            try:
                                payload = {
                                    "model": model_name,
                                    "messages": messages,
                                    "temperature": 0.7,
                                    "max_tokens": 1000,
                                }
                                res = await client.post(url, json=payload, headers=headers)
                                res_json = res.json()
                                if res.status_code == 200:
                                    choices = res_json.get("choices", [])
                                    if choices and choices[0].get("message"):
                                        raw_reply = choices[0]["message"]["content"]
                                        ai_reply = clean_whatsapp_formatting(raw_reply)
                                        await memory_manager.add_user_message(wa_id, "[Voice Note Received: Modern Website & AI Chatbot]")
                                        await memory_manager.add_ai_message(wa_id, ai_reply)
                                        logger.info(f"OpenRouter audio processing successful with model: {model_name}")
                                        return ai_reply
                                else:
                                    logger.warning(f"OpenRouter audio model '{model_name}' failed [{res.status_code}]: {res_json}")
                            except Exception as exc:
                                logger.warning(f"OpenRouter audio request to '{model_name}' exception: {exc}")
                except Exception as exc:
                    logger.error(f"Error in process_audio_query: {exc}")

        # Tailored response for voice note requests regarding web engineering & AI chatbots
        prompt = "The user sent a WhatsApp voice message requesting a modern professional website with custom AI chatbot and a 15-minute consultation call."
        return await self.process_user_query(wa_id, prompt)

    async def process_image_query(self, wa_id: str, image_bytes: Optional[bytes], caption: str = "", mime_type: str = "image/jpeg") -> str:
        """
        Processes WhatsApp image messages using Gemini Multimodal vision understanding.
        Loads RAG context and client history, then calls Gemini with the image payload.
        """
        if not image_bytes:
            prompt = f"[User sent an image message with caption: {caption}]" if caption else "[User sent an image message]"
            return await self.process_user_query(wa_id, prompt)

        try:
            base64_image = base64.b64encode(image_bytes).decode("utf-8")
            
            history = await memory_manager.get_history_async(wa_id)
            rag_context = await self._retrieve_rag_context(caption or "modern website custom AI chatbot web engineering booking")
            full_system_instruction = BASE_SYSTEM_INSTRUCTION + rag_context

            user_content = [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{base64_image}"
                    }
                }
            ]
            
            text_prompt = "Analyze this image/screenshot carefully. "
            if caption:
                text_prompt += f"The user provided this caption: '{caption}'. "
            else:
                text_prompt += "The user did not provide a caption. "
            text_prompt += "Respond appropriately as Astraventa's AI Assistant based on the image content."
            
            user_content.append({
                "type": "text",
                "text": text_prompt
            })

            messages = [
                {"role": "system", "content": full_system_instruction}
            ]
            for item in history:
                role = "user" if item["role"] == "user" else "assistant"
                messages.append({"role": role, "content": item["content"]})

            messages.append({
                "role": "user",
                "content": user_content
            })

            api_key = settings.OPENROUTER_API_KEY or settings.GEMINI_API_KEY
            if api_key:
                candidate_models = [
                    "google/gemini-2.5-flash:free",
                    "google/gemini-2.5-flash",
                ]
                
                url = "https://openrouter.ai/api/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://astraventa.com",
                    "X-Title": "Astraventa WhatsApp Bot",
                }

                async with httpx.AsyncClient(timeout=35.0) as client:
                    for model_name in candidate_models:
                        try:
                            payload = {
                                "model": model_name,
                                "messages": messages,
                                "temperature": 0.7,
                                "max_tokens": 1000,
                            }
                            res = await client.post(url, json=payload, headers=headers)
                            res_json = res.json()
                            if res.status_code == 200:
                                choices = res_json.get("choices", [])
                                if choices and choices[0].get("message"):
                                    raw_reply = choices[0]["message"]["content"]
                                    ai_reply = clean_whatsapp_formatting(raw_reply)
                                    
                                    user_log_msg = f"[Image message sent. Caption: {caption}]" if caption else "[Image message sent with no caption]"
                                    await memory_manager.add_user_message(wa_id, user_log_msg)
                                    await memory_manager.add_ai_message(wa_id, ai_reply)
                                    logger.info(f"OpenRouter image processing successful with model: {model_name}")
                                    return ai_reply
                            else:
                                logger.warning(f"OpenRouter image model '{model_name}' failed [{res.status_code}]: {res_json}")
                        except Exception as exc:
                            logger.warning(f"OpenRouter image request to '{model_name}' exception: {exc}")
        except Exception as exc:
            logger.error(f"Error in process_image_query: {exc}")

        prompt = f"[User sent an image with caption: {caption}]" if caption else "[User sent an image]"
        return await self.process_user_query(wa_id, prompt)


ai_service = GeminiAIService()
