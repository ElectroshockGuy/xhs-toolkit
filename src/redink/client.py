"""
红墨 (RedInk) API 客户端

封装红墨 API 的异步 HTTP 调用
"""

import os
import asyncio
import time
from pathlib import Path
from typing import List, Optional, Dict, Any

import aiohttp

from .models import RedInkPage, RedInkOutline, RedInkTaskState, RedInkGenerateResult
from ..utils.logger import get_logger

logger = get_logger(__name__)


class RedInkClient:
    """红墨 API 客户端"""
    
    def __init__(
        self,
        base_url: str = "https://redink.shunleite.com/api",
        timeout: int = 300,
        poll_interval: int = 3,
        max_retries: int = 2
    ):
        """
        初始化红墨客户端
        
        Args:
            base_url: API 基础地址
            timeout: 超时时间（秒）
            poll_interval: 轮询间隔（秒）
            max_retries: 失败重试次数
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_retries = max_retries
    
    async def health_check(self) -> Dict[str, Any]:
        """
        检查服务健康状态
        
        Returns:
            健康状态信息
        """
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{self.base_url}/health",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    return {"success": False, "error": f"HTTP {response.status}"}
            except asyncio.TimeoutError:
                return {"success": False, "error": "连接超时"}
            except Exception as e:
                return {"success": False, "error": str(e)}
    
    async def generate_outline(
        self,
        topic: str,
        page_count: int = 8,
        images: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        生成大纲
        
        Args:
            topic: 创作主题
            page_count: 页数
            images: 参考图片 base64 列表
            
        Returns:
            大纲生成结果
        """
        payload = {
            "topic": topic,
            "page_count": page_count
        }
        if images:
            payload["images"] = images
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.base_url}/outline",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    result = await response.json()
                    if response.status == 200 and result.get("success"):
                        return result
                    return {
                        "success": False,
                        "error": result.get("error", f"HTTP {response.status}")
                    }
            except asyncio.TimeoutError:
                return {"success": False, "error": "大纲生成超时"}
            except Exception as e:
                return {"success": False, "error": str(e)}
    
    async def generate_images(
        self,
        pages: List[Dict[str, Any]],
        full_outline: Optional[str] = None,
        user_topic: Optional[str] = None,
        user_images: Optional[List[str]] = None,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        批量生成图片（启动任务）
        
        Args:
            pages: 页面列表
            full_outline: 完整大纲
            user_topic: 用户主题
            user_images: 用户参考图
            task_id: 可选任务ID
            
        Returns:
            包含 task_id 的结果
        """
        payload = {"pages": pages}
        if full_outline:
            payload["full_outline"] = full_outline
        if user_topic:
            payload["user_topic"] = user_topic
        if user_images:
            payload["user_images"] = user_images
        if task_id:
            payload["task_id"] = task_id
        
        async with aiohttp.ClientSession() as session:
            try:
                # 使用 SSE 流式接口，但我们只需要获取 task_id
                # 发起请求并读取直到获得 finish 事件
                async with session.post(
                    f"{self.base_url}/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status != 200:
                        text = await response.text()
                        return {"success": False, "error": f"HTTP {response.status}: {text}"}
                    
                    task_id = None
                    images = []
                    completed = 0
                    failed = 0
                    failed_indices = []
                    
                    # 解析 SSE 流
                    async for line in response.content:
                        line = line.decode("utf-8").strip()
                        if not line or not line.startswith("data:"):
                            continue
                        
                        try:
                            import json
                            data = json.loads(line[5:].strip())
                            event_type = data.get("type") or data.get("status")
                            
                            # 处理 finish 事件
                            if "task_id" in data:
                                task_id = data["task_id"]
                            if "images" in data:
                                images = data["images"]
                            if "completed" in data:
                                completed = data["completed"]
                            if "failed" in data:
                                failed = data["failed"]
                            if "failed_indices" in data:
                                failed_indices = data["failed_indices"]
                            
                            # 进度回调（可以在这里发送进度更新）
                            if event_type == "progress":
                                current = data.get("current", 0)
                                total = data.get("total", 1)
                                logger.info(f"📊 生成进度: {current}/{total}")
                            
                        except json.JSONDecodeError:
                            continue
                    
                    return {
                        "success": True,
                        "task_id": task_id,
                        "images": images,
                        "completed": completed,
                        "failed": failed,
                        "failed_indices": failed_indices
                    }
                    
            except asyncio.TimeoutError:
                return {"success": False, "error": "图片生成超时"}
            except Exception as e:
                logger.error(f"图片生成失败: {e}")
                return {"success": False, "error": str(e)}
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态信息
        """
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{self.base_url}/task/{task_id}",
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    result = await response.json()
                    return result
            except Exception as e:
                return {"success": False, "error": str(e)}
    
    async def retry_failed(
        self,
        task_id: str,
        pages: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        重试失败的图片
        
        Args:
            task_id: 任务ID
            pages: 需要重试的页面列表
            
        Returns:
            重试结果
        """
        payload = {
            "task_id": task_id,
            "pages": pages
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.base_url}/retry-failed",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status != 200:
                        text = await response.text()
                        return {"success": False, "error": f"HTTP {response.status}: {text}"}
                    
                    # SSE 流处理
                    completed = 0
                    failed = 0
                    
                    async for line in response.content:
                        line = line.decode("utf-8").strip()
                        if not line or not line.startswith("data:"):
                            continue
                        
                        try:
                            import json
                            data = json.loads(line[5:].strip())
                            if "completed" in data:
                                completed = data["completed"]
                            if "failed" in data:
                                failed = data["failed"]
                        except json.JSONDecodeError:
                            continue
                    
                    return {
                        "success": True,
                        "completed": completed,
                        "failed": failed
                    }
                    
            except Exception as e:
                return {"success": False, "error": str(e)}
    
    async def download_images(
        self,
        task_id: str,
        output_dir: str,
        filenames: Optional[List[str]] = None
    ) -> List[str]:
        """
        下载任务生成的图片
        
        Args:
            task_id: 任务ID
            output_dir: 输出目录
            filenames: 要下载的文件名列表（为空则从任务状态获取）
            
        Returns:
            本地图片路径列表
        """
        # 确保输出目录存在
        output_path = Path(output_dir) / task_id
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 如果没有指定文件名，从任务状态获取
        if not filenames:
            status = await self.get_task_status(task_id)
            if not status.get("success"):
                logger.error(f"获取任务状态失败: {status.get('error')}")
                return []
            
            state = status.get("state", {})
            generated = state.get("generated", {})
            filenames = list(generated.values())
        
        downloaded = []
        async with aiohttp.ClientSession() as session:
            for filename in filenames:
                try:
                    url = f"{self.base_url}/images/{task_id}/{filename}?thumbnail=false"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                        if response.status == 200:
                            local_path = output_path / filename
                            content = await response.read()
                            with open(local_path, "wb") as f:
                                f.write(content)
                            downloaded.append(str(local_path))
                            logger.info(f"✅ 下载图片: {filename}")
                        else:
                            logger.warning(f"⚠️ 下载失败 {filename}: HTTP {response.status}")
                except Exception as e:
                    logger.error(f"❌ 下载图片 {filename} 失败: {e}")
        
        return downloaded
    
    async def create_post(
        self,
        topic: str,
        page_count: int = 8,
        reference_images: Optional[List[str]] = None,
        output_dir: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> RedInkGenerateResult:
        """
        一键生成完整流程
        
        Args:
            topic: 创作主题
            page_count: 页数
            reference_images: 参考图片 base64 列表
            output_dir: 图片输出目录
            progress_callback: 进度回调函数
            
        Returns:
            生成结果
        """
        start_time = time.time()
        
        def report_progress(phase: str, message: str, percent: int = 0):
            """报告进度"""
            if progress_callback:
                progress_callback(phase, message, percent)
            logger.info(f"[{phase}] {message}")
        
        # 1. 健康检查
        report_progress("健康检查", "正在检查服务状态...", 5)
        health = await self.health_check()
        if not health.get("success"):
            return RedInkGenerateResult(
                success=False,
                task_id="",
                topic=topic,
                outline="",
                pages=[],
                stats={},
                error=f"服务不可用: {health.get('error')}"
            )
        
        # 2. 生成大纲
        report_progress("生成大纲", f"正在为「{topic}」生成大纲...", 10)
        outline_result = await self.generate_outline(topic, page_count, reference_images)
        if not outline_result.get("success"):
            return RedInkGenerateResult(
                success=False,
                task_id="",
                topic=topic,
                outline="",
                pages=[],
                stats={},
                error=f"大纲生成失败: {outline_result.get('error')}"
            )
        
        outline = RedInkOutline.from_dict(outline_result)
        report_progress("生成大纲", f"大纲生成完成，共 {len(outline.pages)} 页", 20)
        
        # 3. 生成图片
        report_progress("生成图片", "开始生成图片...", 25)
        pages_dict = [p.to_dict() for p in outline.pages]
        generate_result = await self.generate_images(
            pages=pages_dict,
            full_outline=outline.outline,
            user_topic=topic,
            user_images=reference_images
        )
        
        if not generate_result.get("success"):
            return RedInkGenerateResult(
                success=False,
                task_id="",
                topic=topic,
                outline=outline.outline,
                pages=outline.pages,
                stats={},
                error=f"图片生成失败: {generate_result.get('error')}"
            )
        
        task_id = generate_result.get("task_id", "")
        report_progress("生成图片", f"图片生成任务已创建: {task_id}", 50)
        
        # 4. 等待完成并处理重试
        retry_count = 0
        while retry_count <= self.max_retries:
            # 轮询状态
            for i in range(int(self.timeout / self.poll_interval)):
                await asyncio.sleep(self.poll_interval)
                
                status = await self.get_task_status(task_id)
                if not status.get("success"):
                    continue
                
                state = RedInkTaskState.from_dict(status.get("state", {}))
                total = len(outline.pages)
                done = state.total_generated
                failed = state.total_failed
                
                progress = 50 + int((done / total) * 40)
                report_progress(
                    "生成图片",
                    f"进度: {done}/{total}，失败: {failed}",
                    progress
                )
                
                # 检查是否全部完成
                if done + failed >= total:
                    break
            
            # 获取最终状态
            final_status = await self.get_task_status(task_id)
            final_state = RedInkTaskState.from_dict(final_status.get("state", {}))
            
            # 如果没有失败或已达到最大重试次数
            if final_state.total_failed == 0 or retry_count >= self.max_retries:
                break
            
            # 重试失败的图片
            retry_count += 1
            report_progress(
                "重试失败",
                f"第 {retry_count} 次重试 {final_state.total_failed} 张失败图片...",
                90
            )
            
            failed_pages = [
                p.to_dict() for p in outline.pages
                if str(p.index) in final_state.failed
            ]
            await self.retry_failed(task_id, failed_pages)
        
        # 5. 下载图片
        local_images = []
        if output_dir:
            report_progress("下载图片", "正在下载图片到本地...", 95)
            local_images = await self.download_images(task_id, output_dir)
            report_progress("下载图片", f"已下载 {len(local_images)} 张图片", 98)
        
        # 6. 构建结果
        duration = time.time() - start_time
        final_status = await self.get_task_status(task_id)
        final_state = RedInkTaskState.from_dict(final_status.get("state", {}))
        
        # 更新页面的图片 URL
        for page in outline.pages:
            filename = final_state.generated.get(str(page.index))
            if filename:
                page.image_url = f"{self.base_url}/images/{task_id}/{filename}"
        
        report_progress("完成", f"生成完成，耗时 {duration:.1f} 秒", 100)
        
        return RedInkGenerateResult(
            success=True,
            task_id=task_id,
            topic=topic,
            outline=outline.outline,
            pages=outline.pages,
            stats={
                "total": len(outline.pages),
                "completed": final_state.total_generated,
                "failed": final_state.total_failed,
                "duration_seconds": round(duration, 1),
                "retries": retry_count
            },
            download_url=f"{self.base_url.replace('/api', '')}/api/history/{task_id}/download",
            local_images=local_images
        )
