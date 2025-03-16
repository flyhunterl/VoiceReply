# VoiceReply 语音问答插件
**大家帮忙点点star 谢谢啦!**
> 本项目是 dify-on-wechat 的插件项目，用于以语音方式回答用户问题。项目思路来源于  [SearchMusic](https://github.com/Lingyuzhou111/SearchMusic)  项目，特此感谢。

这是一个支持语音问答的插件，用户可以通过发送"语音+问题"的形式获取AI的语音回答。

如果想使用免费TTS服务 可以查看本项目的分支 [VoiceReplyFree](https://github.com/flyhunterl/VoiceReplyFree))

## 功能特点

- 支持文本到语音的转换
- 使用OpenAI的GPT模型生成回答
- 使用硅基流动的语音合成服务生成自然的语音
- 支持自定义语音模型和声音
- 内置错误处理和重试机制

## 使用方法

1. 发送格式：
   - `语音+您的问题`
   - `语音 您的问题`
   - `语音您的问题`
2. 示例：
   - `语音+今天天气怎么样`
   - `语音 介绍一下你自己`
   - `语音讲个笑话`

## 安装方法

1. 将整个 `VoiceReply` 文件夹复制到 `plugins` 目录下
2. 重启应用程序

## 语音消息配置
> 以下源码修改方案来源于：[SearchMusic 部署教程](https://rq4rfacax27.feishu.cn/wiki/L4zFwQmbKiZezlkQ26jckBkcnod?fromScene=spaceOverview)

需要对 gewechat 源码进行以下修改：

### 1. 安装依赖

```bash
# 安装处理音频文件的必要依赖
sudo yum install ffmpeg   # FFmpeg用于处理音频、视频和其他多媒体文件
pip3 install pydub        # pydub用于简单、高效地处理音频文件
pip3 install pilk         # pilk用于处理微信语音文件（.silk格式）
```

### 2. 修改 gewechat_channel.py 文件

1. 增加依赖支持，在原有导入语句中添加：

```python
import uuid
import threading
import glob
from voice.audio_convert import mp3_to_silk, split_audio
```

2. 添加临时文件清理任务：

```python
def _start_cleanup_task(self):
    """启动定期清理任务"""
    def _do_cleanup():
        while True:
            try:
                self._cleanup_audio_files()
                self._cleanup_video_files()
                self._cleanup_image_files()
                time.sleep(30 * 60)  # 每30分钟执行一次清理
            except Exception as e:
                logger.error(f"[gewechat] 清理任务异常: {e}")
                time.sleep(60)

    cleanup_thread = threading.Thread(target=_do_cleanup, daemon=True)
    cleanup_thread.start()
```

3. 添加音频文件清理方法：

```python
def _cleanup_audio_files(self):
    """清理过期的音频文件"""
    try:
        tmp_dir = TmpDir().path()
        current_time = time.time()
        max_age = 3 * 60 * 60  # 音频文件最大保留3小时

        for ext in ['.mp3', '.silk']:
            pattern = os.path.join(tmp_dir, f'*{ext}')
            for fpath in glob.glob(pattern):
                try:
                    if current_time - os.path.getmtime(fpath) > max_age:
                        os.remove(fpath)
                        logger.debug(f"[gewechat] 清理过期音频文件: {fpath}")
                except Exception as e:
                    logger.warning(f"[gewechat] 清理音频文件失败 {fpath}: {e}")
    except Exception as e:
        logger.error(f"[gewechat] 音频文件清理任务异常: {e}")
```

### 3. 修改 audio_convert.py 文件

优化音频转换效果，提升音质（将采样率从24000提升至32000）：

```python
def mp3_to_silk(mp3_path: str, silk_path: str) -> int:
    """转换MP3文件为SILK格式，并优化音质"""
    try:
        audio = AudioSegment.from_file(mp3_path)
        audio = audio.set_channels(1)
        audio = audio.set_frame_rate(32000)
        
        pcm_path = os.path.splitext(mp3_path)[0] + '.pcm'
        audio.export(pcm_path, format='s16le', parameters=["-acodec", "pcm_s16le", "-ar", "32000", "-ac", "1"])
        
        try:
            pilk.encode(pcm_path, silk_path, pcm_rate=32000, tencent=True, complexity=2)
            duration = pilk.get_duration(silk_path)
            if duration <= 0:
                raise Exception("Invalid SILK duration")
            return duration
        finally:
            if os.path.exists(pcm_path):
                try:
                    os.remove(pcm_path)
                except Exception as e:
                    logger.warning(f"[audio_convert] 清理PCM文件失败: {e}")
    except Exception as e:
        logger.error(f"[audio_convert] MP3转SILK失败: {e}")
        return 0
```

这些修改将提供以下优化：

1. 支持语音消息的自动分段发送
2. 提高音频转换质量
3. 自动清理临时文件
4. 优化发送间隔

## 配置说明

在使用插件之前，需要在`config.json`中配置以下参数：

1. TTS（文本转语音）配置：
```json
{
    "base": "https://api.siliconflow.cn/v1",
    "api_key": "your_tts_api_key_here",
    "model": "FunAudioLLM/CosyVoice2-0.5B",
    "voice": "FunAudioLLM/CosyVoice2-0.5B:diana",
    "response_format": "mp3"
}
```

2. Chat（对话）配置：
```json
{
    "base": "https://api.openai.com/v1",
    "api_key": "your_chat_api_key_here",
    "model": "gpt-3.5-turbo",
    "temperature": 0.7
}
```

## 注意事项

1. 使用前请确保已正确配置API密钥
2. 语音生成可能需要一定时间，请耐心等待
3. 如果语音生成失败，插件会自动返回文字回答

## 错误处理

1. API请求失败时会自动重试3次
2. 生成的语音文件为空时会自动清理并返回错误信息
3. 配置文件加载失败时会使用默认配置


## 鸣谢
- [dify-on-wechat](https://github.com/hanfangyuan4396/dify-on-wechat) - 本项目的基础框架
- [SearchMusic](https://github.com/Lingyuzhou111/SearchMusic) - 项目思路来源
- [Gewechat](https://github.com/Devo919/Gewechat) - 微信机器人框架，个人微信二次开发的免费开源框架 


## 配置说明

在使用插件之前，需要在`config.json`中配置以下参数：

1. TTS（文本转语音）配置：
```json
{
    "base": "https://api.siliconflow.cn/v1",
    "api_key": "your_tts_api_key_here",
    "model": "FunAudioLLM/CosyVoice2-0.5B",
    "voice": "FunAudioLLM/CosyVoice2-0.5B:diana",
    "response_format": "mp3"
}
```

2. Chat（对话）配置：
```json
{
    "base": "https://api.openai.com/v1",
    "api_key": "your_chat_api_key_here",
    "model": "gpt-3.5-turbo",
    "temperature": 0.7
}
```

## 注意事项

1. 使用前请确保已正确配置API密钥
2. 语音生成可能需要一定时间，请耐心等待
3. 如果语音生成失败，插件会自动返回文字回答

## 错误处理

1. API请求失败时会自动重试3次
2. 生成的语音文件为空时会自动清理并返回错误信息
3. 配置文件加载失败时会使用默认配置


## 鸣谢
- [dify-on-wechat](https://github.com/hanfangyuan4396/dify-on-wechat) - 本项目的基础框架
- [SearchMusic](https://github.com/Lingyuzhou111/SearchMusic) - 项目思路来源
- [Gewechat](https://github.com/Devo919/Gewechat) - 微信机器人框架，个人微信二次开发的免费开源框架 


## 打赏

**您的打赏能让我在下一顿的泡面里加上一根火腿肠。**
![20250314_125818_133_copy](https://github.com/user-attachments/assets/33df0129-c322-4b14-8c41-9dc78618e220)




