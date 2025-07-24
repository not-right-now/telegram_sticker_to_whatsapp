"""
TGS to WebP Converter Module

A simple Python module for converting TGS (Telegram animated stickers) to WebP format.
TGS files are gzip-compressed Lottie JSON animations.
"""

import os
import tempfile
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
        Convert TGS file to animated WebP.
        
        Args:
            tgs_path: Path to input TGS file
            webp_path: Path to output WebP file
            
        Returns:
            True if conversion successful, False otherwise
            
        Raises:
            FileNotFoundError: If TGS file doesn't exist
            ValueError: If TGS file is invalid
            IOError: If output file cannot be written
        """
        if not os.path.exists(tgs_path):
            raise FileNotFoundError(f"TGS file not found: {tgs_path}")
        
        try:
            # Parse TGS file using lottie library
            with open(tgs_path, 'rb') as f:
                lottie_animation = parse_tgs(f)
            
            # Get animation properties
            original_total_frames = int(lottie_animation.out_point - lottie_animation.in_point) if lottie_animation else 30
            original_fps = lottie_animation.frame_rate if lottie_animation else 30.0
            
            if self.preserve_timing:
                # Calculate original duration in seconds
                original_duration = original_total_frames / original_fps
                
                # Determine optimal output settings to preserve timing
                max_frames = 60  # Performance limit
                
                if original_total_frames <= max_frames:
                    # For short animations, keep all frames and adjust FPS to maintain duration
                    total_frames = original_total_frames
                    output_fps = total_frames / original_duration
                    print(f"Preserving all {total_frames} frames, adjusting FPS to {output_fps:.1f} to maintain {original_duration:.2f}s duration")
                else:
                    # For long animations, limit frames but maintain duration
                    total_frames = max_frames
                    output_fps = total_frames / original_duration
                    print(f"Limiting to a total of {max_frames} frames, adjusting FPS to {output_fps:.1f} to maintain {original_duration:.2f}s duration")
                
                # Store the calculated FPS for frame duration calculation
                self._calculated_fps = output_fps
            else:
                # Use original logic with user-specified FPS
                total_frames = int(lottie_animation.out_point - lottie_animation.in_point) if lottie_animation else 30
                max_frames = 60
                if total_frames > max_frames:
                    total_frames = max_frames
                    print(f"Limiting animation to a total of {max_frames} frames for performance")
                self._calculated_fps = self.fps
            
            # Render all frames
            frames = []
            for i in range(total_frames):
                # Map our frame index to the original animation frame range
                original_frame = int(i * original_total_frames / total_frames)
                frame = self._render_lottie_frame(lottie_animation, original_frame, total_frames)
                frames.append(frame)
            
            if not frames:
                raise ValueError("No frames could be rendered from TGS file")
            
            # Calculate frame duration in milliseconds using the calculated FPS
            frame_duration = int(1000 / self._calculated_fps)
            
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