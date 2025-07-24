"""
TGS to WebP Converter Module

A simple Python module for converting TGS (Telegram animated stickers) to WebP format.
TGS files are gzip-compressed Lottie JSON animations.
"""

import os 
import tempfile
import io
from PIL import Image, ImageDraw
from lottie import objects
from lottie.exporters.cairo import export_png
from lottie.parsers.tgs import parse_tgs


class TGSToWebPConverter:
    """Converter class for TGS to WebP conversion with automatic timing preservation."""
    
    def __init__(self, width: int = -1, height: int = -1, fps: int = 30, quality: int = 80, preserve_timing: bool = True):
        """
        Initialize the converter.
        
        Args:
            width: Output width in pixels
            height: Output height in pixels
            fps: Target frames per second (ignored if preserve_timing=True)
            quality: WebP quality (0-100)
            preserve_timing: If True, automatically adjusts FPS to preserve original animation timing
        """
        self.width = width
        self.height = height
        self.fps = fps
        self.quality = quality
        self.preserve_timing = preserve_timing
    
    def _save_webp_to_buffer(self, frames: list, quality: int, fps: float) -> int:
        """Saves a list of frames to an in-memory WebP buffer and returns the size in bytes."""
        if not frames:
            return float('inf')  # Return infinity if no frames to avoid errors

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

        Args:
            target_range: A (min, max) tuple for the desired outcome (file size).
            search_space: A (min, max) tuple for the values to search (e.g., frame count or quality).
            evaluator_func: A function that takes a value from search_space and returns an outcome.

        Returns:
            A tuple of (best_value, best_size). Returns (None, None) if no suitable value is found.
        """
        low, high = search_space
        best_value = None
        best_size = float('inf')

        # To handle integer ranges correctly
        low, high = int(low), int(high)
        if low > high:
            return None, None

        while low <= high:
            mid = (low + high) // 2
            if mid == 0: # Avoid getting stuck at 0
                mid = 1

            current_size = evaluator_func(mid)

            if target_range[0] <= current_size <= target_range[1]:
                # Perfect match! We are within our target size bracket.
                return mid, current_size
            elif current_size < target_range[0]:
                # The file is too small, try for better quality/more frames.
                best_value = mid # This is a valid, but small, option
                best_size = current_size
                low = mid + 1
            else:
                # The file is too big, we must reduce quality/frames.
                high = mid - 1
        
        # If we never hit the target range exactly, return the best value found that was *under* the max
        # This is useful if the target range [400, 500] is missed, but we found a solution that is, say, 390KB.
        if best_value is not None and best_size <= target_range[1]:
             return best_value, best_size
             
        return None, None
    
    def _render_lottie_frame(self, lottie_animation, frame_num: int, total_frames: int) -> Image.Image:
        """
        Render a single frame from Lottie animation using the lottie library.
        
        Args:
            lottie_animation: Lottie animation object
            frame_num: Current frame number
            total_frames: Total number of frames
            
        Returns:
            PIL Image of the rendered frame
        """
        try: 
            # Create a temporary file for the frame
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Calculate the frame time based on the animation
            frame_time = frame_num / self.fps
            
            # Export single frame as PNG using Cairo
            export_png(
                lottie_animation,
                temp_path,
                frame=frame_num
            )
            
            # Load the generated PNG
            if os.path.exists(temp_path):
                img = Image.open(temp_path).convert('RGBA')
                # Check for cusrrom width and hight and resize if any
                if self.width != -1 and self.height != -1:
                    img = img.resize((self.width, self.height), Image.LANCZOS)
                os.unlink(temp_path)  # Clean up temp file
                return img
            else:
                raise Exception("Frame export failed")
                
        except Exception as e:
            print(f"Warning: Lottie frame rendering failed, using fallback: {e}")
            return self._create_fallback_frame(lottie_animation, frame_num, total_frames)
    
    def _create_fallback_frame(self, lottie_animation, frame_num: int, total_frames: int) -> Image.Image:
        """Create a simple fallback frame when Lottie rendering fails."""
        # Create a simple animated frame with PIL
        fallback_width = self.width if self.width != -1 else lottie_animation.width
        fallback_height = self.height if self.height != -1 else lottie_animation.height
        img = Image.new('RGBA', (fallback_width, fallback_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Calculate animation progress
        progress = frame_num / max(total_frames - 1, 1)
        
        # Create a simple animated element
        center_x = int(fallback_width * (0.2 + 0.6 * progress))
        center_y = int(fallback_height * 0.5)
        radius = int(30 + 20 * abs(0.5 - progress) * 2)
        
        # Draw a circle
        color = (51, 153, 255, 200)  # Blue with transparency
        draw.ellipse([center_x - radius, center_y - radius, 
                     center_x + radius, center_y + radius], fill=color)
        
        return img
    

    
    def convert(self, tgs_path: str, webp_path: str) -> bool:
        """
        Convert TGS file to animated WebP with a size cap of ~500KB.
        """
        if not os.path.exists(tgs_path):
            raise FileNotFoundError(f"TGS file not found: {tgs_path}")

        # --- Stage 1: Parse and Render ALL Original Frames ---
        try:
            with open(tgs_path, 'rb') as f:
                lottie_animation = parse_tgs(f)
        except Exception as e:
            raise ValueError(f"TGS file is invalid or could not be parsed: {e}")

        original_total_frames = int(lottie_animation.out_point - lottie_animation.in_point)
        original_fps = lottie_animation.frame_rate
        original_duration = original_total_frames / original_fps
        
        print("Pre-rendering all original frames... this might take a moment.")
        all_frames = [self._render_lottie_frame(lottie_animation, i, original_total_frames) for i in range(original_total_frames)]
        
        if not all_frames:
            raise ValueError("Could not render any frames from the TGS file.")

        # --- Stage 2: The Optimization Gauntlet! ---
        SIZE_CAP_KB = 450
        SIZE_TARGET_RANGE = (400 * 1024, SIZE_CAP_KB * 1024)  # Target [400KB, 500KB]
        MAX_FRAMES_CAP = 60
        FRAME_PIVOT = MAX_FRAMES_CAP // 2

        final_frames = None
        final_quality = self.quality # Start with default quality
        
        # Helper to select a subset of frames evenly
        def select_frames(source_frames, count):
            if count >= len(source_frames):
                return source_frames
            indices = [int(i * (len(source_frames) - 1) / (count - 1)) for i in range(count)]
            return [source_frames[i] for i in indices]

        # Define evaluators for binary search
        def eval_frames(num_frames):
            frames_to_test = select_frames(all_frames, num_frames)
            fps = len(frames_to_test) / original_duration
            return self._save_webp_to_buffer(frames_to_test, final_quality, fps)

        def eval_quality(quality):
            fps = len(final_frames) / original_duration
            return self._save_webp_to_buffer(final_frames, quality, fps)
            
        # Determine initial frame count based on caps
        initial_frame_count = min(original_total_frames, MAX_FRAMES_CAP)
        final_frames = select_frames(all_frames, initial_frame_count)

        # --- Run the multi-stage search logic ---
        print(f"Aiming for a file size under {SIZE_CAP_KB}KB.")

        # Stage A: Try with max frames at default quality
        print(f"[*] Stage A: Testing with {len(final_frames)} frames @ Q={final_quality}...")
        current_size = self._save_webp_to_buffer(final_frames, final_quality, len(final_frames) / original_duration)
        
        if current_size <= SIZE_TARGET_RANGE[1]:
            print(f"☑️ Success! Size is {current_size / 1024:.1f}KB. No further optimization needed.")
        else:
            print(f"-> Too big ({current_size / 1024:.1f}KB). Starting advanced optimization...")
            # --- Your algorithm begins! ---
            
            # Decide search ranges based on original frame count
            if original_total_frames > MAX_FRAMES_CAP:
                frame_range_1 = (FRAME_PIVOT, MAX_FRAMES_CAP)
                frame_range_2 = (1, FRAME_PIVOT)
                quality_range_1 = (40, 80)
                quality_range_2 = (1, 40)
                fallback_frame_count = FRAME_PIVOT
            else:
                frame_range_1 = (original_total_frames / 2, original_total_frames)
                frame_range_2 = (1, original_total_frames / 2)
                quality_range_1 = (40, 80)
                quality_range_2 = (1, 40)
                fallback_frame_count = int(original_total_frames / 2)

            # Stage B: Binary search on frame count [X, Y] @ Q=80
            print(f"[*] Stage B: Searching frame count in [{int(frame_range_1[0])}, {int(frame_range_1[1])}] @ Q=80...")
            best_f, best_s = self._binary_search(SIZE_TARGET_RANGE, frame_range_1, eval_frames)

            if best_f:
                final_frames = select_frames(all_frames, best_f)
                current_size = best_s
                print(f"-> ☑️ Found solution: {len(final_frames)} frames, size {current_size / 1024:.1f}KB.")
            else:
                # Stage C: Binary search on quality [40, 80] @ Z frames
                print(f"[*] Stage C: Too big. Fixing at {fallback_frame_count} frames. Searching quality in [{quality_range_1[0]}, {quality_range_1[1]}]...")
                final_frames = select_frames(all_frames, fallback_frame_count)
                best_q, best_s = self._binary_search(SIZE_TARGET_RANGE, quality_range_1, eval_quality)

                if best_q:
                    final_quality = best_q
                    current_size = best_s
                    print(f"-> ☑️ Found solution: Q={final_quality}, size {current_size / 1024:.1f}KB.")
                else:
                    # Stage D: Binary search on frame count [1, Z] @ Q=40
                    print(f"[*] Stage D: Still too big. Fixing quality at 40. Searching frames in [{int(frame_range_2[0])}, {int(frame_range_2[1])}]...")
                    final_quality = 40
                    best_f, best_s = self._binary_search(SIZE_TARGET_RANGE, frame_range_2, eval_frames)
                    
                    if best_f:
                        final_frames = select_frames(all_frames, best_f)
                        current_size = best_s
                        print(f"-> ☑️ Found solution: {len(final_frames)} frames, size {current_size / 1024:.1f}KB.")
                    else:
                        # Stage E: Binary search on quality [1, 40] @ 1 frame
                        print("[*] Stage E: Last resort! Fixing at 1 frame. Searching quality in [1, 40]...")
                        final_frames = select_frames(all_frames, 1)
                        final_quality = 40 # Start at 40
                        best_q, best_s = self._binary_search(SIZE_TARGET_RANGE, quality_range_2, eval_quality)
                        
                        if best_q:
                            final_quality = best_q
                        else:
                            # If all else fails, just take the smallest possible quality
                             final_quality = 1
                        
                        current_size = self._save_webp_to_buffer(final_frames, final_quality, 1/original_duration)
                        print(f"->⚠️ Extreme compression: 1 frame, Q={final_quality}, size {current_size / 1024:.1f}KB.")


        # --- Stage 3: Final Save ---
        try:
            final_fps = len(final_frames) / original_duration
            frame_duration = int(1000 / final_fps)
            
            print(f"\nSaving final WebP to '{webp_path}' with {len(final_frames)} frames, Q={final_quality}, {final_fps:.1f} FPS.")
            
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


def convert_tgs_to_webp(tgs_path: str, webp_path: str, 
                       width: int = -1, height: int = -1, 
                       fps: int = 30, quality: int = 80, preserve_timing: bool = True) -> bool:
    """
    Simple function to convert TGS to WebP with automatic timing preservation.
    
    Args:
        tgs_path: Path to input TGS file
        webp_path: Path to output WebP file
        width: Output width in pixels (default: Original)
        height: Output height in pixels (default: Original)
        fps: Target frames per second (ignored if preserve_timing=True, default: 30)
        quality: WebP quality 0-100 (default: 80)
        preserve_timing: Automatically preserve original animation timing (default: True)
        
    Returns:
        True if conversion successful, False otherwise
        
    Example:
        >>> from tgs_to_webp import convert_tgs_to_webp
        >>> # Automatic timing preservation (recommended)
        >>> success = convert_tgs_to_webp('sticker.tgs', 'sticker.webp')
        >>> # Manual FPS control
        >>> success = convert_tgs_to_webp('sticker.tgs', 'sticker.webp', fps=20, preserve_timing=False)
    """
    converter = TGSToWebPConverter(width, height, fps, quality, preserve_timing)
    try:
        return converter.convert(tgs_path, webp_path)
    except Exception as e:
        print(f"Error during conversion: {e}")
        return False


if __name__ == "__main__":
    # Example usage
    import sys, argparse
    
    
    parser = argparse.ArgumentParser(
        description="Convert TGS (Telegram animated stickers) to animated WebP.",
        # This helps in formatting the help text nicely
        formatter_class=argparse.RawTextHelpFormatter
    )

    # Required positional arguments
    parser.add_argument("input_file", help="Path to the input TGS file.")
    parser.add_argument("output_file", help="Path for the output WebP file.")

    # Optional arguments with default values from your function
    parser.add_argument("--width", type=int, default=-1, help="Output width in pixels. Default: Original.")
    parser.add_argument("--height", type=int, default=-1, help="Output height in pixels. Default: Original.")
    parser.add_argument("--quality", type=int, default=80, help="WebP quality (0-100). Default: 80.")
    parser.add_argument("--fps", type=int, default=30,
                        help="Frames per second. \n(Note: This is ignored by default unless you disable timing preservation).")

    # This is a cool way to handle a boolean flag
    parser.add_argument("--no-preserve-timing", action="store_false", dest="preserve_timing",
                        help="Disable automatic timing preservation to use the manual FPS value.")

    # Let argparse handle the arguments
    args = parser.parse_args()

    # Call the main function with the parsed arguments
    success = convert_tgs_to_webp(
        tgs_path=args.input_file,
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