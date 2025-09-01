#!/usr/bin/env python3

import requests
import os
from PIL import Image
import json
from typing import Optional, Dict, Any, Tuple, Callable
import time
import threading
import queue
from dataclasses import dataclass
from enum import Enum


class E621APIError(Exception):
    """Custom exception for E621 API errors."""
    pass


class RequestType(Enum):
    """Types of requests that can be queued."""
    GET_POST = "get_post"
    DOWNLOAD_IMAGE = "download_image"


@dataclass
class QueuedRequest:
    """Represents a queued request."""
    request_type: RequestType
    args: tuple
    kwargs: dict
    callback: Optional[Callable] = None
    error_callback: Optional[Callable] = None
    future: Optional[threading.Event] = None
    result: Any = None
    exception: Optional[Exception] = None


class E621RequestQueue:
    """Thread-safe queue for E621 API requests with rate limiting."""
    
    def __init__(self, rate_limit_delay: float = 0.5):
        """
        Initialize the request queue.
        
        Args:
            rate_limit_delay: Minimum delay between requests in seconds
        """
        self.rate_limit_delay = rate_limit_delay
        self.request_queue = queue.Queue()
        self.worker_thread = None
        self.is_running = False
        self.last_request_time = 0
        self.lock = threading.Lock()
        
    def start_worker(self):
        """Start the worker thread."""
        if not self.is_running:
            self.is_running = True
            self.worker_thread = threading.Thread(target=self._run, daemon=True)
            self.worker_thread.start()
    
    def shutdown(self):
        """Shutdown the worker thread."""
        self.is_running = False
        if self.worker_thread:
            self.worker_thread.join()
            
    def _run(self):
        """
        Main loop for the worker thread. Processes requests from the queue.
        """
        while self.is_running:
            try:
                # Use a timeout to avoid blocking indefinitely if the queue is empty
                queued_request = self.request_queue.get(timeout=1)
                
                # Rate limit
                with self.lock:
                    elapsed = time.time() - self.last_request_time
                    if elapsed < self.rate_limit_delay:
                        time.sleep(self.rate_limit_delay - elapsed)
                    self.last_request_time = time.time()

                try:
                    if queued_request.request_type == RequestType.GET_POST:
                        post_id = queued_request.args[0]
                        response = requests.get(
                            f"https://e621.net/posts/{post_id}.json",
                            headers={"User-Agent": "e26D-client/1.0.0"},
                            timeout=10 # Added timeout
                        )
                        response.raise_for_status()
                        queued_request.result = response.json()
                    
                    elif queued_request.request_type == RequestType.DOWNLOAD_IMAGE:
                        url = queued_request.args[0]
                        output_path = queued_request.args[1]
                        
                        response = requests.get(
                            url,
                            headers={"User-Agent": "e26D-client/1.0.0"},
                            stream=True,
                            timeout=60 # Added timeout
                        )
                        response.raise_for_status()
                        
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)
                        with open(output_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        
                        queued_request.result = output_path

                except requests.exceptions.Timeout as e:
                    queued_request.exception = E621APIError(f"Request timed out: {e}")
                except requests.exceptions.RequestException as e:
                    queued_request.exception = E621APIError(f"Request failed: {e}")
                except Exception as e:
                    queued_request.exception = e
                finally:
                    if queued_request.future:
                        queued_request.future.set()
                    self.request_queue.task_done()
            except queue.Empty:
                continue

    def queue_request(self, request_type: RequestType, *args, **kwargs) -> Any:
        """
        Queue a request and wait for the result.
        
        This method is blocking.
        """
        future = threading.Event()
        req = QueuedRequest(request_type, args, kwargs, future=future)
        self.request_queue.put(req)
        
        future.wait()
        
        if req.exception:
            raise req.exception
        
        return req.result


class E621PostManager:
    """Manages fetching, caching, and processing of e621 posts."""

    def __init__(self, database_dir: str = "./database/posts"):
        """
        Initialize the post manager.
        
        Args:
            database_dir: Directory to store cached post data
        """
        self.database_dir = database_dir
        self.client = E621RequestQueue()
        self.client.start_worker()
        self.lock = threading.Lock()
    
    def is_cached(self, post_id: int, file_type: str) -> bool:
        """
        Check if a post file is cached locally.

        Args:
            post_id: The ID of the post to check.
            file_type: The type of file to check ('json', 'image', 'preview', 'ascii', 'preview_ascii').

        Returns:
            True if the specified file is cached, False otherwise.
        """
        paths = self.get_post_paths(post_id)
        if file_type == 'json':
            return os.path.exists(paths['json'])
        elif file_type == 'image':
            return os.path.exists(paths['image'])
        elif file_type == 'preview':
            return os.path.exists(paths['preview'])
        elif file_type == 'ascii':
            return os.path.exists(paths['ascii'])
        elif file_type == 'preview_ascii':
            return os.path.exists(paths['preview_ascii'])
        return False
    
    # MODIFIED: Changed return type to a dictionary and added logic to fetch JSON first
    def get_post_paths(self, post_id: int) -> Dict[str, Optional[str]]:
        """
        Get the paths for a post's files.
        
        Args:
            post_id: The ID of the post.
            
        Returns:
            A dictionary containing the paths for json, image, and ascii files.
        """
        post_dir = self._get_post_dir(post_id)
        json_path = self._get_json_path(post_id)
        
        # Ensure JSON data is available first
        if not os.path.exists(json_path):
            post_data = self.get_post(post_id)
            if not post_data:
                return {
                    'json': None,
                    'image': None,
                    'preview': None,
                    'ascii': None,
                    'preview_ascii': None
                }
        
        file_ext = None
        # Read the JSON to find the image file extension if the file exists
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    post_data = json.load(f)
                    file_ext = post_data.get('post', {}).get('file', {}).get('ext')
            except (IOError, json.JSONDecodeError):
                pass
        
        paths = {
            'json': json_path,
            'image': self._get_image_path(post_id, file_ext) if file_ext else None,
            'preview': self._get_preview_path(post_id, file_ext) if file_ext else None,
            'ascii': os.path.join(post_dir, f"{post_id}.ansi"),
            'preview_ascii': os.path.join(post_dir, f"{post_id}_preview.ansi")
        }
        
        return paths

    def _get_post_dir(self, post_id: int) -> str:
        """Get the directory for a given post ID."""
        return os.path.join(self.database_dir, str(post_id))

    def _get_json_path(self, post_id: int) -> str:
        """Get the path for the JSON file."""
        return os.path.join(self._get_post_dir(post_id), f"{post_id}.json")

    def _get_image_path(self, post_id: int, file_ext: str) -> str:
        """Get the path for the image file."""
        return os.path.join(self._get_post_dir(post_id), f"{post_id}.{file_ext}")
    
    def _get_preview_path(self, post_id: int, file_ext: str) -> str:
        """Get the path for the preview image file."""
        return os.path.join(self._get_post_dir(post_id), f"{post_id}_preview.{file_ext}")

    def get_post(self, post_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch a post from the API or cache.
        
        Args:
            post_id: The ID of the post to fetch
            
        Returns:
            The post data as a dictionary, or None if not found
        """
        json_path = self._get_json_path(post_id)
        
        # Check cache first
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # If not in cache, fetch from API
        try:
            post_data = self.client.queue_request(RequestType.GET_POST, post_id)
            if post_data:
                # Cache the new data
                os.makedirs(os.path.dirname(json_path), exist_ok=True)
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(post_data, f, indent=4)
                return post_data
        except E621APIError as e:
            print(f"Error fetching post {post_id}: {e}")
            return None
    
    def fetch_and_cache_post(self, post_id: int) -> bool:
        """
        Fetch a post and its image, and store in the database.
        
        Args:
            post_id: The ID of the post to fetch
        
        Returns:
            True if successful, False otherwise
        """
        post_data = self.get_post(post_id)
        
        if not post_data or 'post' not in post_data:
            return False
            
        post = post_data['post']
        
        file_url = post['file']['url']
        file_ext = post['file']['ext']
        
        if not file_url:
            print(f"Post {post_id} has no file URL.")
            return False
        
        image_path = self._get_image_path(post_id, file_ext)
        
        # Check if image is already downloaded
        if os.path.exists(image_path):
            return True
            
        try:
            self.client.queue_request(RequestType.DOWNLOAD_IMAGE, file_url, image_path)
            return True
        except E621APIError as e:
            print(f"Error downloading image for post {post_id}: {e}")
            return False
    
    def ensure_preview_exists(self, post_id: int) -> bool:
        """
        Fetch the preview image and store in the database.
        
        Args:
            post_id: The ID of the post to fetch
        
        Returns:
            True if successful, False otherwise
        """
        post_data = self.get_post(post_id)
        
        if not post_data or 'post' not in post_data:
            return False
            
        post = post_data['post']
        
        preview_url = post['preview']['url']
        file_ext = post['file']['ext'] # Use original file extension for consistency
        
        if not preview_url:
            print(f"Post {post_id} has no preview URL.")
            return False
        
        preview_path = self._get_preview_path(post_id, file_ext)
        
        if os.path.exists(preview_path):
            return True
            
        try:
            self.client.queue_request(RequestType.DOWNLOAD_IMAGE, preview_url, preview_path)
            return True
        except E621APIError as e:
            print(f"Error downloading preview for post {post_id}: {e}")
            return False

    def get_cache_size(self) -> int:
        """
        Get the total size of cached data.
        
        Returns:
            Cache size in bytes
        """
        with self.lock:
            total_size = 0
            
            if not os.path.exists(self.database_dir):
                return 0
            
            for dirpath, dirnames, filenames in os.walk(self.database_dir):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if not os.path.islink(filepath):
                        try:
                            total_size += os.path.getsize(filepath)
                        except OSError:
                            # Skip files that can't be accessed
                            continue
            
            return total_size
    
    def list_cached_posts(self) -> list[int]:
        """
        List all post IDs that have a cached JSON file.
        
        Returns:
            A list of post IDs.
        """
        cached_posts = []
        if not os.path.exists(self.database_dir):
            return cached_posts
        
        for dir_name in os.listdir(self.database_dir):
            if dir_name.isdigit():
                post_id = int(dir_name)
                json_path = self._get_json_path(post_id)
                if os.path.exists(json_path):
                    cached_posts.append(post_id)
        return cached_posts

    def shutdown(self):
        """Shutdown the post manager and underlying client."""
        self.client.shutdown()
        
# Convenience functions for backward compatibility
def get_post(post_id: int) -> Optional[Dict[str, Any]]:
    """Convenience function to get a post."""
    client = E621RequestQueue()
    try:
        post_data = client.queue_request(RequestType.GET_POST, post_id)
        return post_data['post']
    except E621APIError:
        return None
    finally:
        client.shutdown()


def download_and_convert_post(post_id: int, output_dir: str = "./database/posts") -> bool:
    """Convenience function to download and convert a post."""
    manager = E621PostManager(output_dir)
    try:
        return manager.fetch_and_cache_post(post_id)
    except E621APIError:
        return False
    finally:
        manager.shutdown()