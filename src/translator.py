import os
import json
import litellm
import re

from config.settings import (
    GEMINI_API_KEY,         
    GROQ_API_KEY,           
    OPENROUTER_API_KEY,     
    GEMINI_MODEL,           
    GROQ_MODEL,             
    OPENROUTER_JUDGE_MODEL, 
    TEMPERATURE,            
    MAX_TOKENS,             
    SOURCE_LANGUAGE,        
    TARGET_LANGUAGE,        
    MIN_TEXT_LENGTH,        
    QUALITY_THRESHOLD,      
)

# ── Environment Setup ───────────────────────
if GEMINI_API_KEY: os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
if GROQ_API_KEY: os.environ["GROQ_API_KEY"] = GROQ_API_KEY
if OPENROUTER_API_KEY: os.environ["OPENROUTER_API_KEY"] = OPENROUTER_API_KEY

def _translation_prompt(text: str) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                f"You are a professional {SOURCE_LANGUAGE}-to-{TARGET_LANGUAGE} translator. "
                f"Return ONLY the {TARGET_LANGUAGE} translation. "
                f"No explanations. No original text. No commentary. "
                f"Just the translation."
            )
        },
        {"role": "user", "content": f"Translate this {SOURCE_LANGUAGE} text to {TARGET_LANGUAGE}:\n\n{text}"}
    ]

def translate_robust(text: str) -> str:
    """
    Primary translation function utilizing native Litellm fallbacks.
    (Technical word: Graceful Degradation - system automatically shifts to a backup without crashing).
    """
    if not text or len(text.strip()) < MIN_TEXT_LENGTH:
        raise ValueError(f"Text too short to translate: '{text}'")
    
    try:
        response = litellm.completion(
            model=GEMINI_MODEL,
            fallbacks=[{"model": GROQ_MODEL}], # Auto-routes to Groq if Gemini throws a 503
            messages=_translation_prompt(text),
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        # If both Gemini AND Groq fail, then we raise the flag
        raise RuntimeError(f"All translation models failed: {str(e)}")

def judge_quality(original: str, gemini_output: str, groq_output: str) -> dict:
    judge_messages = [
        {
            "role": "system",
            "content": (
                f"You are a professional translation quality evaluator specializing in {SOURCE_LANGUAGE} to {TARGET_LANGUAGE} translation. "
                "You evaluate translations for accuracy, fluency, and naturalness. "
                "You respond ONLY in the exact JSON format requested. "
                "No extra text before or after the JSON."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Evaluate these two Tamil translations of the given English text.\n\n"
                f"Original ({SOURCE_LANGUAGE}):\n{original}\n\n"
                f"Translation A (Gemini):\n{gemini_output}\n\n"
                f"Translation B (Groq):\n{groq_output}\n\n"
                f"Respond ONLY with this JSON:\n"
                f'{{"gemini_score": 0-100, "groq_score": 0-100, "recommended": "gemini or groq", "reason": "one sentence"}}'
            )
        }
    ]

    try:
        response = litellm.completion(
            model=OPENROUTER_JUDGE_MODEL,
            messages=judge_messages,
            temperature=0.0, 
            max_tokens=256,
        )
        raw = response.choices[0].message.content.strip()

        # ── Regex Data Extraction ───────────────────────
        # This searches the string and extracts ONLY the data between { and }
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not match:
            # If no JSON is found, force an error to trigger the except block
            raise ValueError(f"No JSON found in LLM response. Raw output: {raw}")
        
        clean_json = match.group(0)
        parsed = json.loads(clean_json)

        gemini_score = int(parsed.get("gemini_score", 0))
        groq_score   = int(parsed.get("groq_score", 0))
        recommended  = parsed.get("recommended", "gemini")
        reason       = parsed.get("reason", "No reason provided.")
        
        best_score = max(gemini_score, groq_score)
        flagged = best_score < QUALITY_THRESHOLD

        return {
            "gemini_score": gemini_score,  
            "groq_score":   groq_score,    
            "recommended":  recommended,   
            "reason":       reason,        
            "flagged":      flagged,       
            "raw_response": raw,           
        }
    
    except Exception as e:
        # ── Stop the Silent Failure ───────────────────────
        # Print the exact error to the console so you can debug the bottleneck
        print(f"\n[CRITICAL] Judge failed: {str(e)}\n")
        
        return {
            "gemini_score": 0, "groq_score": 0, "recommended": "gemini",        
            "reason": f"Judge failed: {str(e)}", "flagged": True, "raw_response": "",
        }
def translate_with_comparison(text: str) -> dict:
    """
    Forces independent calls to both models and uses Guard Clauses
    (Technical word: Short-Circuit Evaluation) to bypass the judge if a model fails.
    """
    if not text or len(text.strip()) < MIN_TEXT_LENGTH:
        raise ValueError(f"Text too short to translate: '{text}'")
    
    # Force Gemini
    try:
        gemini_result = litellm.completion(model=GEMINI_MODEL, messages=_translation_prompt(text)).choices[0].message.content.strip()
        gemini_failed = False
    except Exception as e:
        gemini_result = f"[Gemini failed: {str(e)}]"
        gemini_failed = True

    # Force Groq
    try:
        groq_result = litellm.completion(model=GROQ_MODEL, messages=_translation_prompt(text)).choices[0].message.content.strip()
        groq_failed = False
    except Exception as e:
        groq_result = f"[Groq failed: {str(e)}]"
        groq_failed = True

    # ── Control Flow Guard Clauses ───────────────────────

    # State 1: Both APIs bricked
    if gemini_failed and groq_failed:
        return {
            "original": text, "gemini": gemini_result, "groq": groq_result,
            "judge": {"flagged": True, "reason": "Both APIs down."}, "best": "ERROR: Models failed."
        }

    # State 2: Gemini bricked, Groq survived (Short-circuit the Judge)
    if gemini_failed and not groq_failed:
        return {
            "original": text, "gemini": gemini_result, "groq": groq_result,
            "judge": {"flagged": True, "reason": "Bypassed judge: Gemini failed."}, "best": groq_result
        }

    # State 3: Groq bricked, Gemini survived (Short-circuit the Judge)
    if groq_failed and not gemini_failed:
        return {
            "original": text, "gemini": gemini_result, "groq": groq_result,
            "judge": {"flagged": True, "reason": "Bypassed judge: Groq failed."}, "best": gemini_result
        }

    # State 4: Both succeeded, route to Judge (Technical word: A/B Testing)
    judgment = judge_quality(text, gemini_result, groq_result)
    
    best = groq_result if judgment["recommended"] == "groq" else gemini_result

    return {
        "original": text, "gemini": gemini_result, "groq": groq_result,
        "judge": judgment, "best": best,           
    }