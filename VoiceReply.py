#!/usr/bin/env python3
# encoding:utf-8

import json
import requests
import os
import time
import random
import plugins
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from common.tmp_dir import TmpDir
from plugins import *

@plugins.register(
    name="VoiceReply",
    desire_priority=10,
    desc="语音问答插件：发送'语音+问题'、'语音 问题'或'语音问题'，机器人将以语音方式回答",
    version="1.0",
    author="AI Assistant",
)
class VoiceReply(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        self.config_file = os.path.join(os.path.dirname(__file__), "config.json")
        self.config = self.load_config()
        logger.info("[VoiceReply] 插件已初始化")

    def load_config(self):
        """
        加载配置文件
        :return: 配置字典
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    logger.info(f"[VoiceReply] 成功加载配置文件")
                    return config
            else:
                # 创建默认配置
                default_config = {
                    "tts": {
                        "base": "https://api.siliconflow.cn/v1",
                        "api_key": "your_tts_api_key_here",
                        "model": "FunAudioLLM/CosyVoice2-0.5B",
                        "voice": "FunAudioLLM/CosyVoice2-0.5B:diana",
                        "response_format": "mp3"
                    },
                    "chat": {
                        "base": "https://api.openai.com/v1",
                        "api_key": "your_chat_api_key_here",
                        "model": "gpt-3.5-turbo",
                        "temperature": 0.7
                    }
                }
                with open(self.config_file, "w", encoding="utf-8") as f:
                    json.dump(default_config, f, indent=4)
                logger.info(f"[VoiceReply] 已创建默认配置文件")
                return default_config
        except Exception as e:
            logger.error(f"[VoiceReply] 加载配置文件失败: {e}")
            return {
                "tts": {
                    "base": "https://api.siliconflow.cn/v1",
                    "api_key": "",
                    "model": "FunAudioLLM/CosyVoice2-0.5B",
                    "voice": "FunAudioLLM/CosyVoice2-0.5B:diana",
                    "response_format": "mp3"
                },
                "chat": {
                    "base": "https://api.openai.com/v1",
                    "api_key": "",
                    "model": "gpt-3.5-turbo",
                    "temperature": 0.7
                }
            }

    def get_chat_response(self, question):
        """
        使用Chat模型获取回答
        :param question: 用户的问题
        :return: AI的回答文本
        """
        try:
            if not self.config["chat"]["api_key"] or self.config["chat"]["api_key"] == "your_chat_api_key_here":
                return "请先在config.json中配置正确的Chat API密钥"

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config['chat']['api_key']}"
            }

            model = self.config["chat"].get("model", "gpt-3.5-turbo")
            temperature = self.config["chat"].get("temperature", 0.7)

            data = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个友好的AI助手，请用简洁明了的语言回答问题。"
                    },
                    {
                        "role": "user",
                        "content": question
                    }
                ],
                "temperature": temperature
            }

            for retry in range(3):
                try:
                    response = requests.post(
                        f"{self.config['chat']['base']}/chat/completions",
                        headers=headers,
                        json=data,
                        timeout=30
                    )
                    response.raise_for_status()
                    break
                except requests.RequestException as e:
                    if retry == 2:
                        logger.error(f"[VoiceReply] Chat API请求失败，重试次数已用完: {e}")
                        return f"抱歉，回答问题时出现错误: {str(e)}"
                    logger.warning(f"[VoiceReply] Chat API请求重试 {retry + 1}/3: {e}")
                    time.sleep(1)

            if response.status_code == 200:
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"].strip()
                else:
                    return "抱歉，获取回答失败，API返回结果异常"
            else:
                logger.error(f"[VoiceReply] Chat API请求失败: {response.status_code} {response.text}")
                return f"抱歉，获取回答失败，API请求错误: {response.status_code}"

        except Exception as e:
            logger.error(f"[VoiceReply] 获取回答时出错: {e}")
            return f"抱歉，获取回答时发生错误: {str(e)}"

    def text_to_speech(self, text):
        """
        使用TTS模型将文本转换为语音
        :param text: 要转换的文本
        :return: 语音文件路径或None（如果转换失败）
        """
        try:
            if not self.config["tts"]["api_key"] or self.config["tts"]["api_key"] == "your_tts_api_key_here":
                logger.error("[VoiceReply] 未配置TTS API密钥")
                return None

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config['tts']['api_key']}"
            }

            model = self.config["tts"].get("model", "FunAudioLLM/CosyVoice2-0.5B")
            voice = self.config["tts"].get("voice", "FunAudioLLM/CosyVoice2-0.5B:diana")
            response_format = self.config["tts"].get("response_format", "mp3")

            data = {
                "model": model,
                "input": text,
                "voice": voice,
                "response_format": response_format
            }

            logger.debug(f"[VoiceReply] TTS请求参数: {json.dumps(data)}")

            for retry in range(3):
                try:
                    response = requests.post(
                        f"{self.config['tts']['base']}/audio/speech",
                        headers=headers,
                        json=data,
                        timeout=30
                    )
                    response.raise_for_status()
                    break
                except requests.RequestException as e:
                    if retry == 2:
                        logger.error(f"[VoiceReply] TTS API请求失败，重试次数已用完: {e}")
                        return None
                    logger.warning(f"[VoiceReply] TTS API请求重试 {retry + 1}/3: {e}")
                    time.sleep(1)

            if response.status_code == 200:
                tmp_dir = TmpDir().path()
                timestamp = int(time.time())
                random_str = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=6))
                mp3_path = os.path.join(tmp_dir, f"reply_{timestamp}_{random_str}.mp3")

                with open(mp3_path, "wb") as f:
                    f.write(response.content)

                if os.path.getsize(mp3_path) == 0:
                    logger.error("[VoiceReply] 下载的文件大小为0")
                    os.remove(mp3_path)
                    return None

                logger.info(f"[VoiceReply] 语音生成完成: {mp3_path}, 大小: {os.path.getsize(mp3_path)/1024:.2f}KB")
                return mp3_path

            else:
                logger.error(f"[VoiceReply] TTS API请求失败: {response.status_code} {response.text}")
                return None

        except Exception as e:
            logger.error(f"[VoiceReply] 文本转语音时出错: {e}")
            if 'mp3_path' in locals() and os.path.exists(mp3_path):
                try:
                    os.remove(mp3_path)
                except Exception as clean_error:
                    logger.error(f"[VoiceReply] 清理失败的语音文件时出错: {clean_error}")
            return None

    def on_handle_context(self, e_context: EventContext):
        """
        处理上下文事件
        :param e_context: 事件上下文
        """
        if e_context["context"].type != ContextType.TEXT:
            return

        content = e_context["context"].content.strip()
        logger.info(f"[VoiceReply] 正在处理内容: {content}")

        # 处理语音问答命令，支持三种格式："语音+"、"语音 "和直接"语音"后跟问题
        if content.startswith("语音+") or content.startswith("语音 ") or (content.startswith("语音") and len(content) > 2):
            logger.info(f"[VoiceReply] 处理语音问答: {content}")

            # 提取问题
            if content.startswith("语音+"):
                question = content[3:].strip()
            elif content.startswith("语音 "):
                question = content[3:].strip()
            else:  # 处理直接"语音"后跟问题的格式
                question = content[2:].strip()
                
            if not question:
                reply = Reply()
                reply.type = ReplyType.TEXT
                reply.content = "请在'语音'后输入您的问题"
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK
                return

            # 获取AI回答
            answer = self.get_chat_response(question)
            logger.info(f"[VoiceReply] AI回答: {answer}")

            # 生成语音回复
            voice_path = self.text_to_speech(answer)

            if voice_path:
                logger.info(f"[VoiceReply] 生成语音文件: {voice_path}")

                # 发送语音消息
                reply = Reply()
                reply.type = ReplyType.VOICE
                reply.content = voice_path
                e_context["reply"] = reply

                # 阻止请求传递给其他插件
                e_context.action = EventAction.BREAK_PASS
                return True
            else:
                logger.warning("[VoiceReply] 语音生成失败")

                # 发送文本回复
                reply = Reply()
                reply.type = ReplyType.TEXT
                reply.content = f"语音生成失败，这是文字回答：\n{answer}"
                e_context["reply"] = reply

                e_context.action = EventAction.BREAK_PASS
                return True

    def get_help_text(self, **kwargs):
        """
        获取插件帮助文本
        :return: 帮助文本
        """
        help_text = "🎤 语音问答插件 🎤\n\n"
        help_text += "使用方法：\n"
        help_text += "- 发送 '语音+您的问题'、'语音 您的问题' 或 '语音您的问题' 获取AI的语音回答\n"
        help_text += "例如：语音+今天天气怎么样、语音 讲个笑话、语音你好啊\n\n"
        help_text += "注意：请先在config.json中配置正确的API密钥"
        return help_text 