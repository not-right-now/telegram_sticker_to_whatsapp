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
import io


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

    def _save_webp_to_buffer(self, frames: list, quality: int, fps: float) -> int:
        """Saves a list of frames to an in-memory WebP buffer and returns the size in bytes."""
        if not frames:
            return float('inf')

        frame_duration = int(1000 / fps)
        buffer = io.BytesIO()

        frames[0].save(
            buffer,
            format='WebP',
            save_all=True,
            append_images=frames[1:],
            duration=frame_duration,
            loop=0,
            quality=quality,
            method=6
        )
        return buffer.getbuffer().nbytes
    
    @staticmethod
    def _binary_search(target_range: tuple, search_space: tuple, evaluator_func) -> tuple[int, int]:
        """
        Performs a binary search to find a value in search_space that results
        in an outcome within target_range.
        """
        low, high = search_space
        best_value = None
        best_size = float('inf')

        low, high = int(low), int(high)
        if low > high:
            return None, None

        while low <= high:
            mid = (low + high) // 2
            if mid == 0:
                mid = 1

            current_size = evaluator_func(mid)

            if target_range[0] <= current_size <= target_range[1]:
                return mid, current_size
            elif current_size < target_range[0]:
                best_value = mid
                best_size = current_size
                low = mid + 1
            else:
                high = mid - 1

        if best_value is not None and best_size <= target_range[1]:
            return best_value, best_size

        return None, None

    def _extract_all_frames_from_video(self, video_path: str):
        """
        Extracts all frames from a video file using OpenCV and returns them as PIL Images.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")

        # Get video properties
        original_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        original_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        original_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if original_fps <= 0: original_fps = 30.0 # Default fallback
        if total_frames <= 0: raise ValueError("Video file appears to have no frames.")

        original_duration = total_frames / original_fps
        frames = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Convert BGR (OpenCV) to RGB (PIL)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(frame_rgb)

            # Handle resizing
            if self.width != -1 and self.height != -1:
                pil_image = pil_image.resize((self.width, self.height), Image.LANCZOS)

            frames.append(pil_image)

        cap.release()
        return frames, original_fps, original_duration
    
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
        Convert Video file to animated WebP with a size cap of ~500KB.
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # --- Stage 1: Extract ALL Frames From Video ---
        try:
            all_frames, original_fps, original_duration = self._extract_all_frames_from_video(video_path)
        except Exception as e:
            raise ValueError(f"Failed to extract frames from video: {e}")

        if not all_frames:
            raise ValueError("Could not render any frames from the video file.")

        original_total_frames = len(all_frames)

        # --- Stage 2: The Optimization Gauntlet! ---
        SIZE_CAP_KB = 450
        SIZE_TARGET_RANGE = (400 * 1024, SIZE_CAP_KB * 1024)
        MAX_FRAMES_CAP = 60
        FRAME_PIVOT = MAX_FRAMES_CAP // 2

        final_frames = None
        final_quality = self.quality

        def select_frames(source_frames, count):
            if count <= 0: return []
            if count >= len(source_frames): return source_frames
            indices = [int(i * (len(source_frames) - 1) / (count - 1)) for i in range(count)]
            return [source_frames[i] for i in indices]

        def eval_frames(num_frames):
            frames_to_test = select_frames(all_frames, num_frames)
            if not frames_to_test: return float('inf')
            fps = len(frames_to_test) / original_duration
            return self._save_webp_to_buffer(frames_to_test, final_quality, fps)

        def eval_quality(quality):
            if not final_frames: return float('inf')
            fps = len(final_frames) / original_duration
            return self._save_webp_to_buffer(final_frames, quality, fps)

        initial_frame_count = min(original_total_frames, MAX_FRAMES_CAP)
        final_frames = select_frames(all_frames, initial_frame_count)

        print(f"Aiming for a file size under {SIZE_CAP_KB}KB.")
        print(f"[*] Stage A: Testing with {len(final_frames)} frames @ Q={final_quality}...")
        current_size = self._save_webp_to_buffer(final_frames, final_quality, len(final_frames) / original_duration)

        if current_size <= SIZE_TARGET_RANGE[1]:
            print(f"☑️ Success! Size is {current_size / 1024:.1f}KB. No further optimization needed.")
        else:
            print(f"->👎 Too big ({current_size / 1024:.1f}KB). Starting advanced optimization...")

            if original_total_frames > MAX_FRAMES_CAP:
                frame_range_1 = (FRAME_PIVOT, MAX_FRAMES_CAP)
                frame_range_2 = (1, FRAME_PIVOT)
                fallback_frame_count = FRAME_PIVOT
            else:
                frame_range_1 = (original_total_frames // 2, original_total_frames)
                frame_range_2 = (1, original_total_frames // 2)
                fallback_frame_count = original_total_frames // 2

            quality_range_1 = (40, 80)
            quality_range_2 = (1, 40)

            print(f"[*] Stage B: Searching frame count in [{int(frame_range_1[0])}, {int(frame_range_1[1])}] @ Q=80...")
            best_f, best_s = self._binary_search(SIZE_TARGET_RANGE, frame_range_1, eval_frames)

            if best_f:
                final_frames = select_frames(all_frames, best_f)
                current_size = best_s
                print(f"-> ☑️ Found solution: {len(final_frames)} frames, size {current_size / 1024:.1f}KB.")
            else:
                print(f"[*] Stage C: Too big. Fixing at {fallback_frame_count} frames. Searching quality in [{quality_range_1[0]}, {quality_range_1[1]}]...")
                final_frames = select_frames(all_frames, fallback_frame_count)
                best_q, best_s = self._binary_search(SIZE_TARGET_RANGE, quality_range_1, eval_quality)

                if best_q:
                    final_quality = best_q
                    current_size = best_s
                    print(f"-> ☑️ Found solution: Q={final_quality}, size {current_size / 1024:.1f}KB.")
                else:
                    print(f"[*] Stage D: Still too big. Fixing quality at 40. Searching frames in [{int(frame_range_2[0])}, {int(frame_range_2[1])}]...")
                    final_quality = 40
                    best_f, best_s = self._binary_search(SIZE_TARGET_RANGE, frame_range_2, eval_frames)

                    if best_f:
                        final_frames = select_frames(all_frames, best_f)
                        current_size = best_s
                        print(f"-> ☑️ Found solution: {len(final_frames)} frames, size {current_size / 1024:.1f}KB.")
                    else:
                        print("[*] Stage E: Last resort! Fixing at 1 frame. Searching quality in [1, 40]...")
                        final_frames = select_frames(all_frames, 1)
                        final_quality = 40
                        best_q, best_s = self._binary_search(SIZE_TARGET_RANGE, quality_range_2, eval_quality)

                        if best_q:
                            final_quality = best_q
                        else:
                            final_quality = 1

                        current_size = self._save_webp_to_buffer(final_frames, final_quality, 1/original_duration)
                        print(f"->⚠️ Extreme compression: 1 frame, Q={final_quality}, size {current_size / 1024:.1f}KB.")

        # --- Stage 3: Final Save ---
        try:
            if not final_frames:
                raise IOError("Optimization failed to produce any frames.")

            final_fps = len(final_frames) / original_duration
            frame_duration = int(1000 / final_fps)

            print(f"\nSaving final WebP to '{webp_path}' with {len(final_frames)} frames, Q={final_quality}, {final_fps:.1f} FPS.")

            output_dir = os.path.dirname(webp_path)
            if output_dir: os.makedirs(output_dir, exist_ok=True)

            final_frames[0].save(
                webp_path,
                format='WebP',
                save_all=True,
                append_images=final_frames[1:],
                duration=frame_duration,
                loop=0,
                quality=final_quality,
                method=6
            )
            return True
        except Exception as e:
            raise IOError(f"Final WebP saving failed: {e}")


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
