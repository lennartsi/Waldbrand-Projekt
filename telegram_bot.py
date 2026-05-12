import os
from datetime import datetime
import logging
import json
import asyncio
from telegram import Bot
from detection_cutoff import detection_logic
from VAPIXcamera import VAPIXCamera
logger = logging.getLogger()

subscribers = [5894386665, 1361078892, 8655257428]
BOT_TOKEN = os.getenv('BOT_TOKEN')

class TelegramBot:
    def __init__(self, bot_token: str = BOT_TOKEN, subscribers: list[int] = subscribers):
        """
        Initialize the TelegramBot with a bot token and subscribers file.

        Args:
            bot_token (str): The Telegram bot token
            subscribers_file (str): Path to the JSON file containing subscriber chat IDs
        """
        self.bot_token = bot_token
        self.subscribers = subscribers
        self.bot = Bot(token=self.bot_token)

    async def broadcast(self, caption: str, image_path: str = ""):
        """
        Sends a photo with a caption or text-only message to all subscribers asynchronously.

        Args:
            caption (str): The text message to send. If image_path is provided, this becomes the caption.
            image_path (str, optional): The local file path to the image you want to send. If None, sends text only.
        """

        if not self.subscribers:
            logger.warning("There are no subscribers to send a message to. Aborting.")
            return

        logger.info(f"Starting broadcast to {len(self.subscribers)} subscribers.")

        # Loop through all subscribers and send the message
        for chat_id in self.subscribers:
            try:
                if image_path != "":
                    # Send photo with caption
                    with open(image_path, 'rb') as image_file:
                        await self.bot.send_photo(chat_id=chat_id, photo=image_file, caption=caption)
                else:
                    # Send text-only message
                    await self.bot.send_message(chat_id=chat_id, text=caption)
                logger.info(f"Successfully sent message to {chat_id}")
            except FileNotFoundError:
                logger.error(f"Error: The image file was not found at '{image_path}'. Aborting broadcast.")
                return  # Stop the broadcast if the image doesn't exist
            except Exception as e:
                logger.error(f"Failed to send message to {chat_id}: {e}")

    def broadcast_sync(self, caption: str, image_path: str = ""):
        """
        Synchronous wrapper for the broadcast method.
        This allows non-async classes to send broadcasts.

        Args:
            caption (str): The text message to send. If image_path is provided, this becomes the caption.
            image_path (str, optional): The local file path to the image you want to send. If None, sends text only.
        """
        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, create a new event loop in a thread
                import threading
                import concurrent.futures

                def run_in_thread():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(self.broadcast(caption, image_path))
                    finally:
                        new_loop.close()

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_thread)
                    return future.result()
            else:
                # If no loop is running, we can use the current loop
                return loop.run_until_complete(self.broadcast(caption, image_path))
        except RuntimeError:
            # No event loop exists, create a new one
            return asyncio.run(self.broadcast(caption, image_path))
        
if __name__ == "__main__":
    # Example usage
    import os
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    if not BOT_TOKEN:
        raise RuntimeError("Missing BOT_TOKEN environment variable")
    SUBSCRIBERS = subscribers  # Replace with actual chat IDs

    bot = TelegramBot(bot_token=BOT_TOKEN, subscribers=SUBSCRIBERS)
    bot.broadcast_sync("Hello, this is a test message from the TelegramBot!")
    # ip = '192.44.18.67'
    # user='lennart'
    # password='7v1wuUGGsE3W2R3GpGbg'
    # cam = VAPIXCamera(ip, user, password,use_https=False)
    # pos = cam.get_ptz_status()
    # image = cam.get_current_image()
    # timestamp = datetime.now()
    # path = r"\\netappn1\siethoff\Fraunhofer Waldbrand"
    # image_path = cam.save_image_with_metadata(path, image, timestamp, pos, detected=False)  # Assuming this method returns the path to the current image
    # bot.broadcast_sync("Hello, this is a test message from the TelegramBot!", image_path=image_path)
