#!/usr/bin/env python3

import subprocess
import sys
import os
import re
import gzip
import json
import threading
import time
import argparse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any
import socket

# GUI imports
try:
    import tk
    from tk import ttk, scrolledtext
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

# Import our enhanced E621 library
from e621 import E621PostManager, E621APIError


class RequestLogger:
    """Thread-safe request logger for the GUI."""
    
    def __init__(self):
        self.logs = []
        self.lock = threading.Lock()
        self.max_logs = 1000  # Keep only last 1000 logs
    
    def log(self, message):
        with self.lock:
            timestamp = time.strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {message}"
            self.logs.append(log_entry)
            if len(self.logs) > self.max_logs:
                self.logs.pop(0)
    
    def get_logs(self):
        with self.lock:
            return self.logs.copy()


class MonitorGUI:
    """GUI window for monitoring the e26D server."""
    
    def __init__(self, server_instance, post_manager):
        self.server = server_instance
        self.post_manager = post_manager
        
        # Create main window
        self.root = tk.Tk()
        self.root.title("e26D Server Monitor")
        self.root.geometry("600x500")
        self.root.configure(bg='#1a1a1a')
        
        # Configure style for dark theme
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TLabel', background='#1a1a1a', foreground='#ffffff')
        style.configure('TButton', background='#0066cc', foreground='#ffffff')
        style.configure('TFrame', background='#1a1a1a')
        
        self.setup_gui()
        self.update_stats()
        
        # Start update loop
        self.update_loop()
    
    def setup_gui(self):
        """Setup the GUI layout."""
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Stats frame
        stats_frame = ttk.Frame(main_frame)
        stats_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Cache size
        self.cache_size_label = ttk.Label(stats_frame, text="Cache Size: Calculating...")
        self.cache_size_label.pack(anchor=tk.W)
        
        # Memory usage
        self.memory_label = ttk.Label(stats_frame, text="Memory Usage: Calculating...")
        self.memory_label.pack(anchor=tk.W)
        
        # Thread count
        self.threads_label = ttk.Label(stats_frame, text="Threads: Calculating...")
        self.threads_label.pack(anchor=tk.W)
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Delete empty cache folders button
        self.delete_empty_btn = ttk.Button(
            buttons_frame, 
            text="Delete Empty Cache Folders",
            command=self.delete_empty_folders
        )
        self.delete_empty_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Stop program button
        self.stop_btn = ttk.Button(
            buttons_frame,
            text="Stop Program",
            command=self.stop_program
        )
        self.stop_btn.pack(side=tk.LEFT)
        
        # Log frame
        log_frame = ttk.Frame(main_frame)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        # Log label
        ttk.Label(log_frame, text="Request Log:").pack(anchor=tk.W)
        
        # Log text area
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            height=20,
            bg='#2a2a2a',
            fg='#ffffff',
            insertbackground='#ffffff'
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
    
    def update_stats(self):
        """Update the statistics display."""
        try:
            # Calculate cache size
            cache_size_bytes = self.post_manager.get_cache_size()
            cache_size_mb = cache_size_bytes / (1024 * 1024)
            self.cache_size_label.config(text=f"Cache Size: {cache_size_mb:.2f} MB")
            
            # Get memory usage
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            self.memory_label.config(text=f"Memory Usage: {memory_mb:.2f} MB")
            
            # Get thread count
            thread_count = threading.active_count()
            self.threads_label.config(text=f"Threads: {thread_count}")
            
        except Exception as e:
            print(f"Error updating stats: {e}")
    
    def update_logs(self):
        """Update the log display."""
        try:
            if hasattr(self.server.handler_class, 'request_logger'):
                logs = self.server.handler_class.request_logger.get_logs()
                
                # Get current text and new logs
                current_text = self.log_text.get(1.0, tk.END)
                new_logs = "\n".join(logs)
                
                # Only update if content changed
                if current_text.strip() != new_logs.strip():
                    self.log_text.delete(1.0, tk.END)
                    self.log_text.insert(tk.END, new_logs)
                    self.log_text.see(tk.END)  # Auto-scroll to bottom
                    
        except Exception as e:
            print(f"Error updating logs: {e}")
    
    def delete_empty_folders(self):
        """Delete empty folders in the cache directory."""
        try:
            deleted_count = 0
            database_path = "./database/posts"
            
            if os.path.exists(database_path):
                for root, dirs, files in os.walk(database_path, topdown=False):
                    for dir_name in dirs:
                        dir_path = os.path.join(root, dir_name)
                        try:
                            # Check if directory is empty
                            if not os.listdir(dir_path):
                                os.rmdir(dir_path)
                                deleted_count += 1
                                print(f"Deleted empty directory: {dir_path}")
                        except OSError as e:
                            print(f"Could not delete {dir_path}: {e}")
            
            # Update button text temporarily
            original_text = self.delete_empty_btn.cget('text')
            self.delete_empty_btn.config(text=f"Deleted {deleted_count} folders")
            self.root.after(3000, lambda: self.delete_empty_btn.config(text=original_text))
            
        except Exception as e:
            print(f"Error deleting empty folders: {e}")
    
    def stop_program(self):
        """Stop the server and close the application."""
        try:
            print("Stopping server from GUI...")
            self.server.shutdown()
            self.root.quit()
            self.root.destroy()
            sys.exit(0)
        except Exception as e:
            print(f"Error stopping program: {e}")
    
    def update_loop(self):
        """Main update loop for the GUI."""
        try:
            self.update_stats()
            self.update_logs()
            # Schedule next update
            self.root.after(1000, self.update_loop)  # Update every 1 second
        except Exception as e:
            print(f"Error in update loop: {e}")
    
    def run(self):
        """Run the GUI main loop."""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.stop_program()


class E621ASCIIHandler(SimpleHTTPRequestHandler):
    # Class-level thread pool for handling ASCII conversions
    ascii_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ascii_worker")
    # Class-level post manager instance, initialized once on first request
    post_manager = None
    # Request logger for GUI
    request_logger = RequestLogger()
    
    def __init__(self, *args, **kwargs):
        # Initialize the E621 post manager once for the class
        if E621ASCIIHandler.post_manager is None:
            print("Initializing E621PostManager...")
            E621ASCIIHandler.post_manager = E621PostManager()
            
        # Set the directory to serve files from
        super().__init__(*args, directory="./web", **kwargs)
    
    def do_GET(self):
        try:
            parsed_path = urlparse(self.path)
            
            # Log the request
            client_ip = self.client_address[0]
            self.request_logger.log(f"GET {self.path} from {client_ip}")
            
            # Handle API calls
            if parsed_path.path.startswith('/api/'):
                self.handle_api(parsed_path)
            else:
                # Serve files from ./web directory
                super().do_GET()
        except (socket.timeout, ConnectionResetError, BrokenPipeError) as e:
            # Catch common socket errors that occur when the client disconnects
            self.request_logger.log(f"Client connection error: {e}")
            print(f"Client connection closed prematurely: {e}", file=sys.stderr)
            # Do not try to send an error response to a closed socket
    
    def handle_api(self, parsed_path):
        """Handle API endpoints."""
        path_parts = parsed_path.path.split('/')
        
        if len(path_parts) >= 3 and path_parts[2] == 'listCache':
            self.handle_list_cache_request()
        elif len(path_parts) >= 3 and path_parts[2] == 'post':
            if len(path_parts) >= 4:
                post_id = path_parts[3]
                self.handle_post_request(post_id)
            else:
                self.send_error(400, "Post ID required")
        elif len(path_parts) >= 5 and path_parts[2] == 'previewImage' and path_parts[3] == 'post':
            post_id = path_parts[4]
            self.handle_preview_image_request(post_id)
        else:
            self.send_error(404, "API endpoint not found")
    
    def handle_list_cache_request(self):
        """Handle requests for listing all cached post IDs."""
        try:
            cached_ids = self.post_manager.list_cached_posts()
            
            # Create JSON response
            json_response = json.dumps(cached_ids)
            
            # Send response headers
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(json_response.encode('utf-8'))))
            self.send_header('Cache-Control', 'no-cache')  # Don't cache this as it changes
            self.send_header('Access-Control-Allow-Origin', '*')  # Allow CORS
            self.end_headers()
            
            # Send the JSON data
            self.wfile.write(json_response.encode('utf-8'))
            
            self.request_logger.log(f"Served cache list with {len(cached_ids)} entries")
            print(f"Served cache list with {len(cached_ids)} entries")
            
        except Exception as e:
            self.send_error(500, f"Error listing cache: {str(e)}")
            self.request_logger.log(f"Error listing cache: {e}")
            print(f"Error listing cache: {e}", file=sys.stderr)
    
    def handle_post_request(self, post_id_str):
        """Handle requests for e621 posts."""
        try:
            # Validate that post_id is an integer
            try:
                post_id = int(post_id_str)
                if post_id <= 0:
                    raise ValueError("Post ID must be positive")
            except ValueError:
                self.send_error(400, "Invalid post ID: must be a positive integer")
                return
            
            self.request_logger.log(f"Processing post {post_id}")
            paths = self.post_manager.get_post_paths(post_id)
            
            # Check if ASCII file already exists
            if self.post_manager.is_cached(post_id, 'ascii'):
                self.request_logger.log(f"Serving cached ASCII for post {post_id}")
                print(f"Serving cached ASCII for post {post_id}")
                self.serve_ascii_file(paths['ascii'])
                return
            
            # Post doesn't exist locally, try to fetch from e621
            self.request_logger.log(f"Post {post_id} not cached, fetching from e621...")
            print(f"Post {post_id} not cached, fetching from e621...")
            try:
                if self.post_manager.fetch_and_cache_post(post_id):
                    # Successfully downloaded and converted to image
                    # Now convert to ASCII
                    if self.convert_to_ascii(paths['image'], paths['ascii']):
                        self.request_logger.log(f"Successfully converted post {post_id} to ASCII")
                        self.serve_ascii_file(paths['ascii'])
                    else:
                        self.request_logger.log(f"Failed to convert post {post_id} to ASCII")
                        self.send_error(500, f"Failed to convert post {post_id} to ASCII")
                else:
                    self.request_logger.log(f"Post {post_id} not found on e621")
                    self.send_error(404, f"Post {post_id} not found on e621")
            except E621APIError as e:
                if "not found" in str(e).lower():
                    self.request_logger.log(f"Post {post_id} not found on e621: {e}")
                    self.send_error(404, f"Post {post_id} not found on e621")
                else:
                    self.request_logger.log(f"E621 API error for post {post_id}: {e}")
                    self.send_error(400, f"E621 API error: {str(e)}")
            except Exception as e:
                self.request_logger.log(f"Unexpected error for post {post_id}: {e}")
                self.send_error(500, f"Unexpected error: {str(e)}")
                
        except Exception as e:
            self.request_logger.log(f"Internal server error for post {post_id_str}: {e}")
            self.send_error(500, f"Internal server error: {str(e)}")
            print(f"Error handling post {post_id_str}: {e}", file=sys.stderr)
    
    def handle_preview_image_request(self, post_id_str):
        """Handle requests for preview ASCII art."""
        try:
            # Validate that post_id is an integer
            try:
                post_id = int(post_id_str)
                if post_id <= 0:
                    raise ValueError("Post ID must be positive")
            except ValueError:
                self.send_error(400, "Invalid post ID: must be a positive integer")
                return
            
            self.request_logger.log(f"Processing preview for post {post_id}")
            paths = self.post_manager.get_post_paths(post_id)
            
            # Check if preview ASCII already exists
            if self.post_manager.is_cached(post_id, 'preview_ascii'):
                self.request_logger.log(f"Serving cached preview ASCII for post {post_id}")
                print(f"Serving cached preview ASCII for post {post_id}")
                self.serve_ascii_file(paths['preview_ascii'])
                return
            
            # Preview ASCII doesn't exist, need to create it
            try:
                # Ensure preview image exists (this may trigger a download)
                if self.post_manager.ensure_preview_exists(post_id):
                    # Convert preview image to ASCII
                    if self.convert_to_ascii(paths['preview'], paths['preview_ascii']):
                        self.request_logger.log(f"Successfully created preview ASCII for post {post_id}")
                        self.serve_ascii_file(paths['preview_ascii'])
                    else:
                        self.request_logger.log(f"Failed to create preview ASCII for post {post_id}")
                        self.send_error(500, f"Failed to create preview ASCII for post {post_id}")
                else:
                    self.request_logger.log(f"Post {post_id} not found or failed to process")
                    self.send_error(404, f"Post {post_id} not found on e621 or failed to process")
                    
            except E621APIError as e:
                self.request_logger.log(f"E621 API error for preview {post_id}: {e}")
                self.send_error(400, f"E621 API error: {str(e)}")
            except Exception as e:
                self.request_logger.log(f"Unexpected error for preview {post_id}: {e}")
                self.send_error(500, f"Unexpected error: {str(e)}")
                
        except Exception as e:
            self.request_logger.log(f"Internal server error for preview {post_id_str}: {e}")
            self.send_error(500, f"Internal server error: {str(e)}")
            print(f"Error handling preview ASCII for post {post_id_str}: {e}", file=sys.stderr)
    
    def convert_to_ascii(self, image_path, output_path):
        """Convert image to ASCII art using the asciiArt tool."""
        try:
            # Run the asciiArt command with width limit for better quality
            # Format: ./asciiArt [image_path] -W 600 -C -c
            result = subprocess.run(
                ['./asciiArt', image_path, '-W', '200', '-C', '-c'],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Save ASCII art to file
            with open(output_path, 'w') as f:
                f.write(result.stdout)
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"ASCII conversion failed: {e.stderr}")
            return False
        except FileNotFoundError:
            print("Error: './asciiArt' executable not found")
            return False
        except Exception as e:
            print(f"ASCII conversion error: {e}")
            return False

    def serve_ascii_file(self, ascii_file_path):
        """Serve ASCII art file as a clean HTML div with inline styles."""
        try:
            with open(ascii_file_path, 'r') as f:
                ascii_content = f.read()
            
            # Convert ANSI codes to compact HTML
            html_content, css = self.ansi_to_compact_html(ascii_content)
            
            # Create a clean div with inline styles - headless and pasteable
            html_fragment = f'<div style="white-space:pre;overflow-x:auto;{css}">{html_content}</div>'
            
            # Check if client accepts gzip encoding
            accept_encoding = self.headers.get('Accept-Encoding', '')
            use_gzip = 'gzip' in accept_encoding
            
            # Prepare response data
            if use_gzip:
                compressed_data = gzip.compress(html_fragment.encode('utf-8'))
                response_data = compressed_data
                content_encoding = 'gzip'
            else:
                response_data = html_fragment.encode('utf-8')
                content_encoding = None
            
            # Send response headers
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            if content_encoding:
                self.send_header('Content-Encoding', content_encoding)
            self.send_header('Content-Length', str(len(response_data)))
            self.send_header('Cache-Control', 'max-age=86400')  # Cache for 24 hours
            self.end_headers()
            
            # Send the content
            self.wfile.write(response_data)
            
        except (socket.timeout, ConnectionResetError, BrokenPipeError) as e:
            # Handle cases where the client closes the connection during or after the write
            self.request_logger.log(f"Client disconnected while serving file: {ascii_file_path}")
            print(f"Client disconnected while serving file: {ascii_file_path}. Error: {e}")
            # Do not try to send an error response to a closed socket
        except Exception as e:
            # For other unexpected errors, try to send a 500 error
            self.send_error(500, f"Error serving ASCII file: {str(e)}")
            self.request_logger.log(f"Error serving ASCII file {ascii_file_path}: {e}")
            print(f"Error serving ASCII file {ascii_file_path}: {e}", file=sys.stderr)
    
    def ansi_to_compact_html(self, text):
        """Convert ANSI color codes to HTML with inline styles."""
        # Remove reset codes and replace with closing spans
        text = re.sub(r'\x1b\[0m', '</span>', text)
        
        # Handle 24-bit RGB colors: \x1b[38;2;r;g;b;m
        def rgb_replace(match):
            r, g, b = match.groups()
            return f'<span style="color:rgb({r},{g},{b})">'
        
        text = re.sub(r'\x1b\[38;2;(\d+);(\d+);(\d+)m', rgb_replace, text)
        
        # Handle background 24-bit RGB colors: \x1b[48;2;r;g;b;m
        def bg_rgb_replace(match):
            r, g, b = match.groups()
            return f'<span style="background:rgb({r},{g},{b})">'
        
        text = re.sub(r'\x1b\[48;2;(\d+);(\d+);(\d+)m', bg_rgb_replace, text)
        
        # Handle 8-bit colors: \x1b[38;5;n;m (foreground)
        def color_256_replace(match):
            color_num = int(match.group(1))
            # Standard 16 colors
            if color_num < 16:
                colors = ['#000', '#800', '#080', '#880', '#008', '#808', '#088', '#ccc',
                         '#888', '#f00', '#0f0', '#ff0', '#00f', '#f0f', '#0ff', '#fff']
                rgb = colors[color_num] if color_num < len(colors) else '#fff'
            elif color_num < 232:
                # 216 color cube (6x6x6)
                color_num -= 16
                r = (color_num // 36) * 51
                g = ((color_num % 36) // 6) * 51
                b = (color_num % 6) * 51
                rgb = f"#{r:02x}{g:02x}{b:02x}"
            else:
                # Grayscale
                gray = (color_num - 232) * 10 + 8
                rgb = f"#{gray:02x}{gray:02x}{gray:02x}"
            
            return f'<span style="color:{rgb}">'
        
        text = re.sub(r'\x1b\[38;5;(\d+)m', color_256_replace, text)
        
        # Remove any remaining ANSI codes
        text = re.sub(r'\x1b\[[0-9;]*m', '', text)
        
        # Return text and empty CSS (since we're using inline styles now)
        return text, ""
    
    def log_message(self, format, *args):
        """Override to customize logging."""
        message = f"{self.address_string()} - {format % args}"
        print(message)
        self.request_logger.log(message)
    
    @classmethod
    def shutdown_executor(cls):
        """Shutdown the thread pool executor."""
        cls.ascii_executor.shutdown(wait=True)
    
    @classmethod
    def shutdown_post_manager(cls):
        """Shutdown the post manager."""
        if cls.post_manager:
            cls.post_manager.shutdown()


class ThreadedHTTPServer:
    """HTTP server that handles requests in separate threads."""
    
    def __init__(self, server_address, handler_class):
        self.server_address = server_address
        self.handler_class = handler_class
        self.httpd = None
        self.is_running = False
    
    def start_server(self):
        """Start the HTTP server."""
        self.httpd = HTTPServer(self.server_address, self.handler_class)
        self.is_running = True
        
        try:
            self.httpd.serve_forever()
        except KeyboardInterrupt:
            self.shutdown()
    
    def shutdown(self):
        """Shutdown the server and thread pools."""
        self.is_running = False
        
        if self.httpd:
            print("\nShutting down HTTP server...")
            self.httpd.server_close()
        
        print("Shutting down ASCII processing thread pool...")
        self.handler_class.shutdown_executor()
        
        print("Shutting down E621 post manager...")
        self.handler_class.shutdown_post_manager()
        
        print("Server shutdown complete.")


def create_web_directory():
    """Create web directory with sample HTML if it doesn't exist."""
    if not os.path.exists('./web'):
        print("Warning: './web' directory not found. Creating it...")
        os.makedirs('./web', exist_ok=True)
        # Create a simple index.html
        with open('./web/index.html', 'w') as f:
            f.write("""<!DOCTYPE html>
<html>
<head>
    <title>E621 ASCII Art Server</title>
    <style>
        body { font-family: Arial, sans-serif; background: #1a1a1a; color: #fff; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        input, button { padding: 10px; margin: 5px; font-size: 16px; }
        input { background: #333; color: #fff; border: 1px solid #555; }
        button { background: #0066cc; color: #fff; border: none; cursor: pointer; }
        button:hover { background: #0052a3; }
        .example { margin-top: 20px; padding: 10px; background: #333; border-radius: 5px; }
        .cache-list { margin-top: 10px; max-height: 200px; overflow-y: auto; background: #222; padding: 10px; border-radius: 5px; }
        .cache-id { display: inline-block; margin: 2px; padding: 4px 8px; background: #555; border-radius: 3px; cursor: pointer; }
        .cache-id:hover { background: #666; }
        .status { margin: 10px 0; padding: 10px; border-radius: 5px; }
        .status.loading { background: #333; color: #ff0; }
        .status.success { background: #1a5c1a; color: #0f0; }
        .status.error { background: #5c1a1a; color: #f00; }
    </style>
</head>
<body>
    <div class="container">
        <h1>E621 ASCII Art Server</h1>
        <p>Enter an e621 post ID to convert it to ASCII art:</p>
        <p><strong>Enhanced with multithreading and GUI monitoring!</strong></p>
        
        <div>
            <input type="number" id="postId" placeholder="Enter post ID (e.g., 1234567)" min="1">
            <button onclick="viewPost()">View ASCII Art</button>
            <button onclick="viewPreview()">View Preview</button>
            <button onclick="loadCache()">Load Cache</button>
        </div>
        
        <div id="status" class="status" style="display: none;"></div>
        
        <div id="cacheSection" style="display: none;">
            <h3>Cached Posts:</h3>
            <div id="cacheList" class="cache-list"></div>
        </div>
        
        <div class="example">
            <h3>API Usage:</h3>
            <p>GET <code>/api/post/{id}</code> - Get ASCII art for e621 post ID (full size)</p>
            <p>GET <code>/api/previewImage/post/{id}</code> - Get ASCII art for e621 post ID (128x128 preview)</p>
            <p>GET <code>/api/listCache</code> - Get array of all cached post IDs</p>
            <p>Example: <a href="/api/post/1" target="_blank">/api/post/1</a></p>
            <p>Example: <a href="/api/previewImage/post/1" target="_blank">/api/previewImage/post/1</a></p>
            <p>Example: <a href="/api/listCache" target="_blank">/api/listCache</a></p>
            
            <h3>Features:</h3>
            <ul>
                <li>✅ Multithreaded request processing</li>
                <li>✅ Rate-limited E621 API requests (max 1 per 0.5 seconds)</li>
                <li>✅ Request queuing system</li>
                <li>✅ Thread-safe file operations</li>
                <li>✅ Concurrent ASCII art generation</li>
                <li>✅ Non-blocking API responses</li>
                <li>✅ GUI monitoring with -u flag</li>
            </ul>
        </div>
    </div>
    
    <script>
        function showStatus(message, type) {
            const status = document.getElementById('status');
            status.textContent = message;
            status.className = 'status ' + type;
            status.style.display = 'block';
        }
        
        function hideStatus() {
            document.getElementById('status').style.display = 'none';
        }
        
        function viewPost() {
            const postId = document.getElementById('postId').value;
            if (postId && parseInt(postId) > 0) {
                showStatus('Processing post ' + postId + ' (this may take a moment)...', 'loading');
                window.open('/api/post/' + postId, '_blank');
                setTimeout(hideStatus, 3000);
            } else {
                alert('Please enter a valid post ID');
            }
        }
        
        function viewPreview() {
            const postId = document.getElementById('postId').value;
            if (postId && parseInt(postId) > 0) {
                showStatus('Processing preview for post ' + postId + '...', 'loading');
                window.open('/api/previewImage/post/' + postId, '_blank');
                setTimeout(hideStatus, 3000);
            } else {
                alert('Please enter a valid post ID');
            }
        }
        
        function loadCache() {
            showStatus('Loading cache...', 'loading');
            fetch('/api/listCache')
                .then(response => response.json())
                .then(cacheIds => {
                    const cacheSection = document.getElementById('cacheSection');
                    const cacheList = document.getElementById('cacheList');
                    
                    if (cacheIds.length === 0) {
                        cacheList.innerHTML = '<p>No cached posts found.</p>';
                    } else {
                        cacheList.innerHTML = cacheIds.map(id => 
                            `<span class="cache-id" onclick="window.open('/api/post/${id}', '_blank')" title="Click to view post ${id}">${id}</span>`
                        ).join('');
                    }
                    
                    cacheSection.style.display = 'block';
                    showStatus('Cache loaded: ' + cacheIds.length + ' posts', 'success');
                    setTimeout(hideStatus, 3000);
                })
                .catch(error => {
                    console.error('Error loading cache:', error);
                    showStatus('Failed to load cache list', 'error');
                    setTimeout(hideStatus, 5000);
                });
        }
        
        // Allow Enter key to submit
        document.getElementById('postId').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                viewPost();
            }
        });
    </script>
</body>
</html>""")


def run_server_with_gui(server, post_manager):
    """Run the server in a separate thread and start the GUI."""
    def server_thread():
        try:
            server.start_server()
        except Exception as e:
            print(f"Server error: {e}")
    
    # Start server in background thread
    server_thread_obj = threading.Thread(target=server_thread, daemon=True)
    server_thread_obj.start()
    
    # Give the server a moment to start
    time.sleep(1)
    
    # Start GUI (this blocks until GUI is closed)
    gui = MonitorGUI(server, post_manager)
    gui.run()


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='e26D - E621 ASCII Art Server')
    parser.add_argument('-u', '--ui', action='store_true', 
                       help='Show monitoring GUI window')
    args = parser.parse_args()
    
    # Check if GUI is available when requested
    if args.ui and not GUI_AVAILABLE:
        print("Error: GUI requested but tkinter is not available.")
        print("Install tkinter: sudo apt-get install python3-tk (on Debian/Ubuntu)")
        print("Or run without -u flag for console mode.")
        sys.exit(1)
    
    # Check if psutil is available
    try:
        import psutil
    except ImportError:
        print("Error: psutil is required for monitoring features.")
        print("Install with: pip install psutil")
        if args.ui:
            sys.exit(1)
        else:
            print("Continuing without monitoring features...")
    
    port = 6767
    server_address = ('localhost', port)
    
    # Create web directory if needed
    create_web_directory()
    
    # Check if asciiArt executable exists
    if not os.path.exists('./asciiArt'):
        print("Warning: './asciiArt' executable not found. ASCII conversion will fail.")
        print("Make sure to build or download the asciiArt tool.")
    
    # Initialize a temporary post manager to calculate cache size
    temp_post_manager = E621PostManager()
    cache_size_bytes = temp_post_manager.get_cache_size()
    temp_post_manager.shutdown()  # Shut down the temporary instance
    
    cache_size_mb = cache_size_bytes / 1000000
    print(f"You're using {cache_size_mb:.2f} MB of space in cache.")
    
    print("\033[38;2;255;117;162m            ░██████   ░██████  ░███████   \033[0m")
    print("\033[38;2;255;117;162m           ░██   ░██ ░██   ░██ ░██   ░██  \033[0m")
    print("\033[38;2;255;255;255m ░███████        ░██ ░██       ░██    ░██ \033[0m")
    print("\033[38;2;190;87;180m░██    ░██   ░█████  ░███████  ░██    ░██ \033[0m")
    print("\033[38;2;64;64;64m░█████████  ░██      ░██   ░██ ░██    ░██ \033[0m")
    print("\033[38;2;47;139;167m░██        ░██       ░██   ░██ ░██   ░██  \033[0m")
    print("\033[38;2;47;139;167m ░███████  ░████████  ░██████  ░███████   \033[0m")
    print("e26D 25w35a - The web-terminal based e621 client.")
    print(f"Starting e26D on http://localhost:{port}")
    print("Please report bugs to github.com/pugsby/e26D")
    print("Look at README.md for a tutorial")
    
    if args.ui:
        print("GUI monitoring enabled - opening monitor window...")
    else:
        print("Press Ctrl+C to stop the server")
    
    # Create the server
    server = ThreadedHTTPServer(server_address, E621ASCIIHandler)
    
    try:
        if args.ui:
            # Run with GUI
            run_server_with_gui(server, E621ASCIIHandler.post_manager or E621PostManager())
        else:
            # Run normally
            server.start_server()
    except KeyboardInterrupt:
        print("\nReceived shutdown signal...")
    finally:
        # Ensure proper cleanup
        server.shutdown()


if __name__ == "__main__":
    main()