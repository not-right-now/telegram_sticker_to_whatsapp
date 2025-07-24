"""
Video to WebP Converter Module supports many video formats like WEBM, MP4, GIF, MOV, MKV, etc.

A simple Python module for converting various video formats (WebM, MP4, etc.) to animated WebP.
Features smart timing preservation and performance optimization.
"""

import os
import cv2
import tempfile
from PIL import Image, ImageDraw
import argparse
import sys


class VideoToWebPConverter:
    """Converter class for Video to animated WebP conversion with automatic timing preservation."""
    
    def __init__(self, width: int = -1, height: int = -1, fps: float = 30.0, quality: int = 80, preserve_timing: bool = True):
        """
        Initialize the converter.
        
        Args:
            width: Output width in pixels (-1 for original)
            height: Output height in pixels (-1 for original)
            fps: Target frames per second (ignored if preserve_timing=True)
            quality: WebP quality (0-100)
            preserve_timing: If True, automatically adjusts FPS to preserve original video timing
        """
        self.width = width
        self.height = height
        self.fps = fps
        self.quality = quality
        self.preserve_timing = preserve_timing
        self._calculated_fps = fps
    
    def _extract_video_frames(self, video_path: str):
        """
        Extract frames from video using OpenCV.
        
        Args:
            video_path: Path to the input video file
            
        Returns:
            Tuple of (frames_list, original_fps, total_frames, original_width, original_height)
        """
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")
        
        # Get video properties
        original_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        original_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        original_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        if original_fps <= 0:
            original_fps = 30.0  # Default fallback
            
        frames = []
        frame_count = 0
        
        if self.preserve_timing:
            # Calculate original duration in seconds
            original_duration = total_frames / original_fps
            
            # Determine optimal output settings to preserve timing
            max_frames = 30  # Performance limit
            
            if total_frames <= max_frames:
                # For short videos, keep all frames and adjust FPS to maintain duration
                target_frames = total_frames
                output_fps = target_frames / original_duration
                print(f"Preserving all {target_frames} frames, adjusting FPS to {output_fps:.1f} to maintain {original_duration:.2f}s duration")
            else:
                # For long videos, limit frames but maintain duration
                target_frames = max_frames
                output_fps = target_frames / original_duration
                print(f"Limiting to {max_frames} frames, adjusting FPS to {output_fps:.1f} to maintain {original_duration:.2f}s duration")
                
            self._calculated_fps = output_fps
            
            # Calculate frame step for sampling
            frame_step = total_frames / target_frames if target_frames > 0 else 1
        else:
            # Use manual frame limiting
            max_frames = 30
            target_frames = min(total_frames, max_frames)
            if total_frames > max_frames:
                print(f"Limiting video to {max_frames} frames for performance")
            self._calculated_fps = self.fps
            frame_step = total_frames / target_frames if target_frames > 0 else 1
        
        # Extract frames
        current_frame_pos = 0.0
        target_frame_count = 0
        
        while frame_count < total_frames and target_frame_count < target_frames:
            # Set frame position
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(current_frame_pos))
            
            ret, frame = cap.read()
            if not ret:
                break
                
            # Convert BGR to RGB (OpenCV uses BGR by default)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Convert to PIL Image
            pil_image = Image.fromarray(frame_rgb)
            
            # Resize if custom dimensions specified
            if self.width != -1 and self.height != -1:
                pil_image = pil_image.resize((self.width, self.height), Image.LANCZOS)
            elif self.width != -1 or self.height != -1:
                # Maintain aspect ratio if only one dimension specified
                aspect_ratio = original_width / original_height
                if self.width != -1:
                    new_height = int(self.width / aspect_ratio)
                    pil_image = pil_image.resize((self.width, new_height), Image.LANCZOS)
                else:
                    new_width = int(self.height * aspect_ratio)
                    pil_image = pil_image.resize((new_width, self.height), Image.LANCZOS)
            
            frames.append(pil_image)
            
            # Move to next frame position
            current_frame_pos += frame_step
            target_frame_count += 1
            frame_count += 1
        
        cap.release()
        
        if not frames:
            raise ValueError("No frames could be extracted from video file")
            
        return frames, original_fps, total_frames, original_width, original_height
    
    def _create_fallback_frame(self, width: int, height: int, frame_num: int, total_frames: int) -> Image.Image:
        """Create a simple fallback frame when video processing fails."""
        img = Image.new('RGB', (width, height), (128, 128, 128))
        draw = ImageDraw.Draw(img)
        
        # Calculate animation progress
        progress = frame_num / max(total_frames - 1, 1)
        
        # Create a simple animated element
        center_x = int(width * (0.2 + 0.6 * progress))
        center_y = int(height * 0.5)
        radius = int(min(width, height) * 0.1)
        
        # Draw a circle
        color = (255, 100, 100)  # Red
        draw.ellipse([center_x - radius, center_y - radius, 
                     center_x + radius, center_y + radius], fill=color)
        
        # Add text
        text = f"Frame {frame_num + 1}/{total_frames}"
        text_bbox = draw.textbbox((0, 0), text)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        text_x = (width - text_width) // 2
        text_y = center_y + radius + 20
        draw.text((text_x, text_y), text, fill=(255, 255, 255))
        
        return img
    
    def convert(self, video_path: str, webp_path: str) -> bool:
        """
        Convert video file to animated WebP.
        
        Args:
            video_path: Path to input video file
            webp_path: Path to output WebP file
            
        Returns:
            True if conversion successful, False otherwise
            
        Raises:
            FileNotFoundError: If the video file doesn't exist
            ValueError: If the video file is invalid
            IOError: If output file cannot be written
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        try:
            # Extract frames from video
            frames, original_fps, total_frames, original_width, original_height = self._extract_video_frames(video_path)
            
            if not frames:
                # Create fallback frames
                fallback_width = self.width if self.width != -1 else 400
                fallback_height = self.height if self.height != -1 else 300
                frames = [self._create_fallback_frame(fallback_width, fallback_height, i, 10) for i in range(10)]
                self._calculated_fps = 10.0
                print("Warning: Using fallback frames due to video processing failure")
            
            # Calculate frame duration in milliseconds
            frame_duration = int(1000 / self._calculated_fps)
            
            # Ensure output directory exists
            output_dir = os.path.dirname(webp_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            
            # Save as animated WebP
            frames[0].save(
                webp_path,
                format='WebP',
                save_all=True,
                append_images=frames[1:],
                duration=frame_duration,
                loop=0,  # Infinite loop
                quality=self.quality,
                method=6  # Best quality method
            )
            
            return True
            
        except Exception as e:
            raise IOError(f"Conversion failed: {e}")


def convert_video_to_webp(video_path: str, webp_path: str, 
                        width: int = -1, height: int = -1, 
                        fps: float = 30.0, quality: int = 80, preserve_timing: bool = True) -> bool:
    """
    Simple function to convert a video file to animated WebP with automatic timing preservation.
    
    Args:
        video_path: Path to input video file
        webp_path: Path to output WebP file
        width: Output width in pixels (default: Original)
        height: Output height in pixels (default: Original)
        fps: Target frames per second (ignored if preserve_timing=True, default: 30.0)
        quality: WebP quality 0-100 (default: 80)
        preserve_timing: Automatically preserve original video timing (default: True)
        
    Returns:
        True if conversion successful, False otherwise
        
    Example:
        >>> from video_to_webp import convert_video_to_webp
        >>> # Automatic timing preservation (recommended)
        >>> success = convert_video_to_webp('video.mp4', 'video.webp')
        >>> # Manual FPS control
        >>> success = convert_video_to_webp('video.mp4', 'video.webp', fps=20, preserve_timing=False)
    """
    converter = VideoToWebPConverter(width, height, fps, quality, preserve_timing)
    try:
        return converter.convert(video_path, webp_path)
    except Exception as e:
        print(f"Error during conversion: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert video files (WebM, MP4, etc.) to animated WebP.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    # Required positional arguments
    parser.add_argument("input_file", help="Path to the input video file.")
    parser.add_argument("output_file", help="Path for the output WebP file.")

    # Optional arguments
    parser.add_argument("--width", type=int, default=-1, help="Output width in pixels. Default: Original.")
    parser.add_argument("--height", type=int, default=-1, help="Output height in pixels. Default: Original.")
    parser.add_argument("--quality", type=int, default=80, help="WebP quality (0-100). Default: 80.")
    parser.add_argument("--fps", type=float, default=30.0,
                        help="Frames per second. \n(Note: This is ignored by default unless you disable timing preservation).")

    parser.add_argument("--no-preserve-timing", action="store_false", dest="preserve_timing",
                        help="Disable automatic timing preservation to use the manual FPS value.")

    args = parser.parse_args()

    # Call the main function with the parsed arguments
    success = convert_video_to_webp(
        video_path=args.input_file,
        webp_path=args.output_file,
        width=args.width,
        height=args.height,
        quality=args.quality,
        fps=args.fps,
        preserve_timing=args.preserve_timing
    )

    if success:
        print(f"✅ Successfully converted {args.input_file} to {args.output_file}")
    else:
        print(f"❌ Failed to convert {args.input_file}")
        sys.exit(1)
