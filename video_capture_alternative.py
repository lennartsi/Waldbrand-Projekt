    def save_http_media_copy(
        self,
        media_url=None,
        output_file="camera_h264_http.mp4",
        duration_seconds=10,
        request_timeout=10,
        chunk_size=64 * 1024,
        finalize_mp4_index=True,
    ):
        """
        Save the camera HTTP media stream without re-encoding.

        This method writes the incoming bytes directly to disk, so the camera
        keeps full control of compression (for example H.264).

        Args:
            media_url (str): Full media.cgi URL. If None, a default H.264 MP4
                URL is built.
            output_file (str): Output file path.
            duration_seconds (int): Capture duration in seconds.
            request_timeout (int): HTTP request timeout in seconds.
            chunk_size (int): Bytes per streamed chunk.
            finalize_mp4_index (bool): If True and output is MP4, remux the
                captured bytes to write a proper seek index without re-encoding.
        """

        if media_url is None:
            media_url = (
                f"{self.__protocol}://{self.__ip}/axis-cgi/media.cgi"
                "?videocodec=h264&container=mp4"
            )

        start_time = time.monotonic()
        total_bytes = 0
        raw_output_file = f"{output_file}.part"

        response = requests.get(
            media_url,
            auth=auth.HTTPDigestAuth(self.__username, self.__password),
            stream=True,
            timeout=request_timeout,
            verify=False,
        )
        response.raise_for_status()

        try:
            with open(raw_output_file, "wb") as out_file:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if not chunk:
                        continue

                    out_file.write(chunk)
                    total_bytes += len(chunk)

                    if time.monotonic() - start_time >= duration_seconds:
                        break
        finally:
            response.close()

        if total_bytes == 0:
            raise RuntimeError("No bytes were received from media.cgi stream")

        finalized = False
        if finalize_mp4_index and output_file.lower().endswith(".mp4"):
            try:
                self.__remux_copy_to_mp4(raw_output_file, output_file)
            except Exception as exc:
                os.replace(raw_output_file, output_file)
                print(f"Warning: MP4 index finalization failed ({exc}). Kept raw stream capture.")
            else:
                remux_size = os.path.getsize(output_file) if os.path.exists(output_file) else 0
                # Guard against near-empty remux output; prefer playable raw capture.
                if remux_size < max(32 * 1024, int(total_bytes * 0.05)):
                    os.replace(raw_output_file, output_file)
                    print(
                        "Warning: MP4 index finalization produced a very small file "
                        f"({remux_size} bytes). Kept raw stream capture instead."
                    )
                else:
                    finalized = True
                    if os.path.exists(raw_output_file):
                        os.remove(raw_output_file)
        else:
            os.replace(raw_output_file, output_file)

        if finalized:
            print(
                f"Saved finalized HTTP media copy to: {output_file} "
                f"({total_bytes} bytes captured, duration ~{duration_seconds}s)"
            )
        else:
            print(
                f"Saved HTTP media copy to: {output_file} "
                f"({total_bytes} bytes captured, duration ~{duration_seconds}s)"
            )
        return output_file

    @staticmethod
    def __remux_copy_to_mp4(input_file, output_file):
        """
        Remux captured media into MP4 without re-encoding.
        """

        input_container = av.open(input_file, mode="r")
        output_container = av.open(output_file, mode="w")
        packets_written = 0

        try:
            stream_map = {}
            for stream in input_container.streams:
                if stream.type in {"video", "audio"}:
                    codec_name = stream.codec_context.name
                    if not codec_name:
                        continue

                    if stream.type == "video":
                        rate = stream.average_rate
                    else:
                        rate = stream.codec_context.sample_rate

                    # Some PyAV versions need codec_name positionally even when
                    # using template-based stream cloning.
                    try:
                        if rate:
                            out_stream = output_container.add_stream(codec_name, rate=rate, template=stream)
                        else:
                            out_stream = output_container.add_stream(codec_name, template=stream)
                    except Exception:
                        if rate:
                            out_stream = output_container.add_stream(codec_name, rate=rate)
                        else:
                            out_stream = output_container.add_stream(codec_name)

                    # Keep timing/codec metadata aligned when supported.
                    try:
                        out_stream.time_base = stream.time_base
                    except Exception:
                        pass
                    try:
                        out_stream.codec_context.extradata = stream.codec_context.extradata
                    except Exception:
                        pass

                    stream_map[stream.index] = out_stream

            if not stream_map:
                raise RuntimeError("No audio/video streams found for MP4 remux")

            for packet in input_container.demux():
                target_stream = stream_map.get(packet.stream.index)
                if target_stream is None:
                    continue
                if packet.dts is None and packet.pts is None:
                    continue

                packet.stream = target_stream
                output_container.mux(packet)
                packets_written += 1

            if packets_written == 0:
                raise RuntimeError("No packets were written during MP4 remux")
        finally:
            output_container.close()
            input_container.close()

    @staticmethod
    def __extract_mjpeg_frames(buffer: bytes):
        frames = []

        while True:
            start = buffer.find(b"\xff\xd8")
            if start == -1:
                return frames, buffer

            end = buffer.find(b"\xff\xd9", start + 2)
            if end == -1:
                return frames, buffer[start:]

            frames.append(buffer[start:end + 2])
            buffer = buffer[end + 2:]

    @staticmethod
    def __decode_mjpeg_frame(frame_bytes: bytes):
        frame_array = np.frombuffer(frame_bytes, dtype=np.uint8)
        frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
        if frame is None:
            raise RuntimeError("Failed to decode MJPEG frame")
        return frame

    def save_mjpeg_clip(
        self,
        stream_url=None,
        output_file="output.mp4",
        duration_seconds=10,
        request_timeout=10,
        target_fps=15,
        output_codec="h264",
    ):
        stream_url = stream_url or self.__mjpeg_url

        response = requests.get(
            stream_url,
            auth=auth.HTTPDigestAuth(self.__username, self.__password),
            stream=True,
            timeout=request_timeout,
            verify=False,
        )
        response.raise_for_status()

        frames = []
        buffer = b""
        start_time = time.monotonic()

        try:
            for chunk in response.iter_content(chunk_size=4096):
                if not chunk:
                    continue

                buffer += chunk
                extracted_frames, buffer = self.__extract_mjpeg_frames(buffer)

                for frame_bytes in extracted_frames:
                    frame = self.__decode_mjpeg_frame(frame_bytes)
                    frames.append(frame)

                if time.monotonic() - start_time >= duration_seconds:
                    break
        finally:
            response.close()

        if not frames:
            raise RuntimeError("No MJPEG frames were decoded from the stream")

        # Resample frames so the output length is approximately duration_seconds.
        desired_count = max(1, int(round(duration_seconds * float(target_fps))))
        total_captured = len(frames)

        if total_captured >= desired_count:
            # pick evenly spaced frames from captured set
            indices = [int(i * total_captured / desired_count) for i in range(desired_count)]
            write_frames = [frames[idx] for idx in indices]
        else:
            # not enough frames captured; repeat last frame to pad
            write_frames = list(frames)
            last = frames[-1]
            while len(write_frames) < desired_count:
                write_frames.append(last)

        height, width = write_frames[0].shape[:2]
        fps = float(target_fps)
        if fps <= 0:
            raise ValueError("target_fps must be greater than zero")

        codec_name = (output_codec or "").strip().lower()
        if codec_name in {"h264", "h.264", "avc1"}:
            fourcc_candidates = ["avc1", "H264", "X264", "mp4v"]
        else:
            fourcc_candidates = [output_codec, "mp4v"]

        out = None
        used_codec = None
        for codec in fourcc_candidates:
            if not codec:
                continue
            fourcc = getattr(cv2, "VideoWriter_fourcc")(*codec)
            candidate = cv2.VideoWriter(output_file, fourcc, fps, (width, height))
            if candidate.isOpened():
                out = candidate
                used_codec = codec
                break

        if out is None:
            raise RuntimeError(
                f"Could not open video writer for {output_file} using codec preferences {fourcc_candidates}"
            )

        try:
            for frame in write_frames:
                if frame.shape[:2] != (height, width):
                    frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
                out.write(frame)
        finally:
            out.release()

        if used_codec and used_codec.lower() not in {"avc1", "h264", "x264"} and codec_name in {"h264", "h.264", "avc1"}:
            print(
                f"Saved HTTP stream clip to: {output_file} at {target_fps} fps "
                f"(duration ~{duration_seconds}s, requested codec: {output_codec}, actual codec: {used_codec})"
            )
            print("Warning: H.264 was not available in this OpenCV build, so the file was written with a fallback codec.")
        else:
            print(
                f"Saved HTTP stream clip to: {output_file} at {target_fps} fps "
                f"(duration ~{duration_seconds}s, codec: {used_codec})"
            )
        return output_file