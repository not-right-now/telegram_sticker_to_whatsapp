"""
Video to WebP Converter Module supports many video formats like WEBM, MP4, GIF, MOV, MKV, etc.

A simple Python module for converting various video formats (WebM, MP4, etc.) to animated WebP while compressing it to a maximum size cap (Default is 500).
It will basically allow output files between [400,500]KB if SIZE_CAP_KB is 500KB (Default).
Features smart timing preservation and performance optimization.
"""

import os
import cv2
import tempfile
from PIL import Image, ImageDraw
import argparse
import sys
import io
import time
import webp

class VideoToWebPConverter:
    """Converter class for Video to animated WebP conversion with automatic timing preservation."""
    
    def __init__(self, width: int = -1, height: int = -1, quality: int = 80):
        """
        Initialize the converter.
        
        Args:
            width: Output width in pixels (-1 for original)
            height: Output height in pixels (-1 for original)
            quality: WebP quality (0-100)
        """
        self.width = width
        self.height = height
        self.quality = quality

    def _create_webp_buffer(self, frames, quality, fps):
        if not frames:
            return None

        # write to a temp file
        with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as tmp:
            webp.save_images(frames, tmp.name, fps=fps, quality=quality)
            tmp.flush()

            # read that file into BytesIO
            buf = io.BytesIO(tmp.read())
        return buf

    
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
        return frames, original_duration
    
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
        start_time = time.monotonic()
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # --- Stage 1: Extract ALL Frames From Video ---
        try:
            print("Pre-rendering all original frames... this might take a moment.")
            all_frames, original_duration = self._extract_all_frames_from_video(video_path)
        except Exception as e:
            raise ValueError(f"Failed to extract frames from video: {e}")

        if not all_frames:
            raise ValueError("Could not render any frames from the video file.")

        original_total_frames = len(all_frames)

        # --- Stage 2: The Optimization Gauntlet! ---
        SIZE_CAP_KB = 490
        SIZE_TARGET_RANGE = ((SIZE_CAP_KB -100) * 1024, SIZE_CAP_KB * 1024)
        MAX_FRAMES_CAP = 30
        FRAME_PIVOT = MAX_FRAMES_CAP // 2

        final_frames = None
        final_quality = self.quality

        successful_buffer = None
        
        def select_frames(source_frames, count):
            if count <= 0: return []
            if count >= len(source_frames): return source_frames
            indices = [int(i * (len(source_frames) - 1) / (count - 1)) for i in range(count)]
            return [source_frames[i] for i in indices]

        def eval_frames(num_frames):
            # To allow modification of the cache
            nonlocal successful_buffer
            frames_to_test = select_frames(all_frames, num_frames)
            if not frames_to_test: return float('inf')
            fps = len(frames_to_test) / original_duration
            
            # store the result
            buffer = self._create_webp_buffer(frames_to_test, final_quality, fps)
            
            if buffer:
                successful_buffer = buffer
                return buffer.getbuffer().nbytes
            return float('inf')


        def eval_quality(quality):
            # To allow modification of the buffer
            nonlocal successful_buffer
            if not final_frames: return float('inf')
            fps = len(final_frames) / original_duration

            # store the result
            buffer = self._create_webp_buffer(final_frames, quality, fps)

            if buffer:
                successful_buffer = buffer
                return buffer.getbuffer().nbytes
            return float('inf')

        initial_frame_count = min(original_total_frames, MAX_FRAMES_CAP)
        final_frames = select_frames(all_frames, initial_frame_count)

        print(f"[*] Stage A: Testing with {len(final_frames)} frames @ Q={final_quality}...")
        buffer = self._create_webp_buffer(final_frames, final_quality, len(final_frames) / original_duration)
        current_size = buffer.getbuffer().nbytes if buffer else float('inf')

        if current_size <= SIZE_TARGET_RANGE[1]:
            successful_buffer = buffer
            print(f"☑️ Success! Size is {current_size / 1024:.1f}KB. No further optimization needed.")
        else:
            print(f"->👎 Too big ({current_size / 1024:.1f}KB). Starting advanced optimization...")
            
            # --- Define search ranges ---
            if original_total_frames > MAX_FRAMES_CAP:
                frame_range_1 = (FRAME_PIVOT, MAX_FRAMES_CAP)
                frame_range_2 = (1, FRAME_PIVOT)
                fallback_frame_count = FRAME_PIVOT
            else:
                frame_range_1 = (original_total_frames // 2, original_total_frames)
                frame_range_2 = (1, original_total_frames // 2)
                fallback_frame_count = original_total_frames // 2

            quality_range_1 = (int(self.quality / 2), self.quality)
            quality_range_2 = (1, int(self.quality / 2))

            # --- Start the search ---

            # Stage B: Search frame count
            print(f"[*] Stage B: Searching frame count in [{int(frame_range_1[0])}, {int(frame_range_1[1])}] @ Q=80...")
            best_f, best_s = self._binary_search(SIZE_TARGET_RANGE, frame_range_1, eval_frames)

            if best_f:
                print(f"-> ☑️ Found solution in Stage B: {best_f} frames, size {best_s / 1024:.1f}KB.")
            else:
                # Stage C: Search quality
                print(f"[*] Stage C: Too big. Fixing at {fallback_frame_count} frames. Searching quality in [{quality_range_1[0]}, {quality_range_1[1]}]...")
                final_frames = select_frames(all_frames, fallback_frame_count)
                best_q, best_s = self._binary_search(SIZE_TARGET_RANGE, quality_range_1, eval_quality)

                if best_q:
                    print(f"-> ☑️ Found solution in Stage C: Q={best_q}, size {best_s / 1024:.1f}KB.")
                else:
                    # Stage D: Search frame count again
                    print(f"[*] Stage D: Still too big. Fixing quality at 40. Searching frames in [{int(frame_range_2[0])}, {int(frame_range_2[1])}]...")
                    final_quality = 40
                    best_f, best_s = self._binary_search(SIZE_TARGET_RANGE, frame_range_2, eval_frames)

                    if best_f:
                        print(f"-> ☑️ Found solution in Stage D: {best_f} frames, size {best_s / 1024:.1f}KB.")
                    else:
                        # Stage E: Last resort
                        print("[*] Stage E: Last resort! Fixing at 1 frame. Searching quality in [{quality_range_2[0]}, {quality_range_2[1]}]...")
                        final_frames = select_frames(all_frames, 1)
                        best_q, best_s = self._binary_search(SIZE_TARGET_RANGE, quality_range_2, eval_quality)
                        
                        final_quality = best_q if best_q else 1
                        successful_buffer = self._create_webp_buffer(final_frames, final_quality, 1/original_duration)
                        current_size = successful_buffer.getbuffer().nbytes if successful_buffer else float('inf')
                        print(f"->⚠️ Extreme compression: 1 frame, Q={final_quality}, size {current_size / 1024:.1f}KB.")

        # --- Stage 3: Final Save ---
        try:
            if successful_buffer:
                print(f"\nSaving final WebP to '{webp_path}'...")
                with open(webp_path, 'wb') as f:
                    f.write(successful_buffer.getvalue())
                return True
            else:
                # If the buffer is STILL empty after all stages, the conversion failed.
                raise ValueError("Could not produce a WebP file under the size limit after all optimizations.")

        except Exception as e:
            raise IOError(f"Final WebP saving failed: {e}")
        
        finally:
            end_time = time.monotonic()
            duration = end_time - start_time
            print(f"⌛ Total time taken: {duration:.2f} seconds.")


def convert_video_to_webp(video_path: str, webp_path: str, 
                        width: int = -1, height: int = -1, 
                        quality: int = 80) -> bool:
    """
    Simple function to convert a video file to animated WebP with automatic timing preservation.
    
    Args:
        video_path: Path to input video file
        webp_path: Path to output WebP file
        width: Output width in pixels (default: Original)
        height: Output height in pixels (default: Original)
        quality: WebP quality 0-100 (default: 80)
        
    Returns:
        True if conversion successful, False otherwise
        
    """
    converter = VideoToWebPConverter(width, height, quality)
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

    args = parser.parse_args()

    # Call the main function with the parsed arguments
    success = convert_video_to_webp(
        video_path=args.input_file,
        webp_path=args.output_file,
        width=args.width,
        height=args.height,
        quality=args.quality,
    )

    if success:
        print(f"✅ Successfully converted {args.input_file} to {args.output_file}")
    else:
        print(f"❌ Failed to convert {args.input_file}")
        sys.exit(1)
