import os
from datetime import datetime
from contextlib import ExitStack
import logging
import asyncio
from typing import Any, Optional, Sequence, Union
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from detection_cutoff import detection_logic
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler

logger = logging.getLogger()


async def handle_callback(update, context):
    query = update.callback_query
    await query.answer()

    action, alert_id = query.data.split(":", 1)
    alert_id = str(alert_id)

    bot_obj: TelegramBot = context.bot_data["bot_obj"]
    user_id = query.from_user.id

    votes = bot_obj.review_votes.get(alert_id)
    if votes is None:
        await query.answer(text="This review is no longer active", show_alert=True)
        return

    review_threshold = bot_obj.review_threshold

    if action not in ("fire", "nofire", "unclear"):
        await query.answer(text="Unknown action", show_alert=True)
        return

    if user_id in votes["voters"]:
        await query.answer(text="You already voted", show_alert=True)
        return

    if action == "unclear":
        context_data = bot_obj.alert_contexts.get(alert_id, {})
        video_path = context_data.get("video_path")
        await query.answer(text="You chose 'Unclear'. Please review the additional information sent to you and vote again.", show_alert=True)
        if video_path:
            await bot_obj.single_video(chat_id=user_id, caption=f"Additional video for alert {alert_id}", video_path=video_path)
        else:
            await bot_obj.single_broadcast(user_id, f"No video found yet for alert {alert_id}. Please vote again after reviewing the images.")
        
        return
    votes["voters"].add(user_id)
    votes[action] += 1

    fire_count = votes["fire"]
    nofire_count = votes["nofire"]
    unclear_count = votes["unclear"]

    logger.info(
        f"Alert {alert_id} vote by {user_id}: {action}; "
        f"counts fire={fire_count}, nofire={nofire_count}, unclear={unclear_count}"
    )

    if votes[action] < review_threshold:
        caption = f"You voted: {action}. {review_threshold - votes[action]} more votes needed to confirm {action.upper()}."
    else:
        caption = f"You voted: {action}. {action.upper()} confirmed with {votes[action]} votes!"
        if action == "fire":
            await bot_obj.broadcast(f"🔥 FIRE CONFIRMED (Decided by {review_threshold} votes) - Alert {alert_id}")
        elif action == "nofire":
            await bot_obj.broadcast(f"❌ False alarm (Decided by {review_threshold} votes) - Alert {alert_id}")

        bot_obj.review_votes.pop(alert_id, None)
        bot_obj.alert_contexts.pop(alert_id, None)
    try:
        await query.edit_message_text(text=caption)
    except Exception as exc:
        logger.error(f"Failed to update review message for alert {alert_id}: {exc}")


async def handle_review_command(update, context):
    bot_obj: TelegramBot = context.bot_data["bot_obj"]
    image_path = r"\\netappn1\SCS\50_Abteilungen\54_RSA\Sicherheitsforschung\smart_forrest_fire\Images\Smoke_T=0.5_VLM\Forestfire\cropped\20260526_065535_(55.1,0.0,754.0)_yes_mask0.jpg"

    if update.message is not None:
        await update.message.reply_text("Sending review image...")

    class _DummyCam:
        def translate_in_cam_preset(self, position):
            return position

    dummy_cam = _DummyCam()
    dummy_alarm_package = {
        "alert_id": "test123",
        "image_paths": [image_path],
        "pos_value": 1,
    }
    alert_id = await bot_obj.send_review(dummy_cam, alarm_package=dummy_alarm_package)


class TelegramBot:
    def __init__(self, bot_token, subscribers: list[int], review_threshold = 2):
        """
        Initialize the TelegramBot with a bot token and subscribers file.

        Args:
            bot_token (str): The Telegram bot token
            subscribers_file (str): Path to the JSON file containing subscriber chat IDs
        """
        if not bot_token:
            raise RuntimeError("BOT_TOKEN environment variable is required")

        self.bot_token: str = bot_token
        self.subscribers = subscribers
        self.bot = Bot(token=self.bot_token)
        self.review_threshold = review_threshold
        self.application = None
        # In-memory votes per alert. Cleared when a vote round finishes.
        self.review_votes: dict[str, dict[str, Any]] = {}
        self.alert_contexts: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _normalize_alert_id(alert_id: Optional[Union[int, str]] = None) -> str:
        if alert_id is None:
            return str(int(datetime.now().timestamp() * 1_000_000))
        return str(alert_id)

    def register_alert_context(self, alert_id: Union[int, str], **kwargs):
        normalized_id = self._normalize_alert_id(alert_id)
        current = self.alert_contexts.get(normalized_id, {})
        current.update(kwargs)
        self.alert_contexts[normalized_id] = current

    def create_application(self):
        """Build a polling application that routes callbacks back to this instance."""
        app = ApplicationBuilder().token(self.bot_token).build()
        app.bot_data["bot_obj"] = self
        app.add_handler(CallbackQueryHandler(handle_callback))
        app.add_handler(CommandHandler("review", handle_review_command))
        self.application = app
        return app

    def run_polling(self):
        """Run the Telegram polling loop for this bot instance."""
        app = self.application or self.create_application()
        app.run_polling()

    async def _broadcast_with_bot(self, bot, caption: str, image_path: str = ""):
        if not self.subscribers:
            logger.warning("There are no subscribers to send a message to. Aborting.")
            return

        logger.info(f"Starting broadcast to {len(self.subscribers)} subscribers.")

        for chat_id in self.subscribers:
            try:
                if image_path != "":
                    with open(image_path, 'rb') as image_file:
                        await bot.send_photo(
                            chat_id=chat_id,
                            photo=image_file,
                            caption=caption)
                else:
                    await bot.send_message(chat_id=chat_id, text=caption)
                logger.info(f"Successfully sent message to {chat_id}")
            except FileNotFoundError:
                logger.error(f"Error: The image file was not found at '{image_path}'. Aborting broadcast.")
                return
            except Exception as e:
                logger.error(f"Failed to send message to {chat_id}: {e}")

    async def broadcast(self, caption: str, image_path: str = ""):
        """
        Sends a photo with a caption or text-only message to all subscribers asynchronously.

        Args:
            caption (str): The text message to send. If image_path is provided, this becomes the caption.
            image_path (str, optional): The local file path to the image you want to send. If None, sends text only.
        """
        fresh_bot = Bot(token=self.bot_token)
        try:
            await self._broadcast_with_bot(fresh_bot, caption, image_path)
        finally:
            shutdown = getattr(fresh_bot, "shutdown", None)
            if shutdown is not None:
                await shutdown()

    @staticmethod
    def _build_detection_caption(position=None, temp=None, rh=None, precip=None):
        position_text = f"Pos. {position}" if position is not None else "Unknown Pos."
        weather_str = ""
        if temp is not None and rh is not None and precip is not None:
            weather_str = f" (Temp: {temp}°C, RH: {rh}%, Precip: {precip}mm)"

        return f"Detection at {position_text}! {weather_str}".rstrip()

    @staticmethod
    def _normalize_media_paths(image_paths: Union[str, Sequence[str]]) -> list[str]:
        if isinstance(image_paths, str):
            return [image_paths]
        return [str(path) for path in image_paths]

    async def send_review(
        self,
        cam,
        alarm_package: dict,
        # image_paths: Union[str, Sequence[str]] = None,
        # alert_id: Optional[Union[int, str]] = None,
        # position=None,
        # temp=None,
        # rh=None,
        # precip=None,
        # caption: Optional[str] = None,
    ):
        # Allow callers to provide an alarm_package dict or rely on previously
        # registered alert context. Values provided directly take precedence.
        # if alarm_package is not None:
        #     if image_paths is None:
        #         image_paths = alarm_package.get("image_paths")
        #     if alert_id is None:
        #         alert_id = alarm_package.get("alert_id")
        #     if position is None:
        #         position = alarm_package.get("pos_value") or alarm_package.get("position")
        #     if temp is None:
        #         temp = alarm_package.get("temp")
        #     if rh is None:
        #         rh = alarm_package.get("rh")
        #     if precip is None:
        #         precip = alarm_package.get("precip")
        #     if caption is None:
        #         caption = alarm_package.get("caption")

        alert_id = alarm_package.get("alert_id")
        image_paths = alarm_package.get("image_paths")
        position = alarm_package.get("pos_value")
        temp = alarm_package.get("weather", [None, None, None])[0]
        rh = alarm_package.get("weather", [None, None, None])[1]
        precip = alarm_package.get("weather", [None, None, None])[2]
        caption = alarm_package.get("caption")

        # If we have an alert_id and some values are still missing, try the
        # stored alert context that may have been registered earlier.
        # if alert_id is not None:
        #     normalized_id = self._normalize_alert_id(alert_id)
        #     ctx = self.alert_contexts.get(normalized_id, {})
        #     if image_paths is None:
        #         image_paths = ctx.get("image_paths")
        #     if position is None:
        #         position = ctx.get("pos_value") or ctx.get("position")
        #     if caption is None:
        #         caption = ctx.get("caption")

        position = cam.translate_in_cam_preset(position)
        alert_id = self._normalize_alert_id(alert_id)

        media_paths = self._normalize_media_paths(image_paths) if image_paths is not None else []
        if not media_paths:
            raise ValueError("At least one image path is required for send_review")

        review_caption = caption
        if review_caption is None:
            review_caption = self._build_detection_caption(position, temp, rh, precip)
        vote_prompt = "Is this fire? Please vote:"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Fire", callback_data=f"fire:{alert_id}"),
                InlineKeyboardButton("No Fire", callback_data=f"nofire:{alert_id}"),
                InlineKeyboardButton("Unclear", callback_data=f"unclear:{alert_id}")
            ]
        ])
        
        self.review_votes[alert_id] = {"fire": 0, "nofire": 0, "unclear": 0, "voters": set()}

        logger.info(f"Starting broadcast to {len(self.subscribers)} subscribers.")

        fresh_bot = Bot(token=self.bot_token)
        try:
            for chat_id in self.subscribers:
                try:
                    if len(media_paths) > 1:
                        with ExitStack() as stack:
                            media_group = [
                                InputMediaPhoto(
                                    media=stack.enter_context(open(path, "rb")),
                                    caption=review_caption,
                                )
                                if index == 0
                                else InputMediaPhoto(media=stack.enter_context(open(path, "rb")))
                                for index, path in enumerate(media_paths)
                            ]
                            await fresh_bot.send_media_group(chat_id=chat_id, media=media_group)
                    else:
                        with open(media_paths[0], "rb") as review_image:
                            await fresh_bot.send_photo(chat_id=chat_id, photo=review_image, caption=review_caption)

                    await fresh_bot.send_message(
                        chat_id=chat_id,
                        text=vote_prompt,
                        reply_markup=keyboard,
                    )
                except Exception as e:
                    logger.error(f"Failed to send review message to {chat_id}: {e}")
                    return
        finally:
            shutdown = getattr(fresh_bot, "shutdown", None)
            if shutdown is not None:
                await shutdown()

        return alert_id

    def send_review_sync(
        self,
        cam,
        # image_paths: Union[str, Sequence[str]] = None,
        # alert_id: Optional[Union[int, str]] = None,
        # position=None,
        # temp=None,
        # rh=None,
        # precip=None,
        # caption: Optional[str] = None,
        alarm_package: dict,
    ):
        return asyncio.run(
            self.send_review(
                cam=cam,
                # image_paths=image_paths,
                # alert_id=alert_id,
                # position=position,
                # temp=temp,
                # rh=rh,
                # precip=precip,
                # caption=caption,
                alarm_package=alarm_package,
            )
        )

    def broadcast_sync(self, caption: str, image_path: str = ""):
        """
        Synchronous wrapper for the broadcast method.
        This allows non-async classes to send broadcasts.

        Args:
            caption (str): The text message to send. If image_path is provided, this becomes the caption.
            image_path (str, optional): The local file path to the image you want to send. If None, sends text only.
        """
        async def run_with_fresh_bot():
            fresh_bot = Bot(token=self.bot_token)
            try:
                await self._broadcast_with_bot(fresh_bot, caption, image_path)
            finally:
                shutdown = getattr(fresh_bot, "shutdown", None)
                if shutdown is not None:
                    await shutdown()

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
                        return new_loop.run_until_complete(run_with_fresh_bot())
                    finally:
                        new_loop.close()

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_thread)
                    return future.result()
            else:
                # If no loop is running, we can use the current loop
                return loop.run_until_complete(run_with_fresh_bot())
        except RuntimeError:
            # No event loop exists, create a new one
            return asyncio.run(run_with_fresh_bot())
        
    async def single_broadcast(self, chat_id: int, caption: str, image_path: str = ""):
        """
        Send a single message to a specific chat ID.

        Args:
            chat_id (int): The Telegram chat ID to send the message to
            caption (str): The text message to send. If image_path is provided, this becomes the caption.
            image_path (str, optional): The local file path to the image you want to send. If None, sends text only.
        """
        try:
            if image_path != "":
                with open(image_path, 'rb') as image_file:
                    await self.bot.send_photo(chat_id=chat_id, photo=image_file, caption=caption)
            else:
                await self.bot.send_message(chat_id=chat_id, text=caption)
            logger.info(f"Successfully sent message to {chat_id}")
        except FileNotFoundError:
            logger.error(f"Error: The image file was not found at '{image_path}'. Aborting message.")
        except Exception as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")

    async def single_video(self, chat_id: int, caption: str, video_path: str):
        try:
            with open(video_path, "rb") as video_file:
                await self.bot.send_video(chat_id=chat_id, video=video_file, caption=caption)
            logger.info(f"Successfully sent video to {chat_id}")
        except FileNotFoundError:
            logger.error(f"Error: The video file was not found at '{video_path}'. Aborting message.")
        except Exception as e:
            logger.error(f"Failed to send video to {chat_id}: {e}")

    def detection_alert(self, cam, alarm, position, image_path, temp=None, rh=None, precip=None):
        """
        Send an alert message to all subscribers based on the alarm status.

        Args:
            cam (VAPIXCamera): The camera instance
            alarm (bool): Whether an alarm condition was detected
            position (int): preset position no
            image_path (str): The local file path to the image you want to send
            temp (float, optional): Temperature in °C
            rh (float, optional): Relative humidity in %
            precip (float, optional): Precipitation in mm
        """
        if alarm==False:
            return
        position = cam.translate_in_cam_preset(position)
        caption = self._build_detection_caption(position, temp, rh, precip)
        
        self.broadcast_sync(caption, image_path)


if __name__ == "__main__":
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    bot_obj = TelegramBot(BOT_TOKEN, subscribers = [5894386665])

    import threading, time

    polling_thread = threading.Thread(target=bot_obj.run_polling, daemon=True)
    polling_thread.start()

    review_image_paths = [
        r"\\netappn1\SCS\50_Abteilungen\54_RSA\Sicherheitsforschung\smart_forrest_fire\Images\Smoke_T=0.5_VLM\Forestfire\cropped\20260526_065535_(55.1,0.0,754.0)_yes_mask0.jpg"
    ]
    try:
        while True:
            if review_image_paths:
                asyncio.run(bot_obj.single_video(chat_id=5894386665, caption="Test video", video_path=r"\\netappn1\SCS\50_Abteilungen\54_RSA\Sicherheitsforschung\smart_forrest_fire\Images\Smoke_T=0.5_VLM\Forestfire\video\12345.mp4"))
            time.sleep(20)  # Wait for 20 seconds before sending the next review (for testing purposes)
    except KeyboardInterrupt:
        logger.info("Stopping telegram bot test harness after Ctrl+C.")
