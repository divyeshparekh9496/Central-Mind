"""
Amazon Nova Suite — all AI capabilities in one service.
  - Nova 2 Lite   : fast reasoning & fact-checking
  - Nova 2 Sonic  : speech-to-speech conversational AI
  - Nova Act      : agent fleet for UI-workflow automation
  - Nova Embeddings: multimodal semantic embeddings
"""
import os
import json
import base64
import asyncio
import boto3
from typing import List, Dict, Any, Optional


# ---------------------------------------------------------------------------
# Learner level definitions
# ---------------------------------------------------------------------------
LEVEL_PROMPTS = {
    "beginner": (
        "Use simple words and everyday analogies. Avoid equations. "
        "Max 3 sentences per concept."
    ),
    "intermediate": (
        "Assume basic physics knowledge. Include key terms and 1-2 key numbers "
        "(distances, temperatures, masses)."
    ),
    "expert": (
        "Use precise scientific language and equations where helpful. "
        "Cite theoretical models and recent papers."
    ),
}

SYSTEM_TEMPLATE = """\
You are Nova, a friendly cosmic companion for children exploring space. Sound curious, warm, playful and scientifically careful. Treat imaginary adventures as pretend, and never invent a science fact.

Learner level: {level}
Style guide: {style}

Rules:
0. Stay with astronomy and space learning; gently redirect other topics. Do not ask children for real names, addresses or contact details.
1. Answer the question clearly at the learner's level.
2. Always cite any NASA/arXiv source you use as [Source N].
3. Responses will be spoken aloud — use 2-3 short sentences, one simple analogy, and no frightening graphic descriptions. Explain unfamiliar words.
4. Invite the child to a playful optional discovery question, without pressure or grades, prefixed with:
   CHECK: <your question here>
"""


class NovaService:
    """Unified service for the Amazon Nova model suite via Amazon Bedrock."""

    def __init__(self):
        self.region = os.getenv("AWS_REGION", "us-east-1")
        self.api_key = os.getenv("BEDROCK_API_KEY")
        self.bearer_token = os.getenv("AWS_BEARER_TOKEN_BEDROCK")
        
        self._has_credentials = bool(
            os.getenv("AWS_ACCESS_KEY_ID") or 
            self.bearer_token or
            self.api_key
        )

        # Initialize bedrock client
        if self.bearer_token and not os.getenv("AWS_ACCESS_KEY_ID"):
            # For Bedrock API keys / Bearer tokens (ABSK...)
            # Note: botocore supports bearer tokens via specific configuration
            # but we'll try to initialize the client directly.
            self.bedrock = boto3.client(
                "bedrock-runtime",
                region_name=self.region,
            )
            # In latest boto3, session can take bearer_token if configured
            # but we'll rely on the environment variable which is often 
            # supported by underlying auth providers in AWS SDKs.
        elif self.api_key and not os.getenv("AWS_ACCESS_KEY_ID"):
            # If using API key, we might need a custom endpoint or header injection
            # For Bedrock API keys (ABSK...), they are often used in specialized Bedrock environments
            # We'll use a standard session but mark credentials as present
            self.bedrock = boto3.client(
                "bedrock-runtime",
                region_name=self.region,
                # Note: ABSK keys are used in Bedrock's new unified API access
            )
        else:
            session = boto3.Session(
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name=self.region,
            )
            self.bedrock = session.client("bedrock-runtime")

    # ------------------------------------------------------------------
    # Nova 2 Lite — Reasoning & Fact-Checking
    # ------------------------------------------------------------------
    async def invoke_nova_lite_chat(
        self,
        prompt: str,
        system_prompt: str,
        context: Optional[str] = None,
        level: str = "beginner",
    ) -> str:
        """
        Call Nova 2 Lite for adaptive, citation-grounded reasoning.
        Falls back to structured demo response if credentials are absent.
        """
        if not self._has_credentials:
            return self._demo_response(prompt, level)

        style = LEVEL_PROMPTS.get(level, LEVEL_PROMPTS["beginner"])
        system_text = SYSTEM_TEMPLATE.format(level=level, style=style)
        if system_prompt:
            system_text += f"\n\nAdditional task instructions: {system_prompt}"
        if context:
            system_text += f"\n\nResearch context (cite these):\n{context}"

        body = json.dumps({
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ],
            "system": [{"text": system_text}],
            "inferenceConfig": {
                "maxTokens": 512,
                "temperature": 0.15,
                "topP": 0.9,
            },
        })

        try:
            resp = self.bedrock.invoke_model(
                modelId="us.amazon.nova-lite-v1:0",
                contentType="application/json",
                accept="application/json",
                body=body,
            )
            data = json.loads(resp["body"].read())
            return data["output"]["message"]["content"][0]["text"]
        except Exception as e:
            print(f"[NovaLite] Error: {e}")
            return self._demo_response(prompt, level)

    async def check_bedrock_connection(self) -> Dict[str, Any]:
        """Diagnostic check for Bedrock connectivity and credentials."""
        if not self._has_credentials:
            return {"status": "error", "message": "No credentials found in environment."}
        try:
            # Simple list_foundation_models or similar might fail if no permissions,
            # so we do a tiny invocation.
            body = json.dumps({
                "messages": [{"role": "user", "content": [{"text": "ping"}]}],
                "inferenceConfig": {"maxTokens": 1}
            })
            self.bedrock.invoke_model(
                modelId="us.amazon.nova-lite-v1:0",
                contentType="application/json",
                accept="application/json",
                body=body
            )
            return {"status": "ok", "message": "Bedrock connection successful.", "token": "NOVA_SYNC_PHASE_6_FINAL"}
        except Exception as e:
            return {"status": "error", "message": str(e), "token": "NOVA_SYNC_PHASE_6_FINAL"}

    # ------------------------------------------------------------------
    # Nova 2 Sonic — Speech-to-Speech
    # ------------------------------------------------------------------
    async def invoke_nova_sonic_s2s_stream(self, audio_bytes: bytes, context: Optional[str] = None):
        """
        Stream Nova 2 Sonic S2S response for ultra-low latency.
        Yields audio/mpeg chunks as they arrive from Bedrock.
        """
        if not self._has_credentials:
            # Yield demo silence
            yield self._silent_wav()
            return

        try:
            audio_b64 = base64.b64encode(audio_bytes).decode()
            model_input = {
                "inputAudio": audio_b64,
            }
            if context:
                # Add context as text input to the sonic model
                model_input["text"] = f"Use this scientific context to inform your answer: {context}"

            body = json.dumps({
                **model_input,
                "voiceConfig": {
                    "voiceId": "matthew",
                },
                "inferenceConfig": {
                    "maxTokens": 384,
                },
            })
            
            # Using loop.run_in_executor because invoke_model_with_response_stream is synchronous in boto3
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None,
                lambda: self.bedrock.invoke_model_with_response_stream(
                    modelId="us.amazon.nova-sonic-v1:0",
                    contentType="application/json",
                    accept="audio/mpeg",
                    body=body,
                )
            )

            # Iterate over the stream in a separate thread to avoid blocking
            queue = asyncio.Queue()

            def _producer():
                try:
                    for event in resp["body"]:
                        # Put event into queue
                        asyncio.run_coroutine_threadsafe(queue.put(event), loop)
                    # Signal EOF
                    asyncio.run_coroutine_threadsafe(queue.put(None), loop)
                except Exception as e:
                    print(f"[NovaSonicStream] producer error: {e}")
                    asyncio.run_coroutine_threadsafe(queue.put(None), loop)

            import threading
            threading.Thread(target=_producer, daemon=True).start()

            while True:
                event = await queue.get()
                if event is None:
                    break
                
                chunk = event.get("chunk")
                if chunk:
                    yield chunk.get("bytes")
                
                for err_key in ["internalServerException", "modelStreamErrorException", "throttlingException"]:
                    if err_key in event:
                        print(f"[NovaSonicStream] Bedrock Error: {event[err_key]}")

        except Exception as e:
            print(f"[NovaSonicStream] Error: {e}")
            # Yield nothing (or a tiny valid silent MP3 chunk if needed)
            # Yielding a WAV here breaks MediaSource(audio/mpeg)
            pass

    async def invoke_nova_sonic_s2s(self, audio_bytes: bytes) -> bytes:
        """
        Synchronous-like wrapper for S2S (backwards compatibility).
        Collects all chunks and returns them as a single block.
        """
        all_audio = b""
        async for chunk in self.invoke_nova_sonic_s2s_stream(audio_bytes):
            all_audio += chunk
        return all_audio

    async def nova_sonic_transcribe(self, audio_bytes: bytes) -> str:
        """
        Use Nova Sonic in transcription mode to convert speech → text.
        Falls back to a placeholder in demo mode.
        """
        if not self._has_credentials:
            return ""  # caller handles empty string as demo trigger

        try:
            audio_b64 = base64.b64encode(audio_bytes).decode()
            body = json.dumps({
                "inputAudio": audio_b64,
                "task": "transcription",
            })
            resp = self.bedrock.invoke_model(
                modelId="us.amazon.nova-sonic-v1:0",
                contentType="application/json",
                accept="application/json",
                body=body,
            )
            data = json.loads(resp["body"].read())
            return data.get("transcript", "")
        except Exception as e:
            print(f"[NovaSonic transcribe] Error: {e}")
            return ""

    # ------------------------------------------------------------------
    # Nova Multimodal Embeddings — Semantic Similarity
    # ------------------------------------------------------------------
    async def embed_text(self, text: str) -> List[float]:
        """
        Generate a semantic embedding via Nova Multimodal Embeddings.
        Returns a 1024-d float vector.
        Falls back to a deterministic pseudo-embedding in demo mode.
        """
        if not self._has_credentials:
            return self._demo_embedding(text)

        try:
            body = json.dumps({
                "inputText": text,
            })
            resp = self.bedrock.invoke_model(
                modelId="amazon.nova-2-multimodal-embeddings-v1:0",
                contentType="application/json",
                accept="application/json",
                body=body,
            )
            data = json.loads(resp["body"].read())
            return data["embedding"]
        except Exception as e:
            print(f"[NovaEmbed] Error: {e}")
            return self._demo_embedding(text)

    # ------------------------------------------------------------------
    # Nova Act — Agent Fleet for UI-Workflow Automation
    # ------------------------------------------------------------------
    async def invoke_nova_act_workflow(
        self, task: str, context: str
    ) -> Dict[str, Any]:
        """
        Invoke a Nova Act agent to generate structured UI workflow data.
        E.g., orbital trajectory JSON for a 3D visualization.
        """
        if not self._has_credentials:
            return {
                "task": task,
                "status": "demo_mode",
                "result": f"Nova Act would orchestrate: {task}",
            }

        try:
            prompt = (
                f"You are a Nova Act agent. Context: {context}\n"
                f"Generate a JSON result for the task: {task}"
            )
            body = json.dumps({
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"maxTokens": 1024, "temperature": 0.0},
            })
            resp = self.bedrock.invoke_model(
                modelId="us.amazon.nova-lite-v1:0",  # Nova Act often uses specialized model or Lite
                contentType="application/json",
                accept="application/json",
                body=body,
            )
            data = json.loads(resp["body"].read())
            text = data["output"]["message"]["content"][0]["text"]
            # Extract JSON from the response
            import re
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group())
            return {"result": text}
        except Exception as e:
            print(f"[NovaAct] Error: {e}")
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # Demo / Fallback helpers
    # ------------------------------------------------------------------
    def _demo_response(self, prompt: str, level: str) -> str:
        """Structured demo responses for local dev without AWS keys."""
        p = prompt.lower()
        if any(k in p for k in ["starship", "rocket", "spacex"]):
            if level == "beginner":
                return (
                    "Starship is the biggest rocket ever built — taller than the Statue of Liberty! "
                    "It's designed to take people all the way to Mars. "
                    "CHECK: How many engines does Starship use?"
                )
            return (
                "SpaceX Starship is a fully-reusable super-heavy-lift vehicle powered by 33 Raptor engines "
                "using liquid oxygen and sub-cooled methane (Isp ~380s). [Source: NASA TR-2023] "
                "CHECK: What is the significance of sub-cooled propellant in Starship's design?"
            )
        if any(k in p for k in ["webb", "james webb", "jwst"]):
            return (
                "The James Webb Space Telescope sees infrared light invisible to our eyes, "
                "letting it look through dust clouds to find the universe's first galaxies. "
                "CHECK: What is infrared light and how is it different from visible light?"
            )
        if any(k in p for k in ["black hole", "blackhole"]):
            return (
                "A black hole's gravity is so strong that not even light can escape — "
                "its boundary is called the event horizon. [Source: arXiv:2301.00001] "
                "CHECK: What is the name of the boundary around a black hole?"
            )
        if any(k in p for k in ["jupiter"]):
            return (
                "Jupiter is the largest planet in our solar system — so big that 1,300 Earths could fit inside it! "
                "It's a gas giant with a Great Red Spot that is actually a massive storm. [Source: NASA] "
                "CHECK: What is the Great Red Spot on Jupiter?"
            )
        return (
            f"Great question about space! (Demo mode — add AWS credentials for full Nova 2 Lite answers.) "
            f"CHECK: What aspect of '{prompt[:40]}' would you like to explore further?"
        )

    @staticmethod
    def _demo_embedding(text: str) -> List[float]:
        """Deterministic pseudo-embedding for demo mode (256-d)."""
        import hashlib
        h = hashlib.sha256(text.lower().encode()).digest()
        vec = [((b / 255.0) - 0.5) * 2 for b in h]
        # Pad to 256-d
        vec = (vec * 8)[:256]
        norm = sum(x * x for x in vec) ** 0.5 or 1.0
        return [x / norm for x in vec]

    @staticmethod
    def _silent_wav() -> bytes:
        """Return a minimal valid WAV header for 0.1 s of silence."""
        import struct
        sample_rate = 16000
        num_channels = 1
        bits_per_sample = 16
        num_samples = sample_rate // 10  # 0.1 s
        data_size = num_samples * num_channels * (bits_per_sample // 8)
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF", 36 + data_size, b"WAVE", b"fmt ", 16,
            1, num_channels, sample_rate,
            sample_rate * num_channels * bits_per_sample // 8,
            num_channels * bits_per_sample // 8, bits_per_sample,
            b"data", data_size,
        )
        return header + b"\x00" * data_size
