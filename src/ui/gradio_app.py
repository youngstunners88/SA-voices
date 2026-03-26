"""Gradio UI for SA Voices"""

import io
import base64
from typing import Optional

import gradio as gr
import numpy as np

from ..core.config import get_settings, LANGUAGE_METADATA
from ..tts.engine import TTSEngine, SynthesisRequest
from ..skills.language_detection import LanguageDetector


def create_ui() -> gr.Blocks:
    """Create Gradio interface"""
    settings = get_settings()
    
    # Initialize components
    tts_engine = TTSEngine()
    lang_detector = LanguageDetector()
    
    # CSS for SA Voices theme
    css = """
    .sa-header {
        text-align: center;
        padding: 20px;
        background: linear-gradient(135deg, #007749 0%, #FFB81C 50%, #DE3831 100%);
        color: white;
        border-radius: 10px;
    }
    .sa-title {
        font-size: 2.5em;
        font-weight: bold;
        margin-bottom: 10px;
    }
    .sa-subtitle {
        font-size: 1.2em;
        opacity: 0.9;
    }
    .language-flag {
        font-size: 2em;
        margin: 0 10px;
    }
    """
    
    with gr.Blocks(css=css, title="SA Voices") as app:
        # Header
        with gr.Row(elem_classes=["sa-header"]):
            with gr.Column():
                gr.HTML(
                    """
                    <div class="sa-header">
                        <div class="sa-title">🇿🇦 SA Voices</div>
                        <div class="sa-subtitle">South African Multilingual Voice Agent</div>
                        <div style="margin-top: 10px;">
                            <span class="language-flag">🗣️</span>
                            Supporting all 11 official languages
                        </div>
                    </div>
                    """
                )
        
        # Main interface
        with gr.Row():
            with gr.Column(scale=1):
                # Language selection
                gr.Markdown("### 🌐 Language")
                
                language_dropdown = gr.Dropdown(
                    choices=[
                        (f"{meta['name']} ({code})", code)
                        for code, meta in LANGUAGE_METADATA.items()
                    ],
                    value="en",
                    label="Select Language"
                )
                
                auto_detect = gr.Checkbox(
                    label="Auto-detect language",
                    value=True
                )
                
                detected_lang = gr.Textbox(
                    label="Detected Language",
                    interactive=False
                )
                
                # Voice settings
                gr.Markdown("### 🎙️ Voice Settings")
                
                voice_preset = gr.Dropdown(
                    choices=[
                        ("Default", "default"),
                        ("Male", "male"),
                        ("Female", "female"),
                        ("Young", "young"),
                        ("Elderly", "elderly"),
                    ],
                    value="default",
                    label="Voice Preset"
                )
                
                speed_slider = gr.Slider(
                    minimum=0.5,
                    maximum=2.0,
                    value=1.0,
                    step=0.1,
                    label="Speed"
                )
                
                pitch_slider = gr.Slider(
                    minimum=0.5,
                    maximum=2.0,
                    value=1.0,
                    step=0.1,
                    label="Pitch"
                )
            
            with gr.Column(scale=2):
                # Text input
                gr.Markdown("### 📝 Text to Speak")
                
                text_input = gr.Textbox(
                    label="Enter text",
                    placeholder="Type or paste text here...",
                    lines=5,
                    max_lines=10
                )
                
                # Sample texts
                gr.Markdown("#### Quick Samples")
                
                with gr.Row():
                    samples = {
                        "zu": ("Sawubona, igama lami ngu...", "Zulu"),
                        "xh": ("Molo, ndicela uncedo...", "Xhosa"),
                        "af": ("Hallo, hoe kan ek help?", "Afrikaans"),
                        "en": ("Hello, how can I help you today?", "English"),
                    }
                    
                    for code, (text, name) in samples.items():
                        gr.Button(name).click(
                            lambda t=text: t,
                            outputs=text_input
                        )
                
                # Generate button
                generate_btn = gr.Button(
                    "🎵 Generate Speech",
                    variant="primary",
                    size="lg"
                )
                
                # Output
                audio_output = gr.Audio(
                    label="Generated Speech",
                    type="numpy"
                )
                
                # Info
                processing_info = gr.JSON(label="Processing Info")
        
        # History tab
        with gr.Row():
            with gr.Column():
                gr.Markdown("### 📜 Recent Generations")
                history_table = gr.Dataframe(
                    headers=["Time", "Language", "Text Preview", "Duration"],
                    label="Generation History"
                )
        
        # About section
        with gr.Row():
            with gr.Column():
                gr.Markdown("""
                ### About SA Voices
                
                SA Voices is a voice agent supporting all 11 official South African languages:
                - **isiZulu**, **isiXhosa**, **isiNdebele** (Nguni languages)
                - **Sepedi**, **Sesotho**, **Setswana** (Sotho-Tswana languages)
                - **Xitsonga**, **siSwati**, **Tshivenda** (Tsonga-Venda languages)
                - **Afrikaans**, **English** (Germanic languages)
                
                Powered by [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) and 
                [WaxalNLP](https://huggingface.co/datasets/google/WaxalNLP) dataset.
                """)
        
        # Event handlers
        def synthesize_speech(
            text: str,
            language: str,
            auto_detect_lang: bool,
            voice_preset: str,
            speed: float,
            pitch: float
        ):
            if not text.strip():
                return None, {"error": "Please enter some text"}
            
            # Auto-detect if enabled
            if auto_detect_lang:
                detection = lang_detector.detect(text)
                if detection.is_reliable:
                    language = detection.language
                detected = f"{LANGUAGE_METADATA[language]['name']} ({detection.confidence:.0%})"
            else:
                detected = LANGUAGE_METADATA[language]['name']
            
            # Create request
            request = SynthesisRequest(
                text=text,
                language=language,
                voice_profile={"preset": voice_preset},
                speed=speed,
                pitch=pitch
            )
            
            # Generate
            try:
                result = tts_engine.synthesize(request)
                
                info = {
                    "language": language,
                    "detected": detected,
                    "processing_time": f"{result.processing_time:.2f}s",
                    "sample_rate": result.sample_rate,
                    "duration": f"{len(result.audio) / result.sample_rate:.2f}s"
                }
                
                return (result.sample_rate, result.audio), info
                
            except Exception as e:
                return None, {"error": str(e)}
        
        generate_btn.click(
            fn=synthesize_speech,
            inputs=[
                text_input,
                language_dropdown,
                auto_detect,
                voice_preset,
                speed_slider,
                pitch_slider
            ],
            outputs=[audio_output, processing_info]
        )
        
        # Language detection feedback
        def update_detected_lang(text):
            if text:
                detection = lang_detector.detect(text)
                lang_name = LANGUAGE_METADATA.get(
                    detection.language, 
                    {"name": detection.language}
                )["name"]
                return f"{lang_name} ({detection.confidence:.0%})"
            return ""
        
        text_input.change(
            fn=update_detected_lang,
            inputs=text_input,
            outputs=detected_lang
        )
    
    return app


def launch_ui(
    share: bool = False,
    server_name: str = "0.0.0.0",
    server_port: int = 7860
):
    """Launch the Gradio UI"""
    app = create_ui()
    app.launch(
        share=share,
        server_name=server_name,
        server_port=server_port
    )


if __name__ == "__main__":
    launch_ui()
